#!/usr/bin/env python3
"""Freeze manifest for the immutable experiment records under experiments/.

Maps every git-tracked file under experiments/ (except experiments/forge_loop/ and the
manifest itself) to its git blob id. Working-tree files are hashed the way git stores
them (clean filters, .gitattributes, core.autocrlf), so CRLF and LF checkouts both match.

  python scripts/freeze_manifest.py          write experiments/FROZEN_MANIFEST.json
  python scripts/freeze_manifest.py --check  exit 1 if anything drifted

Writing refuses while a frozen working-tree file differs from its git blob, so a
modified record cannot be silently re-frozen. Needs git only; no network, no physics.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_REL = "experiments/FROZEN_MANIFEST.json"
EXCLUDED_PREFIXES = ("experiments/forge_loop/",)


def git(args: list[str], stdin: bytes | None = None) -> bytes:
    proc = subprocess.run(["git", *args], cwd=ROOT, input=stdin, capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {args[0]} failed: {err}")
    return proc.stdout


def is_frozen(path: str) -> bool:
    return path != MANIFEST_REL and not path.startswith(EXCLUDED_PREFIXES)


def tracked_blob_ids() -> dict[str, str]:
    """Index blob id of each tracked frozen path (git ls-files -s)."""
    out = git(["ls-files", "-s", "-z", "--", "experiments/"])
    blobs: dict[str, str] = {}
    for record in out.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.decode("utf-8").partition("\t")
        _mode, blob, stage = meta.split()
        if stage != "0":
            raise RuntimeError(f"unmerged index entry, resolve first: {path}")
        if is_frozen(path):
            blobs[path] = blob
    return blobs


def working_tree_blob_ids(paths: list[str]) -> dict[str, str]:
    """Blob ids git would store for the working-tree files (one batched git call)."""
    if not paths:
        return {}
    payload = ("\n".join(paths) + "\n").encode("utf-8")
    hashes = git(["hash-object", "--stdin-paths"], stdin=payload).decode("ascii").split()
    if len(hashes) != len(paths):
        raise RuntimeError("git hash-object returned an unexpected number of ids")
    return dict(zip(paths, hashes))


def render(manifest: dict[str, str]) -> str:
    return json.dumps(dict(sorted(manifest.items())), indent=1) + "\n"


def working_tree_problems(manifest: dict[str, str]) -> list[str]:
    present = [p for p in manifest if (ROOT / p).is_file()]
    problems = [f"missing from working tree: {p}" for p in manifest if p not in present]
    actual = working_tree_blob_ids(present)
    for path in present:
        if actual[path] != manifest[path]:
            problems.append(f"modified (differs from committed blob): {path}")
    return problems


def write() -> int:
    manifest = tracked_blob_ids()
    problems = working_tree_problems(manifest)
    if problems:
        print("Refusing to freeze: working tree differs from git blobs:", file=sys.stderr)
        for line in problems:
            print("  " + line, file=sys.stderr)
        return 1
    (ROOT / MANIFEST_REL).write_text(render(manifest), encoding="utf-8", newline="\n")
    print(f"Wrote {MANIFEST_REL} with {len(manifest)} entries.")
    return 0


def check() -> int:
    expected = tracked_blob_ids()
    manifest_path = ROOT / MANIFEST_REL
    if not manifest_path.is_file():
        print(f"Drift: {MANIFEST_REL} is missing. Run: python scripts/freeze_manifest.py")
        return 1
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    for path in sorted(set(on_disk) - set(expected)):
        problems.append(f"in manifest but no longer tracked: {path}")
    for path in sorted(set(expected) - set(on_disk)):
        problems.append(f"tracked but not in manifest (re-run the script to add): {path}")
    for path in sorted(set(expected) & set(on_disk)):
        if expected[path] != on_disk[path]:
            problems.append(f"index blob differs from manifest (staged change): {path}")
    problems += working_tree_problems(on_disk)
    if problems:
        print("Frozen-record drift detected:")
        for line in problems:
            print("  " + line)
        return 1
    print(f"OK: {len(on_disk)} frozen records match {MANIFEST_REL}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify instead of writing")
    args = parser.parse_args()
    return check() if args.check else write()


if __name__ == "__main__":
    sys.exit(main())
