"""Tests of the closed-loop mechanism pipeline (`mech_pipelines`). No MuJoCo simulation: `eval_override` replaces every rollout, and a
stand-in for `creature_forge.mechanisms` is injected. The fake evaluator records WHICH seeds each call used so that seed roles can be
asserted (feedback uses train/diag seeds only)."""
import copy
import json
import re
import types
import unittest
import zlib

import numpy as np

from creature_forge import creature_gen as cg
from creature_forge import mech_pipelines as mpl
from creature_forge import walk_opt as wo
from creature_forge.phasegait_init import LOWER15, UPPER15

BODY = cg.dev_named_bodies()["stilts-drawn"]
SEEDS = {"diag": [11, 12, 13, 14], "train": [21, 22, 23, 24], "screen": [910001 + i for i in range(12)]}
S, D = len(SEEDS["train"]), len(SEEDS["diag"])
SCREEN_N, TOPK = 4, 3
RESERVE = (TOPK + 1) * SCREEN_N
PB = 150            # probe budget: enough generations for the fake gain search to find the reward
TARGETS = ("hip", "knee", "ankle", "torque_hip", "torque_knee", "torque_ankle")


# ------------------------------------------------------------------------------------------------------------ mechanisms stand-in
def _validate_mechanism(m):
    errs = []
    if not isinstance(m, dict):
        return ["mechanism must be a dict"]
    allowed = {"id", "target", "leg", "terms", "gain_bound", "rationale", "revises"}
    if set(m) - allowed:
        errs.append(f"unknown key(s) {sorted(set(m) - allowed)}")
    if m.get("target") not in TARGETS:
        errs.append(f"target {m.get('target')!r} not in {TARGETS}")
    if m.get("leg") not in ("swing", "stance", "both"):
        errs.append(f"leg {m.get('leg')!r} invalid")
    t = m.get("terms")
    if not isinstance(t, list) or not 1 <= len(t) <= 4:
        errs.append("terms must be a list of 1-4 expressions")
    else:
        for e in t:
            if not isinstance(e, str) or re.search(r"[^A-Za-z0-9_+\-*/(). ,]", e) or "__" in e:
                errs.append(f"unsafe term {e!r}")
            elif not set(re.findall(r"[A-Za-z_]\w*", e)) <= set(SIGNALS) | {"tanh", "clip", "abs", "min", "max", "sin", "cos"}:
                errs.append(f"unknown name in term {e!r}")
    g = m.get("gain_bound")
    if isinstance(g, bool) or not isinstance(g, (int, float)) or not 0 < g <= 5:
        errs.append("gain_bound must be in (0, 5]")
    return errs


SIGNALS = ("pitch", "pitch_rate", "d", "v", "swing_flag", "torso_height")
SIGNAL_DOCS = {"pitch": "torso pitch (rad, positive forward lean)", "pitch_rate": "torso pitch rate (rad/s)",
               "d": "stance hip-to-ankle horizontal offset divided by leg length", "v": "its rate, divided by leg length",
               "swing_flag": "1 while the leg is in swing", "torso_height": "torso height over leg length"}


def _mk(mid, terms, target="hip", leg="swing", bound=2.0, **kw):
    return {"id": mid, "target": target, "leg": leg, "terms": list(terms), "gain_bound": bound, **kw}


def _random_mechanism(rng, n_terms=2, id="rnd"):
    terms = [SIGNALS[int(i)] for i in rng.choice(len(SIGNALS), size=n_terms, replace=False)]
    return _mk(id, terms, TARGETS[int(rng.integers(len(TARGETS)))], ("swing", "stance", "both")[int(rng.integers(3))],
               float(rng.choice([0.5, 1.0, 2.0])))


STUB = types.SimpleNamespace(
    SIGNALS=SIGNALS, SIGNAL_DOCS=SIGNAL_DOCS, TARGETS=TARGETS, LEGS=("swing", "stance", "both"), validate_mechanism=_validate_mechanism,
    random_mechanism=_random_mechanism,
    generic_linear_mechanisms=lambda: [_mk("gen_hip", ["pitch", "pitch_rate", "d", "v"], "hip", "both", 1.0),
                                       _mk("gen_knee", ["pitch", "pitch_rate", "d", "v"], "knee", "both", 1.0)],
    expert_foot_placement=lambda: _mk("expert_law", ["d", "v"], "hip", "swing", 2.0))


