"""W2: the recorded Nemotron case (gen-0137 one_side_weakness), its derived files and `/api/nemotron`. No physics, no model call."""
import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import w2_case_build as wb  # noqa: E402

from creature_forge.studio.nemotron_api import W2_DIR, create_nemotron_router  # noqa: E402

CASE = W2_DIR / "gen0137_one_side_weakness"
FULL_ROOT = Path(os.environ.get("CF_W2_FULL_ROOT", ROOT.parent / "Creature-Forge" / "artifacts" / "vm" / "hdb" / "artifacts" / "hdb"))
SECRET_RES = (re.compile(r"Bearer\s"), re.compile(r"v1\.[A-Za-z0-9_\-.]{40,}"), re.compile(r"sk-[A-Za-z0-9]{20,}"),
              re.compile(r"NEBIUS_API_KEY\s*="))


def _no_sim(*a, **k):
    raise AssertionError("W2 code must not simulate")


def _load(name: str) -> dict:
    return json.loads((CASE / name).read_text(encoding="utf-8"))


@mock.patch("creature_forge.hidden_plant.plant_rollout", _no_sim)
@mock.patch("creature_forge.recovery.run_walk_seeds", _no_sim)
class W2CaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.man, cls.recs = wb.load_excerpt()
        cls.case = _load("case.json")
        cls.cross = _load("cross_instance.json")

    def test_case_is_rebuilt_exactly_from_the_pinned_excerpt(self):
        self.assertEqual(wb.dumps(wb.build_case(self.man, self.recs)), (CASE / "case.json").read_text(encoding="utf-8"))

    def test_tampered_excerpt_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            for f in CASE.iterdir():
                if f.is_file():
                    shutil.copy(f, d)
            p = Path(d) / "A3.jsonl"
            p.write_bytes(p.read_bytes().replace(b'"FULL_RECOVERY"', b'"FULL_RECOVERX"', 1))
            with self.assertRaises(wb.CaseError):
                wb.load_excerpt(d)

    def test_the_fork_is_clean_and_is_the_experiment_choice(self):
        c = self.case
        self.assertTrue(c["shared"]["identical_in_all_arms"])
        self.assertEqual(c["shared"]["observation"]["n_walking"], 0)
        self.assertEqual([round(b["w"], 4) for b in c["shared"]["belief_after_observation"][:2]], [0.8954, 0.1046])
        nb = c["fork"]["notebook"]
        self.assertEqual(nb["engine_recommendation"], "experiment cf:freq@x1.2")
        self.assertEqual({x["eig"] for x in nb["candidates"]}, {0.34})        # every candidate shows the same EIG
        cand = {x["id"]: x["predicted_walking"] for x in nb["candidates"]}
        self.assertEqual(cand["cf:freq@x0.85"][:2], [2, 0])                   # right vs left: contrast in walking
        self.assertEqual(cand["cf:freq@x1.2"][:2], [1, 1])                    # no contrast in walking
        self.assertEqual((c["fork"]["nemotron"]["experiment"], c["fork"]["engine"]["experiment"]), ("cf:freq@x0.85", "cf:freq@x1.2"))
        self.assertEqual((c["fork"]["nemotron"]["eig"], c["fork"]["nemotron"]["best_eig"]), (0.339, 0.34))
        self.assertFalse(c["fork"]["nemotron"]["registered_prediction"])      # no valid registered prediction
        self.assertIn("missing", c["fork"]["nemotron"]["prediction_issue"])
        self.assertTrue(c["fork"]["a4_same_choice"])
        self.assertEqual(c["determinism"], {"observation_identical_all_arms": True, "x1_identical_A3_A4": True,
                                            "belief_after_x1_identical_A3_A4": True})

    def test_measurements_beliefs_repairs_and_verification(self):
        a3, a1, a4 = (self.case["arms"][k] for k in ("A3", "A1e", "A4"))
        self.assertEqual([e["n_walking"] for e in a3["experiments"]], [0, 3])
        self.assertEqual([e["n_walking"] for e in a1["experiments"]], [0, 2])
        self.assertEqual(a3["belief_history"][1]["top"][0], {"structure": [["actuator_strength", "right"]], "w": 1.0})
        self.assertEqual((a1["belief_history"][1]["top"][0]["structure"], round(a1["belief_history"][1]["top"][0]["w"], 3)), ([["actuator_strength", "left"]], 0.998))
        self.assertTrue(a3["final_belief"]["correct"] and a4["final_belief"]["correct"])
        self.assertFalse(a1["final_belief"]["correct"])
        hyps = [h for s in a3["steps"] for h in s["result"].get("hypotheses", [])]
        self.assertEqual(len(hyps), 4)
        self.assertTrue(all(h["weight"] == 0.0 for h in hyps))               # Nemotron's hypotheses added no belief
        self.assertEqual(a3["steps"][-1]["action"]["action"], "delegate_repair")
        self.assertEqual([(d["index"], d["check"]) for d in a3["designs"] if d["check"]], [(2, [6, 8]), (3, [11, 16]), (4, [5, 16])])
        self.assertEqual([(d["index"], d["check"]) for d in a1["designs"] if d["check"]], [(2, [3, 8]), (3, [12, 16]), (4, [11, 16])])
        self.assertEqual((a3["submitted"]["source"], a1["submitted"]["source"]), ("twin:cma:leg_length", "repair:leg_length"))
        v = {k: (x["verification"]["status"], x["verification"]["walking"], x["verification"]["n"]) for k, x in self.case["arms"].items()}
        self.assertEqual(v, {"A3": ("FULL_RECOVERY", 23, 24), "A1e": ("PARTIAL_IMPROVEMENT", 20, 24), "A4": ("PARTIAL_IMPROVEMENT", 19, 24)})
        self.assertEqual((a3["provenance"], a1["provenance"], a4["provenance"]), ("LIVE", "NO_AI", "LIVE"))
        self.assertIsNone(a1["model"])
        self.assertEqual(a3["costs"]["llm_calls"], 4)

    def test_cross_instance_reproduces_the_stage2_report(self):
        g = self.cross["aggregates"]
        self.assertEqual(g["n"], 36)
        self.assertEqual(g["full"], {"A1e": 14, "A3": 15, "A4": 14})
        self.assertEqual(g["full_discordant_A3_vs_A1e"], {"A3_only": 4, "A1e_only": 3})
        self.assertEqual(g["mcnemar_one_sided_p_A3_gt_A1e"], 0.5)
        self.assertEqual(g["map_correct"], {"A1e": 29, "A3": 28, "A4": 29})
        self.assertEqual(g["map_and_full_both_favour_A3"], [wb.INSTANCE_ID])
        self.assertTrue(all(c["in_ledger"] == 1 for arm in ("A3", "A4") for c in self.cross["ledger"]["this_case"][arm]))
        report = (ROOT / "docs" / "STAGE2_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("| Single mechanism, n = 36: FULL | 14 | 12 | **15** | 14 |", report)
        self.assertIn("Single: A1e 29/36, A2 31, A3 28, A4 29.", report)

    @unittest.skipUnless((FULL_ROOT / wb.FULL_FILES["A3"][0]).is_file(), "full Stage 2 transfer files not on this machine")
    def test_cross_instance_is_rebuilt_exactly_from_the_full_files(self):
        self.assertEqual(wb.dumps(wb.build_cross(str(FULL_ROOT), self.man, self.recs)),
                         (CASE / "cross_instance.json").read_text(encoding="utf-8"))

    def test_every_study_row_quotes_its_source(self):
        s = json.loads((W2_DIR / "studies.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(s["studies"]), 15)
        for r in s["studies"]:
            text = (ROOT / r["source"]).read_text(encoding="utf-8")
            self.assertIn(r["quote"], text, r["id"])
        do1 = next(r for r in s["studies"] if r["id"] == "do1")
        self.assertIn("NO_AI", do1["credited_to"])
        favourable = [r["id"] for r in s["studies"] if r["direction"] == "favourable"]
        self.assertEqual(favourable, ["forge-scoreboard"])     # the only pre-registered result in Nemotron's favour

    def test_no_secret_like_strings_in_w2_files(self):
        for p in W2_DIR.rglob("*"):
            if p.is_file():
                text = p.read_text(encoding="utf-8", errors="replace")
                for rx in SECRET_RES:
                    self.assertIsNone(rx.search(text), f"{p}: {rx.pattern}")


@mock.patch("creature_forge.hidden_plant.plant_rollout", _no_sim)
@mock.patch("creature_forge.recovery.run_walk_seeds", _no_sim)
class NemotronApiTests(unittest.TestCase):
    def _client(self, **kw) -> TestClient:
        app = FastAPI()
        app.include_router(create_nemotron_router(**kw))
        return TestClient(app)

    def test_serves_the_pinned_case_and_marks_playback(self):
        r = self._client().get("/api/nemotron/case")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["playback"], "RECORDED_LIVE")
        self.assertEqual(j["case"]["instance_id"], wb.INSTANCE_ID)
        self.assertTrue(j["replays"]["available"])
        unpinned = self._client(replay_sums_sha256=None).get("/api/nemotron/case").json()["replays"]
        self.assertFalse(unpinned["available"])                    # never served without the pinned export hash
        self.assertIn("approval", unpinned["reason"])
        self.assertEqual(j["cross"]["aggregates"]["full"]["A3"], 15)

    def test_tampered_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(W2_DIR, d, dirs_exist_ok=True)
            p = Path(d) / "studies.json"
            p.write_text(p.read_text(encoding="utf-8").replace("p = 0.031", "p = 0.001"), encoding="utf-8")
            r = self._client(w2_dir=Path(d)).get("/api/nemotron/case")
            self.assertEqual(r.status_code, 503)

    def test_damaged_plant_replays_are_served_and_match_the_record(self):
        c = self._client()
        st = c.get("/api/nemotron/case").json()["replays"]
        self.assertTrue(st["available"], st.get("reason"))
        self.assertEqual(st["fidelity"]["fk_max_err_m"], 0.0)
        self.assertEqual(st["environment"]["mujoco"], "3.15.0")
        walk = {k: sum(r["walking"] for r in v["rows"]) for k, v in st["validation"].items()}
        self.assertEqual(walk, {"nominal": 0, "a3_submitted": 23, "a1e_submitted": 20})     # = case.json verification
        case = json.loads((CASE / "case.json").read_text(encoding="utf-8"))
        self.assertEqual(st["experiments"]["x1_nem"]["seeds"], case["arms"]["A3"]["experiments"][1]["seeds"])
        r = c.get(f"/api/nemotron/replay/x1_nem/{st['experiments']['x1_nem']['seeds'][2]}")
        self.assertEqual(r.status_code, 200)
        p = r.json()
        rec = next(s for s in case["arms"]["A3"]["experiments"][1]["per_seed"] if s["seed"] == p["seed"])
        ev = p["w2_demo"]["evidence"]["features"]
        shared = [k for k in rec if k != "seed" and k in ev]
        self.assertGreaterEqual(len(shared), 8)
        self.assertEqual({k: ev[k] for k in shared}, {k: rec[k] for k in shared})   # the replay carries the recorded features
        self.assertEqual(len(p["events"]), 1)                       # this start falls (recorded time upright 1.726 s)
        self.assertEqual(c.get("/api/nemotron/replay/x1_nem/1").status_code, 404)
        self.assertEqual(c.get("/api/nemotron/replay/../etc/1").status_code, 404)
        self.assertEqual(c.get("/api/nemotron/replay/bogus/1").status_code, 422)

    def test_tampered_replay_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(CASE / "plant_replays", d, dirs_exist_ok=True)
            p = next((Path(d) / "payloads").glob("a3_submitted_*.json"))
            p.write_bytes(p.read_bytes().replace(b'"seed":', b'"seed": ', 1))
            c = self._client(replay_dir=Path(d))
            seed = p.stem.rsplit("_", 1)[1]
            self.assertEqual(c.get(f"/api/nemotron/replay/a3_submitted/{seed}").status_code, 503)

    def test_wrong_sums_pin_is_refused(self):
        self.assertEqual(self._client(sums_sha256="0" * 64).get("/api/nemotron/case").status_code, 503)


if __name__ == "__main__":
    unittest.main()
