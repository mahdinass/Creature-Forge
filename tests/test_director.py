"""Tests of the AI director (`creature_forge.director`). No network and no MuJoCo simulation: replies come from a scripted fixture and
`walk_pipelines.run_pipeline` runs with its `eval_override` hook (synthetic evaluators)."""
import copy
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from creature_forge import creature_gen as cg
from creature_forge import director as dr
from creature_forge import gait_features as gf
from creature_forge import walk_pipelines as wp
from creature_forge.inference_ledger import Caps, InferenceLedger
from creature_forge.investigation import LiveRefused, SCRIPTED_MODEL
from creature_forge.nebius import NebiusError
from creature_forge.phasegait_init import LOWER15, UPPER15

BODY = cg.dev_named_bodies()["stilts-drawn"]
SEEDS = {"diag": [11, 12, 13, 14], "train": [21, 22, 23, 24], "screen": list(range(100, 112))}
S = len(SEEDS["train"])
SCREEN_N, TOPK = 4, 3
KEY = "sk-test-SECRET-0123456789abcdef"
GAIT = {**{k: round(0.123456 * (i + 1), 6) for i, k in enumerate(gf.KEYS) if k != "fall_direction"}, "forward_fall_frac": 1.0, "n_seeds": 4}
FEATURES = {"L": 1.1, "foot_to_leg": 0.0636, "mass_total": 9.87, "torso_frac": 0.4855, "tau_ratio": 0.5651, "friction": 1.0,
            "leg_density": 1000.0}
OUTCOMES = [{"seed": s, "outcome": "FAIL", "label": "fell_forward"} for s in (11, 12, 13)] + [{"seed": 14, "outcome": "POOR", "label": "shuffle"}]


class Fake:
    def __init__(self):
        self.rollouts = 0

    @staticmethod
    def objective(body, vec):
        v = np.asarray(vec[:15], float)
        u = (v - LOWER15) / (UPPER15 - LOWER15)
        return -float(np.sum((u - 0.6) ** 2)) - 2.0 * math.log(body["foot_length"] / 0.12) ** 2

    def eval_fn(self, cands):
        out = []
        for b, v in cands:
            self.rollouts += S
            o = self.objective(b, v)
            w = int(o > -1.2) + int(o > -0.8) + int(o > -0.5) + int(o > -0.3)
            out.append({"walking_count": min(S, w), "survival_count": min(S, w + 1), "mean_fitness": o, "error": None})
        return out

    def screen_fn(self, body, vec, seeds):
        self.rollouts += len(seeds)
        o = self.objective(body, vec)
        return [{"seed": s, "outcome": "PASS" if o > -0.9 else "FAIL", "walking": o > -0.9, "score": o + 0.01 * i} for i, s in enumerate(seeds)]

    def override(self):
        return {"eval_fn": self.eval_fn, "screen_fn": self.screen_fn,
                "similarity_fn": lambda b, v: (list(v), {"fake": True}),
                "diag_fn": lambda b, v, s: {"outcomes": copy.deepcopy(OUTCOMES), "gait": dict(GAIT)},
                "features_fn": lambda b: dict(FEATURES)}


def run(director, total=2000, family=15, rounds=2, probe_budget=60):
    fake = Fake()
    rec = wp.run_pipeline(copy.deepcopy(BODY), director, total_budget=total, family=family, seeds=SEEDS, noise_seed=7,
                          probe_budget=probe_budget, rounds=rounds, screen_top_k=TOPK, screen_n=SCREEN_N, eval_override=fake.override())
    return rec, fake


def hyp(i="H1", ev=("creature.thigh_length", "baseline.forward_fall_frac"), competing=("friction too low",)):
    return {"id": i, "mechanism": "legs are long and the feet are short", "evidence": list(ev), "competing": list(competing)}


def pplan(init="opt_timing", subs=("timing", "posture"), body=(), share=0.4, h="H1", ev=("start.walking_count",)):
    return {"init": init, "ctrl_subspaces": list(subs), "body_params": list(body), "budget_share": share, "hypothesis": h,
            "prediction": "walking seeds go up", "evidence": list(ev)}


