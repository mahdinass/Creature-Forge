"""P05-SV0 runner (proposal CF-V2-P05-SV0 revision 4): checks SV0-0 .. SV0-8 on synthetic fixtures only.

Launch only as specified in proposal section 7A.3 (Linux VM, existing venv, `env -i`, cgroup / prlimit / timeout limits):

    "$V/bin/python" -I -B experiments/causal_engineer/dev/experience_p05/sv0/sv0_run.py \
        --run N --expected /home/forge/sv0/pre/expected.json --out experiments/causal_engineer/dev/experience_p05/sv0/out/runN

The first statements install an audit hook (section 5) that refuses every file open outside the allow-list, all
subprocesses, sockets and glob; it cannot be removed. Writes go to sv0/out/run<N>/ only. No simulation, no MuJoCo,
no network, no sealed data. SV0 verifies implementation correctness and determinism on synthetic fixtures only; it
establishes no coverage, inference validity or transfer.
"""
import os
import sys

# ============================================================================================== 1. guard (first statements)
USAGE = "usage: sv0_run.py --run {1,2} --expected <~/sv0/pre/expected.json> --out <sv0/out/run<N>>"


def _parse_argv(argv: list) -> dict:
    a, out = list(argv), {}
    while a:
        k = a.pop(0)
        if k not in ("--run", "--expected", "--out") or not a or k in out:
            raise SystemExit(USAGE)
        out[k] = a.pop(0)
    if set(out) != {"--run", "--expected", "--out"} or out["--run"] not in ("1", "2"):
        raise SystemExit(USAGE)
    return out


ARGS = _parse_argv(sys.argv[1:])
RUN = int(ARGS["--run"])
_rp = os.path.realpath
SV0_DIR = _rp(os.path.dirname(os.path.abspath(__file__)))
REPO = SV0_DIR
for _ in range(5):                                   # sv0 -> experience_p05 -> dev -> causal_engineer -> experiments -> repo
    REPO = os.path.dirname(REPO)
ARCHIVE = os.path.join(os.path.dirname(SV0_DIR), "design_archive")
OUT = os.path.join(SV0_DIR, "out", f"run{RUN}")
HOME = _rp(os.path.expanduser("~"))
PRE = os.path.join(HOME, "sv0", "pre")
EXPECTED = _rp(ARGS["--expected"])
PREFIXES = tuple(sorted({_rp(sys.prefix), _rp(sys.base_prefix)}))
SV0_REL = "experiments/causal_engineer/dev/experience_p05/sv0"
CODE_FILES = ("sv0_lib.py", "sv0_reference.py", "sv0_run.py")
PINS = {                                             # git blob sha1 (protocol pins + U9)
    "creature_forge/experience_p0.py": "dcfb1f29cc14ea05bb4bb80eb9d18240a81b3360",
    "creature_forge/experience_bank.py": "38aed182696d5d46cf992e7bd4e9d138e6a6a0f4",
    "scripts/exp_p0_audit.py": "dbaa4d34cb83bfc6fdfd0b456aaf3be72753ec98",
    "creature_forge/experience_audit.py": "1273379810988db569e855aa8d954c2da038b04f",
    "creature_forge/__init__.py": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
}


class GuardViolation(PermissionError):
    """Raised by the SV0 guard for any refused file, process, network or glob operation."""


def _under(p: str, root: str) -> bool:
    return p == root or p.startswith(root.rstrip(os.sep) + os.sep)


class _Policy:
    def __init__(self):
        self.read_files = {_rp(os.path.join(REPO, f)) for f in PINS}
        self.read_files |= {_rp(os.path.join(SV0_DIR, f)) for f in CODE_FILES}
        self.read_files |= {_rp(os.path.join(REPO, ".git", f)) for f in ("HEAD", "index")}
        self.read_files |= {_rp(os.path.join(PRE, "expected.json"))} | {_rp(os.path.join(PRE, f"run{RUN}.{x}"))
                                                                      for x in ("head", "status", "freeze")}
        # both forms: /proc/self resolves to /proc/<pid>, /etc/os-release is usually a symlink
        sysf = ("/proc/self/status", "/proc/meminfo", "/proc/cpuinfo", "/etc/os-release", "/proc/self/cgroup")
        self.read_files |= set(sysf) | {_rp(f) for f in sysf}
        self.list_dirs = {REPO, os.path.join(REPO, "creature_forge"), SV0_DIR, os.path.join(SV0_DIR, "out")}
        self.mkdirs = {os.path.join(SV0_DIR, "out"), OUT}

    @staticmethod
    def refused(p: str) -> bool:
        return (_under(p, os.path.join(REPO, "artifacts")) or p.endswith(".jsonl") or os.path.basename(p) == ".env"
                or _under(p, os.path.join(HOME, "creature-forge"))
                or (_under(p, os.path.join(HOME, "dev")) and not any(_under(p, r) for r in PREFIXES)))

    @staticmethod
    def in_prefix(p: str) -> bool:
        """Interpreter trees (stdlib, numpy), excluding any installed creature_forge copy and editable-install files."""
        for r in PREFIXES:
            if _under(p, r):
                rel = os.path.relpath(p, r).split(os.sep)
                return "creature_forge" not in rel and not os.path.basename(p).startswith("__editable__")
        return False

    def allow_read(self, p: str) -> bool:
        if self.refused(p):
            return False
        return (p in self.read_files or _under(p, ARCHIVE) or _under(p, OUT) or self.in_prefix(p)
                or _under(p, "/sys/fs/cgroup"))

    def allow_write(self, p: str) -> bool:
        return _under(p, OUT) and not self.refused(p)

    def allow_list(self, p: str) -> bool:
        return not self.refused(p) and (p in self.list_dirs or _under(p, ARCHIVE) or _under(p, OUT) or self.in_prefix(p))


_POLICY = _Policy()
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_REFUSED_PREFIX = ("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn", "os.fork", "pty.", "glob.",
                   "urllib.", "http.", "ftplib.", "smtplib.", "webbrowser.")
_REFUSED = {"os.system", "os.startfile", "os.kill", "os.killpg", "os.remove", "os.rename", "os.rmdir", "os.chmod",
            "os.chown", "os.truncate", "os.link", "os.symlink", "os.chdir", "os.utime", "shutil.rmtree", "shutil.move",
            "shutil.copyfile", "shutil.copytree", "shutil.make_archive", "shutil.unpack_archive"}


def _norm(path) -> tuple[str, str]:
    """(absolute path as given, symlink-resolved path). A path is refused if EITHER form is refused and allowed if either
    form is allowed: Debian/Ubuntu stdlib files such as sitecustomize.py are symlinks out of the interpreter tree."""
    s = os.fsdecode(os.fspath(path))
    return os.path.abspath(s), _rp(s)


def _ok(paths: tuple[str, str], allow) -> bool:
    return not any(_POLICY.refused(p) for p in paths) and any(allow(p) for p in paths)


def _audit(event: str, args: tuple) -> None:
    if event == "open":
        path, mode, flags = (tuple(args) + (None, None, None))[:3]
        if path is None or isinstance(path, int):
            return
        ps = _norm(path)
        write = (any(ch in mode for ch in "wax+") if isinstance(mode, str)
                 else bool(isinstance(flags, int) and flags & _WRITE_FLAGS))
        if not (_POLICY.allow_write(ps[1]) and not _POLICY.refused(ps[0]) if write else _ok(ps, _POLICY.allow_read)):
            raise GuardViolation(f"SV0 guard refused open({ps[1]!r}, write={write})")
    elif event in ("os.listdir", "os.scandir"):
        path = args[0] if args else None
        if isinstance(path, int):
            return
        ps = _norm(path if path not in (None, "", b"") else ".")
        if not _ok(ps, _POLICY.allow_list):
            raise GuardViolation(f"SV0 guard refused {event}({ps[1]!r})")
    elif event == "os.mkdir":
        if _norm(args[0])[1] not in _POLICY.mkdirs:
            raise GuardViolation(f"SV0 guard refused os.mkdir({args[0]!r})")
    elif event in _REFUSED or event.startswith(_REFUSED_PREFIX):
        raise GuardViolation(f"SV0 guard refused {event}")


sys.addaudithook(_audit)

# ============================================================================================== 2. stdlib (under the guard)
import ast  # noqa: E402
import hashlib  # noqa: E402
import importlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
from fractions import Fraction  # noqa: E402

PROPOSAL = "CF-V2-P05-SV0 revision 4"
STATEMENT = ("SV0 verifies implementation correctness and determinism on synthetic fixtures only; it establishes no coverage, "
             "inference validity or transfer.")
SV0_SEED = 2026102370
SEED_OFF = {"A": (1, 2, 3), "B": (11, 12, 13), "boot_3c": 21, "gstar_12": 22, "gstar_28": 23, "relabel_4b": 24,
            "order_4c": 25, "lemma_5": 26, "half_7": 31}           # +27 .. +29 reserved
M_INST = 3
LIMITS = {"run_wall_s": 1800.0, "run_cpu_s": 1800.0, "check_wall_s": 600.0, "tests_cpu_s": 300.0,
          "rss_max_bytes": 1 << 30, "mem_available_min_bytes": 2 << 30, "mem_available_start_bytes": 3 << 30}
ARCHIVED_TESTS = {"test_p05_design_calc": 25, "test_p05_design_calc_rev21": 15, "test_p05_amend22": 12}
NUMPY_RANGE = ((2, 4, 6), (2, 6))

