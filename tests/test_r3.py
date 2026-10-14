import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from creature_forge import r1, r2, r3
from creature_forge.investigator import InvalidModelOutput
from creature_forge.nebius import Limits, NebiusClient, NebiusError
from creature_forge.optimize import Executor

THETA = r2.incumbent_theta()


def seed_metrics(seed, walking, valid_steps=None):
    return {"seed": seed, "walking": walking, "fell": not walking, "label": "walking" if walking else "fall",
            "fall_time": None if walking else 1.5, "fall_pitch": -1.0, "valid_steps": valid_steps if valid_steps is not None else (30 if walking else 0),
            "backward_steps": 2, "touchdowns": 6, "speed_upright": 0.4 if walking else -0.4, "forward_disp_upright": 1.0, "max_abs_pitch": 0.3,
            "mean_pitch": -0.1, "min_torso_height": 0.5, "single_support_frac": 0.8, "mean_stance_s": 0.3, "mean_swing_s": 0.3,
            "raw_touchdown_rate": 2.0, "violations": [] if walking else ["fall"]}


def synthetic_pool(n_fail_ok=True):
    # every 5th seed walks except a stretch: ~60% failing (>= 60 failing, >= 30 walking among 180)
    return [seed_metrics(s, walking=(i % 5 in (0, 1)) if n_fail_ok else False) for i, s in enumerate(r3.EVIDENCE_POOL_SEEDS)]


POOL = synthetic_pool()
CTXS = r3.build_contexts(THETA, POOL)
CTX = CTXS["contexts"][0]["M"]["context"]
CTX_N = CTXS["contexts"][0]["N"]["context"]


def good(parameter="start_lean", delta=0.1, cites=("controller.pitch_ref.u", "episode.duration_s"), **kw):
    p = {"claim": "Backward lean at start prevents forward stepping.", "cited_evidence": list(cites),
         "edits": [{"parameter": parameter, "delta_u": delta}],
         "prediction": {"metric": "walking_seeds_screen", "direction": "increase", "min_gain_seeds": 2}, "confidence": 0.6}
    p.update(kw)
    return p


def reply(*items):
    return json.dumps({"proposals": list(items)})


def client(replies, max_requests=30, tokens=130_000, usage=(900, 400)):
    return NebiusClient(api_key="test-key", base_url="http://invalid.example", transport=r3.scripted_transport(replies, usage),
                        limits=Limits(max_requests=max_requests, max_total_tokens=tokens, max_tokens_per_request=r3.MAX_TOKENS))


class SchemaTests(unittest.TestCase):
    def test_valid_roundtrip_and_same_schema_for_both_arms(self):
        p = r3.parse_proposal(good(), CTX)
        self.assertEqual(r3.parse_proposal(p.as_dict(), CTX), p)
        r3.parse_proposal(good(), CTX_N)                              # the control is held to the identical schema
        r3.parse_proposal(good(cites=("failing_seeds.0.fall_time", "controller.kp.u")), CTX)
        with self.assertRaises(InvalidModelOutput):                   # measurements do not exist in the control's context
            r3.parse_proposal(good(cites=("failing_seeds.0.fall_time", "controller.kp.u")), CTX_N)

    def test_rejections(self):
        bad = {"unknown parameter": good(parameter="torso_mass"), "delta too large": good(delta=0.16), "zero delta": good(delta=0.0),
               "non-finite delta": good(delta=float("nan")), "bool delta": good(delta=True),
               "one citation": good(cites=("controller.pitch_ref.u",)), "duplicate citations": good(cites=("controller.pitch_ref.u",) * 2),
               "unresolvable": good(cites=("controller.pitch_ref.u", "failing_seeds.99.fall_time")),
               "container": good(cites=("controller.pitch_ref.u", "controller.kp")), "bad confidence": good(confidence=1.5),
               "short claim": good(claim="short"), "extra field": good(extra=1)}
        for name, obj in bad.items():
            with self.subTest(name), self.assertRaises(InvalidModelOutput):
                r3.parse_proposal(obj, CTX)
        too_many = good()
        too_many["edits"] = [{"parameter": n, "delta_u": 0.05} for n in r3.PARAM_NAMES[:5]]
        dup = good()
        dup["edits"] = [{"parameter": "kp", "delta_u": 0.05}, {"parameter": "kp", "delta_u": -0.05}]
        badpred = good()
        badpred["prediction"] = {"metric": "fall_rate", "direction": "decrease", "min_gain_seeds": 2}
        for obj in (too_many, dup, badpred):
            with self.assertRaises(InvalidModelOutput):
                r3.parse_proposal(obj, CTX)

    def test_slots_always_have_four_entries_and_failures_are_not_repaired(self):
        slots, reasons, err = r3.parse_slots(reply(good(), good(parameter="nope"), good(parameter="ramp_s", delta=-0.1)), CTX)
        self.assertIsNone(err)
        self.assertEqual(len(slots), 4)
        self.assertIsNotNone(slots[0])
        self.assertIsNone(slots[1])
        self.assertIsNotNone(slots[2])
        self.assertIsNone(slots[3])
        self.assertEqual(reasons[3], "empty")                           # fewer than 4 items returned -> empty slot
        self.assertIn("unknown parameter", reasons[1])
        for broken in (None, "", "not json", reply(), json.dumps({"proposals": [good()] * 5}), json.dumps({"props": [good()]}), json.dumps([good()])):
            slots, reasons, err = r3.parse_slots(broken, CTX)
            self.assertIsNotNone(err)
            self.assertEqual(slots, [None] * 4)
        fenced = "```json\n" + reply(good()) + "\n```"
        self.assertIsNotNone(r3.parse_slots(fenced, CTX)[0][0])


