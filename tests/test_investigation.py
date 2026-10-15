"""Investigation orchestration: fake model transport, fake arena, fake baselines. No MuJoCo, no network."""
import json
import os
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from creature_forge import interventions as iv
from creature_forge import investigation as inv
from creature_forge.creatures import CreatureStore, content_hash, seed_block
from creature_forge.forge_ai import make_client
from creature_forge.inference_ledger import Caps, InferenceLedger
from creature_forge.jobs import JobCancelled
from creature_forge.nebius import NebiusError
from creature_forge.sandbox import SandboxBody

VERIFIED, NOT_VERIFIED = "VERIFIED_IMPROVEMENT", "NOT_VERIFIED"
LIVE_ENV = {"CREATURE_FORGE_ENABLE_LIVE": "1"}


def spec_for(kind="push", n=4, base=100):
    return {"kind": kind, "seeds": list(range(base, base + n)), "duration": 5.0, "perturb": 0.02, "target_force": 10.0,
            "push_time": 1.0, "push_duration": 0.15, "max_force": 80.0, "start": "drawn", "settle_s": 0.3}


def challenge_record(version, cid, spec=None, run_id=None, extra_creature=None):
    spec = spec or spec_for()
    per = [{"seed": s, "outcome": "FAIL", "score": 2.0 + i, "metrics": {"critical_force_bwd": 2.0 + i, "survival_s": 1.0},
            "events": [], "rollouts": 3, "error": None} for i, s in enumerate(spec["seeds"])]
    return {"run_id": run_id, "spec": spec, "body": version["body"], "controllers": version["controllers"],
            "controller": {"stand": {"kind": "stand-pd", "params": version["controllers"]["stand"], "edited": False}},
            "per_seed": per, "outcome": "FAIL", "summary": {}, "forensics": {"worst_seed": spec["seeds"][0], "note": "fell backwards"},
            "rollouts": len(per) * 3, "wall_s": 0.1,
            "creature": {"cid": cid, "n": version["n"], "content_hash": version["content_hash"], **(extra_creature or {})}}


AI_SOURCES = ("nemotron", "scripted_mock")   # scripted runs label AI arms scripted_mock, never nemotron

class FakeArena:
    """Same shape as arena.run_arena's record. `plan`: list (one per call) of {arm_id: status}; default AI arms VERIFIED."""

    def __init__(self, plan=None, rollouts=100, fail=None, progress_calls=1):
        self.calls, self.plan, self.rollouts, self.fail, self.progress_calls = [], plan, rollouts, fail, progress_calls

    def __call__(self, version, kind, arms, cfg, *, pool=None, progress=None, emit=None, spec_overrides=None):
        self.calls.append({"version": version, "kind": kind, "arms": arms, "cfg": cfg, "spec_overrides": spec_overrides, "emit": emit})
        if self.fail:
            raise RuntimeError(self.fail)
        for i in range(self.progress_calls):
            progress(i + 1, self.progress_calls)
        plan = (self.plan[len(self.calls) - 1] if self.plan else None)
        out_arms, verdicts = [], {}
        for a in arms:
            body, ctrl = iv.apply_edits(version, [iv.Edit.from_dict(e) for e in a["edits"]])
            out_arms.append({**a, "body": body, "controllers": ctrl, "category": "x"})
            if a["arm_id"] == "original":
                continue
            default = VERIFIED if a["source"] in AI_SOURCES else NOT_VERIFIED
            status = (plan or {}).get(a["arm_id"], default if plan is None else NOT_VERIFIED)
            verdicts[a["arm_id"]] = {"status": status, "rule": "verdict_v1", "n": 24, "wins": 20, "losses": 2, "ties": 2,
                                     "median_diff": 4.0 if a["source"] in AI_SOURCES else 0.5, "p_one_sided": 0.001, "reasons": []}
        return {"arms": out_arms, "screening": {"scores": {}}, "selection": {"best_ai": "ai:P1"}, "validation": {"per_seed": {}},
                "verdicts": verdicts, "rollouts": self.rollouts, "wall_s": 0.5}


