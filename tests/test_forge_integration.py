"""Cross-module contract test: a REAL MuJoCo challenge result (challenges) feeds the REAL evidence pack, reply schema,
prompt and validator (evidence, forge_ai, interventions), and an accepted edit produces a body MuJoCo can run.
No model call: the reply is written here from paths the schema actually enumerates."""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from creature_forge import challenges as ch
from creature_forge.creatures import CreatureStore
from creature_forge.evidence import build_evidence, pack_size, resolve
from creature_forge.forge_ai import build_messages, build_reply_schema, validate_reply
from creature_forge.interventions import apply_edits, editable_params, validate_edits

STUBBY = {"torso_mass": 6.0, "thigh_length": 0.30, "shank_length": 0.30, "foot_length": 0.05, "foot_friction": 1.0,
          "torque_limit": 60.0, "leg_density": 1000.0}


class ForgeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        store = CreatureStore(Path(cls.tmp.name))
        c = store.create(name="Stubby", body=STUBBY, mode="experimental", drawing={})
        cls.version = store.version(c["id"], 1)
        spec = ch.default_spec("push", [100501, 100502])
        res = ch.run_challenge(cls.version["body"], cls.version["controllers"], spec)
        cls.result = res if isinstance(res, dict) else dataclasses.asdict(res)
        cls.evidence = build_evidence(cls.version, cls.result)
        cls.allowed = editable_params(cls.version, "push")
        cls.schema = build_reply_schema(cls.evidence, cls.allowed)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def citable(self):
        hyp = self.schema["properties"]["diagnosis"]["properties"]["hypotheses"]["items"]["properties"]
        return hyp["evidence"]["items"]["enum"]

    def test_evidence_from_a_real_run_is_compact_and_every_enumerated_path_resolves(self):
        self.assertLessEqual(pack_size(self.evidence), 6 * 1024)
        paths = self.citable()
        self.assertGreater(len(paths), 10)
        for p in paths:
            resolve(self.evidence, p)      # raises if a schema-enumerated citation does not resolve to a value

    def test_prompt_contains_the_measured_evidence(self):
        msgs = build_messages(self.evidence, allowed=self.allowed)
        self.assertEqual([m["role"] for m in msgs], ["system", "user"])
        self.assertIn(self.citable()[0], msgs[1]["content"])

    def test_a_grounded_reply_is_accepted_and_its_edit_runs_in_mujoco(self):
        paths = [p for p in self.citable() if isinstance(resolve(self.evidence, p), (int, float))][:2]
        cur = self.version["controllers"]["stand"]["balance_gain"]
        reply = {"diagnosis": {"summary": "falls backward under push",
                               "hypotheses": [{"id": "H1", "mechanism": "support too short", "evidence": paths, "competing": []}]},
                 "proposals": [
                     {"id": "P1", "hypothesis": "H1", "category": "morphology",
                      "edits": [{"param": "foot_length", "op": "scale", "value": 1.3, "target": "both"}],
                      "retune_controller": False, "prediction": {"metric": "score", "direction": "increase", "expected_change": "+"},
                      "tradeoffs": "heavier feet", "confidence": 0.5, "verification": "push ladder"},
                     {"id": "P2", "hypothesis": "H1", "category": "control",
                      "edits": [{"param": "stand.balance_gain", "op": "set", "value": cur + 20.0, "target": "both"}],
                      "retune_controller": False, "prediction": {"metric": "score", "direction": "increase", "expected_change": "+"},
                      "tradeoffs": "stiffer", "confidence": 0.4, "verification": "push ladder"}]}
        out = validate_reply(reply, self.evidence, self.version, "push")
        status = {p["id"]: p["status"] for p in out["proposals"]}
        self.assertEqual(status, {"P1": "accepted", "P2": "accepted"}, out)
        edits, reasons = validate_edits(self.version, "push", reply["proposals"][0]["edits"])
        self.assertEqual(reasons, [])
        body, controllers = apply_edits(self.version, edits)
        self.assertAlmostEqual(body["foot_length"], 0.065, places=6)
        self.assertAlmostEqual(body["foot_length_r"], 0.065, places=6)
        r = ch.run_seed(body, controllers, ch.default_spec("push", [100503]), 100503)
        self.assertIn(r.outcome, ("PASS", "POOR", "FAIL"))

    def test_an_invented_citation_rejects_the_proposal_not_the_reply(self):
        reply = {"diagnosis": {"summary": "x", "hypotheses": [{"id": "H1", "mechanism": "m",
                                                               "evidence": ["forensics.made_up_value"], "competing": []}]},
                 "proposals": [{"id": "P1", "hypothesis": "H1", "category": "morphology",
                                "edits": [{"param": "foot_length", "op": "scale", "value": 1.3, "target": "both"}],
                                "retune_controller": False,
                                "prediction": {"metric": "score", "direction": "increase", "expected_change": "+"},
                                "tradeoffs": "t", "confidence": 0.5, "verification": "v"}]}
        out = validate_reply(reply, self.evidence, self.version, "push")
        self.assertTrue(all(p["status"] == "rejected" for p in out["proposals"]), out)


if __name__ == "__main__":
    unittest.main()
