"""Unit tests of the Stage-2 HaS agent pieces that need no rollouts: action validation (SCRIPTED_MOCK), memory dossiers
(predicates, validation, deterministic support, revision rules, freezing), the learned posterior's training code, and prompt
hygiene (no benchmark family names). End-to-end episodes are checked on the VM (scripts/hdb_agent_run.py)."""
import json
import math
import unittest

import numpy as np

from creature_forge import amortized_posterior as ap
from creature_forge import has_agent as ha
from creature_forge import has_memory as hm

DESIGN = {"body": {"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.16, "foot_friction": 1.0,
                   "torque_limit": 60.0, "leg_density": 1000.0}, "vector": [0.1] * 17}


class _Bench:
    designs = [{"index": 0}, {"index": 1}]


class _Session:
    """Minimal stand-in for LabSession in validation tests."""
    b = _Bench()
    memory = None
    learned = None

    def __init__(self):
        self.evidence = {1: {"checks": {"8": ["walking"] * 8}}}

    def _candidate(self, spec):
        return ({"id": spec}, None) if spec in ("cf:freq@x0.85", "floor_test@x3", "weigh_test") else (None, f"unknown {spec}")


def reply(action, **kw):
    return {"understanding": "u", "uncertainty": "q", "action": action, "why": "w", **kw}


PRED = [{"quantity": q, "q05": 0, "q25": 1, "q50": 2, "q75": 3, "q95": 4} for q in ha.PRED_QUANTITIES]


class AgentValidation(unittest.TestCase):
    def setUp(self):
        self.n = ha.NemotronScientist(fixture=[], design=DESIGN)
        self.s = _Session()

    def errs(self, r):
        return self.n._validate(r, self.s)[0]

    def test_missing_prediction_is_recorded_not_fatal(self):
        self.assertEqual(self.errs(reply("experiment", experiment="cf:freq@x0.85", prediction=PRED)), [])
        errs, out = self.n._validate(reply("experiment", experiment="cf:freq@x0.85"), self.s)
        self.assertEqual(errs, [])                                     # v3: the experiment still runs
        self.assertIn("missing", out["prediction_issue"])
        self.assertTrue(self.errs(reply("experiment", experiment="cf:nonsense@x9", prediction=PRED)))

    def test_hypotheses_rejected_not_clipped(self):
        h = {"mechanism": "m", "causal_chain": "c", "expected_signature": "s",
             "primitives": [{"kind": "contact_friction", "target": "feet", "params": [{"name": "factor", "value": 9.0}]}]}
        e = self.errs(reply("propose", hypotheses=[h]))
        self.assertTrue(any("not clipped" in x for x in e), e)

    def test_repair_fields(self):
        self.assertEqual(self.errs(reply("repair", tool="posture", mode="twin", start_edits="pitch_ref@-0.1R")), [])
        self.assertTrue(self.errs(reply("repair", tool="hammer", mode="twin")))
        self.assertTrue(self.errs(reply("repair", tool="posture", mode="plant", plant_share=3.0)))
        self.assertTrue(self.errs(reply("repair", tool="posture", mode="twin", start_edits="pitch_ref@x7")))

    def test_design_references(self):
        self.assertEqual(self.errs(reply("conclude", design=1)), [])
        self.assertTrue(self.errs(reply("conclude", design=5)))
        self.assertEqual(self.errs(reply("assimilate", design=1)), [])
        self.assertTrue(self.errs(reply("assimilate", design=0)))          # no plant check on design 0

    def test_memory_tools_unavailable_without_memory(self):
        self.assertTrue(self.errs(reply("apply_dossier", dossier="D1")))
        self.assertTrue(self.errs(reply("use_learned")))

    def test_prompts_name_no_benchmark_family(self):
        text = (ha.AGENT_SYSTEM + hm.CONSOLIDATOR_SYSTEM).lower()
        for fam in ("pitch_sensor_bias", "payload_offset", "low_ground_friction", "short_feet", "feedback_gain_loss",
                    "actuator_weakness", "one_side_weakness", "clock_fault", "heavy_torso", "sensor_latency",
                    "joint_damping_wear", "leg_asymmetry", "symptom", "family"):
            self.assertNotIn(fam, text, fam)


def summary(true, pitch, tool, outcome, base="b"):
    return {"instance_id": f"{base}:x:1", "base_id": base, "measurements": {"observe": {"pitch_mean": pitch, "walking_frac": 0.0}},
            "true_structure": true, "submitted_tool": tool, "outcome": outcome}


DOSSIER = {"id": "D1", "title": "forward lean", "principle": "p",
           "mechanism": {"structure": [["sensor_bias", "pitch"]], "params": {"sensor_bias.rad": [-0.3, -0.03]}},
           "signature": [{"experiment": "observe", "feature": "pitch_mean", "op": ">", "value": 0.1}], "fails_when": [],
           "repair": {"tools": ["posture"], "start_edits": "pitch_ref@-0.1R"}, "status": "active", "history": []}


