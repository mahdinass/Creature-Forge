"""Model side of the Forge Loop: prompt, schema, call recording, parsing, validation, repair. No network: fake transports only."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from creature_forge import evidence as evm
from creature_forge import forge_ai as fa
from creature_forge import interventions as iv
from creature_forge.inference_ledger import Caps, InferenceLedger
from creature_forge.nebius import BudgetExceeded, Limits, NebiusClient, NebiusError

FX = Path(__file__).parent / "fixtures" / "forge_ai"
SECRET = "sk-test-SECRET-123"
NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def completion(content, finish="stop", pt=2500, ct=900, reasoning=None, extra_usage=None):
    msg = {"role": "assistant", "content": content}
    if reasoning:
        msg["reasoning_content"] = reasoning
    return {"id": "chatcmpl-1", "model": NANO, "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct, **(extra_usage or {})}}


class Scripted:
    """Fake transport: items are raw response dicts or exceptions; records every request body. Running out is an error."""

    def __init__(self, items):
        self.items, self.calls = list(items), []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body, "timeout": timeout})
        if not self.items:
            raise NebiusError("scripted transport exhausted")
        it = self.items.pop(0)
        if isinstance(it, Exception):
            raise it
        return 200, {"x-request-id": f"rid-{len(self.calls)}"}, it


def reply_text(reply):
    return json.dumps(reply)


class Case(unittest.TestCase):
    """Push challenge on the guided fixture creature."""
    version_file, challenge_file = "version_guided.json", "challenge_push.json"

    def setUp(self):
        self.version = load(self.version_file)
        self.cr = load(self.challenge_file)
        self.kind = self.cr["spec"]["kind"]
        self.ev = evm.build_evidence(self.version, self.cr, None)
        self.dir = Path(tempfile.mkdtemp(prefix="cf-fa-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.cfg = fa.ModelConfig(model=NANO)

    def ledger(self, **kw):
        return InferenceLedger(self.dir / "ledger.jsonl", **kw)

    def client(self, transport, cfg=None):
        return fa.make_client(cfg or self.cfg, transport=transport, api_key=SECRET, base_url="https://example.test/v1")

    def good_reply(self):
        pa, pb = "seeds[0].score", "forensics.support.min_xcom_margin_after_push_m"
        return {
            "diagnosis": {"summary": "The weakest seed fails backwards.", "hypotheses": [
                {"id": "H1", "mechanism": "Support polygon is short.", "evidence": [pa, pb], "competing": ["Ankle torque is limited."]},
                {"id": "H2", "mechanism": "Ankle control is too weak.", "evidence": ["outcome.score.median"], "competing": []}]},
            "proposals": [
                {"id": "P1", "hypothesis": "H1", "category": "morphology",
                 "edits": [{"param": "foot_length", "op": "scale", "value": 1.3, "target": "both"}], "retune_controller": False,
                 "prediction": {"metric": "score", "direction": "increase", "expected_change": "a few newtons"}, "tradeoffs": "heavier feet",
                 "confidence": 0.4, "verification": "push score on fresh seeds"},
                {"id": "P2", "hypothesis": "H2", "category": "control",
                 "edits": [{"param": "stand.balance_gain", "op": "set", "value": 100.0, "target": "both"}], "retune_controller": False,
                 "prediction": {"metric": "score", "direction": "increase", "expected_change": "small"}, "tradeoffs": "noise",
                 "confidence": 0.3, "verification": "same"},
                {"id": "P3", "hypothesis": "H2", "category": "combined",
                 "edits": [{"param": "torque_limit", "op": "scale", "value": 1.2, "target": "both"},
                           {"param": "stand.kd", "op": "set", "value": 12.0, "target": "both"}], "retune_controller": False,
                 "prediction": {"metric": "score", "direction": "increase", "expected_change": "small"}, "tradeoffs": "none",
                 "confidence": 0.2, "verification": "same"}]}

    def validate(self, reply, **kw):
        return fa.validate_reply(reply, self.ev, self.version, self.kind, **kw)


def statuses(val):
    return {p["id"]: p["status"] for p in val["proposals"]}


# ---------------------------------------------------------------------------------------------------------------- parsing
class ParseTests(unittest.TestCase):
    OBJ = {"a": 1, "b": [1, 2], "c": {"d": "x"}}

    def test_plain_and_whitespace(self):
        self.assertEqual(fa.parse_reply(json.dumps(self.OBJ)), self.OBJ)
        self.assertEqual(fa.parse_reply("\n  " + json.dumps(self.OBJ) + "  \n"), self.OBJ)

    def test_code_fences(self):
        t = json.dumps(self.OBJ)
        self.assertEqual(fa.parse_reply(f"```json\n{t}\n```"), self.OBJ)
        self.assertEqual(fa.parse_reply(f"```\n{t}\n```"), self.OBJ)
        self.assertEqual(fa.parse_reply(f"Here is the answer:\n```json\n{t}\n```"), self.OBJ)

    def test_think_prefix(self):
        t = json.dumps(self.OBJ)
        self.assertEqual(fa.parse_reply(f"<think>Let me reason {{not json}} about this.</think>\n{t}"), self.OBJ)
        self.assertEqual(fa.parse_reply(f"<think>\nmulti\nline\n</think>\n\n```json\n{t}\n```"), self.OBJ)
        self.assertEqual(fa.parse_reply(f"reasoning without an opening tag\n</think>{t}"), self.OBJ)

    def test_rejections(self):
        for text, why in ((None, "no content"), ("", "no content"), ("   \n", "no content"), ("[1, 2, 3]", "list"), ('[{"a": 1}]', "list"),
                          ('"just a string"', "prose"), ("42", "value"), ("Sure! Here you go.", "prose"), ("<think>never closed {\"a\": 1}", "unterminated"),
                          ("<think>done</think>", "empty"), ('{"a": 1', "valid JSON"), ('{"a": 1} and then some text', "after the JSON"),
                          ('{"a": 1}{"b": 2}', "after the JSON"), ("```json\n[1]\n```", "list"), ("{'a': 1}", "valid JSON")):
            with self.assertRaises(fa.ReplyParseError, msg=repr(text)) as cm:
                fa.parse_reply(text)
            self.assertIn(why, str(cm.exception), repr(text))

    def test_parse_error_is_valueerror(self):
        self.assertTrue(issubclass(fa.ReplyParseError, ValueError))


# ---------------------------------------------------------------------------------------------------------------- schema
class SchemaTests(Case):
    def objects(self, node, path=""):
        if isinstance(node, dict):
            if node.get("type") == "object":
                yield path, node
            for k, v in node.items():
                yield from self.objects(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from self.objects(v, f"{path}[{i}]")

    def test_generic_schema_is_strict(self):
        json.dumps(fa.REPLY_JSON_SCHEMA)
        objs = list(self.objects(fa.REPLY_JSON_SCHEMA))
        self.assertGreaterEqual(len(objs), 5)
        for path, o in objs:
            self.assertIs(o.get("additionalProperties"), False, path)
            self.assertEqual(sorted(o["required"]), sorted(o["properties"]), path)
        self.assertEqual(fa.REPLY_JSON_SCHEMA["required"], ["diagnosis", "proposals"])

    def test_generic_schema_matches_contract(self):
        hyp = fa.REPLY_JSON_SCHEMA["properties"]["diagnosis"]["properties"]["hypotheses"]["items"]
        self.assertEqual(set(hyp["properties"]), {"id", "mechanism", "evidence", "competing"})
        prop = fa.REPLY_JSON_SCHEMA["properties"]["proposals"]["items"]
        self.assertEqual(set(prop["properties"]), {"id", "hypothesis", "category", "edits", "retune_controller", "prediction", "tradeoffs",
                                                   "confidence", "verification"})
        self.assertEqual(prop["properties"]["category"]["enum"], ["morphology", "control", "combined"])
        self.assertEqual(set(prop["properties"]["edits"]["items"]["properties"]), {"param", "op", "value", "target"})

    def test_per_pack_schema_enums(self):
        allowed = iv.editable_params(self.version, self.kind)
        s = fa.build_reply_schema(self.ev, allowed)
        hyp = s["properties"]["diagnosis"]["properties"]["hypotheses"]["items"]["properties"]
        prop = s["properties"]["proposals"]["items"]["properties"]
        self.assertEqual(hyp["id"]["enum"], ["H1", "H2", "H3"])
        self.assertEqual(prop["hypothesis"]["enum"], ["H1", "H2", "H3"])
        self.assertEqual(prop["id"]["enum"], ["P1", "P2", "P3"])
        self.assertEqual(hyp["evidence"]["items"]["enum"], evm.leaf_paths(self.ev))
        self.assertEqual(prop["edits"]["items"]["properties"]["param"]["enum"], list(allowed))
        self.assertIn("seeds[0].score", hyp["evidence"]["items"]["enum"])
        self.assertNotIn("walk.freq", prop["edits"]["items"]["properties"]["param"]["enum"])
        for p in hyp["evidence"]["items"]["enum"]:
            evm.resolve(self.ev, p)                                     # every enumerated citation is a resolvable scalar

    def test_per_pack_schema_does_not_alter_the_generic_one(self):
        before = json.dumps(fa.REPLY_JSON_SCHEMA, sort_keys=True)
        fa.build_reply_schema(self.ev, ["foot_length"], max_proposals=2)
        self.assertEqual(json.dumps(fa.REPLY_JSON_SCHEMA, sort_keys=True), before)
        s = fa.build_reply_schema(self.ev, ["foot_length"], max_proposals=2)
        self.assertEqual(s["properties"]["proposals"]["items"]["properties"]["id"]["enum"], ["P1", "P2"])

    def test_response_format_wrapper(self):
        rf = fa.response_format({"type": "object"})
        self.assertEqual(rf, {"type": "json_schema", "json_schema": {"name": "forge_reply", "schema": {"type": "object"}, "strict": True}})


class WalkSchemaTests(Case):
    version_file, challenge_file = "version_walk.json", "challenge_walk.json"

    def test_walk_params_enumerated(self):
        s = fa.build_reply_schema(self.ev, iv.editable_params(self.version, "walk"))
        params = s["properties"]["proposals"]["items"]["properties"]["edits"]["items"]["properties"]["param"]["enum"]
        self.assertIn("walk.freq", params)
        self.assertNotIn("stand.kp", params)


# ---------------------------------------------------------------------------------------------------------------- prompt
class PromptTests(Case):
    def msgs(self, **kw):
        return fa.build_messages(self.ev, allowed=iv.editable_params(self.version, self.kind), **kw)

    def test_structure_and_size(self):
        m = self.msgs()
        self.assertEqual([x["role"] for x in m], ["system", "user"])
        total = sum(len(x["content"].encode()) for x in m)
        self.assertLess(total, 15000)
        self.assertLess(len(m[0]["content"].encode()), 6000)

    def test_system_prompt_explains_the_task(self):
        s = self.msgs()[0]["content"]
        for needle in ("planar", "REAR", "FRONT", "MuJoCo", "random", "heuristic", "no change is likely to help", "low confidence", "cite", "H1",
                       "never its text", "REJECTED, never clipped", "[0.5, 1.5]", "0.25", "at most 4 edits", "PUSH", "target_force", "score"):
            self.assertIn(needle.lower(), s.lower(), needle)

    def test_system_prompt_lists_every_editable_param_with_meaning(self):
        allowed = iv.editable_params(self.version, self.kind)
        s = self.msgs()[0]["content"]
        for p, d in allowed.items():
            self.assertIn(f"- {p} ", s)
            self.assertIn(d["meaning"], s)
        self.assertNotIn("walk.freq", s)

    def test_challenge_specific_text(self):
        self.assertIn("retune_controller must be false", self.msgs()[0]["content"])
        self.assertIn("Guided mode", self.msgs()[0]["content"])
        self.assertIn("PUSH", self.msgs()[0]["content"])

    def test_user_message_has_exact_paths_and_values(self):
        u = self.msgs()[1]["content"]
        lines = [x for x in u.split("\n\n")[0].split("\n")[1:]]
        self.assertEqual(len(lines), len(evm.leaf_paths(self.ev)))
        self.assertIn(f"seeds[0].score={json.dumps(self.ev['seeds'][0]['score'])}", lines)
        self.assertIn('outcome.aggregate="' + self.ev["outcome"]["aggregate"] + '"', lines)
        for ln in lines:
            path, _, val = ln.partition("=")
            self.assertEqual(evm.resolve(self.ev, path), json.loads(val), ln)
        self.assertIn("EDIT BOUNDS:", u)
        self.assertIn("foot_length: rear=0.16 front=0.16 range=[0.06, 0.3]", u)
        self.assertIn("stand.kp: current=150 range=[0, 500] u=0.3", u)

    def test_no_hint_of_the_right_fix(self):
        text = " ".join(x["content"] for x in self.msgs()).lower()
        for hint in ("longer feet", "wider feet", "increase foot", "increase the foot", "try increasing", "should increase", "you should scale",
                     "the fix is", "heavier torso"):
            self.assertNotIn(hint, text)

    def test_experimental_prompt_allows_targets(self):
        v = load("version_experimental.json")
        cr = load("challenge_stand.json")
        ev = evm.build_evidence(v, cr)
        s = fa.build_messages(ev, allowed=iv.editable_params(v, "stand"))[0]["content"]
        self.assertIn("targets both|rear|front", s)
        self.assertIn("mode: experimental", s)
        self.assertIn("STAND", s)
        self.assertNotIn("Guided mode", s)

    def test_hash_is_stable_and_sensitive(self):
        a, b = self.msgs(), self.msgs()
        self.assertEqual(fa.prompt_sha256(a), fa.prompt_sha256(b))
        b[1]["content"] += " "
        self.assertNotEqual(fa.prompt_sha256(a), fa.prompt_sha256(b))


class WalkPromptTests(Case):
    version_file, challenge_file = "version_walk.json", "challenge_walk.json"

    def test_walk_prompt(self):
        m = fa.build_messages(self.ev, allowed=iv.editable_params(self.version, "walk"))
        s = m[0]["content"]
        self.assertIn("WALK", s)
        self.assertIn("retune_controller may be true", s)
        self.assertIn("- walk.freq ", s)
        self.assertIn("walk.freq: current=", m[1]["content"])
        self.assertLess(sum(len(x["content"].encode()) for x in m), 15000)


# ---------------------------------------------------------------------------------------------------------------- validation
class ValidateTests(Case):
    def test_all_accepted(self):
        v = self.validate(self.good_reply())
        self.assertEqual(v["schema_errors"], [])
        self.assertEqual(statuses(v), {"P1": "accepted", "P2": "accepted", "P3": "accepted"})
        self.assertEqual([h["status"] for h in v["hypotheses"]], ["accepted", "accepted"])
        p1 = v["proposals"][0]
        self.assertEqual(p1["edits"], [{"param": "foot_length", "op": "scale", "value": 1.3, "target": "both"}])
        self.assertEqual(p1["citations"], ["seeds[0].score", "forensics.support.min_xcom_margin_after_push_m"])
        self.assertAlmostEqual(p1["magnitudes"][0], 0.262364, places=5)
        self.assertEqual(p1["category"], "morphology")
        self.assertEqual(v["proposals"][2]["category"], "combined")

    def test_unresolved_citation_rejects_that_hypothesis_and_its_proposals_only(self):
        r = self.good_reply()
        r["diagnosis"]["hypotheses"][0]["evidence"] = ["seeds[0].score", "seeds[0].metrics.critical_force_nope"]
        v = self.validate(r)
        self.assertEqual(statuses(v), {"P1": "rejected", "P2": "accepted", "P3": "accepted"})
        self.assertEqual([h["status"] for h in v["hypotheses"]], ["rejected", "accepted"])
        text = " ".join(v["proposals"][0]["reasons"])
        self.assertIn("unresolved citation", text)
        self.assertIn("critical_force_nope", text)

    def test_citation_must_be_a_scalar(self):
        for bad in ("seeds[0].metrics", "seeds", "forensics", "seeds[0]"):
            r = self.good_reply()
            r["diagnosis"]["hypotheses"][0]["evidence"] = [bad]
            v = self.validate(r)
            self.assertEqual(v["hypotheses"][0]["status"], "rejected", bad)
            self.assertEqual(v["proposals"][0]["status"], "rejected", bad)

    def test_citation_with_appended_value_or_wrong_prefix_is_unresolved(self):
        for bad in ("seeds[0].score: 1.21", "seeds[0].score=1.21", "evidence.seeds[0].score", "seeds[0].metrics.critical_force_bwd_N"):
            r = self.good_reply()
            r["diagnosis"]["hypotheses"][0]["evidence"] = [bad]
            self.assertEqual(self.validate(r)["proposals"][0]["status"], "rejected", bad)

    def test_citation_count_bounds(self):
        r = self.good_reply()
        r["diagnosis"]["hypotheses"][0]["evidence"] = []
        self.assertEqual(self.validate(r)["hypotheses"][0]["status"], "rejected")
        r["diagnosis"]["hypotheses"][0]["evidence"] = ["seeds[0].score"] * 7
        self.assertEqual(self.validate(r)["hypotheses"][0]["status"], "rejected")
        r["diagnosis"]["hypotheses"][0]["evidence"] = [f"seeds[{i}].score" for i in range(6)]
        self.assertEqual(self.validate(r)["hypotheses"][0]["status"], "accepted")

    def test_proposal_hypothesis_must_be_an_id_not_text(self):
        r = self.good_reply()
        r["proposals"][0]["hypothesis"] = "The support polygon is too short"
        v = self.validate(r)
        self.assertEqual(statuses(v)["P1"], "rejected")
        self.assertIn("not text", " ".join(v["proposals"][0]["reasons"]))

    def test_lowercase_ids_rejected(self):
        r = self.good_reply()
        r["proposals"][0]["hypothesis"] = "h1"
        self.assertEqual(statuses(self.validate(r))["P1"], "rejected")
        r = self.good_reply()
        r["diagnosis"]["hypotheses"][0]["id"] = "h1"
        v = self.validate(r)
        self.assertEqual(v["hypotheses"][0]["status"], "rejected")
        self.assertEqual(statuses(v)["P1"], "rejected")
        r = self.good_reply()
        r["proposals"][0]["id"] = "p1"
        self.assertEqual(self.validate(r)["proposals"][0]["status"], "rejected")

    def test_unknown_hypothesis_id(self):
        r = self.good_reply()
        r["proposals"][0]["hypothesis"] = "H3"
        v = self.validate(r)
        self.assertIn("unknown hypothesis id", " ".join(v["proposals"][0]["reasons"]))

    def test_category_mismatch_and_invalid_category(self):
        r = self.good_reply()
        r["proposals"][0]["category"] = "control"
        v = self.validate(r)
        self.assertIn("category mismatch", " ".join(v["proposals"][0]["reasons"]))
        self.assertEqual(statuses(v), {"P1": "rejected", "P2": "accepted", "P3": "accepted"})
        r = self.good_reply()
        r["proposals"][2]["category"] = "morphology"                    # actuation + control is combined
        self.assertIn("category mismatch", " ".join(self.validate(r)["proposals"][2]["reasons"]))
        r = self.good_reply()
        r["proposals"][0]["category"] = "fancy"
        self.assertEqual(statuses(self.validate(r))["P1"], "rejected")

    def test_actuation_only_is_morphology(self):
        r = self.good_reply()
        r["proposals"][0]["edits"] = [{"param": "torque_limit", "op": "scale", "value": 1.2, "target": "both"}]
        self.assertEqual(statuses(self.validate(r))["P1"], "accepted")

    def test_edit_rule_violation_rejects_only_that_proposal(self):
        r = self.good_reply()
        r["proposals"][0]["edits"][0]["value"] = 2.0
        v = self.validate(r)
        self.assertEqual(statuses(v), {"P1": "rejected", "P2": "accepted", "P3": "accepted"})
        text = " ".join(v["proposals"][0]["reasons"])
        self.assertIn("foot_length", text)
        self.assertIn("ratio", text)

    def test_walk_edit_on_push_and_stand_edit_on_walk(self):
        r = self.good_reply()
        r["proposals"][1]["edits"] = [{"param": "walk.freq", "op": "set", "value": 1.0, "target": "both"}]
        v = self.validate(r)
        self.assertEqual(statuses(v)["P2"], "rejected")
        self.assertIn("walk challenges", " ".join(v["proposals"][1]["reasons"]))
        wv, wc = load("version_walk.json"), load("challenge_walk.json")
        wev = evm.build_evidence(wv, wc)
        wr = self.good_reply()
        wr["diagnosis"]["hypotheses"][0]["evidence"] = ["seeds[0].score"]
        wr["diagnosis"]["hypotheses"][1]["evidence"] = ["outcome.score.median"]
        wr["proposals"][1]["edits"] = [{"param": "stand.kp", "op": "scale", "value": 1.1, "target": "both"}]
        wr["proposals"][0]["edits"] = [{"param": "foot_length", "op": "scale", "value": 1.2, "target": "both"}]
        wr["proposals"][2]["edits"] = [{"param": "walk.kp", "op": "scale", "value": 1.1, "target": "both"}]
        wr["proposals"][2]["category"] = "control"
        v = fa.validate_reply(wr, wev, wv, "walk")
        self.assertEqual(statuses(v), {"P1": "accepted", "P2": "rejected", "P3": "accepted"})
        self.assertIn("stand and push", " ".join(v["proposals"][1]["reasons"]))

    def test_retune_only_for_walk(self):
        r = self.good_reply()
        r["proposals"][0]["retune_controller"] = True
        v = self.validate(r)
        self.assertEqual(statuses(v)["P1"], "rejected")
        self.assertIn("retune_controller", " ".join(v["proposals"][0]["reasons"]))
        wv, wc = load("version_walk.json"), load("challenge_walk.json")
        wev = evm.build_evidence(wv, wc)
        wr = self.good_reply()
        wr["diagnosis"]["hypotheses"][0]["evidence"] = ["seeds[0].score"]
        wr["diagnosis"]["hypotheses"][1]["evidence"] = ["outcome.score.median"]
        wr["proposals"] = [dict(wr["proposals"][0], retune_controller=True, edits=[{"param": "walk.kp", "op": "scale", "value": 1.1, "target": "both"}],
                                category="control")]
        v = fa.validate_reply(wr, wev, wv, "walk")
        self.assertEqual(v["proposals"][0]["status"], "accepted")
        self.assertIs(v["proposals"][0]["retune_controller"], True)
        r = self.good_reply()
        r["proposals"][0]["retune_controller"] = "yes"
        self.assertEqual(statuses(self.validate(r))["P1"], "rejected")

    def test_guided_vs_experimental_targets(self):
        r = self.good_reply()
        r["proposals"][0]["edits"][0]["target"] = "rear"
        self.assertEqual(statuses(self.validate(r))["P1"], "rejected")        # guided: symmetric legs
        xv, xc = load("version_experimental.json"), load("challenge_push.json")
        xev = evm.build_evidence(xv, xc)
        v = fa.validate_reply(r, xev, xv, "push")
        self.assertEqual(statuses(v)["P1"], "accepted")
        self.assertEqual(v["proposals"][0]["edits"][0]["target"], "rear")

    def test_confidence_must_be_a_probability(self):
        for bad in (1.5, -0.1, "high", True, None, float("nan")):
            r = self.good_reply()
            r["proposals"][0]["confidence"] = bad
            self.assertEqual(statuses(self.validate(r))["P1"], "rejected", bad)
        for good in (0, 1, 0.0, 0.5):
            r = self.good_reply()
            r["proposals"][0]["confidence"] = good
            self.assertEqual(statuses(self.validate(r))["P1"], "accepted", good)

    def test_prediction_rules(self):
        for bad in ({"metric": "fall_rate", "direction": "increase", "expected_change": "x"}, {"metric": "score", "direction": "up", "expected_change": "x"},
                    {"metric": "score", "direction": "increase"}, {"metric": "score", "direction": "increase", "expected_change": "x", "extra": 1}, "score up"):
            r = self.good_reply()
            r["proposals"][0]["prediction"] = bad
            self.assertEqual(statuses(self.validate(r))["P1"], "rejected", bad)

    def test_unknown_and_missing_fields(self):
        r = self.good_reply()
        r["proposals"][0]["surprise"] = 1
        self.assertEqual(statuses(self.validate(r))["P1"], "rejected")
        r = self.good_reply()
        del r["proposals"][0]["edits"]
        self.assertEqual(statuses(self.validate(r))["P1"], "rejected")
        r = self.good_reply()
        r["diagnosis"]["hypotheses"][0]["surprise"] = 1
        self.assertEqual(self.validate(r)["hypotheses"][0]["status"], "rejected")

    def test_optional_fields_default(self):
        r = self.good_reply()
        for k in ("retune_controller", "tradeoffs", "verification"):
            del r["proposals"][0][k]
        del r["diagnosis"]["hypotheses"][0]["competing"]
        v = self.validate(r)
        self.assertEqual(statuses(v)["P1"], "accepted")
        self.assertIs(v["proposals"][0]["retune_controller"], False)

    def test_envelope_errors(self):
        for bad in (None, [], "text", 3, {}, {"diagnosis": {}}, {"proposals": []}, {"diagnosis": {"summary": "s", "hypotheses": []}, "proposals": []}):
            v = self.validate(bad)
            self.assertTrue(v["schema_errors"], repr(bad))
            self.assertEqual([p for p in v["proposals"] if p["status"] == "accepted"], [])
        r = self.good_reply()
        r["extra"] = 1
        self.assertTrue(self.validate(r)["schema_errors"])
        r = self.good_reply()
        r["proposals"] = []
        self.assertIn("non-empty", " ".join(self.validate(r)["schema_errors"]))
        r = self.good_reply()
        r["diagnosis"]["hypotheses"] = []
        self.assertTrue(self.validate(r)["schema_errors"])

    def test_duplicate_and_excess_ids(self):
        r = self.good_reply()
        r["proposals"][1]["id"] = "P1"
        v = self.validate(r)
        self.assertEqual(v["proposals"][0]["status"], "accepted")
        self.assertEqual(v["proposals"][1]["status"], "rejected")
        self.assertIn("duplicate", " ".join(v["proposals"][1]["reasons"]))
        r = self.good_reply()
        r["proposals"].append(copy.deepcopy(r["proposals"][0]) | {"id": "P4"})
        v = self.validate(r)
        self.assertEqual(v["proposals"][3]["status"], "rejected")
        v = self.validate(self.good_reply(), max_proposals=2)
        self.assertEqual([p["status"] for p in v["proposals"]], ["accepted", "accepted", "rejected"])
        r = self.good_reply()
        r["diagnosis"]["hypotheses"] += [dict(r["diagnosis"]["hypotheses"][0], id="H3"), dict(r["diagnosis"]["hypotheses"][0], id="H4")]
        v = self.validate(r)
        self.assertEqual([h["status"] for h in v["hypotheses"]], ["accepted", "accepted", "accepted", "rejected"])

    def test_long_prose_is_shortened_with_a_warning(self):
        r = self.good_reply()
        r["diagnosis"]["summary"] = "x" * 900
        r["proposals"][0]["tradeoffs"] = "y" * 2000
        v = self.validate(r)
        self.assertEqual(v["schema_errors"], [])
        self.assertEqual(statuses(v)["P1"], "accepted")
        self.assertLessEqual(len(v["proposals"][0]["tradeoffs"]), 600)
        self.assertEqual(len(v["warnings"]), 2)

    def test_edits_malformed(self):
        for bad in ("foot_length", [], [{"param": "foot_length"}], [[1, 2]], None, [{"param": "pose", "op": "set", "value": 0.1, "target": "both"}]):
            r = self.good_reply()
            r["proposals"][0]["edits"] = bad
            self.assertEqual(statuses(self.validate(r))["P1"], "rejected", bad)


# ---------------------------------------------------------------------------------------------------------------- nebius extra_body
class ExtraBodyTests(unittest.TestCase):
    def client(self, t):
        return NebiusClient(transport=t, api_key=SECRET, base_url="https://example.test/v1", limits=Limits(max_tokens_per_request=20000, max_total_tokens=200000))

    def test_merged_into_body(self):
        t = Scripted([completion("{}")])
        self.client(t).chat([{"role": "user", "content": "x"}], max_tokens=100, extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        body = t.calls[0]["body"]
        self.assertEqual(body["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual((body["model"], body["max_tokens"]), (NebiusClient.model, 100))

    def test_cannot_override_client_owned_keys(self):
        for key in ("model", "messages", "max_tokens", "temperature", "reasoning_effort", "response_format"):
            t = Scripted([completion("{}")])
            c = self.client(t)
            with self.assertRaises(ValueError, msg=key):
                c.chat([{"role": "user", "content": "x"}], max_tokens=100, extra_body={key: "evil"})
            self.assertEqual((t.calls, c.requests_made, c.tokens_used), ([], 0, 0))

    def test_not_a_dict(self):
        t = Scripted([])
        with self.assertRaises(ValueError):
            self.client(t).chat([], max_tokens=10, extra_body=["a"])
        self.assertEqual(t.calls, [])

    def test_absent_or_empty_changes_nothing(self):
        t = Scripted([completion("{}"), completion("{}"), completion("{}")])
        c = self.client(t)
        c.chat([], max_tokens=10)
        c.chat([], max_tokens=10, extra_body={})
        c.chat([], max_tokens=10, extra_body=None)
        self.assertEqual(t.calls[0]["body"], t.calls[1]["body"])
        self.assertEqual(t.calls[0]["body"], t.calls[2]["body"])


# ---------------------------------------------------------------------------------------------------------------- call_model
class CallModelTests(Case):
    def messages(self):
        return fa.build_messages(self.ev, allowed=iv.editable_params(self.version, self.kind))

    def call(self, items, cfg=None, ledger=None, **kw):
        cfg = cfg or self.cfg
        t = Scripted(items)
        led = ledger or self.ledger()
        c = fa.call_model(self.client(t, cfg), cfg, self.messages(), led, investigation_id="i-1", **kw)
        return c, t, led

    def test_request_shape_defaults(self):
        c, t, led = self.call([completion(reply_text(self.good_reply()))])
        b = t.calls[0]["body"]
        self.assertEqual(b["model"], NANO)
        self.assertEqual((b["max_tokens"], b["temperature"], b["reasoning_effort"]), (16000, 0.6, "low"))
        self.assertEqual(t.calls[0]["url"], "https://example.test/v1/chat/completions")
        self.assertEqual(t.calls[0]["timeout"], 180.0)
        rf = b["response_format"]
        self.assertEqual((rf["type"], rf["json_schema"]["name"], rf["json_schema"]["strict"]), ("json_schema", "forge_reply", True))
        self.assertEqual(rf["json_schema"]["schema"], fa.REPLY_JSON_SCHEMA)
        self.assertEqual(b["messages"], self.messages())
        self.assertNotIn("chat_template_kwargs", b)
        self.assertTrue(c.ok)

    def test_custom_schema_and_extra_body(self):
        cfg = fa.ModelConfig(model=NANO, extra_body={"chat_template_kwargs": {"enable_thinking": False}}, reasoning_effort=None, max_tokens=8000,
                             temperature=0.2, timeout_s=90.0)
        schema = fa.build_reply_schema(self.ev, ["foot_length"])
        c, t, _ = self.call([completion("{}")], cfg=cfg, response_schema=schema)
        b = t.calls[0]["body"]
        self.assertEqual(b["chat_template_kwargs"], {"enable_thinking": False})
        self.assertNotIn("reasoning_effort", b)
        self.assertEqual(b["response_format"]["json_schema"]["schema"], schema)
        self.assertEqual((b["max_tokens"], b["temperature"], t.calls[0]["timeout"]), (8000, 0.2, 90.0))
        self.assertEqual(c.settings["extra_body"], {"chat_template_kwargs": {"enable_thinking": False}})

    def test_json_schema_off_sends_no_response_format(self):
        cfg = fa.ModelConfig(model=NANO, json_schema=False)
        c, t, _ = self.call([completion("{}")], cfg=cfg)
        self.assertNotIn("response_format", t.calls[0]["body"])
        self.assertFalse(c.settings["json_schema"])

    def test_extra_body_cannot_override(self):
        cfg = fa.ModelConfig(model=NANO, extra_body={"max_tokens": 5})
        t = Scripted([completion("{}")])
        led = self.ledger()
        with self.assertRaises(ValueError):
            fa.call_model(self.client(t, cfg), cfg, self.messages(), led, investigation_id="i-1")
        self.assertEqual(t.calls, [])
        self.assertFalse(led.path.exists())                            # nothing reserved either

    def test_bad_reasoning_effort_rejected_before_ledger(self):
        with self.assertRaises(ValueError):
            fa.ModelConfig(model=NANO, reasoning_effort="extreme").validate()

    def test_record_is_complete_and_cost_is_computed(self):
        c, t, led = self.call([completion(reply_text(self.good_reply()), pt=3000, ct=1000, reasoning="thinking...")])
        self.assertTrue(c.ok)
        self.assertEqual((c.model, c.finish_reason, c.http_status, c.request_id), (NANO, "stop", 200, "rid-1"))
        self.assertTrue(c.reasoning_present)
        self.assertEqual(c.usage["prompt_tokens"], 3000)
        self.assertAlmostEqual(c.cost_usd, 3000 * 6e-8 + 1000 * 2.4e-7)
        self.assertEqual(c.raw_response["choices"][0]["message"]["reasoning_content"], "thinking...")
        self.assertEqual(c.prompt_sha256, fa.prompt_sha256(self.messages()))
        self.assertEqual(c.messages, self.messages())
        self.assertGreaterEqual(c.latency_s, 0.0)
        self.assertIsNone(c.error)
        s = led.status()
        self.assertEqual(s["requests"], 1)
        self.assertAlmostEqual(s["usd"], c.cost_usd)
        d = c.as_dict()
        for k in ("model", "settings", "prompt_sha256", "messages", "raw_response", "content", "reasoning_present", "request_id", "latency_s", "usage",
                  "cost_usd", "finish_reason", "http_status", "error"):
            self.assertIn(k, d)
        self.assertTrue(d["ok"])

    def test_api_key_never_recorded(self):
        c, t, led = self.call([completion("{}")])
        self.assertNotIn(SECRET, json.dumps(c.as_dict()))
        self.assertNotIn(SECRET, json.dumps(t.calls[0]["body"]))
        self.assertNotIn(SECRET, led.path.read_text())

    def test_transport_restored_after_call(self):
        t = Scripted([completion("{}")])
        client = self.client(t)
        fa.call_model(client, self.cfg, self.messages(), self.ledger(), investigation_id="i-1")
        self.assertIs(client.transport, t)
        t2 = Scripted([NebiusError("HTTP 500: boom")])
        client = self.client(t2)
        fa.call_model(client, self.cfg, self.messages(), self.ledger(), investigation_id="i-2")
        self.assertIs(client.transport, t2)

    def test_null_content_is_a_recorded_failure(self):
        c, t, led = self.call([completion(None, ct=16000, reasoning="long hidden reasoning")])
        self.assertFalse(c.ok)
        self.assertIn("content_null", c.error)
        self.assertIsNone(c.content)
        self.assertEqual(len(t.calls), 1)
        self.assertEqual(led.status()["requests"], 1)                   # it still cost a request
        self.assertGreater(led.status()["usd"], 0)

    def test_blank_content(self):
        c, _, _ = self.call([completion("  \n ")])
        self.assertFalse(c.ok)
        self.assertIn("content_empty", c.error)

    def test_finish_reason_length_is_a_failure_even_with_content(self):
        c, t, _ = self.call([completion('{"diagnosis": {', finish="length", ct=16000)])
        self.assertFalse(c.ok)
        self.assertIn("finish_reason=length", c.error)
        self.assertEqual(c.finish_reason, "length")
        self.assertEqual(c.content, '{"diagnosis": {')                   # kept for the record
        self.assertEqual(len(t.calls), 1)

    def test_http_error_recorded_with_status(self):
        c, t, led = self.call([NebiusError("HTTP 503: upstream unavailable")])
        self.assertFalse(c.ok)
        self.assertIn("HTTP 503", c.error)
        self.assertEqual(c.http_status, 503)
        self.assertIsNone(c.raw_response)
        self.assertEqual(len(t.calls), 1)
        self.assertEqual((led.status()["requests"], led.status()["usd"]), (1, 0.0))

    def test_timeout_recorded(self):
        c, t, _ = self.call([NebiusError("TimeoutError: timed out")])
        self.assertFalse(c.ok)
        self.assertIn("TimeoutError", c.error)
        self.assertIsNone(c.http_status)
        self.assertEqual(len(t.calls), 1)

    def test_malformed_response_recorded_and_raw_kept(self):
        c, t, _ = self.call([{"unexpected": True, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}])
        self.assertFalse(c.ok)
        self.assertIn("malformed", c.error)
        self.assertEqual(c.raw_response["unexpected"], True)

    def test_budget_refusal_happens_before_any_transport_call(self):
        t = Scripted([completion("{}")])
        led = self.ledger(caps=Caps(inv_max_requests=0))
        c = fa.call_model(self.client(t), self.cfg, self.messages(), led, investigation_id="i-1")
        self.assertEqual(t.calls, [])
        self.assertFalse(c.ok)
        self.assertTrue(c.budget_refused)
        self.assertIn("BudgetExceeded", c.error)
        self.assertFalse(c.sent)

    def test_total_cap_refusal(self):
        t = Scripted([completion("{}")])
        led = self.ledger(caps=Caps(max_requests=0))
        c = fa.call_model(self.client(t), self.cfg, self.messages(), led, investigation_id="i-1")
        self.assertEqual(t.calls, [])
        self.assertTrue(c.budget_refused)

    def test_unknown_price_refuses_before_network(self):
        cfg = fa.ModelConfig(model="not/priced")
        t = Scripted([completion("{}")])
        c = fa.call_model(self.client(t, cfg), cfg, self.messages(), self.ledger(), investigation_id="i-1")
        self.assertEqual(t.calls, [])
        self.assertTrue(c.budget_refused)
        self.assertIn("price", c.error)

    def test_client_side_refusal_releases_the_reservation(self):
        t = Scripted([completion("{}")])
        small = NebiusClient(transport=t, api_key=SECRET, base_url="https://example.test/v1", limits=Limits(max_tokens_per_request=100))
        led = self.ledger()
        c = fa.call_model(small, self.cfg, self.messages(), led, investigation_id="i-1")
        self.assertEqual(t.calls, [])
        self.assertFalse(c.ok)
        self.assertFalse(c.sent)
        self.assertEqual(led.status()["requests"], 0)
        self.assertEqual(led.investigation_status("i-1")["requests"], 0)

    def test_missing_api_key_releases_too(self):
        t = Scripted([completion("{}")])
        nokey = NebiusClient(transport=t, api_key="", base_url="https://example.test/v1", limits=Limits(max_tokens_per_request=20000, max_total_tokens=200000))
        led = self.ledger()
        c = fa.call_model(nokey, self.cfg, self.messages(), led, investigation_id="i-1")
        self.assertEqual(t.calls, [])
        self.assertIn("NEBIUS_API_KEY", c.error)
        self.assertEqual(led.status()["requests"], 0)

    def test_model_and_timeout_taken_from_config(self):
        cfg = fa.ModelConfig(model="nvidia/Nemotron-3_5-Lightning", timeout_s=33.0)
        t = Scripted([completion("{}")])
        client = NebiusClient(model=NANO, transport=t, api_key=SECRET, base_url="https://example.test/v1", limits=Limits(max_tokens_per_request=20000, max_total_tokens=200000))
        fa.call_model(client, cfg, self.messages(), self.ledger(), investigation_id="i-1")
        self.assertEqual(t.calls[0]["body"]["model"], "nvidia/Nemotron-3_5-Lightning")
        self.assertEqual(t.calls[0]["timeout"], 33.0)

    def test_make_client_limits_fit_the_config(self):
        c = fa.make_client(fa.ModelConfig(model=NANO), transport=Scripted([]), api_key=SECRET, base_url="https://example.test/v1")
        self.assertGreaterEqual(c.limits.max_tokens_per_request, 16000)
        self.assertEqual(c.limits.timeout_s, 180.0)
        self.assertNotIn(SECRET, repr(c))


# ---------------------------------------------------------------------------------------------------------------- investigate_once
class InvestigateTests(Case):
    def run_once(self, items, cfg=None, ledger=None, **kw):
        cfg = cfg or self.cfg
        t = Scripted(items)
        led = ledger or self.ledger()
        out = fa.investigate_once(self.client(t, cfg), cfg, self.version, self.cr, kw.pop("history", None), led, investigation_id=kw.pop("investigation_id", "i-1"),
                                  **kw)
        return out, t, led

    def test_happy_path_single_call(self):
        out, t, led = self.run_once([completion(reply_text(self.good_reply()))])
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(t.calls), 1)
        self.assertFalse(out["repaired"])
        self.assertEqual([p["id"] for p in out["accepted"]], ["P1", "P2", "P3"])
        self.assertEqual(len(out["calls"]), 1)
        self.assertEqual(out["investigation_id"], "i-1")
        self.assertLessEqual(out["evidence_bytes"], 6144)
        self.assertEqual(out["evidence"], self.ev)
        self.assertEqual(out["reply"], self.good_reply())
        self.assertEqual(led.investigation_status("i-1")["requests"], 1)
        self.assertIn("foot_length", out["allowed"])

    def test_request_carries_per_pack_schema_and_evidence(self):
        out, t, _ = self.run_once([completion(reply_text(self.good_reply()))])
        b = t.calls[0]["body"]
        s = b["response_format"]["json_schema"]["schema"]
        hyp = s["properties"]["diagnosis"]["properties"]["hypotheses"]["items"]["properties"]
        self.assertEqual(hyp["evidence"]["items"]["enum"], evm.leaf_paths(self.ev))
        self.assertEqual(hyp["id"]["enum"], ["H1", "H2", "H3"])
        self.assertIn("seeds[0].score=", b["messages"][1]["content"])
        self.assertEqual(b["max_tokens"], 16000)

    def test_think_prefixed_and_fenced_reply(self):
        text = "<think>reasoning...</think>\n```json\n" + reply_text(self.good_reply()) + "\n```"
        out, t, _ = self.run_once([completion(text)])
        self.assertEqual((out["status"], len(t.calls)), ("ok", 1))

    def test_generated_investigation_id(self):
        cfg = self.cfg
        t = Scripted([completion(reply_text(self.good_reply()))])
        out = fa.investigate_once(self.client(t), cfg, self.version, self.cr, None, self.ledger())
        self.assertTrue(out["investigation_id"].startswith("i-"))

    def test_partially_valid_reply_needs_no_repair(self):
        r = self.good_reply()
        r["proposals"][0]["edits"][0]["value"] = 2.0
        out, t, _ = self.run_once([completion(reply_text(r))])
        self.assertEqual((out["status"], len(t.calls), out["repaired"]), ("ok", 1, False))
        self.assertEqual([p["id"] for p in out["accepted"]], ["P2", "P3"])
        self.assertEqual(statuses(out["validation"])["P1"], "rejected")

    def test_repair_after_invalid_json_exactly_one_extra_call(self):
        out, t, led = self.run_once([completion("Sure, here is my analysis: the feet are short."), completion(reply_text(self.good_reply()))])
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["repaired"])
        self.assertEqual(len(t.calls), 2)
        self.assertEqual(len(out["calls"]), 2)
        msgs = t.calls[1]["body"]["messages"]
        self.assertEqual(msgs[:2], t.calls[0]["body"]["messages"])
        self.assertEqual(msgs[2]["role"], "assistant")
        self.assertIn("the feet are short", msgs[2]["content"])
        self.assertEqual(msgs[3]["role"], "user")
        self.assertIn("rejected by the validator", msgs[3]["content"])
        self.assertIn("not a JSON object", msgs[3]["content"])               # the validator's error list is carried
        self.assertEqual(led.investigation_status("i-1")["requests"], 2)     # and counted
        self.assertEqual(out["calls"][1]["settings"]["purpose"], "investigation_repair")

    def test_repair_after_schema_invalid_reply_carries_errors(self):
        bad = self.good_reply()
        for p in bad["proposals"]:
            p["hypothesis"] = "The ankle is weak"                              # text instead of an id: every proposal rejected
        out, t, _ = self.run_once([completion(reply_text(bad)), completion(reply_text(self.good_reply()))])
        self.assertEqual((out["status"], len(t.calls)), ("ok", 2))
        self.assertIn("not text", t.calls[1]["body"]["messages"][3]["content"])
        self.assertIn("proposal P1", t.calls[1]["body"]["messages"][3]["content"])

    def test_repair_after_unresolved_citations_and_envelope_error(self):
        bad = self.good_reply()
        bad["diagnosis"]["hypotheses"][0]["evidence"] = ["made.up.path"]
        bad["diagnosis"]["hypotheses"][1]["evidence"] = ["seeds[0].score: 1.2"]
        out, t, _ = self.run_once([completion(reply_text(bad)), completion(reply_text(self.good_reply()))])
        self.assertEqual((out["status"], len(t.calls)), ("ok", 2))
        self.assertIn("unresolved citation", t.calls[1]["body"]["messages"][3]["content"])
        bad2 = {"diagnosis": {"summary": "s", "hypotheses": []}, "proposals": []}
        out, t, _ = self.run_once([completion(reply_text(bad2)), completion(reply_text(self.good_reply()))])
        self.assertEqual((out["status"], len(t.calls)), ("ok", 2))

    def test_repair_after_list_reply(self):
        out, t, _ = self.run_once([completion("[1, 2]"), completion(reply_text(self.good_reply()))])
        self.assertEqual((out["status"], len(t.calls)), ("ok", 2))

    def test_repair_is_attempted_once_only(self):
        out, t, led = self.run_once([completion("nope"), completion("still nope"), completion(reply_text(self.good_reply()))])
        self.assertEqual(out["status"], "no_valid_proposal")
        self.assertEqual(len(t.calls), 2)                                      # the third scripted reply is never requested
        self.assertEqual(len(t.items), 1)
        self.assertEqual(out["accepted"], [])
        self.assertEqual(led.investigation_status("i-1")["requests"], 2)
        self.assertTrue(out["error"])

    def test_repair_all_rejected_then_all_rejected(self):
        bad = self.good_reply()
        for p in bad["proposals"]:
            p["category"] = "morphology"
            p["edits"] = [{"param": "foot_length", "op": "scale", "value": 2.0, "target": "both"}]
        out, t, _ = self.run_once([completion(reply_text(bad)), completion(reply_text(bad))])
        self.assertEqual((out["status"], len(t.calls)), ("no_valid_proposal", 2))
        self.assertTrue(out["repaired"])
        self.assertIsNotNone(out["validation"])

    def test_null_content_no_repair(self):
        out, t, led = self.run_once([completion(None, ct=16000, reasoning="x"), completion(reply_text(self.good_reply()))])
        self.assertEqual(out["status"], "model_failed")
        self.assertEqual(len(t.calls), 1)
        self.assertIn("content_null", out["error"])
        self.assertFalse(out["repaired"])
        self.assertIsNone(out["reply"])
        self.assertEqual(out["accepted"], [])
        self.assertEqual(led.investigation_status("i-1")["requests"], 1)

    def test_finish_length_no_repair(self):
        out, t, _ = self.run_once([completion('{"diagnosis": {"summary": "cut', finish="length", ct=16000), completion(reply_text(self.good_reply()))])
        self.assertEqual((out["status"], len(t.calls)), ("model_failed", 1))
        self.assertIn("finish_reason=length", out["error"])

    def test_http_error_and_timeout_no_retry(self):
        for i, err in enumerate((NebiusError("HTTP 500: boom"), NebiusError("TimeoutError: timed out"), NebiusError("URLError: refused"))):
            out, t, _ = self.run_once([err, completion(reply_text(self.good_reply()))], ledger=InferenceLedger(self.dir / f"l{i}.jsonl"))
            self.assertEqual((out["status"], len(t.calls)), ("model_failed", 1), str(err))
            self.assertEqual(len(out["calls"]), 1)

    def test_repair_call_failure_is_recorded(self):
        out, t, _ = self.run_once([completion("not json"), NebiusError("HTTP 500: boom"), completion(reply_text(self.good_reply()))])
        self.assertEqual((out["status"], len(t.calls)), ("model_failed", 2))
        self.assertIn("repair call failed", out["error"])
        self.assertTrue(out["repaired"])

    def test_budget_refusal_before_any_call(self):
        led = self.ledger(caps=Caps(max_requests=0))
        out, t, _ = self.run_once([completion(reply_text(self.good_reply()))], ledger=led)
        self.assertEqual(t.calls, [])
        self.assertEqual(out["status"], "model_failed")
        self.assertIn("BudgetExceeded", out["error"])
        self.assertTrue(out["calls"][0]["budget_refused"])

    def test_investigation_cap_blocks_the_repair_call(self):
        led = self.ledger(caps=Caps(inv_max_requests=1))
        out, t, _ = self.run_once([completion("not json"), completion(reply_text(self.good_reply()))], ledger=led)
        self.assertEqual(len(t.calls), 1)
        self.assertEqual(out["status"], "model_failed")
        self.assertIn("repair call failed", out["error"])
        self.assertTrue(out["calls"][1]["budget_refused"])

    def test_default_caps_allow_a_repair_within_80k_tokens(self):
        led = self.ledger()
        out, t, _ = self.run_once([completion("not json", pt=3000, ct=2000), completion(reply_text(self.good_reply()), pt=5000, ct=3000)], ledger=led)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(led.investigation_status("i-1")["tokens"], 13000)

    def test_ledger_shared_across_investigations(self):
        led = self.ledger(caps=Caps(max_requests=2))
        for i in range(2):
            out, t, _ = self.run_once([completion(reply_text(self.good_reply()))], ledger=led, investigation_id=f"i-{i}")
            self.assertEqual(out["status"], "ok")
        out, t, _ = self.run_once([completion(reply_text(self.good_reply()))], ledger=led, investigation_id="i-9")
        self.assertEqual((t.calls, out["status"]), ([], "model_failed"))

    def test_history_is_in_the_prompt(self):
        hist = [{"round": 1, "summary": "tried longer feet", "verdict": {"status": "NOT_VERIFIED"}}]
        out, t, _ = self.run_once([completion(reply_text(self.good_reply()))], history=hist)
        self.assertIn("history[0].round=1", t.calls[0]["body"]["messages"][1]["content"])

    def test_max_proposals_limits_ids(self):
        r = self.good_reply()
        out, t, _ = self.run_once([completion(reply_text(r))], max_proposals=2)
        self.assertEqual([p["id"] for p in out["accepted"]], ["P1", "P2"])
        s = t.calls[0]["body"]["response_format"]["json_schema"]["schema"]
        self.assertEqual(s["properties"]["proposals"]["items"]["properties"]["id"]["enum"], ["P1", "P2"])


class StandScenarioTests(Case):
    version_file, challenge_file = "version_experimental.json", "challenge_stand.json"

    def test_experimental_stand_end_to_end(self):
        r = self.good_reply()
        r["diagnosis"]["hypotheses"][0]["evidence"] = ["seeds[0].score", "outcome.score.median"]
        r["proposals"][0]["edits"] = [{"param": "foot_length", "op": "scale", "value": 1.4, "target": "rear"}]
        t = Scripted([completion(reply_text(r))])
        out = fa.investigate_once(self.client(t), self.cfg, self.version, self.cr, None, self.ledger(), investigation_id="i-s")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["accepted"][0]["edits"][0]["target"], "rear")
        edits = [iv.Edit.from_dict(e) for e in out["accepted"][0]["edits"]]
        body, ctl = iv.apply_edits(self.version, edits)
        self.assertAlmostEqual(body["foot_length"], 0.08 * 1.4)
        self.assertEqual(body["foot_length_r"], 0.1)


# ---------------------------------------------------------------------------------------------------------------- diagnostic probes
class ProbeFlowTests(Case):
    PROBE_PATH = "probes.balance_gain_x1_5.median_delta"

    def setUp(self):
        super().setUp()
        self.runner_calls = []

    def plan(self, probes=None, hyps=None):
        r = self.good_reply()
        probes = [{"probe_id": "balance_gain_x1_5", "hypothesis": "H2", "expect": "increase"},
                  {"probe_id": "no_push", "hypothesis": "H1", "expect": "decrease"}] if probes is None else probes
        return {"diagnosis": hyps or r["diagnosis"], "probes": probes}

    def step_b(self):
        r = self.good_reply()
        r["diagnosis"]["hypotheses"][1]["evidence"].append(self.PROBE_PATH)
        return r

    def runner(self, requests, ids):
        self.runner_calls.append((requests, ids))
        res = {}
        for i in ids:
            res[i] = ({"probe_id": i, "measurement": "static", "status": "ok", "median": 5.0, "n_seeds": 4, "static_fall_frac": 0.0}
                      if i == "no_push" else
                      {"probe_id": i, "measurement": "paired", "status": "ok", "median": 12.0, "median_delta": 2.0, "mean_delta": 2.0,
                       "wins": 3, "losses": 0, "ties": 1, "n_seeds": 4})
        return {"seeds": [1, 2, 3, 4], "resolution": 0.625, "rollouts": 68, "bisection_steps": 7,
                "original": {"median": 10.0, "scores": [10.0] * 4, "status": "ok"}, "results": res}

    def run_probe_flow(self, items, ledger=None, runner=None):
        t = Scripted(items)
        led = ledger or self.ledger()
        out = fa.investigate_with_probes(self.client(t), self.cfg, self.version, self.cr, None, led, probe_runner=runner or self.runner,
                                         investigation_id="i-p")
        return out, t, led

    def ok(self, obj):
        return completion(reply_text(obj))

    # -- protocol
    def test_two_calls_probe_results_in_step_b(self):
        out, t, led = self.run_probe_flow([self.ok(self.plan()), self.ok(self.step_b())])
        self.assertEqual((out["status"], len(t.calls), out["repaired"]), ("ok", 2, False))
        self.assertEqual([c["settings"]["purpose"] for c in out["calls"]], ["investigation_probe_plan", "investigation"])
        self.assertEqual(led.investigation_status("i-p")["requests"], 2)
        self.assertEqual(self.runner_calls[0][1], ["balance_gain_x1_5", "no_push"])
        a, b = t.calls[0]["body"]["messages"], t.calls[1]["body"]["messages"]
        self.assertIn(fa.PROBE_STEP_MARK, a[0]["content"])
        self.assertIn("AVAILABLE PROBES:", a[0]["content"])
        self.assertNotIn("probes.", a[1]["content"])
        self.assertNotIn(fa.PROBE_STEP_MARK, b[0]["content"])
        self.assertIn("PROBE RESULTS", b[0]["content"])
        self.assertIn(self.PROBE_PATH + "=2.0", b[1]["content"])
        self.assertIn("probes.no_push.static_fall_frac=0.0", b[1]["content"])
        self.assertIn("YOUR STEP A", b[1]["content"])
        self.assertIn("Ankle control is too weak.", b[1]["content"])        # the step-A hypotheses are echoed
        self.assertEqual([p["id"] for p in out["accepted"]], ["P1", "P2", "P3"])
        self.assertEqual(out["evidence"]["probes"]["balance_gain_x1_5"]["median_delta"], 2.0)
        self.assertIn(self.PROBE_PATH, [x for x in evm.leaf_paths(out["evidence"])])
        self.assertTrue(any(self.PROBE_PATH in h["evidence"] for h in out["validation"]["hypotheses"]))   # citing a probe path validates

    def test_step_a_schema_enumerates_available_probe_ids_and_citations(self):
        out, t, _ = self.run_probe_flow([self.ok(self.plan()), self.ok(self.step_b())])
        s = t.calls[0]["body"]["response_format"]["json_schema"]["schema"]
        enum = s["properties"]["probes"]["items"]["properties"]["probe_id"]["enum"]
        self.assertEqual(enum, out["probes"]["available"])
        self.assertTrue(set(enum) <= set(pb_ids()))
        self.assertIn("no_push", enum)
        self.assertEqual(s["properties"]["probes"]["items"]["properties"]["expect"]["enum"], ["increase", "decrease", "no_change"])
        self.assertEqual(s["required"], ["diagnosis", "probes"])
        self.assertNotIn("proposals", s["properties"])
        hyp = s["properties"]["diagnosis"]["properties"]["hypotheses"]["items"]["properties"]
        self.assertEqual(hyp["evidence"]["items"]["enum"], evm.leaf_paths(self.ev))
        b = t.calls[1]["body"]["response_format"]["json_schema"]["schema"]
        self.assertIn(self.PROBE_PATH, b["properties"]["diagnosis"]["properties"]["hypotheses"]["items"]["properties"]["evidence"]["items"]["enum"])
        self.assertIn("proposals", b["properties"])

    def test_expectations_are_computed_by_the_executor_not_the_model(self):
        out, _, _ = self.run_probe_flow([self.ok(self.plan()), self.ok(self.step_b())])
        e = {x["probe_id"]: x for x in out["probes"]["expectations"]}
        self.assertEqual((e["balance_gain_x1_5"]["observed"], e["balance_gain_x1_5"]["confirmed"]), ("increase", True))
        self.assertEqual((e["no_push"]["observed"], e["no_push"]["confirmed"]), (None, None))   # measurement-only probe
        self.assertEqual(out["probes"]["requested"], [{"probe_id": "balance_gain_x1_5", "hypothesis": "H2", "expect": "increase"},
                                                      {"probe_id": "no_push", "hypothesis": "H1", "expect": "decrease"}])
        self.assertEqual((out["probes"]["rollouts"], out["probes"]["seeds"]), (68, [1, 2, 3, 4]))

    # -- validation of the plan
    def test_probe_plan_validation(self):
        avail = ["balance_gain_x1_5", "no_push", "foot_x1_5"]
        v = lambda probes: fa.validate_probe_reply(self.plan(probes), self.ev, avail)
        ok = {"probe_id": "foot_x1_5", "hypothesis": "H1", "expect": "no_change"}
        self.assertEqual(len(v([ok])["accepted_probes"]), 1)
        self.assertIn("probe_id must be one of", v([{**ok, "probe_id": "friction_x2"}])["probes"][0]["reasons"][0])   # not offered
        self.assertIn("probe_id must be one of", v([{**ok, "probe_id": "heel_x2_rear"}])["probes"][0]["reasons"][0])  # invented
        self.assertIn("duplicate", " ".join(v([ok, ok])["probes"][1]["reasons"]))
        self.assertIn("expect must be", " ".join(v([{**ok, "expect": "maybe"}])["probes"][0]["reasons"]))
        self.assertIn("not an accepted hypothesis", " ".join(v([{**ok, "hypothesis": "H3"}])["probes"][0]["reasons"]))
        self.assertIn("unknown field", " ".join(v([{**ok, "extra": 1}])["probes"][0]["reasons"]))
        avail4 = avail + ["friction_x2"]
        four = [{"probe_id": i, "hypothesis": "H1", "expect": "increase"} for i in avail4]
        res = fa.validate_probe_reply(self.plan(four), self.ev, avail4)
        self.assertEqual(len(res["accepted_probes"]), 3)
        self.assertIn("at most 3", " ".join(res["probes"][3]["reasons"]))
        self.assertTrue(fa.validate_probe_reply({"diagnosis": self.good_reply()["diagnosis"], "probes": []}, self.ev, avail)["schema_errors"])
        self.assertTrue(fa.validate_probe_reply({"diagnosis": self.good_reply()["diagnosis"], "proposals": []}, self.ev, avail)["schema_errors"])

    def test_unavailable_probe_requested_is_repaired_once_then_runs(self):
        bad = self.plan([{"probe_id": "heel_x2_rear", "hypothesis": "H1", "expect": "increase"}])
        out, t, _ = self.run_probe_flow([self.ok(bad), self.ok(self.plan()), self.ok(self.step_b())])
        self.assertEqual((out["status"], len(t.calls), out["repaired"]), ("ok", 3, True))
        self.assertEqual([c["settings"]["purpose"] for c in out["calls"]], ["investigation_probe_plan", "investigation_repair", "investigation"])
        self.assertIn("probe_id must be one of", t.calls[1]["body"]["messages"][-1]["content"])

    # -- repair cap and failures
    def test_one_repair_in_total_step_a_repair_leaves_none_for_step_b(self):
        bad_b = self.good_reply()
        for p in bad_b["proposals"]:
            p["edits"][0]["value"] = 9.0
        bad_a = {"diagnosis": self.good_reply()["diagnosis"], "probes": []}
        out, t, _ = self.run_probe_flow([self.ok(bad_a), self.ok(self.plan()), self.ok(bad_b), self.ok(self.step_b())])
        self.assertEqual(len(t.calls), 3)                      # A, A-repair, B: no second repair
        self.assertEqual(out["status"], "no_valid_proposal")
        self.assertLessEqual(len(out["calls"]), 3)

    def test_step_b_repair_when_step_a_was_clean(self):
        bad_b = self.good_reply()
        for p in bad_b["proposals"]:
            p["edits"][0]["value"] = 9.0
        out, t, led = self.run_probe_flow([self.ok(self.plan()), self.ok(bad_b), self.ok(self.step_b())])
        self.assertEqual((out["status"], len(t.calls), out["repaired"]), ("ok", 3, True))
        self.assertEqual(led.investigation_status("i-p")["requests"], 3)
        self.assertLessEqual(led.investigation_status("i-p")["requests"], led.caps.inv_max_requests)
        self.assertEqual(len(self.runner_calls), 1)            # probes ran once, the repair does not re-run them

    def test_step_a_invalid_after_repair_runs_no_probes(self):
        bad = {"diagnosis": self.good_reply()["diagnosis"], "probes": []}
        out, t, _ = self.run_probe_flow([self.ok(bad), self.ok(bad)])
        self.assertEqual((out["status"], len(t.calls)), ("no_valid_proposal", 2))
        self.assertEqual(self.runner_calls, [])
        self.assertIn("step A", out["error"])
        self.assertEqual(out["probes"]["requested"], [])

    def test_step_a_model_failure_is_recorded_and_not_retried(self):
        out, t, _ = self.run_probe_flow([NebiusError("HTTP 500: boom")])
        self.assertEqual((out["status"], len(t.calls), self.runner_calls), ("model_failed", 1, []))

    def test_step_b_model_failure_keeps_the_probe_results(self):
        out, t, _ = self.run_probe_flow([self.ok(self.plan()), NebiusError("HTTP 500: boom")])
        self.assertEqual((out["status"], len(t.calls)), ("model_failed", 2))
        self.assertIn("step B failed", out["error"])
        self.assertIn("balance_gain_x1_5", out["probes"]["results"])
        self.assertEqual(out["accepted"], [])

    def test_ledger_refusal_before_the_network(self):
        led = self.ledger(caps=Caps(inv_max_requests=0))
        out, t, _ = self.run_probe_flow([self.ok(self.plan())], ledger=led)
        self.assertEqual((t.calls, out["status"], self.runner_calls), ([], "model_failed", []))
        self.assertTrue(out["calls"][0]["budget_refused"])

    def test_ledger_cap_of_one_refuses_step_b_before_the_network(self):
        led = self.ledger(caps=Caps(inv_max_requests=1))
        out, t, _ = self.run_probe_flow([self.ok(self.plan()), self.ok(self.step_b())], ledger=led)
        self.assertEqual(len(t.calls), 1)
        self.assertTrue(out["calls"][1]["budget_refused"])
        self.assertEqual(out["status"], "model_failed")

    def test_no_available_probe_falls_back_to_the_one_step_path(self):
        orig = fa.pb.available_probes
        fa.pb.available_probes = lambda *a, **k: []
        self.addCleanup(setattr, fa.pb, "available_probes", orig)
        out, t, _ = self.run_probe_flow([self.ok(self.good_reply())])
        self.assertEqual((out["status"], len(t.calls), self.runner_calls), ("ok", 1, []))
        self.assertEqual(out["probes"]["available"], [])
        self.assertIn("skipped", out["probes"])

    def test_one_step_path_is_unchanged(self):
        t = Scripted([completion(reply_text(self.good_reply()))])
        out = fa.investigate_once(self.client(t), self.cfg, self.version, self.cr, None, self.ledger(), investigation_id="i-1")
        self.assertEqual((out["status"], len(t.calls)), ("ok", 1))
        self.assertNotIn("probes", out)
        self.assertNotIn("probes", out["evidence"])
        self.assertNotIn(fa.PROBE_STEP_MARK, t.calls[0]["body"]["messages"][0]["content"])


def pb_ids():
    from creature_forge import probes
    return probes.PROBE_IDS


if __name__ == "__main__":
    unittest.main()