class ControlIdentityTests(unittest.TestCase):
    def test_control_differs_from_treatment_only_by_measured_evidence(self):
        for c in CTXS["contexts"]:
            m, n = c["M"]["context"], c["N"]["context"]
            self.assertEqual(json.dumps(m["controller"], sort_keys=True), json.dumps(n["controller"], sort_keys=True))
            self.assertEqual(m["episode"], n["episode"])
            self.assertEqual(set(m) - set(n), {"summary", "failing_seeds", "walking_seeds"})
            self.assertEqual(set(n), {"controller", "episode"})
        self.assertEqual(len(CTX["controller"]), 15)
        for name, row in CTX_N["controller"].items():
            self.assertEqual(set(row), {"value", "lower", "upper", "u", "meaning"}, name)
        mm, nn = r3.build_messages(CTX), r3.build_messages(CTX_N)
        self.assertEqual(mm[0], nn[0])                                  # identical system prompt
        self.assertNotIn("fall_time", nn[1]["content"])
        self.assertNotIn("failing_seeds", nn[1]["content"])
        self.assertNotEqual(r3.prompt_sha256(mm), r3.prompt_sha256(nn))


class ContextTests(unittest.TestCase):
    def test_fifteen_deterministic_disjoint_contexts_from_pool_outcomes_only(self):
        self.assertFalse(CTXS["stop"])
        self.assertEqual(len(CTXS["contexts"]), 15)
        again = r3.build_contexts(THETA, list(reversed(POOL)))
        self.assertEqual(json.dumps(CTXS, sort_keys=True), json.dumps(again, sort_keys=True))     # input order irrelevant
        allseeds = [s for c in CTXS["contexts"] for s in c["seeds"]]
        self.assertEqual(len(allseeds), 15 * 6)
        self.assertEqual(len(set(allseeds)), len(allseeds))
        by = {m["seed"]: m for m in POOL}
        for c in CTXS["contexts"]:
            self.assertEqual(sum(not by[s]["walking"] for s in c["seeds"]), 4)
            self.assertEqual(sum(bool(by[s]["walking"]) for s in c["seeds"]), 2)
            self.assertEqual(c["seeds"], sorted(c["seeds"]))
            self.assertEqual(len(c["M"]["context"]["failing_seeds"]), 4)
            self.assertEqual(len(c["M"]["prompt_sha256"]), 64)
        self.assertTrue(all(s in r3.EVIDENCE_POOL_SEEDS for s in allseeds))

    def test_insufficient_pool_is_a_registered_stop(self):
        few = [seed_metrics(s, walking=(i % 2 == 0)) for i, s in enumerate(r3.EVIDENCE_POOL_SEEDS[:100])]
        out = r3.build_contexts(THETA, few)
        self.assertTrue(out["stop"])
        self.assertEqual(out["contexts"], [])
        self.assertTrue(r3.build_contexts(THETA, synthetic_pool(False))["stop"])

    def test_screening_seeds_rule_and_stop(self):
        pool = [seed_metrics(s, walking=(i % 3 != 0)) for i, s in enumerate(r3.SCREEN_POOL_SEEDS)]
        sel = r3.select_screening_seeds(pool[::-1])
        self.assertFalse(sel["stop"])
        self.assertEqual(len(sel["seeds"]), 16)
        by = {m["seed"]: m for m in pool}
        self.assertEqual(sum(bool(by[s]["walking"]) for s in sel["seeds"]), 8)
        self.assertTrue(r3.select_screening_seeds([seed_metrics(s, True) for s in r3.SCREEN_POOL_SEEDS])["stop"])

    def test_token_ceiling_of_the_frozen_prompts_fits_the_approved_cap(self):
        msgs = [r3.build_messages(c[a]["context"]) for c in CTXS["contexts"] for a in r3.ARMS_MODEL]
        est = r3.estimate_tokens(msgs)
        self.assertEqual(est["requests"], 30)
        self.assertLessEqual(est["total_tokens_ceiling"], r3.MAX_TOTAL_TOKENS)