class Memory(unittest.TestCase):
    def test_predicates(self):
        t = {"observe": {"pitch_mean": 0.2, "slip_fraction": None}}
        self.assertTrue(hm.eval_predicate(t, {"experiment": "observe", "feature": "pitch_mean", "op": ">", "value": 0.1}))
        self.assertIsNone(hm.eval_predicate(t, {"experiment": "observe", "feature": "slip_fraction", "op": ">", "value": 0.1}))
        self.assertIsNone(hm.eval_predicate(t, {"experiment": "floor_test@x3", "feature": "pitch_mean", "op": ">", "value": 0}))

    def test_validation(self):
        self.assertEqual(hm.validate_dossier(DOSSIER), [])
        bad = json.loads(json.dumps(DOSSIER))
        bad["mechanism"]["structure"] = [["sensor_bias", "elbow"]]
        bad["mechanism"]["params"] = {"sensor_bias.rad": [-0.9, 0.0]}
        bad["repair"]["tools"] = ["hammer"]
        bad["signature"] = []
        e = hm.validate_dossier(bad)
        self.assertEqual(len(e), 4, e)

    def test_support_is_deterministic_counting(self):
        S = [summary([["sensor_bias", "pitch"]], 0.2, "posture", "FULL_RECOVERY"),
             summary([["sensor_bias", "pitch"]], 0.15, "timing", "NOT_RECOVERED"),
             summary([["payload", "torso"]], 0.3, "posture", "NOT_RECOVERED"),
             summary([["sensor_bias", "pitch"]], 0.05, "posture", "FULL_RECOVERY"),
             summary([["payload", "torso"]], 0.0, "torso_mass", "FULL_RECOVERY")]
        sup = hm.compute_support(DOSSIER, S)
        self.assertEqual(sup["matched"], 3)
        self.assertEqual(sup["matched_with_mechanism"], 2)
        self.assertAlmostEqual(sup["precision"], 0.667, places=3)
        self.assertAlmostEqual(sup["recall"], 0.667, places=3)
        self.assertEqual(sup["recommended_repair"], [1, 2])
        self.assertEqual(sup["other_repairs"], [0, 1])

    def test_revision_rule_and_freeze(self):
        S = [summary([["payload", "torso"]], 0.3, "posture", "NOT_RECOVERED", base=f"b{i}") for i in range(4)]
        S.append(summary([["sensor_bias", "pitch"]], 0.3, "posture", "FULL_RECOVERY"))
        m = hm.Memory([json.loads(json.dumps(DOSSIER))], frozen=False)
        m.refresh_support(S)
        self.assertEqual(m.get("D1")["status"], "contested")           # precision 1/5 on 5 matches
        frozen = hm.Memory([json.loads(json.dumps(DOSSIER))], frozen=True)
        with self.assertRaises(RuntimeError):
            frozen.refresh_support(S)

    def test_mechanism_particles_are_valid_deviations(self):
        ps = hm.mechanism_particles(DOSSIER, 10.0)
        self.assertEqual(len(ps), 3)
        self.assertTrue(all(-0.3 <= p[0]["params"]["rad"] <= -0.03 for p in ps))

    def test_dossier_schema_roundtrip(self):
        x = {"title": "t", "principle": "p", "structure": [{"kind": "payload", "target": "torso"}],
             "params": [{"name": "payload.mass_kg", "lo": 0.5, "hi": 3.0}, {"name": "payload.x_m", "lo": 0.05, "hi": 0.15}],
             "signature": [{"experiment": "weigh_test", "feature": "com_x_m", "op": ">", "value": 0.01}], "fails_when": [],
             "tools": ["posture", "torso_mass"], "start_edits": ""}
        d = hm.Consolidator.to_dossier(x, "D9")
        self.assertEqual(hm.validate_dossier(d), [])
        self.assertIsNone(d["repair"]["start_edits"])
        self.assertEqual(len(hm.mechanism_particles(d, 10.0)), 3)


class Learned(unittest.TestCase):
    def test_training_separates_synthetic_classes(self):
        rng = np.random.default_rng(0)
        rows = []
        for i in range(400):
            c = i % len(ap.CLASSES)
            x = rng.normal(0, 1, 30)
            x[c] += 4.0
            rows.append({"base_id": f"b{(i // 10) % 10}", "cls": c, "x_obs": x.tolist(), "x_full": x.tolist(), "y": [float(x[c]) * 0.1]})
        cv = ap.cross_validate(rows, full=False)
        self.assertGreater(cv["top1"], 0.9)
        self.assertLess(cv["log_loss"], cv["chance_log_loss"])

    def test_param_codec(self):
        p = {"kind": "payload", "target": "torso", "params": {"mass_kg": 2.0, "x_m": 0.1}}
        y = ap.encode_params(p, 10.0)
        back = ap.decode_params("payload", "torso", y, 10.0)
        self.assertAlmostEqual(back["params"]["mass_kg"], 2.0, places=6)
        f = ap.decode_params("contact_friction", "feet", [math.log(0.3)], 10.0)
        self.assertAlmostEqual(f["params"]["factor"], 0.3, places=6)
        self.assertIsNone(ap.decode_params("contact_friction", "feet", [math.log(50.0)], 10.0))   # out of range: rejected


if __name__ == "__main__":
    unittest.main()
