"""Write experiments/causal_engineer/heldout/protocol.json (the binding registration of PROTOCOL.md).

    python scripts/ce_heldout_register.py --instances <heldout_shard*.jsonl ...> --memory-probe <dev probe jsonl> \
        --memory-episodes <dev episode jsonl ...> --learned-model <level_c json> --out experiments/causal_engineer/heldout/protocol.json

Pins: the git commit (the working tree must be clean), SHA-256 of every input file (held-out instance files, memory inputs, Level C
model, the PROTOCOL.md text), the model configuration of the thinking arms, the arms, the hypotheses and the selected instance ids.
Run once, then commit protocol.json with a refreshed FROZEN_MANIFEST.json BEFORE any held-out episode runs.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

import ce_eval  # noqa: E402
import ce_heldout_analysis as ha  # noqa: E402
import ce_heldout_select as hs  # noqa: E402

ARMS = ("scientist_think", "scientist_1shot_think", "scientist_think_mem", "scientist_think_mem_learned", "exhaustive", "learned",
        "expert", "random")


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", nargs="+", required=True)
    ap.add_argument("--memory-probe", nargs="+", required=True)
    ap.add_argument("--memory-episodes", nargs="*", default=[])
    ap.add_argument("--learned-model", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO, capture_output=True, text=True).stdout
    if dirty.strip():
        raise SystemExit(f"working tree has uncommitted changes to tracked files; commit first:\n{dirty}")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    pool = [json.loads(l) for p in a.instances for l in open(p, encoding="utf-8") if l.strip()]
    ids, cap = hs.select(pool, a.n)
    cfg = dataclasses.asdict(ce_eval.thinking_config())
    proto = {"id": "ce-heldout-eval-v1", "code_commit": commit, "protocol_md_sha256": sha(os.path.join(REPO, "experiments", "causal_engineer", "heldout", "PROTOCOL.md")),
             "arms": list(ARMS), "hypotheses": [{"id": h, "a": x, "b": y} for h, x, y in ha.HYPOTHESES] +
             [{"id": "C1", "a": "scientist_think prediction accuracy", "b": "majority-direction baseline"}],
             "alpha": 0.05, "correction": "Holm-Bonferroni over C1, C2, C3, C4, C5a, C5b", "primary_outcome": "FULL_RECOVERY (full_recovery_v1)",
             "budget": 700, "n_train": 4, "n_obs": 4, "max_steps": 12, "thinking_model_config": cfg,
             "inputs": {"instances": {os.path.basename(p): sha(p) for p in a.instances},
                        "memory_probe": {os.path.basename(p): sha(p) for p in a.memory_probe},
                        "memory_episodes": {os.path.basename(p): sha(p) for p in a.memory_episodes},
                        "learned_model": {os.path.basename(a.learned_model): sha(a.learned_model)}},
             "selection": {"rule": "PROTOCOL.md", "base_cap_used": cap, "n_pool_kept": sum(1 for r in pool if r.get("kept"))},
             "instance_ids": ids}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(proto, fh, indent=1)
    print(json.dumps({k: v for k, v in proto.items() if k != "instance_ids"} | {"n_instances": len(ids)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