# ------------------------------------------------------------------------------------------------------------ fake evaluator
class Fake:
    """Synthetic evaluator. Mechanisms whose id starts with 'good' have a reward that peaks at gains = 0.5 * bound; all other mechanisms
    are inert (the search stays at gains 0). Records (kind, seeds) of every call and counts rollouts."""

    def __init__(self):
        self.rollouts = 0
        self.events = []

    @staticmethod
    def objective(vec, mechs=()):
        v = np.asarray(vec[:15], float)
        u = (v - LOWER15) / (UPPER15 - LOWER15)
        o = -float(np.sum((u - 0.6) ** 2))
        off = 15
        for m in mechs:
            n = len(m["terms"])
            g = np.asarray(vec[off:off + n], float)
            off += n
            if m["id"].startswith("good"):
                o += 1.5 - 6.0 * float(np.mean((g / m["gain_bound"] - 0.5) ** 2))
        return o

    @staticmethod
    def record(o):
        w = int(o > -1.2) + int(o > -0.8) + int(o > -0.5) + int(o > -0.3)
        return {"walking_count": min(S, w), "survival_count": min(S, w + 1), "mean_fitness": o, "error": None}

    def eval_fn(self, cands):
        return [self.record(self.objective(v) - 2.0 * np.log(b["foot_length"] / 0.12) ** 2) for b, v in cands]

    def cma_fn(self, body, vector, space, budget, train_seeds, noise_seed):
        self.events.append(("train", tuple(train_seeds)))
        mechs = space["mechanisms"]
        if not mechs:
            sp = wo.SearchSpace(ctrl_params=tuple(space["ctrl_params"]), body_params=tuple(space["body_params"]))
            res = wo.cma_search(body, vector, sp, budget=budget, train_seeds=train_seeds, noise_seed=noise_seed,
                                checkpoints=(), eval_fn=self.eval_fn)
            self.rollouts += res["rollouts_used"]
            return res
        rng = np.random.default_rng(np.random.SeedSequence([noise_seed, zlib.crc32("".join(m["id"] for m in mechs).encode())]))
        gains_dim = sum(len(m["terms"]) for m in mechs)
        pen = 2.0 * np.log(body["foot_length"] / 0.12) ** 2

        def ev(vec):
            return self.record(self.objective(vec, mechs) - pen)
        init = ev(vector)
        best = {"vector": list(vector), **init}
        used = S
        lam = 6
        while used + lam * S <= budget:
            for _ in range(lam):
                cand = list(vector[:15]) + [float(x) for x in
                                            np.concatenate([rng.uniform(-m["gain_bound"], m["gain_bound"], len(m["terms"])) for m in mechs])]
                r = ev(cand)
                if (r["walking_count"], r["survival_count"], r["mean_fitness"]) > \
                        (best["walking_count"], best["survival_count"], best["mean_fitness"]):
                    best = {"vector": cand, **r}
            used += lam * S
        assert len(best["vector"]) == 15 + gains_dim
        self.rollouts += used
        return {"init": {**init, "body": body, "vector": list(vector)}, "best": {"body": body, **best}, "rollouts_used": used,
                "errors": []}

    def screen_fn(self, body, vec, mechs, seeds):
        self.events.append(("screen", tuple(seeds)))
        self.rollouts += len(seeds)
        o = self.objective(vec, mechs) - 2.0 * np.log(body["foot_length"] / 0.12) ** 2
        return [{"seed": s, "outcome": "PASS" if o > -0.9 - 0.1 * (i % 3) else "FAIL", "walking": o > -0.9 - 0.1 * (i % 3),
                 "score": float(o + 0.01 * i)} for i, s in enumerate(seeds)]

    def diag_fn(self, body, vec, seeds):
        self.events.append(("diag_baseline", tuple(seeds)))
        return {"outcomes": [], "gait": {"froude": 0.1, "capture_margin_over_leg_mean": -0.5, "n_seeds": len(seeds)}}

    def mech_diag_fn(self, body, vec, mechs, seeds):
        self.events.append(("diag_mech", tuple(seeds)))
        self.rollouts += len(seeds)
        g = float(np.sum(np.abs(vec[15:])))
        return {"gait": {"froude": 0.1 + g, "capture_margin_over_leg_mean": -0.5 + 0.1 * g, "n_seeds": len(seeds)}}

    def override(self):
        return {"cma_fn": self.cma_fn, "screen_fn": self.screen_fn, "diag_fn": self.diag_fn, "mech_diag_fn": self.mech_diag_fn,
                "features_fn": lambda b: {"L": 1.1}}


def run(director, total=3000, fake=None, mode="iterative", max_rounds=3, probe_budget=PB, seeds=None, **kw):
    fake = fake or Fake()
    prev = mpl._MX_OVERRIDE
    mpl.set_mechanisms_module(STUB)
    try:
        rec = mpl.run_mech_pipeline(copy.deepcopy(BODY), director, total_budget=total, seeds=seeds or SEEDS, noise_seed=7,
                                    probe_budget=probe_budget, max_rounds=max_rounds, screen_top_k=TOPK, screen_n=SCREEN_N, mode=mode,
                                    eval_override=fake.override(), **kw)
    finally:
        mpl.set_mechanisms_module(prev)
    return rec, fake


def plan(init="start", subs=("timing",), body=(), mechs=(), share=1.0):
    return {"init": init, "ctrl_subspaces": list(subs), "body_params": list(body), "mechanisms": list(mechs), "budget_share": share}


def invariant(tc, rec, fake=None, total=None):
    lines = rec["budget_lines"]
    tc.assertEqual(rec["used"], sum(l["n"] for l in lines))
    tc.assertLessEqual(rec["used"], total or rec["total_budget"])
    cum = 0
    for l in lines:
        cum += l["n"]
        tc.assertEqual(l["cumulative"], cum)
        tc.assertGreaterEqual(cum, 0)
        tc.assertLessEqual(cum, rec["total_budget"])
    if fake is not None:
        tc.assertEqual(rec["used"], fake.rollouts, "everything charged was executed (the start evaluation is run by cma_fn too)")


