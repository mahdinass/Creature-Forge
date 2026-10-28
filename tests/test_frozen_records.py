"""Guard: every frozen experiment record under experiments/ stays byte-identical.

The manifest (experiments/FROZEN_MANIFEST.json, written by scripts/freeze_manifest.py)
holds the git blob id of each tracked record. Working-tree files are hashed the way git
stores them, so CRLF (Windows autocrlf) and LF (Linux, CI, VM) checkouts both match.
Skipped only when git is unavailable or this is not a git checkout (e.g. installed wheel).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_REL = "experiments/FROZEN_MANIFEST.json"
EXCLUDED_PREFIXES = ("experiments/forge_loop/", "experiments/causal_engineer/dev/", "experiments/causal_engineer/demo_records/")   # living dirs; registered causal-engineer records live outside dev/ and are frozen


def _git(args: list[str], stdin: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=ROOT, input=stdin, capture_output=True, check=True
    ).stdout


def _skip_reason() -> str | None:
    if shutil.which("git") is None:
        return "git is not installed"
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True
    )
    if proc.returncode != 0:
        return "not a git checkout (e.g. installed wheel)"
    if Path(proc.stdout.strip()).resolve() != ROOT.resolve():
        return "source tree is not its own git checkout"
    return None


def _is_frozen(path: str) -> bool:
    return path != MANIFEST_REL and not path.startswith(EXCLUDED_PREFIXES)


def _tracked_frozen_paths() -> set[str]:
    out = _git(["ls-files", "-z", "--", "experiments/"]).decode("utf-8")
    return {p for p in out.split("\0") if p and _is_frozen(p)}


def _working_tree_blob_ids(paths: list[str]) -> dict[str, str]:
    if not paths:
        return {}
    payload = ("\n".join(paths) + "\n").encode("utf-8")
    hashes = _git(["hash-object", "--stdin-paths"], stdin=payload).decode("ascii").split()
    return dict(zip(paths, hashes, strict=True))


class FrozenRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reason = _skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        manifest_path = ROOT / MANIFEST_REL
        if not manifest_path.is_file():
            raise AssertionError(f"{MANIFEST_REL} is missing; run scripts/freeze_manifest.py")
        cls.manifest: dict[str, str] = json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_manifest_is_not_empty(self):
        self.assertTrue(self.manifest, "frozen manifest has no entries")

    def test_manifest_lists_exactly_the_tracked_frozen_files(self):
        tracked = _tracked_frozen_paths()
        missing_from_manifest = sorted(tracked - set(self.manifest))
        no_longer_tracked = sorted(set(self.manifest) - tracked)
        problems = [f"tracked but not in manifest (re-run scripts/freeze_manifest.py): {p}"
                    for p in missing_from_manifest]
        problems += [f"in manifest but not tracked: {p}" for p in no_longer_tracked]
        self.assertFalse(problems, "\n".join(problems))

    def test_working_tree_matches_committed_blobs(self):
        absent = sorted(p for p in self.manifest if not (ROOT / p).is_file())
        present = sorted(p for p in self.manifest if (ROOT / p).is_file())
        actual = _working_tree_blob_ids(present)
        modified = sorted(p for p in present if actual[p] != self.manifest[p])
        problems = [f"missing: {p}" for p in absent]
        problems += [f"modified (differs from committed blob): {p}" for p in modified]
        self.assertFalse(problems, "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
