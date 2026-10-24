"""P05-SV1 shard worker (proposal CF-V2-P05-SV1, sections 7-9).

    "$V/bin/python" -I -B sv1_run.py --phase {pilot,confirm,bench} --shard i --nshards n --out <repo>/<sv1>/out --pre ~/sv1/pre
    "$V/bin/python" -I -B sv1_run.py --phase {pilot,confirm} --replay K --out ... --pre ...        (cross-process determinism)
    python -I -B sv1_run.py --phase pilot --local-test --override '{"S_per_A_cell": 1, ...}' --out <dir>   (local smoke only)

One single-threaded process per shard (parallelism = separate processes, each in its own systemd scope; no multiprocessing).
Work units (cell, kind, s) are dealt round-robin over shards (sv1_lib.work_units); results are deterministic per unit, so they
do not depend on the shard count. Records are appended one line per unit to out/<phase>/records_<i>of<n>.ndjson and are
resumable: units present in ANY records file of the phase are skipped. A unit that raises is written to errors_*.ndjson and
stays missing (the aggregator then reports INCOMPLETE). Timings go to separate timing files (records contain none).
Outside --local-test: a full provenance preflight runs first, --out must be <this checkout>/sv1/out, and the fast path
requires this --out's sv1_selftest PASS produced with the approved code hashes and fingerprint.
"""
import os
import sys

USAGE = ("usage: sv1_run.py --phase {pilot,confirm,bench} --shard I --nshards N --out DIR [--pre DIR] "
         "[--local-test [--override JSON]] [--bench-units K] [--bench-fast] [--replay K]")


def _args(argv):
    a, out, flags = list(argv), {}, set()
    while a:
        k = a.pop(0)
        if k in ("--local-test", "--bench-fast"):
            flags.add(k)
            continue
        if k not in ("--phase", "--shard", "--nshards", "--out", "--pre", "--override", "--bench-units", "--replay") or not a or k in out:
            raise SystemExit(USAGE)
        out[k] = a.pop(0)
    if out.get("--phase") not in ("pilot", "confirm", "bench") or "--out" not in out:
        raise SystemExit(USAGE)
    if "--override" in out and "--local-test" not in flags:
        raise SystemExit("--override is allowed only with --local-test")
    if out["--phase"] == "confirm" and "--local-test" in flags:
        raise SystemExit("the confirm phase never runs in --local-test mode")
    return out, flags


ARGS, FLAGS = _args(sys.argv[1:])
SHARD, NSHARDS = int(ARGS.get("--shard", 0)), int(ARGS.get("--nshards", 1))
if not 0 <= SHARD < NSHARDS:
    raise SystemExit(USAGE)
_HERE = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
sys.path.insert(0, _HERE)
import sv1_guard as GD  # noqa: E402

OUT = os.path.realpath(os.path.join(ARGS["--out"], ARGS["--phase"]))
GD.install(os.path.realpath(ARGS["--out"]), ARGS.get("--pre"))

import hashlib  # noqa: E402
import json  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