# Identical source is executed in-process here and, in session c1, through the candidate venv's own interpreter:
#   "$V/bin/python" -I -B - <<'EOF'  <FINGERPRINT_SRC>  import json; print(json.dumps(fingerprint(), sort_keys=True))  EOF
FINGERPRINT_SRC = r'''
def fingerprint():
    import hashlib, importlib.metadata, json, os, platform, site, sys
    import numpy
    pre = os.path.realpath(sys.prefix)
    sp = sorted(p for p in site.getsitepackages() if os.path.realpath(p).startswith(pre + os.sep))
    lines = sorted({"%s==%s" % (d.metadata["Name"], d.version) for d in importlib.metadata.distributions(path=sp)})
    cfg = numpy.show_config(mode="dicts")
    cpu_model, cpu_flags = None, ""
    if os.path.exists("/proc/cpuinfo"):
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                k = k.strip()
                if k == "model name" and cpu_model is None:
                    cpu_model = v.strip()
                if k == "flags" and not cpu_flags:
                    cpu_flags = v.strip()
    return {"python": sys.version, "numpy": numpy.__version__, "platform": platform.platform(),
            "machine": platform.machine(), "sys_platform": sys.platform, "prefix": pre,
            "numpy_config_sha256": hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest(),
            "cpu_model": cpu_model, "cpu_flags_sha256": hashlib.sha256(cpu_flags.encode()).hexdigest(),
            "dist_manifest_sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest(), "dist_count": len(lines)}
'''


