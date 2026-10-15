"""Engineering memory: lesson extraction, bank, deterministic retrieval, evidence block, prompt note, record field, API. No network."""
import copy
import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from creature_forge import evidence as ev
from creature_forge import forge_ai
from creature_forge import interventions as iv
from creature_forge import investigation as inv
from creature_forge import memory as mem
from creature_forge.forge_ai import build_messages, build_reply_schema

try:
    from tests.test_investigation import LIVE_ENV, Base
except ImportError:  # run from inside tests/
    from test_investigation import LIVE_ENV, Base

ROOT = Path(__file__).resolve().parents[1]
FX = Path(__file__).parent / "fixtures" / "forge_ai"
RECORD_DIRS = [ROOT / "experiments" / "forge_loop" / "scoreboard" / "results" / "records",
               ROOT / "experiments" / "forge_loop" / "dev_live_records"]


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def real_records():
    out = []
    for d in RECORD_DIRS:
        for p in sorted(d.glob("i-*.json")):
            out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def fake_lesson(i, kind="push", cid=None, **feat):
    f = {"mode": "experimental", "leg_length_rear": 0.6, "leg_length_front": 0.6, "foot_to_leg": 0.3, "torque_to_weight": 1.0,
         "mass_total": 10.0, "foot_friction": 1.0, "torque_limit": 60.0, **feat}
    return {"lesson_id": f"i-{i:03d}", "created": "2026-10-01T00:00:00Z", "creature_id": cid or f"c-{i:03d}", "kind": kind, "features": f,
            "original": {"aggregate": "FAIL", "score_median": 10.0}, "failure": {"weak_direction": "backward"},
            "probes": [{"probe_id": "foot_x1_5", "observed": "increase", "median_delta": 5.0}],
            "tried": [{"source": "nemotron", "edits": [{"param": "foot_length", "op": "scale", "value": 1.25, "target": "both"}],
                       "category": "morphology", "verdict": "VERIFIED_IMPROVEMENT", "median_diff": 4.0, "n": 12},
                      {"source": "random_baseline", "edits": [{"param": "foot_friction", "op": "scale", "value": 1.1, "target": "both"}],
                       "category": "morphology", "verdict": "NOT_VERIFIED", "median_diff": 0.2, "n": 12}]}


class ExtractionTests(unittest.TestCase):
    def test_only_live_done_records_give_lessons(self):
        recs = real_records()
        self.assertTrue(recs)
        base = next(r for r in recs if r["provenance"] == "LIVE" and r["status"] == "done")
        self.assertIsNotNone(mem.extract_lesson(base))
        self.assertIsNone(mem.extract_lesson({**base, "provenance": "SCRIPTED_MOCK"}))
        for st in ("failed", "model_failed", "no_valid_proposals", "cancelled"):
            self.assertIsNone(mem.extract_lesson({**base, "status": st}))
        self.assertIsNone(mem.extract_lesson({**base, "evidence": None}))
        self.assertIsNone(mem.extract_lesson(None))

    def test_lesson_fields_and_no_model_prose(self):
        for r in real_records():
            les = mem.extract_lesson(r)
            if les is None:
                continue
            self.assertEqual((les["lesson_id"], les["creature_id"], les["kind"]), (r["id"], r["creature"]["cid"], r["spec"]["kind"]))
            self.assertIn("foot_to_leg", les["features"])
            blob = json.dumps(les)
            for h in (r.get("reply") or {}).get("diagnosis", {}).get("hypotheses", []):
                self.assertNotIn(h["mechanism"], blob)
            for key in ("summary", "mechanism", "tradeoffs", "prediction", "diagnosis", "competing"):
                self.assertNotIn(f'"{key}"', blob)
            for t in les["tried"]:
                self.assertIn(t["source"], ("nemotron", "random_baseline", "heuristic", "scripted_mock"))
                self.assertTrue(t["verdict"])
                self.assertEqual(set(t), {"source", "edits", "category", "verdict", "median_diff", "n"})
            for p in les["probes"]:
                self.assertEqual(set(p), {"probe_id", "observed", "median_delta"})

    def test_tried_covers_validated_arms_with_verdicts(self):
        r = json.loads((RECORD_DIRS[1] / "i-172b6a48a0ad.json").read_text(encoding="utf-8"))
        les = mem.extract_lesson(r)
        self.assertEqual({t["source"] for t in les["tried"]}, {"nemotron", "random_baseline"})
        ai = next(t for t in les["tried"] if t["source"] == "nemotron")
        self.assertEqual((ai["verdict"], ai["median_diff"], ai["n"]), ("VERIFIED_IMPROVEMENT", 4.375, 12))
        self.assertEqual(ai["edits"], [{"param": "foot_length", "op": "scale", "value": 1.25, "target": "rear"}])
        self.assertEqual({p["probe_id"]: p["observed"] for p in les["probes"]},
                         {"friction_x2": "decrease", "torque_x1_5": "no_change", "foot_x1_5": "increase"})
        self.assertEqual(les["failure"]["weak_direction"], "backward")

    def test_stand_signature(self):
        r = json.loads((RECORD_DIRS[1] / "i-d62a72f585fb.json").read_text(encoding="utf-8"))
        les = mem.extract_lesson(r)
        self.assertEqual(les["kind"], "stand")
        self.assertIn("fell", les["failure"])


class BankTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "memory" / "lessons.jsonl"

    def test_add_is_idempotent_and_append_only(self):
        b = mem.MemoryBank(self.path)
        self.assertTrue(b.add(fake_lesson(1)))
        self.assertFalse(b.add(fake_lesson(1, kind="stand")))
        self.assertTrue(b.add(fake_lesson(2)))
        self.assertEqual(len(b), 2)
        self.assertEqual(len(self.path.read_text(encoding="utf-8").splitlines()), 2)
        self.assertFalse(b.add(None))

    def test_build_from_archived_records_is_idempotent(self):
        b = mem.MemoryBank(self.path)
        n = sum(b.build_from(d) for d in RECORD_DIRS)
        self.assertGreater(n, 10)
        self.assertEqual(sum(b.build_from(d) for d in RECORD_DIRS), 0)
        self.assertEqual(len(b), n)

    def test_retrieval_is_deterministic_and_independent_of_order_and_size(self):
        lessons = [fake_lesson(i, foot_to_leg=0.1 + 0.05 * i, torque_to_weight=0.5 + 0.1 * i) for i in range(12)]
        q = fake_lesson(99, foot_to_leg=0.3)["features"]
        ids = {}
        for trial in range(3):
            order = lessons[:]
            random.Random(trial).shuffle(order)
            b = mem.MemoryBank(Path(self._tmp.name) / f"b{trial}.jsonl")
            for les in order:
                b.add(les)
            ids[trial] = [(s, x["lesson_id"]) for s, x in b.retrieve(q, "push", k=4)]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[1], ids[2])
        # a lesson's similarity does not depend on what else is in the bank
        small = mem.MemoryBank(Path(self._tmp.name) / "small.jsonl")
        small.add(lessons[5])
        (s_small, _), = small.retrieve(q, "push", k=3)
        full = {x["lesson_id"]: sim for sim, x in mem.MemoryBank(Path(self._tmp.name) / "b0.jsonl").retrieve(q, "push", k=12)}
        self.assertEqual(s_small, full["i-005"])
        sims = [s for s, _ in ids[0]]
        self.assertEqual(sims, sorted(sims, reverse=True))

    def test_similarity_properties(self):
        a = fake_lesson(1)["features"]
        self.assertAlmostEqual(mem.similarity(a, a), 1.0)
        far = fake_lesson(2, foot_to_leg=0.9, torque_to_weight=2.5)["features"]
        near = fake_lesson(3, foot_to_leg=0.32)["features"]
        self.assertGreater(mem.similarity(a, near), mem.similarity(a, far))
        self.assertEqual(mem.similarity(a, far), mem.similarity(far, a))
        self.assertLess(mem.similarity(a, {**a, "mode": "guided"}), 1.0)

    def test_excludes_same_creature_and_other_kinds(self):
        b = mem.MemoryBank(self.path)
        b.add(fake_lesson(1, cid="c-mine"))
        b.add(fake_lesson(2, cid="c-other"))
        b.add(fake_lesson(3, kind="stand", cid="c-third"))
        q = fake_lesson(0)["features"]
        got = [x["lesson_id"] for _, x in b.retrieve(q, "push", k=5, exclude_creature="c-mine")]
        self.assertEqual(got, ["i-002"])
        self.assertEqual([x["lesson_id"] for _, x in b.retrieve(q, "stand", k=5)], ["i-003"])
        self.assertEqual(b.retrieve(q, "walk", k=5), [])
        self.assertEqual([x["lesson_id"] for _, x in b.retrieve(q, "push", k=5, exclude_lessons=("i-001",))], ["i-002"])


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.v, self.c = load("version_guided.json"), load("challenge_push.json")
        self.hits = [(0.8 - 0.1 * i, fake_lesson(i, cid=f"c-{i}")) for i in range(5)]

    def test_memory_off_is_unchanged(self):
        base = ev.build_evidence(self.v, self.c)
        self.assertNotIn("memory", base)
        self.assertEqual(json.dumps(base, sort_keys=True), json.dumps(ev.build_evidence(self.v, self.c, None, memory=None), sort_keys=True))
        self.assertEqual(base, ev.build_evidence(self.v, self.c, memory=[]))
        allowed = iv.editable_params(self.v, "push")
        msgs = build_messages(base, allowed=allowed)
        self.assertNotIn("PAST CASES", msgs[0]["content"])
        self.assertNotIn("memory", msgs[1]["content"])

    def test_block_shape_size_and_citable_paths(self):
        blk = ev.memory_block(self.hits)
        self.assertTrue(blk)
        self.assertLessEqual(ev._sz(blk), ev.MEMORY_LIMIT_BYTES)
        self.assertLessEqual(ev._sz(ev.memory_block(self.hits[:1])), ev.MEMORY_LIMIT_BYTES)
        e0 = blk[0]
        self.assertEqual(e0["similarity"], 0.8)
        self.assertEqual(e0["challenge"], "push")
        self.assertEqual(e0["tried"][0]["verdict"], "VERIFIED_IMPROVEMENT")   # verified first
        self.assertEqual(e0["probes"][0], {"probe_id": "foot_x1_5", "observed": "increase"})
        pack = ev.build_evidence(self.v, self.c, memory=self.hits)
        self.assertEqual(pack["memory"], blk)
        self.assertLessEqual(ev.pack_size(pack) - ev.pack_size({k: v for k, v in pack.items() if k != "memory"}), ev.MEMORY_LIMIT_BYTES + 20)
        paths = ev.leaf_paths(pack)
        for p in ("memory[0].similarity", "memory[0].creature.foot_to_leg", "memory[0].tried[0].verdict", "memory[0].tried[0].median_diff",
                  "memory[0].probes[0].observed"):
            self.assertIn(p, paths)
            self.assertEqual(ev.resolve(pack, p), ev.resolve(pack, p))
        self.assertTrue(set(ev.leaf_paths({k: v for k, v in pack.items() if k != "memory"})) <= set(paths))

    def test_worse_arms_rank_before_not_verified(self):
        les = fake_lesson(1)
        les["tried"] = [{"source": "heuristic", "edits": [], "category": "morphology", "verdict": "NOT_VERIFIED", "median_diff": 0.1, "n": 12},
                        {"source": "nemotron", "edits": [{"param": "torque_limit", "op": "scale", "value": 0.8, "target": "both"}],
                         "category": "morphology", "verdict": "WORSE", "median_diff": -3.0, "n": 12}]
        e = ev.memory_block([(0.5, les)])[0]
        self.assertEqual([t["verdict"] for t in e["tried"]], ["WORSE", "NOT_VERIFIED"])

    def test_oversized_memory_is_truncated_to_the_cap(self):
        many = []
        for i in range(3):
            les = fake_lesson(i)
            les["tried"] = les["tried"] * 8
            les["probes"] = les["probes"] * 8
            many.append((0.9, les))
        blk = ev.memory_block(many)
        self.assertLessEqual(ev._sz(blk), ev.MEMORY_LIMIT_BYTES)

    def test_prompt_note_and_schema_enum(self):
        pack = ev.build_evidence(self.v, self.c, memory=self.hits[:2])
        allowed = iv.editable_params(self.v, "push")
        msgs = build_messages(pack, allowed=allowed)
        self.assertIn(forge_ai.MEMORY_NOTE, msgs[0]["content"])
        self.assertIn("memory[0].similarity=", msgs[1]["content"])
        enum = json.dumps(build_reply_schema(pack, allowed))
        self.assertIn("memory[0].tried[0].verdict", enum)
        self.assertEqual(msgs[0]["content"].split(forge_ai.MEMORY_NOTE)[0].rstrip("\n"),
                         build_messages({k: v for k, v in pack.items() if k != "memory"}, allowed=allowed)[0]["content"])


