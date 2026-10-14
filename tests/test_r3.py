import json
import unittest

import numpy as np

from creature_forge import r2, r3
from creature_forge.investigator import InvalidModelOutput
from creature_forge.nebius import Limits, NebiusClient, NebiusError


def seed_metrics(seed, walking, label=None, valid_steps=None):
    return {"seed": seed, "walking": walking, "fell": not walking, "label": label or ("walking" if walking else "fall"),
            "fall_time": None if walking else 1.5, "fall_pitch": -1.0, "valid_steps": valid_steps if valid_steps is not None else (30 if walking else 0),
            "backward_steps": 2, "touchdowns": 6, "speed_upright": 0.4 if walking else -0.4, "forward_disp_upright": 1.0, "max_abs_pitch": 0.3,
            "mean_pitch": -0.1, "min_torso_height": 0.5, "single_support_frac": 0.8, "mean_stance_s": 0.3, "mean_swing_s": 0.3,
            "raw_touchdown_rate": 2.0, "violations": [] if walking else ["fall"]}


THETA = r2.incumbent_theta()
PER_SEED = [seed_metrics(9000 + i, i % 3 != 0) for i in range(16)]
EVIDENCE = r3.build_evidence(THETA, PER_SEED)


def good(parameter="start_lean", delta=0.1, cites=("failing_seeds.0.fall_time", "controller.pitch_ref.u"), **kw):
    p = {"claim": "Backward lean at start prevents forward stepping.", "cited_evidence": list(cites),
         "edits": [{"parameter": parameter, "delta_u": delta}],
         "prediction": {"metric": "walking_seeds_screen", "direction": "increase", "min_gain_seeds": 2}, "confidence": 0.6}
    p.update(kw)
    return p


def client(replies, **limits):
    return NebiusClient(api_key="test-key", base_url="http://invalid.example", transport=r3.scripted_transport(replies),
                        limits=Limits(max_requests=limits.get("max_requests", 5), max_total_tokens=limits.get("tokens", 100000)))


class SchemaTests(unittest.TestCase):
    def test_valid_proposal_roundtrip(self):
        p = r3.parse_proposal(good(), EVIDENCE)
        self.assertEqual(p.edits, (("start_lean", 0.1),))
        self.assertEqual(r3.parse_proposal(p.as_dict(), EVIDENCE), p)

    def test_rejections(self):
        bad = {
            "unknown parameter": good(parameter="torso_mass"),
            "delta too large": good(delta=0.16),
            "zero delta": good(delta=0.0),
            "non-finite delta": good(delta=float("nan")),
            "bool delta": good(delta=True),
            "one citation only": good(cites=("controller.pitch_ref.u",)),
            "duplicate citations": good(cites=("controller.pitch_ref.u", "controller.pitch_ref.u")),
            "unresolvable citation": good(cites=("controller.pitch_ref.u", "failing_seeds.99.fall_time")),
            "citation to a container": good(cites=("controller.pitch_ref.u", "failing_seeds.0")),
            "bad confidence": good(confidence=1.5),
            "short claim": good(claim="short"),
            "extra field": good(extra=1),
        }
        for name, obj in bad.items():
            with self.subTest(name):
                with self.assertRaises(InvalidModelOutput):
                    r3.parse_proposal(obj, EVIDENCE)
        too_many = good()
        too_many["edits"] = [{"parameter": n, "delta_u": 0.05} for n in r3.PARAM_NAMES[:5]]
        dup = good()
        dup["edits"] = [{"parameter": "kp", "delta_u": 0.05}, {"parameter": "kp", "delta_u": -0.05}]
        badpred = good()
        badpred["prediction"] = {"metric": "fall_rate", "direction": "decrease", "min_gain_seeds": 2}
        gain0 = good()
        gain0["prediction"]["min_gain_seeds"] = 0
        for obj in (too_many, dup, badpred, gain0):
            with self.assertRaises(InvalidModelOutput):
                r3.parse_proposal(obj, EVIDENCE)

    def test_no_evidence_ablation_requires_empty_citations(self):
        r3.parse_proposal(good(cites=()), None)
        with self.assertRaises(InvalidModelOutput):
            r3.parse_proposal(good(), None)

    def test_response_envelope_and_per_proposal_validity(self):
        txt = json.dumps({"proposals": [good(), good(parameter="nope"), good(parameter="ramp_s", delta=-0.1)]})
        ok, bad = r3.parse_response(txt, EVIDENCE)
        self.assertEqual(len(ok), 2)
        self.assertEqual([b["slot"] for b in bad], [1])
        fenced = "```json\n" + json.dumps({"proposals": [good()]}) + "\n```"
        self.assertEqual(len(r3.parse_response(fenced, EVIDENCE)[0]), 1)
        for broken in (None, "", "not json", json.dumps({"proposals": []}), json.dumps({"proposals": [good()] * 5}),
                       json.dumps({"props": [good()]}), json.dumps([good()])):
            with self.assertRaises(InvalidModelOutput):
                r3.parse_response(broken, EVIDENCE)


