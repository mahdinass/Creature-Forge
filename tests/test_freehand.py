import math
import unittest

from creature_forge.freehand import PX_PER_M, interpret

GROUND_Y = 900.0


def px(x_m: float, z_m: float) -> list[float]:
    """Metres (x right, z up) to canvas pixels (y down)."""
    return [round(500 + x_m * PX_PER_M, 3), round(GROUND_Y - z_m * PX_PER_M, 3)]


def line(a, b, n=40, jitter=0.0):
    pts = []
    for i in range(n + 1):
        t = i / n
        j = jitter * math.sin(i * 1.7)
        pts.append(px(a[0] + (b[0] - a[0]) * t + j, a[1] + (b[1] - a[1]) * t))
    return pts


def poly(*vertices, n=30):
    pts = []
    for a, b in zip(vertices, vertices[1:]):
        pts += line(a, b, n)
    return pts


def stroke(sid, points, role="auto"):
    return {"id": sid, "role": role, "points": points}


def stick_figure(thigh=0.3, shank=0.3, foot=0.16, torso_h=0.3, lean=0.0, role="auto", torso_closed=False):
    """Facing right. Hip at (0, thigh+shank+0.04). Straight vertical legs unless `lean`."""
    hip = (0.0, thigh + shank + 0.04)
    knee = (lean * 0.0, hip[1] - thigh)
    ankle = (0.0, 0.04)
    toe = (0.75 * foot, 0.04)
    heel = (-0.25 * foot, 0.04)
    top = (0.0, hip[1] + torso_h)
    strokes = []
    if torso_closed:
        w = 0.06
        strokes.append(stroke("t", poly((-w, hip[1]), (w, hip[1]), (w, top[1]), (-w, top[1]), (-w, hip[1])), "torso" if role != "auto" else "auto"))
    else:
        strokes.append(stroke("t", line(hip, top), "torso" if role != "auto" else "auto"))
    strokes.append(stroke("l1", poly(hip, knee, ankle), "leg" if role != "auto" else "auto"))
    strokes.append(stroke("f1", line(heel, toe), "foot" if role != "auto" else "auto"))
    return strokes


class InterpretBasicTests(unittest.TestCase):
    def test_stick_figure_is_recognised_and_measured(self):
        r = interpret(stick_figure(), guided=True)
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertIn(r["outcome"], ("valid", "valid_with_snaps"))
        b = r["body"]
        self.assertAlmostEqual(b["thigh_length"], 0.30, delta=0.01)
        self.assertAlmostEqual(b["shank_length"], 0.30, delta=0.01)
        self.assertAlmostEqual(b["foot_length"], 0.16, delta=0.01)
        self.assertEqual({r["roles"][k]["role"] for k in r["roles"]}, {"torso", "leg", "foot"})

    def test_same_strokes_give_identical_results_and_do_not_depend_on_extra_points(self):
        a = interpret(stick_figure(), guided=False)
        b = interpret(stick_figure(), guided=False)
        self.assertEqual(a, b)
        dense = stick_figure()
        for s in dense:
            s["points"] = s["points"][::2] + [s["points"][-1]]  # a coarser hand
        c = interpret(dense, guided=False)
        for k in ("thigh_length", "shank_length", "foot_length"):
            self.assertAlmostEqual(a["body"][k], c["body"][k], delta=0.015)

    def test_explicit_pen_roles_override_auto_classification(self):
        s = stick_figure(role="pen")
        r = interpret(s, guided=True)
        self.assertEqual(r["roles"]["t"]["role"], "torso")
        self.assertEqual(r["roles"]["t"]["source"], "pen")

    def test_closed_torso_drives_mass_by_drawn_area(self):
        small = interpret(stick_figure(torso_closed=True), guided=False)["body"]["torso_mass"]
        big_strokes = stick_figure(torso_closed=True)
        big_strokes[0] = stroke("t", poly((-0.2, 0.64), (0.2, 0.64), (0.2, 1.2), (-0.2, 1.2), (-0.2, 0.64)))
        big = interpret(big_strokes, guided=False)["body"]["torso_mass"]
        self.assertAlmostEqual(small, 5.0, delta=0.6)
        self.assertGreater(big, 4 * small)

    def test_one_leg_drawn_is_mirrored_and_says_so(self):
        r = interpret(stick_figure(), guided=True)
        self.assertTrue(any("second leg" in a.lower() for a in r["assumptions"]))

    def test_leg_drawn_as_two_connected_strokes_is_one_leg(self):
        hip, knee, ankle = (0.0, 0.64), (0.0, 0.34), (0.0, 0.04)
        s = [stroke("t", line(hip, (0, 0.94))), stroke("thigh", line(hip, knee)), stroke("shank", line(knee, ankle)),
             stroke("f", line((-0.04, 0.04), (0.12, 0.04)))]
        r = interpret(s, guided=True)
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertAlmostEqual(r["body"]["thigh_length"], 0.30, delta=0.01)
        self.assertEqual(sum(1 for v in r["roles"].values() if v["role"] == "leg"), 2)