# ============================================================================================== 3. utilities
def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _blob_sha1(b: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def _py(x):
    """JSON-safe, deterministic conversion (numpy -> Python, Fraction -> 'p/q', non-finite floats -> strings)."""
    if isinstance(x, dict):
        return {str(k): _py(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_py(v) for v in x]
    if type(x).__module__ == "numpy":
        return _py(x.tolist()) if hasattr(x, "ndim") and x.ndim else _py(x.item())
    if isinstance(x, Fraction):
        return f"{x.numerator}/{x.denominator}"
    if isinstance(x, float) and not math.isfinite(x):
        return repr(x)
    return x


def _dump(obj, name: str) -> None:
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(_py(obj), sort_keys=True, ensure_ascii=True, indent=1) + "\n")


class ResourceAbort(Exception):
    pass


class Check:
    """One SV0 check: items carry the expected value literally next to the observed value."""

    def __init__(self, cid: str, title: str):
        self.cid, self.title, self.items, self.diagnostics = cid, title, [], []

    def add(self, name, expected, observed, ok, rule="exact", investigate=False, **extra):
        res = "PASS" if ok else ("FAIL-INVESTIGATE" if investigate else "FAIL")
        self.items.append({"name": name, "rule": rule, "expected": _py(expected), "observed": _py(observed), "result": res,
                           **{k: _py(v) for k, v in extra.items()}})
        return ok

    def exact(self, name, expected, observed):
        return self.add(name, expected, observed, _py(expected) == _py(observed))

    def close(self, name, expected, observed, tol=1e-12):
        import numpy as np
        a, b = np.asarray(expected, float), np.asarray(observed, float)
        ok = a.shape == b.shape and bool((np.abs(a - b) <= tol).all())
        dev = float(np.abs(a - b).max()) if a.shape == b.shape and a.size else None
        return self.add(name, expected, observed, ok, rule=f"abs tol {tol:g}", max_abs_diff=dev)

    def diag(self, name, value):
        self.diagnostics.append({"name": name, "value": _py(value)})

    @property
    def status(self) -> str:
        rs = {it["result"] for it in self.items}
        return "FAIL" if "FAIL" in rs or not self.items else "FAIL-INVESTIGATE" if "FAIL-INVESTIGATE" in rs else "PASS"

    def as_dict(self) -> dict:
        return {"id": self.cid, "title": self.title, "status": self.status, "items": self.items,
                "diagnostics": self.diagnostics}


class Budget:
    """In-process limits (section 7); the kernel backstops (cgroup, prlimit, timeout) sit above these."""

    def __init__(self):
        self.t0, self.c0 = time.monotonic(), time.process_time()
        self.cid, self.ct0, self.cc0, self.per_check = None, self.t0, self.c0, {}

    def start(self, cid: str):
        self.cid, self.ct0, self.cc0 = cid, time.monotonic(), time.process_time()

    def stop(self):
        self.per_check[self.cid] = {"wall_s": round(time.monotonic() - self.ct0, 3),
                                    "cpu_s": round(time.process_time() - self.cc0, 3)}
        self.cid = None

    def breach(self) -> str | None:
        now = time.monotonic()
        if now - self.t0 > LIMITS["run_wall_s"]:
            return "run wall time > 30 min"
        if time.process_time() - self.c0 > LIMITS["run_cpu_s"]:
            return "run CPU time > 30 min"
        if self.cid and now - self.ct0 > LIMITS["check_wall_s"]:
            return f"{self.cid} wall time > 10 min"
        return None

    def check(self):
        why = self.breach()
        if why:
            raise ResourceAbort(why)


def _memory_backend():
    """(VmRSS, VmHWM, MemAvailable) in bytes. linux: /proc (the only backend approved for execution); win32: ctypes."""
    if sys.platform == "linux":
        def kb(text, key):
            for line in text.splitlines():
                if line.startswith(key + ":"):
                    return int(line.split()[1]) * 1024
            return -1

        def read():
            st, mi = _read("/proc/self/status").decode("ascii", "replace"), _read("/proc/meminfo").decode("ascii", "replace")
            return kb(st, "VmRSS"), kb(st, "VmHWM"), kb(mi, "MemAvailable")
        return read
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                                               "PagefileUsage", "PeakPagefileUsage")]

        class MSX(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD)] + [
                (n, ctypes.c_ulonglong) for n in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                                                  "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]
        k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE

        def read():
            pmc, ms = PMC(), MSX()
            pmc.cb, ms.dwLength = ctypes.sizeof(PMC), ctypes.sizeof(MSX)
            psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            k32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return pmc.WorkingSetSize, pmc.PeakWorkingSetSize, ms.ullAvailPhys
        return read
    raise RuntimeError(f"no memory backend for {sys.platform}")


class Monitor(threading.Thread):
    """1-s watchdog: aborts (ABORTED-RESOURCE, os._exit(3)) on VmRSS > 1 GB, MemAvailable < 2 GB, or a wall limit
    exceeded by more than 15 s (the main thread's Budget.check normally fires first)."""

    def __init__(self, budget: Budget, read):
        super().__init__(daemon=True)
        self.budget, self.read = budget, read
        self.peak_rss, self.peak_hwm, self.min_avail = 0, 0, None
        self.stop_evt = threading.Event()

    def sample(self):
        rss, hwm, avail = self.read()
        self.peak_rss, self.peak_hwm = max(self.peak_rss, rss), max(self.peak_hwm, hwm)
        self.min_avail = avail if self.min_avail is None else min(self.min_avail, avail)
        return rss, avail

    def run(self):
        while not self.stop_evt.wait(1.0):
            rss, avail = self.sample()
            why = None
            if rss > LIMITS["rss_max_bytes"]:
                why = f"VmRSS {rss} > 1 GB"
            elif avail < LIMITS["mem_available_min_bytes"]:
                why = f"MemAvailable {avail} < 2 GB"
            else:
                b = self.budget
                now = time.monotonic()
                if now - b.t0 > LIMITS["run_wall_s"] + 15 or (b.cid and now - b.ct0 > LIMITS["check_wall_s"] + 15):
                    why = "wall limit exceeded (watchdog)"
            if why:
                try:
                    _dump({"classification": "ABORTED-RESOURCE", "reason": why, "check": self.budget.cid}, "sv0_abort.json")
                finally:
                    os._exit(3)


# ============================================================================================== 4. SV0-0 (proposal 5.1)
class Sv0Fail(Exception):
    pass


def _parse_index(data: bytes) -> tuple[int, dict]:
    """git index v2/v3: path -> stage-0 blob sha1; the trailing SHA-1 checksum is verified."""
    if hashlib.sha1(data[:-20]).digest() != data[-20:]:
        raise ValueError("index checksum mismatch")
    if data[:4] != b"DIRC":
        raise ValueError("index signature")
    ver, n = int.from_bytes(data[4:8], "big"), int.from_bytes(data[8:12], "big")
    if ver not in (2, 3):
        raise ValueError(f"index version {ver} not supported")
    off, out = 12, {}
    for _ in range(n):
        start = off
        sha = data[off + 40:off + 60].hex()
        flags = int.from_bytes(data[off + 60:off + 62], "big")
        off += 62
        if flags & 0x4000:
            if ver < 3:
                raise ValueError("extended flag in a v2 index")
            off += 2
        nlen = flags & 0x0FFF
        end = data.index(b"\0", off) if nlen == 0x0FFF else off + nlen
        path = data[off:end].decode("utf-8")
        off = start + (((end - start) + 8) & ~7)
        if (flags >> 12) & 3 == 0:
            out[path] = sha
    return ver, out


RUN_OUTPUTS = ("sv0_results.json", "sv0_env.json", "sv0_report.md")


def _allowed_status_lines(run: int) -> tuple[set, set]:
    """(required, optional) lines of `git -c core.excludesFile=/dev/null status --porcelain=v1 --untracked-files=all
    --ignored`. Required: the three untracked code files. Optional (run 2 only): run 1's three named outputs, untracked
    ('??'); the tracked .gitignore ignores none of them. Anything else, including any '!!' line, is stray."""
    required = {f"?? {SV0_REL}/{f}" for f in CODE_FILES}
    optional = {f"?? {SV0_REL}/out/run1/{f}" for f in RUN_OUTPUTS} if run == 2 else set()
    return required, optional


def _module_file_ok(name: str, f: str) -> bool:
    p = _rp(f)
    if name == "creature_forge" or name.startswith("creature_forge."):
        return p in {_rp(os.path.join(REPO, k)) for k in PINS if k.startswith("creature_forge/")}
    in_tree = any(any(_under(q, r) for r in PREFIXES) and "creature_forge" not in q.split(os.sep)
                  for q in (os.path.abspath(f), p))                # as-given or resolved (stdlib symlinks, see _norm)
    return (in_tree or _under(p, ARCHIVE) or p in {_rp(os.path.join(SV0_DIR, c)) for c in CODE_FILES})


def _finder_tag(f) -> str:
    """Identifies a meta-path finder; setuptools registers its editable finder as a CLASS, so its own __module__ counts."""
    return " ".join((type(f).__module__, type(f).__qualname__, str(getattr(f, "__module__", "")), str(getattr(f, "__name__", ""))))


def sv0_0(ck: Check, env: dict, read_mem) -> dict:
    """Startup, import and provenance procedure (proposal 5.1, steps 2-9). Raises Sv0Fail on the first failed step;
    the items recorded so far stay in `ck`."""
    mods: dict = {}

    def need(ok, name, expected, observed, **kw):
        if not ck.add(name, expected, observed, ok, **kw):
            raise Sv0Fail(name)

    try:
        os.listdir(HOME)
        probe = None
    except GuardViolation as e:
        probe = type(e).__name__
    need(probe == "GuardViolation", "audit hook active (listing ~ is refused)", "GuardViolation", probe)
    # step 2: locations
    need(REPO == os.path.join(HOME, "sv0", "repo"), "REPO is ~/sv0/repo", os.path.join(HOME, "sv0", "repo"), REPO)
    need(os.path.isdir(os.path.join(REPO, ".git")), ".git is a directory (not a gitfile)", True,
         os.path.isdir(os.path.join(REPO, ".git")))
    need(_rp(ARGS["--out"]) == OUT, "--out is sv0/out/run<N> of this checkout", True, _rp(ARGS["--out"]) == OUT)
    need(EXPECTED == os.path.join(PRE, "expected.json"), "--expected is ~/sv0/pre/expected.json", True,
         EXPECTED == os.path.join(PRE, "expected.json"))
    expected = json.loads(_read(EXPECTED).decode("utf-8"))
    # step 3: interpreter flags and venv
    flags = {"isolated": sys.flags.isolated, "dont_write_bytecode": sys.flags.dont_write_bytecode,
             "no_user_site": sys.flags.no_user_site, "safe_path": getattr(sys.flags, "safe_path", False)}
    need(all(bool(v) for v in flags.values()), "interpreter flags -I -B", {k: True for k in flags},
         {k: bool(v) for k, v in flags.items()})
    need(sys.prefix != sys.base_prefix, "running inside a venv", True, sys.prefix != sys.base_prefix)
    need(_rp(sys.prefix) == _rp(expected["venv"]), "venv equals the c1-approved venv", True, _rp(sys.prefix) == _rp(expected["venv"]))
    # step 4: neutralise other installations
    pre_loaded = sorted(k for k in sys.modules if k == "creature_forge" or k.startswith("creature_forge."))
    need(not pre_loaded, "no creature_forge module loaded before the explicit import", [], pre_loaded)
    env["sys_path_original"] = list(sys.path)
    kept = [p for p in sys.path if p and any(_under(_rp(p), r) for r in PREFIXES)]
    sys.path[:] = [SV0_DIR, REPO, ARCHIVE] + kept
    removed = [_finder_tag(f) for f in sys.meta_path if "__editable__" in _finder_tag(f)]
    sys.meta_path[:] = [f for f in sys.meta_path if "__editable__" not in _finder_tag(f)]
    env["sys_path_pruned"], env["meta_path_removed"] = list(sys.path), removed
    # step 5: explicit imports
    try:
        mods["np"] = importlib.import_module("numpy")
        mods["p0"] = importlib.import_module("creature_forge.experience_p0")
        mods["calc"] = importlib.import_module("p05_design_calc")
        mods["L"] = importlib.import_module("sv0_lib")
        mods["R"] = importlib.import_module("sv0_reference")
        mods["tests"] = {t: importlib.import_module(t) for t in ARCHIVED_TESTS}
        ok, err = True, None
    except Exception as e:                                       # a refused open surfaces here as ImportError
        ok, err = False, f"{type(e).__name__}: {e}"
    need(ok, "explicit imports from the approved checkout", None, err)
    # step 6: fail closed on shadowing
    cf = {k: _rp(m.__file__) for k, m in sys.modules.items()
          if m is not None and (k == "creature_forge" or k.startswith("creature_forge.")) and getattr(m, "__file__", None)}
    want = {"creature_forge": "creature_forge/__init__.py", "creature_forge.experience_p0": "creature_forge/experience_p0.py",
            "creature_forge.experience_audit": "creature_forge/experience_audit.py",
            "creature_forge.experience_bank": "creature_forge/experience_bank.py"}
    need(set(cf) <= set(want) and all(cf[k] == _rp(os.path.join(REPO, want[k])) for k in cf),
         "every creature_forge module is a pinned file of the checkout", {k: os.path.join(REPO, want[k]) for k in sorted(cf)}, cf)
    cfp = [_rp(p) for p in getattr(sys.modules.get("creature_forge"), "__path__", [])]
    need(cfp == [_rp(os.path.join(REPO, "creature_forge"))], "creature_forge.__path__", [os.path.join(REPO, "creature_forge")], cfp)
    bad = sorted(k for k, m in list(sys.modules.items())
                 if m is not None and isinstance(getattr(m, "__file__", None), str) and not _module_file_ok(k, m.__file__))
    need(not bad, "every loaded module comes from the interpreter trees, the checkout pins, the archive or sv0/", [], bad)
    for name, root in (("p05_design_calc", ARCHIVE), ("sv0_lib", SV0_DIR), ("sv0_reference", SV0_DIR)):
        f = _rp(sys.modules[name].__file__)
        need(os.path.dirname(f) == root, f"{name} resolves to its approved directory", root, os.path.dirname(f))
    # step 7: provenance without subprocess
    head_txt = _read(os.path.join(REPO, ".git", "HEAD")).decode("ascii").strip()
    need(len(head_txt) == 40 and all(c in "0123456789abcdef" for c in head_txt), ".git/HEAD is a detached 40-hex hash",
         True, head_txt)
    need(head_txt == expected["head"], ".git/HEAD equals the approved hash", expected["head"], head_txt)
    launcher_head = _read(os.path.join(PRE, f"run{RUN}.head")).decode("ascii").strip()
    need(launcher_head == expected["head"], "launcher git rev-parse HEAD equals the approved hash", expected["head"], launcher_head)
    ver, index = _parse_index(_read(os.path.join(REPO, ".git", "index")))
    env["git_index_version"] = ver
    for path, pin in PINS.items():
        need(index.get(path) == pin, f"index blob {path}", pin, index.get(path))
        need(_blob_sha1(_read(os.path.join(REPO, path))) == pin, f"worktree blob {path}", pin,
             _blob_sha1(_read(os.path.join(REPO, path))))
    required, optional = _allowed_status_lines(RUN)
    lines = [ln for ln in _read(os.path.join(PRE, f"run{RUN}.status")).decode("utf-8").splitlines() if ln.strip()]
    stray = [ln for ln in lines if ln not in required | optional]
    missing = sorted(required - set(lines))
    need(not stray and not missing, "launcher git status lists only the allowed lines",
         {"stray": [], "missing": []}, {"stray": stray, "missing": missing})
    code = {f: _sha256(_read(os.path.join(SV0_DIR, f))) for f in CODE_FILES}
    need(code == expected["code_sha256"], "sha256 of the three sv0 files equals the (b) hashes", expected["code_sha256"], code)
    sums = [ln.split(None, 1) for ln in _read(os.path.join(ARCHIVE, "SHA256SUMS")).decode("utf-8").splitlines() if ln.strip()]
    good = sum(_sha256(_read(os.path.join(ARCHIVE, *rel.lstrip("*").split("/")))) == h for h, rel in sums)
    need(len(sums) == 33 and good == 33, "design_archive SHA256SUMS", "33/33", f"{good}/{len(sums)}")
    # step 8: fingerprint
    ns: dict = {}
    exec(compile(FINGERPRINT_SRC, "<sv0-fingerprint>", "exec"), ns)
    fp = ns["fingerprint"]()
    env["fingerprint"] = fp
    for k in sorted(set(fp) | set(expected["fingerprint"])):
        need(fp.get(k) == expected["fingerprint"].get(k), f"fingerprint {k} equals c1", expected["fingerprint"].get(k), fp.get(k))
    nv = tuple(int(x) for x in fp["numpy"].split(".")[:3])
    need(NUMPY_RANGE[0] <= nv < NUMPY_RANGE[1], "numpy in >=2.4.6,<2.6", ">=2.4.6,<2.6", fp["numpy"])
    need(sys.platform == "linux" and platform.machine() == "x86_64", "platform linux x86_64", "linux x86_64",
         f"{sys.platform} {platform.machine()}")
    freeze = _read(os.path.join(PRE, f"run{RUN}.freeze"))
    fz = expected.get("pip_freeze_sha256")
    need(_sha256(freeze) == fz if fz else freeze == b"", "venv pip freeze (via $V/bin/python -I -m pip) equals c1",
         fz or "pip absent (empty)", _sha256(freeze) if freeze else "empty")
    # step 9: remaining items
    need(importlib.util.find_spec("scipy") is None, "scipy absent", None, None if importlib.util.find_spec("scipy") is None else "present")
    thr = {v: os.environ.get(v) for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}
    need(all(v == "1" for v in thr.values()), "thread variables equal 1", {k: "1" for k in thr}, thr)
    secret = sorted(k for k in os.environ if any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET")))
    need(not secret, "no KEY / TOKEN / SECRET variable present", [], secret)
    avail = read_mem()[2]
    env["mem_available_start_bytes"] = avail
    need(avail >= LIMITS["mem_available_start_bytes"], "MemAvailable >= 3 GB at start", True, avail >= LIMITS["mem_available_start_bytes"])
    return mods


def secondary_guards():
    """Defence in depth after the imports: MuJoCo tripwire and raising replacements for process and socket creation."""
    import multiprocessing
    import socket
    import subprocess

    def refuse(*_a, **_k):
        raise GuardViolation("SV0 guard: refused by the secondary layer")
    sys.modules["mujoco"] = None
    subprocess.Popen = refuse
    multiprocessing.Process.start = refuse
    os.fork = refuse
    socket.socket = refuse


# ============================================================================================== 5. data
def make_datasets(np, calc) -> dict:
    """Sets A (G = 28) and B (G = 12), m = 3, one per calc section-E scenario. Fixed parameters exactly as
    calc.learning_inflation: default_rng(calc.SEED + 7); instance draws from default_rng(SV0_SEED + offset)."""
    out = {}
    for i, sc_name in enumerate(calc.SCENARIOS):
        sc = calc.SCENARIOS[sc_name]
        for set_name, G in (("A", 28), ("B", 12)):
            frng = np.random.default_rng(calc.SEED + 7)
            fixed = {"E_o": frng.normal(size=(9, 8)), "E_c": frng.normal(size=(9, 27)),
                     "theta": frng.normal(0.0, sc["theta"], (9, calc.TOOLS)), "alpha": frng.normal(-1.5, 0.7, calc.TOOLS),
                     "noise_o": sc["noise_o"], "noise_c": sc["noise_c"]}
            rng = np.random.default_rng(SV0_SEED + SEED_OFF[set_name][i])
            X, _Q, Y, base = calc._synth(rng, fixed, G, M_INST)
            out[f"{set_name}{i}"] = {"X": X, "Y": Y, "base": base, "G": G, "scenario": sc_name}
    return out


def _f5(np):
    X = np.array([[0.0], [0.1], [10.0], [10.1], [20.0], [20.1]])
    Y = np.array([[1, 0], [1, 0], [0, 1], [1, 0], [1, 1], [0, 0]], float)
    return X, Y, np.array([0, 0, 1, 1, 2, 2]), {"obs": [0]}


def _same_pred(np, a: dict, b: dict) -> bool:
    return all(np.array_equal(a[k], b[k]) for k in ("P", "prior", "gate_sim")) and a["k"] == b["k"]


def _same_eval(np, a: dict, b: dict) -> bool:
    return all(np.array_equal(a[k], b[k]) for k in ("pick", "pi0", "v_mem", "v_pi0"))


# ============================================================================================== 6. checks
def sv0_1(c) -> Check:
    np, p0, L = c["np"], c["p0"], c["L"]
    ck = Check("SV0-1", "hand-computed reference fixtures on the exact P0 functions")
    D = np.array([[0.0, 1.0, 4.0]])
    ck.close("F1 knn_rates P", [[8 / 9, 1 / 9]], p0.knn_rates(D, np.array([[1.0, 0], [1, 0], [0, 1]]), 2, np.array([2 / 3, 1 / 3])))
    D = np.array([[1.0, 1.0, 0.5]])
    ck.exact("F2 stable-tie neighbours (as in knn_rates)", [[2, 0]], np.argsort(D, axis=1, kind="stable")[:, :2])
    ck.close("F2 knn_rates P", [[1 / 3, 0.0]], p0.knn_rates(D, np.array([[1.0, 0], [0, 1], [0, 0]]), 2, np.zeros(2)))
    X = np.array([[0.0, 0, 0], [2, 0, 0], [4, 0, 0], [2, 1, 3]])
    sp = p0.Space(X, {"A": [0], "B": [1, 2]})
    ck.close("F3 Space.dist", [[6.5, 5.0, 6.5]], sp.dist(np.arange(3), np.array([3]), ("A", "B")))
    Xn = X.copy()
    Xn[:, 0] = np.nan
    ck.close("F3n Space.dist with NaN column", [[5.0, 5.0, 5.0]], p0.Space(Xn, {"A": [0], "B": [1, 2]}).dist(np.arange(3), np.array([3]), ("A", "B")))
    ck.exact("F4 decide", [1, 0], [int(p0.decide(np.array([[0.5, 0.5]]), np.array([[0.3, 0.7]]))[0]),
                                   int(p0.decide(np.array([[0.6, 0.5]]), np.array([[0.0, 1.0]]))[0])])
    X5, Y5, b5, blk5 = _f5(np)
    sp5 = p0.Space(X5, blk5)
    pred = p0.predict(sp5, ("obs",), Y5, b5, b5, k_fixed={"0": 1, "1": 1, "2": 1})
    de = p0.decision_eval(pred, Y5)
    ck.exact("F5 prior", [[.5, .5]] * 2 + [[.75, .25]] * 4, pred["prior"])
    ck.exact("F5 P", [[.25, .75], [.25, .75], [.875, .125], [.875, .625], [.875, .125], [.875, .125]], pred["P"])
    ck.exact("F5 pick", [1, 1, 0, 0, 0, 0], de["pick"])
    ck.exact("F5 v_mem", [0, 0, 0, 1, 1, 0], de["v_mem"])
    ck.exact("F5 v_pi0", [1, 1, 0, 1, 1, 0], de["v_pi0"])
    ck.exact("F5 summarize_decision", {"n": 6, "value_mem": 0.3333, "value_pi0": 0.6667, "oracle_best": 0.8333,
                                       "regret_mem": 0.5, "delta_vs_pi0": -0.3333, "p_plus": 0.0, "p_minus": 0.3333},
             p0.summarize_decision(de))
    f6 = _f6(c)
    for k, v in f6["expected"].items():
        ck.exact(f"F6 {k}", v, f6["observed"][k])
    Xs, _Ys, gs, _c = L.resample(X5, Y5, b5, [0, 0, 2])
    sps = p0.Space(Xs, blk5)
    ck.exact("F7 leak_check, correct labels: rows flagged", [], np.flatnonzero(L.leak_check(sps, gs, ("obs",))))
    ck.exact("F7 leak_check, copies mislabelled [0,0,1,1,2,2]: rows flagged", [0, 1, 2, 3],
             np.flatnonzero(L.leak_check(sps, np.array([0, 0, 1, 1, 2, 2]), ("obs",))))
    return ck


def _f6(c) -> dict:
    """F6 through the fixture entry point: resample(idx = [0, 0, 2]) then refit_eval_fixed_k with k = 1 per fold."""
    np, p0, L = c["np"], c["p0"], c["L"]
    X5, Y5, b5, blk5 = _f5(np)
    Xs, Ys, gs, cnt = L.resample(X5, Y5, b5, [0, 0, 2])
    pred, de = L.refit_eval_fixed_k(p0.Space(Xs, blk5), Ys, gs, ("obs",), {"0": 1, "2": 1})
    copies = (np.array_equal(pred["P"][0:2], pred["P"][2:4]) and np.array_equal(de["pick"][0:2], de["pick"][2:4])
              and np.array_equal(de["v_mem"][0:2], de["v_mem"][2:4]))
    return {"expected": {"X*": [[0.0], [0.1], [0.0], [0.1], [20.0], [20.1]], "groups*": [0, 0, 0, 0, 2, 2], "c": [2, 0, 1],
                         "folds": ["0", "2"], "P*": [[.75, .75]] * 4 + [[1.0, 0.0]] * 2, "pick*": [0] * 6,
                         "v_mem*": [1, 1, 1, 1, 1, 0], "mean v_mem*": 5 / 6, "copies bit-identical": True},
            "observed": {"X*": Xs, "groups*": gs, "c": cnt, "folds": sorted(pred["k"]), "P*": pred["P"], "pick*": de["pick"],
                         "v_mem*": de["v_mem"], "mean v_mem*": float(np.mean(de["v_mem"])), "copies bit-identical": copies}}


def _p0_neighbours(np, p0, sp, use, groups, ks) -> list:
    nb = [None] * len(groups)
    for tr, te, name in p0.folds(groups):
        D = sp.dist(tr, te, use)
        idx = np.argsort(D, axis=1, kind="stable")[:, :min(ks[name], len(tr))]
        for r, i in enumerate(te):
            nb[i] = tuple(sorted(tr[idx[r]].tolist()))
    return nb


def sv0_2(c) -> Check:
    np, p0, L, R, data, budget = c["np"], c["p0"], c["L"], c["R"], c["data"], c["budget"]
    ck = Check("SV0-2", "independent pure-Python reference vs the exact P0 pipeline")
    for dname in ("B0", "B1", "B2", "A2"):
        d = data[dname]
        X, Y, base = d["X"], d["Y"], d["base"]
        sp = p0.Space(X, L.BLOCKS)
        Xl, Yl, gl = X.tolist(), Y.tolist(), base.tolist()
        v = {}
        near_only = True
        for pname, use in L.POLICIES.items():
            pred = p0.predict(sp, use, Y, base, base)
            de = p0.decision_eval(pred, Y)
            nb = _p0_neighbours(np, p0, sp, use, base, pred["k"])
            ref = R.predict(Xl, Yl, gl, L.BLOCKS, use, check=budget.check)
            rd = R.decision(ref["P"], ref["prior"], Yl)
            budget.check()
            dis = []                                                        # (what, fold, row)
            dis += [("k", f, None) for f in sorted(pred["k"]) if pred["k"][f] != ref["k"].get(f)]
            for i in range(len(Y)):
                f = str(gl[i])
                if nb[i] != ref["neighbours"][i]:
                    dis.append(("neighbours", f, i))
                for key, a, b in (("pick", de["pick"][i], rd["pick"][i]), ("v_mem", de["v_mem"][i], rd["v_mem"][i]),
                                  ("v_pi0", de["v_pi0"][i], rd["v_pi0"][i])):
                    if a != b:
                        dis.append((key, f, i))
                if not np.array_equal(pred["prior"][i], np.array(ref["prior"][i])):
                    dis.append(("prior", f, i))
                if np.abs(pred["P"][i] - np.array(ref["P"][i])).max() > 1e-12:
                    dis.append(("P", f, i))
                if abs(pred["gate_sim"][i] - ref["gate_sim"][i]) > 1e-12:
                    dis.append(("gate_sim", f, i))
            margins = [min(rd["margin"][i] if i is not None else math.inf, ref["kgap"][f]) for _w, f, i in dis]
            hard = [x for x, m in zip(dis, margins) if m >= 1e-9]
            near_only &= not hard
            ck.add(f"{dname} {pname}: P0 == reference (k, neighbour sets, pick, v_mem, v_pi0, prior exact; P, gate_sim 1e-12)",
                   0, len(dis), not dis, rule="disagreements; FAIL-INVESTIGATE only if every one has a margin < 1e-9",
                   investigate=bool(dis) and not hard, disagreements=[list(x) for x in dis[:50]],
                   max_abs_diff_P=float(max(np.abs(pred["P"][i] - np.array(ref["P"][i])).max() for i in range(len(Y)))))
            ck.diag(f"{dname} {pname} min pick margin", min(rd["margin"]))
            ck.diag(f"{dname} {pname} min inner-CV loss gap", min(ref["kgap"].values()))
            ck.diag(f"{dname} {pname} min k-boundary distance gap", min(ref["boundary_gap"].values()))
            v[pname] = (de["v_mem"], rd["v_mem"])
        e_p0 = float(np.mean(v["interv"][0] - v["obs_morph"][0]))
        e_ref = math.fsum(a - b for a, b in zip(v["interv"][1], v["obs_morph"][1])) / len(Y)
        ok = e_p0 == e_ref
        ck.add(f"{dname} estimate mean(v_interv - v_obs_morph)", e_ref, e_p0, ok, investigate=not ok and near_only)
    return ck


def _direct(c, dname: str) -> dict:
    """Direct exact-P0 outputs (pred, decision) per policy for one dataset, computed once and shared by SV0-3 and SV0-4."""
    cache = c.setdefault("direct", {})
    if dname not in cache:
        p0, L, d = c["p0"], c["L"], c["data"][dname]
        sp = p0.Space(d["X"], L.BLOCKS)
        cache[dname] = {}
        for p, u in L.POLICIES.items():
            pred = p0.predict(sp, u, d["Y"], d["base"], d["base"])
            cache[dname][p] = (pred, p0.decision_eval(pred, d["Y"]))
    return cache[dname]


def sv0_3(c) -> Check:
    np, p0, L, data, budget = c["np"], c["p0"], c["L"], c["data"], c["budget"]
    ck = Check("SV0-3", "refit wrapper: identity, duplicates, edge cases")
    direct = {}
    # 3a identity
    for dname in ("A0", "A1", "A2", "B0", "B1", "B2"):
        d = data[dname]
        X, Y, base, G = d["X"], d["Y"], d["base"], d["G"]
        direct[dname] = _direct(c, dname)
        reps = [L.replicate(X, Y, base, np.arange(G)) for _ in range(2)]
        budget.check()
        for p in L.POLICIES:
            same = all(_same_pred(np, r["pred"][p], direct[dname][p][0]) and _same_eval(np, r["eval"][p], direct[dname][p][1])
                       for r in reps)
            ck.add(f"3a {dname} {p}: replicate(idx = arange(G)) == direct P0, two calls", True, same, same)
        th = float(np.mean(direct[dname]["interv"][1]["v_mem"] - direct[dname]["obs_morph"][1]["v_mem"]))
        ck.exact(f"3a {dname} estimate", th, [L.theta(r["eval"]) for r in reps][0])
        ck.add(f"3a {dname} rows unchanged by the identity layout", True, bool(np.array_equal(reps[0]["X"], X)),
               bool(np.array_equal(reps[0]["X"], X)))
    # 3b hand duplicates through the fixture entry point
    f6 = _f6(c)
    for k, v in f6["expected"].items():
        ck.exact(f"3b F6 via resample -> refit_eval_fixed_k: {k}", v, f6["observed"][k])
    # 3c / 3d duplicates on synthetic data through the production entry point
    rng = np.random.default_rng(SV0_SEED + SEED_OFF["boot_3c"])
    for dname in ("B0", "B1", "B2"):
        d = data[dname]
        X, Y, base, G = d["X"], d["Y"], d["base"], d["G"]
        patterns = {"one base 2x": [0, 0] + list(range(1, 11)), "one 2x + one 3x": [0, 0, 1, 1, 1] + list(range(2, 9)),
                    "seeded bootstrap draw": rng.integers(0, G, G).tolist()}
        for pat, idx in patterns.items():
            tag = f"3c {dname} [{pat}]"
            rep = L.replicate(X, Y, base, idx)
            budget.check()
            gs, cnt, sp = rep["groups"], rep["c"], rep["space"]
            g_star = int((cnt > 0).sum())
            lab = bool(np.array_equal(gs, np.repeat(np.flatnonzero(cnt > 0), cnt[cnt > 0] * M_INST)))
            ck.add(f"{tag} (i) copies keep the original label", True, lab, lab)
            nf = {p: len(rep["pred"][p]["k"]) for p in L.POLICIES}
            ck.exact(f"{tag} (ii) outer folds = G*", {p: g_star for p in L.POLICIES}, nf)
            ok3 = True
            for tr, te, name in p0.folds(gs):
                g = int(name)
                ok3 &= bool(np.array_equal(te, np.flatnonzero(gs == g))) and len(te) == cnt[g] * M_INST and not (gs[tr] == g).any()
                for itr, ite, iname in p0.folds(gs[tr]):
                    gi = int(iname)
                    a, b = tr[itr], tr[ite]
                    ok3 &= bool(np.array_equal(b, np.flatnonzero(gs == gi))) and len(b) == cnt[gi] * M_INST and not (gs[a] == gi).any()
            ck.add(f"{tag} (iii) every outer and inner fold holds out all copies of its base", True, ok3, ok3)
            ci = L.copy_index(gs, M_INST)
            ok4 = True
            for p in L.POLICIES:
                P, ev = rep["pred"][p]["P"], rep["eval"][p]
                for b in np.flatnonzero(cnt >= 2):
                    r0 = np.flatnonzero((gs == b) & (ci == 0))
                    for j in range(1, int(cnt[b])):
                        rj = np.flatnonzero((gs == b) & (ci == j))
                        ok4 &= (bool(np.array_equal(P[r0], P[rj])) and bool(np.array_equal(ev["pick"][r0], ev["pick"][rj]))
                                and bool(np.array_equal(ev["v_mem"][r0], ev["v_mem"][rj])))
            ck.add(f"{tag} (iv) copies have bit-identical P, pick and v", True, ok4, ok4)
            dd = rep["eval"]["interv"]["v_mem"] - rep["eval"]["obs_morph"]["v_mem"]
            per_base = {int(b): float(dd[(gs == b) & (ci == 0)].sum()) for b in np.flatnonzero(cnt > 0)}
            th_re = sum(float(cnt[b]) * s for b, s in per_base.items()) / (G * M_INST)
            ck.exact(f"{tag} (v) theta* = (1/(G m)) sum_b c_b sum_i d*_bi", th_re, L.theta(rep["eval"]))
            leaks = {p: int(L.leak_check(sp, gs, u).sum()) for p, u in L.POLICIES.items()}
            ck.exact(f"{tag} (vi) leak_check flags no row", {p: 0 for p in L.POLICIES}, leaks)
            sep = gs * 100 + ci                                             # 3d: copies as separate groups (leaky)
            flagged = L.leak_check(sp, sep, L.POLICIES["interv"])
            copied = cnt[gs] >= 2
            det = float(flagged[copied].mean()) if copied.any() else None
            ck.add(f"3d {dname} [{pat}] positive control: separate copy labels are detected", 1.0, det, det == 1.0)
            ck.diag(f"3d {dname} [{pat}] false positives (non-copied rows flagged)", int(flagged[~copied].sum()))
            ck.diag(f"{tag} G*", g_star)
    # 3e degeneracy: the production path rejects G* <= 2; the fixture path rejects only G* = 1
    X5, Y5, b5, blk5 = _f5(np)

    def raised(fn):
        try:
            fn()
        except Exception as e:
            return type(e).__name__
        return None
    f5_use = {"f5": ("obs",)}
    ck.exact("3e replicate on F5, idx [0,0,0] (G* = 1)", "DegenerateReplicate",
             raised(lambda: L.replicate(X5, Y5, b5, [0, 0, 0], uses=f5_use, blocks=blk5)))
    ck.exact("3e replicate on F5, F6's idx [0,0,2] (G* = 2)", "DegenerateReplicate",
             raised(lambda: L.replicate(X5, Y5, b5, [0, 0, 2], uses=f5_use, blocks=blk5)))
    dB = data["B0"]
    ck.exact("3e replicate on B0 with G* = 2", "DegenerateReplicate",
             raised(lambda: L.replicate(dB["X"], dB["Y"], dB["base"], [0] * 6 + [1] * 6)))
    Xs, Ys, gs1, _ = L.resample(X5, Y5, b5, [0, 0, 0])
    ck.exact("3e refit_eval_fixed_k at G* = 1", "ValueError",
             raised(lambda: L.refit_eval_fixed_k(p0.Space(Xs, blk5), Ys, gs1, ("obs",), {"0": 1})))
    # 3f G* moments (index draws only)
    for G, key in ((12, "gstar_12"), (28, "gstar_28")):
        gsd = L.g_star_draws(G, 10000, np.random.default_rng(SV0_SEED + SEED_OFF[key]))
        e, mean, se = L.expected_g_star(G), float(gsd.mean()), float(gsd.std(ddof=1) / math.sqrt(len(gsd)))
        ck.exact(f"3f E[G*] at G = {G} (3 d.p.)", {12: 7.776, 28: 17.886}[G], round(e, 3))
        ck.add(f"3f mean G* over 10,000 draws at G = {G} within 4 MC-SE", e, mean, abs(mean - e) <= 4 * se,
               rule="|mean - E| <= 4 MC-SE", mc_se=se)
    return ck


def _relabel_compare(np, base_pe, pred, ev, kmap) -> bool:
    base_pred, base_eval = base_pe
    return (all(np.array_equal(base_pred[k], pred[k]) for k in ("P", "prior", "gate_sim")) and _same_eval(np, base_eval, ev)
            and {kmap[f]: v for f, v in base_pred["k"].items()} == pred["k"])


def sv0_4(c) -> Check:
    np, p0, L, data, budget = c["np"], c["p0"], c["L"], c["data"], c["budget"]
    ck = Check("SV0-4", "label relabelling")
    direct = {dname: _direct(c, dname) for dname in ("A0", "A1", "A2", "B0", "B1", "B2")}
    for dname in ("A0", "A1", "A2", "B0", "B1", "B2"):
        d = data[dname]
        X, Y, base = d["X"], d["Y"], d["base"]
        sp = p0.Space(X, L.BLOCKS)
        nb = 1000 + 7 * base
        kmap = {str(g): str(1000 + 7 * g) for g in range(d["G"])}
        for p, u in L.POLICIES.items():
            pred, ev = L.refit_eval(sp, Y, nb, u)
            ok = _relabel_compare(np, direct[dname][p], pred, ev, kmap)
            ck.add(f"4a {dname} {p}: labels g -> 1000 + 7g", True, ok, ok)
        budget.check()
    rng = np.random.default_rng(SV0_SEED + SEED_OFF["relabel_4b"])
    for dname in ("B0", "B1", "B2"):
        d = data[dname]
        X, Y, base, G = d["X"], d["Y"], d["base"], d["G"]
        sp = p0.Space(X, L.BLOCKS)
        for j in range(3):
            perm = rng.permutation(G)
            kmap = {str(g): str(int(perm[g])) for g in range(G)}
            for p, u in L.POLICIES.items():
                pred, ev = L.refit_eval(sp, Y, perm[base], u)
                ok = _relabel_compare(np, direct[dname][p], pred, ev, kmap)
                ck.add(f"4b {dname} perm {j} {p}: non-monotone labels", True, ok, ok,
                       rule="exact; any deviation is FAIL-INVESTIGATE (U2)", investigate=True, perm=perm)
            budget.check()
    rng = np.random.default_rng(SV0_SEED + SEED_OFF["order_4c"])
    for dname in ("B0", "B1", "B2"):
        d = data[dname]
        X, Y, base, G = d["X"], d["Y"], d["base"], d["G"]
        for j in range(3):
            order = rng.permutation(G)
            rows = np.concatenate([np.flatnonzero(base == b) for b in order])
            inv = np.argsort(rows)
            sp = p0.Space(X[rows], L.BLOCKS)
            for p, u in L.POLICIES.items():
                pred, ev = L.refit_eval(sp, Y[rows], base[rows], u)
                bp, be = direct[dname][p]
                ck.diag(f"4c {dname} order {j} {p}", {
                    "pick_agreement": float(np.mean(ev["pick"][inv] == be["pick"])),
                    "max_abs_dP": float(np.abs(pred["P"][inv] - bp["P"]).max()),
                    "k_agreement": float(np.mean([pred["k"][f] == bp["k"][f] for f in bp["k"]]))})
            budget.check()
    return ck


def _l4_fixture(ck: Check, np, p0) -> None:
    """Lemma 4 on the exact P0 Space.dist / knn_rates, deterministic hand-built fixture (revision 4b; replaces the gated B2
    item of attempt 1, which was vacuous: no query kept its neighbour set). Expected values are derived by hand:
    training rows r0..r3 in bases 0, 0, 1, 1 with (obs, cf) = (1, 1), (1, -1), (-1, 1), (-1, -1), so both columns have
    training mean 0 and population sd 1 exactly before and after the cf derangement (z = x, all distances exact). The
    unique within-base derangement of pairs swaps the cf values r0 <-> r1 and r2 <-> r3. Y = [1,0], [0,1], [1,0], [0,1],
    prior = [1/2, 1/2], k = 2, single-column blocks (block distance = squared z-difference).
    Case A, query (obs 1, cf 0.5): D [1/4, 9/4, 17/4, 25/4] -> [9/4, 1/4, 25/4, 17/4]; neighbours (0, 1) -> (1, 0): the
    order changes, the set does not; P = ([1,0] + [0,1] + prior) / 3 = [1/2, 1/2] both times (bit-identical).
    Case B (positive control), query (obs 0, cf 1): D [1, 5, 1, 5] -> [5, 1, 5, 1]; neighbours {0, 2} -> {1, 3};
    P = ([1,0] + [1,0] + prior) / 3 = [5/6, 1/6] -> ([0,1] + [0,1] + prior) / 3 = [1/6, 5/6]."""
    X = np.array([[1.0, 1.0], [1.0, -1.0], [-1.0, 1.0], [-1.0, -1.0], [1.0, 0.5], [0.0, 1.0]])
    Y = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 1.0]])
    blocks, use, k = {"obs": [0], "cf": [1]}, ("obs", "cf"), 2
    tr, te = np.arange(4), np.array([4, 5])
    swap = np.array([1, 0, 3, 2])                                  # the only derangement of two pairs
    Xd = X.copy()
    Xd[tr, 1] = X[swap, 1]
    pri = Y.mean(0)
    D, Dd = p0.Space(X, blocks).dist(tr, te, use), p0.Space(Xd, blocks).dist(tr, te, use)
    N, Nd = np.argsort(D, axis=1, kind="stable")[:, :k], np.argsort(Dd, axis=1, kind="stable")[:, :k]   # as in knn_rates
    P, Pd = p0.knn_rates(D, Y, k, pri), p0.knn_rates(Dd, Y, k, pri)
    ck.exact("L4F cf block changed on every training row; obs block unchanged",
             {"cf_changed": [True] * 4, "obs_unchanged": True},
             {"cf_changed": (Xd[tr, 1] != X[tr, 1]).tolist(), "obs_unchanged": bool(np.array_equal(Xd[:, 0], X[:, 0]))})
    ck.exact("L4F distances before the derangement", [[0.25, 2.25, 4.25, 6.25], [1.0, 5.0, 1.0, 5.0]], D)
    ck.exact("L4F distances after the derangement", [[2.25, 0.25, 6.25, 4.25], [5.0, 1.0, 5.0, 1.0]], Dd)
    ck.exact("L4F Case A: ordered neighbours (0, 1) -> (1, 0), same set {0, 1}",
             {"before": [0, 1], "after": [1, 0], "same_set": True},
             {"before": N[0], "after": Nd[0], "same_set": set(N[0].tolist()) == set(Nd[0].tolist())})
    ck.exact("L4F Case A: P before and after", {"before": [0.5, 0.5], "after": [0.5, 0.5]}, {"before": P[0], "after": Pd[0]})
    ok = bool(np.array_equal(P[0], Pd[0]))
    ck.add("L4F Case A: P bit-identical when the neighbour set is unchanged (Lemma 4)", True, ok, ok)
    ck.exact("L4F Case B (positive control): neighbour set {0, 2} -> {1, 3}",
             {"before": [0, 2], "after": [1, 3], "same_set": False},
             {"before": sorted(N[1].tolist()), "after": sorted(Nd[1].tolist()),
              "same_set": set(N[1].tolist()) == set(Nd[1].tolist())})
    ck.close("L4F Case B: P before = [5/6, 1/6]", [5 / 6, 1 / 6], P[1])
    ck.close("L4F Case B: P after = [1/6, 5/6]", [1 / 6, 5 / 6], Pd[1])
    ok = not np.array_equal(P[1], Pd[1])
    ck.add("L4F Case B: P changes when the neighbour set changes", True, ok, ok)


