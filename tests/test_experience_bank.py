"""Tests of the experience bank (`creature_forge.experience_bank`): episodic kNN, mechanism cards, adapter, no label leakage.
Synthetic records; the real pilot files are used only if present."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from creature_forge import experience_bank as eb

FAULTS = ["cadence_fast", "feedback_loss", "heavy_torso", "placement_loss", "posture_lean", "short_feet", "slippery", "weak_motors"]
FEATS = {"L": 0.8, "foot_to_leg": 0.1, "mass_total": 12.0, "torso_frac": 0.3, "tau_ratio": 0.2, "friction": 1.0, "leg_density": 1000.0}
TOOLS = ["feedback", "foot_length", "timing", "torso_mass"]


def median(i: int, **over) -> dict:
    m = {"fall_direction": -1.0 if i % 2 else 1.0, "time_upright": 1.0 + 0.1 * i, "pitch_end": 0.1 * i, "pitch_rate_end": 0.01 * i,
         "com_vx_end": 0.3, "com_ahead_of_cop_over_L_end": 0.02 * i, "capture_margin_over_L_end": -0.1 * i, "step_freq_hz": 2.0,
         "step_length_over_L": 0.3, "swing_peak_clearance_min_over_L": 0.05, "saturation_frac_hip": 0.1, "saturation_frac_knee": 0.2 + 0.01 * i,
         "saturation_frac_ankle": 0.05, "slip_fraction": 0.1, "max_friction_utilisation": 0.9, "angmom_norm_end": 0.1, "leg_length_m": 0.8}
    m.update(over)
    return m


def record(i: int, policy="scientist", fault="slippery", with_obs=True, **over) -> dict:
    pr = {"repairs": [{"tool": "timing", "budget": 100, "ok": True, "train_walking": 2}]}
    if policy.startswith("scientist"):
        pr = {"initial_observation": {"median": median(i, **over), "pre_fall": {}, "n_walking": 0, "n_fell": 4} if with_obs else None,
              "hypotheses": {"H1": {"mechanism": "Torso pitches forward and the capture point leaves the foot.", "status": "supported",
                                    "history": [{"status": "open", "reason": "created"}, {"status": "supported", "reason": "pitch fell as predicted"}]}},
              "experiments": [{"kind": "counterfactual", "status": "ok", "change": "torso_mass_x0.75",
                               "outcome": {"n_walking": 2, "n_walking_base": 0, "quantities": {
                                   "pitch_end": {"base": 0.5, "new": 0.1, "delta": -0.4, "tolerance": 0.1},
                                   "slip_fraction": {"base": 0.1, "new": 0.1, "delta": 0.001, "tolerance": 0.05},
                                   "step_freq_hz": {"base": 2, "new": 2.3, "delta": 0.3, "tolerance": 0.1}}}},
                              {"kind": "repair", "status": "ok", "tool": "torso_mass", "budget": 300, "start_walking": 0, "train_walking": 3, "n_train": 4}],
              "final": {"explanation": "Torso too heavy.", "diagnosis_category": fault}}
    return {"policy": policy, "instance_id": f"base{i}:{fault}:1.0", "fault": fault, "severity": 1.0, "matching_tool": "timing",
            "base_id": f"base{i}", "n_obs": 4, "verification": {"status": "VERIFIED_IMPROVEMENT", "walking_frac": 0.9}, "policy_record": pr}


def instance(i: int, matrix=None) -> dict:
    return {"instance_id": f"base{i}:slippery:1.0", "features": dict(FEATS, torso_frac=0.3 + 0.01 * i), "repair_matrix": matrix}


def make_bank(n=6) -> eb.ExperienceBank:
    bank = eb.ExperienceBank()
    for i in range(n):
        bank.add(eb.episode_from_record(record(i), instance(i, {"timing": 1.0, "torso_mass": 0.0})))
    return bank


def obs(i: int, **over) -> dict:
    return {"median": median(i, **over), "pre_fall": {}, "n_walking": 0, "n_fell": 4}


class TestEpisodes(unittest.TestCase):
    def test_episode_fields_and_opaque_ids(self):
        ep = eb.episode_from_record(record(1), instance(1, {"timing": 1.0}))
        self.assertTrue(ep["id"].startswith("EP-") and len(ep["id"]) == 11)
        self.assertEqual(set(ep["signature"]), set(eb.SIGNATURE_KEYS))
        self.assertAlmostEqual(ep["signature"]["step_freq_norm"], 2.0 / (9.81 / 0.8) ** 0.5, places=4)
        self.assertEqual(ep["signature"]["sat_max"], 0.21)
        kinds = [x["kind"] for x in ep["experiments"]]
        self.assertEqual(kinds, ["counterfactual", "repair"])
        self.assertEqual(ep["experiments"][0]["top_changes"][0][0], "pitch_end")
        self.assertEqual(ep["hypotheses"][0]["reasons"], ["supported: pitch fell as predicted"])
        self.assertEqual(ep["repair_matrix"], {"timing": 1.0})
        self.assertNotIn("diagnosis_category", json.dumps(ep))

    def test_non_scientist_has_no_signature_but_repairs(self):
        ep = eb.episode_from_record(record(1, policy="exhaustive"))
        self.assertIsNone(ep["signature"])
        self.assertEqual(ep["experiments"][0]["tool"], "timing")
        self.assertIsNone(ep["repair_matrix"])

    def test_signature_from_instance_initial_observation(self):
        inst = instance(1)
        inst["initial_observation"] = {"median": median(1)}
        ep = eb.episode_from_record(record(1, policy="exhaustive"), inst)
        self.assertIsNotNone(ep["signature"])


class TestBank(unittest.TestCase):
    def test_determinism(self):
        a, b = make_bank().retrieve(obs(2), FEATS, k=3), make_bank().retrieve(obs(2), FEATS, k=3)
        self.assertEqual(a, b)
        self.assertEqual([x["id"] for x in a], [x["id"] for x in b])

    def test_nearest_by_construction(self):
        bank = make_bank(8)
        for i in (0, 3, 7):
            got = bank.retrieve(obs(i), dict(FEATS, torso_frac=0.3 + 0.01 * i), k=3)
            self.assertEqual(got[0]["id"], eb._opaque("EP", f"base{i}:slippery:1.0", "scientist"))
            self.assertAlmostEqual(got[0]["distance"], 0.0, places=6)
            d = [x["distance"] for x in got]
            self.assertEqual(d, sorted(d))
            self.assertTrue(got[0]["applicability_hint"].startswith("close"))

    def test_save_load_round_trip(self):
        bank = make_bank()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bank.jsonl"
            bank.save(p)
            loaded = eb.ExperienceBank.load(p)
        self.assertEqual(loaded.episodes, bank.episodes)
        self.assertEqual(loaded.retrieve(obs(2), FEATS), bank.retrieve(obs(2), FEATS))

    def test_standardization_ignores_missing(self):
        sigs = [{k: None for k in eb.SIGNATURE_KEYS} for _ in range(3)]
        for s, v in zip(sigs, (1.0, 3.0, None)):
            s["pitch_end"] = v
        n = eb.Norm(sigs)
        self.assertAlmostEqual(n.mean["pitch_end"], 2.0)
        self.assertAlmostEqual(n.std["pitch_end"], 1.0)
        self.assertEqual(n.std["slip_fraction"], 1.0)          # no data -> neutral
        z, missing = n.vec(sigs[2])
        self.assertEqual(z[eb.SIGNATURE_KEYS.index("pitch_end")], 0.0)
        self.assertIn("pitch_end", missing)

    def test_missing_query_values_flagged_and_neutral(self):
        bank = make_bank()
        got = bank.retrieve({"median": {"fall_direction": -1.0, "leg_length_m": 0.8}}, FEATS, k=2)
        self.assertEqual(len(got), 2)
        self.assertIn("missing in the query", got[0]["applicability_hint"])

    def test_one_episode_per_instance_and_empty(self):
        bank = make_bank(3)
        bank.add(eb.episode_from_record(record(0, policy="scientist_1shot"), instance(0)))
        self.assertEqual(len(bank.retrieve(obs(0), FEATS, k=10)), 3)
        self.assertEqual(eb.ExperienceBank().retrieve(obs(0), FEATS), [])

    def test_text_limits_and_content(self):
        bank = make_bank()
        for it in bank.retrieve(obs(1), FEATS, k=5):
            self.assertLessEqual(len(it["text"]), eb.MAX_TEXT)
            self.assertEqual(it["kind"], "episode")
        t = bank.retrieve(obs(1), FEATS, k=1)[0]["text"]
        self.assertIn("fell BACKWARD", t)
        self.assertIn("torso_mass_x0.75", t)
        self.assertIn("Measured repair matrix: repaired by timing", t)
        self.assertEqual(eb._r(0.123456), 0.123)

    def test_provenance(self):
        bank = make_bank()
        it = bank.retrieve(obs(1), FEATS, k=1)[0]
        self.assertEqual(bank.item_provenance(it["id"])["record"]["id"], it["id"])
        with self.assertRaises(KeyError):
            bank.item_provenance("EP-nope")


def card_episodes() -> list[dict]:
    """Two clear groups (6 + 4 robots) on a signature where only 3 keys are tight within the first group."""
    eps = []
    for i in range(10):
        a = i < 6
        med = median(i, fall_direction=-1.0 if a else 1.0, pitch_end=(-0.5 + 0.01 * i) if a else (0.6 + 0.01 * i),
                     capture_margin_over_L_end=(-0.2 + 0.005 * i) if a else (0.1 + 0.005 * i),
                     slip_fraction=(0.05 + 0.002 * i) if a else 0.5 + 0.002 * i,
                     time_upright=(i * 1.7) % 5.0, com_vx_end=((i * 37) % 11) / 10, max_friction_utilisation=((i * 13) % 7) / 7)
        m = ({"timing": 1.0, "torso_mass": 0.1} if a else {"timing": 0.0, "torso_mass": 0.9})
        if i == 5:
            m = {"timing": 0.25, "torso_mass": 0.1}              # counterexample to the group's best tool
        eps.append(eb.episode_from_record(record(i, **{k: v for k, v in med.items() if k in ("fall_direction",)}) | {}, None))
        eps[-1]["signature"] = eb.compute_signature(med, FEATS)
        eps[-1]["repair_matrix"] = m
    return eps


class TestCards(unittest.TestCase):
    def setUp(self):
        self.cards = eb.build_cards(card_episodes())

    def test_group_count_rule(self):
        self.assertEqual(eb.n_groups(10, 3), 2)
        self.assertEqual(eb.n_groups(100, 3), 7)
        self.assertEqual(eb.n_groups(4, 3), 1)

    def test_two_cards_support_and_status(self):
        self.assertEqual(len(self.cards), 2)
        self.assertEqual([c["id"] for c in self.cards], ["CARD-1", "CARD-2"])
        a, b = self.cards
        self.assertEqual((a["support"], b["support"]), (6, 4))
        self.assertEqual(a["best_tool"], "timing")
        self.assertEqual(a["tool_repair_rates"]["timing"], [5, 6])
        self.assertEqual(a["status"], "empirical heuristic")             # 5/6 > 0.7 and support >= 3
        self.assertEqual(b["best_tool"], "torso_mass")
        self.assertEqual(b["tool_repair_rates"]["torso_mass"], [4, 4])
        self.assertIsNone(a["established_physics"])

    def test_counterexamples(self):
        a = self.cards[0]
        self.assertEqual(len(a["counterexamples"]), 1)
        ce = a["counterexamples"][0]
        self.assertEqual(ce["walking_frac"], 0.25)
        self.assertGreaterEqual(ce["distance_to_centroid"], 0)
        self.assertEqual(self.cards[1]["counterexamples"], [])

    def test_condition_keys_are_the_tight_ones(self):
        keys = set(self.cards[0]["condition"])
        self.assertLessEqual(len(keys), 5)
        for k in ("pitch_end", "capture_margin_over_L_end", "slip_fraction"):
            self.assertIn(k, keys)
        c = self.cards[0]["condition"]["pitch_end"]
        self.assertLessEqual(c["min"], c["median"])
        self.assertLessEqual(c["median"], c["max"])

    def test_weak_card_is_hypothesis_with_validation(self):
        eps = card_episodes()
        for e in eps[:6]:
            e["repair_matrix"] = {"timing": 0.5, "torso_mass": 0.0}
        a = eb.build_cards(eps)[0]
        self.assertEqual(a["status"], "hypothesis")
        self.assertIn("validation_experiment", a)
        self.assertLessEqual(len(eb.card_item(a)["text"]), eb.MAX_TEXT)

    def test_min_support_filter_and_dedupe_and_requirements(self):
        self.assertEqual(eb.build_cards(card_episodes()[:2]), [])
        dup = card_episodes() + [dict(e, id=e["id"] + "x") for e in card_episodes()]        # same instances again
        self.assertEqual(sum(c["support"] for c in eb.build_cards(dup)), 10)
        no_matrix = card_episodes()
        for e in no_matrix:
            e["repair_matrix"] = None
        self.assertEqual(eb.build_cards(no_matrix), [])

    def test_determinism_and_item(self):
        self.assertEqual(eb.build_cards(card_episodes()), self.cards)
        it = eb.card_item(self.cards[0], "close (distance 0.5, typical 1)", 0.5)
        self.assertEqual(it["kind"], "card")
        self.assertLessEqual(len(it["text"]), eb.MAX_TEXT)
        self.assertIn("empirical heuristic", it["text"])
        self.assertIn("support 6", it["text"])

    def test_principle_prompt_and_provenance(self):
        c = self.cards[0]
        p = eb.principle_prompt(c)
        self.assertIn("timing 5/6", p)
        eb.set_principle(c, "Restating the capture point idea.", "nemotron-test", "capture point")
        self.assertEqual(c["principle_source"], {"source": "nemotron-test"})
        self.assertEqual(c["established_physics"], "capture point")
        self.assertIn("Restating", eb.card_item(c)["text"])


class TestAdapter(unittest.TestCase):
    def setUp(self):
        eps = card_episodes()
        self.bank = eb.ExperienceBank()
        for e in eps:
            self.bank.add(e)
        self.cards = eb.build_cards(eps)

    def q(self):
        return obs(1, fall_direction=-1.0, pitch_end=-0.5, capture_margin_over_L_end=-0.2, slip_fraction=0.05), FEATS

    def test_modes_and_limits(self):
        o, f = self.q()
        kinds = lambda m, **kw: [i["kind"] for i in eb.MemoryAdapter(self.bank, self.cards, mode=m, **kw).retrieve(o, f)]
        self.assertEqual(kinds("episodes"), ["episode", "episode"])
        self.assertEqual(kinds("cards"), ["card"])
        self.assertEqual(kinds("episodes+cards"), ["card", "episode", "episode"])
        self.assertEqual(kinds("episodes+cards", k_episodes=3, k_cards=2), ["card"] * 2 + ["episode"] * 3)
        self.assertEqual(kinds("cards", k_cards=5), ["card", "card"])
        with self.assertRaises(ValueError):
            eb.MemoryAdapter(self.bank, self.cards, mode="x")

    def test_nearest_card_and_provenance(self):
        o, f = self.q()
        ad = eb.MemoryAdapter(self.bank, self.cards, mode="cards")
        it = ad.retrieve(o, f)[0]
        self.assertEqual(it["id"], "CARD-1")
        self.assertIn("applicability_hint", it)
        prov = ad.item_provenance("CARD-1")
        self.assertEqual(len(prov["members"]), 6)
        self.assertEqual(ad.item_provenance(prov["members"][0]["id"])["kind"], "episode")

    def test_items_have_scientist_shape(self):
        o, f = self.q()
        for it in eb.MemoryAdapter(self.bank, self.cards).retrieve(o, f):
            self.assertTrue({"id", "kind", "text"} <= set(it))
            self.assertLessEqual(len(it["text"]), eb.MAX_TEXT)


class TestNoLeakage(unittest.TestCase):
    def check(self, items, ids):
        for it in items:
            blob = (it["id"] + " " + it["text"]).lower()
            for w in FAULTS + list(ids):
                self.assertNotIn(w.lower(), blob, f"{w!r} leaked into {it['id']}")

    def test_synthetic_leak_scan(self):
        faults = ["feedback_loss", "heavy_torso", "slippery"]
        bank, eps = eb.ExperienceBank(), []
        for i in range(10):
            rec = record(i, fault=faults[i % 3])
            ep = eb.episode_from_record(rec, instance(i, {"timing": 1.0, "torso_mass": 0.0}))
            bank.add(ep)
            eps.append(ep)
        cards = eb.build_cards(eps)
        ids = [f"base{i}:{faults[i % 3]}:1.0" for i in range(10)] + [f"base{i}" for i in range(10)]
        items = eb.MemoryAdapter(bank, cards, k_episodes=10, k_cards=10).retrieve(obs(1), FEATS)
        self.assertGreater(len(items), 3)
        self.check(items, ids)
        blob = json.dumps(bank.episodes) + json.dumps(cards)
        for f in faults:
            self.assertNotIn(f, blob)
        for ep in eps:
            self.assertNotIn("matching_tool", ep)
            self.assertNotIn("severity", ep)


REAL_EP = Path("C:/Users/mbnas/.vscode/Creature-Forge/artifacts/vm/ce2/ce")
REAL_INST = Path("C:/Users/mbnas/.vscode/Creature-Forge/artifacts/vm/ce/ce/dev_shard0.jsonl")


@unittest.skipUnless(REAL_EP.exists() and REAL_INST.exists(), "real example files absent")
class TestRealData(unittest.TestCase):
    def test_real_episodes(self):
        insts = {}
        for line in REAL_INST.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            insts[r["instance_id"]] = r
        bank, ids, n = eb.ExperienceBank(), set(), 0
        for p in sorted(REAL_EP.glob("pilot1_shard*.jsonl")):
            for line in p.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                ids.add(rec["instance_id"])
                ids.add(rec["base_id"])
                bank.add(eb.episode_from_record(rec, insts.get(rec["instance_id"])))
                n += 1
        self.assertGreater(n, 0)
        self.assertTrue(any(e["signature"] for e in bank.episodes.values()))
        sci = next(e for e in bank.episodes.values() if e["signature"])
        items = bank.retrieve({"median": {"fall_direction": 1.0, "leg_length_m": 0.4}}, sci["features"] or {}, k=3)
        for it in items:
            self.assertLessEqual(len(it["text"]), eb.MAX_TEXT)
            blob = (it["id"] + it["text"]).lower()
            for w in FAULTS + list(ids):
                self.assertNotIn(w.lower(), blob)
        with tempfile.TemporaryDirectory() as d:
            bank.save(os.path.join(d, "b.jsonl"))
            self.assertEqual(eb.ExperienceBank.load(os.path.join(d, "b.jsonl")).episodes, bank.episodes)


if __name__ == "__main__":
    unittest.main()