R1_PROBES = {"hypotheses": [hyp()], "probes": [{"probe_id": "opt_timing", "hypothesis": "H1", "expect": "improves"},
                                               {"probe_id": "foot_x1_5", "hypothesis": "H1", "expect": "no_change"},
                                               {"probe_id": "opt_posture", "hypothesis": "H1", "expect": "improves"}]}
R1_PLANS = {"refuted": [], "diagnosis": "timing helps", "plans": [pplan(share=0.4), pplan("start", ("feedback",), ("foot_length",), 0.3)]}
R2_PROBES = {"hypotheses": [], "probes": []}
R2_PLANS = {"refuted": ["H1"], "diagnosis": "H1 refuted by the foot probe", "plans": [pplan("r1p0", ("timing",), (), 1.0, "none", ("plans.r1p0.status",))]}
GOOD = [R1_PROBES, R1_PLANS, R2_PROBES, R2_PLANS]


def make(fixture, **kw):
    return dr.NemotronDirector(mode="scripted", fixture=fixture, **kw)


class Recorder:
    """Transport wrapper that keeps every request body."""

    def __init__(self, inner):
        self.inner, self.bodies = inner, []

    @property
    def requests(self):
        return self.inner.requests

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(copy.deepcopy(body))
        return self.inner(url, headers, body, timeout)


class EndToEnd(unittest.TestCase):
    def test_decisions_reach_the_pipeline(self):
        d = make(copy.deepcopy(GOOD))
        rec, fake = run(d)
        self.assertEqual(rec["used"], fake.rollouts)
        r1, r2 = rec["rounds"]
        self.assertEqual([p["probe_id"] for p in r1["probes"]], ["opt_timing", "foot_x1_5", "opt_posture"])
        self.assertEqual(r1["rejected_probes"], [])
        self.assertEqual(r1["rejected_plans"], [])
        self.assertEqual([p["plan"]["ctrl_subspaces"] for p in r1["plans"]], [["timing", "posture"], ["feedback"]])
        self.assertEqual(r1["plans"][0]["plan"]["rationale"], "H1: walking seeds go up")
        self.assertEqual(r2["plans"][0]["plan"]["init"], "r1p0")
        self.assertEqual(r2["plans"][0]["status"], "ok")
        # the director's returned values are exactly what the pipeline recorded as decisions
        returned = [x["returned"] for x in d.record()["decisions"]]
        self.assertEqual(returned, [x["returned"] for x in rec["decisions"]])
        self.assertEqual(d.record()["refuted_by_round"], {"1": [], "2": ["H1"]})
        self.assertEqual(len(d.calls), 4)
        self.assertEqual(d.record()["provenance"], "SCRIPTED_MOCK")
        self.assertEqual(d.record()["model"], SCRIPTED_MODEL)
        # the second round's prompts show the measured results
        msg = d.calls[3]["messages"][1]["content"]
        self.assertIn("probes.opt_timing.delta_walking = ", msg)
        self.assertIn("plans.r1p0.best_walking_count = ", msg)
        self.assertIn("you expected no_change", msg)

    def test_ids_do_not_collide_across_rounds(self):
        f = copy.deepcopy(GOOD)
        f[0]["hypotheses"] = [hyp("H2")]
        f[0]["probes"] = [{"probe_id": "opt_timing", "hypothesis": "H2", "expect": "improves"}]
        f[1]["plans"] = [pplan(h="H2")]
        f[2]["hypotheses"] = [hyp("H3")]               # H3 is new: the ids of round 2 start after the highest existing id
        f[3]["refuted"] = ["H2"]
        d = make(f)
        run(d)
        self.assertEqual([x["status"] for x in d.record()["decisions"]], ["ok"] * 4)
        self.assertEqual(set(d.hypotheses), {"H2", "H3"})
        self.assertTrue(d.hypotheses["H2"]["refuted"])

    def test_family_17_placement_plan(self):
        f = copy.deepcopy(GOOD)
        f[1]["plans"] = [pplan("start", ("placement",), (), 0.5)]
        f[3]["plans"] = [pplan("r1p0", ("placement", "timing"), (), 1.0, "none", ("plans.r1p0.status",))]
        d = make(f)
        rec, _ = run(d, family=17)
        self.assertEqual(rec["rounds"][0]["plans"][0]["status"], "ok")
        self.assertIn("placement", d.calls[1]["messages"][1]["content"] + "placement")


