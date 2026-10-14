import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from creature_forge import demo, r2, r3, r3v2
from creature_forge.nebius import Limits, NebiusClient, NebiusError
from creature_forge.optimize import Executor

THETA = r2.incumbent_theta()


def fake_job(job):
    d = float(np.linalg.norm(r2.to_u(job["vector"]) - r2.to_u(THETA)))
    per = []
    for s in job["seeds"]:
        base = (s % 3 != 0) and s != demo.FAILING_SEED
        walk = base or (0.05 < d < 0.3 and s % 2 == 0)
        per.append({"seed": s, "walking": bool(walk), "fell": not walk, "label": "walking" if walk else "fall", "fall_time": None if walk else 1.4,
                    "fall_pitch": -1.0, "valid_steps": 30 if walk else 0, "backward_steps": 1, "touchdowns": 5, "speed_upright": 0.4, "forward_disp_upright": 1.0,
                    "max_abs_pitch": 0.3, "mean_pitch": -0.1, "min_torso_height": 0.5, "single_support_frac": 0.8, "mean_stance_s": 0.3, "mean_swing_s": 0.3,
                    "raw_touchdown_rate": 2.0, "violations": [] if walk else ["fall"], "fitness": {"total": 1.0}})
    return {"ok": True, "result": {"per_seed": per}, "wall_s": 0.0, "peak_rss_mb": 50.0}


def good(parameter="pitch_ref", delta=0.1, cites=("controller.pitch_ref.u", "failing_seeds.0.valid_steps")):
    return {"claim": "A larger forward pitch reference may establish the first forward step.", "cited_evidence": list(cites),
            "edits": [{"parameter": parameter, "delta_u": delta}],
            "prediction": {"metric": "walking_seeds_screen", "direction": "increase", "min_gain_seeds": 2}, "confidence": 0.6}


def live_client(replies, usage=(1900, 3000), tokens=300_000):
    return NebiusClient(api_key="test-key", base_url="http://invalid.example", transport=r3.scripted_transport(replies, usage),
                        limits=Limits(max_requests=41, max_total_tokens=tokens, max_tokens_per_request=8000))


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        for target, val in ((demo, {"RECORDS_DIR": t / "rec", "LOCAL_RUNS_DIR": t / "loc", "MANIFEST": t / "rec" / "manifest.json", "DEMO_REQUESTS": t / "demo_requests.jsonl"}),
                            (r3v2, {"DEMO_REQUESTS": t / "demo_requests.jsonl"})):
            for k, v in val.items():
                p = mock.patch.object(target, k, v)
                p.start()
                self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.ex = Executor(1, fn=fake_job)

    def run_live(self, reply):
        return demo.run_investigation("live", self.ex, live_client([reply]))


