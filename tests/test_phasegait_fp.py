"""Tests for creature_forge.phasegait_fp (swing-foot placement feedback, 17-D controller family)."""
import math
import unittest

import mujoco
import numpy as np

from creature_forge import challenges as ch
from creature_forge import creature_walk as cw
from creature_forge import locomotion as loc
from creature_forge import recovery as rc
from creature_forge.morphology import build_model
from creature_forge.phasegait import PhaseGaitParams, leg_references
from creature_forge.phasegait_fp import (FP_BOUNDS, FP_NAMES, LOWER17, UPPER17, FPParams, PhaseGaitFPController)
from creature_forge.phasegait_init import (LOWER15, UPPER15, InitParams, PhaseGaitInitController,
                                           controller_from_vector)
from creature_forge.sandbox import SandboxBody

R2 = list(cw.R2_WINNER)
DEFAULT = SandboxBody()
STILTS = SandboxBody(thigh_length=0.55, shank_length=0.55, foot_length=0.07, torso_mass=4.7917)
N10 = 10.0


def vec17(kd, kv):
    return R2 + [kd, kv]


def pair(vector, body):
    """(PhaseGaitInitController from the first 15 numbers, FP controller with the 17-D vector)."""
    base = controller_from_vector(vector[:15])
    return base, controller_from_vector(vector, body=body)


class FKTests(unittest.TestCase):
    def test_offset_matches_mujoco(self):
        """d_leg = thigh*sin(a1) + shank*sin(a2) is hip-x minus ankle-x of the real model, and its rate matches finite differences."""
        for body in (DEFAULT, STILTS, SandboxBody(thigh_length=0.3, shank_length=0.45, thigh_length_r=0.4, shank_length_r=0.2)):
            model = build_model(body)
            data = mujoco.MjData(model)
            ctrl = controller_from_vector(vec17(0.5, 0.5), body=body)
            rng = np.random.default_rng(3)
            ids = {s: (mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"thigh_{s}"),
                       mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"foot_{s}")) for s in "lr"}
            for _ in range(12):
                pitch = rng.uniform(-0.3, 0.3)
                q = np.array([rng.uniform(-0.8, 0.8), rng.uniform(-1.5, 0.0), rng.uniform(-0.5, 0.5)] * 2)
                q[3:] = [rng.uniform(-0.8, 0.8), rng.uniform(-1.5, 0.0), rng.uniform(-0.5, 0.5)]
                qd = rng.uniform(-1, 1, 6)
                prate = rng.uniform(-1, 1)

                def d_of(p, qq):
                    data.qpos[:] = 0.0
                    data.qpos[2] = p
                    data.qpos[3:9] = qq
                    mujoco.mj_forward(model, data)
                    return [data.xpos[ids[s][0]][0] - data.xpos[ids[s][1]][0] for s in "lr"]

                d0 = d_of(pitch, q)
                eps = 1e-6
                d1 = d_of(pitch + eps * prate, q + eps * qd)
                for leg in (0, 1):
                    d_est, v_est = ctrl.leg_offset(leg, pitch, prate, q, qd)
                    self.assertAlmostEqual(d_est, d0[leg], places=9)
                    self.assertAlmostEqual(v_est, (d1[leg] - d0[leg]) / eps, places=4)

    def test_sign_conventions(self):
        """hip > 0 puts the foot behind the hip (d > 0); pitch > 0 (forward lean) does too; a leg straight down gives 0."""
        ctrl = controller_from_vector(vec17(0.5, 0.5), body=DEFAULT)
        z = [0.0] * 6
        self.assertEqual(ctrl.leg_offset(0, 0.0, 0.0, z, z)[0], 0.0)
        self.assertGreater(ctrl.leg_offset(0, 0.0, 0.0, [0.2, 0, 0, 0, 0, 0], z)[0], 0.0)
        self.assertGreater(ctrl.leg_offset(0, 0.2, 0.0, z, z)[0], 0.0)