class RepairAndFailure(unittest.TestCase):
    def test_repair_after_invalid_citation(self):
        bad = copy.deepcopy(R1_PROBES)
        bad["hypotheses"][0]["evidence"] = ["creature.not_a_field"]
        d = make([bad, R1_PROBES, R1_PLANS, R2_PROBES, R2_PLANS])
        rec, _ = run(d)
        dec = d.record()["decisions"]
        self.assertTrue(dec[0]["repaired"])
        self.assertEqual(dec[0]["status"], "ok")
        self.assertIn("creature.not_a_field", dec[0]["first_attempt_errors"][0])
        self.assertEqual(len(dec[0]["calls"]), 2)
        self.assertEqual(len(d.calls), 5)
        self.assertEqual(d.calls[1]["settings"]["purpose"], "director_repair")
        self.assertIn("creature.not_a_field", d.calls[1]["messages"][-1]["content"])      # the validator's error list is sent back
        self.assertEqual(len(rec["rounds"][0]["probes"]), 3)

    def test_repair_for_unparseable_reply(self):
        d = make(["this is not json", R1_PROBES, R1_PLANS, R2_PROBES, R2_PLANS])
        run(d)
        self.assertTrue(d.record()["decisions"][0]["repaired"])
        self.assertEqual(d.record()["decisions"][0]["status"], "ok")

    def test_still_invalid_after_repair_returns_empty_and_is_recorded(self):
        bad = copy.deepcopy(R1_PROBES)
        bad["probes"][0]["probe_id"] = "opt_placement"          # family 15: unavailable
        # the plan call then has no hypotheses; a plan may cite "none" with its own evidence
        plans = {"refuted": [], "diagnosis": "no usable hypothesis", "plans": [pplan("start", ("timing",), (), 0.5, "none")]}
        d = make([bad, bad, plans, R2_PROBES, R2_PLANS])
        rec, _ = run(d)
        dec = d.record()["decisions"]
        self.assertEqual((dec[0]["status"], dec[0]["returned"]), ("invalid_after_repair", []))
        self.assertTrue(any("not available" in e for e in dec[0]["validation_errors"]))
        self.assertEqual(rec["rounds"][0]["probes"], [])
        self.assertEqual(rec["decisions"][0]["returned"], [])         # no default was substituted
        self.assertEqual(len(d.hypotheses), 0)                        # a rejected reply registers nothing
        self.assertEqual(dec[0]["calls"], [0, 1])                     # exactly one repair, no more retries
        self.assertEqual(dec[1]["calls"], [2])
        self.assertEqual(rec["rounds"][0]["plans"][0]["status"], "ok")

    def test_model_failure_is_not_repaired_and_returns_empty(self):
        class Boom:
            requests = 0

            def __call__(self, *a):
                Boom.requests += 1
                raise NebiusError("HTTP 500: upstream")
        d = dr.NemotronDirector(mode="scripted", transport=Boom())
        rec, _ = run(d)
        self.assertEqual(Boom.requests, 4)                            # one attempt per call, never retried
        self.assertTrue(all(x["status"] == "model_failed" and x["returned"] == [] for x in d.record()["decisions"]))
        self.assertTrue(all(r["probes"] == [] and r["plans"] == [] for r in rec["rounds"]))

    def test_plan_still_invalid_after_repair(self):
        bad = copy.deepcopy(R1_PLANS)
        bad["plans"][0]["budget_share"] = 0.8                          # 0.8 + 0.3 > 1
        d = make([R1_PROBES, bad, bad, R2_PROBES, R2_PLANS])
        rec, _ = run(d)
        dec = d.record()["decisions"][1]
        self.assertEqual((dec["status"], dec["returned"]), ("invalid_after_repair", []))
        self.assertTrue(any("sum to" in e for e in dec["validation_errors"]))
        self.assertEqual(rec["rounds"][0]["plans"], [])
        self.assertEqual(rec["rounds"][0]["rejected_plans"], [])      # the pipeline never even saw them
        self.assertEqual(d.record()["refuted_by_round"].get("1"), None)


