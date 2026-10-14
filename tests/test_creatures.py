import json
import tempfile
import threading
import unittest
from pathlib import Path

from creature_forge.controller import GaitParams
from creature_forge.creatures import (CreatureStore, canonical_json, content_hash, default_controllers,
                                      normalize_body, normalize_controllers, seed_block)
from creature_forge.sandbox import SandboxBody

VERIFIED = {"verdict": {"status": "VERIFIED_IMPROVEMENT", "rule": "verdict_v1"}}


def body(**kw) -> dict:
    return {**SandboxBody().as_dict(), **kw}


def change(status="VERIFIED_IMPROVEMENT") -> dict:
    return {"edits": [{"param": "foot_length", "op": "scale", "value": 1.3, "target": "both"}], "category": "morphology",
            "rationale": "wider support", "source": "nemotron", "verdict": {"status": status, "rule": "verdict_v1"}}


class StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "forge"
        self.store = CreatureStore(self.root)

    def make(self, mode="guided", **kw):
        return self.store.create(name="Stubby", body=body(**kw), mode=mode, drawing={"strokes": [{"id": "a"}]})


class CreateTests(StoreCase):
    def test_nothing_is_created_by_constructing_or_listing(self):
        self.assertFalse(self.root.exists())
        self.assertEqual(self.store.list(), [])
        self.assertFalse(self.root.exists())

    def test_create_makes_explicit_per_leg_values_and_version_one(self):
        c = self.make()
        self.assertRegex(c["id"], r"^c-[0-9a-f]{8}$")
        self.assertEqual(c["current"], 1)
        v = c["versions"][0]
        self.assertEqual((v["n"], v["parent"], v["origin"], v["change"]), (1, None, "user", None))
        for k in ("thigh_length", "shank_length", "foot_length"):
            self.assertEqual(v["body"][k + "_r"], v["body"][k])
        self.assertEqual(v["body"]["pose"], [0.0] * 7)
        self.assertEqual(v["controllers"], {"stand": GaitParams().as_dict(), "walk": None})
        self.assertEqual(v["drawing"]["strokes"], [{"id": "a"}])
        self.assertIsNone(v["drawing"]["approximation"])
        self.assertEqual(json.loads((self.root / "creatures" / f"{c['id']}.json").read_text(encoding="utf-8")), c)

    def test_content_hash_is_canonical_and_stable(self):
        c = self.make()
        v = c["versions"][0]
        self.assertEqual(v["content_hash"], content_hash(v["body"], v["controllers"]))
        a = {"b": 1.5, "a": [1, 2]}
        self.assertEqual(canonical_json(a), canonical_json({"a": [1, 2], "b": 1.5}))
        self.assertEqual(canonical_json(a), '{"a":[1,2],"b":1.5}')
        self.assertEqual(content_hash(v["body"], v["controllers"]), self.make()["versions"][0]["content_hash"])
        self.assertNotEqual(v["content_hash"], self.make(torso_mass=6.0)["versions"][0]["content_hash"])
        with self.assertRaises(ValueError):
            canonical_json({"x": float("nan")})

    def test_integers_are_stored_as_floats_so_the_hash_does_not_depend_on_spelling(self):
        a = self.make(torso_mass=5)["versions"][0]["content_hash"]
        b = self.make(torso_mass=5.0)["versions"][0]["content_hash"]
        self.assertEqual(a, b)

    def test_guided_rejects_asymmetric_legs_and_scientific_bounds(self):
        with self.assertRaisesRegex(ValueError, "symmetric"):
            self.make(thigh_length_r=0.4)
        with self.assertRaisesRegex(ValueError, "guided range"):
            self.make(torso_mass=30.0)
        with self.assertRaisesRegex(ValueError, "guided range"):
            self.make(foot_length_r=0.5, foot_length=0.5)
        self.assertEqual(self.store.list(), [])

    def test_experimental_allows_wide_and_asymmetric_but_not_beyond_sandbox_bounds(self):
        c = self.make("experimental", torso_mass=30.0, thigh_length_r=0.45)
        self.assertEqual(c["versions"][0]["body"]["thigh_length_r"], 0.45)
        self.assertEqual(c["versions"][0]["mode"], "experimental")
        with self.assertRaisesRegex(ValueError, "sandbox range"):
            self.make("experimental", torso_mass=500.0)

    def test_malformed_bodies_are_refused_with_a_reason(self):
        for bad, text in [({**body(), "wings": 2}, "unknown body field"),
                          ({k: v for k, v in body().items() if k != "torso_mass"}, "missing"),
                          (body(torso_mass=float("nan")), "finite"),
                          (body(torso_mass=True), "finite"),
                          (body(torso_mass="5"), "finite"),
                          (body(pose=[0.0] * 6), "7 numbers"),
                          (body(pose=[0.0, 3.0, 0, 0, 0, 0, 0]), "joint range"),
                          ("nope", "object")]:
            with self.assertRaisesRegex(ValueError, text, msg=str(bad)[:60]):
                normalize_body(bad, "experimental")
        with self.assertRaisesRegex(ValueError, "mode"):
            normalize_body(body(), "wild")

    def test_name_and_drawing_validation(self):
        for name in ("", "   ", "x" * 81, None):
            with self.assertRaises(ValueError):
                self.store.create(name=name, body=body(), mode="guided", drawing={})
        with self.assertRaises(ValueError):
            self.store.create(name="a", body=body(), mode="guided", drawing=[1])
        with self.assertRaises(ValueError):
            self.store.create(name="a", body=body(), mode="guided", drawing={"x": float("nan")})

    def test_ids_are_unique_across_threads_and_files_are_never_partial(self):
        ids, errs = [], []

        def worker():
            try:
                ids.append(self.make()["id"])
            except Exception as exc:  # pragma: no cover - failure path
                errs.append(exc)
        ts = [threading.Thread(target=worker) for _ in range(12)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errs, [])
        self.assertEqual(len(set(ids)), 12)
        self.assertEqual(len(self.store.list()), 12)
        self.assertEqual([p.name for p in (self.root / "creatures").iterdir() if not p.name.endswith(".json")], [])


