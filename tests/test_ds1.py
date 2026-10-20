"""DS-1 unit tests (docs/DS1_PROTOCOL.md): engine v6 pieces on canned twin predictions (tempering, open-world reserve, relative
assimilation of plant checks, option validation, v5 defaults), displacement evidence, the R-head, the shared case store and
dual-scored dossiers, and agent v5 validation (registered P(success), constraint feedback). No rollouts."""
import json
import math
import os
import tempfile
import unittest

import numpy as np

from creature_forge import belief_engine as be
from creature_forge import has_agent as ha
from creature_forge import has_cases as hc
from creature_forge import hdb_evidence as hev
from creature_forge import repair_learning as rl


# ------------------------------------------------------------------------------------------------ engine v6 on canned twins
class _Budget:
    def __init__(self, total):
        self.total, self.used = total, 0

    @property
    def remaining(self):
        return self.total - self.used


class _Bench:
    def __init__(self):
        self.twin, self.budget = _Budget(2800), _Budget(700)
        self.designs = [{"index": 0, "body": {}, "vector": []}, {"index": 1, "body": {}, "vector": []}]


def episode(v6, preds):
    """An Episode without a simulator: `preds[pid][experiment id]` are the particles' twin predictions."""
    ep = be.Episode.__new__(be.Episode)
    ep.b = _Bench()
    ep.v6 = None if v6 is None else {**be.V6_DEFAULTS, **v6}
    ep.T = float(ep.v6["temperature"]) if ep.v6 else 1.0
    ep._composite_rounds, ep._assimilated = 0, set()
    ep.particles, ep.experiments, ep.history, ep.events = {}, [], [], []
    ep.max_alive, ep.refine_top, ep.eig_top, ep.proposer, ep.diag_budget = 12, 3, 6, None, 120

    def predict(p, exp, n=None):          # like Episode._predict: charge the twin, cache the prediction per experiment
        if exp["id"] not in p.seen:
            ep.b.twin.used += len(exp.get("seeds") or ())
            p.seen[exp["id"]] = preds[p.pid][exp["id"]]
        return p.seen[exp["id"]]
    ep._predict = predict
    return ep


SEEDS = list(range(8))
OBS = {"id": "X0:observe", "kind": "observe", "seeds": SEEDS[:4],
       "features": {s: {"walking": 0.0, "pitch_mean": 0.1} for s in SEEDS[:4]}, "cost": 4}


def particle(pid, kind):
    return be.Particle(pid, [{"kind": kind, "target": "t", "params": {}}], "test")


def walk_pred(walks):
    return {s: {"walking": 1.0 if w else 0.0, "pitch_mean": 0.1} for s, w in zip(SEEDS, walks)}


