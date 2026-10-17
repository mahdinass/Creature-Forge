"""Tests for creature_forge.mechanisms (safe control-law DSL, controller hook, search-space support)."""
import json
import math
import time
import unittest

import numpy as np

from creature_forge import challenges as ch
from creature_forge import creature_walk as cw
from creature_forge import mechanisms as mech
from creature_forge import walk_opt as wo
from creature_forge.phasegait_init import PhaseGaitInitController, controller_from_vector
from creature_forge.sandbox import SandboxBody

R2 = list(cw.R2_WINNER)
DEFAULT = SandboxBody()
STILTS = SandboxBody(thigh_length=0.55, shank_length=0.55, foot_length=0.07, torso_mass=4.7917)


def sig(**kw):
    s = {k: 0.0 for k in mech.SIGNALS}
    s.update(kw)
    return s


def m1(*terms, target="hip", leg="swing", bound=1.0, id="t"):
    return {"id": id, "target": target, "leg": leg, "terms": list(terms), "gain_bound": bound}


def values(expr, **kw):
    return float(mech.compile_mechanism(m1(expr)).evaluate(sig(**kw))[0])


class DslAcceptance(unittest.TestCase):
    def test_accepts(self):
        for e in ["d", "-d - v", "0.5*pitch + 2*pitch_rate", "tanh(3*d)", "clip(d, -0.2, 0.2)", "abs(v) + min(d, v) - max(d, 1)",
                  "sin(phase*6.28) * cos(t)", "sqrt_abs(pitch)", "(d + v) / (h + 0.1)", "+d", "swing * d", "1e-3 * knee_rate"]:
            self.assertEqual(mech.validate_term(e), [], e)

    def test_rejects(self):
        bad = ["d.__class__", "__import__('os')", "eval('1')", "open('x')", "d[0]", "(lambda: 1)()", "d ** 2", "d % 2", "d // 2",
               "'a'", "b'a'", "d > 1", "d if v else 0", "d and v", "not d", "[d for d in (1,)]", "{d: 1}", "(d, v)", "x", "foo(d)",
               "tanh(d, v)", "clip(d)", "tanh(x=d)", "tanh(*d)", "d.real", "print(d)", "abs", "tanh", "1e999", "True", "None",
               "d; v", "d = 1", "", "   ", "d +", "~d", "d << 1", "d @ v", "f'{d}'", "1j", "__builtins__", "sum(d)", "d if d else v",
               "a" * 201, "d + " * 80 + "d", "tanh(" * 7 + "d" + ")" * 7, "-" * 8 + "d", "(" * 300 + "d" + ")" * 300]
        for e in bad:
            self.assertNotEqual(mech.validate_term(e), [], e[:40])
        self.assertNotEqual(mech.validate_term(None), [])
        self.assertNotEqual(mech.validate_term(3), [])

    def test_depth_limit_is_exactly_six(self):
        self.assertEqual(mech.validate_term("tanh(" * 6 + "d" + ")" * 6), [])
        self.assertNotEqual(mech.validate_term("tanh(" * 7 + "d" + ")" * 7), [])

    def test_mechanism_schema(self):
        good = m1("d", "v")
        self.assertEqual(mech.validate_mechanism(good), [])
        self.assertEqual(mech.validate_mechanism({**good, "rationale": "why", "revises": "old"}), [])
        for bad in [{**good, "id": ""}, {**good, "id": "a" * 25}, {**good, "id": "a b"}, {**good, "id": "x\n"}, {**good, "target": "foot"},
                    {**good, "leg": "left"}, {**good, "terms": []}, {**good, "terms": ["d"] * 5}, {**good, "terms": "d"},
                    {**good, "gain_bound": 0}, {**good, "gain_bound": 5.1}, {**good, "gain_bound": float("nan")},
                    {**good, "gain_bound": True}, {**good, "gain_bound": "1"}, {**good, "extra": 1}, {**good, "rationale": 3},
                    "nope", None, {k: v for k, v in good.items() if k != "terms"}]:
            self.assertNotEqual(mech.validate_mechanism(bad), [], bad)
        with self.assertRaises(ValueError):
            mech.compile_mechanism({**good, "terms": ["__import__('os')"]})

    def test_mechanism_set_rules(self):
        a, b = m1("d", id="a"), m1("v", id="b")
        self.assertEqual(mech.validate_mechanisms([a, b]), [])
        self.assertNotEqual(mech.validate_mechanisms([a, b, m1("t", id="c")]), [])
        self.assertNotEqual(mech.validate_mechanisms([a, m1("v", id="a")]), [])
        self.assertNotEqual(mech.validate_mechanisms([m1("d", "v", "t", "h", id="a"), m1("d", "v", "t", "h", id="b"),
                                                      m1("d", id="c")]), [])
        self.assertEqual(mech.validate_mechanisms([m1("d", "v", "t", "h", id="a"), m1("d", "v", "t", "h", id="b")]), [])