class Replay:
    """Director that returns scripted values and records the states it received (for seed-hygiene assertions)."""

    def __init__(self, investigate, final, fake=None):
        self.inv, self.fin, self.states, self.fake, self.events_at_final = list(investigate), final, [], fake, None

    def investigate(self, state):
        self.states.append(copy.deepcopy(state))
        i = state["round"] - 1
        return copy.deepcopy(self.inv[i]) if i < len(self.inv) else {"stop": True}

    def final_plan(self, state):
        self.states.append(copy.deepcopy(state))
        if self.fake is not None:
            self.events_at_final = list(self.fake.events)
        return copy.deepcopy(self.fin)


GOOD = _mk("good1", ["pitch", "d", "v"], "hip", "swing", 2.0)
FLAT = _mk("flat1", ["pitch_rate"], "ankle", "both", 1.0)


class EndToEnd(unittest.TestCase):
    def test_probe_feedback_and_final_plan(self):
        fake = Fake()
        d = Replay([{"mechanisms": [GOOD, FLAT], "probes": ["opt_body"]},
                    {"mechanisms": [_mk("good2", ["pitch", "d"], "hip", "swing", 1.0, revises="flat1", rationale="flat1 stayed at zero")],
                     "stop": True}],
                   [plan("good1", ("timing",), (), ["good1"], 0.6), plan("start", (), (), ["flat1"], 0.4)], fake)
        rec, _ = run(d, fake=fake)
        invariant(self, rec, fake)
        r1, r2 = rec["rounds"]
        g, f = r1["mechanisms"]
        self.assertEqual((g["probe_id"], g["status"], g["improved"]), ("good1", "ok", True))
        self.assertGreater(g["delta_mean_fitness"], 0)
        self.assertEqual(len(g["gains"]), 3)
        self.assertTrue(f["all_gains_near_zero"])
        self.assertEqual(f["delta_walking"], 0)
        self.assertEqual(g["diag_rollouts"], D)
        self.assertGreater(g["gait_change"]["froude"], 0)                  # post - baseline
        self.assertEqual(g["baseline_gait"]["froude"], 0.1)
        self.assertEqual(g["feedback_seed_roles"], {"search": "train", "gait": "diag"})
        self.assertTrue(r2["stop"])
        self.assertEqual(rec["stopped_by"], "director_stop")
        self.assertEqual(rec["mechanisms"]["good2"]["mechanism"]["revises"], "flat1")
        # budget lines of a mechanism probe: search + diagnostic rollouts (+ refund)
        items = [l["item"] for l in rec["budget_lines"]]
        for it in ("probe:good1", "probe:good1:diag", "probe:opt_body", "plan:f0", "screen_reserve:release", "screen:original"):
            self.assertIn(it, items)
        # the final candidate carries its mechanisms and a matching vector
        fin = rec["final"]
        self.assertEqual(len(fin["vector"]), 15 + sum(len(m["terms"]) for m in fin["mechanisms"]))
        self.assertEqual(rec["final_step"]["round"], 3)
        self.assertEqual([p["plan_id"] for p in rec["final_step"]["plans"]], ["f0", "f1"])

    def test_candidates_include_mechanism_probe_and_plan_with_mechanisms(self):
        d = Replay([{"mechanisms": [GOOD]}], [plan("good1", ("timing",), (), ["good1"], 1.0)])
        rec, _ = run(d)
        sources = {c["source"] for c in rec["candidates"]}
        self.assertTrue(sources & {"good1", "f0"})
        plan_rec = rec["final_step"]["plans"][0]
        self.assertEqual([m["id"] for m in plan_rec["mechanisms"]], ["good1"])
        self.assertEqual(len(plan_rec["best_vector"]), 18)

    def test_unspent_budget_is_recorded(self):
        d = Replay([{"stop": True}], [plan("start", ("timing",), (), [], 0.3)])
        rec, _ = run(d)
        self.assertGreater(rec["unspent_after_final_step"], 0)
        self.assertEqual(rec["unspent_after_final_step"], rec["final_step"]["unspent"])
        invariant(self, rec)

    def test_deterministic_and_json_safe(self):
        mk = lambda: Replay([{"mechanisms": [GOOD, FLAT], "probes": ["opt_posture"]}], [plan("good1", ("timing",), (), ["good1"], 1.0)])  # noqa: E731
        a, _ = run(mk())
        b, _ = run(mk())
        for r in (a, b):
            r.pop("wall_s")
        self.assertEqual(a, b)
        json.dumps(a)
        self.assertNotIn("sk-", json.dumps(a))

    def test_mechanism_probe_error_keeps_charge_and_never_becomes_a_candidate(self):
        fake = Fake()
        ov_cma = fake.cma_fn

        def boom(body, vector, space, budget, train, ns):
            if any(m["id"] == "flat1" for m in space["mechanisms"]):
                raise RuntimeError("boom")
            return ov_cma(body, vector, space, budget, train, ns)
        fake.cma_fn = boom
        d = Replay([{"mechanisms": [FLAT]}], [plan("start", ("timing",), (), ["flat1"], 1.0)])
        rec, _ = run(d, fake=fake)
        p = rec["mechanism_probes"][0]
        self.assertEqual(p["status"], "error")
        self.assertEqual(p["rollouts"], PB)
        self.assertNotIn("flat1", {c["source"] for c in rec["candidates"]})
        self.assertEqual(rec["final_step"]["plans"], [])                    # flat1 was never probed ok: the plan is rejected
        self.assertTrue(any("not probed successfully" in r for x in rec["final_step"]["rejected_plans"] for r in x["reasons"]))
        self.assertEqual(rec["used"], sum(l["n"] for l in rec["budget_lines"]))


