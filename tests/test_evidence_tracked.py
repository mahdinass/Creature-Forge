"""Guard: every file a tracked run-record directory lists in its SHA256SUMS is itself tracked by git, and verifies.

A clean checkout (VM, CI, a judge's clone) must contain the complete evidence. On 2026-10-21 the repository-wide `*.log`
ignore rule had silently left 18 run logs out of experiments/do1 and experiments/ta1; this test would have caught it on
the machine that made the commit. Skipped only outside a git checkout.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ("experiments/do1", "experiments/ta1")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


class EvidenceTrackedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("git") is None or subprocess.run(["git", "rev-parse"], cwd=ROOT, capture_output=True).returncode:
            raise unittest.SkipTest("not a git checkout")
        cls.tracked = set(_git("ls-files", "--", *EVIDENCE).splitlines())
        cls.sums = sorted(p for p in cls.tracked if p.endswith("/SHA256SUMS"))

    def test_record_directories_have_checksums(self):
        self.assertGreaterEqual(len(self.sums), 6)

    def test_every_listed_file_is_tracked_and_verifies(self):
        problems = []
        for s in self.sums:
            d = s.rsplit("/", 1)[0]
            for line in (ROOT / s).read_text(encoding="utf-8").splitlines():
                h, rel = line.split(" *", 1)
                p = f"{d}/{rel}"
                if p not in self.tracked:
                    problems.append(f"listed but not tracked: {p}")
                elif hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h:
                    problems.append(f"checksum differs: {p}")
        self.assertEqual(problems, [])

    def test_no_untracked_file_in_record_directories(self):
        others = _git("ls-files", "--others", "--", *EVIDENCE).splitlines()
        ignored = _git("ls-files", "--others", "--ignored", "--exclude-standard", "--", *EVIDENCE).splitlines()
        self.assertEqual(sorted(set(others) | set(ignored)), [])


if __name__ == "__main__":
    unittest.main()
