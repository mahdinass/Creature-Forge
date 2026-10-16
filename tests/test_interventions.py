"""Edit whitelist, validation matrix and application (docs/FORGE_LOOP_CONTRACTS.md section 5.2)."""
import copy
import json
import math
import unittest
from pathlib import Path

from creature_forge import interventions as iv
from creature_forge.interventions import Edit

FX = Path(__file__).parent / "fixtures" / "forge_ai"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def e(param, op="scale", value=1.2, target="both"):
    return {"param": param, "op": op, "value": value, "target": target}


class Base(unittest.TestCase):
    def setUp(self):
        self.guided = load("version_guided.json")
        self.exp = load("version_experimental.json")
        self.walk = load("version_walk.json")

    def ok(self, version, kind, *edits):
        parsed, reasons = iv.validate_edits(version, kind, list(edits))
        self.assertEqual(reasons, [], reasons)
        self.assertEqual(len(parsed), len(edits))
        return parsed

    def bad(self, version, kind, *edits, param=None, rule=None):
        parsed, reasons = iv.validate_edits(version, kind, list(edits))
        self.assertEqual(parsed, [])
        self.assertTrue(reasons, "expected a rejection")
        text = " | ".join(reasons)
        if param:
            self.assertIn(param, text)
        if rule:
            self.assertIn(rule, text)
        return reasons


class WhitelistTests(Base):
    def test_whitelist_contents(self):
        self.assertEqual(set(iv.MORPH_PARAMS), {"torso_mass", "thigh_length", "shank_length", "foot_length", "leg_density", "foot_friction"})
        self.assertEqual(iv.ACTUATION_PARAMS, ("torque_limit",))
        self.assertEqual(set(iv.STAND_PARAMS), {"stand.kp", "stand.kd", "stand.balance_gain", "stand.stand_hip", "stand.stand_knee"})
        self.assertEqual(len(iv.WALK_PARAMS), 15)
        self.assertTrue(all(p.startswith("walk.") for p in iv.WALK_PARAMS))

    def test_allowed_per_challenge(self):
        for kind in ("stand", "push"):
            a = iv.allowed_params(kind)
            self.assertIn("stand.kp", a)
            self.assertFalse(any(p.startswith("walk.") for p in a))
        w = iv.allowed_params("walk")
        self.assertIn("walk.freq", w)
        self.assertFalse(any(p.startswith("stand.") for p in w))
        with self.assertRaises(ValueError):
            iv.allowed_params("jump")

    def test_pose_and_unknown_params_not_editable(self):
        for p in ("pose", "torso_pitch", "gravity", "walk", "stand", "thigh_length_r", "walk.nope", "stand.gait_freq"):
            self.bad(self.exp, "push", e(p), param=p, rule="whitelist")

    def test_editable_params_catalog(self):
        g = iv.editable_params(self.guided, "push")
        self.assertEqual(g["foot_length"]["targets"], ["both"])
        self.assertEqual((g["foot_length"]["lo"], g["foot_length"]["hi"]), (0.06, 0.3))
        x = iv.editable_params(self.exp, "push")
        self.assertEqual(x["foot_length"]["targets"], ["both", "rear", "front"])
        self.assertEqual((x["foot_length"]["lo"], x["foot_length"]["hi"]), (0.02, 0.6))
        self.assertEqual((x["foot_length"]["rear"], x["foot_length"]["front"]), (0.08, 0.1))
        self.assertIn("u", x["stand.kp"])
        self.assertNotIn("walk.freq", x)
        wk = iv.editable_params(self.walk, "walk")
        self.assertIn("walk.freq", wk)
        self.assertNotIn("stand.kp", wk)
        self.assertEqual(wk["walk.freq"]["current"], round(self.walk["controllers"]["walk"]["vector"][0], 4))
        for d in (g, x, wk):
            self.assertTrue(all(v["meaning"] for v in d.values()))