class Evaluation(unittest.TestCase):
    def test_hand_values(self):
        self.assertAlmostEqual(values("-d - v", d=0.2, v=0.1), -0.3)
        self.assertAlmostEqual(values("0.5*pitch + 2*pitch_rate", pitch=0.2, pitch_rate=0.1), 0.3)
        self.assertAlmostEqual(values("tanh(d)", d=0.5), math.tanh(0.5))
        self.assertEqual(values("clip(d, -0.2, 0.2)", d=1.0), 0.2)
        self.assertEqual(values("abs(d) + min(d, v) + max(d, v)", d=-2.0, v=3.0), 2.0 - 2.0 + 3.0)
        self.assertAlmostEqual(values("sqrt_abs(d)", d=-4.0), 2.0)
        self.assertAlmostEqual(values("sin(d) + cos(v)", d=1.0, v=2.0), math.sin(1.0) + math.cos(2.0))
        self.assertEqual(values("7 / 2"), 3.5)                      # int literals are floats: no floor division
        self.assertEqual(values("d * swing", d=2.0, swing=1.0), 2.0)

    def test_safe_division_and_nan(self):
        self.assertEqual(values("1 / d", d=0.0), 10.0)
        self.assertEqual(values("1 / d", d=-0.0), -10.0)
        self.assertEqual(values("1 / d", d=-1e-9), -10.0)
        self.assertAlmostEqual(values("1e-6 / d", d=0.0), 1.0)      # |b| <= 1e-6 -> copysign(1e-6, b)
        self.assertAlmostEqual(values("d / 2", d=1.0), 0.5)
        self.assertEqual(values("d / d", d=float("nan")), 0.0)      # nan -> 0
        self.assertEqual(values("d * 1e300 * 1e300", d=1.0), 10.0)  # inf -> clipped
        self.assertEqual(values("-d * 1e300 * 1e300", d=1.0), -10.0)
        self.assertEqual(values("d * 1e300 * 1e300 * 0"), 0.0)      # nan -> 0
        self.assertEqual(values("sin(d)", d=float("inf")), 0.0)
        self.assertEqual(values("100*d", d=1.0), 10.0)
        self.assertEqual(values("-100*d", d=1.0), -10.0)

    def test_evaluate_returns_array_of_terms(self):
        c = mech.compile_mechanism(m1("d", "v", "pitch"))
        out = c.evaluate(sig(d=1.0, v=2.0, pitch=3.0))
        self.assertIsInstance(out, np.ndarray)
        self.assertEqual(out.tolist(), [1.0, 2.0, 3.0])

    def test_namespace_has_no_builtins(self):
        c = mech.compile_mechanism(m1("d"))
        self.assertEqual(c.namespace["__builtins__"], {})
        self.assertEqual(sorted(k for k in c.namespace if k != "__builtins__"),
                         sorted(list(mech.FUNCS) + ["_sdiv"]))
        for code in c.codes:
            self.assertTrue(all(n in mech.SIGNALS or n in c.namespace for n in code.co_names))
        # a name outside the whitelist cannot be resolved even if it were injected into a hand-built code object
        bad = compile("__import__('os')", "<x>", "eval")
        with self.assertRaises(NameError):
            eval(bad, c.namespace, sig())

    def test_signal_docs_cover_signals(self):
        self.assertEqual(set(mech.SIGNALS), set(mech.SIGNAL_DOCS))
        self.assertEqual(len(mech.SIGNALS), 16)


