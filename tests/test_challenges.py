import json
import math
import unittest
from pathlib import Path

import numpy as np

from creature_forge import challenges as ch
from creature_forge import creature_walk as cw
from creature_forge.forge_pool import ForgePool
from creature_forge.sandbox import SandboxBody

ZOO = json.loads((Path(__file__).parent / "fixtures" / "forge_zoo.json").read_text(encoding="utf-8"))["creatures"]
BY_ID = {c["id"]: c for c in ZOO}
DEFAULT = BY_ID["default"]["body"]
DOOMED = BY_ID["doomed"]["body"]
SEEDS = (100201, 100202)


def stand_spec(seeds=SEEDS, duration=3.0, **kw):
    return ch.ChallengeSpec.from_dict({"kind": "stand", "seeds": list(seeds), "duration": duration, **kw})


def push_spec(seeds=SEEDS, duration=2.5, **kw):
    return ch.ChallengeSpec.from_dict({"kind": "push", "seeds": list(seeds), "duration": duration, "push_time": 0.5, **kw})


def synthetic_tel(pitch, z=0.9):
    n = len(pitch)
    return {"t": np.arange(n) * 0.005, "torso_pos": np.column_stack([np.zeros(n), np.full(n, z), np.zeros(n)]),
            "torso_pitch": np.asarray(pitch, dtype=float), "ctrl_demand": np.zeros((n, 6)),
            "foot_slip_speed": np.zeros((n, 2)), "foot_contact": np.ones((n, 2))}


class SpecTests(unittest.TestCase):
    def test_defaults_per_kind(self):
        self.assertEqual(ch.default_spec("stand", [1]).duration, 8.0)
        self.assertEqual(ch.default_spec("push", [1]).duration, 5.0)
        w = ch.default_spec("walk", [1])
        self.assertEqual((w.duration, w.start, w.perturb), (10.0, "neutral", 0.03))
        s = ch.default_spec("stand", [1])
        self.assertEqual((s.start, s.perturb, s.target_force, s.max_force, s.settle_s), ("drawn", 0.02, 10.0, 80.0, 0.3))

    def test_round_trip(self):
        spec = ch.default_spec("push", [5, 6, 7])
        self.assertEqual(ch.ChallengeSpec.from_dict(spec.to_dict()), spec)
        json.dumps(spec.to_dict())

    def test_validation_names_the_problem(self):
        bad = [({"kind": "jump", "seeds": [1]}, "kind"), ({"kind": "stand", "seeds": []}, "seeds"),
               ({"kind": "stand", "seeds": [-1]}, "seeds"), ({"kind": "stand", "seeds": [1, 1]}, "distinct"),
               ({"kind": "stand", "seeds": [1], "duration": float("nan")}, "duration"),
               ({"kind": "stand", "seeds": [1], "settle_s": 99}, "settle_s"),
               ({"kind": "stand", "seeds": [1], "start": "sideways"}, "start"),
               ({"kind": "stand", "seeds": [1], "color": "red"}, "unknown"),
               ({"kind": "push", "seeds": [1], "max_force": 10, "target_force": 25}, "max_force"),
               ({"kind": "push", "seeds": [1], "duration": 1.0}, "push must end"), ({"seeds": [1]}, "kind")]
        for d, word in bad:
            with self.assertRaises(ValueError, msg=str(d)) as cm:
                ch.ChallengeSpec.from_dict(d)
            self.assertIn(word, str(cm.exception), d)