class ApplicationTests(unittest.TestCase):
    def test_edits_apply_in_normalised_space_and_stay_in_bounds(self):
        v = np.asarray(r3.apply_edits(THETA, (("start_lean", 0.15), ("hip_amp", -0.15), ("kp", 0.1))))
        self.assertTrue(((v >= r3.LOWER15 - 1e-12) & (v <= r3.UPPER15 + 1e-12)).all())
        u0, u1 = r2.to_u(THETA), r2.to_u(v)
        i = r3.PARAM_NAMES.index("kp")
        self.assertAlmostEqual(u1[i] - u0[i], 0.1)
        j = r3.PARAM_NAMES.index("hip_amp")
        self.assertGreaterEqual(u1[j], 0.0)                           # reflected, not clipped below the bound
        untouched = [k for k in range(15) if r3.PARAM_NAMES[k] not in ("start_lean", "hip_amp", "kp")]
        np.testing.assert_array_equal(v[untouched], THETA[untouched])

    def test_matched_random_matches_size_and_magnitudes_not_content(self):
        model = (("start_lean", 0.12), ("ramp_s", -0.05), ("kp", 0.08))
        a = r3.matched_random_edits(model, [1, 0])
        self.assertEqual(r3.matched_random_edits(model, [1, 0]), a)             # reproducible
        self.assertNotEqual(r3.matched_random_edits(model, [1, 1]), a)
        self.assertEqual(len(a), 3)
        self.assertEqual(len({p for p, _ in a}), 3)
        self.assertEqual(sorted(abs(d) for _, d in a), sorted(abs(d) for _, d in model))
        self.assertTrue(all(p in r3.PARAM_NAMES for p, _ in a))

    def test_heuristic_fires_only_on_startup_failures_and_otherwise_abstains(self):
        self.assertEqual(len(r3.heuristic_proposals(EVIDENCE)), 4)
        late = r3.build_evidence(THETA, [seed_metrics(9000 + i, False, valid_steps=12) for i in range(8)])
        self.assertEqual(r3.heuristic_proposals(late), [])
        allwalk = r3.build_evidence(THETA, [seed_metrics(9000 + i, True) for i in range(8)])
        self.assertEqual(r3.heuristic_proposals(allwalk), [])


