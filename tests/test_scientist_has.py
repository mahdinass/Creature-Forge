"""Tests for creature_forge.scientist_has with scripted replies (SCRIPTED_MOCK; no network, no cost)."""
import json
import unittest

from creature_forge import scientist_has as sh
from creature_forge.investigation import SCRIPTED_MODEL

DESIGN = {"body": {"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.16, "foot_friction": 1.0,
                   "torque_limit": 60.0, "leg_density": 1000.0}, "vector": [0.1] * 17}
STATE = {"experiments": [{"id": "X0:observe", "kind": "observe", "features": {
    1: {"walking": 0.0, "time_upright": 2.1, "pitch_mean": 0.2, "slip_fraction": 0.3},
    2: {"walking": 0.0, "time_upright": 1.9, "pitch_mean": 0.25, "slip_fraction": 0.35}}}],
         "posterior": [{"pid": "contact_friction:feet(factor=0.3)", "source": "generic", "w": 0.9}],
         "residuals_of_map": {"X0:observe": {"pitch_mean": 1.4, "slip_fraction": 0.2}}, "plant_remaining": 690,
         "twin_remaining": 2600}


def hyp(kind, target, **params):
    return {"mechanism": "m", "causal_chain": "c", "expected_signature": "s",
            "primitives": [{"kind": kind, "target": target, "params": [{"name": k, "value": v} for k, v in params.items()]}]}


def make(fixture, roles=("propose", "choose", "engineer")):
    return sh.HasNemotron(roles=roles, fixture=json.loads(json.dumps(fixture)), design=DESIGN)


class Proposer(unittest.TestCase):
    def test_valid_proposals_become_deviations(self):
        n = make([{"reading": "slipping", "hypotheses": [hyp("contact_friction", "feet", factor=0.25),
                                                          hyp("payload", "torso", mass_kg=2.0, x_m=0.1)]}])
        devs = n.propose(STATE)
        self.assertEqual(len(devs), 2)
        self.assertEqual(devs[0][0]["params"], {"factor": 0.25})
        rec = n.record()
        self.assertEqual(rec["provenance"], "SCRIPTED_MOCK")
        self.assertEqual(rec["model"], SCRIPTED_MODEL)
        self.assertEqual(rec["log"][0]["status"], "ok")

    def test_out_of_range_rejected_then_repaired(self):
        bad = {"reading": "r", "hypotheses": [hyp("contact_friction", "feet", factor=9.0)]}
        good = {"reading": "r", "hypotheses": [hyp("contact_friction", "feet", factor=0.2)]}
        n = make([bad, good])
        devs = n.propose(STATE)
        self.assertEqual(devs[0][0]["params"]["factor"], 0.2)          # repaired value, not a clipped one
        self.assertTrue(any("rejected, not clipped" in e for e in n.log[0]["first_attempt_errors"]))

    def test_invalid_twice_gives_nothing(self):
        bad = {"reading": "r", "hypotheses": [hyp("contact_friction", "elbow", factor=0.2)]}
        n = make([bad, bad])
        self.assertEqual(n.propose(STATE), [])
        self.assertEqual(n.log[0]["status"], "invalid")

    def test_prompt_names_no_benchmark_family(self):
        n = make([{"reading": "r", "hypotheses": []}])
        n.propose(STATE)
        text = json.dumps(n.calls).lower() + n.system.lower()
        for fam in ("pitch_sensor_bias", "payload_offset", "low_ground_friction", "short_feet", "symptom", "family"):
            self.assertNotIn(fam, text, fam)


class ExperimenterAndEngineer(unittest.TestCase):
    CANDS = [(0.1, 0.4, {"id": "floor_test@x3", "kind": "floor", "cost": 4}),
             (0.05, 0.05, {"id": "weigh_test", "kind": "weigh", "cost": 1})]

    def test_choice_registers_predictions(self):
        preds = [{"quantity": q, "q05": 0, "q25": 1, "q50": 2, "q75": 3, "q95": 4} for q in sh.PANEL["observe"]]
        n = make([{"reading": "r", "choice": "floor_test@x3", "why": "w", "predictions": preds}])
        pick = n.choose(self.CANDS, STATE)
        self.assertEqual(pick["id"], "floor_test@x3")
        self.assertTrue(n.predictions[0]["registered_before_run"])

    def test_bad_quantiles_fall_back_to_engine(self):
        preds = [{"quantity": q, "q05": 4, "q25": 1, "q50": 2, "q75": 3, "q95": 4} for q in sh.PANEL["observe"]]
        r = {"reading": "r", "choice": "floor_test@x3", "why": "w", "predictions": preds}
        n = make([r, r])
        pick = n.choose(self.CANDS, STATE)
        self.assertEqual(pick["id"], "floor_test@x3")       # engine's best (first) candidate
        self.assertEqual(n.log[0]["fallback"], "engine_best")
        self.assertEqual(n.predictions, [])

    def test_engineer_and_inactive_roles(self):
        n = make([{"reading": "r", "tool_order": ["foot_friction", "timing"], "p_pass": 0.6, "why": "w"}])
        out = n.engineer(STATE, [{"tool": "foot_friction", "score": 1.0, "probe": "foot_friction@x2"}])
        self.assertEqual(out, {"tool_order": ["foot_friction", "timing"], "p_pass": 0.6})
        a3h = make([], roles=("propose",))
        self.assertEqual(a3h.engineer(STATE, []), {})
        self.assertEqual(a3h.choose(self.CANDS, STATE)["id"], "floor_test@x3")
        self.assertEqual(a3h.calls, [])


if __name__ == "__main__":
    unittest.main()