class SeedsAndPromptTests(unittest.TestCase):
    def test_verification_seeds_are_disjoint_from_every_other_role(self):
        demo.check_demo_seeds()
        self.assertEqual(len(demo.VERIFY_SEEDS), 32)

    def test_demo_prompt_differs_from_the_r3_prompt_only_in_the_requested_item_count(self):
        self.assertEqual(demo.DEMO_SYSTEM_PROMPT.removesuffix(demo.PATH_NOTE).replace("exactly 2 items", "exactly 4 items"), r3.SYSTEM_PROMPT)

    def test_live_is_disabled_without_the_explicit_flag(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("CREATURE_FORGE_ENABLE_LIVE", None)
            self.assertFalse(demo.live_enabled())


class MockRunTests(Sandbox):
    def test_mock_run_is_labelled_scripted_and_never_looks_live(self):
        rec = demo.run_investigation("mock", self.ex)
        self.assertEqual(rec["provenance"]["kind"], "SCRIPTED_MOCK")
        self.assertIsNone(rec["provenance"]["model"])
        self.assertIsNone(rec["provenance"]["request_id"])
        self.assertIn("SCRIPTED MOCK", rec["provenance"]["note"])
        self.assertIsNone(rec["model_reply"]["call"])
        self.assertTrue(all("SCRIPTED MOCK" in iv["proposal"]["claim"] for iv in rec["interventions"]))
        with self.assertRaises(ValueError):
            demo.promote_to_recording(rec)                                  # mocks can never become 'recorded live'
        with self.assertRaises(ValueError):
            demo.record_live_request(rec)                                   # nor consume the live budget
        self.assertEqual(demo.demo_usage(), (0, 0))

    def test_every_valid_proposal_is_verified_with_a_matched_random_counterpart(self):
        rec = demo.run_investigation("mock", self.ex)
        self.assertEqual(len(rec["interventions"]), 2)
        ver = rec["verification"]
        self.assertEqual(ver["seeds"], list(demo.VERIFY_SEEDS))
        self.assertEqual(ver["rollouts"], 5 * 32)
        for iv in rec["interventions"]:
            k = f"slot{iv['slot']}"
            self.assertIn(k, ver["results"])
            self.assertIn(k + "_random", ver["results"])
            req = [abs(e["delta_u"]) for e in iv["proposal"]["edits"]]
            self.assertEqual(sorted(abs(e["delta_u"]) for e in iv["matched_random"]["edits"]), sorted(req))
            self.assertTrue(all("realised_delta_u" in r for r in iv["realised"]))
        base = ver["results"]["theta0"]["walking_count"]
        e = ver["results"]["slot0"]
        self.assertEqual(e["verdict"]["gain_seeds"], e["walking_count"] - base)


class VerdictTests(unittest.TestCase):
    def test_verdict_is_measured_only(self):
        self.assertEqual(demo.verdict_for(20, 23, 2), {"gain_seeds": 3, "kind": "improved", "prediction_met": True})
        self.assertEqual(demo.verdict_for(20, 21, 2)["kind"], "no_clear_change")
        self.assertFalse(demo.verdict_for(20, 21, 2)["prediction_met"])
        self.assertEqual(demo.verdict_for(20, 17, None)["kind"], "worse")


class LiveRunTests(Sandbox):
    def test_valid_live_reply_is_stored_as_received_and_verified(self):
        raw = json.dumps({"proposals": [good(), good("kp", -0.05)]})
        rec = self.run_live(raw)
        self.assertEqual(rec["provenance"]["kind"], "LIVE")
        self.assertEqual(rec["provenance"]["model"], "scripted-model")
        self.assertEqual(rec["model_reply"]["raw_reply"], raw)
        self.assertEqual(len(rec["interventions"]), 2)
        self.assertNotIn("test-key", json.dumps(rec))
        self.assertEqual(rec["model_reply"]["setting"], demo.SETTING)

    def test_unusable_live_replies_are_recorded_honestly_and_nothing_is_substituted(self):
        for text in (None, "I would lean forward.", json.dumps({"proposals": [good(parameter="torso_mass")]})):
            rec = self.run_live(text)
            self.assertEqual(rec["provenance"]["kind"], "LIVE")
            self.assertEqual(rec["interventions"], [])
            self.assertIsNone(rec["verification"])
            self.assertEqual(rec["model_reply"]["raw_reply"], text)
        rec = demo.run_investigation("live", self.ex, live_client([NebiusError("HTTP 500: boom")]))
        self.assertEqual(rec["model_reply"]["status"], "model_error")
        self.assertEqual(rec["interventions"], [])
        small = demo.run_investigation("live", self.ex, live_client(["x"], tokens=500))
        self.assertEqual(small["model_reply"]["status"], "budget_exceeded")

    def test_live_budget_is_shared_with_r3_caps(self):
        rec = self.run_live(json.dumps({"proposals": [good()]}))
        demo.record_live_request(rec)
        self.assertEqual(demo.demo_usage()[0], 1)
        u = r3v2.prior_usage()
        self.assertEqual(u["demo"]["requests"], 1)
        self.assertEqual(u["requests"], u["v1"]["requests"] + u["calibration"]["requests"] + u["experiment"]["requests"] + 1)


class RecordingTests(Sandbox):
    def test_promotion_relabels_a_real_live_run_keeps_the_original_hash_and_detects_tampering(self):
        live = self.run_live(json.dumps({"proposals": [good()]}))
        path = demo.promote_to_recording(live, "unit-test")
        rec = demo.load_run("unit-test")
        self.assertEqual(rec["provenance"]["kind"], "RECORDED_LIVE")
        self.assertEqual(rec["provenance"]["recorded_from"]["original_kind"], "LIVE")
        self.assertEqual(rec["provenance"]["recorded_from"]["original_sha256"], demo.record_sha256(live))
        self.assertIn("stored copy of a real Nebius", rec["provenance"]["note"])
        self.assertNotIn("made during this run", rec["provenance"]["note"])                # a recording must not claim to be live
        self.assertTrue(rec["integrity"]["verified"])
        rows = demo.list_runs()
        self.assertEqual([r["kind"] for r in rows], ["RECORDED_LIVE"])
        self.assertTrue(rows[0]["hash_verified"])
        path.write_text(path.read_text(encoding="utf-8").replace("0.6", "0.9"), encoding="utf-8")
        self.assertFalse(demo.load_run("unit-test")["integrity"]["verified"])

    def test_run_ids_cannot_escape_the_record_directories(self):
        for bad in ("../x", "a/b", "..", "", "a.b"):
            with self.assertRaises(KeyError):
                demo.load_run(bad)

    def test_replay_vectors_come_from_the_record(self):
        rec = self.run_live(json.dumps({"proposals": [good()]}))
        self.assertEqual(demo.replay_vector(rec, "baseline"), rec["controller"]["vector"])
        self.assertEqual(demo.replay_vector(rec, "slot0"), rec["interventions"][0]["vector"])
        self.assertEqual(demo.replay_vector(rec, "slot0_random"), rec["interventions"][0]["matched_random"]["vector"])
        with self.assertRaises(KeyError):
            demo.replay_vector(rec, "slot5")
        with self.assertRaises(ValueError):
            demo.build_replay(rec, "baseline", seed=3000)


if __name__ == "__main__":
    unittest.main()