class BudgetAdversarial(unittest.TestCase):
    def adversary(self):
        many = [_mk(f"good{i}", ["pitch"], TARGETS[i], "swing", 1.0) for i in range(5)]
        bad = [{"id": "x"}, "nonsense", _mk("bad", ["os.system('x')"]), _mk("bad2", ["pitch"], bound=99)]
        return Replay([{"mechanisms": [many[0], "nonsense", {"id": "x"}] + many[1:] + bad, "probes": ["opt_timing", "nope", "opt_posture", "opt_feedback", "opt_stride"]},
                       {"mechanisms": many, "probes": ["opt_body", "foot_x1_5"]},
                       {"mechanisms": [_mk("z", ["v"])] * 3, "probes": ["opt_timing"], "stop": False}],
                      [plan("start", ("timing", "posture"), FIX_BODY, ["good0", "good1", "good2"], 0.9), plan("good0", ("stride",), (), ["good0"], 0.9),
                       plan("start", ("feedback",), (), [], 1.5), "junk", plan("start", ("timing",), (), [], 0.1)])

    def test_never_exceeds_the_budget(self):
        for total in (RESERVE + S, RESERVE + S + 10, 120, 400, 700, 1500, 5000):
            for mode in ("iterative", "one_shot"):
                rec, fake = run(self.adversary(), total=total, mode=mode)
                self.assertLessEqual(rec["used"], total, (total, mode))
                self.assertEqual(rec["used"], sum(l["n"] for l in rec["budget_lines"]))
                for l in rec["budget_lines"]:
                    self.assertLessEqual(l["cumulative"], total)
                self.assertEqual(rec["used"], fake.rollouts)

    def test_rejections_cost_nothing_and_are_reasoned(self):
        rec, _ = run(self.adversary(), total=5000)
        r1 = rec["rounds"][0]
        self.assertEqual(len(r1["mechanisms"]), 1)                          # index 1 is junk, index >= 2 is over the cap
        reasons = [x["reasons"][0] for x in r1["rejected_mechanisms"]]
        self.assertTrue(any("more than 2 mechanisms" in r for r in reasons))
        self.assertTrue(any("must be a dict" in r for r in reasons))
        self.assertEqual(len(r1["probes"]), 1)
        self.assertTrue(any("more than 2 probes" in x["reasons"][0] for x in r1["rejected_probes"]))
        self.assertTrue(any("unknown probe" in x["reasons"][0] for x in r1["rejected_probes"]))
        # second round: re-proposed ids/structures are duplicates, opt_body probes fine
        r2 = rec["rounds"][1]
        self.assertTrue(all(any("already used" in r for r in x["reasons"]) for x in r2["rejected_mechanisms"] if x["id"] in ("good0", "good1")))
        # repeated mechanism ids in round 3 (same id z three times: one accepted, the rest rejected)
        r3 = rec["rounds"][2]
        self.assertEqual(len(r3["mechanisms"]) + len(r3["rejected_mechanisms"]), 3)
        # final step: share overflow, junk, too many plans
        fs = rec["final_step"]
        self.assertTrue(fs["rejected_plans"])
        self.assertLessEqual(len(fs["plans"]), 2)
        self.assertGreaterEqual(rec["unspent_after_final_step"], 0)
        invariant(self, rec)

    def test_unaffordable_probes_and_mechanisms_are_rejected_not_clipped(self):
        total = RESERVE + S + PB + D + 10         # exactly one mechanism probe fits
        rec, _ = run(Replay([{"mechanisms": [GOOD, FLAT], "probes": ["opt_timing"]}], []), total=total)
        self.assertEqual(len(rec["rounds"][0]["mechanisms"]), 1)
        self.assertTrue(any("remain" in x["reasons"][0] for x in rec["rounds"][0]["rejected_mechanisms"]))
        self.assertTrue(any("remain" in x["reasons"][0] for x in rec["rounds"][0]["rejected_probes"]))
        invariant(self, rec)

    def test_stop_immediately_and_empty_decisions(self):
        rec, fake = run(Replay([{"stop": True}], []))
        self.assertEqual(rec["stopped_by"], "director_stop")
        self.assertEqual(len(rec["rounds"]), 1)
        self.assertEqual(rec["final"]["source"], "start")                     # nothing substituted
        invariant(self, rec, fake)
        rec2, _ = run(Replay([{}, {}, {}], []))
        self.assertEqual(rec2["stopped_by"], "max_rounds")
        self.assertEqual(rec2["settings"]["rounds_used"], 3)
        rec3, _ = run(Replay(["garbage", [1], None], None))
        self.assertTrue(all(r["rejected_mechanisms"] for r in rec3["rounds"]))
        self.assertTrue(rec3["final_step"]["rejected_plans"])

    def test_shares_over_one_are_rejected(self):
        rec, _ = run(Replay([{"stop": True}], [plan(share=1.2)]))
        self.assertTrue(any("budget_share" in r for x in rec["final_step"]["rejected_plans"] for r in x["reasons"]))
        self.assertEqual(rec["final_step"]["plans"], [])
        rec, _ = run(Replay([{"stop": True}], [plan(share=0.7), plan("start", ("posture",), (), [], 0.6)]))
        self.assertTrue(any("exceed 1" in r for x in rec["final_step"]["rejected_plans"] for r in x["reasons"]))
        self.assertEqual(len(rec["final_step"]["plans"]), 1)
        rec, _ = run(Replay([{"stop": True}], [plan(share=0.2)] * 3))
        self.assertTrue(any("more than 2 plans" in r for x in rec["final_step"]["rejected_plans"] for r in x["reasons"]))

    def test_validation_errors_for_inputs(self):
        with self.assertRaises(ValueError):
            run(Replay([], []), total=RESERVE)             # cannot pay screening + start
        bad = dict(SEEDS, screen=[11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 26])
        with self.assertRaises(ValueError):
            run(Replay([], []), seeds=bad)
        with self.assertRaises(ValueError):
            run(Replay([], []), mode="nope")


