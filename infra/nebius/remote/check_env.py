"""Compatibility + frozen-controller reproducibility checks for a fresh machine. Runs NO R1 rollouts and writes NO ledger.

    python infra/nebius/remote/check_env.py --emit-reference infra/nebius/reference_windows.json   # once, on the reference machine
    python infra/nebius/remote/check_env.py --reference infra/nebius/reference_windows.json --out check_env.json

The frozen Phase 2A incumbent is rolled out on infrastructure-only seeds 9000-9001 (outside every registered partition:
train 4000s, validation 4100s, diagnostic 5000s, final 6000s, Phase 2A 1000-3019), twice in-process and once through a
spawn worker pool; metrics must be bit-identical in-process and match the reference within the documented tolerance
(creature_forge.reproducibility RTOL/ATOL). It also verifies the R1 pre-registration integrity and an untouched ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

from creature_forge import r1  # noqa: E402
from creature_forge.reproducibility import ATOL, RTOL, compare_evidence  # noqa: E402

INFRA_SEEDS = (9000, 9001)
EXPECTED = {"mujoco": "3.15.0"}


def job_metrics(_=None) -> dict:
    out = r1.r1_job(r1.make_jobs([r1.incumbent_vector()], INFRA_SEEDS)[0])
    if not out["ok"]:
        raise RuntimeError(out["error"])
    return json.loads(json.dumps(out["result"], default=float, sort_keys=True))


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference")
    ap.add_argument("--emit-reference")
    ap.add_argument("--out")
    a = ap.parse_args()
    checks: dict[str, dict] = {}

    def rec(name, ok, detail=""):
        checks[name] = {"ok": bool(ok), "detail": detail}
        print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""), flush=True)

    rec("mujoco_version", mujoco.__version__ == EXPECTED["mujoco"], mujoco.__version__)
    rec("numpy_in_pinned_range", "2.4.6" <= np.__version__ < "2.6", np.__version__)
    free = r1.free_memory_gb()
    rec("free_memory_ge_floor", free >= r1.MIN_FREE_GB, f"{free:.2f} GB (floor {r1.MIN_FREE_GB})")
    rec("cpu_count_ge_4", (os.cpu_count() or 0) >= 4, str(os.cpu_count()))
    try:
        commits = r1.require_preregistration()
        rec("preregistration_intact", True, f"protocol commit {commits['protocol']}")
    except Exception as e:  # noqa: BLE001
        rec("preregistration_intact", False, f"{type(e).__name__}: {e}")
    inc_ok = r1.sha256_file(r1.INCUMBENT_FILE) == "8ba7d5ee1324abab07b77a55df2fea6e4f072a5124043fb804d5dbcc60da292c"
    rec("incumbent_sha256_matches_registered", inc_ok)
    led = r1.Ledger()
    led.verify()
    rec("ledger_chain_valid", True, f"{led.total_rollouts()} rollouts counted")

    t0 = time.perf_counter()
    m1, m2 = job_metrics(), job_metrics()
    rec("in_process_determinism_bit_identical", digest(m1) == digest(m2), digest(m1)[:16])
    rec("two_seed_rollout_wall", True, f"{(time.perf_counter() - t0) / 2:.1f} s per 2-seed job")
    ctx = mp.get_context("spawn")
    with ctx.Pool(2) as pool:
        m3 = pool.map(job_metrics, [0, 1])
    rec("spawn_worker_bit_identical", all(digest(m) == digest(m1) for m in m3))

    if a.emit_reference:
        Path(a.emit_reference).write_text(json.dumps({"metrics": m1, "python": platform.python_version(), "numpy": np.__version__,
                                                       "mujoco": mujoco.__version__, "platform": platform.platform()}, indent=1, sort_keys=True))
        print("reference written:", a.emit_reference)
    if a.reference:
        ref = json.loads(Path(a.reference).read_text("utf-8"))
        cmp = compare_evidence(ref["metrics"], m1, rtol=RTOL, atol=ATOL)
        bad = list(cmp.structural) + [d for d in cmp.numeric if not d["within_tolerance"]]
        rec("matches_reference_within_policy", not bad,
            f"{len(cmp.numeric)} float diffs (max rel {max((d['rel'] for d in cmp.numeric), default=0.0):.1e}), {len(cmp.structural)} structural; reference {ref['platform']} py{ref['python']}; rtol={RTOL} atol={ATOL}")

    res = {"all_passed": all(c["ok"] for c in checks.values()), "checks": checks, "python": platform.python_version(),
           "numpy": np.__version__, "mujoco": mujoco.__version__, "platform": platform.platform()}
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1))
    print("ALL PASSED" if res["all_passed"] else "SOME CHECKS FAILED")
    return 0 if res["all_passed"] else 1


if __name__ == "__main__":
    mp.freeze_support()
    sys.exit(main())
