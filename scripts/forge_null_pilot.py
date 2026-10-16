"""Null pilot for verdict_v1: is the paired sign test on near-deterministic scores trustworthy? Run on the VM (heavy):

    python scripts/forge_null_pilot.py                       # experiments/forge_loop/null_pilot/null_pilot.json (~7,500 rollouts)
    python scripts/forge_null_pilot.py --quick               # tiny smoke run
    python scripts/forge_null_pilot.py --max-rollouts 8000   # hard budget (default 8000)

Creatures (tests/fixtures/forge_zoo.json): default, balanced, bird-knees (stand and survive pushes) and tiny-feet (a weak
creature that falls: a positive control, because some random edits really help it). Challenges: stand and push (walk is not
run). No model, no registered seed; seeds are the >= 100000 blocks of `arena.seed_sets`.

Experiments per (creature, challenge):
  (a) A/A same seeds   the original run a second time as an extra arm on the same seeds -> verdict (deterministic: all ties).
  (b) A/A new draws    the original on disjoint seed sets (validate[0:8] vs probe[0:8], validate[8:16] vs validate[0:8], ...)
                       -> measures seed-to-seed variability; any VERIFIED/WORSE here is a seed-noise false alarm.
  (c) random-edit null 20 (push: fewer, budget) edits per creature drawn with `baselines.matched_random` from synthetic "AI" edits
                       of typical size (log-ratio 0.2-0.3, control |du| 0.1-0.25), judged by verdict_v1 on 8 validation seeds
                       (stand: also on 16). Edits are random, so a few genuinely change the creature: VERIFIED/WORSE there is not
                       automatically a false alarm; the A/A cells are the true null.
  (d) variation        the same with `arena.VARIATION_PRESET` conditions on validation seeds (perturb x2, push time +-0.15 s,
                       friction +-10 %), identical for every arm of a seed.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from creature_forge import arena, baselines  # noqa: E402
from creature_forge import interventions as iv  # noqa: E402
from creature_forge import verdict as vd  # noqa: E402
from creature_forge.creatures import default_controllers, normalize_body  # noqa: E402
from creature_forge.forge_pool import get_pool  # noqa: E402
from creature_forge.interventions import Edit  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "forge_zoo.json"
OUT = ROOT / "experiments" / "forge_loop" / "null_pilot" / "null_pilot.json"
CREATURES = ("default", "balanced", "bird-knees", "tiny-feet")
PUSH_EDITS = {"default": 10, "balanced": 6, "bird-knees": 10, "tiny-feet": 14}     # budget: a standing creature costs ~12 rollouts per push seed
STAND_EDITS = 20
STAND_VAR_EDITS = 10
PUSH_VAR_EDITS = 6
PUSH_VAR_CREATURES = ("default",)
SPEC_OVERRIDES = None                                                              # contract defaults: stand 8 s, push 5 s


def zoo() -> dict:
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out = {}
    for c in d["creatures"]:
        if c["id"] in CREATURES:
            out[c["id"]] = {"mode": c["mode"], "body": normalize_body(c["body"], c["mode"]), "controllers": default_controllers(), "n": 1}
    return out


def synthetic_ai_edits(version: dict, kind: str, cid: str, i: int) -> list[Edit]:
    """What a typical model proposal looks like in size: 1 or 2 edits (log-ratio 0.2-0.3; control |du| 0.1-0.25). Only the kinds and
    magnitudes matter to `matched_random`."""
    rng = baselines.make_rng(f"null-pilot-synth:{cid}:{kind}", f"S{i}")
    params = list(iv.allowed_params(kind))
    chosen = [params[int(rng.integers(len(params)))]]
    if i % 2:
        rest = [p for p in params if p != chosen[0]]
        chosen.append(rest[int(rng.integers(len(rest)))])
    out = []
    for p in chosen:
        if iv.kind_of(p) == "control":
            lo, hi = iv.control_bounds(p)
            cur = baselines._control_value(version, p)
            out.append(Edit(p, "set", float(cur + rng.uniform(0.1, 0.25) * (hi - lo))))
        else:
            out.append(Edit(p, "scale", float(math.exp(rng.uniform(0.2, 0.3)))))
    return out


def random_edits(version: dict, kind: str, cid: str, n: int) -> list[dict]:
    out = []
    for i in range(n):
        ai = synthetic_ai_edits(version, kind, cid, i)
        twin = baselines.matched_random(version, kind, ai, baselines.make_rng(f"null-pilot:{cid}:{kind}", f"R{i}"))
        out.append({"i": i, "synthetic_ai": [e.to_dict() for e in ai], "edits": None if twin is None else [e.to_dict() for e in twin],
                    "magnitudes": [round(iv.magnitude(version, e), 4) for e in (twin or [])]})
    return out


class Budget:
    def __init__(self, cap: int):
        self.cap, self.used = cap, 0

    def add(self, results: dict) -> int:
        n = sum(r["rollouts"] for per in results.values() for r in per)
        self.used += n
        return n


def runner(kind: str, budget: Budget, pool, variation=None):
    def run(arms: list[dict], seeds, var=None) -> dict:
        out = arena.evaluate_arms(kind, arms, list(seeds), SPEC_OVERRIDES, pool=pool, variation=var)
        budget.add(out["results"])
        return out["results"]
    return run


def arm_of(version: dict, kind: str, arm_id: str, edits: list[dict] | None) -> dict:
    a = arena.build_arm(version, kind, {"arm_id": arm_id, "source": "original" if not edits else "random_baseline", "edits": edits or []})
    if a["error"]:
        raise RuntimeError(f"{arm_id}: {a['error']}")
    return a


def scores(per) -> list:
    return [r["score"] for r in per]


def passes(per) -> list:
    return [r["outcome"] == "PASS" for r in per]


def judge(kind: str, orig, cand, resolution: float) -> dict:
    v = vd.verdict(kind, scores(orig), scores(cand), resolution=resolution, original_pass=passes(orig), candidate_pass=passes(cand))
    return {k: v[k] for k in ("status", "n", "wins", "losses", "ties", "median_diff", "p_one_sided", "p_worse")}


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    st = {s: sum(r["status"] == s for r in rows) for s in vd.STATUSES}
    med = [r["median_diff"] for r in rows if r["median_diff"] is not None]
    tie = [r["ties"] / r["n"] for r in rows if r["ties"] is not None]
    return {"n": len(rows), "status_counts": st, "status_fraction": {s: round(c / len(rows), 4) for s, c in st.items()},
            "median_diff_quantiles": None if not med else {q: float(np.percentile(med, q)) for q in (0, 10, 25, 50, 75, 90, 100)},
            "median_diff_nonzero_fraction": None if not med else round(sum(abs(m) > 1e-9 for m in med) / len(med), 4),
            "tie_fraction_mean": None if not tie else round(float(np.mean(tie)), 4),
            "all_tied_fraction": None if not tie else round(sum(t == 1.0 for t in tie) / len(tie), 4),
            "ge6_non_tied_fraction": round(sum((r["wins"] + r["losses"]) >= vd.MIN_NON_TIED for r in rows if r["wins"] is not None) / len(rows), 4)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--max-rollouts", type=int, default=8000)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    t0 = time.perf_counter()
    z = zoo()
    n_stand, n_var_stand, n_push_scale = (4, 2, 0.25) if args.quick else (STAND_EDITS, STAND_VAR_EDITS, 1.0)
    pool = get_pool()
    variation = arena._check_variation(arena.VARIATION_PRESET)
    record: dict = {"meta": {}, "aa_same_seed": {}, "aa_new_draws": {}, "random_null": {}, "skipped": []}
    shared = Budget(args.max_rollouts)

    seeds = {c: arena.seed_sets(c, 1, 1, {"validate": 16, "probe": 8}) for c in z}
    record["seeds"] = {c: {"round": s["round"], "validate": list(s["seeds"]["validate"]), "probe": list(s["seeds"]["probe"])} for c, s in seeds.items()}
    res_for = {k: arena.resolution_for(k, arena.make_spec(k, (1,), SPEC_OVERRIDES)) for k in ("stand", "push")}

    origs_cache: dict = {}
    # ---------------- (a) + (b) originals, one batch per challenge ----------------
    for kind in ("stand", "push"):
        run = runner(kind, shared, pool)
        orig = {c: arm_of(z[c], kind, f"{c}:orig", None) for c in z}
        full = {}
        for c in z:                         # original on validate[0:16] + probe[0:8], and the copy on validate[0:8], plus variation twins
            v16 = seeds[c]["seeds"]["validate"]
            probe = seeds[c]["seeds"]["probe"]
            r = run([orig[c]], v16 + probe)
            full[c] = r[orig[c]["arm_id"]]
        copies = {}
        for c in z:
            r = run([dict(orig[c], arm_id=f"{c}:copy")], seeds[c]["seeds"]["validate"][:8])
            copies[c] = r[f"{c}:copy"]
        aa_same, aa_new = {}, {}
        for c in z:
            o16, op = full[c][:16], full[c][16:]
            aa_same[c] = judge(kind, o16[:8], copies[c], res_for[kind])
            aa_same[c]["identical_scores"] = scores(o16[:8]) == scores(copies[c])
            A, B, P = o16[:8], o16[8:], op       # three disjoint 8-seed draws of the SAME original creature
            pairs = {"A_vs_B": (A, B), "B_vs_A": (B, A), "A_vs_P": (A, P), "P_vs_A": (P, A), "B_vs_P": (B, P), "P_vs_B": (P, B)}
            rows = {}
            for name, (a, b) in pairs.items():                       # (a = "original", b = "candidate")
                rows[name] = judge(kind, a, b, res_for[kind])
            aa_new[c] = {"comparisons": rows, "orig_validate16_scores": scores(o16), "orig_probe_scores": scores(op),
                         "orig_validate16_outcomes": [r["outcome"] for r in o16],
                         "unique_scores_validate16": sorted(set(scores(o16)))}
        for c in z:
            origs_cache[(kind, c, False)] = full[c][:16] if kind == "stand" else full[c][:8]
        record["aa_same_seed"][kind], record["aa_new_draws"][kind] = aa_same, aa_new
        record["aa_new_draws"][kind]["_summary"] = summarize([row for c in z for row in aa_new[c]["comparisons"].values()])
        # variation: original on validate16 under the preset, a copy on validate[0:8]
        if kind == "stand" or any(c in PUSH_VAR_CREATURES for c in z):
            var_rows = {}
            for c in z:
                if kind == "push" and c not in PUSH_VAR_CREATURES:
                    continue
                v16 = seeds[c]["seeds"]["validate"]
                o = run([orig[c]], v16, variation)[orig[c]["arm_id"]]
                origs_cache[(kind, c, True)] = o[:16] if kind == "stand" else o[:8]
                cp = run([dict(orig[c], arm_id=f"{c}:copy")], v16[:8], variation)[f"{c}:copy"]
                var_rows[c] = {"same_seed": judge(kind, o[:8], cp, res_for[kind]), "new_draw": judge(kind, o[:8], o[8:], res_for[kind]),
                               "orig_var_scores": scores(o), "plain_scores_same_seeds": scores(full[c][:16]),
                               "distinct_scores_var": len(set(scores(o))), "distinct_scores_plain": len(set(scores(full[c][:16])))}
            record["aa_new_draws"][kind]["_variation"] = var_rows

    # ---------------- (c)/(d) random-edit null ----------------
    cands = {(kind, c): random_edits(z[c], kind, c, n_stand if kind == "stand" else max(2, int(PUSH_EDITS[c] * n_push_scale)))
             for kind in ("stand", "push") for c in z}
    null_rows: dict = {"stand": {}, "push": {}}

    def orig_scores(kind, c, var):
        key = (kind, c, bool(var))
        if key not in origs_cache:
            a = arm_of(z[c], kind, f"{c}:orig", None)
            n = 16 if kind == "stand" else 8
            origs_cache[key] = runner(kind, shared, pool)([a], seeds[c]["seeds"]["validate"][:n], var)[a["arm_id"]]
        return origs_cache[key]

    def run_chunk(kind, c, idxs, var):
        run = runner(kind, shared, pool)
        n = 16 if kind == "stand" else 8
        arms, meta = [], []
        for i in idxs:
            cand = cands[(kind, c)][i]
            if cand["edits"] is None:
                continue
            arms.append(arm_of(z[c], kind, f"{c}:R{i}", cand["edits"]))
            meta.append(i)
        if not arms:
            return
        out = run(arms, seeds[c]["seeds"]["validate"][:n], var)
        orig = orig_scores(kind, c, var)
        for a, i in zip(arms, meta):
            per = out[a["arm_id"]]
            row = {"i": i, "edits": cands[(kind, c)][i]["edits"], "magnitudes": cands[(kind, c)][i]["magnitudes"],
                   "variation": bool(var), "scores": scores(per), "outcomes": [r["outcome"] for r in per],
                   "orig_scores": scores(orig), "verdict_8": judge(kind, orig[:8], per[:8], res_for[kind])}
            if n == 16:
                row["verdict_16"] = judge(kind, orig, per, res_for[kind])
            null_rows[kind].setdefault(f"{c}{'|var' if var else ''}", []).append(row)

    def affordable(est: int) -> bool:
        return shared.used + est <= args.max_rollouts

    # stand: cheap, everything. variation on the first edits.
    for c in z:
        run_chunk("stand", c, range(len(cands[("stand", c)])), None)
        run_chunk("stand", c, range(min(n_var_stand, len(cands[("stand", c)]))), variation)
    # push variation first (small), then base push round-robin across creatures so a truncation hits every creature equally
    for c in PUSH_VAR_CREATURES:
        k = 2 if args.quick else PUSH_VAR_EDITS
        cost = 8 * 13 * k
        if affordable(cost):
            run_chunk("push", c, range(min(k, len(cands[("push", c)]))), variation)
        else:
            record["skipped"].append(f"push variation {c}: budget")
    chunk, rounds = 4, math.ceil(max(len(v) for (k, _), v in cands.items() if k == "push") / 4)
    last_cost = 8 * 13 * chunk * len(z) * 0.5
    for r in range(rounds):
        for c in z:
            idx = [i for i in range(r * chunk, (r + 1) * chunk) if i < len(cands[("push", c)])]
            if not idx:
                continue
            est = int(8 * 12 * len(idx) * (0.4 if c == "tiny-feet" else 1.0))
            if not affordable(est):
                record["skipped"].append(f"push {c} edits {idx}: would exceed the {args.max_rollouts} rollout budget (used {shared.used})")
                continue
            run_chunk("push", c, idx, None)

    # ---------------- aggregate ----------------
    agg: dict = {}
    for kind in ("stand", "push"):
        for key, rows in null_rows[kind].items():
            c, _, v = key.partition("|")
            tag = "variation" if v else "plain"
            agg.setdefault(kind, {}).setdefault(tag, {})[c] = {"verdict_8": summarize([r["verdict_8"] for r in rows])}
            if kind == "stand":
                agg[kind][tag][c]["verdict_16"] = summarize([r["verdict_16"] for r in rows])
        for tag in ("plain", "variation"):
            cells = [r for key, rows in null_rows[kind].items() if (("|var" in key) == (tag == "variation")) for r in rows]
            if cells:
                agg[kind].setdefault(tag, {})["_all"] = {"verdict_8": summarize([r["verdict_8"] for r in cells])}
                if kind == "stand":
                    agg[kind][tag]["_all"]["verdict_16"] = summarize([r["verdict_16"] for r in cells])
                # excluding the weak creature (positive control)
                st = [r for key, rows in null_rows[kind].items() if key.split("|")[0] != "tiny-feet" and (("|var" in key) == (tag == "variation")) for r in rows]
                if st:
                    agg[kind][tag]["_standing_only"] = {"verdict_8": summarize([r["verdict_8"] for r in st])}
    record["random_null"] = {"rows": null_rows, "summary": agg, "candidates": {f"{k}:{c}": v for (k, c), v in cands.items()}}
    unavailable = {f"{k}:{c}": [x["i"] for x in v if x["edits"] is None] for (k, c), v in cands.items() if any(x["edits"] is None for x in v)}
    record["meta"] = {
        "platform": platform.platform(), "python": sys.version.split()[0], "workers": getattr(pool, "max_workers", None),
        "commit": _git("rev-parse", "--short", "HEAD"), "dirty": bool(_git("status", "--porcelain")),
        "rollouts_total": shared.used, "max_rollouts": args.max_rollouts, "wall_s": round(time.perf_counter() - t0, 1),
        "verdict_rule": vd.VERDICT_RULE_VERSION, "min_effect": vd.MIN_EFFECT, "resolution": res_for,
        "variation_preset": arena.VARIATION_PRESET, "creatures": list(z), "quick": args.quick, "unavailable_twins": unavailable,
        "note": "No model call, no registered seed. Nothing here is a registered result."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1, sort_keys=False), encoding="utf-8")
    print(f"wrote {args.out}  rollouts={shared.used}  wall={record['meta']['wall_s']}s")
    pool.close()


def _git(*a) -> str:
    try:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


if __name__ == "__main__":
    main()
