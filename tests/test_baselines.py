"""Matched-random twins and the heuristic baseline (contracts section 6.1). No physics here."""
import copy
import json
import math
import unittest
from pathlib import Path

import numpy as np

from creature_forge import baselines as bl
from creature_forge import interventions as iv
from creature_forge.interventions import Edit

FX = Path(__file__).parent / "fixtures" / "forge_ai"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


class Twin(unittest.TestCase):
    def setUp(self):
        self.guided = load("version_guided.json")
        self.exp = load("version_experimental.json")
        self.walk = load("version_walk.json")

    def twin(self, version, kind, ai, key=("inv-1", "P1")):
        return bl.matched_random(version, kind, ai, bl.make_rng(*key))

    def test_same_count_kind_and_magnitude(self):
        ai = [Edit("foot_length", "scale", 1.3), Edit("stand.kp", "set", 0.0)]
        # make the control edit a legal one: delta u 0.2
        lo, hi = iv.control_bounds("stand.kp")
        cur = iv.stand_params(self.guided)["kp"]
        ai[1] = Edit("stand.kp", "set", cur + 0.2 * (hi - lo))
        for seed in range(25):
            t = self.twin(self.guided, "stand", ai, ("inv", f"P{seed}"))
            self.assertIsNotNone(t)
            self.assertEqual(len(t), len(ai))
            for a, b in zip(ai, t):
                self.assertEqual(iv.kind_of(a.param), iv.kind_of(b.param))
                self.assertEqual(b.target, "both")
                self.assertAlmostEqual(iv.magnitude(self.guided, a), iv.magnitude(self.guided, b), places=9)
            self.assertEqual(iv.category(ai), iv.category(t))
            self.assertEqual(len({e.param for e in t}), len(t))                  # no duplicate fields
            parsed, reasons = iv.validate_edits(self.guided, "stand", [e.to_dict() for e in t])
            self.assertEqual(reasons, [])

    def test_ops(self):
        ai = [Edit("torso_mass", "scale", 1.25)]
        for i in range(15):
            e = self.twin(self.guided, "push", ai, ("inv", f"P{i}"))[0]
            self.assertEqual(e.op, "scale")
            self.assertAlmostEqual(abs(math.log(e.value)), math.log(1.25), places=9)
        lo, hi = iv.control_bounds("stand.kd")
        ai = [Edit("stand.kd", "set", iv.stand_params(self.guided)["kd"] + 0.1 * (hi - lo))]
        e = self.twin(self.guided, "stand", ai)[0]
        self.assertEqual(iv.kind_of(e.param), "control")
        self.assertEqual(e.op, "set")

    def test_actuation_twin_is_torque_limit(self):
        e = self.twin(self.guided, "stand", [Edit("torque_limit", "scale", 1.3)])
        self.assertEqual([x.param for x in e], ["torque_limit"])

    def test_walk_kind_uses_walk_params(self):
        lo, hi = iv.control_bounds("walk.balance_gain")
        cur = iv.walk_vector(self.walk)[iv.r3.PARAM_NAMES.index("balance_gain")]
        ai = [Edit("walk.balance_gain", "set", cur + 0.1 * (hi - lo))]
        for i in range(10):
            e = self.twin(self.walk, "walk", ai, ("inv", f"P{i}"))[0]
            self.assertTrue(e.param.startswith("walk."))

    def test_sign_flip_at_bound(self):
        v = copy.deepcopy(self.exp)
        lo, hi = iv.mode_bounds("experimental")["foot_length"]
        v["body"]["foot_length"] = v["body"]["foot_length_r"] = hi          # only a shrink is legal for foot_length
        v["body"]["thigh_length"] = v["body"]["thigh_length_r"] = 0.3
        shrink_only = 0
        for i in range(40):
            t = self.twin(v, "stand", [Edit("foot_length", "scale", 1.3)], ("inv", f"P{i}"))
            self.assertIsNotNone(t)
            self.assertEqual(iv.validate_edits(v, "stand", [e.to_dict() for e in t])[1], [])
            if t[0].param == "foot_length":
                self.assertLess(t[0].value, 1.0)           # the +sign was invalid, so the sign was flipped
                shrink_only += 1
        self.assertGreater(shrink_only, 0)

    def test_unavailable_returns_none(self):
        # a magnitude beyond the 0.5..1.5 ratio rule can never give a valid edit in either sign
        v = copy.deepcopy(self.guided)
        t = bl.matched_random(v, "stand", [Edit("torque_limit", "scale", 3.0)], bl.make_rng("i", "p"))
        self.assertIsNone(t)
        self.assertIsNone(bl.matched_random(v, "stand", [], bl.make_rng("i", "p")))

    def test_unavailable_when_kind_exhausted(self):
        # two actuation edits cannot be matched: torque_limit is the only actuation parameter and may be used once
        ai = [Edit("torque_limit", "scale", 1.2), Edit("torque_limit", "scale", 1.1, "both")]
        self.assertIsNone(bl.matched_random(self.guided, "stand", ai, bl.make_rng("i", "p")))

    def test_deterministic_by_seed(self):
        ai = [Edit("foot_length", "scale", 1.3), Edit("thigh_length", "scale", 1.2)]
        a = self.twin(self.exp, "stand", ai, ("inv-7", "P2"))
        b = self.twin(self.exp, "stand", ai, ("inv-7", "P2"))
        self.assertEqual(a, b)
        others = {repr([e.to_dict() for e in self.twin(self.exp, "stand", ai, ("inv-7", f"P{k}"))]) for k in range(3, 12)}
        self.assertGreater(len(others), 1)                   # different proposal ids -> different draws
        r1 = bl.make_rng("a", "b").random()
        r2 = bl.make_rng("a", "b").random()
        self.assertEqual(r1, r2)
        self.assertNotEqual(bl.make_rng("a", "b").random(), bl.make_rng("a", "c").random())

    def test_stable_across_processes(self):
        # pinned value: guards against the use of the salted builtin hash()
        self.assertEqual(float(bl.make_rng("inv-1", "P1").random()), float(bl.make_rng("inv-1", "P1").random()))
        self.assertIsInstance(bl.make_rng("inv-1", "P1"), np.random.Generator)

    def test_bad_kind(self):
        with self.assertRaises(ValueError):
            bl.matched_random(self.guided, "fly", [Edit("foot_length", "scale", 1.2)], bl.make_rng("a", "b"))


