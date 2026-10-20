"""No-physics tests of the TA-1 / RV-1 harness (FA-1C Phase 0): fakes and source checks only, no MuJoCo rollout.

They check that the harness changes nothing but the post-screen hook, that its records keep complete per-seed verification
evidence, that pre-hook fingerprints separate pre- from post-intervention state, that seeds reproduce DS-1 at replicate 0,
that the configuration equals DS-1's A1e6 launcher, and that nothing can simulate without an explicit, approved --execute.
Every simulation entry point is patched to fail during the CLI tests."""
import copy
import inspect
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import ta1_tool_access as ta1                         # noqa: E402
import rv1_reverify as rv1                            # noqa: E402
from creature_forge import belief_engine as be        # noqa: E402
from creature_forge import has_agent as ha            # noqa: E402
from creature_forge import hidden_plant as hp         # noqa: E402

STOP_MODEL = {"kind": "isotonic_robust16", "p": [i / 16 for i in range(17)], "fitted_on": "unit-test"}
L1 = "hdb-v1-gen-0073:low_ground_friction:2"


class _Budget:
    def __init__(self, total):
        self.total, self.used, self.lines = total, 0, []

    @property
    def remaining(self):
        return self.total - self.used

    def charge(self, n, item, detail=None):
        self.used += n
        self.lines.append({"item": item, "n": n, "detail": detail or {}, "cumulative": self.used})


class _Bench:
    def __init__(self):
        self.budget, self.twin = _Budget(700), _Budget(2800)
        self.designs = [{"index": 0, "source": "initial", "body": {"foot_friction": 1.3}, "vector": [0.0] * 17}]
        self._best = 0

    def best_design(self):
        return self.designs[self._best]

    def select(self, i):
        self._best = i
        return {"ok": True}

    def add_twin_design(self, body, vector, *, source, parent=None, **extra):
        self.designs.append({"index": len(self.designs), "source": source, "body": body, "vector": vector})
        return len(self.designs) - 1


class _Episode:
    """Stand-in for belief_engine.Episode: robust_repair records its keyword arguments and calls the engineer once with a
    fixed screened ranking, as the real method does after its screens."""
    RANKING = [{"tool": "placement", "score": 1.1}, {"tool": "posture", "score": 0.8}, {"tool": "leg_length", "score": 0.3}]

    def __init__(self, bench):
        self.b, self.events, self.history, self.experiments, self.calls = bench, [], [], [], []

    def state(self):
        return {"experiments": [], "posterior": [{"pid": "contact_friction:feet(factor=0.5)", "w": 0.99}],
                "plant_remaining": self.b.budget.remaining, "twin_remaining": self.b.twin.remaining}

    def robust_repair(self, **kw):
        self.calls.append(kw)
        self.b.budget.charge(16, "baseline_check")
        self.b.twin.charge(36, "twin_walk", {"tag": "screen:placement"})
        self.events.append({"seq": len(self.events), "kind": "tool_screen", "ranking": self.RANKING})
        plan = {}
        if kw.get("engineer") is not None:
            plan = kw["engineer"](self.state(), self.RANKING) or {}
            self.events.append({"seq": len(self.events), "kind": "engineer_plan", "plan": plan})
        tools = [r["tool"] for r in self.RANKING]
        if plan.get("tool_order"):
            tools = list(plan["tool_order"]) + [t for t in tools if t not in plan["tool_order"]]
        self.b.twin.charge(800, "twin_cma", {"tag": f"robust:{tools[0]}"})      # post-hook work
        self.events.append({"seq": len(self.events), "kind": "assimilated_check"})
        return {"accepted": False, "design": 0, "log": [], "tools": tools}


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _session(cls=ha.LabSession, **kw):
    b = _Bench()
    ep = _Episode(b)
    return cls(b, ep, stop_model=STOP_MODEL, tau=0.75, memory=None, learned=None, v5=False, cases=None, **kw), b, ep


def _rows(n, seed0=100):
    return [{k: (seed0 + i if k == "seed" else 0.5) for k in ta1.VALIDATION_ROW_FIELDS} for i in range(n)]