FIX_BODY = ("foot_length", "thigh_length")


class SeedRoles(unittest.TestCase):
    def test_feedback_uses_only_train_and_diag_seeds(self):
        fake = Fake()
        d = Replay([{"mechanisms": [GOOD, FLAT], "probes": ["opt_body"]}, {"mechanisms": [_mk("good2", ["d"], revises="good1", rationale="x")]}],
                   [plan("good1", ("timing",), (), ["good1"], 1.0)], fake)
        rec, _ = run(d, fake=fake)
        screen = set(SEEDS["screen"])
        for kind, seeds in fake.events:
            if kind == "screen":
                self.assertEqual(list(seeds), SEEDS["screen"][:SCREEN_N])
            elif kind == "train":
                self.assertEqual(list(seeds), SEEDS["train"])
            else:
                self.assertEqual(list(seeds), SEEDS["diag"])
        # screening happens only after the final plan has been requested and run
        self.assertNotIn("screen", [k for k, _ in d.events_at_final])
        self.assertEqual([k for k, _ in fake.events][-(TOPK + 1):].count("screen") >= 1, True)
        # no state handed to the director, and no feedback record, contains a screen seed
        blob = json.dumps(d.states)
        for s in screen:
            self.assertNotIn(str(s), blob)
        fb = json.dumps(rec["mechanism_probes"])
        for s in screen:
            self.assertNotIn(str(s), fb)
        self.assertEqual(rec["seed_roles"]["feedback"], ["train", "diag"])
        # state feedback never carries screening results
        self.assertNotIn("screen", json.dumps([s.get("mechanism_probes") for s in d.states]))

    def test_diag_seeds_are_charged(self):
        rec, _ = run(Replay([{"mechanisms": [GOOD]}], []))
        diag_lines = [l for l in rec["budget_lines"] if l["item"].endswith(":diag")]
        self.assertEqual([l["n"] for l in diag_lines], [D])

    def test_roles_must_not_overlap(self):
        with self.assertRaises(ValueError):
            run(Replay([], []), seeds=dict(SEEDS, screen=SEEDS["train"] + SEEDS["screen"][:8]))


