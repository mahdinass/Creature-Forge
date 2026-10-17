import copy
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import ce_export_records as ex  # noqa: E402


def fake_episode(instance_id="tiny-feet:posture_lean:0.5", policy="scientist_think") -> dict:
    msg = "STEP 1 of at most 12.\nROBOT:\n  body parameters: foot_friction=1.0, foot_length=0.5\n  controller parameters: freq=1.0\n" + "x" * 500
    return {
        "version": "ce_eval_v1", "policy": policy, "instance_id": instance_id, "region": "r", "budget": 700, "n_train": 4, "n_obs": 4,
        "fault": "posture_lean", "severity": 0.5, "matching_tool": "posture", "error": None, "provenance": "LIVE",
        "verification": {"status": "FULL_RECOVERY", "walking_frac": 1.0, "reasons": [], "rollouts": {}},
        "diagnosis": {"category": "posture_bias", "injected_category": "posture_bias", "match": True, "confidence": 0.9},
        "ledger": {"total": 700, "used": 100, "remaining": 600, "lines": [], "designs": []},
        "llm": {"calls": 2, "cost_usd": 0.01, "latency_s": 3.0, "model": "m", "tokens": {"prompt": 1, "completion": 2}},
        "policy_record": {
            "version": "causal_scientist_v2", "model": "m", "prompt_version": "v2", "scientist_mode": "iterative", "max_steps": 12,
            "system_prompt": "SECRET-LOOKING SYSTEM PROMPT TEXT",
            "calls": [{"messages": [{"role": "user", "content": "FULLPROMPTBODY"}], "raw_response": {"a": 1}, "cost_usd": 0.005, "latency_s": 1.0,
                       "finish_reason": "stop", "schema_name": "scientist_step", "reasoning_present": False, "usage": {"prompt_tokens": 1}}] * 2,
            "steps": [{"step": 1, "action": "conclude", "calls": [0, 1], "user_message": msg, "parsed": {"result_reading": "text"},
                       "hypothesis_transitions": [], "status": "ok"}],
            "hypotheses": {}, "memory": {"items": [], "assessments": {}, "log": [], "error": None},
            "experiments": [{"id": "E1", "kind": "counterfactual", "predictions": [], "scoring": [],
                             "outcome": {"n_walking": 1, "n_walking_base": 0, "quantities": {"a": 1}, "bench_deltas": {"b": 2}}}],
            "final": {"diagnosis_category": "posture_bias"}, "prediction_summary": {"accuracy": 0.5},
            "submitted_design": {"body": {"foot_length": 0.5}, "vector": [0.0] * 17, "index": 1, "source": "repair:posture"},
            "initial_observation": {"n_walking": 0, "n_fell": 4, "median": {}},
        },
    }


