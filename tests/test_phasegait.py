import unittest

import numpy as np

from creature_forge.contact import SAMPLE_DT
from creature_forge.locomotion import compute_metrics, rollout
from creature_forge.morphology import BipedParams
from creature_forge.phasegait import (BOUNDS, FB_CAP, LOWER, UPPER, PhaseGaitController, PhaseGaitParams,
                                      leg_references)


class ParamTests(unittest.TestCase):
    def test_defaults_are_inside_bounds_and_vector_roundtrips(self):
        p = PhaseGaitParams().validate()
        self.assertEqual(PhaseGaitParams.from_vector(p.to_vector()), p)
        self.assertEqual(len(LOWER), len(BOUNDS))
        self.assertTrue(np.all(LOWER < UPPER))

    def test_out_of_bounds_and_nonfinite_are_rejected_not_clipped(self):
        for k, (lo, hi) in BOUNDS.items():
            with self.assertRaises(ValueError, msg=k):
                PhaseGaitParams().replace(**{k: hi + 1e-3})
        with self.assertRaises(ValueError):
            PhaseGaitParams().replace(kp=float("nan"))


class ReferenceContinuityTests(unittest.TestCase):
    def test_references_are_continuous_across_stance_swing_and_cycle_wrap(self):
        for duty in (0.5, 0.6, 0.8):
            for shift in (-0.15, 0.0, 0.15):
                p = PhaseGaitParams(duty=duty, knee_shift=shift)
                phis = np.linspace(0, 2, 20001)  # two cycles including the wrap
                ref = np.array([leg_references(p, f % 1.0, 1.0, 0.0) for f in phis])
                step = np.abs(np.diff(ref, axis=0)).max()
                self.assertLess(step, 3e-3, (duty, shift))  # max slope step ~1e-3; a real jump would be >= 0.05 rad

    def test_hip_and_knee_velocity_is_continuous_at_transitions(self):
        p = PhaseGaitParams()
        eps = 1e-5
        for edge in (0.0, p.duty):
            a = np.array(leg_references(p, (edge - eps) % 1.0, 1.0, 0.0)[:2])
            b = np.array(leg_references(p, (edge + eps) % 1.0, 1.0, 0.0)[:2])
            self.assertLess(np.abs(a - b).max(), 1e-3)

    def test_ramp_starts_from_standing_posture(self):
        p = PhaseGaitParams(hip_bias=0.0)
        hip, knee, _ = leg_references(p, 0.3, 0.0, 0.0)
        self.assertEqual((hip, knee), (0.0, 0.0))


class ControllerGuardTests(unittest.TestCase):
    def make(self, **kw):
        c = PhaseGaitController(PhaseGaitParams(**kw))
        c.reset(60.0, 100.0)
        return c

    def force_into_late_swing(self, c):
        c.phi = (c.p.duty + 0.8 * (1 - c.p.duty)) % 1.0  # leg 0 late in swing

    def test_impact_chatter_does_not_repeatedly_reset_the_oscillator(self):
        c = self.make(sync_gain=1.0)
        self.force_into_late_swing(c)
        t = 1.0
        for i in range(200):  # 1 s of foot force toggling every sample (raw chatter)
            c.sense(t + i * SAMPLE_DT, [60.0 if i % 2 == 0 else 0.0, 0.0])
        self.assertEqual(c.sync_count, 0)  # one-sample loads are never confirmed touchdowns

    def test_sustained_early_touchdown_is_honoured_once_per_refractory_period(self):
        c = self.make(sync_gain=1.0)
        self.force_into_late_swing(c)
        t = 1.0
        for i in range(10):
            c.sense(t + i * SAMPLE_DT, [60.0, 0.0])
        self.assertEqual(c.sync_count, 1)
        self.assertGreater(c.pending, 0.0)
        for i in range(10, 20):  # lose and regain contact within the refractory window
            c.sense(t + i * SAMPLE_DT, [0.0 if i < 14 else 60.0, 0.0])
        self.assertEqual(c.sync_count, 1)

    def test_phase_correction_is_rate_limited(self):
        c = self.make(sync_gain=1.0, freq=1.0)
        c.pending = 0.3
        phi0 = c.phi
        c.torque(0.001, 0.0, 0.0, np.zeros(6), np.zeros(6))
        c.torque(0.002, 0.0, 0.0, np.zeros(6), np.zeros(6))
        advance = (c.phi - phi0) % 1.0
        self.assertLessEqual(advance, 2.0 * 1.0 * 0.001 * 2 + 1e-12)  # at most 2x clock rate

    def test_stance_feedback_is_bounded_and_only_on_loaded_feet(self):
        c = self.make(pitch_kp=120.0, balance_gain=150.0)
        z = np.zeros(6)
        unloaded = c.torque(0.05, 10.0, 0.0, z, z)  # t fixed below: repeated calls at the same t do not advance phase
        c.est.deb[:] = [True, True]
        t10 = c.torque(0.05, 10.0, 0.0, z, z)
        t100 = c.torque(0.05, 100.0, 0.0, z, z)
        np.testing.assert_allclose(t10[[0, 3]], t100[[0, 3]])  # hip feedback saturates at the cap
        self.assertLessEqual(abs(t10[0] - unloaded[0]), FB_CAP * 60.0 + 1e-6)
        self.assertGreater(abs(t10[0] - unloaded[0]), 1.0)  # and the loaded foot really gets feedback

    def test_rollout_is_bitwise_deterministic(self):
        a = rollout(PhaseGaitController(PhaseGaitParams()), BipedParams(), 5, 1.5)
        b = rollout(PhaseGaitController(PhaseGaitParams()), BipedParams(), 5, 1.5)
        for k in ("x", "z", "pitch", "tau", "force"):
            np.testing.assert_array_equal(a[k], b[k], err_msg=k)

    def test_default_gait_metrics_are_finite_and_classified(self):
        m = compute_metrics(rollout(PhaseGaitController(PhaseGaitParams()), BipedParams(), 1000, 3.0))
        self.assertIn(m["label"], {"fall", "falling_forward", "backward_shuffle", "stationary", "slow_or_few_steps",
                                   "contact_chatter", "hopping", "body_dragging", "foot_sliding",
                                   "torque_saturated", "sliding_without_steps", "walking"})
        self.assertTrue(np.isfinite(m["speed_upright"]))


if __name__ == "__main__":
    unittest.main()
