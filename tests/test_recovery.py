"""Tests for creature_forge.recovery (full_recovery_v1). Status logic runs over an injected job_fn (no MuJoCo);
one real MuJoCo test checks that the conditions are matched with arena.evaluate_arms."""
import json
import unittest

from creature_forge import arena
from creature_forge import creature_walk as cw
from creature_forge import recovery as rc
from creature_forge.arena import VARIATION_PRESET
from creature_forge.challenges import aggregate_outcome
from creature_forge.locomotion import DEFAULT_CRITERIA
from creature_forge.sandbox import SandboxBody

BODY = SandboxBody().as_dict()
MIN_SPEED = cw.creature_criteria(SandboxBody()).min_speed
VS = list(range(100, 124))
CS = list(range(200, 224))
ORIG = {"body": BODY, "vector": [0.0] * 15}
CAND = {"body": BODY, "vector": [1.0] + [0.0] * 14}


def make_job_fn(*, orig_score=0.0, cand_pass=24, cand_score=5.0, cand_fail_outcome="POOR", conf_pass=24, conf_speed=None,
                conf_contact=0.0, error_seed=None, error_on="validate", orig_pass_outcome="FAIL"):
    """Fake seed_job. The original has vector[0] == 0, the candidate 1; the 20 s runs are the confirmation."""
    conf_speed = MIN_SPEED + 0.1 if conf_speed is None else conf_speed

    def fn(job):
        seed, dur = job["seed"], job["spec"]["duration"]
        cand = job["controllers"]["walk"]["vector"][0] == 1.0
        if error_seed is not None and cand and seed == error_seed and (dur == rc.CONFIRM_DURATION) == (error_on == "confirm"):
            return {"seed": seed, "outcome": "ERROR", "score": 0.0, "metrics": {}, "error": "boom"}
        if not cand:
            return {"seed": seed, "outcome": orig_pass_outcome, "score": orig_score, "error": None,
                    "metrics": {"speed_upright": 0.0, "body_contact_frac": 0.0, "fell": True}}
        if dur == rc.CONFIRM_DURATION:
            idx, npass = seed - CS[0], conf_pass
            ok = idx < npass
            return {"seed": seed, "outcome": "PASS" if ok else "FAIL", "score": 5.0, "error": None,
                    "metrics": {"speed_upright": conf_speed, "body_contact_frac": conf_contact, "fell": not ok}}
        ok = (seed - VS[0]) < cand_pass
        return {"seed": seed, "outcome": "PASS" if ok else cand_fail_outcome, "score": cand_score, "error": None,
                "metrics": {"speed_upright": 0.5, "body_contact_frac": 0.0, "fell": False}}
    return fn


def run(**kw):
    return rc.assess(ORIG, CAND, VS, CS, job_fn=make_job_fn(**kw))