class MatchedRandomTests(unittest.TestCase):
    def test_streams_are_fixed_in_advance_and_independent_of_model_output(self):
        a = r3.random_stream("M", 3, 2)
        self.assertEqual(a, r3.random_stream("M", 3, 2))
        self.assertNotEqual(a, r3.random_stream("N", 3, 2))
        self.assertNotEqual(a, r3.random_stream("M", 3, 3))
        e1 = r3.matched_random_edits("M", 3, 2, [0.1, 0.05])
        e2 = r3.matched_random_edits("M", 3, 2, [0.12, 0.02, 0.08])
        self.assertEqual([p for p, _ in e1], [p for p, _ in e2][:2])                      # parameters do not depend on the magnitudes
        self.assertEqual([np.sign(d) for _, d in e1], [np.sign(d) for _, d in e2][:2])    # nor do the signs
        self.assertEqual(sorted(abs(d) for _, d in e1), [0.05, 0.1])

    def test_every_slot_has_a_counterpart_including_invalid_ones_with_fallback(self):
        recs = []
        for arm in r3.ARMS_MODEL:
            for b in range(r3.BLOCKS):
                if (arm, b) == ("M", 0):
                    slots = [{"proposal": r3.parse_proposal(good(), CTX).as_dict(), "reason": None}] + [{"proposal": None, "reason": "empty"}] * 3
                    recs.append({"arm": arm, "block": b, "status": "ok", "slots": slots})
                elif (arm, b) == ("N", 1):
                    recs.append({"arm": arm, "block": b, "status": "invalid_response", "slots": [{"proposal": None, "reason": "bad"}] * 4})
                else:
                    slots = [{"proposal": r3.parse_proposal(good(parameter=r3.PARAM_NAMES[s], delta=0.05 + 0.01 * s), CTX).as_dict(), "reason": None} for s in range(4)]
                    recs.append({"arm": arm, "block": b, "status": "ok", "slots": slots})
        out = r3.build_candidates(THETA, recs, [])
        ids = {c["id"] for c in out["candidates"]}
        for arm in ("RM", "RN"):
            for b in range(15):
                for s in range(4):
                    self.assertIn(f"{arm}-{b}-{s}", ids)
        self.assertNotIn("M-0-1", ids)                                  # empty model slot: no candidate (failure), counterpart still exists
        self.assertIn("RM-0-1", ids)
        fb = next(c for c in out["candidates"] if c["id"] == "RM-0-1")
        self.assertEqual(sorted(abs(e["delta_u"]) for e in fb["edits"]), sorted(r3.FALLBACK_EDIT_MAGNITUDES))
        self.assertFalse(fb["model_slot_valid"])
        valid = next(c for c in out["candidates"] if c["id"] == "RM-0-0")
        self.assertEqual([abs(e["delta_u"]) for e in valid["edits"]], [0.1])
        self.assertEqual(sum(1 for c in out["candidates"] if c["arm"] == "RN"), 60)
        self.assertEqual(out, r3.build_candidates(THETA, recs, []))        # deterministic: freezing is meaningful
        for c in out["candidates"]:
            v = np.asarray(c["vector"])
            self.assertTrue(((v >= r3.LOWER15 - 1e-12) & (v <= r3.UPPER15 + 1e-12)).all())

    def test_requested_and_realised_magnitudes_are_recorded_and_audited(self):
        e = (("start_lean", -0.1), ("kp", 0.1))                     # start_lean sits on its lower bound: reflection flips the step
        rows = r3.realised_edits(THETA, e)
        self.assertEqual(rows[0]["requested_delta_u"], -0.1)
        self.assertAlmostEqual(rows[0]["realised_delta_u"], 0.1)
        self.assertTrue(rows[0]["reflected"])
        self.assertFalse(rows[1]["reflected"])
        self.assertAlmostEqual(rows[1]["realised_delta_u"], 0.1)
        cands = [{"arm": "M", "realised": rows}]
        aud = r3.matching_audit(cands)
        self.assertEqual(aud["M"]["n_edits"], 2)
        self.assertAlmostEqual(aud["M"]["reflected_fraction"], 0.5)
        self.assertIsNone(aud["N"])

    def test_heuristic_abstains_unless_startup_failures_dominate(self):
        startup = [{"seed": i, "valid_steps": 0} for i in range(10)]
        late = [{"seed": i, "valid_steps": 12} for i in range(10)]
        self.assertEqual(len(r3.heuristic_edits(startup)), 4)
        self.assertEqual(r3.heuristic_edits(late), [])
        self.assertEqual(r3.heuristic_edits([]), [])