class AggregationTests(unittest.TestCase):
    def test_aggregate_outcome_rule(self):
        f = ch.aggregate_outcome
        self.assertEqual(f(["PASS"] * 8), "PASS")
        self.assertEqual(f(["PASS"] * 7 + ["FAIL"]), "PASS")         # 87.5 % >= 80 %
        self.assertEqual(f(["PASS"] * 6 + ["FAIL"] * 2), "POOR")     # 75 % PASS, 25 % FAIL
        self.assertEqual(f(["PASS"] * 4 + ["FAIL"] * 4), "FAIL")     # exactly 50 % FAIL
        self.assertEqual(f(["POOR"] * 8), "POOR")
        self.assertEqual(f(["PASS"] * 7 + ["ERROR"]), "ERROR")
        self.assertEqual(f([]), "ERROR")

    def test_wilson_interval(self):
        lo, hi = ch.wilson_interval(8, 8)
        self.assertAlmostEqual(hi, 1.0)
        self.assertAlmostEqual(lo, 0.6756, places=3)
        lo, hi = ch.wilson_interval(0, 8)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.3244, places=3)
        self.assertEqual(ch.wilson_interval(0, 0), (0.0, 1.0))

    def test_summary(self):
        per = [ch.SeedResult(1, "PASS", 10.0, {}, [], 1), ch.SeedResult(2, "FAIL", 0.0, {}, [], 1),
               ch.SeedResult(3, "ERROR", 0.0, {}, [], 0, error="x"), ch.SeedResult(4, "PASS", 30.0, {}, [], 1)]
        s = ch.summarize(per)
        self.assertEqual(s["counts"], {"PASS": 2, "POOR": 0, "FAIL": 1, "ERROR": 1})
        self.assertEqual((s["score"]["min"], s["score"]["max"], s["score"]["median"]), (0.0, 30.0, 10.0))  # errors excluded
        self.assertEqual(s["pass_rate"]["rate"], 0.5)
        self.assertEqual(ch.worst_seed(per).seed, 2)


class SettleWindowTests(unittest.TestCase):
    def test_a_lean_during_the_settle_window_is_not_a_fall_but_a_late_lean_is(self):
        from creature_forge.failures import detect_failures
        body = SandboxBody()
        early = np.zeros(400)
        early[:40] = 1.3                                    # leaning drawing: 0.2 s beyond the 1.0 rad rule
        tel = synthetic_tel(early)
        self.assertTrue(any(e.kind == "fall" for e in detect_failures(tel, body)))       # stock detector: "fall" at t = 0
        self.assertEqual([e for e in ch.settled_events(tel, body, 0.3) if e.kind == "fall"], [])
        late = np.zeros(400)
        late[200:] = 1.3
        ev = ch.settled_events(synthetic_tel(late), body, 0.3)
        fall = [e for e in ev if e.kind == "fall"]
        self.assertEqual(len(fall), 1)
        self.assertAlmostEqual(fall[0].time, 1.0, places=2)
        self.assertEqual(fall[0].evidence["settle_s"], 0.3)

    def test_height_reference_is_the_start_height(self):
        tel = synthetic_tel(np.zeros(400))
        tel["torso_pos"][250:, 1] = 0.3                      # below 0.5 * 0.9
        fall = [e for e in ch.settled_events(tel, SandboxBody(), 0.3) if e.kind == "fall"]
        self.assertAlmostEqual(fall[0].time, 1.25, places=2)

    def test_mirroring_flips_the_push_direction_conventions(self):
        n = 6
        tel = synthetic_tel(np.linspace(0.0, 0.5, n))
        tel.update({"torso_angvel": np.ones(n), "cop_x": np.full(n, 0.1), "torso_linvel": np.column_stack([np.ones(n), np.zeros(n)]),
                    "com_pos": np.column_stack([np.full(n, 0.2), np.zeros(n), np.full(n, 0.5)]),
                    "com_vel": np.column_stack([np.full(n, 0.3), np.zeros(n), np.zeros(n)]),
                    "support_x_min": np.full(n, -0.1), "support_x_max": np.full(n, 0.4)})
        m = ch._mirror(tel)
        self.assertTrue(np.allclose(m["torso_pitch"], -tel["torso_pitch"]))
        self.assertTrue(np.allclose(m["com_pos"][:, 0], -0.2) and np.allclose(m["com_pos"][:, 2], 0.5))
        self.assertTrue(np.allclose(m["com_vel"][:, 0], -0.3))
        self.assertTrue(np.allclose(m["support_x_min"], -0.4) and np.allclose(m["support_x_max"], 0.1))
        self.assertTrue(np.all(m["support_x_min"] <= m["support_x_max"]))
        self.assertTrue(np.allclose(tel["com_pos"][:, 0], 0.2))                       # input untouched


