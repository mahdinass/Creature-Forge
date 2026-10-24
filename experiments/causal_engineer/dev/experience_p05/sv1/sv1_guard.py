"""P05-SV1 process guard (proposal CF-V2-P05-SV1, section 8): the SV0 audit-hook pattern, generalised for sharded workers.

install(out_dir, pre_dir) must be called before numpy or any repository module is imported. The hook cannot be removed. It
refuses: subprocesses, sockets, glob, file mutation outside out_dir, and reads of sealed or secret locations (artifacts/,
*.jsonl, .env, ~/dev outside the interpreter tree, ~/creature-forge). Reads are otherwise limited to the repository, the
interpreter trees, pre_dir and a few /proc and /sys files. Provenance (hashes, fingerprint) is checked separately by sv1_run.
"""
import os
import sys

_rp = os.path.realpath
SV1_DIR = _rp(os.path.dirname(os.path.abspath(__file__)))
REPO = SV1_DIR
for _ in range(5):                                   # sv1 -> experience_p05 -> dev -> causal_engineer -> experiments -> repo
    REPO = os.path.dirname(REPO)
SV0_DIR = os.path.join(os.path.dirname(SV1_DIR), "sv0")
ARCHIVE = os.path.join(os.path.dirname(SV1_DIR), "design_archive")
HOME = _rp(os.path.expanduser("~"))
PREFIXES = tuple(sorted({_rp(sys.prefix), _rp(sys.base_prefix)}))


class GuardViolation(PermissionError):
    """Raised for any refused file, process, network or glob operation."""


def _under(p: str, root: str) -> bool:
    return p == root or p.startswith(root.rstrip(os.sep) + os.sep)


class _Policy:
    def __init__(self, out_dir: str, pre_dir: str | None):
        self.out = _rp(out_dir)
        self.pre = _rp(pre_dir) if pre_dir else None
        sysf = ("/proc/self/status", "/proc/meminfo", "/proc/cpuinfo", "/etc/os-release", "/proc/self/cgroup")
        self.sys_files = set(sysf) | {_rp(f) for f in sysf}

    def refused(self, p: str) -> bool:
        return (_under(p, os.path.join(REPO, "artifacts")) or p.endswith(".jsonl") or os.path.basename(p) == ".env"
                or _under(p, os.path.join(HOME, "creature-forge"))
                or (_under(p, os.path.join(HOME, "dev")) and not any(_under(p, r) for r in PREFIXES)))

    @staticmethod
    def in_prefix(p: str) -> bool:
        for r in PREFIXES:
            if _under(p, r):
                rel = os.path.relpath(p, r).split(os.sep)
                return "creature_forge" not in rel and not os.path.basename(p).startswith("__editable__")
        return False

    def allow_read(self, p: str) -> bool:
        return (_under(p, REPO) or _under(p, self.out) or self.in_prefix(p) or (self.pre is not None and _under(p, self.pre))
                or p in self.sys_files or _under(p, "/sys/fs/cgroup"))

    def allow_write(self, p: str) -> bool:
        return _under(p, self.out)

    def allow_list(self, p: str) -> bool:
        return (_under(p, REPO) or _under(p, self.out) or self.in_prefix(p)
                or (self.pre is not None and _under(p, self.pre)))


_POLICY: _Policy | None = None
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_REFUSED_PREFIX = ("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn", "os.fork", "pty.", "glob.",
                   "urllib.", "http.", "ftplib.", "smtplib.", "webbrowser.")
_REFUSED = {"os.system", "os.startfile", "os.kill", "os.killpg", "os.remove", "os.rename", "os.rmdir", "os.chmod",
            "os.chown", "os.truncate", "os.link", "os.symlink", "os.chdir", "os.utime", "shutil.rmtree", "shutil.move",
            "shutil.copyfile", "shutil.copytree", "shutil.make_archive", "shutil.unpack_archive"}


def _norm(path) -> tuple[str, str]:
    s = os.fsdecode(os.fspath(path))
    return os.path.abspath(s), _rp(s)


def _ok(ps, allow) -> bool:
    return not any(_POLICY.refused(p) for p in ps) and any(allow(p) for p in ps)