class ReadTests(StoreCase):
    def test_list_get_version_and_persistence_across_instances(self):
        a, b = self.make(), self.make("experimental")
        listed = self.store.list()
        self.assertEqual({s["id"] for s in listed}, {a["id"], b["id"]})
        self.assertEqual(set(listed[0]), {"id", "name", "current", "n_versions", "created"})
        again = CreatureStore(self.root)
        self.assertEqual(again.get(a["id"]), a)
        self.assertEqual(again.version(a["id"], 1)["n"], 1)

    def test_missing_creature_version_and_hostile_ids(self):
        c = self.make()
        for cid in ("c-00000000", "../etc/passwd", "", None, "c-1"):
            with self.assertRaises(KeyError):
                self.store.get(cid)
        with self.assertRaises(KeyError):
            self.store.version(c["id"], 2)

    def test_unreadable_file_is_skipped_in_listing(self):
        c = self.make()
        (self.root / "creatures" / "c-deadbeef.json").write_text("{not json", encoding="utf-8")
        self.assertEqual([s["id"] for s in self.store.list()], [c["id"]])


class LineageTests(StoreCase):
    def test_accept_refuses_unless_verified(self):
        c = self.make()
        for status in ("NOT_VERIFIED", "WORSE", "INCONCLUSIVE", None):
            with self.assertRaisesRegex(ValueError, "VERIFIED_IMPROVEMENT"):
                self.store.accept(c["id"], parent_n=1, body=body(), controllers=default_controllers(), change=change(status))
        for bad in ({}, {"verdict": None}, {"verdict": "VERIFIED_IMPROVEMENT"}, None):
            with self.assertRaises(ValueError):
                self.store.accept(c["id"], parent_n=1, body=body(), controllers=default_controllers(), change=bad)
        self.assertEqual(self.store.get(c["id"])["current"], 1)
        self.assertEqual(len(self.store.get(c["id"])["versions"]), 1)

    def test_accept_appends_a_child_version_and_moves_current(self):
        c = self.make()
        new_body = body(foot_length=0.2, foot_length_r=0.2)
        rec = self.store.accept(c["id"], parent_n=1, body=new_body, controllers=default_controllers(), change=change())
        self.assertEqual(rec["current"], 2)
        v2 = rec["versions"][1]
        self.assertEqual((v2["n"], v2["parent"], v2["origin"], v2["mode"]), (2, 1, "ai_accepted", "guided"))
        self.assertEqual(v2["body"]["foot_length"], 0.2)
        self.assertEqual(v2["change"]["verdict"]["status"], "VERIFIED_IMPROVEMENT")
        self.assertNotEqual(v2["content_hash"], rec["versions"][0]["content_hash"])
        self.assertEqual(rec["versions"][0], c["versions"][0])  # the parent is untouched

    def test_accept_validates_the_new_body_in_the_creatures_mode(self):
        c = self.make()  # guided
        with self.assertRaisesRegex(ValueError, "symmetric"):
            self.store.accept(c["id"], parent_n=1, body=body(foot_length_r=0.2), controllers=default_controllers(), change=change())
        with self.assertRaises(ValueError):
            self.store.accept(c["id"], parent_n=1, body=body(), controllers={"stand": {"kp": 1e9}}, change=change())
        with self.assertRaises(KeyError):
            self.store.accept(c["id"], parent_n=7, body=body(), controllers=default_controllers(), change=change())
        self.assertEqual(len(self.store.get(c["id"])["versions"]), 1)

    def test_revert_and_branch_never_delete(self):
        c = self.make()
        self.store.accept(c["id"], parent_n=1, body=body(torso_mass=6.0), controllers=default_controllers(), change=change())
        rec = self.store.set_current(c["id"], 1)
        self.assertEqual((rec["current"], len(rec["versions"])), (1, 2))
        rec = self.store.accept(c["id"], parent_n=1, body=body(torso_mass=7.0), controllers=default_controllers(), change=change())
        self.assertEqual([(v["n"], v["parent"]) for v in rec["versions"]], [(1, None), (2, 1), (3, 1)])
        self.assertEqual(rec["current"], 3)
        self.assertEqual(self.store.set_current(c["id"], 2)["current"], 2)  # forward again
        self.assertEqual(len(self.store.get(c["id"])["versions"]), 3)

    def test_set_current_errors(self):
        c = self.make()
        with self.assertRaises(KeyError):
            self.store.set_current(c["id"], 5)
        with self.assertRaises(KeyError):
            self.store.set_current("c-00000000", 1)
        for bad in ("1", True, 1.0):
            with self.assertRaises(ValueError):
                self.store.set_current(c["id"], bad)