def _assess(confirm_run=True):
    vd = {k: 0 for k in ta1.VERDICT_FIELDS}
    vd.update(status="VERIFIED_IMPROVEMENT", reasons=["x"], min_effect={"required": 0.5})
    out = {"rule": "full_recovery_v1", "status": "FULL_RECOVERY", "reasons": [],
           "validation": {"original": _rows(24), "candidate": _rows(24), "verdict": vd, "aggregate": "PASS", "walking_frac": 1.0},
           "confirmation": {"run": confirm_run, "per_seed": _rows(24, 900) if confirm_run else None,
                            "checks": {"walking_frac": {"passed": True}}} if confirm_run else {"run": False, "reason": ""},
           "rollouts": {"validation": 48, "confirmation": 24 if confirm_run else 0,
                        "confirmation_rollout_equivalents": 48.0 if confirm_run else 0.0},
           "seeds": {"validate": list(range(100, 124)), "confirm": list(range(900, 924))}}
    return out


class SeedsAndConfig(unittest.TestCase):
    def test_replicate_zero_is_the_ds1_seed(self):
        self.assertEqual(ta1.ds1_noise_seed(L1), 1751409197)
        self.assertEqual(ta1.replicate_noise_seed(L1, 0), 1751409197)
        self.assertEqual(ta1.replicate_noise_seed(L1, 2), 1751409197 + 2 * 10007)
        # identical for every hdb-v1 instance ("hdb-" prefix): replicates are plant-CMA technical replicates
        self.assertEqual(ta1.ds1_noise_seed("hdb-v1-gen-0096:low_ground_friction:2"), 1751409197)
        for bad in (-1, True, 1.0):
            with self.assertRaises(ValueError):
                ta1.replicate_noise_seed(L1, bad)

    def test_seed_formula_matches_the_pinned_runner(self):
        src = _read("scripts", "hdb_agent_run.py")
        self.assertIn('noise_seed=int.from_bytes(inst["instance_id"].encode()[:4], "big") % (2 ** 31)', src)

    def test_config_equals_the_ds1_a1e6_launcher(self):
        sh = _read("scripts", "ds1_launch.sh")
        run = _read("scripts", "hdb_agent_run.py")
        self.assertIn(f"D={ta1.DS1_DIR}", sh)
        self.assertIn("MAP=${2:-$D/stopmap_dev_v2.json}", sh)
        self.assertIn('C="$B --stop-model $MAP --v6 $D/engine_v6_settings.json"', sh)
        self.assertIn("--split-file " + ta1.A1E6["split_file"], sh)
        self.assertIn("--thresholds artifacts/hdb/" + ta1.A1E6["thresholds"], sh)
        self.assertIn("--mults " + ",".join(str(m) for m in ta1.A1E6["mults"]), sh)
        self.assertIn("CF_HDB_WALKERS=artifacts/hdb/" + ta1.A1E6["walkers"], sh)
        self.assertRegex(run, r'"--tau", type=float, default=0\.75')
        self.assertRegex(run, r'"--budget", type=int, default=700')
        self.assertRegex(run, r'"--twin-budget", type=int, default=2800')
        self.assertIn("max_alive=12", run)
        self.assertEqual(ta1.A1E6["max_turns"], ha.MAX_TURNS)
        for key in ("v6", "stop_model", "split_file", "eval_instances"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, ta1.A1E6[key])), key)

    def test_case_ids_are_in_the_preregistered_eval_list(self):
        ids = json.loads(_read(ta1.A1E6["eval_instances"]))
        flat = {x for v in ids.values() if isinstance(v, list) for x in v}
        for c in ta1.CASES.values():
            self.assertIn(c["instance_id"], flat)

    def test_eligibility_rollouts_equal_the_check_seed_count(self):
        from creature_forge import hdb_bench as hb
        self.assertEqual(ta1.ELIGIBILITY_ROLLOUTS, hb.SEED_COUNTS["check"])


