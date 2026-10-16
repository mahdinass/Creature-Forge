"""Phase 1 offline tests: forensics, evaluation protocol, baselines, forensic investigator. No network."""
import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from creature_forge.controller import GaitParams
from creature_forge.evaluation import Protocol, classify, evaluate_design_protocol, wilson_interval
from creature_forge.experiment import PHASE0_BASELINE, PHASE0_DURATION, PHASE0_PUSH
from creature_forge.failures import detect_failures
from creature_forge.forensics import build_forensics, contact_transitions, support_margins
from creature_forge.investigator import (InvalidModelOutput, build_evidence, build_forensic_evidence, build_messages,
                                         investigate, parse_hypothesis, prompt_hash)
from creature_forge.morphology import BOUNDS
from creature_forge.nebius import Limits, NebiusClient
from creature_forge.proposers import classify_mechanism, heuristic_proposal, random_proposals
from creature_forge.simulate import run_rollout

BODY, GAIT = PHASE0_BASELINE, GaitParams()


class SupportMarginTests(unittest.TestCase):
    def test_margin_signs_on_synthetic_data(self):
        tel = {"support_x_min": np.array([0.0, 0.0, np.nan]), "support_x_max": np.array([0.2, 0.2, np.nan]),
               "com_pos": np.array([[0.1, 0, 0.5], [0.3, 0, 0.5], [0.1, 0, 0.5]]),
               "com_vel": np.array([[0.0, 0, 0], [0.0, 0, 0], [0.0, 0, 0]])}
        m = support_margins(tel)
        self.assertAlmostEqual(m["com"][0], 0.1)   # centred: 10 cm to either edge
        self.assertAlmostEqual(m["com"][1], -0.1)  # 10 cm beyond the front edge
        self.assertTrue(np.isnan(m["com"][2]))     # no foot loaded -> undefined, not zero

    def test_extrapolated_com_uses_velocity(self):
        tel = {"support_x_min": np.array([0.0]), "support_x_max": np.array([0.2]),
               "com_pos": np.array([[0.1, 0, 0.5]]), "com_vel": np.array([[1.0, 0, 0]])}
        shift = 1.0 * math.sqrt(0.5 / 9.81)
        self.assertAlmostEqual(support_margins(tel)["xcom"][0], 0.2 - (0.1 + shift), places=6)

    def test_contact_transitions(self):
        fc = np.array([[0, 0], [1, 1], [1, 1], [0, 1], [1, 1]], dtype=float)
        ev = contact_transitions(fc, np.arange(5) * 0.005)
        self.assertEqual([(e["foot"], e["event"]) for e in ev],
                         [("left", "touchdown"), ("right", "touchdown"), ("left", "liftoff"),
                          ("left", "touchdown")])