def _h_table(bins_per_base) -> list:
    return [{"base": b, "bin": k, "row": ("row", b, i), "cf": ("cf", b, i)}
            for b, bins in enumerate(bins_per_base) for i, k in enumerate(bins)]


def sv0_5(c) -> Check:
    np, p0, L, R, data = c["np"], c["p0"], c["L"], c["R"], c["data"]
    ck = Check("SV0-5", "H4 non-degeneracy calculator (amendment 2.2 Lemmas 1-7, erratum E2)")
    F = Fraction
    hc = _h_table([[0, 0, 1]] * 3)
    hc[0]["row"] = hc[1]["row"] = ("identical",)
    small = {
        "H-a": (_h_table([[0, 0, 1]] * 3), "S-base", {"D": 8, "F": F(1), "N3": F(1), "valid": True, "regime": "limited exact set"}),
        "H-b": (_h_table([[0, 0, 1]] * 3), "S-family-free",
                {"D": 1, "F": F(2, 3), "N3": F(1), "valid": True, "regime": "single deterministic contrast"}),
        "H-c": (hc, "S-family-free", {"D": 1, "F": F(4, 9), "N3": F(1), "valid": False, "regime": None}),
        "H-d": (_h_table([[0, 0, 0], [0, 0, 1], [0, 0, 1]]), "S-family-free",
                {"D": 2, "F": F(7, 9), "N3": F(1), "valid": True, "regime": "limited exact set"}),
        "H-e": (_h_table([[0, 1, 2]] * 3), "S-family-free", {"D": None, "F": F(0), "N3": F(0), "valid": False, "regime": None}),
        "H-f": (_h_table([[0, 0, 1]] * 3), "S-cf-conditional",
                {"D": 8, "F": F(1), "N3": F(1), "valid": True, "regime": "limited exact set"}),
    }
    for hid, (tab, ctrl, exp) in small.items():
        got = L.h4_calc(tab, ctrl)
        ck.exact(f"{hid} {ctrl}: calculator", exp, {k: got[k] for k in exp})
        bf = R.brute_h4(tab, ctrl)
        d_bf = None if bf["n_groups_ge2"] == 0 else bf["D_enum"]
        ck.exact(f"{hid} {ctrl}: brute-force enumeration (D, F, N3)", {"D": exp["D"], "F": exp["F"], "N3": exp["N3"]},
                 {"D": d_bf, "F": bf["F"], "N3": bf["N3"]})
    pff = _h_table([[0, 0, 1]] * 27)
    pid = _h_table([[0, 0, 1]] * 27)
    pid[0]["row"] = pid[1]["row"] = ("identical",)
    planned = {
        "planned S-base, 27 bases, distinct rows": (pff, "S-base", {"D": 134217728, "F": F(1), "N3": F(1), "valid": True,
                                                                    "regime": "genuine permutation distribution"}),
        "planned S-family-free (2,1) per base": (pff, "S-family-free", {"D": 1, "F": F(2, 3), "N3": F(1), "valid": True,
                                                                       "regime": "single deterministic contrast"}),
        "planned S-family-free, one identical-pair base": (pid, "S-family-free", {"D": 1, "F": F(52, 81), "N3": F(1), "valid": True,
                                                                                 "regime": "single deterministic contrast"}),
        "planned S-global over 81 records": (pff, "S-global", {"D": R.subfactorial_sum(81), "F": F(1), "N3": F(1), "valid": True,
                                                              "regime": "genuine permutation distribution"}),
    }
    for name, (tab, ctrl, exp) in planned.items():
        got = L.h4_calc(tab, ctrl)
        ck.exact(f"{name}: calculator vs closed form", exp, {k: got[k] for k in exp})
    # lemma checks on the exact P0 functions (set B, 'interventions add information')
    d = data["B2"]
    X, Y, base = d["X"], d["Y"], d["base"]
    sp = p0.Space(X, L.BLOCKS)
    use = L.POLICIES["interv"]
    rng = np.random.default_rng(SV0_SEED + SEED_OFF["lemma_5"])
    l1 = l2 = l3 = True
    l2_changed, l4_same_n, l4_changed_n, l4_violations = 0, 0, 0, 0
    cf_cols = L.BLOCKS["cf"]
    for tr, te, _name in p0.folds(base):
        perm = L.derange_within(base[tr], rng)
        l1 &= bool(np.array_equal(Y[tr].mean(0), Y[tr][perm].mean(0)))
        D = sp.dist(tr, te, use)
        pri = Y[tr].mean(0)
        l2 &= bool(np.array_equal(p0.knn_rates(D, Y[tr], len(tr), pri), p0.knn_rates(D, Y[tr][perm], len(tr), pri)))
        l2_changed += int((p0.knn_rates(D, Y[tr], 1, pri) != p0.knn_rates(D, Y[tr][perm], 1, pri)).any(1).sum())
        rp = rng.permutation(len(tr))
        Xtr = X[tr]
        a = np.concatenate([np.nanmean(Xtr, 0), np.nanstd(Xtr, 0)])
        b = np.concatenate([np.nanmean(Xtr[rp], 0), np.nanstd(Xtr[rp], 0)])
        # relative to the column magnitude: a mean that is ~0 by chance has no meaningful own-relative error
        scale = np.concatenate([np.nanmean(np.abs(Xtr), 0)] * 2)
        l3 &= bool((np.abs(a - b) <= 1e-12 * np.maximum(np.maximum(np.abs(a), np.abs(b)), scale)).all())
        cperm = L.derange_within(base[tr], rng)
        Xc = X.copy()
        Xc[np.ix_(tr, cf_cols)] = X[np.ix_(tr[cperm], cf_cols)]
        Dc = p0.Space(Xc, L.BLOCKS).dist(tr, te, use)
        k = 5
        Pk, Pc = p0.knn_rates(D, Y[tr], k, pri), p0.knn_rates(Dc, Y[tr], k, pri)
        Nk = np.argsort(D, axis=1, kind="stable")[:, :k]
        Nc = np.argsort(Dc, axis=1, kind="stable")[:, :k]
        for q in range(len(te)):
            if set(Nk[q].tolist()) == set(Nc[q].tolist()):
                l4_same_n += 1
                l4_violations += int(not np.array_equal(Pk[q], Pc[q]))
            else:
                l4_changed_n += 1
    ck.add("L1 prior bit-identical under within-base derangement (every fold)", True, l1, l1)
    ck.add("L2 k = n_train: P bit-invariant under within-base outcome derangement", True, l2, l2)
    ck.add("L2 positive control k = 1: at least one prediction changes", ">= 1", l2_changed, l2_changed >= 1)
    ck.add("L3 training mean and sd invariant under row permutation (relative 1e-12)", True, l3, l3,
           rule="|a - b| <= 1e-12 * max(|a|, |b|, mean |x| of the column)")
    _l4_fixture(ck, np, p0)                                        # gated: deterministic hand-built fixture (revision 4b)
    ck.diag("L4 synthetic diagnostic (B2, k = 5; NOT gated since revision 4b): cf derangement within training bases",
            {"queries_with_unchanged_set": l4_same_n, "queries_with_changed_set": l4_changed_n,
             "invariance_violations_among_unchanged": l4_violations})
    pred = p0.predict(sp, use, Y, base, base)
    ks = pred["k"]
    mem = p0.decision_eval(p0.predict(sp, use, Y, base, base, k_fixed=ks), Y)["v_mem"]
    n, T = Y.shape
    P, pri_oof = np.zeros((n, T)), np.zeros((n, T))
    singleton = np.arange(n)                                       # every record its own stratum
    for tr, te, name in p0.folds(base):
        perm = L.derange_within(singleton[tr], rng)
        pri = Y[tr].mean(0)
        P[te] = p0.knn_rates(sp.dist(tr, te, use), Y[tr][perm], ks[name], pri)
        pri_oof[te] = pri
    ctrl = p0.decision_eval({"P": P, "prior": pri_oof, "gate_sim": np.zeros(n)}, Y)["v_mem"]
    ck.exact("L5 singleton-stratum control: V(pi_M) - V(pi_ctrl) per instance", [0.0] * n, (mem - ctrl).tolist())
    ck.exact("L6 !1..!4 by enumeration", [0, 1, 2, 9], [len(R.derangements(m)) for m in (1, 2, 3, 4)])
    ck.exact("L6 !1..!4 by the calculator recurrence", [0, 1, 2, 9], [L.subfactorial(m) for m in (1, 2, 3, 4)])
    ck.exact("L6 6^27 (m = 3 uniform, 27 groups)", "1.0235e+21", f"{6 ** 27:.4e}")
    two_bins = _h_table([[(a >> 2) & 1, (a >> 1) & 1, a & 1] for a in range(8)])
    ck.exact("L7 m = 3, K = 2: N3 = 1 for every bin assignment (pigeonhole)", F(1), L.h4_calc(two_bins, "S-family-free")["N3"])
    ck.exact("L7 balanced m = 3, K = 3: N3 = 0", F(0), L.h4_calc(_h_table([[0, 1, 2]] * 3), "S-family-free")["N3"])
    return ck