class EngineAssumptions(unittest.TestCase):
    """Source facts the experiment relies on (fails loudly if the pinned engine changes)."""

    def test_hook_runs_after_both_screens_and_before_the_warm_start(self):
        src = inspect.getsource(be.Episode.robust_repair)
        order = ["ranking = self.screen_tools(hyps)", "ranking = self.screen_tools_cma(hyps, ranking",
                 "plan = engineer(self.state(), ranking) or {}",
                 'tools = list(plan["tool_order"]) + [t for t in tools if t not in plan["tool_order"]]',
                 "res = self.b.twin_cma(hyps[0][0].deviation, start, t1"]
        pos = [src.index(s) for s in order]
        self.assertEqual(pos, sorted(pos))
        # the CMA screen is skipped only for tool_order / prefer, never for an engineer plan
        self.assertIn("if screen_cma and tool_order is None and not prefer:", src)
        # the re-screen condition does not look at the engineer (it can follow the intervention naturally)
        self.assertIn('assim[-1]["leader_changed"] and tool_order is None and not prefer', src)

    def test_pinned_delegate_repair_calls_robust_repair_with_keywords(self):
        src = inspect.getsource(ha.LabSession.delegate_repair)
        self.assertIn("rep = self.ep.robust_repair(twin_budget=TWIN_REPAIR_BUDGET, plant_budget=300, accept_fn=accept,", src)
        self.assertNotIn("engineer", src)


class ArmsAndHook(unittest.TestCase):
    def test_plans(self):
        rk = copy.deepcopy(_Episode.RANKING)
        self.assertEqual(ta1.control_plan({}, rk), {})
        self.assertEqual(ta1.treatment_plan({}, rk), {"tool_order": ["foot_friction"]})
        self.assertEqual(rk, _Episode.RANKING)
        with self.assertRaises(ValueError):
            ta1.HookRecorder("forced", None, None)

    def _run(self, arm):
        b0 = _Bench()
        ep0 = _Episode(b0)
        hook = ta1.HookRecorder(arm, b0, ep0)
        s = ta1.ToolAccessSession(b0, ep0, stop_model=STOP_MODEL, tau=0.75, memory=None, learned=None, v5=False, cases=None,
                                  engineer=hook)
        res = s.delegate_repair()
        return s, ep0, hook, res

    def test_override_adds_only_the_engineer(self):
        base, _, ep_base = _session()
        base.delegate_repair()
        for arm in ("control", "treatment"):
            s, ep, hook, _ = self._run(arm)
            ka, kb = ep_base.calls[0], ep.calls[0]
            self.assertEqual(set(kb) - set(ka), {"engineer"})
            self.assertIs(kb["engineer"], hook)
            for k in ka:
                if k == "accept_fn":       # rebuilt per call from the same stop model and tau
                    self.assertEqual((ka[k].model, ka[k].tau, ka[k].needs_stress), (kb[k].model, kb[k].tau, kb[k].needs_stress))
                else:
                    self.assertEqual(ka[k], kb[k], k)
            self.assertNotIn("robust_repair", vars(ep))            # the class method is restored
            self.assertTrue(s.done)
            self.assertEqual(s.conclusion["by"], "engine_repair")
            self.assertEqual(len(hook.calls), 1)

    def test_treatment_changes_only_the_post_hook_order(self):
        sc, _, hc, _ = self._run("control")
        st, _, ht, _ = self._run("treatment")
        rc, rt = sc.conclusion["repair"], st.conclusion["repair"]
        self.assertEqual(rc["tools"], ["placement", "posture", "leg_length"])
        self.assertEqual(rt["tools"], ["foot_friction", "placement", "posture", "leg_length"])
        self.assertEqual(hc.calls[0]["prehook_fingerprint"], ht.calls[0]["prehook_fingerprint"])
        self.assertFalse(ht.calls[0]["treatment_tool_in_ranking"])
        self.assertIsNone(ht.calls[0]["treatment_tool_rank"])
        self.assertEqual(ht.calls[0]["plan"], {"tool_order": ["foot_friction"]})

    def test_wrapper_refuses_a_second_engineer(self):
        def passes_engineer(self, *a, **k):
            return self.ep.robust_repair(engineer=lambda st, rk: {})
        s, ep, _ = _session(ta1.ToolAccessSession, engineer=lambda st, rk: {})
        with mock.patch.object(ha.LabSession, "delegate_repair", passes_engineer):
            with self.assertRaises(RuntimeError):
                s.delegate_repair()
        self.assertNotIn("robust_repair", vars(ep))


