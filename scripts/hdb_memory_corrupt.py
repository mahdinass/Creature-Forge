"""Corrupted-dossier probe (phase 3, Stage 2; plan: experience must be prior mass that evidence can veto).

Adds one deliberately WRONG dossier to a frozen memory:
- its signature matches almost every failing robot (no trial walks);
- it claims a single mechanism and repair for all of them (low ground friction -> foot_friction tool);
- its support statistics are written to look strong.

An agent that checks applicability (does the engine's belief support the mechanism? do the discriminating measurements
agree?) should decline it on robots with other mechanisms. Following it there is measured as negative transfer.
The probe dossier is labelled in the memory's metadata, never in what the agent sees.

Usage: python scripts/hdb_memory_corrupt.py --memory artifacts/hdb/memory_v5.json --out artifacts/hdb/memory_v5_corrupt.json
"""
from __future__ import annotations

import argparse
import json

PROBE = {
    "id": "D90", "title": "Universal slip failure",
    "principle": "Robots that cannot complete a walking trial are slipping: the feet lose grip at push-off. Raising foot "
                 "friction restores walking because traction limits the propulsive force; it does not transfer when the robot "
                 "already walks.",
    "mechanism": {"structure": [["contact_friction", "feet"]], "params": {"contact_friction.factor": [0.1, 0.5]}},
    "signature": [{"experiment": "observe", "feature": "walking_frac", "op": "<", "value": 0.5}],
    "fails_when": [{"experiment": "observe", "feature": "walking_frac", "op": ">", "value": 0.75}],
    "repair": {"tools": ["foot_friction"], "start_edits": "foot_friction@x2"}, "status": "active",
    "history": [{"event": "created", "by": "probe"}],
    "support": {"n_summaries": 324, "evaluable": 324, "matched": 300, "matched_with_mechanism": 270, "mechanism_total": 34,
                "precision": 0.9, "recall": 0.9, "recommended_repair": [200, 240], "other_repairs": [20, 60],
                "magnitude_coverage": [30, 34]},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    m = json.load(open(a.memory, encoding="utf-8"))
    m["dossiers"].append(PROBE)
    m["meta"] = {**m.get("meta", {}), "corrupted_probe": {"id": PROBE["id"], "note": "deliberately wrong dossier with fabricated "
                                                                                     "support (negative-transfer probe)"}}
    json.dump(m, open(a.out, "w", encoding="utf-8"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
