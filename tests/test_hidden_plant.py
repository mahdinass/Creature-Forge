"""Tests for creature_forge.hidden_plant: bit-identity with the existing rollout, verification and CMA paths at zero deviation;
DSL validation (reject, never clip); physical effect of every primitive kind."""
import unittest

import mujoco
import numpy as np

from creature_forge import challenges
from creature_forge import creature_walk as cw
from creature_forge import hidden_plant as hp
from creature_forge import physics_probe as pp
from creature_forge.forge_pool import InlinePool
from creature_forge.phasegait_init import controller_from_vector
from creature_forge.sandbox import SandboxBody

R2 = list(cw.R2_WINNER)
V17 = R2 + [0.5, 0.5]
BODY = SandboxBody().as_dict()
BODY["pose"] = list(BODY["pose"])
SEED = 100003
SAME_KEYS = ("t", "x", "z", "pitch", "q", "qd", "tau", "demand", "force", "slip", "foot_x", "foot_z", "body_contact")
RICH_KEYS = SAME_KEYS + ("com", "com_vel", "angmom_y", "pitch_rate", "ft_x", "contact_x", "cop_x", "sup_min", "sup_max",
                         "saturated", "tracking_error", "foot_low", "swing_clear")


def prim(kind, target, **params):
    return {"kind": kind, "target": target, "params": params}


def eq(a, b):
    return np.array_equal(np.asarray(a), np.asarray(b), equal_nan=True)


class BitIdentity(unittest.TestCase):
    def test_rich_rollout_identical(self):
        for ff in (None, 1.07):
            ref = pp.rich_rollout(BODY, V17, SEED, duration=2.0, perturb=0.06, friction_factor=ff)
            got = hp.plant_rollout(None, BODY, V17, SEED, duration=2.0, perturb=0.06, friction_factor=ff)
            for k in RICH_KEYS:
                self.assertTrue(eq(ref[k], got[k]), f"{k} differs (ff={ff})")

    def test_plain_rollout_identical_with_settle(self):
        body = cw._body(BODY)
        for settle in (0.0, 0.3):
            ref = cw.rollout(controller_from_vector(V17, body=body), body, SEED, 2.0, perturb=0.06, settle_s=settle)
            got = hp.plant_rollout({}, BODY, V17, SEED, duration=2.0, perturb=0.06, rich=False, settle_s=settle)
            for k in SAME_KEYS:
                self.assertTrue(eq(ref[k], got[k]), f"{k} differs (settle={settle})")

    def test_seed_job_matches_challenges(self):
        spec = challenges.ChallengeSpec.from_dict({**challenges.default_spec("walk", [SEED]).to_dict(), "duration": 3.0})
        job = {"body": BODY, "controllers": {"stand": None, "walk": {"vector": V17, "provenance": {"kind": "custom"}}},
               "spec": spec.to_dict(), "seed": SEED}
        ref = challenges.seed_job(job)
        got = hp.seed_job(job, plant={})
        self.assertEqual(ref["outcome"], got["outcome"])
        self.assertEqual(ref["score"], got["score"])
        for k in challenges.WALK_KEEP:
            self.assertEqual(ref["metrics"][k], got["metrics"][k], k)

    def test_cma_eval_matches_default_path(self):
        seeds = [SEED, SEED + 1]
        rows = hp.walk_seeds({}, BODY, V17, seeds, duration=2.0)
        from creature_forge.arena import VARIATION_PRESET
        conds = hp._conditions(seeds, VARIATION_PRESET)
        for s, c, r in zip(seeds, conds, rows):
            from creature_forge.arena import _body_with_friction
            jb = _body_with_friction(BODY, c["friction_factor"])[0]
            ref = cw.eval_job({"vector": V17, "body": jb, "seeds": [s], "duration": 2.0, "start": c["start"],
                               "perturb": c["perturb"]})["per_seed"][0]
            for k in ("walking", "fell", "fitness", "forward_disp_upright", "valid_steps", "fall_time"):
                self.assertEqual(ref[k], r[k], k)

    def test_observe_matches_probe(self):
        ref = pp.observe(BODY, V17, [SEED], duration=2.0)
        got = hp.observe(BODY, V17, [SEED], plant=None, duration=2.0)
        self.assertEqual(ref["n_walking"], got["n_walking"])
        for k, v in ref["median"].items():
            self.assertTrue(eq(v if v is not None else np.nan, got["median"][k] if got["median"][k] is not None else np.nan), k)