class FakeBaselines:
    def __init__(self, twin=True, heuristic=True):
        self.twin, self.heur, self.twin_calls = twin, heuristic, []

    def matched_random(self, version, kind, ai_edits, rng):
        self.twin_calls.append((len(ai_edits), rng.random()))
        return [iv.Edit("foot_friction", "scale", 1.1, "both")] if self.twin else None

    def heuristic_fn(self, version, kind, challenge_result):
        return [iv.Edit("torque_limit", "scale", 1.2, "both")] if self.heur else None

    def seed_sets(self, cid, n, round_, sizes):
        return {r: seed_block(cid, n, round_, r, k) for r, k in sizes.items()}

    def fns(self):
        return {"matched_random": self.matched_random, "heuristic": self.heuristic_fn, "seed_sets": self.seed_sets}


class RecordingScripted(inv.ScriptedTransport):
    def __init__(self, *a, mutate=None, status=None, **k):
        super().__init__(*a, **k)
        self.mutate, self.status = mutate, status

    def reply(self):
        r = super().reply()
        return self.mutate(r) if self.mutate else r

    def __call__(self, url, headers, body, timeout):
        if self.status is not None:
            self.requests += 1
            raise NebiusError(f"HTTP {self.status}: upstream error")
        return super().__call__(url, headers, body, timeout)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "forge"
        self.store = CreatureStore(self.dir)
        self.cr = self.store.create(name="Stubby", body=SandboxBody().as_dict(), mode="experimental", drawing={})
        self.cid = self.cr["id"]
        self.version = self.store.version(self.cid, 1)
        self.run_id = self.write_run(self.version)
        self.arena, self.bl = FakeArena(), FakeBaselines()
        self.events = []
        self.transports = []
        self.fixed = {"code_fn": lambda: {"commit": "abc", "dirty": False}}

    def write_run(self, version, spec=None, extra_creature=None):
        rid = "r-" + secrets.token_hex(4)
        d = self.dir / "runs"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{rid}.json").write_text(json.dumps(challenge_record(version, self.cid, spec, rid, extra_creature)), encoding="utf-8")
        return rid

    def emit(self, type_, data):
        self.events.append((type_, data))

    def factory(self, **tkw):
        def make(cfg, *, mode, max_requests, evidence, version, challenge_kind, **_):
            t = RecordingScripted(evidence, version, challenge_kind, **tkw)
            self.transports.append(t)
            return make_client(cfg, transport=t, api_key="k", base_url="http://x.invalid", max_requests=max_requests)
        return make

    def run_inv(self, mode="scripted", **kw):
        base = dict(mode=mode, forge_dir=self.dir, arena_runner=self.arena, baseline_fns=self.bl.fns(), emit=self.emit,
                    progress=lambda *a: None, **self.fixed)
        base.update(kw)
        return inv.run_investigation(self.store, self.cid, 1, self.run_id, **base)