class Validators(unittest.TestCase):
    paths = {"creature.thigh_length", "start.walking_count", "baseline.forward_fall_frac"}

    def probes(self, reply, avail=("opt_timing", "foot_x1_5"), live=()):
        return dr.validate_probe_reply(reply, paths=self.paths, new_ids=["H1", "H2", "H3"], live_ids=list(live), available=list(avail))

    def plans(self, reply, family=15, live=("H1", "H2"), refutable=None, runs=None):
        return dr.validate_plan_reply(reply, paths=self.paths, live_ids=list(live), refutable=list(live if refutable is None else refutable),
                                      family=family, runs={"opt_timing": 1} if runs is None else runs)

    def test_valid(self):
        e, ids = self.probes(R1_PROBES | {"probes": R1_PROBES["probes"][:2]}, )
        self.assertEqual(e, [])
        self.assertEqual(ids, ["opt_timing", "foot_x1_5"])
        self.assertEqual(self.plans({"refuted": ["H2"], "diagnosis": "x", "plans": [pplan(h="H1")]}), [])

    def test_probe_errors(self):
        bad = lambda **kw: self.probes({"hypotheses": [hyp()], "probes": [{"probe_id": "opt_timing", "hypothesis": "H1", "expect": "improves", **kw}]})[0]  # noqa: E731
        self.assertTrue(bad(probe_id="opt_stride"))            # not available
        self.assertTrue(bad(probe_id="nope"))
        self.assertTrue(bad(hypothesis="H9"))
        self.assertTrue(bad(expect="worse"))
        self.assertTrue(bad(extra=1))
        dup = {"hypotheses": [hyp()], "probes": [{"probe_id": "opt_timing", "hypothesis": "H1", "expect": "improves"}] * 2}
        self.assertTrue(any("twice" in e for e in self.probes(dup)[0]))
        four = {"hypotheses": [hyp()], "probes": [{"probe_id": p, "hypothesis": "H1", "expect": "improves"} for p in
                                                  ("opt_timing", "foot_x1_5", "opt_posture", "opt_stride")]}
        self.assertTrue(any("at most 3" in e for e in self.probes(four, avail=("opt_timing", "foot_x1_5", "opt_posture", "opt_stride"))[0]))
        self.assertTrue(self.probes({"hypotheses": [], "probes": []})[0])                  # no hypothesis and none open
        self.assertEqual(self.probes({"hypotheses": [], "probes": []}, live=("H1",))[0], [])
        self.assertTrue(self.probes({"hypotheses": [hyp(competing=())], "probes": []})[0])
        self.assertTrue(self.probes({"hypotheses": [hyp(ev=())], "probes": []})[0])
        self.assertTrue(self.probes({"hypotheses": [hyp(ev=("start.walking_count", "start.walking_count"))], "probes": []})[0])
        self.assertTrue(self.probes({"hypotheses": [hyp("H4")], "probes": []})[0])

    def test_citations_are_restricted_to_the_evidence(self):
        for c in ("creature.thigh_length_x", "budget.remaining", "creature", ""):
            e, _ = self.probes({"hypotheses": [hyp(ev=(c,))], "probes": []})
            self.assertTrue(any("not an evidence path" in x for x in e), c)

    def test_plan_errors(self):
        def bad(**kw):
            return self.plans({"refuted": [], "diagnosis": "x", "plans": [pplan(**kw)]})
        self.assertTrue(bad(subs=("placement",)))               # family 15
        self.assertEqual(self.plans({"refuted": [], "diagnosis": "x", "plans": [pplan(subs=("placement",))]}, family=17), [])
        self.assertTrue(bad(init="opt_stride"))                 # never run
        self.assertTrue(bad(share=0))
        self.assertTrue(bad(body=("leg_density",)))
        self.assertTrue(bad(h="H7"))
        self.assertTrue(bad(ev=()))
        two = {"refuted": [], "diagnosis": "x", "plans": [pplan(share=0.6), pplan(share=0.6)]}
        self.assertTrue(any("sum to" in e for e in self.plans(two)))
        three = {"refuted": [], "diagnosis": "x", "plans": [pplan(share=0.2)] * 3}
        self.assertTrue(any("1-2 plans" in e for e in self.plans(three)))
        self.assertTrue(any("1-2 plans" in e for e in self.plans({"refuted": [], "diagnosis": "x", "plans": []})))

    def test_refuted_must_reference_existing_open_hypotheses(self):
        mk = lambda ref, h="none": {"refuted": ref, "diagnosis": "x", "plans": [pplan(h=h)]}  # noqa: E731
        self.assertTrue(self.plans(mk(["H9"])))
        self.assertTrue(self.plans(mk(["H1"], "H1")))            # refuted and pursued in the same reply
        self.assertTrue(self.plans(mk(["H3"]), live=("H1",)))
        self.assertTrue(self.plans(mk(["H1"]), live=("H2",), refutable=["H2"]))   # H1 was already refuted before
        self.assertEqual(self.plans(mk(["H1"])), [])
        self.assertTrue(self.plans(mk(["H1", "H1"])))

    def test_refuted_end_to_end_rejects_unknown_ids(self):
        bad = copy.deepcopy(R1_PLANS)
        bad["refuted"] = ["H5"]
        d = make([R1_PROBES, bad, bad, R2_PROBES, R2_PLANS])
        rec, _ = run(d)
        self.assertEqual(d.record()["decisions"][1]["status"], "invalid_after_repair")
        self.assertEqual(rec["rounds"][0]["plans"], [])
        self.assertFalse(any(h["refuted"] for h in d.hypotheses.values() if h["refuted_round"] == 1))

    def test_unavailable_probe_is_never_sent_to_the_pipeline(self):
        bad = copy.deepcopy(R1_PROBES)
        bad["probes"] = [{"probe_id": "opt_placement", "hypothesis": "H1", "expect": "improves"}]
        d = make([bad, bad, R1_PLANS, R2_PROBES, R2_PLANS])
        rec, _ = run(d)
        self.assertEqual(rec["rounds"][0]["rejected_probes"], [])
        self.assertEqual(rec["decisions"][0]["returned"], [])


