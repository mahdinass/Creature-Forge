"""Dependency-free tests for Creature Forge session context safeguards."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def import_script(name: str):
    source = ROOT / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot import " + str(source))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class MemoryGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = import_script("guard_venv")
        cls.preflight = import_script("context_preflight")

    def test_detect_existing_environment_and_block_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / ".venv").mkdir()
            with patch.object(self.guard, "ROOT", base):
                self.assertEqual(self.guard.existing_envs(), [".venv"])
                self.assertTrue(self.guard.should_block("python -m venv .venv"))
                self.assertTrue(self.guard.should_block("uv venv"))
                self.assertTrue(self.guard.should_block("py -3 -m venv env"))
                self.assertTrue(self.guard.should_block("echo ready && virtualenv env"))
                self.assertFalse(self.guard.should_block("python -m pytest"))
                self.assertFalse(self.guard.should_block('echo "python -m venv .venv"'))

    def test_no_environment_does_not_block(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(self.guard, "ROOT", Path(d)):
                self.assertFalse(self.guard.should_block("python -m venv .venv"))

    def test_hook_configuration_is_valid_json(self):
        cfg = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertIn("SessionStart", cfg["hooks"])
        self.assertIn("PreToolUse", cfg["hooks"])
        for hook, script in (
            (cfg["hooks"]["SessionStart"][0]["hooks"][0], "context_preflight.py"),
            (cfg["hooks"]["PreToolUse"][0]["hooks"][0], "guard_venv.py"),
        ):
            # Must be cwd-independent: anchored on the project dir, never a relative path.
            self.assertEqual(hook["command"], "python")
            self.assertEqual(hook["args"], ["${CLAUDE_PROJECT_DIR}/scripts/" + script])

    def test_preflight_repository_root(self):
        self.assertTrue((self.preflight.ROOT / "docs/PROJECT_SPEC.md").is_file())

if __name__ == "__main__":
    unittest.main()