class CategoryTests(Base):
    def test_category(self):
        E = Edit
        self.assertEqual(iv.category([E("foot_length", "scale", 1.2)]), "morphology")
        self.assertEqual(iv.category([E("torque_limit", "scale", 1.2)]), "morphology")
        self.assertEqual(iv.category([E("torque_limit", "scale", 1.2), E("torso_mass", "scale", 1.1)]), "morphology")
        self.assertEqual(iv.category([E("stand.kp", "scale", 1.2)]), "control")
        self.assertEqual(iv.category([E("walk.freq", "scale", 1.1), E("stand.kd", "scale", 1.1)]), "control")
        self.assertEqual(iv.category([E("foot_length", "scale", 1.2), E("stand.kp", "scale", 1.2)]), "combined")
        self.assertEqual(iv.category([E("torque_limit", "scale", 1.2), E("walk.kp", "scale", 1.2)]), "combined")
        with self.assertRaises(ValueError):
            iv.category([])

    def test_kind_of(self):
        self.assertEqual(iv.kind_of("foot_friction"), "morphology")
        self.assertEqual(iv.kind_of("torque_limit"), "actuation")
        self.assertEqual(iv.kind_of("walk.duty"), "control")
        with self.assertRaises(ValueError):
            iv.kind_of("pose")


class MorphologyRuleTests(Base):
    def test_valid_scale_and_set(self):
        parsed = self.ok(self.guided, "push", e("foot_length", "scale", 1.3), e("torso_mass", "set", 6.0))
        self.assertEqual(parsed[0], Edit("foot_length", "scale", 1.3, "both"))
        self.assertEqual(parsed[1].op, "set")

    def test_ratio_limits_inclusive_and_exclusive(self):
        self.ok(self.guided, "push", e("torque_limit", "scale", 1.5))
        self.ok(self.guided, "push", e("torque_limit", "scale", 0.5))
        self.bad(self.guided, "push", e("torque_limit", "scale", 1.51), param="torque_limit", rule="ratio")
        self.bad(self.guided, "push", e("torque_limit", "scale", 0.49), param="torque_limit", rule="ratio")
        self.bad(self.guided, "push", e("torso_mass", "set", 9.0), param="torso_mass", rule="ratio")   # 5 -> 9

    def test_bounds_guided_vs_experimental(self):
        v = copy.deepcopy(self.guided)
        v["body"]["torque_limit"] = 150.0
        self.bad(v, "push", e("torque_limit", "scale", 1.5), param="torque_limit", rule="bounds")     # 225 > 200
        v["mode"] = "experimental"
        self.ok(v, "push", e("torque_limit", "scale", 1.5))                                             # 225 <= 500
        # foot_length guided max 0.30: 0.16 * 1.5 = 0.24 ok, but at 0.25 -> 0.375 out of guided bounds
        g = copy.deepcopy(self.guided)
        g["body"].update(foot_length=0.25, foot_length_r=0.25)
        self.bad(g, "push", e("foot_length", "scale", 1.5), param="foot_length", rule="bounds")
        g["mode"] = "experimental"
        self.ok(g, "push", e("foot_length", "scale", 1.5))

    def test_never_clips(self):
        v = copy.deepcopy(self.guided)
        v["body"].update(foot_length=0.25, foot_length_r=0.25)
        parsed, reasons = iv.validate_edits(v, "push", [e("foot_length", "scale", 1.3)])
        self.assertEqual(parsed, [])                           # 0.325 > 0.30: rejected, not clipped to 0.30
        self.assertTrue(reasons)
        with self.assertRaises(ValueError):
            iv.apply_edits(v, [Edit("foot_length", "scale", 1.3)])

    def test_set_below_min_reports_both_rules(self):
        reasons = self.bad(self.guided, "push", e("thigh_length", "set", 0.1), param="thigh_length")
        text = " ".join(reasons)
        self.assertIn("ratio", text)
        self.assertIn("bounds", text)

    def test_guided_forbids_rear_front(self):
        self.bad(self.guided, "push", e("foot_length", target="rear"), param="foot_length", rule="symmetric")
        self.bad(self.guided, "push", e("shank_length", target="front"), param="shank_length", rule="symmetric")

    def test_experimental_targets(self):
        self.ok(self.exp, "push", e("foot_length", target="rear"))
        self.ok(self.exp, "push", e("foot_length", target="front"))
        self.ok(self.exp, "push", e("foot_length", target="rear"), e("foot_length", target="front", value=1.1))

    def test_target_only_for_leg_lengths(self):
        self.bad(self.exp, "push", e("torso_mass", target="rear"), param="torso_mass", rule="per-leg targets")
        self.bad(self.exp, "push", e("torque_limit", target="front"), param="torque_limit", rule="per-leg targets")

    def test_scale_must_be_positive(self):
        self.bad(self.guided, "push", e("foot_length", "scale", -1.2), param="foot_length", rule="positive")
        self.bad(self.guided, "push", e("foot_length", "scale", 0.0), param="foot_length", rule="positive")

    def test_guided_asymmetric_body_rejects_leg_edits(self):
        v = copy.deepcopy(self.guided)
        v["body"]["foot_length_r"] = 0.2
        self.bad(v, "push", e("foot_length"), param="foot_length", rule="symmetric")
        self.ok(v, "push", e("torso_mass", value=1.1))