class Fingerprint(unittest.TestCase):
    def _hook_state(self):
        b = _Bench()
        b.budget.charge(4, "observe")
        b.twin.charge(340, "twin_observe", {"tag": "nominal|X0:observe#screen"})
        ep = _Episode(b)
        ep.events.append({"seq": 0, "kind": "generic_screen", "n": 81})
        ep.history.append({"label": "after_observation", "top": []})
        return b, ep

    def test_stable_and_sensitive_to_pre_hook_state(self):
        b1, e1 = self._hook_state()
        b2, e2 = self._hook_state()
        f1 = ta1.fingerprint(ta1.prehook_snapshot(b1, e1, e1.state(), _Episode.RANKING))
        f2 = ta1.fingerprint(ta1.prehook_snapshot(b2, e2, e2.state(), _Episode.RANKING))
        self.assertEqual(f1, f2)
        b2.twin.lines[0]["n"] = 341
        self.assertNotEqual(f1, ta1.fingerprint(ta1.prehook_snapshot(b2, e2, e2.state(), _Episode.RANKING)))
        rk = copy.deepcopy(_Episode.RANKING)
        rk[0]["score"] = 1.2
        self.assertNotEqual(f1, ta1.fingerprint(ta1.prehook_snapshot(b1, e1, e1.state(), rk)))

    def test_blind_to_post_hook_state(self):
        b, ep = self._hook_state()
        hook = ta1.HookRecorder("control", b, ep)
        hook(ep.state(), _Episode.RANKING)
        before = copy.deepcopy(hook.calls[0])
        b.twin.charge(800, "twin_cma")
        ep.events.append({"seq": 9, "kind": "assimilated_check"})
        b.twin.lines[0]["detail"]["tag"] = "mutated after the hook"
        self.assertEqual(hook.calls[0], before)
        self.assertEqual(before["prehook_twin_used"], 340)
        self.assertEqual(before["prehook_n_events"], 1)


class Records(unittest.TestCase):
    def test_rescreen_is_recorded_not_discarded(self):
        self.assertEqual(ta1.rescreen_summary([{"kind": "tool_screen"}])["classification"], "no re-screen")
        ev = [{"seq": 5, "kind": "rescreen_after_assimilation", "old_order": ["foot_friction", "placement"],
               "new_order": ["posture", "placement"]}]
        s = ta1.rescreen_summary(ev)
        self.assertEqual(s["n"], 1)
        self.assertTrue(s["sensitivity_exclude"])
        self.assertEqual(s["classification"], "re-screen; treatment tool absent from the new order")
        ev[0]["new_order"] = ["foot_friction", "posture"]
        self.assertEqual(ta1.rescreen_summary(ev)["classification"], "re-screen; treatment tool kept")

    def test_verification_serialisation_keeps_every_per_seed_row(self):
        for confirm in (True, False):
            v = _assess(confirm)
            s = ta1.serialize_verification(v)
            self.assertEqual(s["summary"], {"status": v["status"], "walking_frac": 1.0, "reasons": [], "rollouts": v["rollouts"]})
            self.assertEqual(ta1.verification_complete(s["full"]), [])
            self.assertEqual(len(s["full"]["validation"]["candidate"]), 24)
        broken = _assess()
        broken["validation"]["candidate"] = broken["validation"]["candidate"][:23]
        del broken["validation"]["verdict"]["median_diff"]
        broken["confirmation"]["per_seed"] = []
        errs = ta1.verification_complete(broken)
        self.assertEqual(len(errs), 3)

    def test_serialised_fields_exist_in_the_pinned_verifier(self):
        from creature_forge import recovery, verdict
        rec_src, vd_src = inspect.getsource(recovery.run_walk_seeds), inspect.getsource(verdict.verdict)
        for f in ta1.VALIDATION_ROW_FIELDS:
            self.assertTrue(f'"{f}"' in rec_src or f == "perturb" or f == "friction_used", f)
        self.assertIn('"perturb": c["perturb"]', rec_src)
        self.assertIn('"friction_used": used', rec_src)
        for f in ta1.VERDICT_FIELDS:
            self.assertIn(f'"{f}"', vd_src + inspect.getsource(verdict))

    def test_resource_accounting(self):
        ledger = {"used": 700, "total": 700, "twin": {"used": 2588, "total": 2800}}
        calls = [{"prehook_plant_used": 60, "prehook_twin_used": 1900}]
        r = ta1.resource_accounting(ledger, calls, {"rollouts": {"validation": 48, "confirmation_rollout_equivalents": 0.0}})
        self.assertEqual((r["plant"]["prehook"], r["plant"]["posthook"]), (60, 640))
        self.assertEqual((r["twin"]["prehook"], r["twin"]["posthook"]), (1900, 688))
        self.assertEqual(r["total_rollout_equivalents"], 700 + 2588 + 8 + 48)
        self.assertLessEqual(r["total_rollout_equivalents"], ta1.PER_EPISODE_CAP["plant"] + ta1.PER_EPISODE_CAP["twin"])

    def test_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "w") as fh:
                fh.write("{}")
            m = ta1.provenance_manifest(ROOT, {"present": p, "absent": os.path.join(d, "none.json")}, {"phase": "test"})
        self.assertRegex(m["git_commit"] or "", r"^[0-9a-f]{40}$")
        self.assertIsNotNone(m["git_dirty"])
        self.assertEqual(len(m["inputs"]["present"]["sha256"]), 64)
        self.assertIsNone(m["inputs"]["absent"]["sha256"])
        for k in ("python", "numpy", "mujoco", "platform", "engine_version", "harness_version", "created_utc"):
            self.assertIn(k, m)
        self.assertEqual(m["phase"], "test")