class SignFlipTests(unittest.TestCase):
    @staticmethod
    def brute(d):
        obs = sum(d)
        cnt = 0
        for signs in itertools.product((1, -1), repeat=len(d)):
            cnt += abs(sum(s * x for s, x in zip(signs, d))) >= abs(obs)
        return cnt / 2 ** len(d)

    def test_matches_brute_force_enumeration(self):
        for d in ([1, 2, -1, 0, 3], [4, 4, 4, 4, 4, 4], [-1, 1], [0, 0, 0], [2, -3, 1, 1, -2, 0, 4], [1] * 10):
            r = r3.signflip_exact(d)
            nz = [x for x in d if x != 0]
            self.assertAlmostEqual(r["p_two_sided"], self.brute(nz) if nz else 1.0, msg=str(d))

    def test_reference_values(self):
        self.assertAlmostEqual(r3.signflip_exact([1] * 15)["p_two_sided"], 2 / 2 ** 15)          # all blocks favour M by one
        self.assertAlmostEqual(r3.signflip_exact([1] * 15)["p_one_sided_greater"], 1 / 2 ** 15)
        self.assertEqual(r3.signflip_exact([0] * 15)["p_two_sided"], 1.0)
        self.assertEqual(r3.signflip_exact([1, -1])["p_two_sided"], 1.0)
        self.assertAlmostEqual(r3.signflip_exact([3, 2, 1, 1])["p_two_sided"], 2 / 16)           # only the two all-same-sign assignments reach |7|

    def test_clustering_is_respected_primary_test_is_over_blocks_not_slots(self):
        # M beats RM in every slot of 3 blocks (12 slot pairs) and ties elsewhere: block-level p cannot be below 2/2^3
        out = {}
        for b in range(15):
            for s in range(4):
                out[f"RM-{b}-{s}"] = {"improved": False}
                out[f"RN-{b}-{s}"] = {"improved": False}
                out[f"M-{b}-{s}"] = {"improved": b < 3}
                out[f"N-{b}-{s}"] = {"improved": False}
        res = r3.primary_analysis(out)
        self.assertEqual(res["primary"]["per_block_diff"][:3], [4, 4, 4])
        self.assertAlmostEqual(res["primary"]["p_two_sided"], 2 / 2 ** 3)
        self.assertGreater(res["primary"]["p_two_sided"], 0.05)
        self.assertIsNone(res["primary"]["claim"])
        self.assertEqual(res["primary"]["slots_per_arm"], 60)

    def test_invalid_slots_are_failures_and_claim_requires_significance_and_direction(self):
        out = {}
        for b in range(15):
            for s in range(4):
                out[f"RM-{b}-{s}"] = {"improved": s < 1}
                out[f"RN-{b}-{s}"] = {"improved": False}
                out[f"N-{b}-{s}"] = {"improved": False}
                if s < 3:                                              # slot 3 of every M block is invalid: no candidate -> failure
                    out[f"M-{b}-{s}"] = {"improved": True}
        res = r3.primary_analysis(out)
        self.assertEqual(res["primary"]["per_block_M"], [3] * 15)
        self.assertEqual(res["primary"]["per_block_RM"], [1] * 15)
        self.assertEqual(res["primary"]["per_block_diff"], [2] * 15)
        self.assertLess(res["primary"]["p_two_sided"], 0.001)
        self.assertEqual(res["primary"]["claim"], "model edits improve more often than matched random edits")
        rev = {k: ({"improved": not v["improved"]} if k.startswith(("M-", "RM-")) else v) for k, v in out.items()}
        rev = {**rev, **{f"M-{b}-3": {"improved": False} for b in range(15)}}
        flipped = r3.primary_analysis(rev)
        self.assertIsNone(flipped["primary"]["claim"])             # significant in the wrong direction is not a claim