def sv0_6(c) -> Check:
    np, calc, data, budget = c["np"], c["calc"], c["data"], c["budget"]
    ck = Check("SV0-6", "generator and archived regression")
    again = make_datasets(np, calc)
    for dname in sorted(data):
        d, e = data[dname], again[dname]
        G = d["G"]
        ck.exact(f"{dname} X shape", [3 * G, 42], list(d["X"].shape))
        ck.exact(f"{dname} Y shape", [3 * G, 10], list(d["Y"].shape))
        ck.exact(f"{dname} base = repeat(arange(G), 3)", np.repeat(np.arange(G), 3), d["base"])
        ck.add(f"{dname} Y in {{0, 1}}", True, bool(np.isin(d["Y"], (0.0, 1.0)).all()), bool(np.isin(d["Y"], (0.0, 1.0)).all()))
        h1 = {k: _sha256(np.ascontiguousarray(d[k]).tobytes()) for k in ("X", "Y", "base")}
        h2 = {k: _sha256(np.ascontiguousarray(e[k]).tobytes()) for k in ("X", "Y", "base")}
        ck.exact(f"{dname} regeneration bit-identical (sha256 of X, Y, base)", h1, h2)
    c0 = time.process_time()
    total = 0
    for mod_name, n_expected in ARCHIVED_TESTS.items():
        suite = unittest.defaultTestLoader.loadTestsFromModule(c["tests"][mod_name])
        res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        total += res.testsRun
        ck.exact(f"archived suite {mod_name}", {"run": n_expected, "failures": 0, "errors": 0, "skipped": 0, "ok": True},
                 {"run": res.testsRun, "failures": len(res.failures), "errors": len(res.errors), "skipped": len(res.skipped),
                  "ok": res.wasSuccessful()})
    ck.exact("archived tests in total", 52, total)
    c["tests_cpu_s"] = time.process_time() - c0
    if c["tests_cpu_s"] > LIMITS["tests_cpu_s"]:
        raise ResourceAbort("archived tests CPU > 5 min")
    budget.check()
    return ck


