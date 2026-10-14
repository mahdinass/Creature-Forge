import json
import unittest

from creature_forge import r2, r3, r3v2
from creature_forge.nebius import NebiusClient, Limits, NebiusError

THETA = r2.incumbent_theta()


def seed_metrics(seed, walking):
    return {"seed": seed, "walking": walking, "fell": not walking, "label": "walking" if walking else "fall", "fall_time": None if walking else 1.5,
            "fall_pitch": -1.0, "valid_steps": 30 if walking else 0, "backward_steps": 2, "touchdowns": 6, "speed_upright": 0.4, "forward_disp_upright": 1.0,
            "max_abs_pitch": 0.3, "mean_pitch": -0.1, "min_torso_height": 0.5, "single_support_frac": 0.8, "mean_stance_s": 0.3, "mean_swing_s": 0.3,
            "raw_touchdown_rate": 2.0, "violations": [] if walking else ["fall"]}


POOL = [seed_metrics(s, walking=(i % 3 == 0)) for i, s in enumerate(r3.PILOT_SEEDS)]
CAL = r3v2.build_calibration_context(THETA, POOL)


def good(parameter="start_lean", delta=0.1):
    return {"claim": "Backward lean at start prevents forward stepping.", "cited_evidence": ["controller.pitch_ref.u", "episode.duration_s"],
            "edits": [{"parameter": parameter, "delta_u": delta}],
            "prediction": {"metric": "walking_seeds_screen", "direction": "increase", "min_gain_seeds": 2}, "confidence": 0.6}


OK2 = json.dumps({"proposals": [good(), good("kp", -0.05)]})
OK1 = json.dumps({"proposals": [good()]})


class Capture:
    """Scripted transport that also records the request bodies actually sent."""
    def __init__(self, replies, usage=(900, 400), details=None):
        self.bodies, self.inner, self.details = [], r3.scripted_transport(replies, usage), details

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(body)
        status, hdr, raw = self.inner(url, headers, body, timeout)
        if self.details is not None:
            raw["usage"]["completion_tokens_details"] = {"reasoning_tokens": self.details}
        return status, hdr, raw


def client(replies, **kw):
    cap = Capture(replies, **kw)
    c = r3v2.make_client(api_key="test-key", base_url="http://invalid.example", transport=cap)
    c.cap = cap
    return c


class SettingsAndCapsTests(unittest.TestCase):
    def test_exactly_the_four_preregistered_settings_in_order(self):
        self.assertEqual([(s["name"], s["reasoning_effort"], s["max_tokens"]) for s in r3v2.SETTINGS],
                         [("A", "none", 3500), ("B", "low", 3500), ("C", "low", 5000), ("D", "medium", 5000)])
        self.assertEqual((r3v2.CAL_MAX_REQUESTS, r3v2.EXP_REQUESTS, r3v2.TOTAL_REQUESTS_CAP, r3v2.TOTAL_TOKENS_CAP), (8, 30, 41, 300_000))
        self.assertEqual(3 + r3v2.CAL_MAX_REQUESTS + r3v2.EXP_REQUESTS, r3v2.TOTAL_REQUESTS_CAP)

    def test_historical_v1_requests_count_toward_the_combined_caps(self):
        u = r3v2.prior_usage()
        self.assertEqual((u["v1"]["requests"], u["v1"]["tokens"]), (3, 13114))
        c = client([OK2])
        self.assertEqual((c.requests_made, c.tokens_used), (u["requests"], u["tokens"]))
        self.assertEqual((c.limits.max_requests, c.limits.max_total_tokens), (41, 300_000))

    def test_combined_request_cap_is_enforced_including_v1(self):
        already = r3v2.prior_usage()["requests"]                      # v1 + any calibration/experiment/demo requests recorded so far
        c = client([OK2] * 60)
        sent = 0
        for _ in range(60):
            r = r3v2.request_with_setting(c, "M", -1, CAL["M"]["context"], r3v2.SETTINGS[0])
            if r["status"] == "budget_exceeded":
                break
            sent += 1
        self.assertEqual(sent, 41 - already)                        # only what is left under the 41 combined cap can be sent

    def test_spend_bound_is_below_two_dollars_including_v1_tokens(self):
        s = r3v2.spend_bound()
        self.assertTrue(s["within_cap"])
        self.assertLess(s["total_bound_usd"], 2.0)