class EngineV6(unittest.TestCase):
    def setup(self, v6, check_preds):
        preds = {"A": {"X0:observe": {s: {"walking": 0.0, "pitch_mean": 0.1} for s in SEEDS[:4]}},
                 "B": {"X0:observe": {s: {"walking": 0.0, "pitch_mean": 0.1} for s in SEEDS[:4]}}}
        for pid, w in check_preds.items():
            preds[pid]["X1:check@1"] = walk_pred(w)
        ep = episode(v6, preds)
        ep.experiments.append(OBS)
        for pid, kind in (("A", "payload"), ("B", "sensor_bias")):
            p = particle(pid, kind)
            ep._update_particle(p)
            ep.particles[pid] = p
        return ep

    def weights(self, ep):
        return {p.pid: round(w, 6) for p, w in ep.posterior()}

    def test_options_validated_and_v5_default(self):
        with self.assertRaises(ValueError):
            be.Episode.__init__(be.Episode.__new__(be.Episode), _Bench(), v6={"nonsense": 1})
        ep = self.setup(None, {})
        self.assertEqual(ep.unmodelled_mass(), 0.0)
        self.assertTrue(all(p.logw == p.loglik for p in ep.particles.values()))          # v5: untempered
        self.assertNotIn(be.UNMODELLED, [s for s, _ in ep.structure_posterior()])

    def test_tempering_divides_log_likelihood(self):
        ep = self.setup({"temperature": 4.0}, {})
        for p in ep.particles.values():
            self.assertAlmostEqual(p.logw, p.loglik / 4.0)

    def test_open_world_reserve(self):
        ep = self.setup({"misfit_threshold": 10.0}, {})       # every explanation fits worse than the reserve's level
        self.assertGreater(ep.unmodelled_mass(), 0.99)
        self.assertEqual(ep.structure_posterior()[0][0], be.UNMODELLED)
        self.assertFalse(ep.diagnosis_done(0.9))                # the reserve is never a confident diagnosis
        ep2 = self.setup({"misfit_threshold": -1e6}, {})
        self.assertLess(ep2.unmodelled_mass(), 1e-6)

    def test_assimilation_is_relative(self):
        # both explanations predicted the repair walks; the plant says it fails: no relative change
        ep = self.setup({}, {"A": [1] * 8, "B": [1] * 8})
        before = self.weights(ep)
        out = ep.assimilate_light({"body": {}, "vector": []}, ["fall"] * 8, seeds=SEEDS, design_index=1)
        self.assertEqual(before, self.weights(ep))
        self.assertFalse(out["leader_changed"])
        self.assertEqual(out["predicted_walking"], {"payload:t": 8, "sensor_bias:t": 8})
        # A predicted walking, B predicted falling; the plant falls: B gains
        ep = self.setup({}, {"A": [1] * 8, "B": [0] * 8})
        ep.assimilate_light({"body": {}, "vector": []}, ["fall"] * 8, seeds=SEEDS, design_index=1)
        w = self.weights(ep)
        self.assertGreater(w["B"], 0.99)
        self.assertIsNone(ep.assimilate_light({"body": {}, "vector": []}, ["fall"] * 8, seeds=SEEDS, design_index=1))  # once

    def test_misfit_excludes_repair_checks(self):
        ep = self.setup({"misfit_threshold": -100.0}, {"A": [1] * 8, "B": [1] * 8})
        s0 = ep.misfit_stat()
        ep.assimilate_light({"body": {}, "vector": []}, ["fall"] * 8, seeds=SEEDS, design_index=1)
        self.assertAlmostEqual(ep.misfit_stat(), s0)            # a failed repair is not evidence of an unmodelled cause

    def test_stop_map_v2(self):
        model = {"kind": "logistic_v2", "features": ["robust16", "stress4", "disp_pass", "disp_median_m"],
                 "n_by_feature": {"robust16": 16, "stress4": 4}, "w": [0.0, 1.0, 0.5, 1.0, 0.5]}
        ev = {"robust16": 16, "stress4": 4, "disp_pass": True, "disp_median_m": 1.0}
        self.assertGreater(be.mapped_p_full(model, ev), be.mapped_p_full(model, {**ev, "disp_pass": False}))
        self.assertIsNone(be.mapped_p_full(model, {"robust16": 16, "stress4": 4}))
        acc = be.calibrated_accept(model, 0.75)
        self.assertTrue(acc.needs_stress)


# ------------------------------------------------------------------------------------------------ displacement evidence
class Displacement(unittest.TestCase):
    def test_walk_score_rule(self):
        self.assertEqual(hev.walk_score({"ok": True, "fell": True, "fall_time": 0.5, "valid_steps": 3,
                                         "forward_disp_upright": 2.0}), 0.0)
        self.assertEqual(hev.walk_score({"ok": True, "fell": False, "valid_steps": 0, "forward_disp_upright": 2.0}), 0.0)
        self.assertEqual(hev.walk_score({"ok": True, "fell": False, "valid_steps": 4, "forward_disp_upright": 2.5}), 2.5)
        self.assertIsNone(hev.walk_score({"ok": False}))

    def test_verdict_statistics_on_robust_seeds(self):
        far = hev.displacement_evidence([0.5] * 16, [2.0] * 16, [False] * 16, [True] * 16)
        self.assertTrue(far["pass"])
        self.assertAlmostEqual(far["median_diff_m"], 1.5)
        same = hev.displacement_evidence([1.0] * 16, [1.1] * 16, [False] * 16, [True] * 16)
        self.assertFalse(same["pass"])                          # walking, but not clearly farther than the faulty robot