class LiveGateTests(Base):
    def live_ledger(self, **caps):
        return InferenceLedger(self.dir / "live_ledger.jsonl", caps=Caps(**caps) if caps else None)

    def test_flag_missing_refuses_before_any_transport_call(self):
        env = {k: v for k, v in os.environ.items() if k != "CREATURE_FORGE_ENABLE_LIVE"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(inv, "api_key_present", return_value=True):
            with self.assertRaisesRegex(inv.LiveRefused, "CREATURE_FORGE_ENABLE_LIVE"):
                self.run_inv("live", ledger=self.live_ledger(), client_factory=self.factory())
        self.assertEqual(self.transports, [])
        self.assertFalse((self.dir / "investigations").exists())

    def test_missing_key_refuses(self):
        with mock.patch.dict(os.environ, LIVE_ENV), mock.patch.object(inv, "api_key_present", return_value=False):
            with self.assertRaisesRegex(inv.LiveRefused, "API key"):
                self.run_inv("live", ledger=self.live_ledger(), client_factory=self.factory())
        self.assertEqual(self.transports, [])

    def test_no_ledger_headroom_refuses_before_any_call(self):
        with mock.patch.dict(os.environ, LIVE_ENV), mock.patch.object(inv, "api_key_present", return_value=True):
            with self.assertRaisesRegex(inv.LiveRefused, "spend cap"):
                self.run_inv("live", ledger=self.live_ledger(max_usd=0.0001), client_factory=self.factory())
            with self.assertRaisesRegex(inv.LiveRefused, "request cap"):
                self.run_inv("live", ledger=self.live_ledger(max_requests=0), client_factory=self.factory())
        self.assertEqual(self.transports, [])

    def test_live_with_everything_in_place_is_labelled_live(self):
        led = self.live_ledger()
        with mock.patch.dict(os.environ, LIVE_ENV), mock.patch.object(inv, "api_key_present", return_value=True):
            rec = self.run_inv("live", ledger=led, client_factory=self.factory())
        self.assertEqual((rec["mode"], rec["provenance"]), ("live", "LIVE"))
        self.assertEqual(rec["status"], "done")
        self.assertEqual(led.status()["requests"], 1)  # the live ledger was used

    def test_ledger_cap_mid_run_refuses_the_repair_before_the_transport(self):
        led = self.live_ledger(max_requests=1)
        bad = lambda r: {**r, "proposals": [{**p, "edits": [{"param": "foot_length", "op": "scale", "value": 3.0, "target": "both"}]}
                                            for p in r["proposals"]]}
        with mock.patch.dict(os.environ, LIVE_ENV), mock.patch.object(inv, "api_key_present", return_value=True):
            rec = self.run_inv("live", ledger=led, client_factory=self.factory(mutate=bad))
        self.assertEqual(self.transports[0].requests, 1)  # the second request never reached the transport
        self.assertTrue(rec["model_calls"][-1]["budget_refused"])
        self.assertEqual(rec["status"], "model_failed")
        self.assertEqual(led.status()["requests"], 1)
        self.assertFalse([a for a in rec["arms"] if a["source"] in AI_SOURCES])

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_inv("mock")


class ScriptedTests(Base):
    def test_scripted_provenance_is_everywhere_and_never_live(self):
        rec = self.run_inv()
        self.assertEqual((rec["mode"], rec["provenance"], rec["status"]), ("scripted", "SCRIPTED_MOCK", "done"))
        self.assertTrue(all(a["provenance"] == "SCRIPTED_MOCK" for a in rec["arms"]))
        self.assertTrue(all(v["provenance"] == "SCRIPTED_MOCK" for v in rec["verdicts"].values()))
        self.assertTrue(self.events and all(d["provenance"] == "SCRIPTED_MOCK" for _, d in self.events))
        self.assertTrue(all(c["model"] == inv.SCRIPTED_MODEL for c in rec["model_calls"]))
        self.assertNotIn("LIVE", json.dumps(rec["provenance"]))
        # scripted calls never touch the real ledger file
        self.assertFalse((self.dir / "inference_ledger.jsonl").exists())
        self.assertTrue((self.dir / "scripted_inference_ledger.jsonl").exists())

    def test_scripted_reply_cites_only_real_evidence_paths(self):
        rec = self.run_inv()
        for h in rec["validation"]["hypotheses"]:
            self.assertEqual(h["status"], "accepted", h["reasons"])
        self.assertEqual(len(rec["model_calls"]), 1)

    def test_record_has_exactly_the_contract_keys_and_is_persisted(self):
        rec = self.run_inv()
        self.assertEqual(set(rec), set(inv.RECORD_KEYS))
        on_disk = json.loads((self.dir / "investigations" / f"{rec['id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(list(on_disk), list(inv.RECORD_KEYS))
        self.assertEqual(set(on_disk["budget"]), {"rollouts", "wall_s", "calls", "tokens", "usd"})
        self.assertEqual(on_disk["creature"]["content_hash"], self.version["content_hash"])
        self.assertEqual(on_disk["challenge_run_id"], self.run_id)
        self.assertEqual(on_disk["code"], {"commit": "abc", "dirty": False})
        self.assertEqual(on_disk["budget"]["rollouts"], 100)
        self.assertEqual(on_disk["budget"]["calls"], 1)

    def test_arms_original_ai_twins_and_heuristic(self):
        rec = self.run_inv()
        ids = [a["arm_id"] for a in rec["arms"]]
        self.assertEqual(ids, ["original", "ai:P1", "ai:P2", "random:P1", "random:P2", "heuristic"])
        by = {a["arm_id"]: a for a in rec["arms"]}
        self.assertEqual([by[i]["source"] for i in ids], ["original", "scripted_mock", "scripted_mock", "random_baseline", "random_baseline", "heuristic"])
        self.assertEqual(by["original"]["edits"], [])
        self.assertEqual(by["random:P1"]["proposal_id"], "P1")
        self.assertEqual(by["heuristic"]["edits"][0]["param"], "torque_limit")
        sent = self.arena.calls[0]
        self.assertEqual([a["arm_id"] for a in sent["arms"]], ids)
        self.assertEqual(sent["kind"], "push")
        self.assertNotIn("seeds", sent["spec_overrides"])
        self.assertEqual(sent["spec_overrides"]["target_force"], 10.0)
        self.assertTrue(all(a["retune"] is False for a in sent["arms"]))
        self.assertEqual(self.bl.twin_calls[0][0], len(by["ai:P1"]["edits"]))

    def test_twin_rng_is_seeded_by_investigation_and_proposal(self):
        self.run_inv(investigation_id="i-aaaaaa000001")
        first = list(self.bl.twin_calls)
        self.bl.twin_calls.clear()
        self.run_inv(investigation_id="i-aaaaaa000001")
        self.assertEqual(first, self.bl.twin_calls)
        self.bl.twin_calls.clear()
        self.run_inv(investigation_id="i-bbbbbb000002")
        self.assertNotEqual(first, self.bl.twin_calls)

    def test_seed_sets_are_disjoint_from_each_other_and_the_challenge(self):
        rec = self.run_inv()
        sets = [set(rec["seeds"][k]) for k in ("train", "screen", "validate")]
        self.assertEqual(sum(len(s) for s in sets), len(set().union(*sets)))
        self.assertFalse(set().union(*sets) & set(rec["spec"]["seeds"]))
        self.assertEqual((len(sets[0]), len(sets[1]), len(sets[2])), tuple(inv.SIZES_BY_KIND["push"][k] for k in ("train", "screen", "validate")))
        cfg = self.arena.calls[0]["cfg"]
        self.assertEqual(set(cfg.screen_seeds), sets[1])
        self.assertEqual(cfg.retune_budget, 0)

    def test_colliding_seed_blocks_bump_the_round(self):
        spec = spec_for(base=0)
        calls = []

        def seeds(cid, n, r, sizes):
            calls.append(r)
            return {"train": (1, 2, 3), "screen": (r, r + 1), "validate": (500 + r, 501 + r)} if r < 2000 else self.bl.seed_sets(cid, n, r, sizes)
        self.bl.seed_sets = seeds
        self.run_id = self.write_run(self.version, spec={**spec_for(), "seeds": [0]})
        rec = self.run_inv()  # round 1: screen=(1,2) collides with train -> bump to 1001
        self.assertEqual(calls, [1, 1001])
        self.assertEqual(rec["seeds"]["round_used"], 1001)

    def test_unavailable_twin_is_recorded_and_not_sent_to_the_arena(self):
        self.bl.twin = False
        rec = self.run_inv()
        tw = [a for a in rec["arms"] if a["arm_id"].startswith("random:")]
        self.assertTrue(tw and all(a.get("unavailable") for a in tw))
        self.assertFalse([a for a in self.arena.calls[0]["arms"] if a["arm_id"].startswith("random:")])

    def test_events_cover_the_pipeline(self):
        self.run_inv()
        types = [t for t, _ in self.events]
        for need in ("phase", "model_request", "model_response", "validation", "arm_result", "verdict"):
            self.assertIn(need, types)
        self.assertLess(types.index("model_request"), types.index("model_response"))
        self.assertLess(types.index("validation"), types.index("verdict"))


class FailureTests(Base):
    def test_model_failure_keeps_baselines_and_no_ai_arm(self):
        rec = self.run_inv(client_factory=self.factory(status=500))
        self.assertEqual(rec["status"], "model_failed")
        self.assertIn("HTTP 500", rec["error"])
        self.assertEqual([a["arm_id"] for a in rec["arms"]], ["original", "heuristic"])
        self.assertTrue(all(a["source"] not in AI_SOURCES for a in rec["arms"]))
        self.assertEqual(rec["verdicts"]["heuristic"]["source"], "heuristic")
        self.assertEqual(len(self.arena.calls), 1)
        self.assertEqual(self.transports[0].requests, 1)  # a failed call is never retried

    def test_all_proposals_rejected_is_no_valid_proposals_with_baselines(self):
        bad = lambda r: {**r, "proposals": [{**p, "edits": [{"param": "foot_length", "op": "scale", "value": 3.0, "target": "both"}]}
                                            for p in r["proposals"]]}
        rec = self.run_inv(client_factory=self.factory(mutate=bad))
        self.assertEqual(rec["status"], "no_valid_proposals")
        self.assertEqual([a["arm_id"] for a in rec["arms"]], ["original", "heuristic"])
        self.assertEqual(len(rec["model_calls"]), 2)  # one repair, no more
        self.assertTrue(all(p["status"] == "rejected" for p in rec["validation"]["proposals"]))
        self.assertIn("heuristic", rec["verdicts"])

    def test_nothing_comparable_skips_the_arena_and_says_so(self):
        self.bl.heur = False
        rec = self.run_inv(client_factory=self.factory(status=500))
        self.assertEqual(self.arena.calls, [])
        self.assertEqual(rec["status"], "model_failed")
        self.assertIn("arena was not run", rec["error"])
        self.assertEqual(rec["verdicts"], {})

    def test_arena_error_is_recorded_not_papered_over(self):
        self.arena.fail = "pool crashed"
        rec = self.run_inv()
        self.assertEqual(rec["status"], "failed")
        self.assertIn("arena failed: RuntimeError: pool crashed", rec["error"])
        self.assertEqual(rec["verdicts"], {})
        self.assertIsNone(rec["screening"])
        self.assertTrue((self.dir / "investigations" / f"{rec['id']}.json").is_file())

    def test_cancel_during_the_arena_records_cancelled(self):
        def progress(*a):
            raise JobCancelled()
        rec = self.run_inv(progress=progress)
        self.assertEqual(rec["status"], "cancelled")
        self.assertEqual(rec["verdicts"], {})
        self.assertEqual(json.loads((self.dir / "investigations" / f"{rec['id']}.json").read_text(encoding="utf-8"))["status"], "cancelled")

    def test_cancel_flag_before_the_arena(self):
        rec = self.run_inv(cancelled=lambda: True)
        self.assertEqual(rec["status"], "cancelled")
        self.assertEqual(self.arena.calls, [])


class AcceptTests(Base):
    def test_accept_only_verified_with_lineage_and_attribution(self):
        self.arena.plan = [{"ai:P1": VERIFIED, "ai:P2": NOT_VERIFIED, "random:P1": VERIFIED, "heuristic": "WORSE"}]
        rec = self.run_inv()
        with self.assertRaisesRegex(inv.AcceptRefused, "NOT_VERIFIED"):
            inv.build_accept(self.store, self.cid, rec, "ai:P2")
        with self.assertRaisesRegex(inv.AcceptRefused, "WORSE"):
            inv.build_accept(self.store, self.cid, rec, "heuristic")
        with self.assertRaisesRegex(inv.AcceptRefused, "no such arm"):
            inv.build_accept(self.store, self.cid, rec, "ai:P9")
        parent_n, body, ctrl, change = inv.build_accept(self.store, self.cid, rec, "ai:P1")
        self.assertEqual(parent_n, 1)
        self.assertEqual(change["source"], "scripted_mock")  # a scripted reply is never attributed to the model
        self.assertEqual(change["provenance"], "SCRIPTED_MOCK")
        self.assertEqual(change["model"], inv.SCRIPTED_MODEL)
        self.assertIn("SCRIPTED MOCK hypothesis", change["rationale"])
        self.assertEqual((change["investigation_id"], change["arm_id"]), (rec["id"], "ai:P1"))
        out = self.store.accept(self.cid, parent_n=parent_n, body=body, controllers=ctrl, change=change)
        self.assertEqual(out["current"], 2)
        v2 = out["versions"][1]
        self.assertEqual((v2["parent"], v2["origin"], v2["change"]["verdict"]["status"]), (1, "ai_accepted", VERIFIED))
        self.assertEqual(v2["change"]["category"], iv.category([iv.Edit.from_dict(e) for e in change["edits"]]))
        # random twin: accepted but attributed honestly
        _, _, _, c2 = inv.build_accept(self.store, self.cid, rec, "random:P1")
        self.assertEqual((c2["source"], c2["model"]), ("random_baseline", None))
        self.assertNotIn("model hypothesis", c2["rationale"].lower())

    def test_live_ai_arm_is_attributed_to_nemotron(self):
        rec = self.run_inv()
        rec["provenance"] = "LIVE"
        _, _, _, change = inv.build_accept(self.store, self.cid, rec, "ai:P1")
        self.assertEqual(change["source"], "nemotron")

    def test_wrong_creature_and_hypothetical_parent_are_refused(self):
        rec = self.run_inv()
        with self.assertRaisesRegex(inv.AcceptRefused, "belongs to creature"):
            inv.build_accept(self.store, "c-00000000", rec, "ai:P1")
        rec["creature"]["hypothetical_parent"] = {"investigation_id": "i-x", "arm_id": "ai:P1"}
        rec["creature"]["content_hash"] = "deadbeef"
        with self.assertRaisesRegex(inv.AcceptRefused, "hypothetical parent"):
            inv.build_accept(self.store, self.cid, rec, "ai:P1")


class LoopTests(Base):
    def setUp(self):
        super().setUp()
        self.challenge_calls = []

    def challenge_runner(self, body, controllers, spec, progress):
        self.challenge_calls.append({"body": body, "spec": spec})
        v = {**self.version, "body": body, "controllers": controllers}
        rec = challenge_record(v, self.cid, spec)
        return {k: rec[k] for k in ("spec", "controller", "per_seed", "outcome", "summary", "forensics", "rollouts", "wall_s")}

    def loop(self, **kw):
        base = dict(mode="scripted", forge_dir=self.dir, arena_runner=self.arena, baseline_fns=self.bl.fns(),
                    challenge_runner=self.challenge_runner, emit=self.emit, progress=lambda *a: None, **self.fixed)
        base.update(kw)
        return inv.run_loop(self.store, self.cid, 1, self.run_id, **base)

    def test_stops_after_a_round_without_a_verified_ai_arm(self):
        self.arena.plan = [{"ai:P1": NOT_VERIFIED, "ai:P2": NOT_VERIFIED, "heuristic": VERIFIED}]
        out = self.loop()
        self.assertEqual((len(out["rounds"]), out["stop_reason"]), (1, "no_verified_arm"))  # a verified baseline does not continue the AI loop
        self.assertIsNone(out["best"])

    def test_three_rounds_history_hypothetical_parent_and_no_auto_accept(self):
        out = self.loop()
        self.assertEqual((len(out["rounds"]), out["stop_reason"]), (3, "max_rounds"))
        self.assertFalse(out["auto_accepted"])
        self.assertEqual(len(self.store.get(self.cid)["versions"]), 1)  # nothing was accepted
        self.assertEqual(self.store.get(self.cid)["current"], 1)
        r1, r2, r3 = [inv.load_investigation(self.dir, r["investigation_id"]) for r in out["rounds"]]
        self.assertIsNone(r1["creature"]["hypothetical_parent"])
        self.assertEqual(r2["creature"]["hypothetical_parent"]["investigation_id"], r1["id"])
        self.assertEqual(r3["creature"]["hypothetical_parent"]["investigation_id"], r2["id"])
        self.assertEqual([r["creature"]["round"] for r in (r1, r2, r3)], [1, 2, 3])
        self.assertNotEqual(r2["creature"]["content_hash"], r1["creature"]["content_hash"])
        self.assertNotEqual(r2["challenge_run_id"], r1["challenge_run_id"])
        self.assertTrue((self.dir / "runs" / f"{r2['challenge_run_id']}.json").is_file())
        self.assertNotIn("history", r1["evidence"])
        hist = r2["evidence"]["history"]
        self.assertEqual(hist[0]["round"], 1)
        self.assertEqual(hist[0]["verdict"], VERIFIED)
        self.assertEqual(len(r3["evidence"]["history"]), 2)
        # round 2's challenge ran on the proposed body, with fresh seeds, through the injected runner
        arm = next(a for a in r1["arms"] if a["arm_id"] == out["rounds"][0]["best_verified_arm"])
        self.assertEqual(self.challenge_calls[0]["body"], arm["body"])
        self.assertFalse(set(self.challenge_calls[0]["spec"]["seeds"]) & set(r1["spec"]["seeds"]))
        self.assertEqual(out["best"]["round"], 3)
        self.assertTrue(all(e[1]["provenance"] == "SCRIPTED_MOCK" for e in self.events))

    def test_max_rollouts_stops_the_loop(self):
        self.arena.rollouts = 2000
        out = self.loop()
        self.assertEqual((len(out["rounds"]), out["stop_reason"]), (2, "max_rollouts"))
        self.assertGreaterEqual(out["budget"]["rollouts"], 3000)

    def test_max_model_calls_stops_the_loop_and_caps_the_client(self):
        out = self.loop(limits=inv.LoopLimits(max_calls=2))
        self.assertEqual((len(out["rounds"]), out["stop_reason"]), (2, "max_model_calls"))
        self.assertEqual(out["budget"]["calls"], 2)

    def test_remaining_calls_limit_the_client(self):
        bad = lambda r: {**r, "proposals": [{**p, "edits": [{"param": "foot_length", "op": "scale", "value": 3.0, "target": "both"}]}
                                            for p in r["proposals"]]}
        out = self.loop(limits=inv.LoopLimits(max_calls=1), client_factory=self.factory(mutate=bad))
        self.assertEqual(self.transports[0].requests, 1)  # the repair would have been call 2 of 1
        self.assertEqual(out["rounds"][0]["status"], "model_failed")
        self.assertTrue(out["stop_reason"].startswith("round_status:"))

    def test_wall_clock_stops_the_loop(self):
        ticks = iter(range(0, 10000, 400))
        out = self.loop(clock=lambda: next(ticks))
        self.assertEqual((len(out["rounds"]), out["stop_reason"]), (1, "wall_clock"))

    def test_cancel_before_start_and_during_a_round(self):
        out = self.loop(cancelled=lambda: True)
        self.assertEqual((out["rounds"], out["stop_reason"]), ([], "cancelled"))
        state = {"n": 0}

        def progress(*a):
            state["n"] += 1
            raise JobCancelled()
        out = self.loop(progress=progress)
        self.assertEqual((len(out["rounds"]), out["stop_reason"]), (1, "cancelled"))

    def test_model_failure_round_stops_the_loop(self):
        out = self.loop(client_factory=self.factory(status=503))
        self.assertEqual(out["stop_reason"], "round_status:model_failed")
        self.assertEqual(len(self.store.get(self.cid)["versions"]), 1)


class ConfigTests(unittest.TestCase):
    def test_model_config_profiles_come_from_the_json(self):
        d = inv.load_model_config("default")
        self.assertEqual((d.model, d.max_tokens, d.reasoning_effort), ("nvidia/nemotron-3-super-120b-a12b", 8000, None))
        self.assertEqual(d.extra_body, {"chat_template_kwargs": {"enable_thinking": False}})
        deep = inv.load_model_config("deep")
        self.assertEqual((deep.model, deep.max_tokens, deep.reasoning_effort), ("nvidia/Nemotron-3-Ultra-550b-a55b", 24000, "low"))
        with self.assertRaises(ValueError):
            inv.load_model_config("turbo")

    def test_client_limits_allow_the_configured_max_tokens(self):
        cfg = inv.load_model_config("deep")
        c = inv.default_client_factory(cfg, mode="live", max_requests=2)
        self.assertGreaterEqual(c.limits.max_tokens_per_request, 24000)
        self.assertEqual(c.limits.max_requests, 2)

    def test_model_summary_has_no_secrets(self):
        s = inv.model_summary()
        self.assertEqual(s["model"], "nvidia/nemotron-3-super-120b-a12b")
        self.assertNotIn("key", json.dumps(s).lower())


if __name__ == "__main__":
    unittest.main()
