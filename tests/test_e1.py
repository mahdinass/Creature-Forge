"""E-1 (docs/E1_PROTOCOL.md): test-bench builder, sampler determinism, arm settings and the registered analysis. No physics."""
import hashlib
import importlib
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from creature_forge import hdb_bench as hb  # noqa: E402
from creature_forge import hdb_heldout as hh  # noqa: E402
from creature_forge import hdb_testbench as tb  # noqa: E402

an = importlib.import_module("e1_analysis")

BASES = [{"base_id": f"hdb-v1-gen-{i:04d}", "body": {"foot_length": 0.07}, "vector": [0.0] * 17} for i in range(30)]


def fake_physics(c: dict) -> dict:
    """Deterministic stand-in for evaluate_candidate: eligibility from a hash of the candidate id."""
    h = int(hashlib.sha256(tb.cand_id(c).encode()).hexdigest()[:8], 16)
    if h % 7 == 0:
        return {"instance": None}
    return {"instance": {"instance_id": tb.cand_id(c), "eligible": h % 3 != 0, "reason": "x", "base_id": c["base_id"]}}


def run_sampler(quotas, batch, shuffle_seed=None, per_base=2, per_stratum=1):
    ordered = {s: tb.candidates(s, BASES, 7) for s in quotas}
    smp = tb.Sampler(ordered, quotas, per_base=per_base, per_base_family=per_stratum)
    rng = random.Random(shuffle_seed)
    while not smp.done:
        need = smp.next_needed(batch)
        if not need:
            break
        if shuffle_seed is not None:
            rng.shuffle(need)
        for c in need:
            smp.feed(tb.cand_id(c), fake_physics(c))
    return smp


class SpecTests(unittest.TestCase):
    def test_union_of_specs_and_strata(self):
        self.assertEqual(set(tb.SPECS), set(hb.FAMILY_SPECS) | set(hh.HELDOUT_FAMILY_SPECS))
        st = tb.strata()
        self.assertEqual(sum(1 for v in st.values() if v["kind"] == "comp"), len(hh.COMPOSITIONS))
        for f in hh.HELDOUT_FAMILY_SPECS:
            self.assertTrue(st[f]["heldout"])
            for v in tb.SPECS[f]["variants"]:
                self.assertIsNotNone(tb.variant_max(BASES[0], f, v))
        self.assertFalse(st["clock_fault"]["heldout"])

    def test_candidate_order_is_seeded_and_complete(self):
        c1 = tb.candidates("leg_asymmetry", BASES, 7)
        self.assertEqual(c1, tb.candidates("leg_asymmetry", BASES, 7))
        self.assertNotEqual([tb.cand_id(c) for c in c1], [tb.cand_id(c) for c in tb.candidates("leg_asymmetry", BASES, 8)])
        self.assertEqual(len(c1), len(BASES) * 2 * len(hb.MULTS))
        comp = tb.comp_family(hh.COMPOSITIONS[1])
        cc = tb.candidates(comp, BASES, 7)
        self.assertEqual(len(cc), len(BASES) * len(hh.COMPOSITION_FRACTIONS))
        self.assertEqual(tb.needed_thresholds(cc[0]), [("low_ground_friction", ""), ("clock_fault", "fast")])


class InstanceTests(unittest.TestCase):
    def th(self, base, fam, var, s):
        return {tb.th_key(base["base_id"], fam, var): {"s_star": s, "s_max": tb.variant_max(base, fam, var)}}

    def test_single_heldout_instance(self):
        b = BASES[0]
        c = next(c for c in tb.candidates("sensor_latency", [b], 7) if c["mult"] == 1.3)
        inst = tb.make_instance(b, c, self.th(b, "sensor_latency", "", 0.05))
        self.assertTrue(inst["heldout"])
        self.assertEqual(inst["split"], "test")
        self.assertAlmostEqual(inst["strength"], 0.065)
        self.assertEqual(inst["plant"]["deviation"][0]["kind"], "sensor_delay")
        self.assertTrue(inst["plant"]["gap"])
        hb.assert_disjoint(inst["seeds"])
        self.assertIsNone(tb.make_instance(b, c, self.th(b, "sensor_latency", "", 0.14)))   # 1.3 x 0.14 > max 0.15
        self.assertIsNone(tb.make_instance(b, c, {tb.th_key(b["base_id"], "sensor_latency", ""): {"s_star": None, "s_max": 0.15}}))

    def test_composition_uses_fraction_of_each_threshold(self):
        b = BASES[1]
        comp = tb.comp_family(hh.COMPOSITIONS[1])
        c = next(c for c in tb.candidates(comp, [b], 7) if c["mult"] == 0.6)
        ths = {**self.th(b, "low_ground_friction", "", 1.0), **self.th(b, "clock_fault", "fast", 0.5)}
        inst = tb.make_instance(b, c, ths)
        kinds = {p["kind"]: p for p in inst["plant"]["deviation"]}
        self.assertAlmostEqual(kinds["contact_friction"]["params"]["factor"], round(2.718281828459045 ** -0.6, 6), places=6)
        self.assertAlmostEqual(kinds["clock_scale"]["params"]["factor"], round(2.718281828459045 ** 0.3, 6), places=6)
        self.assertTrue(inst["heldout"])
        self.assertEqual(inst["pair"], "HC")

    def test_instance_ids_unique_across_strata(self):
        ids = set()
        for s in tb.strata():
            for c in tb.candidates(s, BASES[:3], 7):
                key = hb.instance_key(c["base_id"], c["family"], c["severity"])
                self.assertNotIn(key, ids)
                ids.add(key)


