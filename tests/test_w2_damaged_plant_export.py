"""W2 damaged-plant exporter: plan and fail-closed gate with injected fakes. No physics, no model call."""
import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import w2_case_build as wcb  # noqa: E402
import w2_damaged_plant_export as wx  # noqa: E402


def _no_sim(*a, **k):
    raise AssertionError("the no-physics tests must not simulate")


def _rows(seeds, walking):
    return [{"seed": s, "outcome": "PASS" if w else "POOR", "score": 1.0 if w else 0.0, "walking": w, "fell": False,
             "label": "walking" if w else "slow", "fall_time": None, "forward_disp_upright": 1.0 if w else 0.1} for s, w in zip(seeds, walking)]


@mock.patch("creature_forge.hidden_plant.plant_rollout", _no_sim)
@mock.patch("creature_forge.recovery.run_walk_seeds", _no_sim)
class W2ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.recs = wcb.load_excerpt()
        cls.pl = wx.plan(cls.recs)

    def _inst(self):
        a3 = self.recs["A3"]
        return {"check": a3["check"], "robot": wx._design(a3, 0), "seeds": {"obs": self.pl["experiments"]["observe"]["seeds"]},
                "strength": a3["strength"], "plant": {}}

    def _fakes(self, *, bad_feature=False, bad_status=False, bad_trace=False):
        pl, recs = self.pl, self.recs
        by_hash = {v["design_hash"]: v["features"] for v in pl["experiments"].values()}

        def production(inst, design, seeds, pool):
            f = copy.deepcopy(by_hash[wcb.design_hash(design)])
            if bad_feature and wcb.design_hash(design) == pl["experiments"]["x1_nem"]["design_hash"]:
                f[seeds[0]]["step_freq_hz"] += 1e-12
            return f

        def traced_obs(inst, design, seeds, seed):
            return {}, by_hash[wcb.design_hash(design)][seed], {}, design["body"]

        val_seeds = list(range(100, 124))
        verifs = {}
        for name in ("a3_submitted", "a1e_submitted"):
            rec = pl["validation"][name]["recorded"]
            k = round(rec["walking_frac"] * 24)
            verifs[pl["validation"][name]["design_hash"]] = {
                "status": "NOT_RECOVERED" if bad_status and name == "a3_submitted" else rec["status"], "reasons": rec["reasons"],
                "validation": {"walking_frac": rec["walking_frac"], "original": _rows(val_seeds, [False] * 24),
                               "candidate": _rows(val_seeds, [True] * k + [False] * (24 - k))}}

        def verify(design):
            return verifs[wcb.design_hash(design)]

        def traced_val(inst, design, seeds, seed):
            h = wcb.design_hash(design)
            rows = verifs[h]["validation"]["candidate"] if h in verifs else verifs[next(iter(verifs))]["validation"]["original"]
            row = dict(next(r for r in rows if r["seed"] == seed))
            if bad_trace and seed == 100:
                row["score"] += 1e-9
            return {}, row, {}, design["body"]

        return dict(production_fn=production, verify_fn=verify, traced_obs_fn=traced_obs, traced_val_fn=traced_val,
                    frames_fn=lambda body, tr, states: {"fk_max_err_m": 0.0})

    def test_plan_reads_the_fork_from_the_record(self):
        e = self.pl["experiments"]
        self.assertEqual((e["x1_nem"]["id"], e["x1_eng"]["id"]), ("X1:cf:freq@x0.85", "X1:cf:freq@x1.2"))
        self.assertEqual(len(e["observe"]["seeds"]), 4)
        self.assertEqual(self.pl["validation"]["a3_submitted"]["recorded"]["status"], "FULL_RECOVERY")
        self.assertEqual(self.pl["validation"]["a1e_submitted"]["recorded"]["status"], "PARTIAL_IMPROVEMENT")
        self.assertLess(self.pl["rollout_equivalents"], 400)

    def test_counterfactual_designs_are_the_recorded_ones(self):
        d = wx.experiment_design(self.recs["A3"], 1)
        self.assertEqual(wcb.design_hash(d), wcb.design_hash(wx._design(self.recs["A3"], 1)))
        self.assertNotEqual(wcb.design_hash(d), wcb.design_hash(wx.experiment_design(self.recs["A1e"], 1)))

    def test_gate_passes_when_everything_reproduces(self):
        problems, payloads, _ = wx.replay(self.recs, self.pl, self._inst(), pool=None, **self._fakes())
        self.assertEqual(problems, [])
        self.assertEqual(len(payloads), 12 + 72)

    def test_one_feature_off_by_1e_12_blocks_the_export(self):
        problems, _, _ = wx.replay(self.recs, self.pl, self._inst(), pool=None, **self._fakes(bad_feature=True))
        self.assertTrue(any(p.startswith("production x1_nem") for p in problems), problems)

    def test_a_different_verification_status_blocks_the_export(self):
        problems, _, _ = wx.replay(self.recs, self.pl, self._inst(), pool=None, **self._fakes(bad_status=True))
        self.assertTrue(any(p.startswith("verification a3_submitted") for p in problems), problems)

    def test_a_trace_that_differs_from_its_production_row_blocks_the_export(self):
        problems, _, _ = wx.replay(self.recs, self.pl, self._inst(), pool=None, **self._fakes(bad_trace=True))
        self.assertTrue(any("seed 100" in p for p in problems), problems)

    def test_a_different_instance_is_refused(self):
        inst = self._inst()
        inst["check"] = {**inst["check"], "walking": 1}
        with self.assertRaises(wx.FidelityError):
            wx.replay(self.recs, self.pl, inst, pool=None, **self._fakes())

    def test_smoke_passes_and_fails_closed(self):
        f = self._fakes()
        kw = {k: f[k] for k in ("production_fn", "traced_obs_fn", "frames_fn")}
        self.assertTrue(wx.smoke(self.recs, self.pl, self._inst(), pool=None, **kw)["passed"])
        bad = self._fakes(bad_feature=True)
        res = wx.smoke(self.recs, self.pl, self._inst(), pool=None, **{k: bad[k] for k in ("production_fn", "traced_obs_fn", "frames_fn")})
        self.assertFalse(res["passed"])

    def test_experiment_fall_event_comes_from_the_record(self):
        feats = self.pl["experiments"]["x1_nem"]["features"]
        falls = [wx.fall_of(f) for f in feats.values()]
        self.assertEqual(sum(x["fell"] for x in falls), 1)
        self.assertAlmostEqual(next(x["fall_time"] for x in falls if x["fell"]), 1.726, places=3)

    def test_environment_gate(self):
        self.assertEqual(wx.environment_problems(dict(wx.RECORDED_ENV)), [])
        self.assertTrue(wx.environment_problems({**wx.RECORDED_ENV, "system": "Windows"}))

    def test_execute_refuses_without_approval(self):
        self.assertEqual(wx.main(["--execute"]), 2)


if __name__ == "__main__":
    unittest.main()
