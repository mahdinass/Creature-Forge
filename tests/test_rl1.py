"""RL-1 / E-2 (docs/RL1_PLAN.md): HF2 definitions are new, sealed modules stay isolated, the cohort builder is deterministic,
and the online runner's arms differ from A1 only by the tool order. No physics."""
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from creature_forge import hdb_bench as hb  # noqa: E402
from creature_forge import hdb_cohort2 as c2  # noqa: E402
from creature_forge import hdb_heldout as hh  # noqa: E402
from creature_forge import hdb_heldout2 as h2  # noqa: E402

BASE = {"base_id": "hdb-v2-gen-0001", "body": {"foot_length": 0.1}, "vector": [0.0] * 17}


def kind_targets(specs):
    out = set()
    for spec in specs.values():
        for v in spec["variants"].values():
            for p in v["make"](0.1, BASE):
                out.add((p["kind"], p["target"]))
    return out


class HF2DefinitionTests(unittest.TestCase):
    def test_hf2_primitives_are_new(self):
        dev = kind_targets({k: v for k, v in hb.FAMILY_SPECS.items() if k != "payload_offset"})
        e1 = kind_targets(hh.HELDOUT_FAMILY_SPECS)
        new = kind_targets(h2.HF2_FAMILY_SPECS)
        self.assertFalse(new & dev, new & dev)
        self.assertFalse(new & e1, new & e1)
        self.assertNotIn(("payload", "torso"), new)

    def test_cohort_candidates_and_instances(self):
        c1 = c2.candidates("one_side_slip", [BASE], 9)
        self.assertEqual(c1, c2.candidates("one_side_slip", [BASE], 9))
        self.assertEqual(len(c1), 2 * len(hb.MULTS))
        c = next(x for x in c1 if x["mult"] == 1.0)
        th = {c2.th_key(BASE["base_id"], "one_side_slip", c["variant"]): {"s_star": 1.0, "s_max": 3.9}}
        inst = c2.make_instance(BASE, c, th)
        self.assertTrue(inst["heldout"])
        self.assertEqual(inst["plant"]["deviation"][0]["kind"], "contact_friction")
        self.assertIn(inst["plant"]["deviation"][0]["target"], ("foot_l", "foot_r"))
        hb.assert_disjoint(inst["seeds"])
        self.assertIsNone(c2.make_instance(BASE, {**c, "mult": 1.7}, {c2.th_key(BASE["base_id"], "one_side_slip", c["variant"]): {"s_star": 3.0, "s_max": 3.9}}))


class IsolationTests(unittest.TestCase):
    def test_agent_facing_code_and_the_memory_never_import_sealed_or_cohort_modules(self):
        for mod in ("belief_engine", "scientist_has", "hdb_policies", "hdb_workbench", "has_agent", "has_memory", "repair_memory"):
            p = ROOT / "creature_forge" / f"{mod}.py"
            if p.exists():
                src = p.read_text(encoding="utf-8")
                for sealed in ("hdb_heldout", "hdb_heldout2", "hdb_cohort2", "hdb_testbench"):
                    self.assertNotIn(sealed, src, f"{mod} imports {sealed}")

    def test_runner_arms(self):
        run = importlib.import_module("rl1_run")
        self.assertEqual(run.ARMS, ("A1", "A1S", "A1M", "A1I"))
        rk = [{"tool": "timing"}, {"tool": "posture"}]
        self.assertIs(run.identity_ranker(None, None, rk), rk)
        self.assertIs(run.pick_model({"by_family": {"x": {"m": 1}}}, {"family": "x"})["m"], 1)


if __name__ == "__main__":
    unittest.main()