class Generators(unittest.TestCase):
    def test_random_valid_and_deterministic(self):
        rng = np.random.default_rng(0)
        draws = [mech.random_mechanism(rng, n_terms=1 + i % 4, id=f"r{i}") for i in range(1000)]
        for m in draws:
            self.assertEqual(mech.validate_mechanism(m), [], m)
            json.dumps(m)
            c = mech.compile_mechanism(m)
            self.assertTrue(c.signals_used)
            c.evaluate(sig(d=0.1, v=0.1, pitch=0.1))
        self.assertGreater(len({m["target"] for m in draws}), 5)
        self.assertEqual({m["leg"] for m in draws}, set(mech.LEGS))
        a = [mech.random_mechanism(np.random.default_rng(7)) for _ in range(3)]
        b = [mech.random_mechanism(np.random.default_rng(7)) for _ in range(3)]
        self.assertEqual(a, b)
        r1, r2 = np.random.default_rng(1), np.random.default_rng(2)
        self.assertNotEqual([mech.random_mechanism(r1) for _ in range(5)], [mech.random_mechanism(r2) for _ in range(5)])

    def test_generic_and_expert(self):
        g = mech.generic_linear_mechanisms()
        self.assertEqual([m["id"] for m in g], ["gen_hip_swing", "gen_hip_stance"])
        self.assertEqual(mech.validate_mechanisms(g), [])
        self.assertEqual(mech.n_gains(g), 8)
        self.assertEqual([m["leg"] for m in g], ["swing", "stance"])
        e = mech.expert_foot_placement()
        self.assertEqual(e, {"id": "expert_fp", "target": "hip", "leg": "swing", "terms": ["-d", "-v"], "gain_bound": 1.5})
        self.assertEqual(mech.validate_mechanism(e), [])