class ForensicsOnRealRollouts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tel8 = run_rollout(BODY, GAIT, seed=0, duration=PHASE0_DURATION, push=PHASE0_PUSH)
        cls.f8 = build_forensics(cls.tel8, BODY, PHASE0_PUSH, detect_failures(cls.tel8, BODY))
        b16 = BODY.replace(foot_length=0.16)
        cls.tel16 = run_rollout(b16, GAIT, seed=0, duration=PHASE0_DURATION, push=PHASE0_PUSH)
        cls.f16 = build_forensics(cls.tel16, b16, PHASE0_PUSH, detect_failures(cls.tel16, b16))

    def test_support_telemetry_matches_foot_geometry(self):
        # before the push both feet stand flat: support length ~ foot length (heel..toe contact corners)
        self.assertAlmostEqual(self.f8["support"]["support_length_before_push_m"], BODY.foot_length, delta=0.01)
        self.assertGreater(self.f16["support"]["support_length_before_push_m"], 0.15)

    def test_fall_summary_agrees_with_detector(self):
        events = detect_failures(self.tel8, BODY)
        fall = next(e for e in events if e.kind == "fall")
        self.assertTrue(self.f8["failure"]["fell"])
        self.assertAlmostEqual(self.f8["failure"]["fall_time_s"], fall.time, places=3)
        self.assertFalse(self.f16["failure"]["fell"])
        self.assertIsNone(self.f16["failure"]["fall_time_s"])

    def test_instability_follows_push_and_recovery_is_reported(self):
        self.assertGreaterEqual(self.f8["failure"]["instability_onset_s"], PHASE0_PUSH.time)
        self.assertIsNone(self.f8["failure"]["xcom_margin_recovered_s"])      # never recovers
        self.assertIsNotNone(self.f16["failure"]["xcom_margin_recovered_s"])  # recovers

    def test_summary_is_strict_json_and_compact(self):
        for f in (self.f8, self.f16):
            s = json.dumps(f, allow_nan=False)  # no NaN/Infinity leaks
            self.assertLess(len(s), 6000)

    def test_disturbance_numbers_are_measured(self):
        d = self.f8["disturbance"]
        self.assertAlmostEqual(d["impulse_Ns"], 25.0 * 0.15)
        self.assertGreater(d["com_vx_at_push_end_mps"], 0.1)
        self.assertGreater(d["peak_abs_pitch_within_1s_rad"], 1.0)

    def test_no_unmeasured_fields(self):
        # actuation numbers must equal values recomputed straight from telemetry
        t = self.tel8["t"]
        sel = (t >= PHASE0_PUSH.time) & (t <= self.f8["failure"]["fall_time_s"] + 1e-9)
        peak = np.abs(self.tel8["ctrl_demand"][sel][:, [2, 5]]).max()
        self.assertAlmostEqual(self.f8["actuation"]["ankle_peak_demand_Nm"], peak, delta=0.01)


class MechanismAndProposerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tel = run_rollout(BODY, GAIT, seed=0, duration=PHASE0_DURATION, push=PHASE0_PUSH)
        cls.f = build_forensics(tel, BODY, PHASE0_PUSH, detect_failures(tel, BODY))

    def test_mechanism_screen_on_real_failure(self):
        self.assertEqual(classify_mechanism(self.f), "tipping_support_margin")

    def test_mechanism_screen_abstains_without_failure_and_flags_others(self):
        import copy
        ok = copy.deepcopy(self.f)
        ok["failure"]["fell"] = False
        self.assertIsNone(classify_mechanism(ok))
        sat = copy.deepcopy(self.f)
        sat["actuation"]["fraction_samples_saturated_push_to_fall"] = 0.5
        self.assertEqual(classify_mechanism(sat), "actuator_saturation")
        slip = copy.deepcopy(self.f)
        slip["contacts"].update(fraction_samples_slipping_push_to_fall=0.5, peak_slip_speed_mps=0.6)
        self.assertEqual(classify_mechanism(slip), "foot_slip")

    def test_heuristic_is_a_bounded_single_change_not_the_known_answer(self):
        p = heuristic_proposal(self.f, BODY)
        self.assertEqual(p["parameter"], "foot_length")
        self.assertAlmostEqual(p["value"], 0.12)   # x1.5, NOT the known 16 cm solution
        self.assertNotAlmostEqual(p["value"], 0.16)

    def test_random_is_reproducible_bounded_and_uninformed(self):
        a, b = random_proposals(7, 200, BODY), random_proposals(7, 200, BODY)
        self.assertEqual(a, b)
        self.assertNotEqual(a, random_proposals(8, 200, BODY))
        for p in a:
            lo, hi = BOUNDS[p["parameter"]]
            self.assertTrue(lo <= p["value"] <= hi)
            self.assertNotEqual(p["value"], getattr(BODY, p["parameter"]))
        self.assertEqual({p["parameter"] for p in a}, set(BOUNDS))  # no parameter is favoured or excluded