class RevisionRules(unittest.TestCase):
    def one(self, round2, round1=None):
        d = Replay([{"mechanisms": round1 or [GOOD]}, {"mechanisms": round2}], [])
        rec, _ = run(d)
        return rec["rounds"][1], rec

    def test_valid_revision(self):
        r2, rec = self.one([_mk("good_b", ["pitch", "v"], revises="good1", rationale="gain at bound")])
        self.assertEqual(len(r2["mechanisms"]), 1)
        self.assertEqual(r2["mechanisms"][0]["revises"], "good1")
        self.assertEqual(rec["mechanisms"]["good_b"]["mechanism"]["revises"], "good1")

    def test_revision_of_unknown_or_same_round_mechanism(self):
        r2, _ = self.one([_mk("good_b", ["pitch", "v"], revises="ghost", rationale="x")])
        self.assertTrue(any("not a mechanism probed in an earlier round" in r for x in r2["rejected_mechanisms"] for r in x["reasons"]))
        # a mechanism proposed in the same round cannot be revised by a sibling
        d = Replay([{"mechanisms": [GOOD, _mk("good_c", ["v"], revises="good1", rationale="same round")]}], [])
        rec, _ = run(d)
        self.assertEqual(len(rec["rounds"][0]["mechanisms"]), 1)
        self.assertTrue(rec["rounds"][0]["rejected_mechanisms"])

    def test_revision_needs_rationale_and_is_not_a_duplicate(self):
        r2, _ = self.one([_mk("good_b", ["pitch", "v"], revises="good1", rationale="  ")])
        self.assertTrue(any("rationale" in r for x in r2["rejected_mechanisms"] for r in x["reasons"]))
        r2, _ = self.one([_mk("good_d", ["pitch", "d", "v"], "hip", "swing", 2.0, revises="good1", rationale="same structure")])
        self.assertTrue(any("same target, leg and terms" in r for x in r2["rejected_mechanisms"] for r in x["reasons"]))

    def test_reserved_and_reused_ids(self):
        r2, _ = self.one([_mk("opt_body", ["v"]), _mk("good1", ["v"])])
        reasons = [r for x in r2["rejected_mechanisms"] for r in x["reasons"]]
        self.assertTrue(any("reserved" in r for r in reasons))
        self.assertTrue(any("already used" in r for r in reasons))

    def test_revising_an_errored_probe_is_allowed(self):
        fake = Fake()
        inner = fake.cma_fn
        fake.cma_fn = lambda b, v, sp, bud, tr, ns: (_ for _ in ()).throw(RuntimeError("x")) if any(m["id"] == "flat1" for m in sp["mechanisms"]) \
            else inner(b, v, sp, bud, tr, ns)
        d = Replay([{"mechanisms": [FLAT]}, {"mechanisms": [_mk("flat2", ["v"], revises="flat1", rationale="errored")]}], [])
        rec, _ = run(d, fake=fake)
        self.assertEqual(rec["rounds"][0]["mechanisms"][0]["status"], "error")
        self.assertEqual(len(rec["rounds"][1]["mechanisms"]), 1)

    def test_rejections_are_reported_back_to_the_director(self):
        d = Replay([{"mechanisms": [{"id": "x"}]}, {"stop": True}], [])
        run(d)
        self.assertTrue(d.states[1]["rejected_last_round"])
        self.assertEqual(d.states[0]["rejected_last_round"], [])


class ModesAndCalls(unittest.TestCase):
    def test_one_shot_has_exactly_one_investigate_round(self):
        d = Replay([{"mechanisms": [GOOD]}, {"mechanisms": [FLAT]}], [])
        rec, _ = run(d, mode="one_shot")
        self.assertEqual(len(rec["rounds"]), 1)
        self.assertEqual(len([s for s in d.states if s["stage"] == "investigate"]), 1)
        self.assertEqual(rec["states_mode"] if "states_mode" in rec else rec["mode"], "one_shot")
        self.assertEqual(d.states[-1]["stage"], "final")

    def test_iterative_runs_until_stop_or_max_rounds(self):
        d = Replay([{"mechanisms": [GOOD]}, {"mechanisms": [FLAT]}, {"stop": True}], [])
        rec, _ = run(d, max_rounds=5)
        self.assertEqual(len(rec["rounds"]), 3)
        self.assertEqual(rec["stopped_by"], "director_stop")
        d = Replay([{}] * 9, [])
        rec, _ = run(d, max_rounds=2)
        self.assertEqual(len(rec["rounds"]), 2)

    def test_iterative_sees_feedback_after_each_round(self):
        d = Replay([{"mechanisms": [GOOD]}, {"stop": True}], [])
        run(d)
        self.assertEqual(d.states[0]["mechanism_probes"], [])
        mp1 = d.states[1]["mechanism_probes"]
        self.assertEqual([p["probe_id"] for p in mp1], ["good1"])
        self.assertIn("gains", mp1[0])
        self.assertIn("post_gait", mp1[0])
        self.assertIn("gait_change", mp1[0])
        self.assertEqual(d.states[1]["baseline"]["gait"]["froude"], 0.1)

    def test_stop_with_items_runs_the_items_then_ends(self):
        d = Replay([{"mechanisms": [GOOD], "stop": True}, {"mechanisms": [FLAT]}], [])
        rec, _ = run(d)
        self.assertEqual(len(rec["rounds"]), 1)
        self.assertEqual(len(rec["rounds"][0]["mechanisms"]), 1)

    def test_non_boolean_stop_is_ignored_and_reported(self):
        d = Replay([{"stop": "yes"}, {"stop": True}], [])
        rec, _ = run(d)
        self.assertEqual(len(rec["rounds"]), 2)
        self.assertTrue(any("stop must be a boolean" in r for x in rec["rounds"][0]["rejected_mechanisms"] for r in x["reasons"]))