def _record(designs, submitted, events, twin_lines, plant_lines, status="NOT_RECOVERED", frac=23 / 24, harness=None):
    designs, events, twin_lines, plant_lines = (copy.deepcopy(x) for x in (designs, events, twin_lines, plant_lines))
    r = {"instance_id": L1, "designs": designs, "submitted": submitted, "check": {"labels": ["contact_chatter"] * 8},
         "verification": {"status": status, "walking_frac": frac, "reasons": ["verdict_v1 is WORSE, not VERIFIED_IMPROVEMENT"]},
         "engine": {"events": events, "history": [{"label": "after_observation"}],
                    "ledger": {"used": sum(l["n"] for l in plant_lines), "lines": plant_lines,
                               "twin": {"used": sum(l["n"] for l in twin_lines), "lines": twin_lines}}}}
    if harness:
        r["harness"] = harness
    return r


class Comparisons(unittest.TestCase):
    D = [{"body": {"a": 1}, "vector": [0.0]}, {"body": {"a": 2}, "vector": [0.1]}]
    EV = [{"seq": 0, "kind": "tool_screen"}, {"seq": 1, "kind": "assimilated_check"}]
    TL = [{"item": "twin_observe", "n": 4}, {"item": "twin_cma", "n": 800}]
    PL = [{"item": "observe", "n": 4}, {"item": "repair", "n": 300}]

    def test_exact_reproduction_ignores_only_the_engineer_event(self):
        stored = _record(self.D, 1, self.EV, self.TL, self.PL)
        new = _record(self.D, 1, [self.EV[0], {"seq": 1, "kind": "engineer_plan", "plan": {}}, {"seq": 2, "kind": "assimilated_check"}],
                      self.TL, self.PL)
        new["verification"] = {"summary": dict(stored["verification"]), "full": {}}
        self.assertTrue(ta1.compare_to_stored(new, stored)["exact"])
        new["engine"]["ledger"]["twin"]["lines"][1] = {"item": "twin_cma", "n": 799}
        res = ta1.compare_to_stored(new, stored)
        self.assertFalse(res["exact"])
        self.assertFalse(res["checks"]["twin_lines"])

    def test_stored_verdict_parsing(self):
        self.assertEqual(ta1.stored_verdict({"reasons": ["verdict_v1 is WORSE, not VERIFIED_IMPROVEMENT"]}), "WORSE")
        self.assertEqual(ta1.stored_verdict({"status": "PARTIAL_IMPROVEMENT", "reasons": ["candidate aggregate is POOR"]}),
                         "VERIFIED_IMPROVEMENT")
        self.assertEqual(ta1.stored_verdict({"status": "FULL_RECOVERY", "reasons": []}), "VERIFIED_IMPROVEMENT")

    def test_prehook_prefix_and_pairing(self):
        h = {"replicate": 0, "noise_seed": 1751409197, "hook_calls": [
            {"prehook_n_plant_lines": 1, "prehook_n_twin_lines": 1, "prehook_n_events": 1, "prehook_n_history": 1,
             "prehook_fingerprint": "abc"}]}
        stored = _record(self.D, 1, self.EV, self.TL, self.PL)
        new = _record(self.D, 0, [self.EV[0], {"seq": 1, "kind": "engineer_plan"}],
                      [self.TL[0], {"item": "twin_cma", "n": 500}], [self.PL[0], {"item": "repair", "n": 120}], harness=h)
        self.assertTrue(ta1.prehook_prefix_matches(new, stored)["match"])          # only the post-hook parts differ
        new["engine"]["ledger"]["twin"]["lines"][0] = {"item": "twin_observe", "n": 5}
        self.assertFalse(ta1.prehook_prefix_matches(new, stored)["match"])
        c = {"instance_id": L1, "harness": copy.deepcopy(h)}
        t = {"instance_id": L1, "harness": copy.deepcopy(h)}
        self.assertTrue(ta1.paired_prehook_equal(c, t)["equal"])
        t["harness"]["hook_calls"][0]["prehook_fingerprint"] = "abd"
        self.assertFalse(ta1.paired_prehook_equal(c, t)["equal"])
        t["harness"] = dict(copy.deepcopy(h), replicate=1)
        self.assertFalse(ta1.paired_prehook_equal(c, t)["equal"])