class CalibrationContextTests(unittest.TestCase):
    def test_context_uses_pilot_seeds_only_and_keeps_the_control_identical(self):
        self.assertFalse(CAL["stop"])
        self.assertTrue(all(s in r3.PILOT_SEEDS for s in CAL["seeds"]))
        self.assertEqual(len(CAL["seeds"]), 6)
        self.assertTrue(CAL["controller_block_identical"])
        self.assertEqual(set(CAL["M"]["context"]) - set(CAL["N"]["context"]), {"summary", "failing_seeds", "walking_seeds"})
        exp_seeds = set(r3.EVIDENCE_POOL_SEEDS) | set(r3.SCREEN_POOL_SEEDS) | set(r3.VALIDATION_SEEDS) | set(r2.FINAL_SEEDS)
        self.assertFalse(set(CAL["seeds"]) & exp_seeds)

    def test_insufficient_pool_stops_calibration(self):
        self.assertTrue(r3v2.build_calibration_context(THETA, [seed_metrics(s, True) for s in r3.PILOT_SEEDS])["stop"])
        self.assertTrue(r3v2.build_calibration_context(THETA, [seed_metrics(s, False) for s in r3.PILOT_SEEDS])["stop"])


class RequestTests(unittest.TestCase):
    def test_requested_settings_are_actually_sent_and_recorded(self):
        c = client([OK2], details=1234)
        rec = r3v2.request_with_setting(c, "M", -1, CAL["M"]["context"], r3v2.SETTINGS[1])
        body = c.cap.bodies[0]
        self.assertEqual((body["reasoning_effort"], body["max_tokens"], body["temperature"]), ("low", 3500, r3.TEMPERATURE))
        self.assertEqual(rec["generation"], {"reasoning_effort_requested": "low", "max_tokens_requested": 3500, "temperature": r3.TEMPERATURE,
                                             "setting": "B", "reasoning_tokens_reported": 1234})
        self.assertNotIn("test-key", json.dumps(rec))
        self.assertEqual(rec["prompt_sha256"], CAL["M"]["prompt_sha256"])

    def test_accepted_parameters_are_not_assumed_honoured_reasoning_tokens_recorded_when_present(self):
        c = client([OK2])
        rec = r3v2.request_with_setting(c, "N", -1, CAL["N"]["context"], r3v2.SETTINGS[0])
        self.assertIsNone(rec["generation"]["reasoning_tokens_reported"])           # not reported -> recorded as such, not invented