class StandTests(unittest.TestCase):
    def test_default_body_stands_on_every_seed_with_the_documented_metrics(self):
        res = ch.run_challenge(DEFAULT, None, stand_spec())
        self.assertEqual(res.outcome, "PASS")
        for s in res.per_seed:
            self.assertEqual(s.outcome, "PASS")
            self.assertEqual(s.score, 3.0)                  # survived the whole 3 s
            for k in ("survival_s", "fell", "fall_time", "max_abs_pitch_after_settle", "min_height_ratio",
                      "saturation_frac", "slip_frac", "settle_s", "z_ref"):
                self.assertIn(k, s.metrics)
            self.assertFalse(s.metrics["fell"])
            self.assertEqual(s.rollouts, 1)
        self.assertEqual(res.rollouts, 2)
        self.assertEqual(res.controller["stand"]["kind"], "stand-pd")
        self.assertFalse(res.controller["stand"]["edited"])
        self.assertEqual(res.controller["walk"]["kind"], "none")

    def test_stand_is_deterministic(self):
        a = ch.run_seed(DEFAULT, None, stand_spec(), 100201).as_dict()
        b = ch.run_seed(DEFAULT, None, stand_spec(), 100201).as_dict()
        self.assertEqual(a, b)

    def test_doomed_creature_fails_with_structured_evidence_not_an_exception(self):
        res = ch.run_challenge(DOOMED, None, stand_spec())
        self.assertEqual(res.outcome, "FAIL")
        s = res.per_seed[0]
        self.assertEqual(s.outcome, "FAIL")
        self.assertTrue(s.metrics["fell"])
        self.assertLess(s.score, 3.0)
        self.assertTrue(any(e["kind"] == "fall" for e in s.events))
        self.assertIsNone(s.error)
        f = res.forensics
        self.assertEqual(f["seed_outcome"], "FAIL")
        for k in ("failure", "support", "actuation", "contacts", "timeline"):
            self.assertIn(k, f)
        self.assertTrue(f["failure"]["fell"])
        self.assertTrue(all(x.forensics is None for x in res.per_seed))
        json.dumps(res.as_dict(), allow_nan=False)           # strict JSON

    def test_edited_stand_controller_is_flagged_in_the_provenance(self):
        res = ch.run_challenge(DEFAULT, {"stand": {"kp": 200.0}}, stand_spec(seeds=(100201,), duration=2.0))
        self.assertTrue(res.controller["stand"]["edited"])
        self.assertEqual(res.controller["stand"]["params"]["kp"], 200.0)