# ------------------------------------------------------------------------------------------------ R-head
def rows(n=300, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        k = rng.integers(len(rl.KINDS))
        kind_w = [0.0] * len(rl.KINDS)
        kind_w[k] = 1.0
        tool = rl.TOOLS[rng.integers(len(rl.TOOLS))]
        full = (tool == rl.TOOLS[k % len(rl.TOOLS)]) if rng.random() < 0.9 else bool(rng.random() < 0.5)
        out.append({"sit": {"kind_w": kind_w, "entropy": 0.1, "lead": 0.9}, "ev": [1, 0.5, 0.5, 0, 0, 1], "tool": tool,
                    "procedure": "engine_final", "full": full, "base": f"b{i % 5}", "iid": f"b{i % 5}:x:{i}"})
    return out


class RepairLearning(unittest.TestCase):
    def test_learns_situation_tool_interaction_and_roundtrip(self):
        m = rl.RHead.fit(rows(3000))
        sit = {"kind_w": [1.0] + [0.0] * (len(rl.KINDS) - 1), "entropy": 0.1, "lead": 0.9}
        ev = {t: [1, 0.5, 0.5, 0, 0, 1] for t in rl.TOOLS}
        p = {t: m.p(sit, ev, t) for t in rl.TOOLS}
        self.assertEqual(max(p, key=p.get), rl.TOOLS[0])
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "r.json")
            m.save(f)
            m2 = rl.RHead.load(f)
            self.assertAlmostEqual(m2.p(sit, ev, "timing"), m.p(sit, ev, "timing"))

    def test_baseline_feature_sets_exclude_situation(self):
        sit = {"kind_w": [1.0] + [0.0] * 9, "entropy": 0.0, "lead": 1.0}
        x_full = rl.featurize(sit, [0] * 6, "timing", "engine_final", "full")
        x_b1 = rl.featurize(sit, [0] * 6, "timing", "engine_final", "b1")
        self.assertEqual(len(x_b1), 1 + 6 + len(rl.PROCEDURES))
        self.assertEqual(len(x_full), 1 + len(rl.TOOLS) + 6 + len(rl.KINDS) * len(rl.TOOLS) + 2 + len(rl.PROCEDURES))

    def test_situation_ignores_unmodelled(self):
        s = rl.situation_features([([["unmodelled", "any"]], 0.5), ([["payload", "torso"]], 0.5)])
        self.assertAlmostEqual(s["kind_w"][rl.KINDS.index("payload")], 1.0)


# ------------------------------------------------------------------------------------------------ case store, dossiers
class Cases(unittest.TestCase):
    def test_store_retrieval_track_record_and_freeze(self):
        st = hc.CaseStore(rows(60), [{"deviated": True, "p_success": 0.8, "full": False},
                                     {"deviated": False, "p_success": 0.4, "full": True}], T=6.0)
        st.refit()
        sim = st.similar({"kind_w": [1.0] + [0.0] * 9, "entropy": 0.1, "lead": 0.9})
        self.assertAlmostEqual(sum(w for w, _ in sim), 1.0)
        lines = st.evidence_lines([([["segment_length", "feet"]], 1.0)], None, None, ["posture", "timing"])
        self.assertTrue(any("P(verified recovery)" in l for l in lines))
        tr = " ".join(st.track_record_lines())
        self.assertIn("overrode", tr)
        self.assertIn("Brier", tr)
        with self.assertRaises(RuntimeError):
            st.append_records([])
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "c.json")
            st.save(f)
            self.assertEqual(len(hc.CaseStore.load(f).cases), 60)

    def test_dual_status_separates_signals(self):
        # weak diagnosis but a helpful repair (Stage 2's retired right-side dossier) and the reverse
        a = hc.dual_status({"precision": 0.09, "matched": 30, "recommended_repair": [19, 24], "other_repairs": [23, 34]})
        self.assertEqual((a["diagnostic"], a["repair"]), ("weak", "helpful"))
        b = hc.dual_status({"precision": 0.9, "matched": 10, "recommended_repair": [3, 22], "other_repairs": [10, 32]})
        self.assertEqual((b["diagnostic"], b["repair"]), ("reliable", "harmful"))

    def test_agent_decision(self):
        rec = {"instance_id": "b:f:1", "arm": "A4x", "nemotron": {"x": 1}, "verification": {"status": "FULL_RECOVERY"},
               "agent": {"trace": [{"actor": "nemotron", "action": {"action": "delegate_repair", "tool_order": ["timing"],
                                                                    "p_success": 0.6}}]}}
        d = hc.agent_decision(rec)
        self.assertEqual((d["deviated"], d["p_success"], d["full"]), (True, 0.6, True))

    def test_stream_split_is_the_declared_one(self):
        split = json.load(open("experiments/causal_engineer/dev/hdb/stage2_split.json", encoding="utf-8"))
        self.assertEqual(hc.ds1_stream_bases(split), [
            "walkrec-dev-m1-gen-0001", "stilts-drawn", "tiny-feet", "walkrec-dev-m1-gen-0005", "hdb-v1-gen-0038",
            "hdb-v1-gen-0028", "hdb-v1-gen-0036", "hdb-v1-gen-0004", "hdb-v1-gen-0013", "hdb-v1-gen-0064"])
        self.assertFalse(set(hc.ds1_init_bases(split)) & set(hc.ds1_stream_bases(split)))
        self.assertFalse(set(hc.ds1_init_bases(split)) & set(split["transfer_bases"]))