class SamplerTests(unittest.TestCase):
    QUOTAS = {"sensor_latency": 6, "leg_asymmetry": 6, tb.comp_family(hh.COMPOSITIONS[0]): 5, "clock_fault": 4}

    def test_sample_independent_of_batching_and_feed_order(self):
        ref = run_sampler(self.QUOTAS, batch=1)
        for batch, seed in ((4, None), (16, 1), (64, 2), (3, 3)):
            other = run_sampler(self.QUOTAS, batch=batch, shuffle_seed=seed)
            self.assertEqual({s: [i["instance_id"] for i in v] for s, v in other.accepted.items()},
                             {s: [i["instance_id"] for i in v] for s, v in ref.accepted.items()})
            self.assertEqual(other.log, ref.log)

    def test_quotas_and_caps(self):
        smp = run_sampler(self.QUOTAS, batch=8)
        for s, q in self.QUOTAS.items():
            self.assertEqual(len(smp.accepted[s]), q)
            self.assertTrue(all(i["eligible"] for i in smp.accepted[s]))
        per_base = {}
        for s, v in smp.accepted.items():
            self.assertEqual(len({i["base_id"] for i in v}), len(v))          # <= 1 per base and stratum
            for i in v:
                per_base[i["base_id"]] = per_base.get(i["base_id"], 0) + 1
        self.assertLessEqual(max(per_base.values()), 2)

    def test_shortfall_when_candidates_run_out(self):
        smp = run_sampler({"sensor_latency": 1000}, batch=32)
        self.assertTrue(smp.done)
        self.assertLess(len(smp.accepted["sensor_latency"]), 1000)
        self.assertEqual(smp.summary()["sensor_latency"]["examined"], len(BASES) * 3)


class AnalysisTests(unittest.TestCase):
    def test_mcnemar_and_holm(self):
        c = an.mcnemar_one_sided([True] * 5 + [False] * 3, [False] * 5 + [False] * 3)
        self.assertEqual((c["a_only"], c["b_only"]), (5, 0))
        self.assertAlmostEqual(c["p_one_sided"], 1 / 32)
        self.assertAlmostEqual(an.binom_tail_ge(61, 75), sum(__import__("math").comb(75, i) for i in range(61, 76)) / 2 ** 75)
        self.assertEqual(an.holm({"a": 0.01, "b": 0.04}), {"a": True, "b": True})
        self.assertEqual(an.holm({"a": 0.03, "b": 0.04}), {"a": False, "b": False})

    def test_signflip_deterministic_and_sensible(self):
        d = {f"b{i}": [1, 0] for i in range(12)}
        r1, r2 = an.cluster_signflip(d, n=2000), an.cluster_signflip(d, n=2000)
        self.assertEqual(r1, r2)
        self.assertLess(r1["p_one_sided"], 0.01)
        self.assertGreater(an.cluster_signflip({f"b{i}": [1, -1] for i in range(12)}, n=2000)["p_one_sided"], 0.5)

    def test_analyse_itt_counts_missing_as_not_full(self):
        insts = [{"instance_id": f"i{k}", "base_id": f"b{k % 3}", "stratum": "s", "heldout": k % 2 == 0, "mult": 1.0}
                 for k in range(6)]
        ok = {"verification": {"status": "FULL_RECOVERY", "walking_frac": 1.0}}
        no = {"verification": {"status": "NOT_RECOVERED", "walking_frac": 0.0}}
        arms = {"A1": {f"i{k}": ok for k in range(5)}, "A0": {f"i{k}": no for k in range(6)},
                "K0n": {f"i{k}": (ok if k < 2 else no) for k in range(6)}}
        res = an.analyse(insts, arms)
        self.assertEqual(res["full"], {"A1": 5, "A0": 0, "K0n": 2})
        self.assertEqual(res["missing"]["A1"], ["i5"])
        self.assertEqual(res["contrasts"]["H-E1"]["a_only"], 5)
        self.assertTrue(res["primary"]["reject_null"])
        self.assertIn("H-E2", res["secondary_holm"])


class RunnerAndIsolationTests(unittest.TestCase):
    def test_engine_arms_require_the_frozen_stop_map(self):
        run = importlib.import_module("e1_run")
        with self.assertRaises(SystemExit):
            run.settings("A1", None)
        a = run.settings("K0n", "map.json")
        self.assertEqual((a.budget, a.twin_budget, a.tau, a.plant_repair, a.twin_repair), (700, 2800, 0.75, 300, 800))
        self.assertEqual(run.settings("A1", "m").arm, "A1")

    def test_agent_facing_code_never_imports_the_test_bench(self):
        for mod in ("belief_engine", "scientist_has", "hdb_policies", "hdb_workbench", "has_agent", "has_memory"):
            p = ROOT / "creature_forge" / f"{mod}.py"
            if p.exists():
                src = p.read_text(encoding="utf-8")
                self.assertNotIn("hdb_testbench", src, mod)
                self.assertNotIn("hdb_heldout", src, mod)

    def test_protocol_file_matches_the_code(self):
        p = ROOT / "experiments" / "e1" / "protocol.json"
        proto = json.loads(p.read_text(encoding="utf-8"))
        q = proto["sampling"]["quotas"]
        self.assertTrue(set(q) <= set(tb.strata()))
        self.assertEqual(sum(q.values()), proto["sampling"]["n_total"])
        self.assertEqual(proto["arms"], ["A0", "A1", "K0n"])


if __name__ == "__main__":
    unittest.main()
