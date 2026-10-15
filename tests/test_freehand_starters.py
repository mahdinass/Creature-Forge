"""The six Studio starter drawings (studio/src/sketch/starters.ts, ported exactly) must all be read as creatures.

Regression: with the starters' 5 cm leg gap, a short foot overlapped both ankles, was matched to the other leg, had toe
and heel flipped and the drawing was refused with "the feet point in opposite directions" (top-heavy, stilts)."""
import math
import unittest

from creature_forge.freehand import interpret

PX_PER_M, GROUND_Y, CX = 400, 620, 500


def px(x, z):
    return [CX + x * PX_PER_M, GROUND_Y - z * PX_PER_M]


def line(a, b, n=24, wobble=1.1, seed=0):
    out = []
    for i in range(n + 1):
        t = i / n
        x, y = px(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        out.append([round((x + wobble * math.sin(i * 1.3 + seed)) * 10) / 10, round((y + wobble * math.cos(i * 0.9 + seed)) * 10) / 10])
    return out


def poly(vs, seed=0):
    return [p for i in range(1, len(vs)) for p in line(vs[i - 1], vs[i], 18, 1.1, seed + i - 1)]


def rect(cx, z0, w, h, seed=0):
    return poly([[cx - w / 2, z0], [cx + w / 2, z0], [cx + w / 2, z0 + h], [cx - w / 2, z0 + h], [cx - w / 2, z0]], seed)


BASE = dict(thigh=0.3, shank=0.3, foot=0.16, torsoW=0.12, torsoH=0.3, kneeBack=0.0, legGap=0.05)


def figure(**o):
    s = {**BASE, **o}
    hip_z = s["thigh"] + s["shank"] + 0.04
    strokes = [{"id": "torso", "role": "torso", "points": rect(0, hip_z, s["torsoW"], s["torsoH"], 1)}]
    for i, dx in enumerate((-s["legGap"] / 2, s["legGap"] / 2)):
        strokes.append({"id": f"leg{i}", "role": "leg",
                        "points": poly([[dx, hip_z], [dx - s["kneeBack"], hip_z - s["thigh"]], [dx, 0.04]], 3 + i)})
        strokes.append({"id": f"foot{i}", "role": "foot",
                        "points": line([dx - 0.25 * s["foot"], 0.04], [dx + 0.75 * s["foot"], 0.04], 10, 0.8, 5 + i)})
    return strokes


STARTERS = {
    "balanced": (figure(), None),
    "tiny-feet": (figure(foot=0.03), None),
    "top-heavy": (figure(torsoW=0.4, torsoH=0.7, foot=0.08), None),
    "stilts": (figure(thigh=0.6, shank=0.6, foot=0.07), None),
    "bird-knees": (figure(kneeBack=0.1), None),
    "weak-slippery": (figure(), {"torque_limit": 5, "foot_friction": 0.05}),
}


class StarterTests(unittest.TestCase):
    def test_every_starter_is_read_as_a_creature_in_experimental_mode(self):
        for name, (strokes, materials) in STARTERS.items():
            with self.subTest(name):
                res = interpret(strokes, guided=False, materials=materials)
                self.assertNotEqual(res["status"], "needs_input", (name, res.get("errors")))
                self.assertIsNotNone(res.get("body"), (name, res.get("errors")))

    def test_both_feet_face_forward_with_toe_ahead_of_the_ankle(self):
        res = interpret(STARTERS["top-heavy"][0], guided=False)
        b = res["body"]
        # 75 % of each drawn foot is ahead of the ankle: both feet keep their drawn length
        self.assertAlmostEqual(b["foot_length"], 0.08, delta=0.01)
        self.assertAlmostEqual(b["foot_length_r"], 0.08, delta=0.01)

    def test_genuinely_opposite_feet_still_ask(self):
        s = figure()
        s[2]["points"] = list(reversed(line([-0.025 + 0.25 * 0.16, 0.04], [-0.025 - 0.75 * 0.16, 0.04], 10, 0.8, 5)))
        res = interpret(s, guided=False)
        self.assertEqual(res["status"], "needs_input")
        self.assertEqual(res["ambiguities"][0]["kind"], "facing")


if __name__ == "__main__":
    unittest.main()