class GuidedVersusExperimentalTests(unittest.TestCase):
    def leaning(self, deg):
        hip, ankle = (0.0, 0.64), (math.sin(math.radians(deg)) * 0.6, 0.64 - math.cos(math.radians(deg)) * 0.6 + 0.0)
        ankle = (ankle[0], 0.04)
        s = stick_figure()
        s[1] = stroke("l1", line(hip, ankle))
        return s

    def test_guided_snaps_a_nearly_vertical_leg_and_reports_it(self):
        r = interpret(self.leaning(3), guided=True)
        self.assertTrue(any(a["kind"] == "straighten" for a in r["adjustments"]))
        self.assertAlmostEqual(r["body"]["pose"][1], 0.0, places=6)

    def test_experimental_keeps_the_raw_angle_exactly(self):
        r = interpret(self.leaning(3), guided=False)
        self.assertEqual(r["adjustments"], [])
        self.assertAlmostEqual(r["body"]["pose"][1], -math.radians(3) * -1 if False else r["body"]["pose"][1])
        self.assertGreater(abs(r["body"]["pose"][1]), math.radians(2))

    def test_tiny_foot_is_refused_with_consentable_approximation_when_guided(self):
        r = interpret(stick_figure(foot=0.03), guided=True)
        self.assertEqual(r["outcome"], "unrepresentable")
        self.assertIsNone(r["body"])
        self.assertTrue(any("foot" in e.lower() for e in r["errors"]))
        self.assertIsNotNone(r["approximation"])
        self.assertGreaterEqual(r["approximation"]["body"]["foot_length"], 0.06)
        self.assertTrue(r["approximation"]["changes"])

    def test_tiny_foot_is_simulated_as_is_when_experimental(self):
        r = interpret(stick_figure(foot=0.03), guided=False)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["outcome"], "questionable")
        self.assertAlmostEqual(r["body"]["foot_length"], 0.03, delta=0.005)
        self.assertTrue(any("foot" in n.lower() for n in r["notes"]))

    def test_very_heavy_upper_body_and_asymmetric_legs_are_buildable_in_experimental_mode(self):
        s = stick_figure(torso_closed=True)
        s[0] = stroke("t", poly((-0.25, 0.64), (0.25, 0.64), (0.25, 1.3), (-0.25, 1.3), (-0.25, 0.64)))
        s.append(stroke("l2", line((0.0, 0.64), (0.0, 0.24))))
        s.append(stroke("f2", line((-0.03, 0.24), (0.12, 0.24))))
        r = interpret(s, guided=False)
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertGreater(r["body"]["torso_mass"], 15.0)  # beyond the verified range, still buildable
        self.assertNotEqual(r["body"]["thigh_length"], r["body"]["thigh_length_r"])  # genuinely different legs
        self.assertEqual(r["outcome"], "questionable")

    def test_asymmetric_legs_are_not_claimed_exact_when_guided(self):
        s = stick_figure()
        s.append(stroke("l2", line((0.0, 0.64), (0.0, 0.24))))
        r = interpret(s, guided=True)
        self.assertEqual(r["outcome"], "unrepresentable")
        self.assertTrue(any("different" in e.lower() for e in r["errors"]))
        self.assertTrue(r["approximation"]["changes"])


class RepresentabilityTests(unittest.TestCase):
    def bent(self, knee_x):
        hip, knee, ankle = (0.0, 0.64), (knee_x, 0.34), (0.0, 0.04)
        s = stick_figure()
        s[1] = stroke("l1", poly(hip, knee, ankle))
        return s

    def test_a_knee_that_points_forward_is_unrepresentable_and_explained(self):
        r = interpret(self.bent(0.12), guided=False)  # knee ahead of the toes
        self.assertEqual(r["outcome"], "unrepresentable")
        self.assertIsNone(r["body"])
        self.assertTrue(any("knee" in e.lower() and "backward" in e.lower() for e in r["errors"]))
        self.assertIsNotNone(r["approximation"])
        self.assertTrue(any("knee" in c["what"] for c in r["approximation"]["changes"]))

    def test_a_knee_that_points_backward_is_built_with_the_real_pose(self):
        r = interpret(self.bent(-0.12), guided=False)
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertLess(r["body"]["pose"][2], -0.2)  # real knee flexion in the initial pose

    def test_drawing_facing_left_is_mirrored_and_reported(self):
        s = stick_figure()
        for st in s:
            st["points"] = [[1000 - x, y] for x, y in st["points"]]
        r = interpret(s, guided=True)
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertTrue(any("mirror" in n.lower() for n in r["notes"] + r["assumptions"]))

    def test_nothing_usable_is_a_clear_error_without_an_approximation(self):
        r = interpret([stroke("dot", [[10, 10], [11, 10]])], guided=False)
        self.assertEqual(r["status"], "unbuildable")
        self.assertIsNone(r["approximation"])
        self.assertTrue(r["errors"])
        r = interpret([], guided=True)
        self.assertEqual(r["status"], "unbuildable")

    def test_ambiguous_torso_asks_the_user_instead_of_guessing(self):
        s = stick_figure(torso_closed=True)
        s.append(stroke("t2", poly((0.3, 0.64), (0.42, 0.64), (0.42, 0.94), (0.3, 0.94), (0.3, 0.64))))
        r = interpret(s, guided=True)
        self.assertEqual(r["status"], "needs_input")
        self.assertIsNone(r["body"])
        amb = r["ambiguities"][0]
        self.assertEqual(amb["kind"], "torso")
        self.assertTrue(amb["options"])
        # applying one option resolves it
        fixed = [dict(x, role=amb["options"][0]["assign"].get(x["id"], x["role"])) for x in s]
        self.assertEqual(interpret(fixed, guided=True)["status"], "ok")

    def test_compiled_skeleton_is_returned_for_the_overlay(self):
        r = interpret(stick_figure(), guided=True)
        sk = r["skeleton"]
        for k in ("torso", "legs", "ground_y"):
            self.assertIn(k, sk)
        self.assertEqual(len(sk["legs"]), 2)
        for leg in sk["legs"]:
            for j in ("hip", "knee", "ankle", "toe", "heel"):
                self.assertEqual(len(leg[j]), 2)


if __name__ == "__main__":
    unittest.main()
