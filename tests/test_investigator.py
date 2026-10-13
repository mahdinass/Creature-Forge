import json
import tempfile
import unittest
from pathlib import Path

from creature_forge.controller import GaitParams
from creature_forge.experiment import PHASE0_BASELINE, PHASE0_DURATION, PHASE0_PUSH
from creature_forge.investigator import (InvalidModelOutput, build_evidence, investigate, list_trials,
                                         load_trial, parse_hypothesis)
from creature_forge.nebius import Limits, NebiusClient, NebiusError

BODY, GAIT = PHASE0_BASELINE, GaitParams()
UNSET = object()


def good(**over):
    d = {"claim": "The short foot gives a small support polygon, so the push tips the torso over.",
         "cited_evidence": ["matched_seed_results.fall_rate", "detailed_run.events.0.time"],
         "prediction": {"metric": "fall_rate", "direction": "decrease"},
         "confidence": 0.7, "intervention": {"parameter": "foot_length", "value": 0.16}}
    d.update(over)
    return d


class Fake:
    """Fake model transport: returns a canned reply; counts calls. Never touches the network."""
    def __init__(self, reply=None, error=None, content=UNSET):
        self.reply, self.error, self.content, self.calls = reply, error, content, 0

    def __call__(self, url, headers, body, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        content = json.dumps(self.reply) if self.content is UNSET else self.content
        return 200, {}, {"model": "fake", "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200}}


def run(fake, tmp, **kw):
    c = NebiusClient(transport=fake, api_key="k", limits=Limits(max_requests=1, max_total_tokens=8000))
    return c, investigate(c, BODY, GAIT, PHASE0_PUSH, duration=PHASE0_DURATION, save_to=Path(tmp), **kw)


class ParseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = build_evidence(BODY, GAIT, PHASE0_PUSH, seeds=(0,), duration=PHASE0_DURATION)

    def parse(self, reply):
        return parse_hypothesis(reply if isinstance(reply, str) else json.dumps(reply), self.ev, BODY)

    def test_valid_and_fenced(self):
        self.assertEqual(self.parse(good()).value, 0.16)
        self.assertEqual(self.parse("```json\n" + json.dumps(good()) + "\n```").parameter, "foot_length")

    def test_rejections(self):
        iv = lambda p, v: {"parameter": p, "value": v}  # noqa: E731
        bad = {
            "unknown top field": {**good(), "extra": 1},
            "unknown nested field": good(intervention={"parameter": "foot_length", "value": 0.16, "x": 1}),
            "missing field": {k: v for k, v in good().items() if k != "confidence"},
            "unsupported parameter": good(intervention=iv("gravity", 1.0)),
            "gait parameter": good(intervention=iv("kp", 100.0)),
            "out of bounds high": good(intervention=iv("foot_length", 5.0)),
            "out of bounds low": good(intervention=iv("foot_length", 0.0)),
            "nan": good(intervention=iv("foot_length", float("nan"))),
            "bool value": good(intervention=iv("foot_length", True)),
            "string value": good(intervention=iv("foot_length", "0.16")),
            "no-op change": good(intervention=iv("foot_length", BODY.foot_length)),
            "bad metric": good(prediction={"metric": "vibes", "direction": "decrease"}),
            "bad direction": good(prediction={"metric": "fall_rate", "direction": "sideways"}),
            "confidence > 1": good(confidence=1.5),
            "fabricated evidence path": good(cited_evidence=["detailed_run.invented_metric"]),
            "empty evidence": good(cited_evidence=[]),
            "short claim": good(claim="bad"),
        }
        for name, reply in bad.items():
            with self.subTest(name), self.assertRaises(InvalidModelOutput):
                self.parse(reply)

    def test_non_json_and_empty(self):
        for text in ("sure! foot longer", "", None, "[1,2]"):
            with self.subTest(text), self.assertRaises(InvalidModelOutput):
                parse_hypothesis(text, self.ev, BODY)


class PipelineTests(unittest.TestCase):
    def test_accepted_investigation_end_to_end_with_fake_model(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Fake(good())
            _, t = run(fake, d)
            self.assertEqual(fake.calls, 1)
            self.assertEqual((t.status, t.mode), ("accepted", "fake"))
            m = t.measured_outcome
            self.assertEqual(m["observed"]["fall_rate"]["baseline"], 1.0)  # Phase 0: 8 cm foot falls 5/5 at 25 N
            self.assertEqual(m["observed"]["fall_rate"]["candidate"], 0.0)
            self.assertTrue(m["prediction_held"] and m["improved"])
            self.assertEqual(t.hypothesis["intervention"], {"parameter": "foot_length", "value": 0.16})
            self.assertEqual(t.model_call["usage"]["total_tokens"], 1200)
            self.assertEqual(load_trial(t.trial_id, Path(d))["status"], "accepted")
            self.assertEqual(list_trials(Path(d))[0]["trial_id"], t.trial_id)

    def test_verifier_rejects_a_wrong_hypothesis(self):
        with tempfile.TemporaryDirectory() as d:
            wrong = good(intervention={"parameter": "torque_limit", "value": 150.0})  # Phase 0: no effect
            _, t = run(Fake(wrong), d)
            self.assertEqual(t.status, "rejected_by_verifier")
            self.assertFalse(t.measured_outcome["accepted"])  # stated confidence 0.7 is irrelevant
            self.assertEqual(load_trial(t.trial_id, Path(d))["status"], "rejected_by_verifier")

    def test_invalid_output_is_preserved_and_nothing_is_simulated(self):
        with tempfile.TemporaryDirectory() as d:
            _, t = run(Fake(content="here you go: foot longer"), d)
            self.assertEqual(t.status, "invalid_model_output")
            self.assertIsNone(t.measured_outcome)
            self.assertEqual(t.raw_model_reply, "here you go: foot longer")
            self.assertTrue((Path(d) / f"{t.trial_id}.json").exists())

    def test_null_content_is_invalid_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            _, t = run(Fake(content=None), d)
            self.assertEqual(t.status, "invalid_model_output")

    def test_model_error_has_no_retry(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Fake(error=NebiusError("HTTP 429: slow down"))
            _, t = run(fake, d)
            self.assertEqual((t.status, fake.calls), ("model_error", 1))

    def test_budget_exceeded_makes_no_call(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Fake(good())
            c = NebiusClient(transport=fake, api_key="k", limits=Limits(max_requests=0))
            t = investigate(c, BODY, GAIT, PHASE0_PUSH, duration=1.0, save_to=Path(d))
            self.assertEqual((t.status, fake.calls), ("budget_exceeded", 0))

    def test_reasoning_effort_is_configurable_and_recorded(self):
        seen = {}

        def spy(url, headers, body, timeout):
            seen.update(body)
            return Fake(good())(url, headers, body, timeout)
        with tempfile.TemporaryDirectory() as d:
            _, t = run(spy, d, reasoning_effort="none", max_tokens=777)
            self.assertEqual((seen["reasoning_effort"], seen["max_tokens"]), ("none", 777))
            self.assertEqual(t.config["reasoning_effort"], "none")

    def test_trial_record_contains_no_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            _, t = run(Fake(good()), d)
            self.assertNotIn("Bearer", (Path(d) / f"{t.trial_id}.json").read_text())


if __name__ == "__main__":
    unittest.main()