class PhasesAndCaps(unittest.TestCase):
    def test_phase_lists_and_caps(self):
        cap = lambda p, **k: ta1.phase_cap(ta1.planned_runs(p, **k))["total"]  # noqa: E731
        self.assertEqual(ta1.planned_runs("1B"), [("L1", "control", 0), ("L1", "treatment", 0)])
        self.assertEqual(cap("1B"), 7208)
        self.assertEqual(cap("2a"), 14416)
        self.assertEqual(cap("2b"), 57664)
        self.assertEqual(ta1.planned_runs("2a-contingency", cases=["L3"]), [("L3", "control", 0)])
        with self.assertRaises(ValueError):
            ta1.planned_runs("2a-contingency")
        with self.assertRaises(ValueError):
            ta1.planned_runs("1B", cases=["L1"])
        self.assertEqual({r[2] for r in ta1.planned_runs("2b")}, {1, 2})
        self.assertNotIn("L5", {r[0] for r in ta1.planned_runs("2b")})
        self.assertEqual((rv1.N_INSTANCES, rv1.PHASE_CAP), (7, 824))

    def test_controls_of_ta1_are_the_rv1_designs(self):
        rv = {e[1]: e for e in rv1.DESIGNS}
        for c in ta1.CASES.values():
            f, line, idx, h = c["stored"]
            e = rv[c["instance_id"]]
            self.assertEqual((e[2], e[3], e[5], e[6]), (f, line, idx, h))


def _records_root():
    for p in (os.environ.get("TA1_RECORDS_ROOT"), os.path.join(ROOT, "artifacts", "vm", "ds1", "eval"),
              os.path.join(os.path.dirname(ROOT), "Creature-Forge", "artifacts", "vm", "ds1", "eval")):
        if p and os.path.isdir(p):
            return p
    return None


class StoredInputs(unittest.TestCase):
    """Reads the stored DS-1 records (data only) to confirm every preregistered reference resolves exactly."""

    def test_preregistered_designs_resolve(self):
        root = _records_root()
        if root is None:
            self.skipTest("stored DS-1 records not available locally")
        for e in rv1.DESIGNS:
            r = rv1.resolve(root, e)
            self.assertEqual(r["problems"], [], e[0])
            self.assertEqual(r["record"]["instance_id"], e[1])


