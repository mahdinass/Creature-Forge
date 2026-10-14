import unittest

import mujoco
import numpy as np

from creature_forge.contact import ContactConfig, FootContactEstimator, SAMPLE_DT, replay
from creature_forge.controller import GaitParams, compute_torque
from creature_forge.locomotion import (DEFAULT_CRITERIA, compute_metrics, evaluate_controller, fitness_components,
                                       rollout, step_events)
from creature_forge.morphology import BipedParams, build_model
from creature_forge.phasegait import (LagSinusoidController, LagSinusoidParams, OpenLoopController)

W = 100.0  # synthetic body weight (N)


class ContactEstimatorTests(unittest.TestCase):
    def feed(self, forces):
        est = FootContactEstimator(W, 1)
        for i, f in enumerate(forces):
            est.update(i * SAMPLE_DT, [f])
        return est

    def test_hysteresis_band_does_not_flip_state(self):
        on, off = 0.05 * W, 0.02 * W
        est = self.feed([0.0] * 5 + [on + 1] * 10 + [(on + off) / 2] * 20)  # inside the band: stays loaded
        self.assertTrue(est.deb[0])
        self.assertEqual(est.raw_touchdowns[0], 1)

    def test_single_sample_spike_is_not_a_touchdown_but_is_counted_as_raw_chatter(self):
        est = self.feed([0.0] * 5 + [50.0] + [0.0] * 10)
        self.assertEqual([e for e in est.events if e["kind"] == "touchdown"], [])
        self.assertEqual(est.raw_touchdowns[0], 1)

    def test_sustained_load_confirms_with_backdated_onset(self):
        est = self.feed([0.0] * 5 + [50.0] * 10)
        td = [e for e in est.events if e["kind"] == "touchdown"]
        self.assertEqual(len(td), 1)
        self.assertAlmostEqual(td[0]["t"], 5 * SAMPLE_DT)
        self.assertGreaterEqual(td[0]["t_confirm"] - td[0]["t"], 0.02 - 1e-9)

    def test_liftoff_requires_minimum_duration(self):
        est = self.feed([50.0] * 10 + [0.0] * 2 + [50.0] * 10)  # 10 ms dropout is not a liftoff
        self.assertEqual([e["kind"] for e in est.events], ["touchdown"])

    def test_replay_matches_online_updates(self):
        f = np.concatenate([np.zeros(5), np.full(30, 60.0), np.zeros(30)])[:, None]
        t = np.arange(len(f)) * SAMPLE_DT
        est, raw, deb = replay(t, f, W)
        online = self.feed(f[:, 0])
        self.assertEqual(est.events, online.events)
        self.assertEqual(deb[:, 0].tolist()[-1], online.deb[0])


class PhysicalContactValidationTests(unittest.TestCase):
    def test_freefall_touchdown_time_matches_analytic_and_force_balances_weight(self):
        body = BipedParams()
        model = build_model(body)
        data = mujoco.MjData(model)
        foot_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"foot_{s}") for s in "lr"]
        floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
        mujoco.mj_forward(model, data)
        low = min(data.geom_xpos[i][2] - np.abs(data.geom_xmat[i].reshape(3, 3)[2]) @ model.geom_size[i]
                  for i in foot_ids)
        h = 0.05
        data.qpos[1] -= low - h  # lowest foot point exactly h above the floor
        mujoco.mj_forward(model, data)
        weight = float(model.body_mass.sum()) * 9.81
        est = FootContactEstimator(weight, 2)
        f6 = np.zeros(6)
        for step in range(400):
            mujoco.mj_step(model, data)  # zero torque: passive joints, whole body in free fall
            if step % 5:
                continue
            force = [0.0, 0.0]
            for c in range(data.ncon):
                con = data.contact[c]
                if floor in (con.geom1, con.geom2):
                    other = con.geom2 if con.geom1 == floor else con.geom1
                    mujoco.mj_contactForce(model, data, c, f6)
                    if other in foot_ids and f6[0] > 0:
                        force[foot_ids.index(other)] += f6[0]
            est.update(data.time, force)
        td = [e for e in est.events if e["kind"] == "touchdown"]
        self.assertTrue(td, "no touchdown detected")
        expected = (2 * h / 9.81) ** 0.5
        self.assertAlmostEqual(td[0]["t"], expected, delta=0.015)  # within 15 ms of analytic fall time

    def test_standing_normal_force_equals_body_weight(self):
        tr = rollout(OpenLoopController(GaitParams()), BipedParams(), 0, 3.0)
        total = tr["force"].sum(1)[-100:]
        self.assertAlmostEqual(float(np.mean(total)) / tr["meta"]["weight"], 1.0, delta=0.05)


