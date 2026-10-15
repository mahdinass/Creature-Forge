"""Step B tells the model, per probe, what MuJoCo measured and whether its expectation was confirmed or refuted (live run
i-c2c4c48729d3 showed the model proposing a mechanism its own probe had just refuted when only the raw numbers were given)."""
import json
import unittest
from pathlib import Path

from creature_forge.forge_ai import build_step_b_messages

FIX = Path(__file__).parent / "fixtures" / "forge_ai"


class StepBPromptTests(unittest.TestCase):
    def test_measured_probe_verdicts_and_method_rule_are_in_the_prompt(self):
        ev = json.loads((FIX / "challenge_push.json").read_text(encoding="utf-8"))
        evidence = {"challenge": {"kind": "push", "duration": 5.0}, "creature": {"mode": "experimental"}, "probes": {"resolution": 0.625}}
        hyps = [{"id": "H1", "mechanism": "slip", "status": "accepted"}, {"id": "H2", "mechanism": "torque", "status": "accepted"}]
        reqs = [{"probe_id": "friction_x2", "hypothesis": "H1", "expect": "increase"},
                {"probe_id": "torque_x1_5", "hypothesis": "H2", "expect": "increase"}]
        exps = [{"probe_id": "friction_x2", "observed": "decrease", "confirmed": False},
                {"probe_id": "torque_x1_5", "observed": "no_change", "confirmed": False}]
        msgs = build_step_b_messages(evidence, allowed={}, hypotheses=hyps, requests=reqs, expectations=exps)
        self.assertIn("MuJoCo measured: decrease -> REFUTED", msgs[1]["content"])
        self.assertIn("MuJoCo measured: no_change -> REFUTED", msgs[1]["content"])
        self.assertIn("a refuted expectation is evidence against that mechanism", msgs[0]["content"])
        self.assertTrue(ev)   # fixture present


if __name__ == "__main__":
    unittest.main()