class VectorTests(unittest.TestCase):
    def test_bounds_and_names(self):
        self.assertEqual(FP_NAMES, ("fp_kd", "fp_kv"))
        self.assertEqual(FP_BOUNDS, {"fp_kd": (0.0, 1.5), "fp_kv": (0.0, 1.5)})
        self.assertEqual(len(LOWER17), 17)
        np.testing.assert_array_equal(LOWER17[:15], LOWER15)
        np.testing.assert_array_equal(UPPER17[:15], UPPER15)
        np.testing.assert_array_equal(LOWER17[15:], [0.0, 0.0])
        np.testing.assert_array_equal(UPPER17[15:], [1.5, 1.5])

    def test_validation(self):
        with self.assertRaises(ValueError):
            controller_from_vector(vec17(0.1, 0.1))                     # 17-D needs the body
        for bad in ((-0.01, 0.0), (0.0, 1.51), (float("nan"), 0.0)):
            with self.assertRaises(ValueError):
                controller_from_vector(vec17(*bad), body=DEFAULT)
        with self.assertRaises(ValueError):
            controller_from_vector(R2 + [0.1], body=DEFAULT)           # 16 numbers
        c = controller_from_vector(vec17(0.3, 0.7), body=DEFAULT)
        self.assertIsInstance(c, PhaseGaitFPController)
        self.assertEqual((c.fp.fp_kd, c.fp.fp_kv), (0.3, 0.7))
        self.assertAlmostEqual(c.L, 0.6)
        # 13-D / 15-D are unchanged and ignore the body
        self.assertIs(type(controller_from_vector(R2)), PhaseGaitInitController)
        self.assertIs(type(controller_from_vector(R2, body=DEFAULT)), PhaseGaitInitController)
        self.assertEqual(type(controller_from_vector(R2[:13], body=DEFAULT)).__name__, "PhaseGaitController")
        self.assertEqual(FPParams().as_dict(), {"fp_kd": 0.0, "fp_kv": 0.0})

    def test_asymmetric_legs_mean_length(self):
        b = SandboxBody(thigh_length=0.3, shank_length=0.3, thigh_length_r=0.5, shank_length_r=0.5)
        self.assertAlmostEqual(controller_from_vector(vec17(0, 0), body=b).L, 0.8)

    def test_walk_vector_accepts_15_and_17(self):
        self.assertEqual(len(ch.walk_vector({"walk": {"vector": R2}})), 15)
        self.assertEqual(len(ch.walk_vector({"walk": {"vector": vec17(0.1, 0.2)}})), 17)
        with self.assertRaises(ch.ChallengeError) as cm:
            ch.walk_vector({"walk": {"vector": R2 + [0.0]}})
        self.assertIn("15", str(cm.exception))
        self.assertIn("17", str(cm.exception))