class CalibrationLogicTests(unittest.TestCase):
    def run_cal(self, replies):
        c = client(replies)
        sink = []
        out = r3v2.run_calibration(c, CAL, sink.append)
        return out, sink, c

    def test_first_passing_setting_is_chosen_and_later_ones_are_not_tested(self):
        out, sink, c = self.run_cal([OK2, OK2])
        self.assertEqual(out["chosen"]["name"], "A")
        self.assertEqual(out["requests_sent"], 2)
        self.assertEqual(out["not_tested"], ["B", "C", "D"])
        self.assertEqual([r["arm"] for r in sink], ["M", "N"])
        self.assertEqual(len(c.cap.bodies), 2)

    def test_skips_failing_settings_in_order_and_requires_both_arms_to_pass(self):
        # A: M null content, N ok -> fail; B: M ok, N only one valid proposal -> fail; C: both ok -> chosen
        out, sink, _ = self.run_cal([None, OK2, OK2, OK1, OK2, OK2])
        self.assertEqual(out["chosen"]["name"], "C")
        self.assertEqual(out["requests_sent"], 6)
        names = [r["setting"]["name"] for r in out["results"]]
        self.assertEqual(names, ["A", "B", "C"])
        self.assertFalse(out["results"][0]["passes"])
        self.assertFalse(out["results"][1]["passes"])
        self.assertEqual(out["results"][1]["checks"][1]["valid_proposals"], 1)
        self.assertEqual(out["not_tested"], ["D"])
        self.assertEqual([r["generation"]["setting"] for r in sink], ["A", "A", "B", "B", "C", "C"])

    def test_no_passing_setting_means_no_choice_and_at_most_eight_requests(self):
        out, sink, c = self.run_cal(["plain text"] * 8 + [OK2] * 4)
        self.assertIsNone(out["chosen"])
        self.assertEqual(out["requests_sent"], 8)
        self.assertEqual(len(c.cap.bodies), 8)
        self.assertEqual([r["setting"]["name"] for r in out["results"]], ["A", "B", "C", "D"])
        self.assertTrue(all(not r["passes"] for r in out["results"]))

    def test_transport_error_stops_calibration_without_retry(self):
        out, sink, c = self.run_cal([OK2, OK2][:0] + [NebiusError("HTTP 500: boom")])
        self.assertIsNone(out["chosen"])
        self.assertIn("model_error", out["stopped"])
        self.assertEqual(len(c.cap.bodies), 1)

    def test_pass_rule_ignores_proposal_quality_and_physics(self):
        silly = json.dumps({"proposals": [good("kp", 0.15), good("kd", -0.15)]})      # schema-valid, scientifically arbitrary: still passes
        out, _, _ = self.run_cal([silly, silly])
        self.assertEqual(out["chosen"]["name"], "A")
        import inspect
        self.assertNotIn("outcome", inspect.getsource(r3v2.setting_passes))
        self.assertNotIn("walking_count", inspect.getsource(r3v2.setting_passes))

    def test_invalid_envelope_and_truncated_replies_fail_with_reasons_recorded(self):
        recs = [r3v2.request_with_setting(client([x]), "M", -1, CAL["M"]["context"], r3v2.SETTINGS[0]) for x in (None, "```", json.dumps({"proposals": []}), OK2)]
        v = r3v2.setting_passes(recs[:2])
        self.assertFalse(v["passes"])
        self.assertTrue(all(c["failure_reasons"] for c in v["checks"]))
        self.assertFalse(r3v2.setting_passes([recs[2], recs[3]])["passes"])


class ProtocolV2Tests(unittest.TestCase):
    def test_protocol_self_consistent_with_required_content(self):
        p = r3v2.build_protocol_v2()
        self.assertEqual(p, json.loads(json.dumps(r3v2.build_protocol_v2())))
        self.assertEqual(p["limits"]["combined_requests_v1_and_v2"], 41)
        self.assertEqual(p["limits"]["combined_tokens_v1_and_v2"], 300_000)
        self.assertEqual(p["limits"]["physics_existing_rollouts_counted"], 340)
        self.assertEqual(p["limits"]["historical_v1_requests_included"], 3)
        self.assertLessEqual(p["physics_budget"]["planned_total_including_existing"], 6000)
        self.assertEqual([s["name"] for s in p["calibration"]["settings_in_order"]], ["A", "B", "C", "D"])
        self.assertIn("proposal quality", p["calibration"]["selection"])
        self.assertIn("not run", p["calibration"]["if_none_passes"])
        self.assertIn("NOT assumed to be honoured", " ".join(p["generation_diagnosis"]["consequences"]))
        self.assertIn("not rerun", p["experiment"]["carryover"].lower().replace("and not rerun", "not rerun"))

    def test_v1_protocol_is_unchanged_and_still_matches_its_code(self):
        stored = json.loads((r3.EXP_DIR / "protocol.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, json.loads(json.dumps(r3.build_protocol())))
        self.assertEqual(stored["id"], "phase2a-r3-protocol-v1")

    def test_preserved_v1_files_are_hashed(self):
        h = r3v2.v1_hashes()
        self.assertEqual(set(h), set(r3v2.V1_FILES))
        self.assertTrue(all(len(v) == 64 for v in h.values()))
        self.assertEqual(r3v2.build_protocol_v2()["supersedes"]["preserved_files_sha256_lf"], h)


if __name__ == "__main__":
    unittest.main()