def _audit(event: str, args: tuple) -> None:
    if _POLICY is None:
        return
    if event == "open":
        path, mode, flags = (tuple(args) + (None, None, None))[:3]
        if path is None or isinstance(path, int):
            return
        ps = _norm(path)
        write = (any(ch in mode for ch in "wax+") if isinstance(mode, str)
                 else bool(isinstance(flags, int) and flags & _WRITE_FLAGS))
        if not (_POLICY.allow_write(ps[1]) and not _POLICY.refused(ps[0]) if write else _ok(ps, _POLICY.allow_read)):
            raise GuardViolation(f"SV1 guard refused open({ps[1]!r}, write={write})")
    elif event in ("os.listdir", "os.scandir"):
        path = args[0] if args else None
        if isinstance(path, int):
            return
        ps = _norm(path if path not in (None, "", b"") else ".")
        if not _ok(ps, _POLICY.allow_list):
            raise GuardViolation(f"SV1 guard refused {event}({ps[1]!r})")
    elif event == "os.mkdir":
        if not _under(_norm(args[0])[1], _POLICY.out):
            raise GuardViolation(f"SV1 guard refused os.mkdir({args[0]!r})")
    elif event in _REFUSED or event.startswith(_REFUSED_PREFIX):
        raise GuardViolation(f"SV1 guard refused {event}")


def install(out_dir: str, pre_dir: str | None = None) -> None:
    """Install the audit hook (idempotent per process) and set the import path to the approved checkout."""
    global _POLICY
    if _POLICY is not None:
        return
    _POLICY = _Policy(out_dir, pre_dir)
    sys.addaudithook(_audit)
    kept = [p for p in sys.path if p and any(_under(_rp(p), r) for r in PREFIXES)]
    sys.path[:] = [SV1_DIR, SV0_DIR, REPO, ARCHIVE] + kept
    sys.meta_path[:] = [f for f in sys.meta_path if "__editable__" not in " ".join(
        (type(f).__module__, type(f).__qualname__, str(getattr(f, "__module__", "")), str(getattr(f, "__name__", ""))))]


def secondary() -> None:
    """Defence in depth after imports: MuJoCo tripwire and raising replacements for process and socket creation."""
    import multiprocessing
    import socket
    import subprocess

    def refuse(*_a, **_k):
        raise GuardViolation("SV1 guard: refused by the secondary layer")
    sys.modules["mujoco"] = None
    subprocess.Popen = refuse
    multiprocessing.Process.start = refuse
    if hasattr(os, "fork"):
        os.fork = refuse
    socket.socket = refuse


def module_provenance_ok() -> list:
    """Every loaded creature_forge module must be a file of this checkout (fail closed on an installed copy)."""
    bad = []
    for k, m in list(sys.modules.items()):
        if m is None or not (k == "creature_forge" or k.startswith("creature_forge.")):
            continue
        f = getattr(m, "__file__", None)
        if not f or not _under(_rp(f), os.path.join(REPO, "creature_forge")):
            bad.append(f"{k}: {f}")
    return bad


# ------------------------------------------------------------------------------------------------ provenance helpers (shared by
# sv1_run, sv1_selftest and sv1_aggregate; they only read files)
CODE = {"sv0/sv0_lib.py": os.path.join(SV0_DIR, "sv0_lib.py"), "sv0/sv0_run.py": os.path.join(SV0_DIR, "sv0_run.py"),
        "design_archive/p05_design_calc.py": os.path.join(ARCHIVE, "p05_design_calc.py"),
        **{f"sv1/{f}": os.path.join(SV1_DIR, f) for f in ("sv1_guard.py", "sv1_fast.py", "sv1_lib.py", "sv1_run.py",
                                                         "sv1_aggregate.py", "sv1_selftest.py", "sv1_config.json")}}


def _read(p: str) -> bytes:
    with open(p, "rb") as fh:
        return fh.read()


def code_hashes() -> dict:
    import hashlib
    return {k: hashlib.sha256(_read(p)).hexdigest() for k, p in CODE.items()}


def fingerprint() -> dict:
    """The SV0 fingerprint snippet, parsed (not imported) from the pinned sv0_run.py and executed, so SV1 certifies the
    identical fingerprint SV0 passed in."""
    import ast
    for n in ast.parse(_read(CODE["sv0/sv0_run.py"]).decode("utf-8")).body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "FINGERPRINT_SRC":
            ns: dict = {}
            exec(compile(n.value.value, "<sv0-fingerprint>", "exec"), ns)
            return ns["fingerprint"]()
    raise RuntimeError("FINGERPRINT_SRC not found in sv0_run.py")