class InvestigationMemoryTests(Base):
    def seed_bank(self, *lessons):
        bank = mem.MemoryBank.for_forge_dir(self.dir)
        for les in lessons:
            bank.add(les)
        return bank

    def test_default_record_says_memory_not_used(self):
        rec = self.run_inv()
        self.assertEqual(rec["memory"], {"used": False, "retrieved": [], "bank_size": None, "k": None})
        self.assertIn("memory", inv.RECORD_KEYS)
        self.assertNotIn("memory", rec["evidence"])
        self.assertNotIn("PAST CASES", json.dumps(rec["model_calls"]))

    def test_memory_on_retrieves_other_creatures_only(self):
        self.seed_bank(fake_lesson(1, cid="c-other"), fake_lesson(2, cid=self.cid), fake_lesson(3, kind="stand", cid="c-x"))
        rec = self.run_inv(memory=True, memory_k=3)
        m = rec["memory"]
        self.assertTrue(m["used"])
        self.assertEqual((m["bank_size"], m["k"]), (3, 3))
        self.assertEqual([r["lesson_id"] for r in m["retrieved"]], ["i-001"])
        self.assertTrue(0 < m["retrieved"][0]["similarity"] <= 1)
        self.assertEqual(len(rec["evidence"]["memory"]), 1)
        self.assertEqual(rec["status"], "done")
        self.assertTrue(all(h["status"] == "accepted" for h in rec["validation"]["hypotheses"]))

    def test_memory_on_with_empty_bank_adds_no_block(self):
        rec = self.run_inv(memory=True)
        self.assertEqual(rec["memory"], {"used": True, "retrieved": [], "bank_size": 0, "k": 3})
        self.assertNotIn("memory", rec["evidence"])

    def test_explicit_bank_object(self):
        other = mem.MemoryBank(Path(self._tmp.name) / "elsewhere.jsonl")
        other.add(fake_lesson(7, cid="c-other"))
        rec = self.run_inv(memory=True, memory_bank=other, memory_k=1)
        self.assertEqual([r["lesson_id"] for r in rec["memory"]["retrieved"]], ["i-007"])

    def test_lesson_auto_added_only_for_live_done_with_cf_memory(self):
        bank = mem.MemoryBank.for_forge_dir(self.dir)
        led = inv.InferenceLedger(self.dir / "live_ledger.jsonl")
        env_off = {k: v for k, v in os.environ.items() if k != "CF_MEMORY"}
        with mock.patch.dict(os.environ, {**env_off, **LIVE_ENV}, clear=True), mock.patch.object(inv, "api_key_present", return_value=True):
            self.run_inv("live", ledger=led, client_factory=self.factory())
        self.assertEqual(len(bank), 0)                      # CF_MEMORY unset: bank frozen
        with mock.patch.dict(os.environ, {**env_off, "CF_MEMORY": "1"}, clear=True):
            self.run_inv()                                   # scripted: never a lesson
        self.assertEqual(len(bank), 0)
        with mock.patch.dict(os.environ, {**env_off, **LIVE_ENV, "CF_MEMORY": "1"}, clear=True), \
                mock.patch.object(inv, "api_key_present", return_value=True):
            rec = self.run_inv("live", ledger=led, client_factory=self.factory())
            self.assertEqual(rec["status"], "done")
            self.assertEqual([x["lesson_id"] for x in bank.lessons()], [rec["id"]])
            self.assertEqual(bank.lessons()[0]["creature_id"], self.cid)


