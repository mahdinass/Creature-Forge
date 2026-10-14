"""Phase 2A-R1 (robustness) experiment: protocol, budget ledger, resource guards, training, validation, selection.

Pre-registered in experiments/phase2a_r1/protocol.json (committed before any optimisation). Design:
  arms     A: 13-D, mean fitness over 8 training seeds, 10 s episodes
           B: as A but lower-tail fitness (mean of the worst 2 of the 8 per-seed fitnesses)
           C: as B plus the optional initiation parameters ramp_s, start_lean (15-D)
  runs     2 independent random-search replicates per arm, 150 candidates each; candidate 0 is the frozen Phase 2A
           incumbent. Candidates 1..149 are shared (common random numbers) by arms A/B/C in the first 13 dims.
  seeds    train 4000-4007, validation 4100-4115, diagnostic 5000-5009, final 6000-6029 (disjoint from each other and
           from every Phase 2A seed). Final seeds are touched only by scripts/eval_r1_final.py after the selection is
           committed.
  budget   hard cap of 8,500 actual MuJoCo rollouts across everything, counted in an append-only hash-chained ledger
           (every started batch counts, including duplicates, retries and failed/crashed jobs).
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import phase2a
from .locomotion import DEFAULT_CRITERIA, PERTURB, aggregate, compute_metrics, fitness_components, rollout
from .morphology import BipedParams
from .optimize import Executor, jsonable
from .phasegait import LOWER, UPPER, PhaseGaitParams
from .phasegait_init import INIT_BOUNDS, INIT_DEFAULTS, LOWER15, UPPER15, controller_from_vector

ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = ROOT / "experiments" / "phase2a_r1"
RESULTS = EXP_DIR / "results"
PROTOCOL = EXP_DIR / "protocol.json"
LEDGER = RESULTS / "ledger.jsonl"
SELECTION = RESULTS / "selection.json"
INCUMBENT_FILE = phase2a.EXP_DIR / "results" / "best_random_search.json"

TRAIN_SEEDS = tuple(range(4000, 4008))
VALIDATION_SEEDS = tuple(range(4100, 4116))
DIAGNOSTIC_SEEDS = tuple(range(5000, 5010))
FINAL_SEEDS = tuple(range(6000, 6030))
DURATION = 10.0

CANDIDATES = 150
TOP_K = 5
REPLICATES = (1, 2)
ARMS = {"A": {"dim": 13, "objective": "mean"}, "B": {"dim": 13, "objective": "worst2"},
        "C": {"dim": 15, "objective": "worst2"}}
ARM_ORDER = tuple(ARMS)
RNG_BASE = 20261014
WORST_K = 2

BUDGET_CAP = 8500
PILOT_CAP = 40
MAX_WORKERS = 4
MIN_FREE_GB = 4.0
WALL_LIMIT_S = 90 * 60
FUTILITY_MIN_SEED_GAIN = 2   # >= 10 percentage points of the 16 validation seeds (1 seed = 6.25 pp)
ENGINEERING = {"min_walking_seeds": 27, "n_seeds": 30, "min_median_speed_upright": 0.25, "max_body_dragging_seeds": 0}
ALPHA = 0.05
ERROR_FITNESS = -10.0


# ----------------------------------------------------------------------------------------------------------
# seeds, candidates
# ----------------------------------------------------------------------------------------------------------
def check_disjoint() -> None:
    sets = {"train": TRAIN_SEEDS, "validation": VALIDATION_SEEDS, "diagnostic": DIAGNOSTIC_SEEDS, "final": FINAL_SEEDS,
            "p2a_train": phase2a.TRAIN_SEEDS, "p2a_diagnostic": phase2a.DIAGNOSTIC_SEEDS,
            "p2a_heldout": phase2a.HELDOUT_SEEDS}
    names = list(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if set(sets[a]) & set(sets[b]):
                raise ValueError(f"seed sets overlap: {a} & {b}")


def seed_role(seed: int) -> str | None:
    for name, seeds in (("r1_train", TRAIN_SEEDS), ("r1_validation", VALIDATION_SEEDS),
                        ("r1_diagnostic", DIAGNOSTIC_SEEDS), ("r1_final", FINAL_SEEDS)):
        if seed in seeds:
            return name
    return None


def incumbent_export() -> dict:
    return json.loads(INCUMBENT_FILE.read_text(encoding="utf-8"))


def incumbent_vector(dim: int = 15) -> np.ndarray:
    base = PhaseGaitParams(**incumbent_export()["params"]).validate().to_vector()
    return np.concatenate([base, [INIT_DEFAULTS[k] for k in INIT_BOUNDS]])[:dim]


def candidate_vectors(arm: str, rep: int) -> np.ndarray:
    """(CANDIDATES, dim). Row 0 = frozen incumbent. Rows 1.. = uniform random; the first 13 dims depend only on the
    replicate (shared across arms), the 2 initiation dims (arm C) come from a separate stream."""
    dim = ARMS[arm]["dim"]
    rng = np.random.default_rng(np.random.SeedSequence([RNG_BASE, rep]))
    rows = LOWER + (UPPER - LOWER) * rng.random((CANDIDATES - 1, len(LOWER)))
    if dim == 15:
        rng_ext = np.random.default_rng(np.random.SeedSequence([RNG_BASE, rep, 15]))
        lo, hi = LOWER15[len(LOWER):], UPPER15[len(LOWER):]
        rows = np.hstack([rows, lo + (hi - lo) * rng_ext.random((CANDIDATES - 1, len(lo)))])
    return np.vstack([incumbent_vector(dim), rows])


def objective_values(per_seed_fitness) -> dict:
    f = np.asarray(per_seed_fitness, dtype=float)
    return {"mean": float(f.mean()), "worst2": float(np.sort(f)[:WORST_K].mean())}


# ----------------------------------------------------------------------------------------------------------
# resources
# ----------------------------------------------------------------------------------------------------------
class BudgetExceeded(RuntimeError):
    pass


class ResourceAbort(RuntimeError):
    pass


def free_memory_gb() -> float:
    if sys.platform == "win32":
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MS()
        st.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return st.ullAvailPhys / 2 ** 30
    with open("/proc/meminfo", encoding="utf-8") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 2 ** 20
    raise OSError("cannot read available memory")


def peak_rss_mb() -> float:
    """Peak resident set size of the current process (MB)."""
    if sys.platform == "win32":
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        ctypes.windll.psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / 2 ** 20
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


# ----------------------------------------------------------------------------------------------------------
# budget ledger (append-only, hash-chained, survives restarts)
# ----------------------------------------------------------------------------------------------------------
class Ledger:
    """Every batch is recorded with a `begin` entry BEFORE any MuJoCo rollout runs, so crashed or interrupted batches
    still count in full. Entries chain by the SHA-256 of the previous raw line (tamper-evident)."""

    def __init__(self, path: Path = LEDGER):
        self.path = Path(path)

    def _lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def entries(self) -> list[dict]:
        return [json.loads(ln) for ln in self._lines()]

    def verify(self) -> None:
        prev = "0" * 64
        for ln in self._lines():
            if json.loads(ln)["prev"] != prev:
                raise RuntimeError("ledger hash chain broken")
            prev = hashlib.sha256(ln.encode("utf-8")).hexdigest()

    def total_rollouts(self) -> int:
        return sum(e["rollouts"] for e in self.entries() if e["event"] == "begin")

    def stage_rollouts(self, stage: str) -> int:
        return sum(e["rollouts"] for e in self.entries() if e["event"] == "begin" and e["stage"] == stage)

    def total_wall_s(self) -> float:
        """Cumulative ACTIVE wall time across all runs, for the 90-minute hard stop. Takes the larger of (a) the sum of
        completed batch durations and (b) the sum of whole script sessions (batches + pool start-up, ranking, I/O and
        stage overhead). A session that crashed without `session_end` counts up to the last ledger entry it wrote; the
        session open in THIS process counts its live elapsed time. Idle time between runs is not counted."""
        ents = self.entries()
        batches = sum(e.get("wall_s", 0.0) for e in ents if e["event"] == "end")
        sessions, open_t = 0.0, None
        last_t = None
        for e in ents:
            t = datetime.fromisoformat(e["time_utc"])
            if e["event"] == "session_begin":
                if open_t is not None:
                    sessions += max(0.0, (last_t - open_t).total_seconds())   # previous session never ended (crash)
                open_t = t
            elif e["event"] == "session_end":
                sessions += e["wall_s"]
                open_t = None
            last_t = t
        live = 0.0
        if open_t is not None:
            if getattr(self, "_session_t0", None) is not None and getattr(self, "_session_open_utc", None) == open_t:
                live = time.perf_counter() - self._session_t0          # this process's own open session
            else:
                live = max(0.0, (last_t - open_t).total_seconds())     # crashed session
        return max(batches, sessions + live)

    def session_begin(self, stage: str) -> None:
        self.verify()
        self._append({"event": "session_begin", "stage": stage, "pid": os.getpid()})
        self._session_t0 = time.perf_counter()
        self._session_open_utc = datetime.fromisoformat(self._lines_last()["time_utc"])

    def session_end(self) -> None:
        if getattr(self, "_session_t0", None) is None:
            return
        self._append({"event": "session_end", "wall_s": time.perf_counter() - self._session_t0})
        self._session_t0 = None

    def _lines_last(self) -> dict:
        return json.loads(self._lines()[-1])

    def _append(self, entry: dict) -> None:
        lines = self._lines()
        entry["prev"] = hashlib.sha256(lines[-1].encode("utf-8")).hexdigest() if lines else "0" * 64
        entry["time_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(jsonable(entry), sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def begin(self, stage: str, rollouts: int, note: str = "") -> int:
        self.verify()
        if self.total_rollouts() + rollouts > BUDGET_CAP:
            raise BudgetExceeded(f"{self.total_rollouts()} + {rollouts} would exceed the hard cap {BUDGET_CAP}")
        if stage == "pilot" and self.stage_rollouts("pilot") + rollouts > PILOT_CAP:
            raise BudgetExceeded(f"pilot is capped at {PILOT_CAP} rollouts")
        bid = sum(e["event"] == "begin" for e in self.entries()) + 1
        self._append({"event": "begin", "id": bid, "stage": stage, "rollouts": int(rollouts), "note": note,
                      "cumulative_after": self.total_rollouts() + int(rollouts)})
        return bid

    def end(self, bid: int, executed: int, errors: int, wall_s: float, peak_rss_mb_: float | None, free_gb: float) -> None:
        self._append({"event": "end", "id": bid, "executed": int(executed), "errors": int(errors),
                      "wall_s": float(wall_s), "peak_worker_rss_mb": peak_rss_mb_, "free_memory_gb": free_gb})


def check_resources(ledger: Ledger) -> None:
    free = free_memory_gb()
    if free < MIN_FREE_GB:
        raise ResourceAbort(f"free memory {free:.2f} GB is below the {MIN_FREE_GB} GB floor")
    if ledger.total_wall_s() >= WALL_LIMIT_S:
        raise ResourceAbort(f"cumulative wall time {ledger.total_wall_s():.0f}s reached the {WALL_LIMIT_S}s hard stop")


# ----------------------------------------------------------------------------------------------------------
# jobs
# ----------------------------------------------------------------------------------------------------------
def r1_job(job: dict) -> dict:
    t0 = time.perf_counter()
    try:
        ctrl = controller_from_vector(job["vector"])
        body = BipedParams(**job["body"])
        per = []
        for s in job["seeds"]:
            m = compute_metrics(rollout(ctrl, body, s, job["duration"]), DEFAULT_CRITERIA)
            m["fitness"] = fitness_components(m, DEFAULT_CRITERIA)
            per.append(m)
        return {"ok": True, "result": aggregate(per), "wall_s": time.perf_counter() - t0, "peak_rss_mb": peak_rss_mb()}
    except Exception as e:  # recorded, never swallowed
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "wall_s": time.perf_counter() - t0,
                "peak_rss_mb": peak_rss_mb()}


def make_jobs(vectors, seeds, duration: float = DURATION) -> list[dict]:
    body = BipedParams().as_dict()
    return [{"vector": [float(x) for x in v], "body": body, "seeds": list(seeds), "duration": duration} for v in vectors]


def _compact_seed(m: dict) -> dict:
    return {"seed": m["seed"], "label": m["label"], "walking": bool(m["walking"]), "fell": bool(m["fell"]),
            "fall_time": m["fall_time"], "speed_upright": m["speed_upright"], "forward_disp_upright": m["forward_disp_upright"],
            "valid_steps": m["valid_steps"], "violations": m["violations"], "fitness": m["fitness"]["total"]}


def run_batch(ex: Executor, ledger: Ledger, stage: str, vectors, seeds, note: str = "") -> list[dict]:
    """One counted batch: ledger.begin (before any physics) -> execute -> ledger.end. Returns per-vector job outputs."""
    check_resources(ledger)
    n = len(vectors) * len(seeds)
    bid = ledger.begin(stage, n, note)
    t0 = time.perf_counter()
    outs = ex.map(make_jobs(vectors, seeds))
    errors = sum(not o["ok"] for o in outs)
    peak = max((o.get("peak_rss_mb") or 0.0) for o in outs)
    ledger.end(bid, executed=n, errors=errors, wall_s=time.perf_counter() - t0, peak_rss_mb_=peak, free_gb=free_memory_gb())
    return outs


def _record(vector, out: dict, seeds, extra: dict) -> dict:
    rec = {**extra, "vector": [float(x) for x in vector], "seeds": list(seeds), "wall_s": out["wall_s"]}
    if out["ok"]:
        r = out["result"]
        fit = [m["fitness"]["total"] for m in r["per_seed"]]
        rec.update({"error": None, "objective": objective_values(fit), "walking_count": int(sum(m["walking"] for m in r["per_seed"])),
                    "survival_count": int(sum(not m["fell"] for m in r["per_seed"])),
                    "median_speed": r["median_speed"], "labels": r["labels"],
                    "per_seed": [_compact_seed(m) for m in r["per_seed"]]})
    else:
        n = len(seeds)
        rec.update({"error": out["error"], "objective": {"mean": ERROR_FITNESS, "worst2": ERROR_FITNESS},
                    "walking_count": 0, "survival_count": 0, "median_speed": None, "labels": ["error"] * n, "per_seed": []})
    return jsonable(rec)


# ----------------------------------------------------------------------------------------------------------
# training / ranking / validation
# ----------------------------------------------------------------------------------------------------------
def run_training(arm: str, rep: int, ex: Executor, ledger: Ledger, out_dir: Path = RESULTS, batch: int = 20) -> list[dict]:
    path = out_dir / f"history_{arm}{rep}.jsonl"
    if path.exists():
        raise FileExistsError(f"{path} exists: runs are never silently repeated or overwritten")
    vecs = candidate_vectors(arm, rep)
    history: list[dict] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for lo in range(0, len(vecs), batch):
        chunk = vecs[lo:lo + batch]
        outs = run_batch(ex, ledger, f"train-{arm}{rep}", chunk, TRAIN_SEEDS, f"{arm}{rep} candidates {lo}-{lo + len(chunk) - 1}")
        recs = [_record(v, o, TRAIN_SEEDS, {"arm": arm, "replicate": rep, "index": lo + i, "incumbent": lo + i == 0})
                for i, (v, o) in enumerate(zip(chunk, outs))]
        history.extend(recs)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.writelines(json.dumps(r, allow_nan=False) + "\n" for r in recs)
    return history


def rank_training(history: list[dict], objective: str) -> list[int]:
    """Candidate indices, best first by the arm's training objective (ties: earlier index)."""
    return sorted(range(len(history)), key=lambda i: (-history[i]["objective"][objective], history[i]["index"]))