CONFIG_PATH = os.path.join(GD.SV1_DIR, "sv1_config.json")
CODE = GD.CODE
PINS = {"creature_forge/experience_p0.py": "dcfb1f29cc14ea05bb4bb80eb9d18240a81b3360",
        "creature_forge/experience_bank.py": "38aed182696d5d46cf992e7bd4e9d138e6a6a0f4",
        "creature_forge/experience_audit.py": "1273379810988db569e855aa8d954c2da038b04f",
        "creature_forge/__init__.py": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"}
SV1_REL = "experiments/causal_engineer/dev/experience_p05/sv1"
SV0_REL = "experiments/causal_engineer/dev/experience_p05/sv0"


def _read(p: str) -> bytes:
    with open(p, "rb") as fh:
        return fh.read()


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


code_hashes, fingerprint = GD.code_hashes, GD.fingerprint


def preflight() -> list:
    """VM preflight (skipped only in --local-test). Returns a list of failures; empty means PASS."""
    fails = []
    pre = ARGS.get("--pre")
    if not pre:
        return ["--pre is required outside --local-test"]
    exp = json.loads(_read(os.path.join(pre, "expected.json")).decode("utf-8"))
    if GD.REPO != os.path.join(GD.HOME, "sv1", "repo"):
        fails.append(f"REPO {GD.REPO} is not ~/sv1/repo")
    if os.path.realpath(ARGS["--out"]) != os.path.join(GD.SV1_DIR, "out"):
        fails.append("--out must be sv1/out of this checkout")
    head = _read(os.path.join(GD.REPO, ".git", "HEAD")).decode("ascii").strip()
    if not (len(head) == 40 and all(c in "0123456789abcdef" for c in head)) or head != exp["head"]:
        fails.append(f".git/HEAD {head!r} is not the detached approved hash")
    if _read(os.path.join(pre, "head.txt")).decode("ascii").strip() != exp["head"]:
        fails.append("launcher git rev-parse HEAD != approved hash")
    for rel, pin in PINS.items():
        b = _read(os.path.join(GD.REPO, rel))
        if hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest() != pin:
            fails.append(f"blob mismatch {rel}")
    code = code_hashes()
    if code != exp["code_sha256"]:
        fails.append(f"code sha256 mismatch: {sorted(k for k in set(code) | set(exp['code_sha256']) if code.get(k) != exp['code_sha256'].get(k))}")
    if not (sys.flags.isolated and sys.flags.dont_write_bytecode) or os.path.realpath(sys.prefix) != os.path.realpath(exp["venv"]):
        fails.append("interpreter flags or venv mismatch")
    fp = fingerprint()
    if fp != exp["fingerprint"]:
        fails.append(f"fingerprint mismatch: {sorted(k for k in set(fp) | set(exp['fingerprint']) if fp.get(k) != exp['fingerprint'].get(k))}")
    if any(os.environ.get(v) != "1" for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")):
        fails.append("thread variables are not all 1")
    if any(s in k.upper() for k in os.environ for s in ("KEY", "TOKEN", "SECRET")):
        fails.append("a KEY/TOKEN/SECRET variable is present")
    if _sha256(_read(os.path.join(pre, "freeze.txt"))) != exp["pip_freeze_sha256"]:
        fails.append("pip freeze sha256 mismatch")
    allowed = {f"?? {SV0_REL}/{f}" for f in ("sv0_lib.py", "sv0_run.py")} | {f"?? {SV1_REL}/{k[4:]}" for k in CODE if k.startswith("sv1/")}
    for ln in _read(os.path.join(pre, "status.txt")).decode("utf-8").splitlines():
        if ln.strip() and ln not in allowed and not (ln.startswith(f"?? {SV1_REL}/out/") and ln.endswith((".ndjson", ".json", ".md", ".txt"))):
            fails.append(f"stray git status line: {ln}")
    return fails


def _done_keys(phase_dir: str) -> set:
    keys = set()
    if os.path.isdir(phase_dir):
        for f in sorted(os.listdir(phase_dir)):
            if f.startswith("records_") and f.endswith(".ndjson"):
                for ln in _read(os.path.join(phase_dir, f)).decode("utf-8").split("\n"):
                    try:                                           # an unterminated last line (killed worker) is ignored
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    keys.add((r["cell"], r["kind"], r["s"]))
    return keys


def _rss_watch(limit_bytes: int):
    """Linux only: abort (exit 3) if VmRSS exceeds the limit; the systemd MemoryMax scope is the kernel backstop."""
    if sys.platform != "linux":
        return

    def run():
        while True:
            for ln in _read("/proc/self/status").decode("ascii", "replace").splitlines():
                if ln.startswith("VmRSS:") and int(ln.split()[1]) * 1024 > limit_bytes:
                    os._exit(3)
            time.sleep(1.0)
    threading.Thread(target=run, daemon=True).start()


def compute(S, phase, cell, kind, s, par, fast) -> dict:
    if kind == "truth":
        return S.truth_unit(phase, cell, s, par["new"], fast)
    return S.coverage_unit(phase, cell, kind, s, par["B"], par["R"], par["new"], fast)


def replay(S, phase: str, units: list, K: int, fast: bool) -> int:
    """Recompute K pre-declared units (chosen by a fixed seed, never by results) in this fresh process and write them to
    replay.ndjson; sv1_aggregate compares them byte-for-byte with the original records."""
    import numpy as np
    rng = np.random.default_rng(np.random.SeedSequence([S.SV1_ROOT, 77, S.PHASES[phase]]))
    pick = sorted(int(x) for x in rng.choice(len(units), size=min(K, len(units)), replace=False))
    with open(os.path.join(OUT, "replay.ndjson"), "w", encoding="utf-8", newline="\n") as rf:
        for j in pick:
            cell, kind, s, par = units[j]
            rf.write(json.dumps(compute(S, phase, cell, kind, s, par, fast), sort_keys=True, separators=(",", ":")) + "\n")
    return 0


def main() -> int:
    phase = ARGS["--phase"]
    local = "--local-test" in FLAGS
    if local and os.path.realpath(ARGS["--out"]) == os.path.join(GD.SV1_DIR, "out"):
        raise SystemExit("--local-test may not write into the real sv1/out")
    os.makedirs(OUT, exist_ok=True)
    cfg = json.loads(_read(CONFIG_PATH).decode("utf-8"))
    override = json.loads(ARGS.get("--override", "{}"))
    fails = [] if local else preflight()
    import numpy as np  # noqa: F401  (imported after the preflight reads, under the guard)
    import sv1_lib as S
    bad = GD.module_provenance_ok()
    GD.secondary()
    tag = "replay" if "--replay" in ARGS else f"{SHARD}of{NSHARDS}"
    pf = {"shard": SHARD, "nshards": NSHARDS, "phase": phase, "local_test": local, "failures": fails + bad,
          "code_sha256": code_hashes()}
    with open(os.path.join(OUT, f"preflight_{tag}.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(pf, sort_keys=True, indent=1) + "\n")
    if fails or bad:
        print("preflight FAIL:", fails + bad, file=sys.stderr)
        return 2
    _rss_watch(1 << 30)
    fast = bool(override.get("fast", cfg["engineering"]["fast_path"] is True))
    if fast and not local and phase != "bench":                    # the fast path requires this session's SV1-0 PASS
        st_path = os.path.join(os.path.realpath(ARGS["--out"]), "selftest", "selftest_results.json")
        st = json.loads(_read(st_path).decode("utf-8")) if os.path.exists(st_path) else {"status": "MISSING", "items": []}
        a_items = [i for i in st["items"] if i["name"].startswith("(a)")]
        exp = json.loads(_read(os.path.join(ARGS["--pre"], "expected.json")).decode("utf-8"))
        same_env = st.get("code_sha256") == exp["code_sha256"] and st.get("fingerprint") == exp["fingerprint"]
        if st["status"] != "PASS" or len(a_items) < 20 or any(i["result"] != "PASS" for i in a_items) or not same_env:
            print("refused: fast_path requires a PASS sv1_selftest (all (a) bit-identity items) run with the approved code "
                  "hashes and fingerprint in this --out", file=sys.stderr)
            return 2
    if phase == "bench":
        K = int(ARGS.get("--bench-units", 4))
        bfast = "--bench-fast" in FLAGS
        t0, c0 = time.time(), time.process_time()
        for j in range(K):
            fixed = S.fixed_params("info")
            X, _Q, Y, base = S.dataset(fixed, 28, S.rng_for("bench", "A-info", "bench", SHARD * 1000 + j))
            S.fit(X, Y, base, bfast)
        rec = {"shard": SHARD, "nshards": NSHARDS, "units": K, "fast": bfast, "wall_s": time.time() - t0,
               "cpu_s": time.process_time() - c0, "start": t0, "end": time.time()}
        with open(os.path.join(OUT, f"bench_{NSHARDS}procs_{SHARD}{'_fast' if bfast else ''}.json"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return 0
    units = S.work_units(cfg, phase, override)
    if "--replay" in ARGS:
        return replay(S, phase, units, int(ARGS["--replay"]), fast)
    done = _done_keys(OUT)
    mine = [u for j, u in enumerate(units) if j % NSHARDS == SHARD and (u[0], u[1], u[2]) not in done]
    rec_path = os.path.join(OUT, f"records_{SHARD}of{NSHARDS}.ndjson")
    tim_path = os.path.join(OUT, f"timing_{SHARD}of{NSHARDS}.ndjson")
    err_path = os.path.join(OUT, f"errors_{SHARD}of{NSHARDS}.ndjson")
    if os.path.exists(rec_path) and not _read(rec_path).endswith(b"\n") and os.path.getsize(rec_path):
        with open(rec_path, "a", encoding="utf-8", newline="\n") as rf:   # terminate a killed worker's fragment (kept as evidence)
            rf.write("\n")
    with open(rec_path, "a", encoding="utf-8", newline="\n") as rf, open(tim_path, "a", encoding="utf-8", newline="\n") as tf:
        for cell, kind, s, par in mine:
            t0, c0 = time.time(), time.process_time()
            try:
                rec = compute(S, phase, cell, kind, s, par, fast)
            except Exception as e:                                 # noqa: BLE001 - recorded; the unit stays missing
                with open(err_path, "a", encoding="utf-8", newline="\n") as ef:
                    ef.write(json.dumps({"cell": cell, "kind": kind, "s": s, "error": f"{type(e).__name__}: {e}"}, sort_keys=True) + "\n")
                continue
            rf.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
            rf.flush()
            tf.write(json.dumps({"cell": cell, "kind": kind, "s": s, "wall_s": round(time.time() - t0, 4),
                                 "cpu_s": round(time.process_time() - c0, 4)}, sort_keys=True) + "\n")
            tf.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
