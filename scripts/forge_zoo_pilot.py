"""Zoo pilot for the Forge Loop challenge system: how much does each challenge vary across seeds, and what does a short
controller adaptation buy? Run on the VM (heavy):

    python scripts/forge_zoo_pilot.py --make-fixture                 # tests/fixtures/forge_zoo.json from the 6 Studio starters
    python scripts/forge_zoo_pilot.py --heavy                        # experiments/forge_loop/pilot/zoo_pilot.json
    python scripts/forge_zoo_pilot.py --heavy --only default,doomed  # subset

Per creature: stand (8 seeds), push (8 seeds, both directions, bisection), walk with the R2 controller ("r2-transfer", 8 seeds),
and walk after adaptation with K in {48, 96, 192} rollouts (3 training seeds; evaluated on the same 8 seeds as the transfer
run). K = 48/96/192 are nested checkpoints of ONE 192-rollout run per noise seed (same noise stream, so a run with a smaller
budget is exactly the prefix of a larger one; tested), which keeps the pilot cheap. Seeds come from the >= 100000 namespace of
contracts section 7 (a local `seed_block`); nothing here uses a registered seed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "forge_zoo.json"
OUT = ROOT / "experiments" / "forge_loop" / "pilot" / "zoo_pilot.json"
CHALLENGE_SEEDS = 8
TRAIN_SEEDS = 3
KS = (48, 96, 192)
NOISE_SEEDS = (910001, 910002)
LAMBDA = 8


# ---------------------------------------------------------------------------------------------------------
# seeds (contracts section 7)
# ---------------------------------------------------------------------------------------------------------
def seed_block(creature_id: str, n: int, round_: int, role: str, k: int) -> tuple[int, ...]:
    h = hashlib.sha256(f"{creature_id}:{n}:{round_}:{role}".encode()).hexdigest()
    base = 100_000 + int(h[:8], 16) % 800_000
    return tuple(range(base, base + k))


# ---------------------------------------------------------------------------------------------------------
# zoo fixture: port of studio/src/sketch/starters.ts
# ---------------------------------------------------------------------------------------------------------
PX_PER_M, GROUND_Y, CX = 400.0, 620.0, 500.0


def _px(x: float, z: float) -> list[float]:
    return [CX + x * PX_PER_M, GROUND_Y - z * PX_PER_M]


def _js_round1(v: float) -> float:
    return math.floor(v * 10 + 0.5) / 10   # Math.round(v * 10) / 10 (half rounds up, unlike Python's round)


def _line(a, b, n=24, wobble=1.1, seed=0.0):
    out = []
    for i in range(n + 1):
        t = i / n
        x, y = _px(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        out.append([_js_round1(x + wobble * math.sin(i * 1.3 + seed)), _js_round1(y + wobble * math.cos(i * 0.9 + seed))])
    return out


def _poly(vs, seed=0):
    return [p for i, v in enumerate(vs[1:]) for p in _line(vs[i], v, 18, 1.1, seed + i)]


def _rect(cx, z0, w, h, seed=0):
    return _poly([(cx - w / 2, z0), (cx + w / 2, z0), (cx + w / 2, z0 + h), (cx - w / 2, z0 + h), (cx - w / 2, z0)], seed)


def _figure(thigh=0.3, shank=0.3, foot=0.16, torsoW=0.12, torsoH=0.3, kneeBack=0.0, legGap=0.05):
    hip_z = thigh + shank + 0.04
    strokes = [{"id": "torso", "role": "torso", "points": _rect(0, hip_z, torsoW, torsoH, 1)}]
    for i, dx in enumerate((-legGap / 2, legGap / 2)):
        strokes.append({"id": f"leg{i}", "role": "leg", "points": _poly([(dx, hip_z), (dx - kneeBack, hip_z - thigh), (dx, 0.04)], 3 + i)})
        strokes.append({"id": f"foot{i}", "role": "foot", "points": _line((dx - 0.25 * foot, 0.04), (dx + 0.75 * foot, 0.04), 10, 0.8, 5 + i)})
    return strokes


# (id, label, hint, terrible, figure kwargs, materials). The Studio draws the two legs 0.05 m apart; with a foot longer than
# that gap `freehand.interpret` can attach a foot to the neighbouring leg and report "feet point in opposite directions"
# (found while porting: top-heavy, stilts). `build_zoo` then widens the gap (0.10, 0.15 m) and records it.
STARTERS = [
    ("balanced", "Balanced biped", "A sensible creature: it should stand.", False, {}, None),
    ("tiny-feet", "Tiny feet", "A 3 cm foot under a normal body.", True, {"foot": 0.03}, None),
    ("top-heavy", "Top-heavy", "A huge torso on thin legs with small feet.", True, {"torsoW": 0.4, "torsoH": 0.7, "foot": 0.08}, None),
    ("stilts", "Stilts", "Very long legs, short feet.", True, {"thigh": 0.6, "shank": 0.6, "foot": 0.07}, None),
    ("bird-knees", "Bird knees", "Knees that bend the way this model allows.", False, {"kneeBack": 0.1}, None),
    ("weak-slippery", "Weak and slippery", "A normal shape with feeble motors and ice-like feet.", True, {},
     {"torque_limit": 5, "foot_friction": 0.05}),
]
LEG_GAPS = (0.05, 0.10, 0.15)


def _interpret_starter(kw: dict, materials):
    from creature_forge.freehand import interpret
    last = None
    for gap in LEG_GAPS:
        strokes = _figure(**{**kw, "legGap": gap})
        for guided in (True, False):
            res = interpret(strokes, guided=guided, materials=materials)
            if res.get("body") is not None:
                return res, guided, gap
            last = res
    raise SystemExit(f"starter {kw} could not be interpreted: {last.get('errors')}")


def build_zoo() -> list[dict]:
    from creature_forge.sandbox import SandboxBody
    zoo = []
    base = SandboxBody().as_dict()
    base.update({"thigh_length_r": base["thigh_length"], "shank_length_r": base["shank_length"], "foot_length_r": base["foot_length"]})
    zoo.append({"id": "default", "name": "Default biped", "mode": "guided", "terrible": False,
                "hint": "The registered default body (Phase 0).", "source": "creature_forge.sandbox.SandboxBody()", "body": base})
    for sid, label, hint, terrible, kw, materials in STARTERS:
        res, guided, gap = _interpret_starter(kw, materials)
        body = res["body"]
        for k in ("thigh_length", "shank_length", "foot_length"):
            assert body[k + "_r"] is not None, "freehand must fill the per-leg fields"
        mode = "guided" if guided else "experimental"
        zoo.append({"id": sid, "name": label, "mode": mode, "terrible": terrible, "hint": hint,
                    "source": f"studio/src/sketch/starters.ts:{sid} via freehand.interpret(guided={guided}), leg gap {gap} m",
                    "interpretation": {"outcome": res["outcome"], "notes": res["notes"], "errors": res["errors"],
                                       "adjustments": [a["message"] for a in res["adjustments"]], "leg_gap_m": gap},
                    "body": body})
    zoo.append({"id": "doomed", "name": "Doomed", "mode": "experimental", "terrible": True,
                "hint": "Tiny feet, a very heavy torso and weak motors at once.",
                "source": "hand-built sandbox body", "body": {
                    "torso_mass": 40.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.03, "foot_friction": 1.0,
                    "torque_limit": 4.0, "leg_density": 1000.0, "thigh_length_r": 0.3, "shank_length_r": 0.3,
                    "foot_length_r": 0.03, "pose": [0.0] * 7}})
    return zoo


def make_fixture(path: Path) -> None:
    zoo = build_zoo()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"description": "Zoo of creature bodies for the Forge Loop challenge tests and pilot. Generated by "
                                "scripts/forge_zoo_pilot.py --make-fixture from the six Studio starters, the default body and one "
                                "deliberately terrible hand-built body.", "creatures": zoo}, indent=1) + "\n", encoding="utf-8")
    for c in zoo:
        b = c["body"]
        print(f"{c['id']:14s} mode={c['mode']:12s} mass={b['torso_mass']:.2f} legs={b['thigh_length']+b['shank_length']:.2f}/"
              f"{b['thigh_length_r']+b['shank_length_r']:.2f} foot={b['foot_length']:.3f} mu={b['foot_friction']} tq={b['torque_limit']} "
              f"pose0={b['pose'][0]:+.3f}")
    print(f"wrote {path}")


def load_zoo(path: Path = FIXTURE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["creatures"]


# ---------------------------------------------------------------------------------------------------------
# pilot
# ---------------------------------------------------------------------------------------------------------
def dist(xs) -> dict:
    a = np.asarray([x for x in xs if x is not None], dtype=float)
    if not len(a):
        return {"median": None, "q25": None, "q75": None, "min": None, "max": None, "iqr": None, "range": None}
    q1, q3 = np.percentile(a, [25, 75])
    return {"median": float(np.median(a)), "q25": float(q1), "q75": float(q3), "min": float(a.min()), "max": float(a.max()),
            "iqr": float(q3 - q1), "range": float(a.max() - a.min())}


def challenge_record(res) -> dict:
    d = res.as_dict()
    return {"outcome": d["outcome"], "counts": d["summary"]["counts"], "pass_rate": d["summary"]["pass_rate"],
            "score": dist([s["score"] for s in d["per_seed"] if s["outcome"] != "ERROR"]),
            "per_seed": [{"seed": s["seed"], "outcome": s["outcome"], "score": s["score"], "error": s["error"],
                          "label": s["metrics"].get("label"), "rollouts": s["rollouts"]} for s in d["per_seed"]],
            "rollouts": d["rollouts"], "wall_s": d["wall_s"], "controller": d["controller"]["walk"]["kind"]}


def run_creature(c: dict, pool) -> dict:
    from creature_forge import challenges as ch
    from creature_forge import creature_walk as cw
    t0 = time.perf_counter()
    cid, body = c["id"], c["body"]
    seeds = seed_block(cid, 1, 0, "challenge", CHALLENGE_SEEDS)
    train = seed_block(cid, 1, 0, "train", TRAIN_SEEDS)
    assert not set(seeds) & set(train) and min(seeds + train) >= 100_000
    rec: dict = {"id": cid, "name": c["name"], "mode": c["mode"], "terrible": c["terrible"], "body": body,
                 "seeds": {"challenge": list(seeds), "train": list(train)}}
    rollouts = 0

    stand = ch.run_challenge(body, None, ch.default_spec("stand", seeds), pool=pool)
    rec["stand"] = challenge_record(stand)
    rollouts += stand.rollouts

    push = ch.run_challenge(body, None, ch.default_spec("push", seeds), pool=pool)
    pr = challenge_record(push)
    pd = push.as_dict()["per_seed"]
    pr["critical_force_fwd"] = dist([s["metrics"].get("critical_force_fwd") for s in pd])
    pr["critical_force_bwd"] = dist([s["metrics"].get("critical_force_bwd") for s in pd])
    pr["critical_force_per_seed"] = [[s["metrics"].get("critical_force_fwd"), s["metrics"].get("critical_force_bwd")] for s in pd]
    pr["weak_direction_counts"] = {k: sum(s["metrics"].get("weak_direction") == k for s in pd) for k in ("forward", "backward", "equal")}
    pr["censored_seeds"] = sum(bool(s["metrics"].get("censored")) for s in pd)
    pr["falls_without_push_seeds"] = sum(bool(s["metrics"].get("falls_without_push")) for s in pd)
    pr["force_resolution_N"] = pd[0]["metrics"].get("force_resolution_N") if pd else None
    rec["push"] = pr
    rollouts += push.rollouts

    wspec = ch.default_spec("walk", seeds)
    transfer = ch.run_challenge(body, None, wspec, pool=pool)
    rec["walk_transfer"] = challenge_record(transfer)
    rollouts += transfer.rollouts
    t_pass = transfer.as_dict()["summary"]["counts"]["PASS"]

    rec["adaptation"] = {"train_seeds": list(train), "ks": list(KS), "replicates": []}
    for ns in NOISE_SEEDS:
        a = cw.adapt_controller(body, list(cw.R2_WINNER), budget=max(KS), train_seeds=train, noise_seed=ns, pool=pool)
        rollouts += a["rollouts_used"]
        by_k = {}
        for k in KS:
            g = k // (LAMBDA * len(train))
            vec = a["init_vector"] if g == 0 else a["history"][g - 1]["parent_vector"]
            adaptation = {"budget": k, "rollouts_used": g * LAMBDA * len(train), "train_seeds": list(train), "noise_seed": ns,
                          "parent_vector": a["init_vector"], "generations": g}
            res = ch.run_challenge(body, {"walk": {"vector": vec, "adaptation": adaptation}}, wspec, pool=pool)
            rollouts += res.rollouts
            r = challenge_record(res)
            changed = vec != a["init_vector"]
            r.update({"vector_changed": changed, "train_score": a["history"][g - 1]["parent_score_after"] if g else a["init_score"],
                      "pass_before": t_pass, "pass_after": r["counts"]["PASS"], "pass_delta": r["counts"]["PASS"] - t_pass,
                      "improved_train": bool(g and a["history"][g - 1]["parent_score_after"] > a["init_score"]),
                      "solved": r["outcome"] == "PASS"})
            by_k[str(k)] = r
        rec["adaptation"]["replicates"].append({
            "noise_seed": ns, "init_train_score": a["init_score"], "final_train_score": a["best_score"],
            "train_rollouts": a["rollouts_used"], "train_wall_s": a["wall_s"],
            "generation_scores": [h["parent_score_after"] for h in a["history"]],
            "generation_success_rates": [h["success_rate"] for h in a["history"]], "by_k": by_k})
    rec["rollouts"] = rollouts
    rec["wall_s"] = time.perf_counter() - t0
    return rec


def headline(rec: dict) -> dict:
    p = rec["push"]
    reps = rec["adaptation"]["replicates"]
    return {"id": rec["id"], "stand": rec["stand"]["outcome"], "push": p["outcome"],
            "push_median_N": p["score"]["median"], "push_range_N": p["score"]["range"], "walk_transfer": rec["walk_transfer"]["outcome"],
            "walk_pass_transfer": rec["walk_transfer"]["counts"]["PASS"],
            "walk_pass_by_k": {k: [r["by_k"][k]["counts"]["PASS"] for r in reps] for k in map(str, KS)},
            "rollouts": rec["rollouts"], "wall_s": round(rec["wall_s"], 1)}


def run_pilot(zoo: list[dict], out: Path) -> dict:
    from creature_forge.forge_pool import get_pool
    import mujoco
    pool = get_pool()
    t0 = time.perf_counter()
    results = []
    for c in zoo:
        r = run_creature(c, pool)
        results.append(r)
        print(json.dumps(headline(r)), flush=True)
    wall = time.perf_counter() - t0
    total = sum(r["rollouts"] for r in results)
    doc = {"description": "Forge Loop zoo pilot: challenge variability and controller adaptation across seeds.",
           "protocol": {"challenge_seeds": CHALLENGE_SEEDS, "train_seeds": TRAIN_SEEDS, "ks": list(KS), "noise_seeds": list(NOISE_SEEDS),
                        "adaptation": "(1+8)-ES from the R2 winner in r2's normalised space; K=48/96/192 are nested checkpoints of one 192-rollout run",
                        "seed_namespace": ">= 100000, sha256 block per (creature, role)"},
           "environment": {"python": platform.python_version(), "platform": platform.platform(), "mujoco": mujoco.__version__,
                           "numpy": np.__version__, "workers": pool.max_workers},
           "totals": {"rollouts": total, "wall_s": wall, "rollouts_per_s": total / wall},
           "headline": [headline(r) for r in results], "creatures": results}
    out.parent.mkdir(parents=True, exist_ok=True)
    from creature_forge.optimize import jsonable
    out.write_text(json.dumps(jsonable(doc), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {out}: {total} rollouts in {wall:.0f} s ({total / wall:.1f}/s)")
    return doc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--make-fixture", action="store_true", help="(re)generate tests/fixtures/forge_zoo.json")
    ap.add_argument("--heavy", action="store_true", help="required to run the pilot (thousands of MuJoCo rollouts; VM only)")
    ap.add_argument("--only", default="", help="comma-separated creature ids")
    ap.add_argument("--fixture", type=Path, default=FIXTURE)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.make_fixture:
        make_fixture(a.fixture)
        return
    if not a.heavy:
        raise SystemExit("refusing to run thousands of rollouts without --heavy (run it on the VM)")
    zoo = load_zoo(a.fixture)
    if a.only:
        keep = set(a.only.split(","))
        zoo = [c for c in zoo if c["id"] in keep]
    run_pilot(zoo, a.out)


if __name__ == "__main__":
    main()