def run_validation(arm: str, rep: int, history: list[dict], ex: Executor, ledger: Ledger, out_dir: Path = RESULTS) -> dict:
    path = out_dir / f"validation_{arm}{rep}.json"
    if path.exists():
        raise FileExistsError(f"{path} exists: validation is never silently repeated")
    top = rank_training(history, ARMS[arm]["objective"])[:TOP_K]
    to_run = [i for i in top if not history[i]["incumbent"]]   # the incumbent is validated once, separately
    outs = run_batch(ex, ledger, f"validate-{arm}{rep}", [history[i]["vector"] for i in to_run], VALIDATION_SEEDS,
                     f"{arm}{rep} validation of training ranks {top}") if to_run else []
    recs = [_record(history[i]["vector"], o, VALIDATION_SEEDS,
                    {"arm": arm, "replicate": rep, "index": i, "training_rank": top.index(i) + 1,
                     "training_objective": history[i]["objective"]})
            for i, o in zip(to_run, outs)]
    res = {"arm": arm, "replicate": rep, "objective": ARMS[arm]["objective"], "top5_training_indices": top,
           "incumbent_in_top5": any(history[i]["incumbent"] for i in top), "validated": recs}
    path.write_text(json.dumps(jsonable(res), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return res


def run_incumbent_validation(ex: Executor, ledger: Ledger, out_dir: Path = RESULTS) -> dict:
    path = out_dir / "validation_incumbent.json"
    if path.exists():
        raise FileExistsError(f"{path} exists")
    vec = incumbent_vector(15)
    outs = run_batch(ex, ledger, "validate-incumbent", [vec], VALIDATION_SEEDS, "frozen Phase 2A incumbent")
    res = _record(vec, outs[0], VALIDATION_SEEDS, {"arm": "incumbent", "replicate": 0, "index": 0})
    path.write_text(json.dumps(res, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return res


# ----------------------------------------------------------------------------------------------------------
# selection (prespecified, deterministic)
# ----------------------------------------------------------------------------------------------------------
SELECTION_RULE = (
    "Eligible: validated candidates that are not the incumbent. Rank by (1) number of the 16 validation seeds passing "
    "every walking gate, (2) number of validation seeds that did not fall, (3) mean validation fitness, all higher is "
    "better; remaining ties by arm order A<B<C, then replicate, then candidate index. Training ranks and final seeds "
    "play no part.")


def validation_sort_key(rec: dict):
    return (-rec["walking_count"], -rec["survival_count"], -rec["objective"]["mean"],
            ARM_ORDER.index(rec["arm"]), rec["replicate"], rec["index"])


def rank_validated(recs: list[dict]) -> list[dict]:
    return sorted([r for r in recs if r["error"] is None], key=validation_sort_key)


def futility_gate(validations: dict, incumbent: dict) -> dict:
    """validations: {arm: [validation result dicts for replicate 1]}. Proceed iff some arm's best validated candidate
    beats the incumbent's validation walking-seed count by >= FUTILITY_MIN_SEED_GAIN (>= 10 pp of 16 seeds)."""
    arms = {}
    for arm, results in validations.items():
        recs = rank_validated([r for res in results for r in res["validated"]])
        best = recs[0] if recs else None
        gain = (best["walking_count"] - incumbent["walking_count"]) if best else None
        arms[arm] = {"best": None if best is None else {"index": best["index"], "replicate": best["replicate"],
                                                          "walking_count": best["walking_count"]},
                     "incumbent_walking_count": incumbent["walking_count"], "gain_seeds": gain,
                     "gain_percentage_points": None if gain is None else 100.0 * gain / len(VALIDATION_SEEDS),
                     "meets_threshold": bool(gain is not None and gain >= FUTILITY_MIN_SEED_GAIN)}
    return {"arms": arms, "proceed": any(a["meets_threshold"] for a in arms.values()),
            "threshold": f">= {FUTILITY_MIN_SEED_GAIN} validation seeds (>= 10 pp of {len(VALIDATION_SEEDS)}); an engineering "
                         "stopping heuristic, not a significance test"}


def select_winner(validations: list[dict]) -> dict:
    recs = rank_validated([r for res in validations for r in res["validated"]])
    if not recs:
        raise RuntimeError("no eligible validated candidate")
    return recs[0]


# ----------------------------------------------------------------------------------------------------------
# final-evaluation analysis (prespecified)
# ----------------------------------------------------------------------------------------------------------
def engineering_verdict(per_seed: list[dict]) -> dict:
    e = ENGINEERING
    walking = int(sum(m["walking"] for m in per_seed))
    med = float(np.median([m["speed_upright"] for m in per_seed]))
    drag = int(sum("body_dragging" in m["violations"] for m in per_seed))
    ok = len(per_seed) == e["n_seeds"] and walking >= e["min_walking_seeds"] and med >= e["min_median_speed_upright"] \
        and drag <= e["max_body_dragging_seeds"]
    return {"meets_engineering_criterion": bool(ok), "walking_seeds": walking, "n_seeds": len(per_seed),
            "median_speed_upright": med, "body_dragging_seeds": drag, "criterion": e}


def initial_perturbation(seed: int) -> dict:
    """The seed's only effect (mirrors rollout()): torso pitch then 6 joint offsets ~ N(0, PERTURB)."""
    rng = np.random.default_rng(seed)
    p0 = PERTURB * float(rng.standard_normal())
    j = PERTURB * rng.standard_normal(6)
    return {"pitch0": p0, "l_hip": float(j[0]), "l_knee": float(j[1]), "l_ankle": float(j[2]),
            "r_hip": float(j[3]), "r_knee": float(j[4]), "r_ankle": float(j[5])}


def knee_hypothesis_test(seeds, walking, n_perm: int = 20000, rng_seed: int = 0) -> dict:
    """Prespecified SECONDARY exploratory analysis (not a basis for selection, not causal): is the right-knee initial
    offset higher on non-walking seeds? Permutation test on the difference of means, two-sided."""
    x = np.array([initial_perturbation(s)["r_knee"] for s in seeds])
    w = np.asarray(walking, dtype=bool)
    if w.all() or (~w).all():
        return {"n_nonwalking": int((~w).sum()), "n_walking": int(w.sum()), "p_two_sided": None,
                "note": "only one outcome class present; test not defined"}
    obs = float(x[~w].mean() - x[w].mean())
    rng = np.random.default_rng(rng_seed)
    k = int((~w).sum())
    hits = 0
    for _ in range(n_perm):
        perm = rng.permutation(x)
        hits += abs(perm[:k].mean() - perm[k:].mean()) >= abs(obs) - 1e-15
    return {"n_nonwalking": k, "n_walking": int(w.sum()), "mean_nonwalking": float(x[~w].mean()),
            "mean_walking": float(x[w].mean()), "difference": obs, "p_two_sided": hits / n_perm,
            "status": "exploratory, uncorrected, descriptive only"}


# ----------------------------------------------------------------------------------------------------------
# protocol
# ----------------------------------------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_protocol() -> dict:
    check_disjoint()
    return {
        "id": "phase2a-r1-protocol-v1",
        "status": "immutable once committed; changes require a new protocol id and re-registration",
        "question": ("Does training for robustness (more seeds per candidate, longer episodes, a lower-tail objective) and "
                     "an optional 2-parameter gait-initiation extension raise the fraction of fresh seeds on which the "
                     "phase-gait controller reaches gate-validated walking?"),
        "basis": "docs/PHASE2A_FAILURE_DIAGNOSIS.md (post-hoc, correlational)",
        "frozen_inputs": {"incumbent_export": INCUMBENT_FILE.relative_to(ROOT).as_posix(),
                          "incumbent_sha256": sha256_file(INCUMBENT_FILE),
                          "phase2a_protocol_sha256": sha256_file(phase2a.PROTOCOL),
                          "phase2a_heldout_sha256": sha256_file(phase2a.EXP_DIR / "results" / "heldout.json")},
        "morphology": BipedParams().as_dict(),
        "walking_criteria": DEFAULT_CRITERIA.as_dict(),
        "controller": {"arms_A_B": "PhaseGaitController, 13 parameters (phasegait.BOUNDS), unchanged",
                       "arm_C": ("PhaseGaitInitController: the 13 parameters plus ramp_s (bounds %s, default 0.5 s = Phase 2A "
                                 "RAMP_S) and start_lean (bounds %s rad, default 0; extra forward pitch reference decaying "
                                 "to zero over 1.0 s by smoothstep). Defaults reproduce Phase 2A bit-identically (tested)."
                                 % (INIT_BOUNDS["ramp_s"], INIT_BOUNDS["start_lean"])),
                       "no_fsm_no_rl": True},
        "seeds": {"train": list(TRAIN_SEEDS), "validation": list(VALIDATION_SEEDS), "diagnostic": list(DIAGNOSTIC_SEEDS),
                  "final": list(FINAL_SEEDS)},
        "seed_policy": ("train: optimisation objective only. validation: choose among each run's top-5 and the overall "
                        "winner only. diagnostic: post-hoc analysis only. final: touched once by scripts/eval_r1_final.py "
                        "after selection.json is committed; never used to select, tune or stop. Phase 2A seeds 1000-1002, "
                        "2000-2009 and 3000-3019 are not reused for any R1 selection or final evaluation."),
        "durations_s": {"train": DURATION, "validation": DURATION, "final": DURATION, "diagnostic": DURATION},
        "initial_state": "torso pitch and 6 joint angles ~ N(0, 0.03 rad) from the episode seed; feet 2 mm above floor",
        "arms": {k: {"parameters": v["dim"], "training_objective": v["objective"]} for k, v in ARMS.items()},
        "objectives": {"mean": "mean over the 8 training seeds of per-seed fitness (creature_forge.locomotion.fitness_components)",
                       "worst2": "mean of the 2 lowest per-seed fitness values among the 8 training seeds (lower-tail)"},
        "optimization": {"method": "random_search (uniform in bounds), no polishing, no adaptive step",
                         "replicates_per_arm": list(REPLICATES), "candidates_per_replicate": CANDIDATES,
                         "rollouts_per_candidate": len(TRAIN_SEEDS), "candidate_zero": "frozen Phase 2A incumbent (counts toward the 150)",
                         "common_random_numbers": ("candidates 1..149 of arms A, B, C share the first 13 dimensions within a "
                                                   "replicate; arm C's 2 extra dimensions use a separate stream; replicates use "
                                                   "independent streams"),
                         "rng_base": RNG_BASE,
                         "determinism_audit": ("arms A and B evaluate identical vectors on identical seeds, so their rollout "
                                               "results must be bit-identical; they are executed separately (and counted) "
                                               "and compared as a determinism check")},
        "validation": {"top_k_per_run": TOP_K, "ranking": "by the run's own training objective, ties by earlier index",
                       "incumbent": ("if the incumbent is among a run's top-5 it is not re-executed; the incumbent is validated "
                                     "once, separately, on the same 16 seeds")},
        "selection_rule": SELECTION_RULE,
        "futility": {"after": "replicate 1 of A, B, C is trained and validated",
                     "rule": ("stop and report a null result unless, for some arm, the best eligible validated candidate "
                              "passes every walking gate on at least %d more of the 16 validation seeds than the incumbent "
                              "(>= 10 percentage points)" % FUTILITY_MIN_SEED_GAIN),
                     "nature": "pragmatic engineering stopping heuristic, not a significance test",
                     "if_proceeding": "replicate 2 of A, B, C, then selection of ONE overall winner, committed before final evaluation"},
        "final_evaluation": {"controllers": ["selected R1 winner", "frozen Phase 2A incumbent"],
                             "seeds": list(FINAL_SEEDS), "conditions": "identical seeds, duration, morphology and gates for both",
                             "engineering_criterion": ENGINEERING,
                             "superiority": {"test": "exact two-sided McNemar on the 30 paired seeds (success = passes every walking gate)",
                                             "alpha": ALPHA, "requires": "p < alpha AND a positive paired success-rate difference"},
                             "reporting": ["paired 2x2 table", "discordant counts", "exact McNemar p", "paired difference with "
                                           "Newcombe 95% interval", "Wilson and exact intervals per controller", "conditional odds ratio"],
                             "caveat": ("27/30 does not establish a true success probability >= 90%; report the exact interval. "
                                        "Comparisons between arms are exploratory and are not additional confirmatory tests.")},
        "secondary_exploratory": {"hypothesis": ("failure on the final seeds is associated with a larger right-knee initial offset "
                                                 "(from Phase 2A post-hoc exploratory p=0.016 uncorrected, 0.145 Bonferroni)"),
                                  "method": "two-sided permutation test, difference of means, 20000 permutations, rng seed 0",
                                  "status": "exploratory; not causal; never a basis for selection"},
        "interpretation_notes": [
            "Comparing arm A with historical Phase 2A changes BOTH the number of training seeds (3 -> 8) and the episode "
            "duration (6 s -> 10 s) (and the sampling streams); it does not isolate a single factor and must not be described "
            "as doing so.",
            "A vs B isolates the objective (identical candidates and rollouts); B vs C isolates the initiation parameters "
            "only to the extent that random search over 15-D vs 13-D is comparable; all arm comparisons are exploratory.",
            "A single selected winner is evaluated on the final seeds; only the winner-vs-incumbent test is confirmatory."],
        "budget": {"hard_cap_rollouts": BUDGET_CAP,
                   "counted": "every MuJoCo rollout executed or started: training, validation, final, diagnostics, pilot, duplicates, retries, failed jobs, reruns",
                   "ledger": LEDGER.relative_to(ROOT).as_posix() + " (append-only, hash-chained; begin entries are written before any physics runs)",
                   "pilot_cap_rollouts": PILOT_CAP,
                   "planned": {"training": len(ARMS) * len(REPLICATES) * CANDIDATES * len(TRAIN_SEEDS),
                               "validation": len(ARMS) * len(REPLICATES) * TOP_K * len(VALIDATION_SEEDS) + len(VALIDATION_SEEDS),
                               "final": 2 * len(FINAL_SEEDS), "pilot": PILOT_CAP},
                   "no_automatic_extension": True},
        "resources": {"max_workers": MAX_WORKERS, "min_free_memory_gb": MIN_FREE_GB, "wall_clock_hard_stop_s": WALL_LIMIT_S,
                      "start_method": "spawn", "no_overlap_with_verification": True,
                      "pilot": "at most 40 rollouts; measures throughput and per-worker peak memory; failing resource checks stops the experiment"},
        "stopping_rules": ["any lost or errored job, memory abort, wall-clock stop or budget breach stops the run (no silent retry)",
                           "the final evaluation runs once and cannot be used to revise the controller, objective, gates or stopping rule",
                           "a null or partial result is reported as such; the search is not extended automatically"],
    }


def vector_export(vector, source: dict) -> dict:
    """Replayable, self-contained description of a (13- or 15-D) candidate."""
    v = np.asarray(vector, dtype=float)
    base = PhaseGaitParams.from_vector(v[:len(LOWER)]).as_dict()
    out = {"controller": "phase_gait" if len(v) == len(LOWER) else "phase_gait_init", "params": base,
           "body": BipedParams().as_dict(), "source": source}
    if len(v) != len(LOWER):
        out["init"] = {k: float(x) for k, x in zip(INIT_BOUNDS, v[len(LOWER):])}
    return out


def require_preregistration(need_selection: bool = False) -> dict:
    commits = {"protocol": phase2a.committed_unmodified(PROTOCOL)}
    stored = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if stored != json.loads(json.dumps(build_protocol())):
        raise RuntimeError("protocol.json no longer matches the code that defines it or its frozen inputs; re-registration required")
    if need_selection:
        commits["selection"] = phase2a.committed_unmodified(SELECTION)
    return commits