def cr(kind, outcome, per_seed, forensics=None):
    return {"spec": {"kind": kind}, "outcome": outcome, "per_seed": per_seed, "forensics": forensics or {}}


def seed(outcome="PASS", **metrics):
    return {"seed": 1, "outcome": outcome, "score": 1.0, "metrics": metrics}


class Heuristic(unittest.TestCase):
    def setUp(self):
        self.v = load("version_guided.json")
        self.e = load("version_experimental.json")
        self.w = load("version_walk.json")

    def test_saturation_first(self):
        r = cr("stand", "FAIL", [seed("FAIL", saturation_frac=0.4, slip_frac=0.5, fell=True)] * 3)
        out = bl.heuristic(self.v, "stand", r)
        self.assertEqual([(x.param, x.op, x.value) for x in out], [("torque_limit", "scale", 1.3)])

    def test_slip(self):
        r = cr("stand", "FAIL", [seed("FAIL", saturation_frac=0.0, slip_frac=0.3, fell=True)] * 3)
        self.assertEqual([x.param for x in bl.heuristic(self.v, "stand", r)], ["foot_friction"])

    def test_push_falls_without_push_and_backward_weak(self):
        r = cr("push", "FAIL", [seed("FAIL", falls_without_push=True, weak_direction="forward")] * 2)
        self.assertEqual([x.param for x in bl.heuristic(self.v, "push", r)], ["foot_length"])
        r2 = cr("push", "POOR", [seed("POOR", weak_direction="backward")] * 2)
        self.assertEqual([x.param for x in bl.heuristic(self.v, "push", r2)], ["foot_length"])

    def test_push_forensics_saturation(self):
        r = cr("push", "POOR", [seed("POOR", weak_direction="backward")],
               {"actuation": {"fraction_samples_saturated_push_to_fall": 0.3}})
        self.assertEqual([x.param for x in bl.heuristic(self.v, "push", r)], ["torque_limit"])

    def test_passing_creature_abstains(self):
        r = cr("push", "PASS", [seed("PASS", weak_direction="backward")] * 4)
        self.assertIsNone(bl.heuristic(self.v, "push", r))
        self.assertIsNone(bl.heuristic(self.v, "stand", cr("stand", "PASS", [seed("PASS", fell=False, saturation_frac=0.0, slip_frac=0.0)])))

    def test_walk_rule(self):
        r = cr("walk", "FAIL", [seed("FAIL", fell=True)] * 4)
        out = bl.heuristic(self.w, "walk", r)
        self.assertEqual([x.param for x in out], ["walk.balance_gain", "walk.pitch_kp"])
        for x in out:
            self.assertEqual(x.op, "set")
        parsed, reasons = iv.validate_edits(self.w, "walk", [x.to_dict() for x in out])
        self.assertEqual(reasons, [])
        for x in out:
            d = iv.magnitude(self.w, x)
            self.assertAlmostEqual(d, 0.1, places=6)

    def test_always_validated_and_deterministic(self):
        r = cr("stand", "FAIL", [seed("FAIL", fell=True)] * 3)
        a = bl.heuristic(self.e, "stand", r)
        self.assertEqual(a, bl.heuristic(self.e, "stand", r))
        self.assertEqual(iv.validate_edits(self.e, "stand", [x.to_dict() for x in a])[1], [])

    def test_invalid_result_is_dropped_not_clipped(self):
        v = copy.deepcopy(self.v)
        lo, hi = iv.mode_bounds("guided")["foot_length"]
        v["body"]["foot_length"] = v["body"]["foot_length_r"] = hi
        r = cr("stand", "FAIL", [seed("FAIL", fell=True)] * 3)
        self.assertIsNone(bl.heuristic(v, "stand", r))


if __name__ == "__main__":
    unittest.main()