class SelectionV2(unittest.TestCase):
    @staticmethod
    def c(walk, med, order, train=(0, 0, 0.0)):
        return {"train_score": list(train), "order": order, "screen": {"walking": walk, "median": -1e18 if med is None else med, "median_score": med}}

    def test_effect_bar_beats_walking_count(self):
        orig = 1.0
        a = self.c(8, 1.2, 0)             # many walkers, below the bar (1.5)
        b = self.c(5, 2.0, 1)             # fewer walkers, passes the bar
        self.assertEqual(mpl.select_final_v2([a, b], orig), 1)
        self.assertEqual(mpl.select_final_v2([a], orig), 0)

    def test_inside_the_bar_walking_then_median_then_train_then_order(self):
        orig = 1.0
        cs = [self.c(5, 2.0, 0), self.c(6, 1.6, 1), self.c(6, 1.9, 2), self.c(6, 1.9, 3, (0, 0, 1.0))]
        self.assertEqual(mpl.select_final_v2(cs, orig), 3)                   # train score breaks the tie
        cs[3] = self.c(6, 1.9, 3)
        self.assertEqual(mpl.select_final_v2(cs, orig), 2)                   # earlier order breaks the tie

    def test_bar_is_exact_and_error_medians_never_pass(self):
        self.assertTrue(mpl.passes_effect_bar(1.5, 1.0))
        self.assertFalse(mpl.passes_effect_bar(1.4999, 1.0))
        self.assertFalse(mpl.passes_effect_bar(None, 1.0))
        self.assertTrue(mpl.passes_effect_bar(0.2, None))                    # the original has no median: bar reduces to finite
        self.assertEqual(mpl.MIN_EFFECT_M, 0.5)
        a, b = self.c(3, None, 0), self.c(2, 1.6, 1)
        self.assertEqual(mpl.select_final_v2([a, b], 1.0), 1)

    def test_end_to_end_original_is_charged_once_and_sets_the_bar(self):
        rec, fake = run(Replay([{"mechanisms": [GOOD]}], [plan("good1", ("timing",), (), ["good1"], 1.0)]))
        sel = rec["selection"]
        self.assertEqual(sel["rule"], "selection_v2")
        self.assertAlmostEqual(sel["bar"], sel["original_median_score"] + 0.5)
        screens = [l for l in rec["budget_lines"] if l["item"].startswith("screen:")]
        self.assertEqual(sum(l["n"] for l in screens), SCREEN_N * (1 + len([c for c in rec["candidates"] if c["source"] != "start"])))
        self.assertEqual(len(screens), 1 + len([c for c in rec["candidates"] if c["source"] != "start"]))
        # the winner passes the bar iff any screened candidate does
        passes = [c["passes_effect_bar"] for c in rec["candidates"]]
        win = rec["candidates"][sel["winner_index"]]
        self.assertEqual(win["passes_effect_bar"], any(passes))
        self.assertEqual(rec["final"]["source"], win["source"])

    def test_original_among_screened_is_not_screened_twice(self):
        rec, fake = run(Replay([{"stop": True}], []))               # pool = just the start
        screens = [l for l in rec["budget_lines"] if l["item"].startswith("screen:")]
        self.assertEqual([l["item"] for l in screens], ["screen:original"])
        self.assertEqual(sum(1 for k, _ in fake.events if k == "screen"), 1)
        self.assertEqual(rec["final"]["source"], "start")


class FinalPlanValidation(unittest.TestCase):
    runs = {"opt_timing": [], "good1": ["good1"], "pair": ["good1", "flat1"]}
    ids = {"good1", "flat1"}

    def v(self, **kw):
        return mpl.validate_final_plan(plan(**kw), runs=self.runs, mech_ids=self.ids)

    def test_valid_and_invalid(self):
        self.assertEqual(self.v(init="good1", mechs=["good1"]), [])
        self.assertEqual(self.v(subs=(), mechs=["flat1"]), [])
        self.assertTrue(self.v(init="good1", mechs=[]))                                  # init carries good1
        self.assertTrue(self.v(mechs=["ghost"]))
        self.assertTrue(self.v(mechs=["good1", "flat1", "good1"]))
        self.assertTrue(self.v(init="opt_stride"))
        self.assertTrue(self.v(subs=(), mechs=[]))
        self.assertTrue(self.v(subs=("placement",)))
        self.assertTrue(self.v(share=0))
        self.assertTrue(self.v(body=("leg_density", "a", "b", "c", "d")))
        self.assertTrue(mpl.validate_final_plan({"init": "start"}, runs={}, mech_ids=set()))

    def test_too_many_mechanisms(self):
        runs = {"start_x": []}
        self.assertTrue(mpl.validate_final_plan(plan(subs=(), mechs=["a", "b", "c"]), runs=runs, mech_ids={"a", "b", "c"}))

    def test_vector_bookkeeping(self):
        g, f = GOOD, FLAT
        vec = list(np.arange(15, dtype=float)) + [1.0, 2.0, 3.0]
        out = mpl.vector_for(vec, [g], [f, g])
        self.assertEqual(out, list(vec[:15]) + [0.0] + [1.0, 2.0, 3.0])
        self.assertEqual(mpl.vector_for(vec[:15], [], [g]), list(vec[:15]) + [0.0, 0.0, 0.0])
        with self.assertRaises(ValueError):
            mpl.vector_for(vec, [g], [f])
        with self.assertRaises(ValueError):
            mpl.vector_for(vec[:16], [g], [g])

    def test_gain_report_flags(self):
        m = _mk("x", ["pitch", "d", "v"], bound=2.0)
        r = mpl.gain_report(m, [0.0] * 15 + [2.0, 0.05, -1.0])
        self.assertEqual([(g["at_bound"], g["near_zero"]) for g in r], [(True, False), (False, True), (False, False)])
        self.assertAlmostEqual(r[2]["fraction_of_bound"], -0.5)