class StructureRuleTests(Base):
    def test_counts(self):
        names = ["torso_mass", "thigh_length", "shank_length", "foot_length", "leg_density"]
        self.ok(self.guided, "push", *[e(n, value=1.1) for n in names[:4]])
        self.bad(self.guided, "push", *[e(n, value=1.1) for n in names], rule="at most 4")
        self.bad(self.guided, "push", rule="at least one")
        self.assertEqual(iv.validate_edits(self.guided, "push", "foot_length")[0], [])

    def test_duplicates_and_overlaps(self):
        self.bad(self.guided, "push", e("foot_length", value=1.1), e("foot_length", value=1.2), param="foot_length", rule="same field")
        self.bad(self.exp, "push", e("foot_length", target="both"), e("foot_length", target="rear", value=1.1), param="foot_length", rule="same field")
        self.bad(self.guided, "push", e("stand.kp", value=1.1), e("stand.kp", "set", 160.0), param="stand.kp", rule="same field")

    def test_no_op(self):
        self.bad(self.guided, "push", e("foot_length", "scale", 1.0), param="foot_length", rule="must change")
        self.bad(self.guided, "push", e("torso_mass", "set", 5.0), param="torso_mass", rule="must change")
        reasons = self.bad(self.guided, "push", e("stand.stand_hip", "scale", 1.2), param="stand.stand_hip")   # scaling 0 changes nothing
        self.assertIn("set", " ".join(reasons))

    def test_malformed_edits(self):
        self.bad(self.guided, "push", {"param": "foot_length", "op": "scale", "value": "1.2"}, param="foot_length", rule="finite number")
        self.bad(self.guided, "push", {"param": "foot_length", "op": "scale", "value": float("nan")}, param="foot_length", rule="finite number")
        self.bad(self.guided, "push", {"param": "foot_length", "op": "scale", "value": True}, param="foot_length", rule="finite number")
        self.bad(self.guided, "push", {"param": "foot_length", "op": "mul", "value": 1.2}, param="foot_length", rule="op is one of")
        self.bad(self.guided, "push", {"param": "foot_length", "op": "scale", "value": 1.2, "target": "left"}, param="foot_length", rule="target")
        self.bad(self.guided, "push", {"param": "foot_length", "op": "scale", "value": 1.2, "colour": "red"}, param="foot_length", rule="allowed")
        self.bad(self.guided, "push", {"op": "scale", "value": 1.2}, rule="whitelist")
        self.bad(self.guided, "push", "foot_length", rule="object")
        self.bad(self.guided, "push", {"param": ["foot_length"], "op": "scale", "value": 1.2}, rule="whitelist")

    def test_target_defaults_to_both(self):
        parsed, reasons = iv.validate_edits(self.guided, "push", [{"param": "foot_length", "op": "scale", "value": 1.2}])
        self.assertEqual((reasons, parsed[0].target), ([], "both"))

    def test_unknown_challenge_kind(self):
        with self.assertRaises(ValueError):
            iv.validate_edits(self.guided, "jump", [e("foot_length")])

    def test_every_reason_names_the_param_and_a_rule(self):
        cases = [(self.guided, "push", e("torque_limit", "scale", 2.0)), (self.guided, "push", e("foot_length", target="rear")),
                 (self.guided, "push", e("walk.freq", "set", 1.0)), (self.exp, "walk", e("stand.kp")),
                 (self.guided, "push", e("stand.kp", "set", 400.0)), (self.guided, "push", e("foot_length", "scale", 1.0))]
        for v, k, ed in cases:
            reasons = self.bad(v, k, ed)
            for r in reasons:
                self.assertIn(ed["param"], r)
                self.assertIn("rule", r)

    def test_whole_list_rejected_if_one_edit_bad(self):
        parsed, reasons = iv.validate_edits(self.guided, "push", [e("foot_length", value=1.2), e("torque_limit", value=3.0)])
        self.assertEqual(parsed, [])
        self.assertEqual(len(reasons), 1)
        self.assertIn("torque_limit", reasons[0])