def sv0_7(c) -> Check:
    np, calc, L = c["np"], c["calc"], c["L"]
    ck = Check("SV0-7", "interval constructors (fixtures; no coverage)")
    ck.close("CR1 SE (calc section E formula)", math.sqrt(3) / 6, L.cr1_se([1, 1, 0, 0, 1, 0], [0, 0, 1, 1, 2, 2]))
    ck.close("t_ppf(0.95, df) for df = 2 / 11 / 27", [2.919986, 1.795885, 1.703288],
             [calc.t_ppf(0.95, df) for df in (2, 11, 27)], tol=1e-5)
    ck.close("percentile 5 / 95 of 1..20 (linear)", [1.95, 19.05], list(L.percentile_ci(range(1, 21))))
    ck.close("Wilson lower bounds", [0.7647, 0.7353, 0.7639, 0.7356],
             [L.wilson_lower(k, n, z) for k, n, z in ((35, 40, 1.645), (34, 40, 1.645), (34, 40, 1.282), (33, 40, 1.282))],
             tol=5e-4)
    for G in (12, 28):
        s1 = L.half_splits(G, 40, np.random.default_rng(SV0_SEED + SEED_OFF["half_7"]))
        s2 = L.half_splits(G, 40, np.random.default_rng(SV0_SEED + SEED_OFF["half_7"]))
        shape_ok = all(len(a) == len(b) == G // 2 and not set(a) & set(b) and set(a) | set(b) == set(range(G)) for a, b in s1)
        keys = {a if 0 in a else b for a, b in s1}
        ck.add(f"half-sample splits G = {G}: 40 splits of two disjoint covering halves", True, len(s1) == 40 and shape_ok,
               len(s1) == 40 and shape_ok)
        ck.exact(f"half-sample splits G = {G}: distinct", 40, len(keys))
        ck.add(f"half-sample splits G = {G}: identical on regeneration", True, s1 == s2, s1 == s2)
    return ck


def _ast_violations() -> list:
    allowed_rng = {"default_rng", "Generator", "PCG64", "SeedSequence"}
    banned = {"coverage_sim", "learning_inflation", "cluster_bootstrap"}
    out = []
    for f in CODE_FILES:
        tree = ast.parse(_read(os.path.join(SV0_DIR, f)).decode("utf-8"), filename=f)
        for node in ast.walk(tree):
            line = getattr(node, "lineno", 0)
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "random" for a in node.names):
                out.append(f"{f}:{line} import random")
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "random":
                out.append(f"{f}:{line} from random import")
            elif isinstance(node, ast.Attribute):
                v = node.value
                if (isinstance(v, ast.Attribute) and v.attr == "random" and isinstance(v.value, ast.Name)
                        and v.value.id in ("np", "numpy") and node.attr not in allowed_rng):
                    out.append(f"{f}:{line} numpy.random.{node.attr}")
                if node.attr in banned:
                    out.append(f"{f}:{line} .{node.attr}")
            elif isinstance(node, ast.Name) and node.id in banned:
                out.append(f"{f}:{line} {node.id}")
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and "coverage" in node.name.lower():
                out.append(f"{f}:{line} def {node.name}")
    return out