BASE_BODY = {"foot_friction": 1.0, "foot_length": 0.5, "thigh_length": 0.3, "shank_length": 0.3, "torso_mass": 5.0, "torque_limit": 70.0}
FAKE_ROBOT = {"body": dict(BASE_BODY), "vector": [0.1] * 17}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self._orig = ex.initial_robot
        ex.initial_robot = lambda iid, bases: copy.deepcopy(FAKE_ROBOT)

    def tearDown(self):
        ex.initial_robot = self._orig

    def trim(self, ep=None, baselines=None):
        return ex.trim_record("C:/some/dir/results.jsonl", 7, ep or fake_episode(), [], baselines)

    def test_trimming_drops_prompts_and_keeps_hashes(self):
        ep = fake_episode()
        rec = self.trim(ep)
        text = json.dumps(rec)
        for gone in ("FULLPROMPTBODY", "raw_response", "SECRET-LOOKING", '"messages"', "bench_deltas", "quantities\": {"):
            self.assertNotIn(gone, text)
        st = rec["steps"][0]
        um = ep["policy_record"]["steps"][0]["user_message"]
        self.assertEqual(st["user_message"], {"sha256": ex.sha(um), "length": len(um)})
        self.assertEqual(rec["config"]["system_prompt"]["sha256"], ex.sha("SECRET-LOOKING SYSTEM PROMPT TEXT"))
        self.assertEqual(rec["experiments"][0]["outcome"], {"n_walking": 1, "n_walking_base": 0})
        self.assertEqual(rec["steps"][0]["parsed"]["result_reading"], "text")
        self.assertEqual(len(rec["steps"][0]["calls"]), 2)

    def test_provenance_has_basename_and_line_only(self):
        rec = self.trim()
        self.assertEqual(rec["source"]["file"], "results.jsonl")
        self.assertEqual(rec["source"]["line"], 7)
        self.assertNotIn("some/dir", json.dumps(rec))

    def test_ground_truth_is_separated(self):
        rec = self.trim()
        ev = rec["evaluation_only"]
        self.assertEqual((ev["fault"], ev["severity"], ev["matching_tool"], ev["diagnosis_match"]), ("posture_lean", 0.5, "posture", True))
        self.assertIn("never saw", ev["note"])
        rest = json.dumps({k: v for k, v in rec.items() if k != "evaluation_only"})
        self.assertNotIn("posture_lean", rest)
        self.assertNotIn("matching_tool", rest)

    def test_record_id_is_opaque_and_stable(self):
        rid = ex.record_id("tiny-feet:posture_lean:0.5", "scientist_think")
        self.assertRegex(rid, r"^c-[0-9a-f]{12}$")
        self.assertEqual(rid, ex.record_id("tiny-feet:posture_lean:0.5", "scientist_think"))
        self.assertNotEqual(rid, ex.record_id("tiny-feet:posture_lean:0.5", "scientist"))
        self.assertNotIn("tiny", rid)
        self.assertEqual(self.trim()["id"], rid)

    def test_prompt_robot_mismatch_is_refused(self):
        bad = fake_episode()
        bad["policy_record"]["steps"][0]["user_message"] = bad["policy_record"]["steps"][0]["user_message"].replace("foot_length=0.5", "foot_length=0.9")
        with self.assertRaises(ValueError):
            self.trim(bad)

    def test_secret_detection(self):
        for s in ("Authorization: Bearer abc", "key v1." + "A" * 45):
            with self.assertRaises(ValueError):
                ex.assert_no_secret(s)
        ex.assert_no_secret("v1.short and ordinary text")

    def test_export_refuses_a_secret_and_writes_nothing(self):
        ep = fake_episode()
        ep["policy_record"]["steps"][0]["parsed"]["result_reading"] = "token v1." + "B" * 50
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                ex.export([("f.jsonl", 1, ep)], [("f.jsonl", 1, ep)], [], d)
            self.assertEqual(os.listdir(d), [])

    def test_export_writes_files_index_and_baselines(self):
        ep = fake_episode()
        base = fake_episode(policy="expert")
        base["verification"] = {"status": "NOT_RECOVERED", "walking_frac": 0.1}
        base["rollouts_used"] = 650
        rows = [("f.jsonl", 1, base), ("f.jsonl", 2, ep)]
        with tempfile.TemporaryDirectory() as d:
            index = ex.export(rows, [rows[1]], [], d)
            self.assertEqual(sorted(os.listdir(d)), sorted(["index.json", index[0]["id"] + ".json"]))
            rec = json.loads(Path(d, index[0]["id"] + ".json").read_text(encoding="utf-8"))
            self.assertEqual(rec["no_ai_comparison"], [{"policy": "expert", "status": "NOT_RECOVERED", "walking_frac": 0.1,
                                                         "rollouts_used": 650, "error": None}])
            idx = json.loads(Path(d, "index.json").read_text(encoding="utf-8"))
            self.assertEqual(idx["records"][0]["status"], "FULL_RECOVERY")
            self.assertNotIn("tiny-feet", json.dumps(idx))

    def test_committed_samples_have_no_secrets_or_instance_ids(self):
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "experiments", "causal_engineer", "demo_records")
        for name in os.listdir(d):
            text = Path(d, name).read_text(encoding="utf-8")
            ex.assert_no_secret(text)
            self.assertIsNone(re.search(r"\b(tiny-feet|stilts-drawn|top-heavy|walkrec-dev)[\w-]*:[a-z_]+:\d", text), name)


if __name__ == "__main__":
    unittest.main()