def synth(n=1000, speed=0.4, cadence=1.0, flight=False, chatter=False, sat=0.0, slip=0.0, fall_at=None,
          body=0.0, back=False, pitch=0.05):
    """Synthetic 200 Hz trace of an idealised walker (alternating feet, double support) with injectable faults."""
    t = np.arange(n) * SAMPLE_DT
    sgn = -1.0 if back else 1.0
    x = sgn * speed * t
    z = np.full(n, 0.77)
    p = np.full(n, pitch)
    ph = (t * cadence) % 1.0  # foot 0 stance for ph<0.6, foot 1 in antiphase (duty 0.6 -> double support)
    f = np.zeros((n, 2))
    f[:, 0] = np.where(ph < 0.6, 300.0, 0.0)
    f[:, 1] = np.where(((ph + 0.5) % 1.0) < 0.6, 300.0, 0.0)
    if flight:
        f[:] = np.where((t[:, None] * cadence % 1.0) < 0.4, 0.0, f)
    if chatter:  # contact toggles every 15 ms
        f[:, 0] = np.where((np.arange(n) // 3) % 2 == 0, 300.0, 0.0)
    # foot placement: x is constant during stance and advances 0.6 m per cycle while the foot is airborne
    foot_x = np.zeros((n, 2))
    for k in (0, 1):
        phk = (ph + 0.5 * k) % 1.0
        cycle = np.floor(t * cadence + 0.5 * k)
        foot_x[:, k] = sgn * (0.6 * cycle + np.where(phk < 0.6, 0.0, 0.6 * (phk - 0.6) / 0.4))
    lim = 60.0
    demand = np.zeros((n, 6))
    demand[:, 0] = 20.0
    if sat:
        demand[: int(sat * n), 0] = lim
    sl = np.zeros((n, 2))
    sl[: int(slip * n), :] = 0.5
    bc = np.zeros(n)
    bc[: int(body * n)] = 1.0
    if fall_at is not None:
        i = int(fall_at / SAMPLE_DT)
        z[i:] = 0.1
        p[i:] = 1.3
        x[i:] = x[i]
    tr = {"t": t, "x": x, "z": z, "pitch": p, "q": np.zeros((n, 6)), "qd": np.zeros((n, 6)),
          "tau": np.clip(demand, -lim, lim), "demand": demand, "force": f, "slip": sl, "foot_x": foot_x,
          "foot_z": np.zeros((n, 2)), "body_contact": bc,
          "meta": {"seed": 0, "duration": n * SAMPLE_DT, "mass": 12.0, "weight": W, "torque_limit": lim,
                   "controller": "synthetic"}}
    if fall_at is not None:
        for k in ("t", "x", "z", "pitch", "q", "qd", "tau", "demand", "force", "slip", "foot_x", "foot_z",
                  "body_contact"):
            tr[k] = tr[k][: int((fall_at + 0.15) / SAMPLE_DT)]
    return tr


class GateTests(unittest.TestCase):
    def label(self, **kw):
        m = compute_metrics(synth(**kw))
        return m["label"], m

    def test_synthetic_ideal_walker_passes_all_gates(self):
        label, m = self.label()
        self.assertEqual(m["violations"], [], m)
        self.assertEqual(label, "walking")
        self.assertGreater(m["valid_step_rate"], 0.8)

    def test_each_fault_is_rejected_with_the_expected_label(self):
        cases = {
            "backward": ({"back": True}, "backward_shuffle"),
            "hopping": ({"flight": True}, "hopping"),
            "chatter": ({"chatter": True}, "contact_chatter"),
            "saturated": ({"sat": 0.6}, "torque_saturated"),
            "sliding": ({"slip": 0.6}, "foot_sliding"),
            "dragging": ({"body": 0.2}, "body_dragging"),
            "stationary": ({"speed": 0.0}, None),
        }
        for name, (kw, want) in cases.items():
            label, m = self.label(**kw)
            self.assertFalse(m["walking"], name)
            if want:
                self.assertEqual(label, want, (name, m["violations"]))

    def test_falling_forward_is_not_walking_and_counts_only_upright_displacement(self):
        label, m = self.label(speed=2.0, fall_at=1.0)
        self.assertEqual(label, "falling_forward")
        self.assertFalse(m["walking"])
        self.assertLess(m["forward_disp_upright"], 2.0 * 1.1)  # nothing after the fall onset is credited

    def test_sliding_without_steps_is_not_walking(self):
        tr = synth()
        tr["force"][:] = 300.0  # both feet permanently loaded: displacement but no steps
        m = compute_metrics(tr)
        self.assertEqual(m["valid_steps"], 0)
        self.assertEqual(m["label"], "sliding_without_steps")

    def test_fitness_ranks_walker_above_every_faulty_variant(self):
        base = compute_metrics(synth())
        base_f = fitness_components(base)["total"]
        for kw in ({"back": True}, {"flight": True}, {"chatter": True}, {"sat": 0.6}, {"fall_at": 1.0, "speed": 2.0}):
            m = compute_metrics(synth(**kw))
            self.assertLess(fitness_components(m)["total"], base_f, kw)

    def test_fitness_still_ranks_failing_candidates_by_progress(self):
        slow = compute_metrics(synth(speed=0.05))
        quick = compute_metrics(synth(speed=0.15))
        self.assertFalse(slow["walking"] or quick["walking"])
        self.assertGreater(fitness_components(quick)["total"], fitness_components(slow)["total"])


class StepEventTests(unittest.TestCase):
    def ev(self, foot, kind, t):
        return {"foot": foot, "kind": kind, "t": t, "t_confirm": t + 0.02}

    def test_valid_alternating_forward_steps(self):
        foot_x = np.zeros((400, 2))
        events = [self.ev(0, "touchdown", 0.0), self.ev(1, "touchdown", 0.0)]
        x = 0.0
        for i in range(4):
            k = i % 2
            t0 = 0.4 + i * 0.4
            foot_x[int(t0 / SAMPLE_DT):, k] = x
            events.append(self.ev(k, "liftoff", t0))
            x += 0.3
            foot_x[int((t0 + 0.25) / SAMPLE_DT):, k] = x
            events.append(self.ev(k, "touchdown", t0 + 0.25))
        out = step_events(events, foot_x, DEFAULT_CRITERIA)
        self.assertEqual(len(out["valid"]), 4)  # the initial touchdown at t=0 is each foot's first stance
        self.assertEqual(out["backward"], 0)

    def test_short_stance_and_short_swing_are_not_steps(self):
        foot_x = np.zeros((400, 2))
        foot_x[:, 0] = np.linspace(0, 2, 400)
        ev = [self.ev(0, "touchdown", 0.0), self.ev(0, "liftoff", 0.05), self.ev(0, "touchdown", 0.10),
              self.ev(0, "liftoff", 0.15), self.ev(0, "touchdown", 0.20)]
        self.assertEqual(step_events(ev, foot_x, DEFAULT_CRITERIA)["valid"], [])

    def test_rearward_landing_is_a_backward_step(self):
        foot_x = np.zeros((400, 2))
        foot_x[int(0.6 / SAMPLE_DT):, 0] = -0.3
        ev = [self.ev(0, "touchdown", 0.0), self.ev(0, "liftoff", 0.4), self.ev(0, "touchdown", 0.6)]
        out = step_events(ev, foot_x, DEFAULT_CRITERIA)
        self.assertEqual((len(out["valid"]), out["backward"]), (0, 1))

    def test_same_foot_twice_does_not_alternate(self):
        foot_x = np.zeros((600, 2))
        ev, x = [self.ev(0, "touchdown", 0.0)], 0.0
        for i in range(3):
            ev.append(self.ev(0, "liftoff", 0.4 + 0.5 * i))
            x += 0.3
            foot_x[int((0.65 + 0.5 * i) / SAMPLE_DT):, 0] = x
            ev.append(self.ev(0, "touchdown", 0.65 + 0.5 * i))
        self.assertEqual(len(step_events(ev, foot_x, DEFAULT_CRITERIA)["valid"]), 1)


class RealControllerRegressionTests(unittest.TestCase):
    SEEDS = (1000, 1001, 1002)

    def test_standing_is_stationary_not_walking(self):
        r = evaluate_controller(OpenLoopController(GaitParams()), BipedParams(), self.SEEDS[:2], 4.0)
        self.assertEqual(set(r["labels"]), {"stationary"})

    def test_phase0_open_loop_gait_does_not_count_as_walking(self):
        g = GaitParams(gait_freq=1.0, hip_amp=0.4, knee_amp=0.4, stand_knee=-0.1)
        r = evaluate_controller(OpenLoopController(g), BipedParams(), self.SEEDS[:2], 6.0)
        self.assertEqual(r["walking_fraction"], 0.0)
        self.assertTrue(all(m["speed_upright"] < 0 for m in r["per_seed"]))  # it moves backward

    def test_phase2a_feasibility_exploit_fails_walking_classification(self):
        # Rounded parameters of the candidate found in the 2026-10-13 feasibility search: forward displacement
        # via high-frequency contact chatter, long flight phases and saturated torque.
        p = LagSinusoidParams(gait_freq=0.82, hip_amp=0.66, knee_amp=0.68, lag=1.62, stand_hip=0.14,
                              stand_knee=-0.56, kp=438.62, kd=23.65, balance_gain=132.35)
        r = evaluate_controller(LagSinusoidController(p), BipedParams(), self.SEEDS, 8.0)
        self.assertEqual(r["walking_fraction"], 0.0)
        self.assertFalse(r["feasible"])
        for m in r["per_seed"]:
            self.assertTrue({"contact_chatter", "hopping", "torque_saturated"} & set(m["violations"]), m["violations"])
            self.assertGreater(m["saturation_frac"], 0.5)

    def test_open_loop_adapter_matches_original_controller(self):
        g = GaitParams(gait_freq=1.0, hip_amp=0.3, knee_amp=0.3)
        q, qd = np.linspace(-0.1, 0.1, 6), np.linspace(0.2, -0.2, 6)
        np.testing.assert_array_equal(OpenLoopController(g).torque(0.37, 0.05, 0.1, q, qd),
                                      compute_torque(g, 0.37, 0.05, 0.1, q, qd))

    def test_slip_uses_contact_point_velocity_zero_when_standing(self):
        tr = rollout(OpenLoopController(GaitParams()), BipedParams(), 0, 3.0)
        self.assertLess(float(tr["slip"][-100:].max()), 0.02)


if __name__ == "__main__":
    unittest.main()