class NoPhysicsGuards(unittest.TestCase):
    def setUp(self):
        boom = mock.Mock(side_effect=AssertionError("simulation attempted"))
        self.patches = [mock.patch.object(hp, name, boom) for name in ("plant_rollout", "walk_seeds", "observe", "plant_cma", "verify")]
        self.patches += [mock.patch.object(ta1, "build_instance", boom), mock.patch.object(ta1, "run_episode", boom),
                         mock.patch.object(ta1, "_execute", boom), mock.patch.object(rv1, "_execute", boom)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_default_and_unapproved_runs_never_simulate(self):
        with mock.patch("sys.stdout"):
            self.assertEqual(ta1.main([]), 0)
            self.assertEqual(ta1.main(["--phase", "1B"]), 0)
            self.assertEqual(ta1.main(["--phase", "1B", "--execute"]), 2)
            outside = os.path.join(tempfile.gettempdir(), "ta1_unit_test.jsonl")
            self.assertEqual(ta1.main(["--phase", "1B", "--execute", "--approved-by", "x", "--max-rollouts", "7207",
                                       "--out", outside]), 2)
            self.assertEqual(ta1.main(["--phase", "1B", "--execute", "--approved-by", "x", "--max-rollouts", "7208",
                                       "--out", os.path.join(ROOT, "inside.jsonl")]), 2)
            self.assertEqual(ta1.main(["--phase", "1B", "--execute", "--approved-by", "x", "--max-rollouts", "7208",
                                       "--out", outside, "--artifacts-root", os.path.join(tempfile.gettempdir(), "no-such")]), 2)
            self.assertEqual(rv1.main([]), 0)
            self.assertEqual(rv1.main(["--execute"]), 2)
            self.assertEqual(rv1.main(["--execute", "--phase", "1A", "--approved-by", "x", "--max-rollouts", "823",
                                       "--out", outside]), 2)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "inside.jsonl")))

    def test_only_a_complete_approved_command_reaches_execution(self):
        with tempfile.TemporaryDirectory() as art:
            for name in (ta1.A1E6["thresholds"], ta1.A1E6["walkers"]):
                with open(os.path.join(art, name), "w") as fh:
                    fh.write("{}\n")
            out = os.path.join(art, "runs", "ta1.jsonl")
            with mock.patch.object(ta1, "_execute", mock.Mock(return_value=0)) as ex, mock.patch("sys.stdout"):
                self.assertEqual(ta1.main(["--phase", "1B", "--execute", "--approved-by", "owner (unit test)", "--max-rollouts",
                                           "7208", "--out", out, "--artifacts-root", art]), 0)
            self.assertEqual(ex.call_count, 1)
            args, runs, inputs, cap = ex.call_args[0]
            self.assertEqual(runs, ta1.PHASES["1B"])
            self.assertEqual(cap["total"], 7208)

    def test_import_and_dry_run_never_step_physics(self):
        import subprocess
        code = (
            "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import mujoco\n"
            "def boom(*a, **k):\n    raise SystemExit(7)\n"
            "mujoco.mj_step = boom\n"
            "from creature_forge import hidden_plant as hp\n"
            "for n in ('plant_rollout', 'walk_seeds', 'observe', 'plant_cma', 'verify'): setattr(hp, n, boom)\n"
            "import ta1_tool_access as t, rv1_reverify as r\n"
            "assert t.main(['--phase', '2b']) == 0 and t.main([]) == 0 and r.main([]) == 0\n"
            "print('no-physics-ok')\n") % (ROOT, os.path.join(ROOT, "scripts"))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertIn("no-physics-ok", p.stdout)

    def test_out_path_must_be_outside_the_repository(self):
        self.assertTrue(ta1.inside(os.path.join(ROOT, "scripts", "x.jsonl"), ROOT))
        self.assertFalse(ta1.inside(os.path.join(os.path.dirname(ROOT), "elsewhere", "x.jsonl"), ROOT))


if __name__ == "__main__":
    unittest.main()