class PushTests(unittest.TestCase):
    def test_default_body_critical_force_is_in_the_measured_band_and_bisection_is_recorded(self):
        spec = ch.default_spec("push", [100201])
        r = ch.run_seed(DEFAULT, None, spec, 100201)
        m = r.metrics
        self.assertEqual(r.score, min(m["critical_force_fwd"], m["critical_force_bwd"]))
        # forward: the Phase 0 sweep found 10-30 N survived and 40 N fell on every seed
        self.assertGreaterEqual(m["critical_force_fwd"], 25.0, m)
        self.assertLessEqual(m["critical_force_fwd"], 40.0, m)
        # backward is physically weaker: the heel is 0.04 m behind the ankle, the toe 0.12 m ahead
        self.assertGreater(m["critical_force_bwd"], 0.0, m)
        self.assertLess(m["critical_force_bwd"], m["critical_force_fwd"], m)
        self.assertEqual(m["weak_direction"], "backward")
        self.assertEqual(r.outcome, "PASS" if r.score >= spec.target_force else ("POOR" if r.score >= 0.6 * spec.target_force else "FAIL"))
        self.assertEqual(r.forensics["direction"], "backward")
        self.assertTrue(r.forensics["mirrored"])
        self.assertLess(r.forensics["force_N"], 0.0)
        self.assertTrue(r.forensics["failure"]["fell"])
        self.assertIn(m["weak_direction"], ("forward", "backward", "equal"))
        self.assertFalse(m["falls_without_push"])
        trace = m["bisection_trace"]
        self.assertEqual(len(trace), r.rollouts)
        self.assertEqual(r.rollouts, 1 + 2 * (1 + ch.PUSH_BISECTION_STEPS))
        self.assertEqual(trace[0], [0.0, True])
        self.assertTrue(any(f < 0 for f, _ in trace) and any(f > 0 for f, _ in trace))     # both directions probed
        self.assertAlmostEqual(m["force_resolution_N"], 2.5)
        # every survived force is below every fallen force, per direction (the bisection is consistent)
        for sign in (1, -1):
            ok = [abs(f) for f, s in trace if s and f * sign > 0]
            bad = [abs(f) for f, s in trace if not s and f * sign > 0]
            self.assertTrue(not ok or not bad or max(ok) < min(bad))

    def test_push_seeds_jitter_the_onset_but_each_seed_is_reproducible(self):
        spec = push_spec(seeds=(100201, 100202))
        a, b = (ch.run_seed(DEFAULT, None, spec, s) for s in spec.seeds)
        self.assertNotEqual(a.metrics["push_time_s"], b.metrics["push_time_s"])
        self.assertTrue(all(abs(r.metrics["push_time_s"] - 0.5) <= 0.1 + 1e-9 for r in (a, b)))
        self.assertEqual(ch.run_seed(DEFAULT, None, spec, 100201).as_dict(), a.as_dict())

    def test_creature_that_falls_without_a_push_scores_zero_with_forensics(self):
        r = ch.run_seed(DOOMED, None, push_spec(seeds=(100201,)), 100201)
        self.assertEqual(r.outcome, "FAIL")
        self.assertEqual(r.score, 0.0)
        self.assertTrue(r.metrics["falls_without_push"])
        self.assertEqual(r.rollouts, 1)
        self.assertEqual(r.metrics["weak_direction"], "equal")
        self.assertIsNotNone(r.forensics)
        self.assertTrue(any(e["kind"] == "fall" for e in r.events))

    def test_weak_creature_gets_forensics_at_its_first_failing_force_and_marks_mirroring(self):
        spec = push_spec(seeds=(100201,), duration=3.0)
        r = ch.run_seed(BY_ID["tiny-feet"]["body"], None, spec, 100201)
        self.assertIn(r.outcome, ("PASS", "POOR", "FAIL"))
        if r.outcome != "PASS" and not r.metrics["falls_without_push"]:
            f = r.forensics
            self.assertEqual(f["mirrored"], r.metrics["weak_direction"] == "backward")
            self.assertEqual(f["direction"], r.metrics["weak_direction"] if r.metrics["weak_direction"] != "equal" else "forward")
            self.assertGreater(f["first_failing_force_N"], r.score - 1e-9)
            self.assertLessEqual(f["first_failing_force_N"] - r.score, 2.5 + 1e-9)       # bisection resolution
            self.assertTrue(f["failure"]["fell"])