def sv0_8(c) -> Check:
    ck = Check("SV0-8", "guards and process determinism")
    import glob
    import multiprocessing
    import socket
    import subprocess

    def raised(fn):
        try:
            fn()
        except BaseException as e:                                  # noqa: BLE001 - the exception is the observation
            return e
        return None

    def probe_open(path, mode):
        with open(path, mode):
            pass
    probes = {                                                      # None in sys.modules raises ModuleNotFoundError (an ImportError)
        "import mujoco": (lambda: importlib.import_module("mujoco"), ImportError),
        "socket.socket()": (lambda: socket.socket(), GuardViolation),
        "open artifacts/x": (lambda: probe_open(os.path.join(REPO, "artifacts", "x"), "r"), GuardViolation),
        "open ~/dev/.env": (lambda: probe_open(os.path.join(HOME, "dev", ".env"), "r"), GuardViolation),
        "write outside sv0/out/run<N>/": (lambda: probe_open(os.path.join(REPO, "sv0_guard_probe.txt"), "w"), GuardViolation),
        "subprocess.run": (lambda: subprocess.run(["true"], check=False), GuardViolation),
        "multiprocessing.Process.start": (lambda: multiprocessing.Process(target=int).start(), GuardViolation),
        "glob.glob": (lambda: glob.glob(os.path.join(REPO, "*")), GuardViolation),
    }
    for name, (fn, exp) in probes.items():
        e = raised(fn)
        ck.add(f"guard fires: {name}", f"raises {exp.__name__}", None if e is None else type(e).__name__, isinstance(e, exp))
    ck.exact("AST scan of sv0/*.py: no global RNG seeding, no random module, no coverage loop", [], _ast_violations())
    loaded = sorted(k for k, m in sys.modules.items() if k.split(".")[0] == "mujoco" and m is not None)
    ck.exact("no mujoco* module loaded", [], loaded)
    ck.diag("cross-process byte identity", "verified outside the process: cmp run1/sv0_results.json run2/sv0_results.json")
    return ck


