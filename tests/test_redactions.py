"""Guard: tracked run evidence exposes no local Windows account path, and the documented redactions are verifiable.

The rule and its record are in scripts/redact_local_paths.py and docs/archive/redactions_2026-10-21.json. When the
git-ignored run archive is present (owner's PC), each tracked copy must equal the rule applied to its byte-exact
original. Elsewhere (CI, VM) the tracked copies are checked against the recorded hashes only.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import redact_local_paths as rl  # noqa: E402


class RedactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(rl.RECORD, encoding="utf-8") as fh:
            cls.record = json.load(fh)

    def test_rule_replaces_only_the_account_segment(self):
        for raw in (rb'r"C:\Users\someone\.vscode\x"', rb'"C:\\Users\\someone\\.vscode\\x"', rb"C:/Users/someone/.vscode/x"):
            red, n = rl.redact(raw)
            self.assertEqual(n, 1)
            self.assertEqual(red, raw.replace(b"someone", b"<user>"))
            self.assertEqual(rl.redact(red), (red, 0))     # idempotent: the placeholder is never replaced again
        self.assertEqual(rl.redact(b"/home/forge/dev/x and D:\\data\\y"), (b"/home/forge/dev/x and D:\\data\\y", 0))

    def test_record_covers_seven_files(self):
        self.assertEqual(len(self.record["files"]), 7)
        for e in self.record["files"]:
            self.assertGreater(e["replacements"], 0)
            self.assertNotEqual(e["original_sha256"], e["redacted_sha256"])

    def test_tracked_copies_match_the_record_and_originals(self):
        self.assertEqual(rl.check(self.record), [])

    def test_no_tracked_run_file_contains_an_account_path(self):
        bad = []
        for base in ("experiments/do1", "experiments/ta1"):
            for d, _, files in os.walk(os.path.join(ROOT, base)):
                for f in files:
                    with open(os.path.join(d, f), "rb") as fh:
                        if rl.account_paths(fh.read()):
                            bad.append(os.path.relpath(os.path.join(d, f), ROOT))
        self.assertEqual(bad, [])

    def test_redacted_json_manifests_still_parse(self):
        for e in self.record["files"]:
            if e["tracked"].endswith(".json"):
                with open(os.path.join(ROOT, e["tracked"]), encoding="utf-8") as fh:
                    self.assertIsInstance(json.load(fh), dict)


if __name__ == "__main__":
    unittest.main()
