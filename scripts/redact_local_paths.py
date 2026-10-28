"""Publication copies of run files that contain local Windows account paths.

The tracked evidence under experiments/do1/ and experiments/ta1/ was copied from runs made on the owner's Windows PC.
Seven of those files contain absolute paths such as C:\\Users\\<account>\\.vscode\\... They are three analysis
scripts, plus the manifests and logs of the two locally run phases (RV-1 1A, X1).

The tracked copies replace only the account segment of such paths with `<user>`. The rule is the same in all three
spellings: `C:\\Users\\`, JSON-escaped `C:\\\\Users\\\\`, and `C:/Users/`. Nothing else changes. The byte-exact originals
stay in the git-ignored run archive. docs/archive/runs_2026-10-21.SHA256SUMS lists their SHA-256, and
docs/archive/redactions_2026-10-21.json records (original sha256, redacted sha256, replacements) for every file.
tests/test_redactions.py re-applies the rule to the archived originals whenever they are present.

  python scripts/redact_local_paths.py --check            # tracked copies match the record (and the originals, if found)
  python scripts/redact_local_paths.py --write <files>    # apply the rule in place (used once, 2026-10-21)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(ROOT, "docs", "archive", "redactions_2026-10-21.json")
PLACEHOLDER = b"<user>"
# account segment after C:\Users\ (raw), C:\\Users\\ (JSON-escaped) or C:/Users/; an existing placeholder is left alone
ACCOUNT_PATH = re.compile(rb"(?i)(C:(?:\\\\|\\|/)Users(?:\\\\|\\|/))(?!<user>)([^\\/\"'\s<>]+)")
ARCHIVE_CANDIDATES = (os.path.join(ROOT, "artifacts", "runs", "2026-10-20_21"),
                      os.path.join(ROOT, "..", "Creature-Forge", "artifacts", "runs", "2026-10-20_21"),
                      os.path.join(ROOT, "..", "creature_forge_runs"))


def redact(data: bytes) -> tuple[bytes, int]:
    return ACCOUNT_PATH.subn(lambda m: m.group(1) + PLACEHOLDER, data)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def account_paths(data: bytes) -> list[bytes]:
    """Every account path segment that is not the placeholder (empty list = publication-safe)."""
    return [m.group(0) for m in ACCOUNT_PATH.finditer(data)]


def archive_root() -> str | None:
    env = os.environ.get("CF_RUNS_ARCHIVE")
    for p in ((env,) if env else ()) + ARCHIVE_CANDIDATES:
        if p and os.path.isdir(p):
            return os.path.abspath(p)
    return None


def check(record: dict) -> list[str]:
    """Problems with the tracked copies, plus the originals when the archive is available (empty list = verified)."""
    problems, arch = [], archive_root()
    for e in record["files"]:
        with open(os.path.join(ROOT, e["tracked"]), "rb") as fh:
            tracked = fh.read()
        if sha256(tracked) != e["redacted_sha256"]:
            problems.append(f"{e['tracked']}: sha256 {sha256(tracked)} != recorded {e['redacted_sha256']}")
        if account_paths(tracked):
            problems.append(f"{e['tracked']}: still contains an account path")
        if arch:
            orig_path = os.path.join(arch, e["archive"])
            if not os.path.isfile(orig_path):
                problems.append(f"original {e['archive']} not in {arch}")
                continue
            with open(orig_path, "rb") as fh:
                orig = fh.read()
            red, n = redact(orig)
            if sha256(orig) != e["original_sha256"]:
                problems.append(f"original {e['archive']}: sha256 {sha256(orig)} != recorded {e['original_sha256']}")
            if red != tracked or n != e["replacements"]:
                problems.append(f"{e['tracked']}: redacting the original gives a different file ({n} vs {e['replacements']} replacements)")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.write:
        for f in a.write:
            with open(f, "rb") as fh:
                data = fh.read()
            red, n = redact(data)
            with open(f, "wb") as fh:
                fh.write(red)
            print(f"{f}: {n} replacement(s), sha256 {sha256(data)[:12]} -> {sha256(red)[:12]}")
        return 0
    with open(RECORD, encoding="utf-8") as fh:
        record = json.load(fh)
    problems = check(record)
    where = archive_root() or "archive not found: tracked copies only"
    if problems:
        print("REDACTION CHECK FAILED:\n  " + "\n  ".join(problems))
        return 1
    print(f"OK: {len(record['files'])} redacted files verified ({where})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