class EvidenceAndPromptTests(unittest.TestCase):
    def test_evidence_is_observed_facts_only_and_ordered_by_seed(self):
        ev = EVIDENCE
        self.assertEqual(ev["summary"]["n_seeds"], 16)
        self.assertEqual(ev["summary"]["walking_seeds"], sum(m["walking"] for m in PER_SEED))
        seeds = [f["seed"] for f in ev["failing_seeds"]]
        self.assertEqual(seeds, sorted(seeds))
        self.assertTrue(all(not f["label"] == "walking" for f in ev["failing_seeds"]))
        self.assertIn("initial_perturbation_rad", ev["failing_seeds"][0])
        self.assertEqual(len(ev["controller"]), 15)
        s = json.dumps(ev)
        for forbidden in ("api_key", "winner", "R2", "selection"):
            self.assertNotIn(forbidden, s)

    def test_prompts_are_stable_and_the_no_evidence_prompt_contains_no_measurements(self):
        m1, m2 = r3.build_messages(EVIDENCE), r3.build_messages(EVIDENCE)
        self.assertEqual(r3.prompt_sha256(m1), r3.prompt_sha256(m2))
        n = r3.build_messages(None)
        text = json.dumps(n)
        self.assertNotIn("failing_seeds.0", text)
        self.assertNotIn("fall_time\":", text)
        self.assertIn("NO measurements", text)
        self.assertNotEqual(r3.prompt_sha256(m1), r3.prompt_sha256(n))
        est = r3.estimate_tokens(m1, 2048, 30)
        self.assertEqual(est["requests"], 30)
        self.assertGreater(est["total_tokens_ceiling"], 30 * 2048)


class ModelFlowTests(unittest.TestCase):
    def test_valid_reply_yields_validated_proposals_and_redacted_metadata(self):
        c = client([json.dumps({"proposals": [good(), good(parameter="kp", delta=-0.05)]})])
        rec = r3.request_proposals(c, "M", 0, EVIDENCE)
        self.assertEqual(rec.status, "ok")
        self.assertEqual(len(rec.proposals), 2)
        self.assertNotIn("test-key", json.dumps(rec.as_dict()))
        self.assertNotIn("test-key", repr(c))
        self.assertEqual(c.requests_made, 1)

    def test_invalid_outputs_stay_invalid_and_nothing_is_repaired_or_retried(self):
        for reply in ("I think you should lean forward.", None, json.dumps({"proposals": [good(parameter="nope")]})):
            c = client([reply])
            rec = r3.request_proposals(c, "M", 0, EVIDENCE)
            self.assertEqual(c.requests_made, 1)
            if reply is None or reply.startswith("I think"):
                self.assertEqual(rec.status, "invalid_response")
                self.assertEqual(rec.proposals, [])
            else:
                self.assertEqual(rec.status, "ok")
                self.assertEqual(rec.proposals, [])
                self.assertEqual(len(rec.invalid_proposals), 1)

    def test_transport_error_and_budget_are_recorded_not_hidden(self):
        c = client([NebiusError("HTTP 500: boom")])
        rec = r3.request_proposals(c, "M", 0, EVIDENCE)
        self.assertEqual(rec.status, "model_error")
        self.assertEqual(c.requests_made, 1)
        c2 = client([json.dumps({"proposals": [good()]})] * 3, max_requests=1)
        r3.request_proposals(c2, "M", 0, EVIDENCE)
        rec2 = r3.request_proposals(c2, "M", 1, EVIDENCE)
        self.assertEqual(rec2.status, "budget_exceeded")
        self.assertEqual(c2.requests_made, 1)
        c3 = client([json.dumps({"proposals": [good()]})], tokens=500)
        self.assertEqual(r3.request_proposals(c3, "M", 0, EVIDENCE).status, "budget_exceeded")
        self.assertEqual(c3.requests_made, 0)

    def test_no_evidence_arm_end_to_end_with_scripted_model(self):
        c = client([json.dumps({"proposals": [good(cites=())]})])
        rec = r3.request_proposals(c, "N", 0, None)
        self.assertEqual(rec.status, "ok")
        self.assertEqual(len(rec.proposals), 1)
        c2 = client([json.dumps({"proposals": [good()]})])                    # cites evidence that was never provided -> invalid
        self.assertEqual(r3.request_proposals(c2, "N", 0, None).proposals, [])


class OutcomeTests(unittest.TestCase):
    def test_outcome_counts_only_measured_gain(self):
        self.assertEqual(r3.outcome(8, 11, 2), {"gain_seeds": 3, "improved": True, "prediction_met": True})
        self.assertEqual(r3.outcome(8, 9, 3), {"gain_seeds": 1, "improved": False, "prediction_met": False})
        self.assertEqual(r3.outcome(8, 8), {"gain_seeds": 0, "improved": False})


if __name__ == "__main__":
    unittest.main()