class DSL(unittest.TestCase):
    def test_rejects_not_clips(self):
        with self.assertRaises(hp.DeviationError):
            hp.validate_primitive(prim("actuator_strength", "all", factor=3.0))
        with self.assertRaises(hp.DeviationError):
            hp.validate_primitive(prim("warp_drive", "all", factor=1.0))
        with self.assertRaises(hp.DeviationError):
            hp.validate_primitive(prim("payload", "torso", mass_kg=1.0))
        with self.assertRaises(hp.DeviationError):
            hp.validate_primitive(prim("sensor_bias", "elbow", rad=0.1))
        with self.assertRaises(hp.DeviationError):
            hp.normalize_plant({"deviation": [], "secret": 1})
        p = hp.validate_primitive(prim("sensor_delay", "all", seconds=0.02))
        self.assertEqual(p["params"]["seconds"], 0.02)


class Effects(unittest.TestCase):
    def model_after(self, prims):
        model = mujoco.MjModel.from_xml_string(__import__("creature_forge.sandbox", fromlist=["_mjcf"])._mjcf(cw._body(BODY)))
        data = mujoco.MjData(model)
        hp.apply_model(model, prims)
        mujoco.mj_setConst(model, data)
        return model

    def test_model_primitives(self):
        base = self.model_after([])
        m = self.model_after([prim("actuator_strength", "left", factor=0.4)])
        self.assertTrue(np.allclose(m.actuator_gear[:3, 0], 0.4 * base.actuator_gear[:3, 0]))
        self.assertTrue(np.allclose(m.actuator_gear[3:, 0], base.actuator_gear[3:, 0]))
        m = self.model_after([prim("joint_damping", "knees", factor=10.0)])
        self.assertAlmostEqual(m.dof_damping[4], 5.0)
        self.assertAlmostEqual(m.dof_damping[3], 0.5)
        m = self.model_after([prim("payload", "torso", mass_kg=2.0, x_m=0.1)])
        self.assertAlmostEqual(m.body_mass.sum(), base.body_mass.sum() + 2.0)
        t = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "torso")
        self.assertGreater(m.body_ipos[t][0], base.body_ipos[t][0])
        m = self.model_after([prim("contact_friction", "feet", factor=0.2)])
        g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "foot_l")
        self.assertAlmostEqual(m.geom_friction[g, 0], 0.2 * base.geom_friction[g, 0])

    def test_body_and_vector_primitives(self):
        b = hp.plant_body(BODY, hp.validate_deviation([prim("segment_length", "shank_r", factor=0.8)]))
        self.assertAlmostEqual(b["shank_length_r"], 0.8 * BODY["shank_length"])
        self.assertAlmostEqual(b["shank_length"], BODY["shank_length"])
        v = hp.plant_vector(V17, hp.validate_deviation([prim("gain_scale", "placement", factor=0.0)]))
        self.assertEqual(v[-2:], [0.0, 0.0])
        self.assertEqual(v[:-2], V17[:-2])

    def test_controller_primitives_change_motion(self):
        ref = hp.plant_rollout(None, BODY, V17, SEED, duration=1.0, perturb=0.06, rich=False)
        for p in (prim("sensor_delay", "all", seconds=0.05), prim("sensor_bias", "pitch", rad=0.1),
                  prim("clock_scale", "clock", factor=1.5)):
            got = hp.plant_rollout({"deviation": [p]}, BODY, V17, SEED, duration=1.0, perturb=0.06, rich=False)
            self.assertFalse(eq(ref["pitch"], got["pitch"]), p["kind"])

    def test_weak_actuators_limit_delivered_torque(self):
        tr = hp.plant_rollout({"deviation": [prim("actuator_strength", "all", factor=0.25)]}, BODY, V17, SEED, duration=1.0,
                              perturb=0.06, rich=False)
        self.assertLessEqual(float(np.abs(tr["tau"]).max()), 0.25 * BODY["torque_limit"] + 1e-6)

    def test_verify_runs_on_plant(self):
        hard = {"deviation": [prim("actuator_strength", "all", factor=0.1)]}
        design = {"body": BODY, "vector": V17}
        out = hp.verify(hard, design, design, [SEED], [SEED + 1], pool=InlinePool())
        self.assertEqual(out["status"], "NOT_RECOVERED")
        self.assertEqual(out["rule"], "full_recovery_v1")


if __name__ == "__main__":
    unittest.main()