class ControllerTests(unittest.TestCase):
    def test_defaults_and_walk_vector_rules(self):
        self.assertEqual(normalize_controllers(None), default_controllers())
        self.assertEqual(normalize_controllers({"stand": {"kp": 100.0}})["stand"]["kp"], 100.0)
        ok = normalize_controllers({"walk": {"vector": [0.0] * 15, "provenance": {"kind": "adapted"}}})
        self.assertEqual(len(ok["walk"]["vector"]), 15)
        for bad in ({"walk": {"vector": [0.0] * 14}}, {"walk": [0.0] * 15}, {"walk": {"vector": [float("inf")] * 15}},
                    {"stand": {"bogus": 1}}, {"jump": None}, {"stand": [1]}, "x"):
            with self.assertRaises(ValueError, msg=str(bad)):
                normalize_controllers(bad)


class SeedBlockTests(unittest.TestCase):
    def test_deterministic_namespaced_and_varying(self):
        a = seed_block("c-1a2b3c4d", 1, 0, "challenge", 8)
        self.assertEqual(a, seed_block("c-1a2b3c4d", 1, 0, "challenge", 8))
        self.assertEqual(len(a), 8)
        self.assertEqual(a, tuple(range(a[0], a[0] + 8)))
        self.assertTrue(100_000 <= a[0] < 900_000)
        self.assertNotEqual(a, seed_block("c-1a2b3c4d", 1, 1, "challenge", 8))
        self.assertNotEqual(a, seed_block("c-1a2b3c4d", 2, 0, "challenge", 8))
        self.assertNotEqual(a, seed_block("c-1a2b3c4d", 1, 0, "screen", 8))


if __name__ == "__main__":
    unittest.main()