class EvaluationTests(unittest.TestCase):
    def test_tier_rule(self):
        proto = Protocol(push_levels_N=(15.0, 25.0), heldout_seeds=(1, 2))

        def ev(f15, f25, surv25=2.0):
            return {"by_push": {"15.0": {"fall_rate": f15, "mean_survival_s": 5.0, "falls": 0, "n": 2},
                                "25.0": {"fall_rate": f25, "mean_survival_s": surv25, "falls": 0, "n": 2}}}
        base = ev(0.0, 1.0)
        self.assertEqual(classify(base, ev(0.0, 0.0, 5.0), proto)["tier"], "success")
        self.assertEqual(classify(base, ev(0.5, 0.0, 5.0), proto)["tier"], "partial")  # regresses at 15 N
        self.assertEqual(classify(base, ev(0.0, 1.0, 4.0), proto)["tier"], "none")     # survives longer, still falls
        self.assertEqual(classify(base, ev(0.0, 0.6, 3.0), proto)["tier"], "partial")  # 0.4 reduction only
        self.assertEqual(classify(base, ev(0.0, 0.9, 3.0), proto)["tier"], "none")

    def test_protocol_seeds_are_disjoint_from_evidence_and_screening_seeds(self):
        self.assertFalse(set(Protocol().heldout_seeds) & set(range(0, 100)))

    def test_known_answer_succeeds_and_baseline_not_better_than_itself(self):
        proto = Protocol(push_levels_N=(15.0, 25.0, 35.0), heldout_seeds=(200, 201))
        base = evaluate_design_protocol(BODY, GAIT, proto)
        cand = evaluate_design_protocol(BODY.replace(foot_length=0.16), GAIT, proto)
        self.assertEqual(base["simulations"], 6)
        self.assertEqual(classify(base, base, proto)["tier"], "none")
        self.assertEqual(classify(base, cand, proto)["falls_by_push"]["25.0"], [2, 0])
        # at 35 N both designs fall on every seed, so the candidate is not *worse* anywhere
        self.assertEqual(classify(base, cand, proto)["levels_where_candidate_worse"], [])

    def test_wilson(self):
        lo, hi = wilson_interval(0, 60)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.07)
        self.assertEqual(wilson_interval(0, 0), (0.0, 1.0))


def forensic_reply(**over):
    d = {"mechanism": "tipping_support_margin",
         "claim": "The centre of mass leaves the small support interval right after the push.",
         "cited_evidence": ["forensics.detailed.support.com_margin_before_push_m",
                            "forensics.detailed.failure.com_left_support_s"],
         "prediction": {"metric": "fall_rate", "direction": "decrease"}, "confidence": 0.6,
         "intervention": {"parameter": "foot_length", "value": 0.12}}
    d.update(over)
    return d


