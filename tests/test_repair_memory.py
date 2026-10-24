"""RL-1 repair memory (creature_forge/repair_memory.py): memory evidence, calibrator and decision rules. No physics."""
import unittest

import numpy as np

from creature_forge import repair_memory as rm


def rec(screen, cma, kinds=(("payload", "torso"),), w=0.9):
    obs = {"1": {k: 0.0 for k in rm.OBS_SCALES}, "2": {k: 0.0 for k in rm.OBS_SCALES}}
    return {"engine": {"experiments": [{"kind": "observe", "features": obs}],
                       "history": [{"top": [{"pid": "p1", "w": w}, {"pid": "p2", "w": 1 - w}]}],
                       "particles": [{"pid": "p1", "structure": [list(kinds[0])]}, {"pid": "p2", "structure": [["sensor_bias", "pitch"]]}],
                       "events": [{"kind": "tool_screen", "ranking": [{"tool": t, "score": s} for t, s in screen]},
                                  {"kind": "tool_screen_cma", "ranking": [{"tool": t, "score": 0.0, "cma_walking": cw, "cma_fitness": 1.0}
                                                                          for t, cw in cma]}]}}


BODY = {"thigh_length": 0.3, "shank_length": 0.2, "foot_length": 0.1, "torso_mass": 6.0, "torque_limit": 20.0,
        "leg_density": 500.0, "foot_friction": 1.0}


class FeatureTests(unittest.TestCase):
    def test_engine_order_puts_the_cma_screen_first_then_the_probe_screen(self):
        r = rec([("foot_length", 1.0), ("feedback", 0.6), ("timing", 0.5)], [("timing", 4), ("foot_length", 3)])
        order = rm.engine_order(r)
        self.assertEqual(order[:3], ["timing", "foot_length", "feedback"])
        self.assertEqual(sorted(order), sorted(rm.TOOLS))
        ev = rm.twin_evidence(r)
        self.assertEqual(ev["timing"]["screened"], 1.0)
        self.assertIsNone(ev["posture"]["probe"])

    def test_context_vector_is_finite_and_uses_no_family_label(self):
        c = rm.context(rec([("timing", 1.0)], [("timing", 4)]), BODY)
        x = rm.ctx_vector(c)
        self.assertTrue(np.isfinite(x).all())
        self.assertAlmostEqual(c["kinds"]["payload"], 0.9)
        self.assertAlmostEqual(c["kinds"]["sensor_bias"], 0.1, places=6)
        self.assertNotIn("family", c)


class MemoryTests(unittest.TestCase):
    def test_kernel_memory_prefers_tools_that_worked_nearby_and_reports_support(self):
        rng = np.random.default_rng(0)
        X = np.vstack([rng.normal(0, 0.1, (20, 3)), rng.normal(5, 0.1, (20, 3))])
        Y = np.zeros((40, len(rm.TOOLS)))
        Y[:20, 0] = 1          # near 0: tool 0 works
        Y[20:, 1] = 1          # near 5: tool 1 works
        mem = rm.Memory(X, Y, bandwidth=0.5)
        q0, q5 = mem.query(np.zeros(3)), mem.query(np.full(3, 5.0))
        self.assertGreater(q0["rate"][0], 0.8)
        self.assertLess(q0["rate"][1], 0.2)
        self.assertGreater(q5["rate"][1], 0.8)
        far = mem.query(np.full(3, 50.0))
        self.assertLess(far["n_eff"], 1e-6)                                     # out of support
        self.assertAlmostEqual(float(far["rate"][0]), float(mem.base[0]), places=6)   # falls back to the population prior

    def test_simple_memory_breaks_ties_by_engine_order(self):
        X = np.zeros((3, 2))
        Y = np.zeros((3, len(rm.TOOLS)))
        eng = list(reversed(rm.TOOLS))
        self.assertEqual(rm.simple_memory_order(X, Y, np.zeros(2), eng), eng)


class CalibratorAndDecisionTests(unittest.TestCase):
    def test_logistic_recovers_a_monotone_signal(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=400)
        y = (rng.random(400) < 1 / (1 + np.exp(-2 * x))).astype(float)
        w = rm.fit_logistic(np.column_stack([np.ones(400), x]), y, l2=0.1)
        self.assertGreater(w[1], 1.2)

    def test_decide_abstain_commit_and_hedge(self):
        eng = list(rm.TOOLS)
        P = {t: 0.1 for t in rm.TOOLS}
        P["timing"] = 0.6
        self.assertEqual(rm.decide(P, eng, 0.5, n_min=1.0, hedge_delta=0.1)["mode"], "abstain")
        d = rm.decide(P, eng, 5.0, n_min=1.0, hedge_delta=0.1)
        self.assertEqual((d["mode"], d["order"][0]), ("commit", "timing"))
        P["posture"] = 0.55                                                    # the engine's top tool, close behind
        d = rm.decide(P, eng, 5.0, n_min=1.0, hedge_delta=0.1)
        self.assertEqual((d["mode"], d["order"][:2]), ("hedge", ["timing", "posture"]))
        self.assertEqual(sorted(d["order"]), sorted(rm.TOOLS))


if __name__ == "__main__":
    unittest.main()