class SchemaAndPrompt(unittest.TestCase):
    def run_recorded(self, **kw):
        d = make(copy.deepcopy(GOOD), **kw)
        rec_t = Recorder(d.client.transport)
        d.client.transport = rec_t
        run(d)
        return d, rec_t

    def test_schema_enums_restrict_citations_and_ids(self):
        d, t = self.run_recorded()
        self.assertEqual(len(t.bodies), 4)
        for b in t.bodies:
            rf = b["response_format"]
            self.assertTrue(rf["json_schema"]["strict"])
            self.assertEqual(b["model"], SCRIPTED_MODEL)
        s0 = t.bodies[0]["response_format"]["json_schema"]["schema"]
        cites = s0["properties"]["hypotheses"]["items"]["properties"]["evidence"]["items"]["enum"]
        self.assertIn("creature.thigh_length", cites)
        self.assertIn("budget.probe_cost.opt_timing", cites)
        self.assertIn("baseline.outcome_FAIL", cites)
        self.assertNotIn("probes.opt_timing.status", cites)                       # nothing measured yet
        self.assertEqual(s0["properties"]["hypotheses"]["items"]["properties"]["id"]["enum"], ["H1", "H2", "H3"])
        ids = s0["properties"]["probes"]["items"]["properties"]["probe_id"]["enum"]
        self.assertNotIn("opt_placement", ids)                                     # family 15
        self.assertTrue(set(ids) <= set(wp.PROBES) - {"opt_placement"} and "opt_timing" in ids)
        self.assertNotIn("legs_x1_2", ids)                                         # 0.55 m legs x1.2 would leave the guided bounds
        s3 = t.bodies[3]["response_format"]["json_schema"]["schema"]
        p3 = s3["properties"]["plans"]["items"]["properties"]
        self.assertIn("plans.r1p0.best_walking_count", p3["evidence"]["items"]["enum"])
        self.assertIn("probes.foot_x1_5.delta_walking", p3["evidence"]["items"]["enum"])
        self.assertEqual(p3["init"]["enum"], ["start", "foot_x1_5", "opt_posture", "opt_timing", "r1p0", "r1p1"])
        self.assertEqual(p3["ctrl_subspaces"]["items"]["enum"], ["timing", "posture", "feedback", "stride"])
        self.assertEqual(p3["hypothesis"]["enum"], ["H1", "none"])
        self.assertEqual(s3["properties"]["refuted"]["items"]["enum"], ["H1"])
        self.assertEqual(p3["body_params"]["items"]["enum"], list(wp.FIX_BODY_PARAMS))
        # the plan schema never exposes numeric parameter values, only a share
        self.assertEqual(set(p3), {"init", "ctrl_subspaces", "body_params", "budget_share", "hypothesis", "prediction", "evidence"})

    def test_prompt_size(self):
        d, t = self.run_recorded()
        for i, c in enumerate(d.calls):
            self.assertLess(len(c["messages"][1]["content"].encode()), dr.PROMPT_TARGET_BYTES, f"call {i}")

    def test_system_prompt_content_and_neutrality(self):
        s = dr.build_system_prompt()
        for needle in ("80%", "24 held-out seeds", "20 s", "fp_kd", "fp_kv", "0.5-1.5", "guided bounds", "excludes everything outside",
                       "refuted", "same budget", "never choose numeric parameter values"):
            self.assertIn(needle, s)
        for pid in wp.PROBES:
            self.assertIn(f"- {pid}:", s)
        for sub in ("timing", "posture", "feedback", "stride", "placement"):
            self.assertIn(f"- {sub}", s)
        for k in gf.SUMMARY_DOCS:
            self.assertIn(f"baseline.{k}:", s)
        for leak in ("usually", "typically works", "most effective", "best subspace", "recommended"):
            self.assertNotIn(leak, s.lower())
        self.assertEqual(s, dr.build_system_prompt())                              # deterministic

    def test_no_numeric_parameter_values_in_returned_plans(self):
        d = make(copy.deepcopy(GOOD))
        rec, _ = run(d)
        for x in d.record()["decisions"]:
            for p in x["returned"] if x["kind"] == "plans" else []:
                self.assertEqual(set(p), wp.PLAN_KEYS | wp.PLAN_OPTIONAL_KEYS)


class LedgerAndProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.jsonl"

    def ledger(self, **caps):
        return InferenceLedger(self.path, prices={SCRIPTED_MODEL: (1e-7, 1e-7), "nvidia/nemotron-3-super-120b-a12b": (3e-7, 9e-7)},
                               caps=Caps(**caps) if caps else None)

    def test_ledger_reservation_is_used(self):
        led = self.ledger()
        d = make(copy.deepcopy(GOOD), ledger=led, investigation_id="i-abcdef123456")
        run(d)
        rows = [json.loads(x) for x in self.path.read_text().splitlines()]
        reserves = [r for r in rows if r.get("kind") == "reserve"]
        settles = [r for r in rows if r.get("kind") != "reserve"]
        self.assertEqual(len(reserves), 4)
        self.assertEqual(len(settles), 4)
        self.assertEqual({r["investigation_id"] for r in rows}, {"i-abcdef123456"})
        self.assertEqual({r["reservation_id"] for r in reserves}, {r["reservation_id"] for r in settles})
        self.assertEqual(led.investigation_status("i-abcdef123456")["requests"], 4)
        self.assertAlmostEqual(d.record()["cost_usd"], sum(r["cost_usd"] for r in settles))
        self.assertGreater(d.record()["cost_usd"], 0)

    def test_call_over_the_cap_is_refused_before_sending(self):
        led = self.ledger(max_requests=2)
        d = make(copy.deepcopy(GOOD), ledger=led)
        t = d.client.transport
        rec, _ = run(d)
        self.assertEqual(t.requests, 2)                                            # calls 3 and 4 never reached the transport
        dec = d.record()["decisions"]
        self.assertEqual([x["status"] for x in dec], ["ok", "ok", "model_failed", "model_failed"])
        refused = d.calls[2]
        self.assertTrue(refused["budget_refused"])
        self.assertFalse(refused["sent"])
        self.assertIn("request cap", refused["error"])
        self.assertEqual(rec["rounds"][1]["plans"], [])
        self.assertEqual(led.status()["requests"], 2)

    def test_investigation_cap_blocks_extra_repairs(self):
        led = self.ledger(inv_max_requests=1)
        d = make(copy.deepcopy(GOOD), ledger=led)
        run(d)
        self.assertEqual(sum(1 for c in d.calls if c["sent"]), 1)

    def test_client_limits_come_from_max_requests(self):
        d = make(copy.deepcopy(GOOD), max_requests=3, ledger=self.ledger())
        t = d.client.transport
        run(d)
        self.assertEqual(t.requests, 3)
        self.assertEqual(d.record()["decisions"][3]["status"], "model_failed")
        self.assertIn("request limit", d.record()["decisions"][3]["validation_errors"][0])

    def test_live_gate(self):
        env = {k: v for k, v in os.environ.items() if k not in ("CREATURE_FORGE_ENABLE_LIVE", "NEBIUS_API_KEY")}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(LiveRefused) as cm:
                dr.NemotronDirector(mode="live", ledger=self.ledger())
            self.assertIn("CREATURE_FORGE_ENABLE_LIVE", str(cm.exception))
            os.environ["CREATURE_FORGE_ENABLE_LIVE"] = "1"
            with mock.patch("creature_forge.config.load_env", return_value=False):
                with self.assertRaises(LiveRefused) as cm:
                    dr.NemotronDirector(mode="live", ledger=self.ledger())
            self.assertIn("API key", str(cm.exception))

    def test_live_record_has_no_key_and_injected_transport_is_not_live(self):
        class Leaky:
            """Fake provider that echoes the key in its error text (the client must redact it)."""
            n = 0

            def __init__(self):
                self.inner = dr.FixtureTransport(copy.deepcopy(GOOD))

            def __call__(self, url, headers, body, timeout):
                Leaky.n += 1
                assert headers["Authorization"] == f"Bearer {KEY}"
                if Leaky.n == 2:
                    raise NebiusError(f"HTTP 401: invalid key {KEY}")
                return self.inner(url, headers, body, timeout)
        with mock.patch.dict(os.environ, {"CREATURE_FORGE_ENABLE_LIVE": "1", "NEBIUS_API_KEY": KEY}), \
                mock.patch("creature_forge.config.load_env", return_value=False):
            d = dr.NemotronDirector(mode="live", ledger=self.ledger(), transport=Leaky())
            run(d)
            rec = d.record()
        text = json.dumps(rec)
        self.assertNotIn(KEY, text)
        self.assertNotIn("Bearer", text)
        self.assertEqual(rec["model"], "nvidia/nemotron-3-super-120b-a12b")
        self.assertEqual(rec["provenance"], "SCRIPTED_MOCK")                       # a fake transport is never labelled LIVE
        self.assertEqual(rec["decisions"][1]["status"], "model_failed")
        self.assertIn("[redacted]", rec["decisions"][1]["validation_errors"][0])

    def test_scripted_is_never_live(self):
        d = make(copy.deepcopy(GOOD))
        self.assertEqual(d.record()["provenance"], "SCRIPTED_MOCK")
        with self.assertRaises(ValueError):
            dr.NemotronDirector(mode="scripted")
        with self.assertRaises(ValueError):
            dr.NemotronDirector(mode="bogus", fixture=[])

    def test_record_is_json_safe_and_complete(self):
        d = make(copy.deepcopy(GOOD))
        run(d)
        rec = d.record()
        json.dumps(rec)
        for k in ("provenance", "model", "settings", "calls", "decisions", "refuted_by_round", "cost_usd", "tokens"):
            self.assertIn(k, rec)
        for dec in rec["decisions"]:
            for k in ("kind", "round", "parsed", "validation_errors", "returned"):
                self.assertIn(k, dec)
        self.assertEqual(rec["calls"][0]["prompt_sha256"], d.calls[0]["prompt_sha256"])
        self.assertGreater(rec["tokens"]["prompt"], 0)


if __name__ == "__main__":
    unittest.main()


class PromptV2Tests(unittest.TestCase):
    def test_v1_unchanged_and_v2_deterministic_and_shuffled(self):
        from creature_forge import director as dr
        self.assertEqual(dr.build_system_prompt(), dr.build_system_prompt("v1", 7))   # v1 ignores the order seed
        a, b, c = dr.build_system_prompt("v2", 1), dr.build_system_prompt("v2", 1), dr.build_system_prompt("v2", 2)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(sorted(a.splitlines()), sorted(c.splitlines()))     # same content, different order
        self.assertIn("wasted", a)
        self.assertIn("BODY", a)
        for w in ("usually works", "most often", "best subspace"):
            self.assertNotIn(w, a)

    def test_v2_requires_known_version(self):
        from creature_forge import director as dr
        with self.assertRaises(ValueError):
            dr.NemotronDirector(mode="scripted", fixture=[], prompt_version="v3")
