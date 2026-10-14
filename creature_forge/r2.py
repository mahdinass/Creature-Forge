"""R2 - local robustness optimisation around the frozen Phase 2A walker (protocol id phase2a-r2-protocol-v1).

Design and rationale: docs/R2_DESIGN_PROPOSAL.md (approved with corrections) and the immutable
experiments/phase2a_r2/protocol.json built by `build_protocol()`. Nothing here selects with a final seed.

Reuses the R1 machinery (executor, hash-chained ledger, resource probes) but with R2's own caps and its own ledger path.
All incumbent/reference evaluations are accounted for explicitly: the incumbent theta0 is executed (and counted) exactly
once on each of: the 64 screen seeds, the 64 validation seeds, the 150 final seeds, the 32 diagnostic seeds (+32 stress).
Its performance on the 16 training seeds is DERIVED from the screen (identical deterministic rollouts): 0 new rollouts,
recorded in training_set.json, never re-executed.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from . import phase2a, r1, r1_stats, r2_stats
from .locomotion import DEFAULT_CRITERIA, PERTURB, aggregate, compute_metrics, fitness_components, rollout
from .morphology import BipedParams
from .optimize import Executor, jsonable
from .phasegait_init import INIT_DEFAULTS, LOWER15, UPPER15, controller_from_vector

ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = ROOT / "experiments" / "phase2a_r2"
RESULTS = EXP_DIR / "results"
PROTOCOL = EXP_DIR / "protocol.json"
LEDGER = RESULTS / "ledger.jsonl"
SELECTION = RESULTS / "selection.json"
TRAINING_SET = RESULTS / "training_set.json"

PROTOCOL_ID = "phase2a-r2-protocol-v1"
SCREEN_SEEDS = tuple(range(7000, 7064))
VALIDATION_SEEDS = tuple(range(7100, 7164))
DIAGNOSTIC_SEEDS = tuple(range(7200, 7232))
PILOT_SEEDS = tuple(range(7300, 7316))
FINAL_SEEDS = tuple(range(8000, 8150))
N_TRAIN_PER_CLASS = 8
DURATION = 10.0
STRESS_PERTURB = 0.05

BUDGET_CAP = 12000
PILOT_CAP = 100
MAX_WORKERS = 4
MIN_FREE_GB = 4.0
WALL_LIMIT_S = 60 * 60
RNG_BASE = 20261015
TOP_K = 5
FUTILITY_MIN_SEED_GAIN = 5            # of 64 validation seeds (7.8 pp)
NI_MARGIN = 0.05
ALPHA_NI_ONE_SIDED = 0.025
ALPHA_SUP = 0.05
ENGINEERING = {"min_walking_seeds": 135, "n_seeds": 150, "min_median_speed_upright": 0.25, "max_body_dragging_seeds": 0}
ERROR_FITNESS = -10.0
FEASIBILITY_SLACK = 1                 # a candidate must walk on >= W(theta0) - 1 training seeds
ARM_ORDER = ("S", "I", "T")
S_CANDIDATES = 120
S_SCALES = (0.02, 0.05, 0.10, 0.25)
S_KS = (2, 4, 8)
T_LAMBDA = 8
T_GENERATIONS = 15
T_SIGMA0 = 0.05
T_SIGMA_RANGE = (0.005, 0.2)
T_UP, T_DOWN = 1.5, 1.5 ** -0.25      # 1/5 success rule: stationary at success rate 0.2
RAMP_GRID = (0.2, 0.5, 0.8, 1.1, 1.4, 1.7, 2.0)
LEAN_GRID = (0.0, 0.025, 0.05, 0.075, 0.1, 0.125, 0.15)
REPLICATES = {"S": (1, 2), "T": (1, 2), "I": (1,)}
N_GAIT = 13

# ----------------------------------------------------------------------------------------------------------
# seeds
# ----------------------------------------------------------------------------------------------------------
def consumed_seed_sets() -> dict[str, tuple]:
    return {"phase2a_train": phase2a.TRAIN_SEEDS, "phase2a_diagnostic": phase2a.DIAGNOSTIC_SEEDS, "phase2a_heldout": phase2a.HELDOUT_SEEDS,
            "r1_train": r1.TRAIN_SEEDS, "r1_validation": r1.VALIDATION_SEEDS, "r1_diagnostic": r1.DIAGNOSTIC_SEEDS,
            "r1_final": r1.FINAL_SEEDS}


def check_disjoint() -> None:
    mine = {"screen": SCREEN_SEEDS, "validation": VALIDATION_SEEDS, "diagnostic": DIAGNOSTIC_SEEDS, "pilot": PILOT_SEEDS, "final": FINAL_SEEDS}
    allsets = {**mine, **consumed_seed_sets()}
    names = list(allsets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if set(allsets[a]) & set(allsets[b]):
                raise ValueError(f"seed sets overlap: {a} & {b}")


def select_training_seeds(screen_per_seed: list[dict]) -> dict:
    """Deterministic, prespecified: the first 8 incumbent-walking and the first 8 incumbent-NOT-walking seeds of the
    screen in ascending seed order. If either class has fewer than 8 members the registered outcome is STOP (no
    improvised substitute)."""
    ordered = sorted(screen_per_seed, key=lambda m: m["seed"])
    walking = [m["seed"] for m in ordered if m["walking"]]
    failing = [m["seed"] for m in ordered if not m["walking"]]
    out = {"n_screen": len(ordered), "n_incumbent_walking": len(walking), "n_incumbent_failing": len(failing),
           "walking_class": walking[:N_TRAIN_PER_CLASS], "failing_class": failing[:N_TRAIN_PER_CLASS]}
    if len(walking) < N_TRAIN_PER_CLASS or len(failing) < N_TRAIN_PER_CLASS:
        out.update({"stop": True, "reason": f"fewer than {N_TRAIN_PER_CLASS} seeds in an incumbent outcome class "
                                             f"({len(walking)} walking, {len(failing)} failing); registered STOP"})
        out["train_seeds"] = []
    else:
        out.update({"stop": False, "train_seeds": sorted(out["walking_class"] + out["failing_class"])})
    return out


def train_seeds() -> tuple[int, ...]:
    ts = json.loads(TRAINING_SET.read_text(encoding="utf-8"))
    if ts.get("stop"):
        raise SystemExit("training_set.json records the registered STOP: " + ts["reason"])
    return tuple(ts["train_seeds"])


# ----------------------------------------------------------------------------------------------------------
# parameter space and candidate generation (reproducible, always within bounds)
# ----------------------------------------------------------------------------------------------------------
def incumbent_theta() -> np.ndarray:
    return r1.incumbent_vector(15)


def to_u(theta) -> np.ndarray:
    return (np.asarray(theta, float) - LOWER15) / (UPPER15 - LOWER15)


def from_u(u) -> np.ndarray:
    return LOWER15 + (UPPER15 - LOWER15) * np.asarray(u, float)


def reflect(u) -> np.ndarray:
    """Fold values into [0, 1] by reflection at the bounds (a step across a bound returns inside by the overshoot)."""
    x = np.mod(np.asarray(u, float), 2.0)
    return np.where(x > 1.0, 2.0 - x, x)


def s_candidates(rep: int) -> list[dict]:
    """Arm S: candidate i (0-based) uses scale S_SCALES[i % 4] and subset size S_KS[(i % 12) // 4]; the coordinate subset and
    Gaussian deltas come from one sequential stream per replicate. Only the 13 gait coordinates are perturbed."""
    rng = np.random.default_rng(np.random.SeedSequence([RNG_BASE, 1, rep]))
    u0 = to_u(incumbent_theta())
    out = []
    for i in range(S_CANDIDATES):
        sigma, k = S_SCALES[i % 4], S_KS[(i % 12) // 4]
        coords = sorted(int(c) for c in rng.choice(N_GAIT, size=k, replace=False))
        delta = rng.normal(0.0, sigma, size=k)
        u = u0.copy()
        u[coords] += delta
        u = reflect(u)
        out.append({"index": i, "sigma": sigma, "k": k, "coords": coords, "vector": from_u(u).tolist()})
    return out


def i_candidates() -> list[dict]:
    """Arm I: the exact 7x7 grid over (ramp_s, start_lean), other 13 coordinates = theta0. Index = 7*ramp_idx + lean_idx.
    The grid point (0.5, 0.0) IS theta0: it is marked `reference`, never executed, and uses the screen-derived result."""
    base = incumbent_theta()
    out = []
    for ri, ramp in enumerate(RAMP_GRID):
        for li, lean in enumerate(LEAN_GRID):
            v = base.copy()
            v[13], v[14] = ramp, lean
            ref = bool(ramp == INIT_DEFAULTS["ramp_s"] and lean == INIT_DEFAULTS["start_lean"])
            out.append({"index": 7 * ri + li, "ramp_s": ramp, "start_lean": lean, "reference": ref, "vector": v.tolist()})
    return out


def t_offspring(rep: int, gen: int, parent_u: np.ndarray, sigma: float, z_all: np.ndarray) -> list[list[float]]:
    return [from_u(reflect(parent_u + sigma * z_all[gen, i])).tolist() for i in range(T_LAMBDA)]


def t_noise(rep: int) -> np.ndarray:
    """All Gaussian draws for arm T replicate `rep`: shape (generations, lambda, 15); independent of outcomes."""
    rng = np.random.default_rng(np.random.SeedSequence([RNG_BASE, 3, rep]))
    return rng.standard_normal((T_GENERATIONS, T_LAMBDA, 15))


def _round_nested(x, nd=12):
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, (list, tuple)):
        return [_round_nested(v, nd) for v in x]
    if isinstance(x, dict):
        return {k: _round_nested(v, nd) for k, v in x.items()}
    return x


def candidate_manifest_sha256() -> str:
    """Hash of every S vector (both replicates), the full I grid, the T noise (rep 1 & 2) and theta0, rounded to 12 digits
    so a 1-ulp platform difference in a Gaussian tail draw cannot change it."""
    blob = {"theta0": incumbent_theta().tolist(), "S": {str(r): [c["vector"] for c in s_candidates(r)] for r in REPLICATES["S"]},
            "I": [c["vector"] for c in i_candidates()],
            "T_noise": {str(r): t_noise(r).tolist() for r in REPLICATES["T"]}}
    return hashlib.sha256(json.dumps(_round_nested(blob), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ----------------------------------------------------------------------------------------------------------
# training score, feasibility, ranking
# ----------------------------------------------------------------------------------------------------------
def score_of(rec: dict) -> tuple:
    return (rec["walking_count"], rec["survival_count"], rec["objective"]["mean"])


def is_feasible(rec: dict, w0: int) -> bool:
    return rec["error"] is None and rec["walking_count"] >= w0 - FEASIBILITY_SLACK


def train_sort_key(rec: dict, w0: int):
    s = score_of(rec)
    return (not is_feasible(rec, w0), -s[0], -s[1], -s[2], rec["index"])


def rank_training(history: list[dict], w0: int) -> list[int]:
    """Indices into `history` (executed candidates only), best first: feasible first, then (walking, non-falling, mean fitness)."""
    cand = [i for i, h in enumerate(history) if not h.get("reference")]
    return sorted(cand, key=lambda i: train_sort_key(history[i], w0))


def better(a: dict, b: dict) -> bool:
    return score_of(a) > score_of(b)


# ----------------------------------------------------------------------------------------------------------
# ledger (R1's hash-chained ledger with R2's caps) and resources
# ----------------------------------------------------------------------------------------------------------
class Ledger(r1.Ledger):
    def __init__(self, path: Path = LEDGER):
        super().__init__(path)

    def begin(self, stage: str, rollouts: int, note: str = "") -> int:
        self.verify()
        if self.total_rollouts() + rollouts > BUDGET_CAP:
            raise r1.BudgetExceeded(f"{self.total_rollouts()} + {rollouts} would exceed the hard cap {BUDGET_CAP}")
        if stage == "pilot" and self.stage_rollouts("pilot") + rollouts > PILOT_CAP:
            raise r1.BudgetExceeded(f"pilot is capped at {PILOT_CAP} rollouts")
        bid = sum(e["event"] == "begin" for e in self.entries()) + 1
        self._append({"event": "begin", "id": bid, "stage": stage, "rollouts": int(rollouts), "note": note,
                      "cumulative_after": self.total_rollouts() + int(rollouts)})
        return bid


def check_resources(ledger: Ledger) -> None:
    free = r1.free_memory_gb()
    if free < MIN_FREE_GB:
        raise r1.ResourceAbort(f"free memory {free:.2f} GB is below the {MIN_FREE_GB} GB floor")
    if ledger.total_wall_s() >= WALL_LIMIT_S:
        raise r1.ResourceAbort(f"cumulative active wall time {ledger.total_wall_s():.0f}s reached the {WALL_LIMIT_S}s hard stop")


# ----------------------------------------------------------------------------------------------------------
# jobs / batches
# ----------------------------------------------------------------------------------------------------------
def r2_job(job: dict) -> dict:
    t0 = time.perf_counter()
    try:
        ctrl = controller_from_vector(job["vector"])
        body = BipedParams(**job["body"])
        per = []
        for s in job["seeds"]:
            m = compute_metrics(rollout(ctrl, body, s, job["duration"], perturb=job.get("perturb", PERTURB)), DEFAULT_CRITERIA)
            m["fitness"] = fitness_components(m, DEFAULT_CRITERIA)
            per.append(m)
        return {"ok": True, "result": aggregate(per), "wall_s": time.perf_counter() - t0, "peak_rss_mb": r1.peak_rss_mb()}
    except Exception as e:  # recorded, never swallowed
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "wall_s": time.perf_counter() - t0, "peak_rss_mb": r1.peak_rss_mb()}


def make_jobs(vectors, seeds, duration: float = DURATION, perturb: float | None = None) -> list[dict]:
    body = BipedParams().as_dict()
    jobs = [{"vector": [float(x) for x in v], "body": body, "seeds": list(seeds), "duration": duration} for v in vectors]
    if perturb is not None:
        for j in jobs:
            j["perturb"] = perturb
    return jobs


def run_batch(ex: Executor, ledger: Ledger, stage: str, vectors, seeds, note: str = "", perturb: float | None = None) -> list[dict]:
    """One counted batch: check resources -> ledger.begin (before any physics) -> execute -> ledger.end."""
    check_resources(ledger)
    n = len(vectors) * len(seeds)
    bid = ledger.begin(stage, n, note)
    t0 = time.perf_counter()
    outs = ex.map(make_jobs(vectors, seeds, perturb=perturb))
    errors = sum(not o["ok"] for o in outs)
    peak = max((o.get("peak_rss_mb") or 0.0) for o in outs)
    ledger.end(bid, executed=n, errors=errors, wall_s=time.perf_counter() - t0, peak_rss_mb_=peak, free_gb=r1.free_memory_gb())
    return outs


def make_record(vector, out: dict, seeds, extra: dict) -> dict:
    rec = r1._record(vector, out, seeds, extra)       # error -> fitness -10 and zero counts; otherwise compact per-seed metrics
    return rec


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(obj), indent=1, allow_nan=False) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------------------------------------
# stages
# ----------------------------------------------------------------------------------------------------------
def run_screen(ex: Executor, ledger: Ledger, out_dir: Path = RESULTS) -> dict:
    path = out_dir / "screen.json"
    if path.exists():
        raise FileExistsError(f"{path} exists: the incumbent screen is executed once")
    vec = incumbent_theta()
    outs = run_batch(ex, ledger, "screen", [vec], SCREEN_SEEDS, "frozen incumbent on the 64 screen seeds (once)")
    res = make_record(vec, outs[0], SCREEN_SEEDS, {"arm": "incumbent", "role": "screen"})
    if res["error"] is not None:
        raise RuntimeError("incumbent screen failed: " + res["error"])
    write_json(path, res)
    return res


def freeze_training_set(out_dir: Path = RESULTS) -> dict:
    """Pure computation from screen.json (0 rollouts). Writes training_set.json, to be committed before any optimisation."""
    path = out_dir / "training_set.json"
    if path.exists():
        raise FileExistsError(f"{path} exists: the training set is frozen")
    screen = json.loads((out_dir / "screen.json").read_text(encoding="utf-8"))
    sel = select_training_seeds(screen["per_seed"])
    by_seed = {m["seed"]: m for m in screen["per_seed"]}
    ref = [by_seed[s] for s in sel["train_seeds"]]
    sel["incumbent_on_training_seeds"] = {
        "derived_from_screen_no_new_rollouts": True, "per_seed": ref,
        "walking_count": int(sum(m["walking"] for m in ref)), "survival_count": int(sum(not m["fell"] for m in ref)),
        "mean_fitness": float(np.mean([m["fitness"] for m in ref])) if ref else None,
        "body_dragging_seeds": int(sum("body_dragging" in m["violations"] for m in ref))}
    sel["rule"] = ("first 8 incumbent-walking and first 8 incumbent-not-walking seeds of 7000-7063, ascending seed order; "
                   "STOP if either class has fewer than 8")
    sel["screen_sha256"] = r1.sha256_file(out_dir / "screen.json")
    write_json(path, sel)
    return sel


def incumbent_training_reference(ts: dict | None = None) -> dict:
    ts = ts or json.loads(TRAINING_SET.read_text(encoding="utf-8"))
    return ts["incumbent_on_training_seeds"]


def incumbent_parent_record(ts: dict | None = None) -> dict:
    """theta0 as a history-like record on the training seeds (derived from the screen; not re-executed)."""
    ref = incumbent_training_reference(ts)
    return {"error": None, "walking_count": ref["walking_count"], "survival_count": ref["survival_count"],
            "objective": {"mean": ref["mean_fitness"]}, "vector": incumbent_theta().tolist(), "index": -1, "reference": True}


def _hist_path(arm: str, rep: int, out_dir: Path) -> Path:
    return out_dir / f"history_{arm}{rep}.jsonl"


def _append_history(path: Path, recs: list[dict]) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(r, allow_nan=False) + "\n" for r in recs)


def run_training_S(rep: int, ex: Executor, ledger: Ledger, seeds, out_dir: Path = RESULTS, batch: int = 20) -> list[dict]:
    path = _hist_path("S", rep, out_dir)
    if path.exists():
        raise FileExistsError(f"{path} exists: runs are never silently repeated")
    cands = s_candidates(rep)
    out_dir.mkdir(parents=True, exist_ok=True)
    hist: list[dict] = []
    for lo in range(0, len(cands), batch):
        chunk = cands[lo:lo + batch]
        outs = run_batch(ex, ledger, f"train-S{rep}", [c["vector"] for c in chunk], seeds, f"S{rep} candidates {lo}-{lo + len(chunk) - 1}")
        recs = [make_record(c["vector"], o, seeds, {"arm": "S", "replicate": rep, "index": c["index"], "sigma": c["sigma"], "k": c["k"],
                                                    "coords": c["coords"]}) for c, o in zip(chunk, outs)]
        hist.extend(recs)
        _append_history(path, recs)
    return hist


def run_training_I(ex: Executor, ledger: Ledger, seeds, out_dir: Path = RESULTS) -> list[dict]:
    path = _hist_path("I", 1, out_dir)
    if path.exists():
        raise FileExistsError(f"{path} exists: runs are never silently repeated")
    grid = i_candidates()
    todo = [c for c in grid if not c["reference"]]
    out_dir.mkdir(parents=True, exist_ok=True)
    outs = run_batch(ex, ledger, "train-I1", [c["vector"] for c in todo], seeds, "I grid: 48 executed + 1 reference (theta0, derived)")
    hist = []
    for c, o in zip(todo, outs):
        hist.append(make_record(c["vector"], o, seeds, {"arm": "I", "replicate": 1, "index": c["index"], "ramp_s": c["ramp_s"],
                                                        "start_lean": c["start_lean"]}))
    _append_history(path, hist)
    return hist


def run_training_T(rep: int, ex: Executor, ledger: Ledger, seeds, w0: int, parent_rec: dict, out_dir: Path = RESULTS) -> list[dict]:
    """(1+lambda)-ES with 1/5-rule step size. `parent_rec` is theta0's screen-derived record on the training seeds (not re-executed)."""
    path = _hist_path("T", rep, out_dir)
    if path.exists():
        raise FileExistsError(f"{path} exists: runs are never silently repeated")
    out_dir.mkdir(parents=True, exist_ok=True)
    noise = t_noise(rep)
    parent = parent_rec
    parent_u = to_u(incumbent_theta())
    sigma = T_SIGMA0
    hist: list[dict] = []
    for g in range(T_GENERATIONS):
        vecs = t_offspring(rep, g, parent_u, sigma, noise)
        outs = run_batch(ex, ledger, f"train-T{rep}", vecs, seeds, f"T{rep} generation {g} sigma={sigma:.5f}")
        recs = []
        for i, (v, o) in enumerate(zip(vecs, outs)):
            recs.append(make_record(v, o, seeds, {"arm": "T", "replicate": rep, "index": g * T_LAMBDA + i, "generation": g,
                                                  "sigma": sigma, "parent_score": list(score_of(parent))}))
        feas = [r for r in recs if is_feasible(r, w0)]
        succ = [r for r in feas if better(r, parent)]
        ps = len(succ) / T_LAMBDA
        if succ:
            best = max(succ, key=lambda r: (score_of(r), -r["index"]))
            parent, parent_u = best, to_u(best["vector"])
        for r in recs:
            r["generation_success_rate"] = ps
        hist.extend(recs)
        _append_history(path, recs)
        sigma = float(np.clip(sigma * (T_UP if ps > 0.2 else (T_DOWN if ps < 0.2 else 1.0)), *T_SIGMA_RANGE))
    return hist


def run_validation(arm: str, rep: int, history: list[dict], w0: int, ex: Executor, ledger: Ledger, out_dir: Path = RESULTS) -> dict:
    path = out_dir / f"validation_{arm}{rep}.json"
    if path.exists():
        raise FileExistsError(f"{path} exists: validation is never silently repeated")
    top = rank_training(history, w0)[:TOP_K]
    outs = run_batch(ex, ledger, f"validate-{arm}{rep}", [history[i]["vector"] for i in top], VALIDATION_SEEDS,
                     f"{arm}{rep} validation of history positions {top}")
    recs = [make_record(history[i]["vector"], o, VALIDATION_SEEDS,
                        {"arm": arm, "replicate": rep, "index": history[i]["index"], "training_rank": k + 1,
                         "training_score": list(score_of(history[i])), "training_feasible": is_feasible(history[i], w0)})
            for k, (i, o) in enumerate(zip(top, outs))]
    res = {"arm": arm, "replicate": rep, "top5_history_positions": top, "validated": recs}
    write_json(path, res)
    return res


def run_incumbent_validation(ex: Executor, ledger: Ledger, out_dir: Path = RESULTS) -> dict:
    path = out_dir / "validation_incumbent.json"
    if path.exists():
        raise FileExistsError(f"{path} exists")
    vec = incumbent_theta()
    outs = run_batch(ex, ledger, "validate-incumbent", [vec], VALIDATION_SEEDS, "frozen incumbent (once)")
    res = make_record(vec, outs[0], VALIDATION_SEEDS, {"arm": "incumbent", "replicate": 0, "index": 0})
    write_json(path, res)
    return res


# ----------------------------------------------------------------------------------------------------------
# gate / selection (prespecified)
# ----------------------------------------------------------------------------------------------------------
def n_dragging(rec: dict) -> int:
    return int(sum("body_dragging" in m["violations"] for m in rec["per_seed"]))


def eligible(rec: dict, inc: dict) -> bool:
    """Validated, no error, and preserving: not more body-dragging seeds and not fewer non-falling seeds than theta0."""
    return rec["error"] is None and n_dragging(rec) <= n_dragging(inc) and rec["survival_count"] >= inc["survival_count"]


def validation_sort_key(rec: dict):
    return (-rec["walking_count"], -rec["survival_count"], -rec["objective"]["mean"], ARM_ORDER.index(rec["arm"]),
            rec["replicate"], rec["index"])


def rank_eligible(recs: list[dict], inc: dict) -> list[dict]:
    return sorted([r for r in recs if eligible(r, inc)], key=validation_sort_key)


def futility_gate(validations: dict, inc: dict) -> dict:
    arms = {}
    for arm, results in validations.items():
        recs = rank_eligible([r for res in results for r in res["validated"]], inc)
        best = recs[0] if recs else None
        gain = (best["walking_count"] - inc["walking_count"]) if best else None
        arms[arm] = {"best": None if best is None else {"index": best["index"], "replicate": best["replicate"],
                                                          "walking_count": best["walking_count"], "survival_count": best["survival_count"]},
                     "incumbent_walking_count": inc["walking_count"], "gain_seeds": gain,
                     "gain_percentage_points": None if gain is None else 100.0 * gain / len(VALIDATION_SEEDS),
                     "meets_threshold": bool(gain is not None and gain >= FUTILITY_MIN_SEED_GAIN)}
    return {"arms": arms, "proceed": any(a["meets_threshold"] for a in arms.values()),
            "threshold": f">= {FUTILITY_MIN_SEED_GAIN} more of the {len(VALIDATION_SEEDS)} validation seeds walking than the incumbent, "
                         "among preserving candidates; a pragmatic stopping heuristic, not a significance test"}


def select_winner(validations: list[dict], inc: dict) -> dict:
    recs = rank_eligible([r for res in validations for r in res["validated"]], inc)
    if not recs:
        raise RuntimeError("no eligible validated candidate")
    return recs[0]


# ----------------------------------------------------------------------------------------------------------
# final analysis
# ----------------------------------------------------------------------------------------------------------
def engineering_verdict(per_seed: list[dict]) -> dict:
    e = ENGINEERING
    walking = int(sum(m["walking"] for m in per_seed))
    med = float(np.median([m["speed_upright"] for m in per_seed]))
    drag = int(sum("body_dragging" in m["violations"] for m in per_seed))
    ok = len(per_seed) == e["n_seeds"] and walking >= e["min_walking_seeds"] and med >= e["min_median_speed_upright"] \
        and drag <= e["max_body_dragging_seeds"]
    return {"meets_engineering_criterion": bool(ok), "walking_seeds": walking, "n_seeds": len(per_seed),
            "median_speed_upright": med, "body_dragging_seeds": drag, "criterion": e,
            "caveat": "135/150 does not establish a true success probability >= 90%; see the exact interval"}


def final_analysis(winner_per_seed: list[dict], inc_per_seed: list[dict]) -> dict:
    """Winner ("new") vs frozen incumbent ("old") on the same final seeds. Confirmatory: hierarchical decision
    (non-inferiority then superiority). Engineering success and descriptive intervals are reported separately."""
    new = [m["walking"] for m in winner_per_seed]
    old = [m["walking"] for m in inc_per_seed]
    t = r1_stats.paired_table(new, old)
    return {"paired_table": t, "confirmatory_hierarchy": r2_stats.hierarchical_decision(t["new_only"], t["old_only"], t["n"], NI_MARGIN, ALPHA_NI_ONE_SIDED, ALPHA_SUP),
            "descriptive_paired_comparison": r1_stats.paired_comparison(new, old, alpha=ALPHA_SUP),
            "engineering": {"winner": engineering_verdict(winner_per_seed), "incumbent": engineering_verdict(inc_per_seed)}}


# ----------------------------------------------------------------------------------------------------------
# protocol
# ----------------------------------------------------------------------------------------------------------
def sha256_lf(path: Path) -> str:
    """sha256 of the file with CRLF normalised to LF, so the registered hash is the same on Windows and Linux checkouts."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def planned_budget() -> dict:
    n_s = S_CANDIDATES * len(REPLICATES["S"]) * 16
    n_t = T_LAMBDA * T_GENERATIONS * len(REPLICATES["T"]) * 16
    n_i = 48 * 16
    val = (len(REPLICATES["S"]) + len(REPLICATES["T"]) + len(REPLICATES["I"])) * TOP_K * len(VALIDATION_SEEDS) + len(VALIDATION_SEEDS)
    return {"pilot": 96, "screen": len(SCREEN_SEEDS), "training_S": n_s, "training_T": n_t, "training_I": n_i, "validation": val,
            "final": 2 * len(FINAL_SEEDS), "diagnostic": 2 * 2 * len(DIAGNOSTIC_SEEDS),
            "total": 96 + len(SCREEN_SEEDS) + n_s + n_t + n_i + val + 2 * len(FINAL_SEEDS) + 4 * len(DIAGNOSTIC_SEEDS)}


def build_protocol() -> dict:
    check_disjoint()
    r1_protocol = r1.PROTOCOL
    return {
        "id": PROTOCOL_ID,
        "status": "immutable once committed; changes require a new protocol id and re-registration",
        "question": ("Starting from the frozen Phase 2A walker (theta0), does a LOCAL search in normalised parameter space, trained "
                     "for robustness across initial conditions, produce a controller that (a) preserves walking (non-inferiority, margin "
                     "5 percentage points) and (b) improves it (superiority) on untouched fresh seeds? This is a refinement experiment; "
                     "it cannot show discovery of a gait from scratch."),
        "basis": ["docs/R1_SEARCH_ANALYSIS.md (post-hoc)", "docs/R2_DESIGN_PROPOSAL.md (approved with corrections 2026-10-14)"],
        "frozen_inputs": {"incumbent_export": r1.INCUMBENT_FILE.relative_to(ROOT).as_posix(),
                          "incumbent_sha256_lf": sha256_lf(r1.INCUMBENT_FILE),
                          "phase2a_protocol_sha256_lf": sha256_lf(phase2a.PROTOCOL),
                          "r1_protocol_sha256_lf": sha256_lf(r1_protocol),
                          "hashing": "sha256 of file bytes with CRLF normalised to LF (platform independent)"},
        "morphology": BipedParams().as_dict(),
        "walking_criteria": DEFAULT_CRITERIA.as_dict(),
        "controller": "PhaseGaitInitController, 15 parameters (13 gait + ramp_s + start_lean), bounds INIT_BOUNDS/phasegait.BOUNDS; no FSM, no RL",
        "parameter_space": {"normalisation": "u = (theta - lower) / (upper - lower), 15 coordinates",
                            "reflection": "values crossing a bound are reflected back inside (u -> fold into [0,1])",
                            "theta0_normalised": dict(zip([f"p{i}" for i in range(15)], [round(float(x), 6) for x in to_u(incumbent_theta())]))},
        "seeds": {"screen": list(SCREEN_SEEDS), "train": "derived from the screen (see training_selection); frozen in results/training_set.json before any candidate optimisation",
                  "validation": list(VALIDATION_SEEDS), "diagnostic": list(DIAGNOSTIC_SEEDS), "pilot": list(PILOT_SEEDS),
                  "final": list(FINAL_SEEDS)},
        "seed_policy": ("pilot seeds 7300-7315 are used ONLY for implementation and resource checks and are disjoint from every other "
                        "role; screen: theta0 only, executed once; train: the 16 selected screen seeds (the screen outcomes of theta0 "
                        "decide membership, nothing else); validation: choose among each run's top-5, the futility gate and the winner; "
                        "diagnostic: post-hoc analysis only (after the final), never used for selection; final: touched once, after "
                        "selection.json is committed. Consumed and excluded: " +
                        ", ".join(f"{k} ({min(v)}-{max(v)})" for k, v in consumed_seed_sets().items()) + "."),
        "durations_s": {"screen": DURATION, "train": DURATION, "validation": DURATION, "final": DURATION, "diagnostic": DURATION, "pilot": DURATION},
        "initial_state": "torso pitch and 6 joint angles ~ N(0, 0.03 rad) from the episode seed; feet 2 mm above floor; diagnostic stress variant N(0, 0.05) on the same diagnostic seeds, never used for selection",
        "training_selection": {"rule": "first 8 incumbent-walking and first 8 incumbent-not-walking seeds of the screen, ascending seed order",
                               "insufficient_class": "if either class has fewer than 8 members the registered outcome is STOP (null: screen unusable); no substitute rule",
                               "frozen_in": "experiments/phase2a_r2/results/training_set.json, committed before any candidate is optimised"},
        "training_criterion": {"order": ["number of training seeds passing every walking gate", "number of non-falling seeds", "mean per-seed fitness (locomotion.fitness_components)"],
                               "feasibility": f"walking_count >= W(theta0) - {FEASIBILITY_SLACK}; infeasible candidates rank below all feasible ones",
                               "theta0_on_training_seeds": "derived from the screen (identical deterministic rollouts): 0 new rollouts, recorded in training_set.json, never re-executed"},
        "arms": {
            "S": {"method": "non-adaptive subset perturbation of theta0 in u-space", "replicates": list(REPLICATES["S"]), "candidates_per_replicate": S_CANDIDATES,
                  "scales_sigma_u": list(S_SCALES), "subset_sizes_k": list(S_KS),
                  "assignment": "candidate i: sigma = scales[i % 4], k = sizes[(i % 12) // 4]; subset = sorted rng.choice(13, k) of the gait coordinates; deltas ~ N(0, sigma) from one sequential stream default_rng(SeedSequence([rng_base, 1, rep])); reflection at bounds; ramp_s/start_lean fixed at theta0",
                  "evaluations_per_candidate": 16},
            "I": {"method": "exhaustive 7x7 grid over (ramp_s, start_lean); other 13 coordinates = theta0", "ramp_s_grid": list(RAMP_GRID),
                  "start_lean_grid": list(LEAN_GRID), "index": "7 * ramp_index + lean_index", "candidates": 49,
                  "reference_point": "grid point (ramp_s 0.5, start_lean 0.0) equals theta0: marked reference, NOT executed (0 rollouts), derived from the screen; 48 candidates executed",
                  "replicates": [1], "evaluations_per_candidate": 16},
            "T": {"method": "(1+lambda)-ES with 1/5 success rule over all 15 coordinates in u-space", "lambda": T_LAMBDA, "generations": T_GENERATIONS,
                  "replicates": list(REPLICATES["T"]), "sigma0": T_SIGMA0, "sigma_range": list(T_SIGMA_RANGE),
                  "step_rule": f"success rate p = (# feasible offspring strictly better than the parent)/lambda; sigma *= {T_UP} if p > 0.2, *= 1.5^(-1/4) if p < 0.2, unchanged if p == 0.2; clipped to the range",
                  "offspring": "u_parent + sigma * z, z from default_rng(SeedSequence([rng_base, 3, rep])).standard_normal((generations, lambda, 15)) (outcome-independent), then reflection",
                  "parent_update": "best strictly-better feasible offspring (lexicographic training criterion, ties: earlier index) replaces the parent; otherwise the parent stays; the initial parent is theta0 (screen-derived)",
                  "evaluations_per_candidate": 16},
            "not_used": "sep-CMA-ES (too little information per evaluation to justify it); possible later comparison"},
        "candidate_generation": {"rng_base": RNG_BASE, "candidate_manifest_sha256": candidate_manifest_sha256(),
                                 "manifest_note": "sha256 of every S vector (both replicates), the full I grid, the T noise tensors and theta0, rounded to 12 digits"},
        "validation": {"top_k_per_run": TOP_K, "seeds": list(VALIDATION_SEEDS), "ranking": "training criterion (feasible first); top-5 history positions per run",
                       "incumbent": "validated once on the same 64 seeds (64 rollouts)", "runs": ["S1", "S2", "T1", "T2", "I1"]},
        "eligibility": "validated, no error, number of body-dragging seeds <= theta0's and number of non-falling seeds >= theta0's (preservation)",
        "selection_rule": ("Eligible candidates ranked by (1) validation seeds passing every walking gate, (2) non-falling validation seeds, (3) mean "
                           "validation fitness, higher better; ties by arm order S<I<T, replicate, candidate index. Origin plays no role; training "
                           "ranks and final seeds play no part."),
        "futility": {"after": "replicate 1 of S and T and the I run are trained and validated",
                     "rule": f"stop and report a null result unless some arm's best eligible validated candidate passes every walking gate on at least {FUTILITY_MIN_SEED_GAIN} more of the 64 validation seeds than theta0",
                     "nature": "pragmatic stopping heuristic, not a significance test",
                     "if_proceeding": "replicate 2 of S and T (training + validation), then selection of ONE winner, committed before the final evaluation"},
        "final_evaluation": {
            "controllers": ["selected winner", "frozen Phase 2A incumbent theta0"], "seeds": list(FINAL_SEEDS), "n": len(FINAL_SEEDS),
            "conditions": "identical seeds, duration, morphology and gates; each controller executed once on the 150 seeds",
            "confirmatory_hierarchy": {
                "order": "fixed sequence; each step at its full level; step 2 is tested only if step 1 succeeds",
                "step1_noninferiority": {"parameter": "theta = p_win - p_inc (paired risk difference of 'passes every walking gate')",
                                         "H0": f"theta <= -{NI_MARGIN}", "H1": f"theta > -{NI_MARGIN}",
                                         "test": "Tango (1998) score test for the paired risk difference with nonzero margin (creature_forge.r2_stats)",
                                         "decision_rule": f"non-inferior iff the Tango score statistic at the margin exceeds z(1-{ALPHA_NI_ONE_SIDED}) = 1.959964, i.e. the lower bound of the two-sided 95% Tango score interval exceeds -{NI_MARGIN}",
                                         "alpha_one_sided": ALPHA_NI_ONE_SIDED},
                "step2_superiority": {"test": "exact two-sided McNemar on the paired outcomes", "alpha": ALPHA_SUP, "requires": "p < alpha AND winner-only successes > incumbent-only successes"},
                "if_step1_fails": "superiority is not tested confirmatorily (descriptive p reported)"},
            "engineering_criterion": {**ENGINEERING, "note": "reported separately from the statistical claims"},
            "reporting": ["paired 2x2 table", "discordant counts", "Tango non-inferiority statistic, one-sided p and 95% interval", "exact McNemar p",
                          "paired difference with Newcombe 95% interval", "Wilson and exact intervals per controller", "conditional odds ratio",
                          "basin map: P(feasible | sigma_u, k) for arm S with Wilson intervals (descriptive)"],
            "caveat": "arm comparisons are exploratory; only the winner-vs-theta0 hierarchy is confirmatory"},
        "diagnostic": {"controllers": ["winner", "theta0"], "seeds": list(DIAGNOSTIC_SEEDS), "runs": ["standard N(0,0.03)", f"stress N(0,{STRESS_PERTURB})"],
                       "when": "after the final evaluation; post-hoc, never used to select, tune or stop"},
        "budget": {"hard_cap_rollouts": BUDGET_CAP, "pilot_cap_rollouts": PILOT_CAP, "planned": planned_budget(),
                   "counted": "every MuJoCo rollout executed or started: pilot, screen, training, validation, final, diagnostics, duplicates, retries, failed jobs, reruns",
                   "reference_evaluations": ("theta0 is executed exactly once on each of: screen (64), validation (64), final (150), diagnostic (32) and "
                                             "diagnostic stress (32); its training-seed performance is derived from the screen (0 rollouts); the I-grid "
                                             "reference point is not executed. No silent repetition."),
                   "ledger": "experiments/phase2a_r2/results/ledger.jsonl (append-only, hash-chained; begin entries precede physics; session_begin/session_end events feed the wall guard)",
                   "no_automatic_extension": True},
        "resources": {"max_workers": MAX_WORKERS, "min_free_memory_gb": MIN_FREE_GB, "wall_clock_hard_stop_s": WALL_LIMIT_S,
                      "wall_definition": "cumulative ACTIVE time over all script sessions (ledger session events), not idle time between runs",
                      "start_method": "spawn", "no_overlap_with_verification": True,
                      "pilot": (f"at most {PILOT_CAP} rollouts: theta0 + 5 candidates (S index 0 of replicate 1, S index 6 of replicate 1, T generation-0 offspring 0 and 1 "
                                "of replicate 1, I grid index 24) x 16 pilot seeds 7300-7315 = 96; it checks code paths (reflection at bounds, ledger, "
                                "determinism between two workers) and resources only and can change nothing in this protocol")},
        "stopping_rules": ["any lost or errored job, memory abort, wall-clock stop or budget breach stops the run (no silent retry)",
                           "futility gate STOP and the screen insufficient-class STOP are reported as the result",
                           "the final evaluation runs once and cannot be used to revise the controller, objective, gates or stopping rule",
                           "a null or partial result is reported as such; the search is not extended automatically"],
    }


def require_preregistration(need_training_set: bool = False, need_selection: bool = False) -> dict:
    commits = {"protocol": phase2a.committed_unmodified(PROTOCOL)}
    stored = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if stored != json.loads(json.dumps(build_protocol())):
        raise RuntimeError("protocol.json no longer matches the code that defines it or its frozen inputs; re-registration required")
    if need_training_set:
        commits["training_set"] = phase2a.committed_unmodified(TRAINING_SET)
    if need_selection:
        commits["selection"] = phase2a.committed_unmodified(SELECTION)
    return commits