class SpecAndSpace(unittest.TestCase):
    def test_controller_from_spec_identity_without_mechanisms(self):
        for v in (R2, R2[:13], R2 + [0.3, 0.2]):
            a = mech.controller_from_spec(v, (), body=DEFAULT)
            b = controller_from_vector(v, body=DEFAULT)
            self.assertIs(type(a), type(b))
            self.assertEqual(vars(a)["p"], vars(b)["p"])
        self.assertIs(type(mech.controller_from_spec(R2)), PhaseGaitInitController)

    def test_controller_from_spec_with_mechanisms(self):
        c = mech.controller_from_spec(R2 + [0.5, 0.25], [mech.expert_foot_placement()], body=DEFAULT)
        self.assertIsInstance(c, mech.MechanismController)
        self.assertIsInstance(c, PhaseGaitInitController)
        with self.assertRaises(ValueError):
            mech.controller_from_spec(R2, [mech.expert_foot_placement()], body=DEFAULT)            # missing gains
        with self.assertRaises(ValueError):
            mech.controller_from_spec(R2 + [0.1, 0.1, 0.1], [mech.expert_foot_placement()], body=DEFAULT)  # fp-style padding
        with self.assertRaises(ValueError):
            mech.controller_from_spec(R2 + [2.0, 0.0], [mech.expert_foot_placement()], body=DEFAULT)  # beyond gain_bound
        with self.assertRaises(ValueError):
            mech.controller_from_spec(R2 + [0.5, 0.2], [mech.expert_foot_placement()])               # needs the body for d, v
        three = [m1("d", id="a"), m1("d", id="b"), m1("d", id="c")]
        with self.assertRaises(ValueError):
            mech.controller_from_spec(R2 + [0.0] * 3, three, body=DEFAULT)

    def test_search_space_dimensions_and_round_trip(self):
        exp = mech.expert_foot_placement()
        sp = wo.SearchSpace(("freq", "kp"), ("torso_mass",), mechanisms=(exp,))
        self.assertEqual(sp.dim, 2 + 2 + 1)
        self.assertEqual(sp.n_gains, 2)
        self.assertEqual(sp.to_dict()["dim"], 5)
        self.assertEqual(sp.to_dict()["mechanisms"], [exp])
        self.assertNotIn("mechanisms", wo.SearchSpace(("freq",)).to_dict())
        vec = R2 + [0.6, -0.9]
        x = wo.encode(sp, DEFAULT, vec, DEFAULT, vec)
        self.assertEqual(len(x), 5)
        self.assertAlmostEqual(x[2], (0.6 + 1.5) / 3.0)
        self.assertAlmostEqual(x[3], (-0.9 + 1.5) / 3.0)
        body, v = wo.decode(sp, DEFAULT, vec, x)
        self.assertEqual(len(v), 17)
        np.testing.assert_allclose(v, vec, atol=1e-9)
        # base gains are 0 -> u = 0.5 exactly; 15-D base vector accepted
        x0 = wo.encode(sp, DEFAULT, R2, DEFAULT, R2)
        self.assertEqual(x0[2:4].tolist(), [0.5, 0.5])
        _, v0 = wo.decode(sp, DEFAULT, R2, x0)
        self.assertEqual(v0[15:], [0.0, 0.0])
        _, vlo = wo.decode(sp, DEFAULT, R2, np.array([0.5, 0.5, 0.0, 1.0, 0.5]))
        self.assertEqual(vlo[15:], [-1.5, 1.5])
        with self.assertRaises(ValueError):
            wo.encode(sp, DEFAULT, R2 + [2.0, 0.0], DEFAULT, R2 + [2.0, 0.0])
        gsp = wo.SearchSpace((), mechanisms=tuple(mech.generic_linear_mechanisms()))   # gains alone make a space
        self.assertEqual(gsp.dim, 8)
        self.assertEqual(gsp.gain_bounds, [1.5] * 8)
        self.assertEqual(len(wo.decode(gsp, DEFAULT, R2, np.full(8, 0.5))[1]), 23)

    def test_search_space_rejections(self):
        exp = mech.expert_foot_placement()
        with self.assertRaises(ValueError):
            wo.SearchSpace(("fp_kd",), mechanisms=(exp,))
        with self.assertRaises(ValueError):
            wo.SearchSpace(("freq",), mechanisms=({**exp, "terms": ["__import__('os')"]},))
        with self.assertRaises(ValueError):
            wo.SearchSpace(("freq",), mechanisms=(exp, exp))                      # duplicate ids
        three = tuple(m1("d", id=f"m{i}") for i in range(3))
        with self.assertRaises(ValueError):
            wo.SearchSpace(("freq",), mechanisms=three)

    def test_search_space_without_mechanisms_unchanged(self):
        sp = wo.SearchSpace(("freq", "kp"), ("torso_mass",))
        self.assertEqual(sp.mechanisms, ())
        self.assertEqual(sp.dim, 3)
        self.assertEqual(sp.to_dict(), {"ctrl_params": ["freq", "kp"], "body_params": ["torso_mass"], "body_ratio": [0.5, 1.5],
                                        "mode": "guided", "dim": 3})
        hash(sp)

    def test_challenges_walk_vector_with_mechanisms(self):
        exp = mech.expert_foot_placement()
        c = {"walk": {"vector": R2 + [0.5, 0.5], "mechanisms": [exp]}}
        self.assertEqual(ch.walk_vector(c), R2 + [0.5, 0.5])
        with self.assertRaises(ch.ChallengeError):
            ch.walk_vector({"walk": {"vector": R2, "mechanisms": [exp]}})
        with self.assertRaises(ch.ChallengeError):
            ch.walk_vector({"walk": {"vector": R2 + [0, 0], "mechanisms": [{**exp, "leg": "x"}]}})
        self.assertEqual(ch.walk_vector({"walk": {"mechanisms": [exp]}}), R2 + [0.0, 0.0])
        self.assertEqual(ch.walk_vector({"walk": {"vector": R2}}), R2)
        self.assertEqual(ch.controller_provenance(c, "walk")["walk"]["mechanisms"], [exp])