class ControlRuleTests(Base):
    def test_challenge_family(self):
        self.bad(self.guided, "push", e("walk.freq", "set", 1.0), param="walk.freq", rule="walk challenges")
        self.bad(self.guided, "stand", e("walk.freq", "set", 1.0), param="walk.freq", rule="walk challenges")
        self.bad(self.walk, "walk", e("stand.kp"), param="stand.kp", rule="stand and push")
        self.ok(self.guided, "stand", e("stand.kp"))
        self.ok(self.guided, "push", e("stand.kd", value=1.1))
        self.ok(self.walk, "walk", e("walk.kp", value=1.1))
        self.ok(self.walk, "walk", e("foot_friction", value=1.2))                 # morphology allowed in every challenge

    def test_delta_u_limit(self):
        self.ok(self.guided, "push", e("stand.kp", "scale", 1.2))                  # 150 -> 180: du 0.06
        self.ok(self.guided, "push", e("stand.balance_gain", "set", 105.0))        # du 0.125
        self.ok(self.guided, "push", e("stand.stand_knee", "set", -0.2))           # du exactly 0.25 over [-0.8, 0]
        self.bad(self.guided, "push", e("stand.stand_knee", "set", -0.3), param="stand.stand_knee", rule="delta u")
        self.bad(self.guided, "push", e("stand.kp", "set", 300.0), param="stand.kp", rule="delta u")       # 0.3
        self.ok(self.guided, "push", e("stand.kd", "set", 20.0))                   # 12 / 50 = 0.24

    def test_control_bounds_rejected_not_clipped(self):
        self.bad(self.guided, "push", e("stand.stand_hip", "set", 0.5), param="stand.stand_hip", rule="bounds")
        self.bad(self.guided, "push", e("stand.stand_knee", "set", 0.1), param="stand.stand_knee", rule="bounds")

    def test_walk_delta_u(self):
        vec = self.walk["controllers"]["walk"]["vector"]
        for name in ("freq", "balance_gain", "pitch_kp"):
            i = iv.r3.PARAM_NAMES.index(name)
            lo, hi = iv.control_bounds(f"walk.{name}")
            old, span = vec[i], hi - lo
            sgn = next(s for s in (1.0, -1.0) if lo <= old + s * 0.2 * span <= hi)
            self.ok(self.walk, "walk", e(f"walk.{name}", "set", old + sgn * 0.2 * span))
            if lo <= old + sgn * 0.3 * span <= hi:
                self.bad(self.walk, "walk", e(f"walk.{name}", "set", old + sgn * 0.3 * span), param=f"walk.{name}", rule="delta u")
            self.bad(self.walk, "walk", e(f"walk.{name}", "set", hi + span), param=f"walk.{name}", rule="bounds")

    def test_walk_null_vector_uses_r2_winner(self):
        v = copy.deepcopy(self.walk)
        v["controllers"]["walk"] = None
        self.assertEqual(iv.walk_vector(v), self.walk["controllers"]["walk"]["vector"])
        self.ok(v, "walk", e("walk.kp", value=1.1))
        body, ctl = iv.apply_edits(v, [Edit("walk.kp", "scale", 1.1)])
        i = iv.r3.PARAM_NAMES.index("kp")
        self.assertAlmostEqual(ctl["walk"]["vector"][i], self.walk["controllers"]["walk"]["vector"][i] * 1.1)
        self.assertTrue(ctl["walk"]["provenance"]["edited"])
        self.assertEqual(len(ctl["walk"]["vector"]), 15)