class MemoryApiTests(unittest.TestCase):
    def test_memory_endpoint_and_flag(self):
        try:
            from tests.test_forge_api import InvestigationApiCase
        except ImportError:
            from test_forge_api import InvestigationApiCase

        class Case(InvestigationApiCase):
            def runTest(self):
                pass

        c = Case()
        c.setUp()
        try:
            self.assertEqual(c.c.get("/api/forge/memory").json(), {"bank_size": 0, "lessons": []})
            mem.MemoryBank.for_forge_dir(c.dir).add(fake_lesson(1, cid="c-other"))
            out = c.c.get("/api/forge/memory").json()
            self.assertEqual((out["bank_size"], out["lessons"][0]["lesson_id"], out["lessons"][0]["verified"]), (1, "i-001", 1))
            cr = c.create(mode="experimental")
            run_id = c.run_challenge(cr["id"])
            o = c.investigate(cr["id"], run_id, memory=True)
            rec = c.c.get(f"/api/forge/investigations/{o['investigation_id']}").json()
            self.assertTrue(rec["memory"]["used"])
            self.assertEqual(rec["memory"]["bank_size"], 1)
            o2 = c.investigate(cr["id"], run_id)
            self.assertFalse(c.c.get(f"/api/forge/investigations/{o2['investigation_id']}").json()["memory"]["used"])
            r = c.c.post(f"/api/forge/creatures/{cr['id']}/versions/1/investigations", json={"run_id": run_id, "mode": "scripted", "memory": 5})
            self.assertEqual(r.status_code, 422)
        finally:
            c.doCleanups()


if __name__ == "__main__":
    unittest.main()