class TraceTests(unittest.TestCase):
    def check_identity(self, body):
        base, fp = pair(vec17(0.0, 0.0), body)
        a = cw.rollout(base, body, 7, N10)
        b = cw.rollout(fp, body, 7, N10)
        self.assertGreater(len(a["t"]), 100)
        for k in ("demand", "tau", "q", "qd", "x", "z", "pitch", "force"):
            self.assertTrue(np.array_equal(a[k], b[k]), f"{k} differs for zero gains")

    def test_zero_gain_bit_identical_default(self):
        self.check_identity(DEFAULT)

    def test_zero_gain_bit_identical_stilts(self):
        self.check_identity(STILTS)

    def test_nonzero_gain_changes_behaviour(self):
        a = cw.rollout(controller_from_vector(R2), DEFAULT, 7, 3.0)
        b = cw.rollout(controller_from_vector(vec17(0.8, 0.8), body=DEFAULT), DEFAULT, 7, 3.0)
        self.assertFalse(np.array_equal(a["demand"], b["demand"]))

    def test_offset_continuity(self):
        """Hip reference (gait reference + placement offset) never jumps by more than 0.05 rad between 1 kHz steps."""
        for body in (DEFAULT, STILTS):
            for gains in ((0.5, 0.5), (1.5, 1.5)):
                rec = {0: [], 1: []}

                class Probe(PhaseGaitFPController):
                    def _offset(self, leg, phi_leg, ramp):
                        off = super()._offset(leg, phi_leg, ramp)
                        rec[leg].append((leg_references(self.p, phi_leg, ramp, 0.0)[0] + off, off, phi_leg < self.p.duty))
                        return off

                base = PhaseGaitParams.from_vector(R2[:13])
                ctrl = Probe(base, InitParams(*R2[13:15]), FPParams(*gains), body=body)
                cw.rollout(ctrl, body, 5, N10)
                transitions = 0
                for leg in (0, 1):
                    h = np.array([r[0] for r in rec[leg]])
                    o = np.array([r[1] for r in rec[leg]])
                    st = np.array([r[2] for r in rec[leg]])
                    self.assertLess(np.max(np.abs(np.diff(h))), 0.05, f"{body.thigh_length} {gains}")
                    self.assertLess(np.max(np.abs(np.diff(o))), 0.05)
                    transitions += int(np.sum(st[1:] != st[:-1]))
                    self.assertLessEqual(np.max(np.abs(o)), 0.5 + 1e-12)
                self.assertGreater(transitions, 4)
                self.assertGreater(max(abs(r[1]) for r in rec[0]), 0.0)     # the offset was exercised

    def test_swing_offset_sign(self):
        """A body ahead of / moving forward over the stance foot (d, v > 0) asks the swing hip for a negative (forward) offset."""
        c = controller_from_vector(vec17(1.0, 1.0), body=DEFAULT)
        c.reset(30.0, 100.0)
        c._d, c._v = 0.1, 0.5
        c._update_target(10.0)                # a long step: the slew limit does not bind
        off = c._offset(0, 0.9, 1.0)          # phi_leg 0.9: late swing, blend complete
        self.assertLess(off, 0.0)
        self.assertAlmostEqual(off, -(0.1 / 0.6 + 0.5 / math.sqrt(9.81 * 0.6)), places=9)


class RecoveryPathTests(unittest.TestCase):
    def test_eval_vector_17d(self):
        out = cw.eval_vector(vec17(0.3, 0.3), STILTS, [100], 2.0)
        self.assertEqual(len(out["per_seed"]), 1)
        z = cw.eval_vector(vec17(0.0, 0.0), STILTS, [100], 2.0)
        o = cw.eval_vector(R2, STILTS, [100], 2.0)
        self.assertEqual(z["per_seed"], o["per_seed"])

    def test_run_walk_seeds_17d(self):
        rows = rc.run_walk_seeds(STILTS.as_dict(), vec17(0.3, 0.3), [100], duration=2.0)
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0]["outcome"], "ERROR", rows[0])
        rows0 = rc.run_walk_seeds(STILTS.as_dict(), vec17(0.0, 0.0), [100], duration=2.0)
        rows15 = rc.run_walk_seeds(STILTS.as_dict(), R2, [100], duration=2.0)
        self.assertEqual(rows0[0]["score"], rows15[0]["score"])


class StiltsReport(unittest.TestCase):
    def test_report_stilts_rollouts(self):
        """Reports (does not assert) how the R2 winner plus placement gains does on the stilts body."""
        crit = cw.creature_criteria(STILTS)
        for seed in (100, 101):
            for gains in ((0.0, 0.0), (0.5, 0.5), (1.0, 0.0), (0.0, 1.0), (0.3, 0.6), (1.0, 1.0)):
                tr = cw.rollout(controller_from_vector(vec17(*gains), body=STILTS), STILTS, seed, N10)
                m = loc.compute_metrics(tr, crit)
                print(f"STILTS seed={seed} fp_kd={gains[0]} fp_kv={gains[1]}: label={m['label']} walking={m['walking']} "
                      f"fell={m['fell']} fall_time={m['fall_time']} disp={m['forward_disp_upright']:.3f} "
                      f"speed={m['speed_upright']:.3f} steps={m['valid_steps']}")
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