class MagnitudeTests(Base):
    def test_morphology_magnitude_is_abs_log_ratio(self):
        self.assertAlmostEqual(iv.magnitude(self.guided, Edit("foot_length", "scale", 1.3)), math.log(1.3))
        self.assertAlmostEqual(iv.magnitude(self.guided, Edit("foot_length", "scale", 1 / 1.3)), math.log(1.3))
        self.assertAlmostEqual(iv.magnitude(self.guided, Edit("torso_mass", "set", 6.0)), math.log(6.0 / 5.0))

    def test_control_magnitude_is_linear_over_bounds(self):
        self.assertAlmostEqual(iv.magnitude(self.guided, Edit("stand.kp", "set", 200.0)), 50.0 / 500.0)
        self.assertAlmostEqual(iv.magnitude(self.guided, Edit("stand.stand_knee", "set", -0.2)), 0.25)
        self.assertAlmostEqual(iv.magnitude(self.guided, Edit("stand.kp", "set", 100.0)), 0.1)

    def test_magnitude_both_on_asymmetric_legs_is_max(self):
        m = iv.magnitude(self.exp, Edit("thigh_length", "set", 0.2, "both"))        # 0.35 -> 0.2 and 0.30 -> 0.2
        self.assertAlmostEqual(m, math.log(0.35 / 0.2))
        self.assertAlmostEqual(iv.magnitude(self.exp, Edit("thigh_length", "set", 0.2, "front")), math.log(0.3 / 0.2))

    def test_magnitude_pure(self):
        before = copy.deepcopy(self.exp)
        iv.magnitude(self.exp, Edit("foot_length", "scale", 1.3, "rear"))
        self.assertEqual(before, self.exp)

    def test_magnitude_nonpositive_raises(self):
        with self.assertRaises(ValueError):
            iv.magnitude(self.guided, Edit("foot_length", "set", -0.1))


class ApplyTests(Base):
    def test_apply_does_not_mutate_and_changes_only_edited(self):
        before = copy.deepcopy(self.guided)
        body, ctl = iv.apply_edits(self.guided, [Edit("foot_length", "scale", 1.3), Edit("stand.kp", "set", 170.0), Edit("torque_limit", "scale", 0.8)])
        self.assertEqual(self.guided, before)
        self.assertAlmostEqual(body["foot_length"], 0.16 * 1.3)
        self.assertAlmostEqual(body["foot_length_r"], 0.16 * 1.3)
        self.assertAlmostEqual(body["torque_limit"], 48.0)
        self.assertEqual(body["thigh_length"], 0.3)
        self.assertEqual(body["pose"], [0.0] * 7)
        self.assertEqual(ctl["stand"]["kp"], 170.0)
        self.assertEqual(ctl["stand"]["kd"], 8.0)
        self.assertIsNone(ctl["walk"])
        body["pose"][0] = 9.0                                                      # result must not alias the input
        self.assertEqual(self.guided["body"]["pose"], [0.0] * 7)

    def test_rear_front_targets_map_to_left_and_right_fields(self):
        body, _ = iv.apply_edits(self.exp, [Edit("foot_length", "set", 0.12, "rear")])
        self.assertEqual((body["foot_length"], body["foot_length_r"]), (0.12, 0.1))
        body, _ = iv.apply_edits(self.exp, [Edit("thigh_length", "scale", 1.1, "front")])
        self.assertAlmostEqual(body["thigh_length_r"], 0.33)
        self.assertEqual(body["thigh_length"], 0.35)

    def test_missing_right_leg_fields_become_explicit(self):
        v = copy.deepcopy(self.guided)
        for k in iv.LEG_PARAMS:
            v["body"][k + "_r"] = None
        body, _ = iv.apply_edits(v, [Edit("torso_mass", "set", 6.0)])
        self.assertEqual(body["thigh_length_r"], 0.3)

    def test_apply_result_is_a_valid_sandbox_body_in_mode_bounds(self):
        body, _ = iv.apply_edits(self.exp, [Edit("foot_length", "scale", 1.4, "both"), Edit("torso_mass", "set", 10.0)])
        v = copy.deepcopy(self.exp)
        v["body"] = body
        iv.sandbox_body(v).validate()
        gbody, _ = iv.apply_edits(self.guided, [Edit("leg_density", "scale", 1.5)])
        g = copy.deepcopy(self.guided)
        g["body"] = gbody
        iv.sandbox_body(g).validate()

    def test_apply_refuses_out_of_bounds(self):
        with self.assertRaises(ValueError):
            iv.apply_edits(self.guided, [Edit("stand.stand_hip", "set", 0.5)])
        with self.assertRaises(ValueError):
            iv.apply_edits(self.guided, [Edit("torso_mass", "set", 99.0)])

    def test_edit_roundtrip(self):
        ed = Edit("foot_length", "scale", 1.3, "rear")
        self.assertEqual(Edit.from_dict(ed.to_dict()), ed)


if __name__ == "__main__":
    unittest.main()
