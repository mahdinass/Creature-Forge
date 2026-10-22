"""Experience-learning P0 audit (docs/plans/EXPERIENCE_LEARNING_PLAN.md rev. 2): leakage whitelist, comparability levels,
adequacy gates, decision-point legality, sealed/off-split exclusion, fold isolation, decision and coverage arithmetic, and a
MuJoCo tripwire (the audit must never simulate). No physics; synthetic records except the last, data-gated class."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import numpy as np

from creature_forge import experience_audit as ea
from creature_forge import experience_p0 as p0

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VM = os.path.join(ROOT, "..", "Creature-Forge", "artifacts", "vm")
SPLIT = {"experience_bases": ["stilts-drawn", "hdb-v1-gen-0004"], "transfer_bases": ["hdb-v1-gen-0070"]}
BODY = {"thigh_length": 0.22, "shank_length": 0.26, "foot_length": 0.11, "torso_mass": 5.7, "leg_density": 800.0,
        "foot_friction": 1.3, "torque_limit": 98.0, "thigh_length_r": 0.22, "shank_length_r": 0.26, "foot_length_r": 0.11,
        "pose": [0.0] * 7}


def _row(iid, tool, full, *, engine: str | None = "belief_engine_v6", procedure="engine", oracle=False, bench="hdb_v2", noise_seed=None,
         family="pitch_sensor_bias"):
    return {"bench": bench, "iid": iid, "base": ea.base_of(iid), "tool": tool, "full": full, "engine": engine,
            "procedure": procedure, "oracle": oracle, "noise_seed": noise_seed, "family": family}


def _episode(iid, arm, tool, status, *, bench="hdb_v2", eligible=None):
    rec = {"instance_id": iid, "arm": arm, "bench": bench, "family": iid.split(":")[1], "injected_structure": [["x", "y"]],
           "verification": {"status": status}, "submitted": 1,
           "designs": [{"index": 0, "source": "initial", "body": BODY, "vector": [0.0] * 17},
                       {"index": 1, "source": f"repair:{tool}", "body": BODY, "vector": [0.0] * 17}],
           "repair": {"design": 1, "log": [{"step": "plant", "tool": tool, "budget": 300, "design": 1}]},
           "engine": {"version": "belief_engine_v6", "settings": {"a": 1},
                      "experiments": [{"kind": "observe", "seeds": [1, 2], "features": {"1": {"walking": 0.0}, "2": {"walking": 1.0}}}],
                      "ledger": {"total": 700, "used": 600, "twin": {"used": 2000}}}}
    if eligible is not None:
        rec["eligible"] = eligible
    return rec


class WhitelistAndLegality(unittest.TestCase):
    def test_forbidden_names_raise(self):
        for bad in ("instance_id", "o:severity", "c:x:fault", "seed_3", "q:injected", "repair_matrix:feedback", "w:status"):
            with self.assertRaises(ValueError, msg=bad):
                ea.assert_whitelisted(["o:pitch_mean", bad])

    def test_dataset_feature_names_are_whitelisted(self):
        names = ([f"m:{k}" for k in ea.MORPH_KEYS] + [f"o:{k}" for k in p0.CE_OBS_KEYS + p0.IDENT_KEYS]
                 + [f"c:cf:{k}" for k in p0.CE_CF_KEYS] + [f"q:{i}" for i in range(9)] + ["w:mass_kg", "w:com_x_m"])
        ea.assert_whitelisted(names)

    def test_interventional_feature_only_after_its_experiment(self):
        self.assertTrue(ea.legal_at(decision_index=3, experiment_index=2))
        self.assertFalse(ea.legal_at(decision_index=2, experiment_index=2))
        self.assertFalse(ea.legal_at(decision_index=0, experiment_index=0))


class Comparability(unittest.TestCase):
    def test_levels(self):
        rows = [_row("hdb-v1-gen-0070:payload_offset:1", "leg_length", True),
                _row("hdb-v1-gen-0070:payload_offset:1", "placement", False, procedure="nemotron"),
                _row("hdb-v1-gen-0070:payload_offset:1", "timing", True, procedure="a0_generic", engine=None),
                _row("hdb-v1-gen-0070:payload_offset:1", "posture", True, procedure="mkv_oracle:K2", oracle=True)]
        c = ea.comparability(rows)[("hdb_v2", "hdb-v1-gen-0070:payload_offset:1")]
        self.assertEqual(set(c["P"]), {"leg_length", "placement"})          # same engine, policy-chosen
        self.assertEqual(set(c["X"]), {"leg_length", "placement", "timing"})  # oracle row never counted
        self.assertEqual(c["S"], {})
        self.assertTrue(ea.informative(c["P"]))

    def test_engine_versions_are_not_pooled_at_level_p(self):
        rows = [_row("a:f:1", "leg_length", True, engine="belief_engine_v5"),
                _row("a:f:1", "placement", False, engine="belief_engine_v6")]
        c = ea.comparability(rows)[("hdb_v2", "a:f:1")]
        self.assertEqual(len(c["P"]), 1)
        self.assertEqual(len(c["X"]), 2)

    def test_bench_versions_are_different_plants(self):
        rows = [_row("a:f:1", "leg_length", True, bench="hdb_v1"), _row("a:f:1", "placement", False, bench="hdb_v2")]
        comp = ea.comparability(rows)
        self.assertEqual(len(comp), 2)
        self.assertTrue(all(len(v["X"]) == 1 for v in comp.values()))

    def test_assigned_level_s_within_one_replicate(self):
        rows = [_row("a:f:1", "leg_length", False, procedure="ta1:control", noise_seed=7),
                _row("a:f:1", "foot_friction", False, procedure="ta1:treatment", noise_seed=7)]
        c = ea.comparability(rows)[("hdb_v2", "a:f:1")]
        self.assertEqual(set(c["S"]), {"leg_length", "foot_friction"})
        self.assertFalse(ea.informative(c["S"]))

    def test_support_counts_groups_not_rows(self):
        rows = [_row(f"b1:f:{i}", t, t == "x") for i in range(3) for t in ("x", "y")]
        rows += [_row("b2:g:0", "x", True), _row("b2:g:0", "y", False), _row("b2:g:0", "y", False)]
        s = ea.support(ea.comparability(rows), "P", rows)
        self.assertEqual(s["informative_instances"], 4)
        self.assertEqual(s["informative_bases"], 2)
        self.assertAlmostEqual(s["kish_neff_bases"], 16 / 10)


class Gates(unittest.TestCase):
    def test_d1_d2_thresholds(self):
        ok = {"informative_bases": 20, "informative_instances": 40, "families_on_ge2_bases": 3}
        self.assertEqual(ea.adequacy(ok, assigned=True, tier="FULL_VERIFIED"), {"D1": True, "D2": True, "assigned": True,
                                                                                "tier": "FULL_VERIFIED"})
        self.assertFalse(ea.adequacy(ok, assigned=True, tier="STANDARDIZED_DEV_PROXY")["D2"])   # proxy never gives a GO
        self.assertFalse(ea.adequacy(ok, assigned=False, tier="FULL_VERIFIED")["D1"])         # policy-chosen never qualifies
        low = {"informative_bases": 9, "informative_instances": 100, "families_on_ge2_bases": 5}
        self.assertFalse(ea.adequacy(low, assigned=True, tier="FULL_VERIFIED")["D1"])


class Groups(unittest.TestCase):
    def test_generator_groups(self):
        self.assertEqual(ea.generator_group("tiny-feet"), "hand")
        self.assertEqual(ea.generator_group("walkrec-dev-m1-gen-0003"), "walkrec-m1")
        self.assertEqual(ea.generator_group("hdb-v1-gen-0101"), "hdb-v1")

    def test_near_duplicates(self):
        m = {"a": dict.fromkeys(ea.MORPH_KEYS, 1.0), "b": dict.fromkeys(ea.MORPH_KEYS, 1.0001),
             "c": dict.fromkeys(ea.MORPH_KEYS, 5.0), "d": dict.fromkeys(ea.MORPH_KEYS, 9.0)}
        self.assertEqual(ea.near_duplicate_groups(m), [["a", "b"]])

    def test_morphology_needs_no_model(self):
        m = ea.morphology(BODY)
        self.assertAlmostEqual(m["L"], 0.48)
        self.assertEqual(m["leg_asym"], 0.0)


class InventoryOnSyntheticTree(unittest.TestCase):
    def test_off_split_records_are_dropped_and_excluded_files_never_registered(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "hdb", "artifacts", "hdb")
            os.makedirs(d)
            recs = [_episode("hdb-v1-gen-0070:payload_offset:1", "A1e6", "leg_length", "FULL_RECOVERY"),
                    _episode("hdb-v1-gen-0070:payload_offset:1", "A0", "timing", "NOT_RECOVERED"),
                    _episode("hdb-v1-gen-9999:payload_offset:1", "A1e6", "leg_length", "FULL_RECOVERY"),   # not a dev base
                    _episode("hdb-v1-gen-0004:short_feet:0", "A1e6", "foot_length", "FULL_RECOVERY", eligible=False)]
            with open(os.path.join(d, "s2T_A1e.jsonl"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(json.dumps(r) for r in recs) + "\n")
            with open(os.path.join(d, "walkers_all.jsonl"), "w", encoding="utf-8") as fh:
                fh.write("SEALED - must never be parsed\n")
            inv = ea.inventory({"vm": tmp, "repo": tmp}, SPLIT)
            self.assertEqual(inv["dropped_off_split"], {"hdb/artifacts/hdb/s2T_A1e.jsonl": 1})
            self.assertEqual(inv["outcome_rows"], 2)          # the ineligible plant is not an outcome
            self.assertNotIn("walkers_all.jsonl", json.dumps(inv["manifest"]))
            self.assertEqual(inv["support"]["X"]["informative_instances"], 1)
            self.assertEqual(inv["support"]["P"]["instances_ge2_tools"], 0)   # A0 is another procedure

    def test_registry_never_globs_excluded_files(self):
        for rel, *_ in ea.SOURCES:
            self.assertNotIn("walkers", rel)
            self.assertFalse(rel.startswith("cehb"))
            self.assertNotIn("heldout", rel)


class FoldIsolationAndArithmetic(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        n, self.T = 40, 3
        self.base = np.repeat(np.arange(8), 5).astype(str)
        X = rng.normal(size=(n, 4))
        self.Y = (rng.random((n, self.T)) < 0.4).astype(float)
        self.sp = p0.Space(X, {"a": [0, 1], "b": [2, 3]})

    def test_prior_and_k_come_from_training_folds(self):
        pr = p0.predict(self.sp, (), self.Y, self.base, self.base)
        for tr, te, _ in p0.folds(self.base):
            np.testing.assert_allclose(pr["prior"][te], np.tile(self.Y[tr].mean(0), (len(te), 1)))
        pr = p0.predict(self.sp, ("a",), self.Y, self.base, self.base)
        self.assertEqual(set(pr["k"]), set(self.base.tolist()))
        self.assertTrue(all(k in p0.K_GRID for k in pr["k"].values()))

    def test_test_rows_do_not_change_training_standardisation(self):
        X2 = self.sp.X.copy()
        X2[self.base == "0"] *= 1e6           # extreme test rows
        tr, te = np.where(self.base != "0")[0], np.where(self.base == "0")[0]
        D1 = self.sp.dist(tr, tr[:3], ("a", "b"))
        D2 = p0.Space(X2, self.sp.blocks).dist(tr, tr[:3], ("a", "b"))
        np.testing.assert_allclose(D1, D2)
        self.assertEqual(len(te), 5)

    def test_decision_and_coverage(self):
        Y = np.array([[1, 0], [0, 1], [0, 1], [1, 0]], float)
        pred = {"P": np.array([[0.9, 0.1], [0.2, 0.8], [0.9, 0.1], [0.1, 0.2]]), "prior": np.tile([0.6, 0.4], (4, 1)),
                "gate_sim": np.array([4.0, 3.0, 2.0, 1.0])}
        d = p0.decision_eval(pred, Y)
        np.testing.assert_array_equal(d["pick"], [0, 1, 0, 1])
        np.testing.assert_array_equal(d["v_pi0"], [1, 0, 0, 1])
        s = p0.summarize_decision(d)
        self.assertEqual((s["value_mem"], s["value_pi0"], s["p_plus"], s["p_minus"]), (0.5, 0.5, 0.25, 0.25))
        rc = {x["coverage"]: x for x in p0.risk_coverage(d, "gate_sim")}
        self.assertEqual(rc[1.0]["value"], 0.5)
        self.assertEqual(rc[0.5]["value"], 0.75)       # memory on the two most similar cases only
        self.assertEqual(rc[0.5]["negative_transfer"], 0.0)

    def test_cluster_bootstrap_resamples_groups(self):
        v = {"x": np.ones(10)}
        b = p0.cluster_bootstrap(v, np.repeat(["a", "b"], 5), lambda d: d["x"].mean(), n_boot=50)
        self.assertEqual(b["ci90"], [1.0, 1.0])
        self.assertEqual(b["n_groups"], 2)

    def test_shuffled_control_uses_the_real_k(self):
        real = p0.predict(self.sp, ("a", "b"), self.Y, self.base, self.base)
        sh = p0.predict(self.sp, ("a", "b"), self.Y, self.base, self.base, shuffle_rng=np.random.default_rng(1),
                        k_fixed=real["k"])
        self.assertEqual(real["k"], sh["k"])
        self.assertFalse(np.allclose(real["P"], sh["P"]))

    def test_hard_negative_control_runs(self):
        res = p0.hard_negative_separation(self.sp, self.Y, self.base, ("a",), {"ab": ("a", "b"), "a": ("a",)})
        self.assertIn("n_queries", res)


class NoSimulation(unittest.TestCase):
    """Tripwire: the audit and analysis code paths must never step, forward or compile a MuJoCo model."""

    def test_tripwire(self):
        try:
            import mujoco
        except ImportError:
            self.skipTest("mujoco not installed")
        boom = mock.Mock(side_effect=AssertionError("MuJoCo was called by the offline audit"))
        with mock.patch.object(mujoco, "mj_step", boom), mock.patch.object(mujoco, "mj_forward", boom), \
                mock.patch.object(mujoco.MjModel, "from_xml_string", boom), mock.patch.object(mujoco.MjModel, "from_xml_path", boom):
            Wh = FoldIsolationAndArithmetic("test_decision_and_coverage")
            Wh.setUp()
            Wh.test_decision_and_coverage()
            InventoryOnSyntheticTree("test_off_split_records_are_dropped_and_excluded_files_never_registered") \
                .test_off_split_records_are_dropped_and_excluded_files_never_registered()
            probe = [{"base_id": "stilts-drawn", "instance_id": "stilts-drawn:slippery:1.0", "robot": {"body": BODY},
                      "observation": {"median": {"time_upright": 2.0, "leg_length_m": 0.48}, "n_walking": 0},
                      "counterfactuals": {"cf1": {"observation": {"median": {"time_upright": 4.0}, "n_walking": 2}}},
                      "repair_matrix": {t: 0.0 for t in p0.CE_TOOLS} | {"foot_friction": 1.0}}]
            ds = p0.ce_dataset(probe, {"stilts-drawn": ea.morphology(BODY)})
            self.assertEqual(ds["Y"].sum(), 1.0)
            self.assertEqual(ds["missing_nominal_morph"], 0)
        boom.assert_not_called()


@unittest.skipUnless(os.path.isdir(os.path.join(VM, "hdb", "artifacts", "hdb")), "git-ignored development records absent")
class RecordedGates(unittest.TestCase):
    """The reported gate outcome, recomputed from the local records (skipped in CI, where the records are absent)."""

    def test_gates(self):
        split = json.load(open(os.path.join(ROOT, ea.SPLIT_FILE), encoding="utf-8"))
        old = os.getcwd()
        os.chdir(ROOT)
        try:
            inv = ea.inventory({"vm": os.path.abspath(VM), "repo": ROOT}, split)
        finally:
            os.chdir(old)
        g = inv["gates"]
        self.assertFalse(any(v["D1"] or v["D2"] for k, v in g.items() if k.startswith("HDB")))
        self.assertTrue(g["CE STANDARDIZED_DEV_PROXY (complete matrix)"]["D1"])
        self.assertFalse(g["CE STANDARDIZED_DEV_PROXY (complete matrix)"]["D2"])
        self.assertEqual(inv["dropped_off_split"], {})
        self.assertEqual(inv["x0_consistency"]["plants_inconsistent"], 0)


if __name__ == "__main__":
    unittest.main()