# ---------------------------------------------------------------------------------------------------------
# MuJoCo (run on the VM)
# ---------------------------------------------------------------------------------------------------------
def trace(ctrl, body, seed=100301, duration=10.0):
    tr = cw.rollout(ctrl, body, seed, duration)
    return {k: tr[k] for k in ("t", "x", "z", "pitch", "q", "qd", "tau", "demand", "force")}


def same(a, b):
    return a.keys() == b.keys() and all(a[k].shape == b[k].shape and np.array_equal(a[k], b[k]) for k in a)


class MuJoCoMechanisms(unittest.TestCase):
    def test_zero_gains_are_bit_identical(self):
        for body in (DEFAULT, STILTS):
            base = trace(controller_from_vector(R2), body)
            for ms in ([mech.expert_foot_placement()], mech.generic_linear_mechanisms(),
                       [m1("pitch", "d", target="torque_ankle", leg="both", bound=5.0, id="tq")]):
                ctrl = mech.controller_from_spec(R2 + [0.0] * mech.n_gains(ms), ms, body=body)
                self.assertTrue(same(base, trace(ctrl, body)), (body.thigh_length, ms[0]["id"]))
            self.assertGreater(len(base["t"]), 100)

    def test_nonzero_gain_changes_the_trace(self):
        base = trace(controller_from_vector(R2), DEFAULT, duration=3.0)
        for ms, g in (([mech.expert_foot_placement()], [0.5, 0.5]),
                      ([m1("pitch", target="torque_hip", leg="stance", bound=5.0)], [3.0]),
                      ([m1("0.5*swing", target="knee", leg="both")], [0.3]),
                      ([m1("pitch", target="ankle", leg="stance")], [0.3])):
            alt = trace(mech.controller_from_spec(R2 + g, ms, body=DEFAULT), DEFAULT, duration=3.0)
            self.assertFalse(same(base, alt), ms[0]["id"])
            self.assertTrue(np.all(np.isfinite(alt["tau"])))

    def test_geometry_signals_match_fp_estimate(self):
        """d, v, h are finite and in a plausible range during a real walk (stance leg FK)."""
        ms = [m1("d", "v", "h", target="torque_hip", leg="both", bound=5.0)]
        ctrl = mech.controller_from_spec(R2 + [1e-9, 1e-9, 1e-9], ms, body=DEFAULT)
        seen = []
        orig = ctrl.torque

        def spy(*a):
            out = orig(*a)
            seen.append(ctrl._geo)
            return out
        ctrl.torque = spy
        cw.rollout(ctrl, DEFAULT, 100301, 3.0)
        g = np.array(seen)
        self.assertTrue(np.all(np.isfinite(g)))
        self.assertTrue(0.5 < g[-1, 2] < 1.1, g[-1])
        self.assertTrue(np.abs(g[:, 0]).max() < 1.0)

    def test_challenge_walk_with_mechanisms(self):
        exp = mech.expert_foot_placement()
        controllers = {"walk": {"vector": R2 + [0.4, 0.2], "mechanisms": [exp]}}
        spec = ch.default_spec("walk", [100301])
        res = ch.run_challenge(DEFAULT, controllers, spec)
        self.assertEqual(len(res.per_seed), 1)
        self.assertIn("label", res.per_seed[0].metrics)
        self.assertEqual(res.controller["walk"]["mechanisms"], [exp])
        plain = ch.run_challenge(DEFAULT, {"walk": {"vector": R2}}, spec)
        zero = ch.run_challenge(DEFAULT, {"walk": {"vector": R2 + [0.0, 0.0], "mechanisms": [exp]}}, spec)
        self.assertEqual(plain.per_seed[0].metrics, zero.per_seed[0].metrics)
        self.assertEqual(plain.per_seed[0].score, zero.per_seed[0].score)
        pay = ch._walk_payload(DEFAULT, controllers, spec, 100301, 20)
        self.assertEqual(len(pay["gait"]["walk_vector"]), 17)

    def test_eval_job_with_mechanisms(self):
        job = {"vector": R2 + [0.0, 0.0], "body": DEFAULT.as_dict(), "seeds": [1], "duration": 1.0,
               "mechanisms": [mech.expert_foot_placement()]}
        out = cw.eval_job(job)
        self.assertTrue(out["ok"], out)
        base = cw.eval_job({"vector": R2, "body": DEFAULT.as_dict(), "seeds": [1], "duration": 1.0})
        self.assertEqual(out["per_seed"], base["per_seed"])

    def test_tiny_cma_search_with_mechanisms(self):
        sp = wo.SearchSpace(("freq",), mechanisms=(mech.expert_foot_placement(),))
        res = wo.cma_search(DEFAULT, R2, sp, budget=40, train_seeds=[1, 2], noise_seed=3, duration=1.0, variation=None)
        self.assertLessEqual(res["rollouts_used"], 40)
        self.assertGreater(len(res["history"]), 0)
        self.assertEqual(len(res["best"]["vector"]), 17)
        self.assertEqual(len(res["init"]["vector"]), 17)
        self.assertEqual(res["space"]["mechanisms"], [mech.expert_foot_placement()])
        self.assertEqual(res["errors"], [])

    def test_rollout_slowdown(self):
        def timed(ctrl):
            t0 = time.perf_counter()
            cw.rollout(ctrl, DEFAULT, 100301, 10.0)
            return time.perf_counter() - t0
        cases = {"base": lambda: controller_from_vector(R2),
                 "expert": lambda: mech.controller_from_spec(R2 + [0.5, 0.5], [mech.expert_foot_placement()], body=DEFAULT),
                 "generic": lambda: mech.controller_from_spec(R2 + [0.1] * 8, mech.generic_linear_mechanisms(), body=DEFAULT)}
        mean = {k: float(np.mean([timed(f()) for _ in range(5)])) for k, f in cases.items()}
        print("\nrollout 10 s default body, mean of 5:", {k: round(v, 3) for k, v in mean.items()},
              "slowdown expert %.2fx generic %.2fx" % (mean["expert"] / mean["base"], mean["generic"] / mean["base"]))
        self.assertLess(mean["generic"] / mean["base"], 10.0)


if __name__ == "__main__":
    unittest.main()


class ConstantsTests(unittest.TestCase):
    def test_pi_is_an_allowed_constant_and_evaluates(self):
        import math
        from creature_forge import mechanisms as mx
        m = {"id": "pc", "target": "hip", "leg": "swing", "terms": ["sin(2 * pi * phase)"], "gain_bound": 1.0}
        self.assertEqual(mx.validate_mechanism(m), [])
        c = mx.compile_mechanism(m)
        sig = {k: 0.0 for k in mx.SIGNALS}
        sig["phase"] = 0.25
        self.assertAlmostEqual(float(c.evaluate(sig)[0]), math.sin(2 * math.pi * 0.25))

    def test_controller_parameters_are_not_signals(self):
        from creature_forge import mechanisms as mx
        reasons = mx.validate_mechanism({"id": "f", "target": "hip", "leg": "swing", "terms": ["freq * t"], "gain_bound": 1.0})
        self.assertTrue(any("not signals" in r for r in reasons))