class WalkTests(unittest.TestCase):
    def test_r2_winner_walks_the_default_body_and_the_provenance_says_transfer(self):
        spec = ch.default_spec("walk", [100301, 100302])
        res = ch.run_challenge(DEFAULT, None, spec)
        self.assertEqual(res.outcome, "PASS", [s.metrics.get("label") for s in res.per_seed])
        for s in res.per_seed:
            self.assertGreater(s.score, 1.0)
            self.assertEqual(s.metrics["label"], "walking")
            self.assertEqual(s.metrics["criteria_scale"], 1.0)
        self.assertEqual(res.controller["walk"]["kind"], "r2-transfer")
        self.assertEqual(res.controller["walk"]["vector"], list(cw.R2_WINNER))

    def test_a_walker_that_falls_is_a_fail_with_evidence(self):
        res = ch.run_challenge(DOOMED, None, ch.default_spec("walk", [100301]))
        s = res.per_seed[0]
        self.assertEqual(s.outcome, "FAIL")
        self.assertTrue(s.metrics["fell"])
        self.assertTrue(any(e["kind"] == "fall" for e in s.events))
        self.assertIn("fall", res.forensics["violations"])

    def test_adapted_controller_provenance(self):
        adaptation = {"budget": 48, "rollouts_used": 48, "train_seeds": [1, 2, 3], "noise_seed": 9, "parent_vector": list(cw.R2_WINNER)}
        prov = ch.controller_provenance({"walk": {"vector": list(cw.R2_WINNER), "adaptation": adaptation}}, "walk")
        self.assertEqual(prov["walk"]["kind"], "adapted")
        self.assertEqual(prov["walk"]["adaptation"]["budget"], 48)
        self.assertEqual(ch.controller_provenance(None, "walk")["walk"]["kind"], "r2-transfer")
        self.assertEqual(ch.controller_provenance(None, "stand")["walk"]["kind"], "none")


class ErrorTests(unittest.TestCase):
    def assert_error(self, r, word):
        self.assertEqual(r.outcome, "ERROR")
        self.assertIn(word, r.error)
        self.assertEqual(r.rollouts, 0)

    def test_invalid_bodies_and_controllers_are_errors_with_a_message_never_exceptions(self):
        spec = stand_spec(seeds=(1,), duration=2.0)
        self.assert_error(ch.run_seed({**DEFAULT, "foot_length": -1.0}, None, spec, 1), "foot_length")
        self.assert_error(ch.run_seed({**DEFAULT, "wings": 2}, None, spec, 1), "wings")
        self.assert_error(ch.run_seed({**DEFAULT, "torso_mass": float("nan")}, None, spec, 1), "torso_mass")
        self.assert_error(ch.run_seed("not a body", None, spec, 1), "body")
        self.assert_error(ch.run_seed(DEFAULT, {"stand": {"kp": -5.0}}, spec, 1), "kp")
        self.assert_error(ch.run_seed(DEFAULT, {"stand": {"warp": 1}}, spec, 1), "warp")
        wspec = ch.default_spec("walk", [1])
        self.assert_error(ch.run_seed(DEFAULT, {"walk": [0.0] * 3}, wspec, 1), "15 numbers")

    def test_challenge_with_an_invalid_body_is_an_ERROR_outcome_and_still_json(self):
        res = ch.run_challenge({**DEFAULT, "foot_length": -1.0}, None, stand_spec(seeds=(1, 2), duration=2.0))
        self.assertEqual(res.outcome, "ERROR")
        self.assertEqual(res.summary["counts"]["ERROR"], 2)
        self.assertEqual(res.rollouts, 0)
        self.assertIsNone(res.summary["score"]["median"])
        json.dumps(res.as_dict(), allow_nan=False)

    def test_error_is_not_folded_into_fail(self):
        per = [ch.SeedResult(1, "FAIL", 0, {}, [], 1), ch.SeedResult(2, "FAIL", 0, {}, [], 1),
               ch.SeedResult(3, "ERROR", 0, {}, [], 0, error="boom")]
        self.assertEqual(ch.aggregate_outcome([s.outcome for s in per]), "ERROR")


class PoolIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = ForgePool(2)

    @classmethod
    def tearDownClass(cls):
        cls.pool.close()

    def test_pooled_run_equals_inline_run_and_reports_progress_per_seed(self):
        spec = stand_spec(seeds=(100201, 100202, 100203), duration=2.0)
        seen = []
        pooled = ch.run_challenge(BY_ID["top-heavy"]["body"], None, spec, pool=self.pool, progress=lambda d, t: seen.append((d, t)))
        inline = ch.run_challenge(BY_ID["top-heavy"]["body"], None, spec)
        self.assertEqual([s.as_dict() for s in pooled.per_seed], [s.as_dict() for s in inline.per_seed])
        self.assertEqual(pooled.outcome, inline.outcome)
        self.assertEqual(seen, [(1, 3), (2, 3), (3, 3)])

    def test_whole_zoo_runs_without_exceptions_and_orders_sensibly(self):
        spec = stand_spec(seeds=(100201,), duration=2.0)
        out = {}
        for c in ZOO:
            out[c["id"]] = ch.run_challenge(c["body"], None, spec, pool=self.pool)
            self.assertIn(out[c["id"]].outcome, ("PASS", "POOR", "FAIL"), c["id"])
        self.assertEqual(out["default"].outcome, "PASS")
        self.assertEqual(out["doomed"].outcome, "FAIL")
        for c in ZOO:
            SandboxBody(**{**c["body"], "pose": tuple(c["body"]["pose"])}).validate()
            for k in ("thigh_length_r", "shank_length_r", "foot_length_r"):
                self.assertIsNotNone(c["body"][k], (c["id"], k))

    def test_a_dying_worker_becomes_an_error_seed(self):
        class Dying:
            def imap(self, fn, jobs):
                yield 0, ("error", "worker process died: simulated")
                yield 1, fn(jobs[1])
        res = ch.run_challenge(DEFAULT, None, stand_spec(seeds=(100201, 100202), duration=2.0), pool=Dying())
        self.assertEqual([s.outcome for s in res.per_seed], ["ERROR", "PASS"])
        self.assertIn("died", res.per_seed[0].error)
        self.assertEqual(res.outcome, "ERROR")


class ReplayTests(unittest.TestCase):
    def test_stand_replay_is_decimated_and_consistent(self):
        spec = stand_spec(seeds=(100201,), duration=2.0)
        p = ch.replay_payload(DEFAULT, None, spec, 100201, max_hz=50)
        n = len(p["time"])
        self.assertLessEqual(n, 2.0 * 50 + 2)
        self.assertGreater(n, 50)
        self.assertEqual(len(p["frames"]["pos"]), n)
        self.assertEqual(len(p["series"]["torso_height"]), n)
        self.assertIsNone(p["push"])
        self.assertFalse(p["metrics"]["fell"])
        self.assertEqual(p["challenge"]["kind"], "stand")
        json.dumps(p, allow_nan=False)

    def test_push_replay_applies_the_signed_force_and_uses_settled_events(self):
        spec = push_spec(seeds=(100201,), duration=2.5)
        p = ch.replay_payload(DEFAULT, None, spec, 100201, force=100.0, direction=-1)
        self.assertEqual(p["push"]["force"], -100.0)
        self.assertTrue(p["metrics"]["fell"])
        self.assertTrue(any(e["kind"] == "fall" and e["time"] >= spec.settle_s for e in p["events"]))
        q = ch.replay_payload(DEFAULT, None, spec, 100201)
        self.assertEqual(q["push"]["force"], spec.target_force)
        with self.assertRaises(ch.ChallengeError):
            ch.replay_payload(DEFAULT, None, spec, 100201, direction=0)
        with self.assertRaises(ch.ChallengeError):
            ch.replay_payload(DEFAULT, None, spec, 100201, force=-5.0)

    def test_walk_replay(self):
        spec = ch.ChallengeSpec.from_dict({"kind": "walk", "seeds": [100301], "duration": 4.0})
        p = ch.replay_payload(DEFAULT, None, spec, 100301)
        n = len(p["time"])
        self.assertLessEqual(n, 4.0 * 50 + 2)
        self.assertEqual(len(p["frames"]["pos"]), n)
        self.assertEqual(len(p["series"]["foot_contact"]), n)
        self.assertIn("locomotion", p)
        self.assertTrue(all(math.isfinite(x) for x in p["series"]["torso_x"]))


if __name__ == "__main__":
    unittest.main()