class NonAIDirectors(unittest.TestCase):
    def test_fix15_probes_and_plan(self):
        rec, _ = run(mpl.Fix15Director())
        probes = [p["probe_id"] for r in rec["rounds"] for p in r["probes"]]
        self.assertEqual(probes, ["opt_body", "opt_posture", "opt_timing"])
        self.assertEqual(rec["mechanism_probes"], [])
        fp = rec["final_step"]["plans"][0]["plan"]
        self.assertEqual(sorted(fp["ctrl_subspaces"]), ["posture", "timing"])
        self.assertEqual(fp["mechanisms"], [])
        self.assertEqual(fp["budget_share"], 1.0)
        invariant(self, rec)
        # single-round mode still works and probes at most two
        rec1, _ = run(mpl.Fix15Director(), mode="one_shot")
        self.assertEqual(len([p for r in rec1["rounds"] for p in r["probes"]]), 2)

    def test_generic_probes_both_mechanisms_and_uses_improved_ones(self):
        rec, _ = run(mpl.GenericDirector())
        self.assertEqual([p["probe_id"] for p in rec["mechanism_probes"]], ["gen_hip", "gen_knee"])
        self.assertEqual([p["probe_id"] for p in rec["rounds"][0]["probes"]], ["opt_body"])
        self.assertEqual(len(rec["rounds"]), 1)
        fp = rec["final_step"]["plans"][0]["plan"]
        self.assertEqual(fp["mechanisms"], [])                    # the fake's generic mechanisms are inert -> not improved
        invariant(self, rec)

    def test_rand_is_deterministic_and_seeded(self):
        a, _ = run(mpl.RandMechDirector(5))
        b, _ = run(mpl.RandMechDirector(5))
        c, _ = run(mpl.RandMechDirector(6))
        ids = lambda r: [m["probe_id"] for m in r["mechanism_probes"]]   # noqa: E731
        self.assertEqual(ids(a), ["rnd_r1_0", "rnd_r1_1", "rnd_r2_0", "rnd_r2_1"])
        for r in (a, b):
            r.pop("wall_s")
        self.assertEqual(a, b)
        self.assertNotEqual([m["mechanism"] for m in a["mechanism_probes"]], [m["mechanism"] for m in c["mechanism_probes"]])
        self.assertEqual(len(a["rounds"]), 2)

    def test_expert_mechanism_improving_enters_the_plan(self):
        stub = types.SimpleNamespace(**vars(STUB))
        stub.expert_foot_placement = lambda: _mk("good_expert", ["d", "v"], "hip", "swing", 2.0)
        fake = Fake()
        mpl.set_mechanisms_module(stub)
        try:
            rec = mpl.run_mech_pipeline(copy.deepcopy(BODY), mpl.ExpertDirector(), total_budget=3000, seeds=SEEDS, noise_seed=7,
                                        probe_budget=PB, max_rounds=3, screen_top_k=TOPK, screen_n=SCREEN_N,
                                        eval_override=fake.override())
        finally:
            mpl.set_mechanisms_module(None)
        self.assertTrue(rec["mechanism_probes"][0]["improved"])
        fp = rec["final_step"]["plans"][0]["plan"]
        self.assertEqual(fp["mechanisms"], ["good_expert"])
        self.assertEqual(fp["init"], "good_expert")
        self.assertEqual([m["id"] for m in rec["final_step"]["plans"][0]["mechanisms"]], ["good_expert"])
        invariant(self, rec)

    def test_scripted_replays_a_recorded_run(self):
        rec, _ = run(mpl.GenericDirector())
        rec2, _ = run(mpl.ScriptedMechDirector(rec["decisions"]))
        for r in (rec, rec2):
            r.pop("wall_s")
            r.pop("director")
        self.assertEqual(rec, rec2)
        with self.assertRaises(ValueError):
            mpl.ScriptedMechDirector([{"kind": "plans", "returned": []}])


class AdapterTests(unittest.TestCase):
    def test_job_fn_attaches_mechanisms_only_to_vectors_with_gains(self):
        calls = []
        import creature_forge.challenges as ch
        orig = ch.seed_job
        ch.seed_job = lambda job: calls.append(job) or {"ok": True}
        try:
            fn = mpl.job_fn_for([GOOD])
            fn({"controllers": {"walk": {"vector": [0.0] * 18}}})
            fn({"controllers": {"walk": {"vector": [0.0] * 15}}})
        finally:
            ch.seed_job = orig
        self.assertEqual(calls[0]["controllers"]["walk"]["mechanisms"][0]["id"], "good1")
        self.assertNotIn("mechanisms", calls[1]["controllers"]["walk"])
        self.assertIsNone(mpl.job_fn_for([]))

    def test_features_without_hook_fails_loudly_with_mechanisms(self):
        with self.assertRaises(NotImplementedError):
            mpl.features_with_mechanisms({}, [0.0] * 18, [GOOD], 1)


if __name__ == "__main__":
    unittest.main()