class ModelFlowTests(unittest.TestCase):
    def test_valid_reply_redacted_metadata_and_slot_records(self):
        c = client([reply(good(), good(parameter="kp", delta=-0.05))])
        rec = r3.request_block(c, "M", 0, CTX)
        self.assertEqual(rec.status, "ok")
        self.assertEqual(len(rec.slots), 4)
        self.assertIsNotNone(rec.slots[0]["proposal"])
        self.assertEqual(rec.slots[3]["reason"], "empty")
        s = json.dumps(rec.as_dict())
        self.assertNotIn("test-key", s)
        self.assertNotIn("test-key", repr(c))
        self.assertEqual(rec.call["model"], "scripted-model")
        self.assertEqual(rec.call["usage"]["total_tokens"], 1300)
        self.assertEqual(rec.prompt_sha256, r3.prompt_sha256(r3.build_messages(CTX)))
        self.assertEqual((rec.temperature, rec.max_tokens), (r3.TEMPERATURE, r3.MAX_TOKENS))

    def test_invalid_outputs_stay_invalid_and_are_never_repaired_or_retried(self):
        for text in ("I think you should lean forward.", None, reply()):
            c = client([text])
            rec = r3.request_block(c, "M", 0, CTX)
            self.assertEqual(c.requests_made, 1)
            self.assertEqual(rec.status, "invalid_response")
            self.assertTrue(all(s["proposal"] is None for s in rec.slots))
        self.assertEqual(r3.request_block(client(["plain text"]), "N", 0, CTX_N).raw_reply, "plain text")      # raw reply kept as received

    def test_transport_error_and_budget_refusals_are_recorded(self):
        c = client([NebiusError("HTTP 500: boom")])
        rec = r3.request_block(c, "M", 0, CTX)
        self.assertEqual((rec.status, c.requests_made), ("model_error", 1))
        c2 = client([reply(good())] * 3, max_requests=1)
        r3.request_block(c2, "M", 0, CTX)
        self.assertEqual(r3.request_block(c2, "M", 1, CTX).status, "budget_exceeded")
        self.assertEqual(c2.requests_made, 1)
        c3 = client([reply(good())], tokens=500)
        self.assertEqual(r3.request_block(c3, "M", 0, CTX).status, "budget_exceeded")
        self.assertEqual(c3.requests_made, 0)

    def test_full_registered_batch_fits_the_approved_request_and_token_caps(self):
        """30 requests over the real frozen prompts with realistic usage: every request is sent, totals stay within 130k tokens."""
        usage = (2300, 1500)                                       # generous per-request actuals (prompt + completion incl. hidden reasoning)
        c = client([reply(*[good(parameter=r3.PARAM_NAMES[s], delta=0.05) for s in range(4)])] * 30, usage=usage)
        recs = []
        for b in range(r3.BLOCKS):
            for arm in r3.ARMS_MODEL:
                recs.append(r3.request_block(c, arm, b, CTXS["contexts"][b][arm]["context"]))
        self.assertEqual(c.requests_made, 30)
        self.assertLessEqual(c.tokens_used, r3.MAX_TOTAL_TOKENS)
        self.assertTrue(all(r.status == "ok" for r in recs))
        for r in recs:
            self.assertEqual(r.prompt_sha256, CTXS["contexts"][r.block][r.arm]["prompt_sha256"])
        c31 = client([reply(good())] * 31, max_requests=30)
        for i in range(30):
            r3.request_block(c31, "M", 0, CTX)
        self.assertEqual(r3.request_block(c31, "M", 0, CTX).status, "budget_exceeded")


def fake_job(job):
    d = float(np.linalg.norm(r2.to_u(job["vector"]) - r2.to_u(THETA)))
    per = []
    for k, s in enumerate(job["seeds"]):
        walk = d < 0.05 or (d < 0.3 and k % 2 == 0)
        per.append({**seed_metrics(s, walk), "fitness": {"total": 1.0}})
    return {"ok": True, "result": {"per_seed": per}, "wall_s": 0.0, "peak_rss_mb": 50.0}


class EndToEndAndBudgetTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(r1, "free_memory_gb", return_value=16.0)
        p.start()
        self.addCleanup(p.stop)

    def test_planned_maximum_fits_the_rollout_cap_and_limits_match_the_approval(self):
        plan = r3.planned_rollouts()
        self.assertLessEqual(plan["total_max"], r3.BUDGET_CAP)
        self.assertEqual((r3.MAX_REQUESTS, r3.MAX_TOTAL_TOKENS, r3.BUDGET_CAP, r3.ESTIMATED_SPEND_CAP_USD), (30, 130_000, 6000, 2.0))
        p = r3.build_protocol()
        self.assertLessEqual(p["spend_estimate"]["total_upper_bound_usd"], 2.0)
        self.assertEqual(p["approved_limits"]["live_requests"], 30)

    def test_whole_pipeline_with_scripted_model_and_fake_physics_stays_under_every_cap(self):
        c = client([reply(*[good(parameter=r3.PARAM_NAMES[(b + s) % 15], delta=0.05 + 0.02 * s) for s in range(4)]) for b in range(15)] * 2,
                   usage=(2300, 1500))
        recs = []
        for b in range(r3.BLOCKS):
            for arm in r3.ARMS_MODEL:
                recs.append(r3.request_block(c, arm, b, CTXS["contexts"][b][arm]["context"]).as_dict())
        cand = r3.build_candidates(THETA, recs, [{"seed": i, "valid_steps": 0} for i in range(10)])
        self.assertEqual(cand["n_candidates"], 4 * 60 + 4)
        with tempfile.TemporaryDirectory() as d:
            led = r3.Ledger(Path(d) / "l.jsonl")
            led.session_begin("screen")
            results = {}
            with Executor(1, fn=fake_job) as ex:
                cs = cand["candidates"]
                for lo in range(0, len(cs), 20):
                    chunk = cs[lo:lo + 20]
                    outs = r3.run_batch(ex, led, "screen", [x["vector"] for x in chunk], tuple(range(16)))
                    for x, o in zip(chunk, outs):
                        wk = sum(m["walking"] for m in o["result"]["per_seed"])
                        results[x["id"]] = r3.outcome(8, wk, x.get("predicted_min_gain_seeds"))
            led.session_end()
            led.verify()
            self.assertEqual(led.total_rollouts(), 244 * 16)
            self.assertLessEqual(led.total_rollouts() + 96 + 180 + 64 + 64 + 15 * 64, r3.BUDGET_CAP)
        res = r3.primary_analysis(results)
        self.assertEqual(len(res["primary"]["per_block_diff"]), 15)
        self.assertLessEqual(c.tokens_used, r3.MAX_TOTAL_TOKENS)

    def test_ledger_caps(self):
        with tempfile.TemporaryDirectory() as d:
            led = r3.Ledger(Path(d) / "l.jsonl")
            led.begin("pilot", 96)
            with self.assertRaises(r1.BudgetExceeded):
                led.begin("pilot", 5)
            with mock.patch.object(r3, "BUDGET_CAP", 200):
                with self.assertRaises(r1.BudgetExceeded):
                    led.begin("x", 105)
        self.assertEqual(r3.WALL_LIMIT_S, 3600)


class ProtocolTests(unittest.TestCase):
    def test_protocol_is_self_consistent_and_documents_the_corrections(self):
        p = r3.build_protocol()
        self.assertEqual(p, json.loads(json.dumps(r3.build_protocol())))
        self.assertTrue(p["primary_analysis"]["test"].startswith("paired request-block exact sign-flip"))
        self.assertIn("invalid/empty model slot = failure", p["primary_analysis"]["endpoint"])
        self.assertTrue(p["matched_random"]["every_slot_has_a_counterpart"])
        self.assertIn("identical controller", p["arms"]["N"])
        self.assertEqual(p["contexts"]["n"], 15)
        self.assertIn("8000-8149", p["seeds"]["disclosure"])
        self.assertIn("9000-9001", p["seeds"]["disclosure"])

    def test_seeds_are_disjoint_from_everything_consumed_including_r2_final(self):
        r3.check_disjoint()
        mine = set(r3.EVIDENCE_POOL_SEEDS) | set(r3.SCREEN_POOL_SEEDS) | set(r3.VALIDATION_SEEDS) | set(r3.PILOT_SEEDS)
        self.assertFalse(mine & set(r2.FINAL_SEEDS))
        self.assertFalse(mine & set(r3.INFRA_ONLY_SEEDS))
        for name, seeds in r3.consumed_seed_sets().items():
            self.assertFalse(mine & set(seeds), name)


if __name__ == "__main__":
    unittest.main()