class Fake:
    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def __call__(self, url, headers, body, timeout):
        self.calls += 1
        self.body = body
        return 200, {}, {"model": "fake", "choices": [{"message": {"content": json.dumps(self.reply)},
                                                       "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 3000, "completion_tokens": 300, "total_tokens": 3300}}


class ForensicInvestigatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = build_forensic_evidence(BODY, GAIT, PHASE0_PUSH, seeds=(0, 1), duration=PHASE0_DURATION)

    def parse(self, r):
        return parse_hypothesis(json.dumps(r), self.ev, BODY, variant="forensic")

    def test_evidence_is_superset_and_does_not_leak_answer(self):
        self.assertIn("matched_seed_results", self.ev)
        self.assertEqual(len(self.ev["forensics"]["per_seed"]), 2)
        text = json.dumps(self.ev) + json.dumps(build_messages(self.ev, BODY, "forensic"))
        self.assertEqual(self.ev["body"]["foot_length"], 0.08)
        self.assertNotIn('"foot_length":0.16', text)  # the known good design never appears in the input
        for word in ("known solution", "recommended", "should be 16"):
            self.assertNotIn(word, text)

    def test_valid_forensic_reply(self):
        h = self.parse(forensic_reply())
        self.assertEqual(h.mechanism, "tipping_support_margin")

    def test_rejects_ungrounded_citations(self):
        only_agg = forensic_reply(cited_evidence=["matched_seed_results.fall_rate",
                                                  "matched_seed_results.mean_max_abs_pitch_rad"])
        one = forensic_reply(cited_evidence=["forensics.detailed.support.com_margin_before_push_m"])
        dup = forensic_reply(cited_evidence=["forensics.detailed.support.com_margin_before_push_m"] * 2)
        defs = forensic_reply(cited_evidence=["forensics.detailed.definitions.support",
                                              "forensics.detailed.definitions.com_margin_m"])
        section = forensic_reply(cited_evidence=["forensics.detailed.support", "forensics.detailed.failure"])
        for bad in (only_agg, one, dup, defs, section):
            with self.assertRaises(InvalidModelOutput):
                self.parse(bad)

    def test_rejects_missing_or_unknown_mechanism_and_nonexistent_path(self):
        with self.assertRaises(InvalidModelOutput):
            self.parse(forensic_reply(mechanism="vibes"))
        r = forensic_reply()
        del r["mechanism"]
        with self.assertRaises(InvalidModelOutput):
            self.parse(r)
        with self.assertRaises(InvalidModelOutput):
            self.parse(forensic_reply(cited_evidence=["forensics.detailed.support.nope",
                                                      "forensics.detailed.failure.fell"]))

    def test_legacy_variant_still_rejects_mechanism_field(self):
        with self.assertRaises(InvalidModelOutput):
            parse_hypothesis(json.dumps(forensic_reply()), self.ev, BODY)

    def test_prompt_hash_is_deterministic(self):
        m = build_messages(self.ev, BODY, "forensic")
        self.assertEqual(prompt_hash(m), prompt_hash(json.loads(json.dumps(m))))

    def test_end_to_end_with_fake_model_and_protocol(self):
        proto = Protocol(push_levels_N=(15.0, 25.0), heldout_seeds=(200, 201))
        fake = Fake(forensic_reply(intervention={"parameter": "foot_length", "value": 0.16}))
        client = NebiusClient(transport=fake, api_key="k", limits=Limits(max_requests=1, max_total_tokens=8000))
        with tempfile.TemporaryDirectory() as tmp:
            t = investigate(client, BODY, GAIT, PHASE0_PUSH, evidence_seeds=(0, 1), verify_seeds=(0, 1),
                            duration=PHASE0_DURATION, save_to=Path(tmp), variant="forensic",
                            temperature=0.7, protocol=proto, label="fake")
            self.assertEqual(fake.calls, 1)
            self.assertEqual(fake.body["temperature"], 0.7)
            self.assertEqual(t.status, "accepted")
            self.assertEqual(t.measured_outcome["protocol"]["verdict"]["tier"], "success")
            self.assertTrue(t.measured_outcome["protocol"]["prediction_held_heldout_primary"])
            self.assertEqual(t.measured_outcome["protocol"]["simulations"], 8)
            self.assertEqual(t.config["variant"], "forensic")
            self.assertEqual(len(t.config["prompt_sha256"]), 64)
            self.assertTrue((Path(tmp) / f"{t.trial_id}.json").exists())

    def test_protocol_rejection_is_recorded_not_hidden(self):
        proto = Protocol(push_levels_N=(15.0, 25.0), heldout_seeds=(200, 201))
        fake = Fake(forensic_reply(intervention={"parameter": "torso_mass", "value": 3.0}))
        client = NebiusClient(transport=fake, api_key="k", limits=Limits(max_requests=1, max_total_tokens=8000))
        t = investigate(client, BODY, GAIT, PHASE0_PUSH, evidence_seeds=(0,), verify_seeds=(0,),
                        duration=PHASE0_DURATION, save_to=None, variant="forensic", protocol=proto)
        self.assertEqual(t.status, "rejected_by_verifier")
        self.assertEqual(t.measured_outcome["protocol"]["verdict"]["tier"], "none")


if __name__ == "__main__":
    unittest.main()


REGISTERED_SHA256 = {  # pinned here too, so rewriting protocol.json alone cannot pass the integrity test
    "legacy": "77898ff0a6010058319b52e44ef17209a6ed7ba3e6ee58333320efa8caa21bac",
    "forensic": "fbcf1e8064b54857d1e69369d6bf04ae572bf18003b59a6561b7222a336467b5",
}


class RegistrationTests(unittest.TestCase):
    """A. Exact historical integrity. Platform independent: reads only the stored, frozen prompts."""

    def setUp(self):
        self.reg = json.loads(Path("experiments/phase1/protocol.json").read_text(encoding="utf-8"))

    def test_registered_limits_and_plan_are_unchanged(self):
        self.assertEqual(self.reg["live_limits"]["max_live_requests"], 3)
        self.assertEqual(self.reg["live_limits"]["max_total_tokens"], 18000)
        self.assertEqual(self.reg["live_limits"]["max_completion_tokens_per_request"], 4096)
        self.assertEqual(self.reg["live_limits"]["retries"], 0)
        self.assertEqual(len(self.reg["call_plan"]), 3)
        self.assertNotIn('"foot_length":0.16', json.dumps(self.reg["prompts"]))

    def test_frozen_prompts_hash_to_the_originally_registered_values(self):
        from creature_forge.reproducibility import verify_frozen_prompts
        res = verify_frozen_prompts(self.reg)
        self.assertEqual(set(res), set(REGISTERED_SHA256))
        for variant, (ok, registered, recomputed) in res.items():
            self.assertEqual(registered, REGISTERED_SHA256[variant], variant)
            self.assertTrue(ok, f"{variant}: stored messages hash to {recomputed}, registered {registered}")


class PhysicsReproducibilityTests(unittest.TestCase):
    """B. Does MuJoCo on this platform regenerate the registered evidence within the documented policy?

    Compares evidence, never hashes. Structural/categorical content must match exactly; only floats get the
    tolerance in creature_forge.reproducibility (RTOL/ATOL)."""

    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(Path("experiments/phase1/protocol.json").read_text(encoding="utf-8"))

    def _regen(self, variant):
        fn = build_forensic_evidence if variant == "forensic" else build_evidence
        return fn(BODY, GAIT, PHASE0_PUSH, seeds=(0, 1, 2), duration=PHASE0_DURATION)

    def test_regenerated_evidence_matches_registered_reference(self):
        from creature_forge.reproducibility import compare_evidence, format_report, reference_evidence
        for variant in ("legacy", "forensic"):
            cmp = compare_evidence(reference_evidence(self.reg, variant), self._regen(variant))
            print("\n" + format_report(cmp, variant))  # visible in CI logs
            self.assertTrue(cmp.ok, "\n".join(cmp.failures()))

    def test_scientific_conclusions_are_exactly_reproduced(self):
        from creature_forge.reproducibility import reference_evidence
        ref, new = reference_evidence(self.reg, "forensic"), self._regen("forensic")
        self.assertEqual(new["matched_seed_results"]["fall_rate"], ref["matched_seed_results"]["fall_rate"])
        rf, nf = ref["forensics"]["detailed"], new["forensics"]["detailed"]
        self.assertEqual(nf["failure"]["fell"], rf["failure"]["fell"])
        self.assertEqual(nf["contacts"]["transitions"], rf["contacts"]["transitions"])
        self.assertEqual([e.get("type", e.get("event")) for e in new["detailed_run"]["events"]],
                         [e.get("type", e.get("event")) for e in ref["detailed_run"]["events"]])
        self.assertEqual(new["forensics"]["per_seed"], ref["forensics"]["per_seed"])


class ProvenanceTests(unittest.TestCase):
    def test_registration_provenance_is_complete_and_hash_matches(self):
        from creature_forge.reproducibility import prompt_sha256, registration_provenance
        msgs = [{"role": "user", "content": "x"}]
        rec = registration_provenance(msgs, {"a": 1.0})
        self.assertEqual(rec["frozen_prompt"]["sha256"], prompt_sha256(msgs))
        self.assertEqual(rec["frozen_prompt"]["sha256"], prompt_hash(msgs))  # same as the historical scheme
        for k in ("python", "mujoco", "numpy", "platform", "machine"):
            self.assertIn(k, rec["generated_in"])
        self.assertIn("rtol", rec["evidence_tolerance"])


class CompareEvidencePolicyTests(unittest.TestCase):
    """The tolerance policy must not silently accept scientifically material divergence."""

    REF = {"seed": 0, "label": "fell", "fell": True, "t": 1.846, "v": 0.5, "rows": [[0.1, 2], [0.2, 3]],
           "events": ["contact_loss"]}

    def cmp(self, **chg):
        from copy import deepcopy
        from creature_forge.reproducibility import compare_evidence
        new = deepcopy(self.REF)
        new.update(chg)
        return compare_evidence(self.REF, new)

    def test_identical_and_ulp_level_differences_pass(self):
        self.assertTrue(self.cmp().ok)
        c = self.cmp(v=0.5 + 4e-14)
        self.assertTrue(c.ok)
        self.assertEqual(len(c.numeric), 1)  # reported, within tolerance

    def test_float_beyond_tolerance_fails_and_is_reported(self):
        c = self.cmp(v=0.5 + 1e-6)
        self.assertFalse(c.ok)
        self.assertIn("v:", c.failures()[0])

    def test_one_rounding_unit_flip_is_not_silently_accepted(self):
        c = self.cmp(t=1.847)
        self.assertFalse(c.ok)
        self.assertIn("rounding-boundary", c.failures()[0])

    def test_categorical_and_structural_changes_fail(self):
        for chg in ({"label": "recovered"}, {"fell": False}, {"seed": 1}, {"events": ["slip"]},
                    {"events": []}, {"rows": [[0.1, 2]]}, {"rows": [[0.1, 2], [0.2, 4]]}, {"extra": 1},
                    {"seed": 0.0}, {"fell": 1}):
            self.assertFalse(self.cmp(**chg).ok, chg)

    def test_missing_key_fails(self):
        from creature_forge.reproducibility import compare_evidence
        self.assertFalse(compare_evidence(self.REF, {k: v for k, v in self.REF.items() if k != "t"}).ok)


class TrialViewTests(unittest.TestCase):
    def test_view_reshapes_without_changing_numbers_and_serves_read_only(self):
        from fastapi.testclient import TestClient
        from creature_forge.studio.app import create_app
        from creature_forge.trial_view import trial_view
        proto = Protocol(push_levels_N=(15.0, 25.0), heldout_seeds=(200,))
        fake = Fake(forensic_reply(intervention={"parameter": "foot_length", "value": 0.16}))
        client = NebiusClient(transport=fake, api_key="k", limits=Limits(max_requests=1, max_total_tokens=8000))
        with tempfile.TemporaryDirectory() as tmp:
            t = investigate(client, BODY, GAIT, PHASE0_PUSH, evidence_seeds=(0,), verify_seeds=(0,),
                            duration=PHASE0_DURATION, save_to=Path(tmp), variant="forensic", protocol=proto,
                            label="view")
            v = trial_view(t.as_dict())
            self.assertEqual(v["design_change"]["original"], 0.08)
            self.assertEqual(v["design_change"]["modified"], 0.16)
            self.assertEqual(v["rationale"]["cited"][0]["value"],
                             t.observed_evidence["forensics"]["detailed"]["support"]["com_margin_before_push_m"])
            self.assertEqual(v["predicted_vs_measured"]["heldout_by_push"]["25.0"]["candidate"]["fall_rate"],
                             t.measured_outcome["protocol"]["candidate"]["by_push"]["25.0"]["fall_rate"])
            self.assertEqual(v["outcome"]["tier"], "success")
            c = TestClient(create_app(investigations_dir=Path(tmp)))
            self.assertEqual(c.get(f"/api/investigations/{t.trial_id}/view").json()["outcome"]["status"], "accepted")
            self.assertEqual(c.get("/api/investigations/nope/view").status_code, 404)

    def test_view_handles_legacy_trial(self):
        from creature_forge.trial_view import trial_view
        import glob
        files = glob.glob("artifacts/investigations/20261013T002054Z-aaad96.json")
        if not files:
            self.skipTest("first live trial artifact not present")
        v = trial_view(json.loads(Path(files[0]).read_text(encoding="utf-8")))
        self.assertIsNone(v["observed"]["forensic_highlights"])
        self.assertEqual(v["outcome"]["status"], "rejected_by_verifier")
