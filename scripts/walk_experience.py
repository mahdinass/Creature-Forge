"""L2 pilot driver: does experience on OTHER creatures improve the first decision (a warm start) on an unfamiliar creature?

Three modes (append-only JSONL, protocol sha256 in every line, deterministic units, --resume, --shard i/k, pro-rata rollout cap):

  --make-panels  --panel-dir DIR     writes DIR/panel_train.json (regions NOT held out) and DIR/panel_test.json (held-out regions
                                     only) with creature_gen.generate_panel; refuses to overwrite; leakage_check on the regions.
  --collect      --panel-dir DIR --out FILE
                                     one line per TRAINING creature: joint-17 `cma_search` (17 controller + 4 body dims) from the
                                     padded R2 start, budget `collect.budget`, TRAIN seeds, VARIATION_PRESET, log_candidates=True.
  --evaluate     --panel-dir DIR --collect-file FILE --out FILE
                                     one line per (TEST creature, variant, N): the variant's warm start (first one inside the guided
                                     bounds; discards recorded), its zero-budget `recovery.assess`, then a joint-17 `cma_search` of
                                     `evaluate.budget` rollouts from it (the warm start's own evaluation is included) and
                                     `recovery.assess` of the best candidate by TRAIN score. Variants: r2 (N-independent), and
                                     knn / mean_best / learned for every N in `evaluate.learning_curve` (the first N training creatures
                                     in panel order). All variants of a test creature share seeds and the noise seed (paired).

The search after a warm start runs on the warm body, with body_ratio chosen so that every candidate stays inside the interventions
ratio box [0.5, 1.5] of the ORIGINAL body (r_lo = max_p 0.5/w_p, r_hi = min_p 1.5/w_p, w = warm/original), so all variants are
judged under the same edit rule. Assessment compares against the original body with the frozen R2 winner (as walk_oracle does).

Seeds: creature_gen.walkrec_seed_block(protocol["campaign"], role, creature_id, n). Units are deterministic: an interrupted unit leaves
no line and reproduces exactly when run again.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from creature_forge import creature_gen as cg  # noqa: E402
from creature_forge import creature_walk as cw  # noqa: E402
from creature_forge import experience as ex  # noqa: E402
from creature_forge import recovery as rc  # noqa: E402
from creature_forge import walk_opt as wo  # noqa: E402
from creature_forge.arena import VARIATION_PRESET  # noqa: E402
from creature_forge.forge_pool import ForgePool  # noqa: E402
from creature_forge.optimize import jsonable  # noqa: E402

ASSESS_ROLLOUT_EQUIV = rc.VALIDATE_N * 2 + rc.CONFIRM_N * rc.CONFIRM_DURATION / rc.TRAIN_DURATION
VARIANTS = ("r2", "knn", "mean_best", "learned")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        c = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
        return c + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("CF_SNAPSHOT", "unknown")


def clean(o):
    """Plain-JSON copy (numpy arrays/scalars converted)."""
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    return o


def heldout_regions(proto: dict) -> list[str]:
    pats = proto["heldout_regions"]
    held = sorted({r for r in cg.REGIONS if any(fnmatch.fnmatchcase(r, p) for p in pats)})
    if not held:
        raise SystemExit(f"heldout_regions {pats} match no region")
    return held


# ------------------------------------------------------------------------------------------------------------ panels
def make_panels(proto: dict, psha: str, pdir: Path, workers: int) -> int:
    held = heldout_regions(proto)
    train_allowed = [r for r in cg.REGIONS if r not in held]
    pdir.mkdir(parents=True, exist_ok=True)
    targets = {"train": pdir / "panel_train.json", "test": pdir / "panel_test.json"}
    for p in targets.values():
        if p.exists():
            raise SystemExit(f"{p} exists; a panel is written once")
    allowed = {"train": train_allowed, "test": held}
    summary = {}
    with ForgePool(max_workers=workers) as pool:
        for role in ("train", "test"):
            spec = proto["panels"][role]
            panel = cg.generate_panel(spec["campaign"], int(spec["n"]), allowed_regions=allowed[role],
                                      min_dist=float(spec.get("min_dist", 0.15)), max_draws=int(spec.get("max_draws", 2000)),
                                      max_per_region=spec.get("max_per_region"), pool=pool)
            panel.update({"role": role, "protocol_id": proto["id"], "protocol_sha256": psha, "code_commit": git_commit(),
                          "heldout_regions": held})
            targets[role].write_text(json.dumps(jsonable(panel), indent=1), encoding="utf-8")
            summary[role] = {"file": str(targets[role]), "accepted": len(panel["accepted"]), "requested": int(spec["n"]),
                             "draws": panel["draws"], "rollouts": panel["rollouts"],
                             "regions": sorted({a["region"] for a in panel["accepted"]})}
    ex.leakage_check([], [], summary["train"]["regions"], summary["test"]["regions"])
    print(json.dumps(summary))
    return 0


def load_panel(proto: dict, pdir: Path, role: str) -> list[dict]:
    p = pdir / f"panel_{role}.json"
    if not p.exists():
        raise SystemExit(f"{p} missing; run --make-panels first")
    panel = json.loads(p.read_text(encoding="utf-8"))
    spec = proto["panels"][role]
    if panel["campaign"] != spec["campaign"] or panel["n_requested"] != int(spec["n"]):
        raise SystemExit(f"{p} does not match the protocol's {role} panel campaign / size")
    held = set(heldout_regions(proto))
    regs = {a["region"] for a in panel["accepted"]}
    if (role == "train" and regs & held) or (role == "test" and not regs <= held):
        raise SystemExit(f"{p}: regions violate the held-out split")
    return [{"id": a["id"], "body": a["body"], "features": a["features"], "region": a["region"]} for a in panel["accepted"]]


def seeds_for(proto: dict, cid: str) -> dict:
    return {r: list(cg.walkrec_seed_block(proto["campaign"], r, cid, int(proto["seeds"][r]))) for r in ("train", "validate", "confirm")}


def joint_space(body_ratio=(0.5, 1.5)) -> "wo.SearchSpace":
    return wo.SearchSpace.full_ctrl_fp(body_params=ex.BODY_DIMS, body_ratio=body_ratio)


# ------------------------------------------------------------------------------------------------------------ collect
def run_collect(proto: dict, c: dict, noise: int, pool) -> dict:
    t0 = time.perf_counter()
    seeds = seeds_for(proto, c["id"])
    init = wo.pad_to_17(list(cw.R2_WINNER))
    cfg = proto["collect"]
    train = seeds["train"][: int(cfg.get("n_train_seeds", len(seeds["train"])))]
    search = wo.cma_search(c["body"], init, joint_space(), budget=int(cfg["budget"]), train_seeds=train, noise_seed=noise, pool=pool,
                           variation=VARIATION_PRESET, checkpoints=(int(cfg["budget"]),), log_candidates=True)
    return jsonable({"unit": f"{c['id']}|collect|{noise}", "kind": "collect", "creature": c["id"], "region": c["region"],
                     "body": c["body"], "features": c["features"], "noise_seed": noise, "seeds": seeds, "search": search,
                     "rollouts": {"search": search["rollouts_used"], "assessment": 0}, "wall_s": time.perf_counter() - t0})


# ------------------------------------------------------------------------------------------------------------ evaluate
def warm_body_ratio(orig: dict, warm: dict) -> tuple[float, float]:
    """(r_lo, r_hi) so that candidate/warm in [r_lo, r_hi] implies candidate/orig in [0.5, 1.5] for all four searched body params."""
    w = [float(warm[p]) / float(orig[p]) for p in ex.BODY_DIMS]
    lo = min(1.0, max(0.5 / x for x in w))
    hi = max(1.0, min(1.5 / x for x in w))
    return lo, hi


def pick_warm(variant: str, n: int, c: dict, recs: list[dict], model, pool_, proto: dict) -> tuple[dict, dict]:
    """(warm item with body/vector, decision record) for a variant; falls back to R2 (recorded) if nothing is inside the bounds."""
    body, f = c["body"], c["features"]
    info: dict = {"variant": variant, "n_train": n}
    item = None
    if variant == "r2":
        item = ex.r2_start(body)
    elif variant == "knn":
        item, disc = ex.realise(ex.knn_warm_start(body, recs, k=len(recs), features=f), body)
        info["discarded"] = disc
    elif variant == "mean_best":
        item, disc = ex.realise(ex.mean_best_start(recs), body)
        info["discarded"] = disc
    elif variant == "learned":
        ev = proto["evaluate"]
        top = ex.propose_warm_starts(model, body, pool_, k=int(ev.get("k_warm", 3)), beta=float(ev.get("beta", ex.DEFAULT_BETA)),
                                     features=f)
        info["top_k"] = [{k: o[k] for k in ("source", "mean", "std", "score", "rank", "applicability", "may_not_apply",
                                            "design", "discarded_before")} for o in top]
        item = top[0] if top else None
        if item is not None:
            info["applicability"], info["may_not_apply"] = item["applicability"], item["may_not_apply"]
            info["discarded"] = item["discarded_before"]
    else:
        raise SystemExit(f"unknown variant {variant!r}")
    info["fallback_to_r2"] = item is None
    if item is None:
        item = ex.r2_start(body)
    info["source"] = item.get("source")
    info["design"] = item["design"]
    info["distance"] = item.get("distance")
    return item, info


def run_eval_unit(proto: dict, c: dict, variant: str, n: int, recs, model, pool_, noise: int, pool) -> dict:
    t0 = time.perf_counter()
    seeds = seeds_for(proto, c["id"])
    orig_body = wo._base_dict(c["body"])
    original = {"body": orig_body, "vector": list(cw.R2_WINNER)}
    warm, decision = pick_warm(variant, n, c, recs, model, pool_, proto)
    wbody, wvec = warm["body"], list(warm["vector"])
    cache: dict[str, dict] = {}

    def assess(cand: dict) -> tuple[str, dict]:
        key = hashlib.sha256(json.dumps(jsonable(cand), sort_keys=True).encode()).hexdigest()
        if key not in cache:
            cache[key] = rc.assess(original, cand, seeds["validate"], seeds["confirm"], pool=pool)
        return key, cache[key]

    def summ(key, a):
        return {"candidate_key": key, "status": a["status"], "reasons": a["reasons"], "walking_frac": a["validation"]["walking_frac"],
                "assessment": a}

    wk, wa = assess({"body": wbody, "vector": wvec})
    warm_assessed = summ(wk, wa)
    lo, hi = warm_body_ratio(orig_body, wbody)
    search = wo.cma_search(wbody, wvec, joint_space((lo, hi)), budget=int(proto["evaluate"]["budget"]), train_seeds=seeds["train"],
                           noise_seed=noise, pool=pool, variation=VARIATION_PRESET,
                           checkpoints=(int(proto["evaluate"]["budget"]),))
    best = search["best"]
    ratios = {p: float(best["body"][p]) / float(orig_body[p]) for p in ex.BODY_DIMS}
    if not all(0.5 - 1e-9 <= r <= 1.5 + 1e-9 for r in ratios.values()):
        raise RuntimeError(f"edit-ratio rule violated for {c['id']}: {ratios}")
    fk, fa = assess({"body": best["body"], "vector": best["vector"]})
    final = summ(fk, fa)
    final.update({"train_score": best["score"], "found_at_rollouts": best["found_at_rollouts"],
                  "edits_vs_original": wo.body_edits(orig_body, best["body"]), "ratios_vs_original": ratios})
    assess_rollouts = sum(v["rollouts"]["validation"] + v["rollouts"]["confirmation"] for v in cache.values())
    return clean(jsonable({
        "unit": f"{c['id']}|{variant}|{n}|{noise}", "kind": "evaluate", "creature": c["id"], "region": c["region"], "body": c["body"],
        "variant": variant, "n_train": n, "noise_seed": noise, "seeds": seeds, "decision": decision,
        "warm_start": {"body": wbody, "vector": wvec, "body_ratio_box": [lo, hi]}, "warm_assessment": warm_assessed,
        "search": search, "final": final, "rollouts": {"search": search["rollouts_used"], "assessment": assess_rollouts},
        "wall_s": time.perf_counter() - t0}))


def read_lines(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--panel-dir", required=True)
    ap.add_argument("--out", help="results JSONL (--collect / --evaluate)")
    ap.add_argument("--collect-file", help="the --collect results used as experience by --evaluate")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--make-panels", action="store_true")
    mode.add_argument("--collect", action="store_true")
    mode.add_argument("--evaluate", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", help="run only this creature id")
    ap.add_argument("--shard", help="i/k: only creatures whose panel index %% k == i")
    a = ap.parse_args()
    ppath = Path(a.protocol)
    proto = json.loads(ppath.read_text(encoding="utf-8"))
    psha = sha256_file(ppath)
    pdir = Path(a.panel_dir)
    if a.make_panels:
        return make_panels(proto, psha, pdir, a.workers)
    if not a.out:
        raise SystemExit("--out is required")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    train_panel, test_panel = load_panel(proto, pdir, "train"), load_panel(proto, pdir, "test")
    ex.leakage_check([c["id"] for c in train_panel], [c["id"] for c in test_panel],
                     {c["region"] for c in train_panel}, {c["region"] for c in test_panel})
    done: set[str] = set()
    used = 0.0
    if out.exists():
        if not a.resume:
            raise SystemExit(f"{out} exists; use --resume to continue (completed units are skipped, never rerun)")
        for r in read_lines(out):
            if r["protocol_sha256"] != psha:
                raise SystemExit("results file was produced under a different protocol; refusing to mix")
            done.add(r["unit"])
            used += r["rollouts"]["search"] + r["rollouts"]["assessment"]
    shard = tuple(int(x) for x in a.shard.split("/")) if a.shard else None
    cap = float(proto["rollout_cap"][("collect" if a.collect else "evaluate")]) if isinstance(proto["rollout_cap"], dict) \
        else float(proto["rollout_cap"])
    commit = git_commit()
    creatures = train_panel if a.collect else test_panel
    if shard:
        mine = sum(1 for i in range(len(creatures)) if i % shard[1] == shard[0])
        cap = cap * mine / max(1, len(creatures))
    noise = int(proto["collect"]["noise_seed"] if a.collect else proto["evaluate"]["noise_seed"])

    recs_all: list[dict] = []
    models: dict[int, tuple] = {}
    ns: list[int] = []
    if a.evaluate:
        if not a.collect_file:
            raise SystemExit("--collect-file is required with --evaluate")
        cpath = Path(a.collect_file)
        by_id = {}
        for r in read_lines(cpath):
            if r["protocol_sha256"] != psha:
                raise SystemExit("collect file was produced under a different protocol; refusing to mix")
            by_id[r["creature"]] = r
        ns = sorted(int(n) for n in proto["evaluate"]["learning_curve"])
        order = [c["id"] for c in train_panel]
        recs_all = [by_id[i] for i in order if i in by_id]
        if [r["creature"] for r in recs_all] != order[: len(recs_all)] or len(recs_all) < max(ns):
            raise SystemExit(f"collect file lacks the first {max(ns)} training creatures in panel order "
                             f"(has {len(recs_all)} contiguous)")
        # variants x N, in a fixed order; r2 does not depend on experience
        units_spec = [("r2", 0)] + [(v, n) for n in ns for v in ("knn", "mean_best", "learned")]
        want = [v for v in proto["evaluate"].get("variants", VARIANTS)]
        units_spec = [(v, n) for v, n in units_spec if v in want]
    with ForgePool(max_workers=a.workers) as pool:
        for idx, c in enumerate(creatures):
            if (a.only and c["id"] != a.only) or (shard and idx % shard[1] != shard[0]):
                continue
            todo = ([("collect", 0)] if a.collect else units_spec)
            for variant, n in todo:
                unit = f"{c['id']}|collect|{noise}" if a.collect else f"{c['id']}|{variant}|{n}|{noise}"
                if unit in done:
                    continue
                budget = int(proto["collect"]["budget"] if a.collect else proto["evaluate"]["budget"])
                worst = budget + (0 if a.collect else 2 * ASSESS_ROLLOUT_EQUIV)
                if used + worst > cap:
                    print(json.dumps({"stop": "rollout cap", "used": used, "next_worst": worst, "cap": cap}), flush=True)
                    return 2
                if a.collect:
                    rec = run_collect(proto, c, noise, pool)
                else:
                    recs = recs_all[:n]
                    model = pool_ = None
                    if variant == "learned":
                        if n not in models:
                            ds = ex.build_dataset(recs)
                            m = proto.get("model", {})
                            model = ex.SurrogateEnsemble(**{**m, "hidden": tuple(m.get("hidden", (64, 64)))}).fit(
                                ds["X"], ds["y"], ds["groups"])
                            models[n] = (model, ex.build_pool(recs, per_creature=int(proto["evaluate"].get("per_creature", 20))))
                        model, pool_ = models[n]
                    if recs:
                        ex.leakage_check([r["creature"] for r in recs], [c["id"]], {r["region"] for r in recs}, {c["region"]})
                    rec = run_eval_unit(proto, c, variant, n, recs, model, pool_, noise, pool)
                rec.update({"protocol_id": proto["id"], "protocol_sha256": psha, "code_commit": commit,
                            "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                with out.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, separators=(",", ":")) + "\n")
                used += rec["rollouts"]["search"] + rec["rollouts"]["assessment"]
                brief = {"unit": unit, "rollouts": rec["rollouts"], "used_total": used, "wall_s": round(rec["wall_s"], 1)}
                if not a.collect:
                    brief.update({"warm": rec["warm_assessment"]["status"], "final": rec["final"]["status"],
                                  "fallback": rec["decision"]["fallback_to_r2"]})
                print(json.dumps(brief), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