CHECKS = (("SV0-1", sv0_1), ("SV0-2", sv0_2), ("SV0-3", sv0_3), ("SV0-4", sv0_4), ("SV0-5", sv0_5), ("SV0-6", sv0_6),
          ("SV0-7", sv0_7), ("SV0-8", sv0_8))


# ============================================================================================== 7. outputs
def _cgroup_info() -> dict:
    info = {}
    try:
        txt = _read("/proc/self/cgroup").decode("ascii", "replace")
        info["proc_self_cgroup"] = txt.strip()
        for line in txt.splitlines():
            if line.startswith("0::"):
                base = "/sys/fs/cgroup" + line[3:].strip()
                for f in ("memory.max", "memory.swap.max", "cpu.max", "pids.max"):
                    p = os.path.join(base, f)
                    if os.path.exists(p):
                        info[f] = _read(p).decode("ascii", "replace").strip()
    except OSError as e:
        info["error"] = f"{type(e).__name__}: {e}"
    try:
        import resource
        info["rlimit_cpu"] = list(resource.getrlimit(resource.RLIMIT_CPU))
    except ImportError:
        pass
    return info


def _report(classification: str, checks: list, reason: str | None) -> str:
    L = [f"# P05-SV0 run report ({PROPOSAL})", "", f"**Classification: {classification}**", ""]
    if reason:
        L += [f"Reason: {reason}", ""]
    L += ["| check | status |", "|---|---|"] + [f"| {c['id']} {c['title']} | {c['status']} |" for c in checks]
    fails = [(c["id"], it) for c in checks for it in c["items"] if it["result"] != "PASS"]
    L += ["", "## Items not passing (verbatim)", ""]
    L += [f"- {cid} / {it['name']}: {it['result']}; expected {json.dumps(it['expected'])}; observed {json.dumps(it['observed'])}"
          for cid, it in fails] or ["- none"]
    diag4c = [d for c in checks if c["id"] == "SV0-4" for d in c["diagnostics"]]
    L += ["", "## SV0-4c row-block reorder (diagnostic, not gated)", ""]
    L += [f"- {d['name']}: {json.dumps(d['value'], sort_keys=True)}" for d in diag4c] or ["- not reached"]
    L += ["", "Cross-process determinism (SV0-8) is verified outside the process with `cmp` of the two runs' sv0_results.json.",
          "", STATEMENT, ""]
    return "\n".join(L)


def main() -> int:
    env = {"proposal": PROPOSAL, "run": RUN, "argv": sys.argv[1:], "limits": LIMITS, "pins": PINS,
           "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        os.makedirs(OUT)
    except FileExistsError:
        print(f"refusing to overwrite {OUT}", file=sys.stderr)
        return 2

    def setup_fail(stage: str, e: Exception, done: list) -> int:
        """Unexpected setup error outside a check: explicit FAIL result, nothing else is run."""
        ck = Check("SETUP", stage)
        ck.add(f"{stage} completed without exception", None, f"{type(e).__name__}: {e}", False)
        _dump({"proposal": PROPOSAL, "classification": "FAIL", "failed_at": stage, "error": f"{type(e).__name__}: {e}",
               "checks": done + [ck.as_dict()], "statement": STATEMENT}, "sv0_results.json")
        return 1
    try:
        read_mem = _memory_backend()
        budget = Budget()
        mon = Monitor(budget, read_mem)
        mon.sample()
        mon.start()
    except Exception as e:                                              # noqa: BLE001 - reported as FAIL
        return setup_fail("resource monitor setup", e, [])
    budget.start("SV0-0")
    ck0 = Check("SV0-0", "provenance and environment preflight")
    try:
        mods = sv0_0(ck0, env, read_mem)
    except Exception as e:                                              # Sv0Fail or anything unexpected: fail closed
        if not isinstance(e, Sv0Fail):
            ck0.add("SV0-0 completed without exception", None, f"{type(e).__name__}: {e}", False)
        _dump({"proposal": PROPOSAL, "classification": "FAIL", "failed_at": "SV0-0", "error": f"{type(e).__name__}: {e}",
               "checks": [ck0.as_dict()], "statement": STATEMENT}, "sv0_results.json")
        return 1
    budget.stop()
    try:                                                                # the audit hook stays active whatever happens here
        secondary_guards()
    except Exception as e:                                              # noqa: BLE001 - reported as FAIL
        return setup_fail("secondary guards", e, [ck0.as_dict()])
    try:
        ctx = dict(mods, budget=budget, data=make_datasets(mods["np"], mods["calc"]))
    except Exception as e:                                              # noqa: BLE001 - reported as FAIL
        return setup_fail("synthetic dataset generation", e, [ck0.as_dict()])
    checks, classification, reason = [ck0.as_dict()], None, None
    try:
        for cid, fn in CHECKS:
            budget.start(cid)
            try:
                ck = fn(ctx)
            except ResourceAbort:
                raise
            except Exception as e:                                      # noqa: BLE001 - recorded as a FAIL item
                ck = Check(cid, "unexpected exception")
                ck.add("check completed without exception", None, f"{type(e).__name__}: {e}", False)
            budget.stop()
            checks.append(ck.as_dict())
            budget.check()
    except ResourceAbort as e:
        classification, reason = "ABORTED-RESOURCE", str(e)
    if classification is None:
        st = {c["status"] for c in checks}
        classification = "FAIL" if "FAIL" in st else "FAIL-INVESTIGATE" if "FAIL-INVESTIGATE" in st else "PASS"
    mon.stop_evt.set()
    mon.sample()
    results = {"proposal": PROPOSAL, "classification": classification, "reason": reason, "checks": checks,
               "statement": STATEMENT}
    _dump(results, "sv0_results.json")
    env.update({"end_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "per_check": budget.per_check,
                "run_wall_s": round(time.monotonic() - budget.t0, 3), "run_cpu_s": round(time.process_time() - budget.c0, 3),
                "archived_tests_cpu_s": ctx.get("tests_cpu_s"), "peak_rss_bytes": mon.peak_rss, "peak_vmhwm_bytes": mon.peak_hwm,
                "min_mem_available_bytes": mon.min_avail, "cgroup": _cgroup_info(),
                "threads": {v: os.environ.get(v) for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}})
    _dump(env, "sv0_env.json")
    with open(os.path.join(OUT, "sv0_report.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_report(classification, checks, reason))
    return {"PASS": 0, "FAIL": 1, "ABORTED-RESOURCE": 3, "FAIL-INVESTIGATE": 4}[classification]


if __name__ == "__main__":
    sys.exit(main())
