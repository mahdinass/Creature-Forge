"""Deterministic tests for the rev. 2.2 amendment, including the invariance lemmas on the EXACT P0 kNN functions.
    python -I test_p05_amend22.py <cf-experience worktree>   (worktree defaults to ../../../../.vscode/cf-experience path below)"""
import math
import os
import sys
import unittest

sys.modules["mujoco"] = None
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
WT = os.environ.get("CF_WORKTREE", os.path.abspath(os.path.join(HERE, *[os.pardir] * 5)))   # sanitised for publication: repo root from the archive
sys.path.insert(0, WT)
import numpy as np  # noqa: E402

import p05_amend22 as a  # noqa: E402
from creature_forge import experience_p0 as p0  # noqa: E402  (pure numpy)


class Combinatorics(unittest.TestCase):
    def test_against_enumeration(self):
        for m in (1, 2, 3, 4):
            for sch in ("uniform", "derangement"):
                ex, br = a.perm_stats(m, 5, sch), a.brute_perm_stats(m, sch)
                self.assertEqual(ex["per_group"], br["per_group"])
                self.assertAlmostEqual(ex["moved"], br["moved"])

    def test_m2_derangement_is_a_point_mass(self):
        r = a.perm_stats(2, 27, "derangement")
        self.assertEqual(r["distinct"], 1)            # every one of the 20 'permutations' is the same swap
        self.assertEqual(r["P_dup"], 1.0)

    def test_m1_cannot_be_altered(self):
        self.assertEqual(a.perm_stats(1, 27, "derangement")["per_group"], 0)

    def test_singleton_strata(self):
        self.assertAlmostEqual(a.p_all_singletons(2, 3), 2 / 3)
        self.assertAlmostEqual(a.p_all_singletons(3, 3), 6 / 27)
        self.assertEqual(a.frac_groups_alterable(3, 3, True), 0.0)   # adversarial: balanced severities -> identity control


class InvarianceLemmas(unittest.TestCase):
    """Lemmas 1-4 of the amendment, checked on experience_p0.Space / knn_rates exactly."""

    def setUp(self):
        rng = np.random.default_rng(11)
        self.G, self.m = 6, 2
        self.base = np.repeat(np.arange(self.G), self.m)
        n = self.G * self.m
        morph = rng.normal(size=(self.G, 3))[self.base]
        obs = rng.normal(size=(n, 4))
        cf = rng.normal(size=(n, 5))
        self.X = np.hstack([morph, obs, cf])
        self.blocks = {"morph": [0, 1, 2], "obs": [3, 4, 5, 6], "cf": list(range(7, 12))}
        self.Y = (rng.random((n, 10)) < 0.3).astype(float)
        self.tr = np.where(self.base != 0)[0]
        self.te = np.where(self.base == 0)[0]

    def _pred(self, X, Y, k, use=("obs", "morph", "cf")):
        sp = p0.Space(X, self.blocks)
        D = sp.dist(self.tr, self.te, use)
        return p0.knn_rates(D, Y[self.tr], k, Y[self.tr].mean(0)), D

    def _within_base_perm(self, rows_of):
        perm = np.arange(len(self.base))
        for b in range(1, self.G):
            idx = np.where(self.base == b)[0]
            perm[idx] = idx[::-1]                      # the only derangement for m = 2
        return perm

    def test_lemma1_prior_invariant(self):
        perm = self._within_base_perm(None)
        self.assertTrue(np.array_equal(self.Y[self.tr].mean(0), self.Y[perm][self.tr].mean(0)))

    def test_lemma2_whole_base_neighbour_sets_are_invariant(self):
        k = len(self.tr)                               # every training base fully inside every neighbour set
        P, _ = self._pred(self.X, self.Y, k)
        P2, _ = self._pred(self.X, self.Y[self._within_base_perm(None)], k)
        self.assertTrue(np.array_equal(P, P2))

    def test_lemma2_split_neighbour_set_can_change(self):
        P, _ = self._pred(self.X, self.Y, 1)
        P2, _ = self._pred(self.X, self.Y[self._within_base_perm(None)], 1)
        self.assertFalse(np.array_equal(P, P2))        # k = 1 splits bases; rows differ in this fixture

    def test_lemma3_standardisation_invariant_under_training_row_permutation(self):
        sp = p0.Space(self.X, self.blocks)
        perm = self._within_base_perm(None)
        sp2 = p0.Space(self.X[perm], self.blocks)
        D1 = sp.dist(self.tr, self.te, ("obs", "cf"))
        D2 = sp2.dist(self.tr, self.te, ("obs", "cf"))
        # same multiset of distances per query (columns permuted), because mean/sd over the training rows are unchanged
        self.assertTrue(np.allclose(np.sort(D1, 1), np.sort(D2, 1)))

    def test_lemma4_cf_swap_keeping_both_in_set_is_invariant(self):
        k = len(self.tr)
        Xs = self.X.copy()
        perm = self._within_base_perm(None)
        Xs[:, self.blocks["cf"]] = self.X[perm][:, self.blocks["cf"]]
        P, _ = self._pred(self.X, self.Y, k)
        P2, _ = self._pred(Xs, self.Y, k)
        self.assertTrue(np.array_equal(P, P2))

    def test_singleton_stratum_control_is_exact_identity(self):
        # strata of size 1: every within-stratum permutation is the identity, so the control equals the real run
        strata = np.arange(len(self.base))
        perm = np.arange(len(self.base))
        for s in np.unique(strata):
            idx = np.where(strata == s)[0]
            perm[idx] = idx[np.random.default_rng(int(s)).permutation(len(idx))]
        self.assertTrue(np.array_equal(perm, np.arange(len(self.base))))


class Options(unittest.TestCase):
    def test_compositions_and_losses(self):
        self.assertEqual(a.composition(("T1", "T3")), {"hdb-v1": 34})
        rB = a.option_row("P-B / T1-panel pilot (recommended default)")
        self.assertEqual((rB["G"], rB["lost"], rB["TV"]), (28, 6, 0.0))
        rB2 = a.option_row("P-B / T2 pilot")
        self.assertEqual((rB2["G"], rB2["lost"], rB2["TV"]), (34, 0, 1.0))
        rC = a.option_row("P-C / stratified pilot")
        self.assertEqual((rC["n_pop"], rC["G"]), (46, 40))

    def test_stage0b_cumulative(self):
        rows = a.stage0b_re(a.c.COST_SETS["mid"])
        self.assertEqual(sum(r[1] for r in rows), 182)
        self.assertAlmostEqual(rows[-1][3], sum(r[2] for r in rows))


if __name__ == "__main__":
    unittest.main()
