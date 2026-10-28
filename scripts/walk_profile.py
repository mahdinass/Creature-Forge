"""S0 resource profile for the walking-recovery study: rollout throughput and memory by worker count.

Measures, on the machine it runs on (the Nebius VM; never run locally):
  * rollouts/s of 10 s walk rollouts for 1..W workers, separately for a creature that walks for the full 10 s (default body)
    and one that falls after ~2-3 s (the drawn stilts), since falls end episodes early;
  * the peak resident memory of one worker process.
Seeds come from 99_000_000+ (outside every research namespace); nothing here is an experiment and nothing is recorded as
one. Output: one JSON object on stdout (and optionally written with --out).

    python scripts/walk_profile.py --workers 1 2 4 8 --jobs 48
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from creature_forge import creature_walk as cw  # noqa: E402
from creature_forge.forge_pool import ForgePool  # noqa: E402

SEED0 = 99_000_000
DEFAULT_BODY = {"torso_mass": 5.0, "thigh_length": 0.30, "shank_length": 0.30, "foot_length": 0.16, "foot_friction": 1.0,
                "torque_limit": 60.0, "leg_density": 1000.0, "pose": [0.0] * 7}
STILTS_BODY = {"torso_mass": 4.7917, "thigh_length": 0.55, "shank_length": 0.55, "foot_length": 0.07, "foot_friction": 1.0,
               "torque_limit": 60.0, "leg_density": 1000.0, "pose": [0.0] * 7}


def _job(body: dict, seed: int) -> dict:
    return {"vector": list(cw.R2_WINNER), "body": body, "seeds": [seed], "duration": 10.0}


def _peak_rss_job(job: dict) -> dict:
    out = cw.eval_job(job)
    out["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    out["pid"] = os.getpid()
    return out


def measure(body: dict, workers: int, n_jobs: int, seed_offset: int) -> dict:
    jobs = [_job(body, SEED0 + seed_offset + i) for i in range(n_jobs)]
    with ForgePool(max_workers=workers) as pool:
        list(pool.imap(_peak_rss_job, jobs[:workers]))         # warm-up: spawn workers, import MuJoCo
        t0 = time.perf_counter()
        res = [r for _, r in pool.imap(_peak_rss_job, jobs)]
        wall = time.perf_counter() - t0
    ok = [r for r in res if isinstance(r, dict) and r.get("ok")]
    per = [p for r in ok for p in r["per_seed"]]
    return {"workers": workers, "jobs": n_jobs, "ok": len(ok), "wall_s": round(wall, 3),
            "rollouts_per_s": round(len(ok) / wall, 2) if wall > 0 else None,
            "mean_job_wall_s": round(sum(r["wall_s"] for r in ok) / max(1, len(ok)), 4),
            "fell_frac": round(sum(p["fell"] for p in per) / max(1, len(per)), 3),
            "walking_frac": round(sum(p["walking"] for p in per) / max(1, len(per)), 3),
            "peak_worker_rss_mb": round(max((r["peak_rss_mb"] for r in ok), default=0.0), 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--jobs", type=int, default=48)
    ap.add_argument("--out")
    a = ap.parse_args()
    out = {"host": platform.node(), "cpus": os.cpu_count(), "python": platform.python_version(), "results": []}
    for name, body in (("default_walks", DEFAULT_BODY), ("stilts_falls", STILTS_BODY)):
        for k, w in enumerate(a.workers):
            r = measure(body, w, a.jobs, seed_offset=1000 * k)
            r["body"] = name
            out["results"].append(r)
            print(json.dumps(r), flush=True)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