# ------------------------------------------------------------------------------------------------ agent v5
from creature_forge.phasegait_fp import LOWER17, UPPER17          # noqa: E402

DESIGN = {"body": {"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.16, "foot_friction": 1.0,
                   "torque_limit": 60.0, "leg_density": 1000.0},
          "vector": [0.5 * (lo + hi) for lo, hi in zip(LOWER17, UPPER17)]}      # mid-range controller: within bounds


class _S:
    class b:
        designs = [{"index": 0, **DESIGN}, {"index": 1, **DESIGN}]

        @staticmethod
        def best_design():
            return {"index": 0, **DESIGN}
    memory = learned = None

    def __init__(self):
        self.evidence = {}

    def _candidate(self, spec):
        return ({"id": spec}, None)


def reply(action, **kw):
    return {"understanding": "u", "uncertainty": "q", "action": action, "why": "w", **kw}


class AgentV5(unittest.TestCase):
    def test_schema_and_p_success(self):
        v4 = ha.NemotronScientist(fixture=[], design=DESIGN)
        v5 = ha.NemotronScientist(fixture=[], design=DESIGN, v5=True)
        self.assertNotIn("p_success", v4.schema()["required"])
        self.assertIn("p_success", v5.schema()["required"])
        self.assertEqual(v4.system, ha.AGENT_SYSTEM)
        self.assertTrue(v5._validate(reply("delegate_repair"), _S())[0])             # missing p_success
        self.assertTrue(v5._validate(reply("delegate_repair", p_success=1.4), _S())[0])
        self.assertEqual(v5._validate(reply("delegate_repair", p_success=0.4), _S())[0], [])
        self.assertEqual(v4._validate(reply("delegate_repair"), _S())[0], [])

    def test_v5_prompt_names_no_benchmark_family(self):
        text = ha.AGENT_SYSTEM_V5.lower()
        for fam in ("pitch_sensor_bias", "payload_offset", "low_ground_friction", "short_feet", "feedback_gain_loss",
                    "actuator_weakness", "one_side_weakness", "clock_fault", "heavy_torso", "sensor_latency",
                    "joint_damping_wear", "leg_asymmetry", "symptom", "family"):
            self.assertNotIn(fam, text, fam)

    def test_constraint_feedback(self):
        hint = ha.level_hint("actuator_strength:all@x0.6", DESIGN)
        self.assertIn("hidden-deviation kind", hint)
        lv = ha.valid_levels(DESIGN)
        self.assertTrue(lv["freq"])
        bad = [x for x in ha.SCALE_LEVELS if x not in lv["torque_limit"]]
        if bad:
            self.assertIn("valid levels for torque_limit", ha.level_hint(f"torque_limit@{bad[0]}", DESIGN))


if __name__ == "__main__":
    unittest.main()