class StatusLogic(unittest.TestCase):
    def test_full_recovery(self):
        a = run()
        self.assertEqual(a["status"], "FULL_RECOVERY")
        self.assertEqual(a["reasons"], [])
        self.assertEqual(a["rule"], rc.RECOVERY_RULE)
        self.assertEqual(a["validation"]["verdict"]["status"], "VERIFIED_IMPROVEMENT")
        self.assertEqual(a["validation"]["aggregate"], "PASS")
        self.assertTrue(a["confirmation"]["run"] and a["confirmation"]["passed"])
        self.assertEqual(a["rollouts"], {"validation": 48, "confirmation": 24, "confirmation_rollout_equivalents": 48.0})
        self.assertEqual(a["variation"], VARIATION_PRESET)
        json.dumps(a)

    def test_pass_but_verdict_not_verified(self):
        a = run(orig_score=5.0, orig_pass_outcome="PASS")
        self.assertEqual(a["validation"]["aggregate"], "PASS")
        self.assertNotEqual(a["validation"]["verdict"]["status"], "VERIFIED_IMPROVEMENT")
        self.assertEqual(a["status"], "NOT_RECOVERED")
        self.assertFalse(a["worse"])
        self.assertFalse(a["confirmation"]["run"])
        self.assertEqual(a["rollouts"]["confirmation"], 0)
        self.assertEqual(a["rollouts"]["confirmation_rollout_equivalents"], 0.0)
        self.assertTrue(any("verdict_v1" in r for r in a["reasons"]))

    def test_verified_but_poor_is_partial(self):
        a = run(cand_pass=10)
        self.assertEqual(a["validation"]["verdict"]["status"], "VERIFIED_IMPROVEMENT")
        self.assertEqual(a["validation"]["aggregate"], "POOR")
        self.assertEqual(a["status"], "PARTIAL_IMPROVEMENT")
        self.assertFalse(a["confirmation"]["run"])
        self.assertEqual(a["rollouts"]["confirmation"], 0)
        self.assertTrue(any("aggregate" in r for r in a["reasons"]))

    def test_confirmation_walking_fraction_fails(self):
        a = run(conf_pass=10)
        self.assertEqual(a["status"], "PARTIAL_IMPROVEMENT")
        self.assertFalse(a["confirmation"]["checks"]["walking_frac"]["passed"])
        self.assertTrue(a["confirmation"]["checks"]["median_speed_upright"]["passed"])
        self.assertEqual(a["rollouts"]["confirmation"], 24)

    def test_confirmation_speed_fails(self):
        a = run(conf_speed=MIN_SPEED * 0.5)
        self.assertEqual(a["status"], "PARTIAL_IMPROVEMENT")
        self.assertFalse(a["confirmation"]["checks"]["median_speed_upright"]["passed"])
        self.assertTrue(a["confirmation"]["checks"]["walking_frac"]["passed"])
        self.assertTrue(any("upright speed" in r for r in a["reasons"]))

    def test_confirmation_body_contact_fails(self):
        a = run(conf_contact=DEFAULT_CRITERIA.max_body_contact_frac * 2)
        self.assertEqual(a["status"], "PARTIAL_IMPROVEMENT")
        self.assertFalse(a["confirmation"]["checks"]["body_contact"]["passed"])
        self.assertEqual(len(a["confirmation"]["checks"]["body_contact"]["seeds_over"]), 24)

    def test_worse_flag(self):
        a = run(orig_score=5.0, orig_pass_outcome="PASS", cand_score=0.0, cand_pass=0, cand_fail_outcome="FAIL")
        self.assertEqual(a["validation"]["verdict"]["status"], "WORSE")
        self.assertEqual(a["status"], "NOT_RECOVERED")
        self.assertTrue(a["worse"])

    def test_error_is_inconclusive_never_success(self):
        a = run(error_seed=VS[3])
        self.assertEqual(a["status"], "INCONCLUSIVE_ERROR")
        self.assertFalse(a["confirmation"]["run"])
        self.assertEqual(a["rollouts"]["confirmation"], 0)
        row = a["validation"]["candidate"][3]
        self.assertEqual((row["outcome"], row["error"], row["score"]), ("ERROR", "boom", None))
        self.assertEqual(a["errors"][0]["seed"], VS[3])

    def test_confirmation_error_is_inconclusive(self):
        a = run(error_seed=CS[0], error_on="confirm")
        self.assertEqual(a["status"], "INCONCLUSIVE_ERROR")
        self.assertTrue(a["confirmation"]["run"])

    def test_pool_error_value_becomes_error_row(self):
        def fn(job):
            return ("error", "worker died")
        rows = rc.run_walk_seeds(BODY, CAND["vector"], VS[:2], job_fn=fn)
        self.assertEqual([r["outcome"] for r in rows], ["ERROR", "ERROR"])
        self.assertEqual(rows[0]["error"], "worker died")

    def test_overlapping_seeds_raise(self):
        with self.assertRaises(ValueError):
            rc.assess(ORIG, CAND, VS, [VS[0]] + CS[1:], job_fn=make_job_fn())

    def test_eighty_percent_boundary(self):
        self.assertEqual(aggregate_outcome(["PASS"] * 19 + ["POOR"] * 5), "POOR")
        self.assertEqual(aggregate_outcome(["PASS"] * 20 + ["POOR"] * 4), "PASS")
        self.assertEqual(run(cand_pass=19)["status"], "PARTIAL_IMPROVEMENT")
        self.assertEqual(run(cand_pass=20)["status"], "FULL_RECOVERY")
        self.assertEqual(run(conf_pass=19)["status"], "PARTIAL_IMPROVEMENT")
        self.assertEqual(run(conf_pass=20)["status"], "FULL_RECOVERY")

    def test_conditions_recorded_per_seed(self):
        rows = rc.run_walk_seeds(BODY, CAND["vector"], VS[:3], job_fn=make_job_fn())
        for r in rows:
            self.assertIn("perturb", r)
            self.assertIn("friction_used", r)

    def test_summarize_statuses(self):
        s = rc.summarize_statuses([run(), run(), run(cand_pass=10), run(error_seed=VS[0])])
        self.assertEqual(s["counts"], {"FULL_RECOVERY": 2, "PARTIAL_IMPROVEMENT": 1, "NOT_RECOVERED": 0, "INCONCLUSIVE_ERROR": 1})


class MatchedWithArena(unittest.TestCase):
    def test_scores_equal_arena_evaluate_arms(self):
        seeds = [100001, 100002]
        vec = list(cw.R2_WINNER)
        arm = {"arm_id": "a", "body": BODY, "controllers": {"stand": None, "walk": {"vector": vec, "provenance": {"kind": "custom"}}}}
        ref = arena.evaluate_arms("walk", [arm], seeds, variation=VARIATION_PRESET)["results"]["a"]
        rows = rc.run_walk_seeds(BODY, vec, seeds)
        self.assertEqual([r["score"] for r in rows], [r["score"] for r in ref])
        self.assertEqual([r["outcome"] for r in rows], [r["outcome"] for r in ref])


if __name__ == "__main__":
    unittest.main()
