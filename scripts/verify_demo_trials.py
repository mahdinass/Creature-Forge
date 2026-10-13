#!/usr/bin/env python
"""Re-run MuJoCo from the parameters saved in each bundled demo trial and compare with the saved numbers.

For every record: (1) sha256 against experiments/demo_trials/manifest.json, (2) per-seed screening statistics for
every saved seed (original + modified robot), (3) with --full, the complete held-out protocol (5 push levels x 10
seeds x 2 designs = 100 simulations). Uses the cross-platform tolerance policy of creature_forge.reproducibility.
No model call, no network, writes nothing. Exit 0 = every record reproduces.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from creature_forge import lab  # noqa: E402


def main() -> int:
    full = "--full" in sys.argv
    bad = 0
    for row in lab.list_lab_trials(Path("/nonexistent"), lab.DEMO_DIR):
        tid = row["trial_id"]
        trial, _ = lab.load_lab_trial(tid, Path("/nonexistent"), lab.DEMO_DIR)
        integ = lab.demo_integrity(tid)
        line = [f"{tid} [{row['status']}] sha256={'ok' if integ and integ['verified'] else 'MISMATCH'}"]
        bad += not (integ and integ["verified"])
        for seed in lab.replay_seeds(trial):
            rep = lab.build_replay(trial, seed)
            for arm, c in rep["consistency"].items():
                if c["checked"]:
                    bad += not c["matches_saved_record"]
                    line.append(f"seed{seed}/{arm}:{'ok' if c['matches_saved_record'] else 'DIFF'}(max_rel={c['max_rel_diff']:.1e})")
        if full and (trial.get("measured_outcome") or {}).get("protocol"):
            rep = lab.reverify_protocol(trial)
            bad += not rep["ok"]
            line.append(f"heldout-protocol:{'ok' if rep['ok'] else 'DIFF'}")
        print(" ".join(line))
    print("ALL DEMO TRIALS REPRODUCE" if bad == 0 else f"{bad} MISMATCH(ES)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
