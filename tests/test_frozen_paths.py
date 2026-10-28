"""Guard: the source and inputs that decided the DO-1 pilot (commit e9d2379) stay byte-identical.

`tests/fixtures/frozen_paths_e9d2379.json` pins the git blob id of every top-level `creature_forge/*.py` module,
`scripts/do1_objective.py` and the DS-1 inputs (v6 settings, stop map, split, eval instances) as they were when
DO1-L4-r0 ran. Demo and integration work may add files, but must not change these. A change needs a documented owner
decision and a new pin file. Working-tree files are hashed the way git stores them, so CRLF and LF checkouts both match.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "tests" / "fixtures" / "frozen_paths_e9d2379.json"


def _git(args: list[str], stdin: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, input=stdin, capture_output=True, check=True).stdout


def _skip_reason() -> str | None:
    if shutil.which("git") is None:
        return "git is not installed"
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        return "not a git checkout (e.g. installed wheel)"
    if Path(proc.stdout.strip()).resolve() != ROOT.resolve():
        return "source tree is not its own git checkout"
    return None


class FrozenPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reason = _skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        cls.pins = json.loads(PINS.read_text(encoding="utf-8"))

    def test_pins_cover_the_experiment_core(self):
        blobs = self.pins["blobs"]
        self.assertEqual(self.pins["commit"], "e9d2379def2546cedcc9ce5c3cc2aa22b9746392")
        for p in ("creature_forge/hidden_plant.py", "creature_forge/belief_engine.py", "creature_forge/walk_opt.py",
                  "creature_forge/hdb_bench.py", "creature_forge/verdict.py", "scripts/do1_objective.py",
                  "experiments/causal_engineer/dev/hdb/ds1/stopmap_dev_v2.json"):
            self.assertIn(p, blobs)

    def test_working_tree_matches_pinned_blobs(self):
        blobs = self.pins["blobs"]
        absent = sorted(p for p in blobs if not (ROOT / p).is_file())
        present = sorted(p for p in blobs if (ROOT / p).is_file())
        payload = ("\n".join(present) + "\n").encode("utf-8")
        actual = dict(zip(present, _git(["hash-object", "--stdin-paths"], stdin=payload).decode("ascii").split(), strict=True))
        problems = [f"missing: {p}" for p in absent]
        problems += [f"modified since e9d2379: {p}" for p in present if actual[p] != blobs[p]]
        self.assertFalse(problems, "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
