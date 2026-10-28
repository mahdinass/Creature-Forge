"""Displacement-aware plant evidence (phase 3, DS-1; owner-approved amendment of 2026-10-20, docs/DS1_PROTOCOL.md §1.4).

The hidden verification (`full_recovery_v1`) also requires `verdict_v1` = VERIFIED_IMPROVEMENT: the repaired robot must walk
clearly farther than the faulty one on paired validation seeds. Stage 2 lost 32 of 128 failures there (the design walked, but
not farther than the faulty robot), and the stop rule could not see it. This module adds a policy-visible stand-in on the
ROBUST seeds only (never validation or confirmation seeds):
  * robustness checks also return each seed's walk score (forward displacement while upright; 0 if fallen before 1 s or no
    valid step: the walk challenge's score rule);
  * a one-time, charged baseline check of the faulty design (design 0) on the same robust seeds;
  * `displacement_evidence`: the frozen `verdict_v1` statistics applied to those paired robust-seed scores.

`EvidenceWorkbench` subclasses the frozen `HDBWorkbench` (unchanged) with identical seeds, costs and labels.
"""
from __future__ import annotations

from . import hidden_plant as hp
from . import verdict as vd
from .hdb_workbench import HDBWorkbench

VERSION = "hdb_evidence_v1"
BASELINE_N = 16


def walk_score(row: dict) -> float | None:
    """The walk challenge's score of one walk_job row (challenges.py: 0 if fallen before 1 s or no valid step)."""
    if not row.get("ok"):
        return None
    fell_early = bool(row.get("fell")) and (row.get("fall_time") or 0.0) < 1.0
    if fell_early or int(row.get("valid_steps") or 0) < 1:
        return 0.0
    return max(0.0, float(row.get("forward_disp_upright") or 0.0))


def displacement_evidence(faulty: list, cand: list, faulty_pass: list, cand_pass: list) -> dict | None:
    """verdict_v1's paired statistics on robust-seed walk scores (candidate vs faulty design, same seeds)."""
    n = min(len(faulty), len(cand))
    if n == 0:
        return None
    out = vd.verdict("walk", faulty[:n], cand[:n], original_pass=faulty_pass[:n], candidate_pass=cand_pass[:n])
    med = out.get("median_diff")
    return {"n": n, "status": out["status"], "median_diff_m": None if med is None else round(float(med), 4),
            "pass": out["status"] == "VERIFIED_IMPROVEMENT"}


class EvidenceWorkbench(HDBWorkbench):
    """HDBWorkbench whose robustness checks also report walk scores, with a charged baseline of the faulty design."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._baseline = None
        self.scores: dict[int, dict] = {}          # design index -> {"n": n, "scores": [...], "pass": [...]}

    def robustness_check(self, n: int = 8) -> dict:
        # identical to HDBWorkbench.robustness_check (same refusals, cost, seeds and labels) plus per-seed walk scores
        if n not in (8, 16):
            return self._refuse("robustness_check", f"n must be 8 or 16, got {n!r}")
        if self.remaining < n:
            return self._refuse("robustness_check", f"needs {n} rollouts, {self.remaining} remain")
        idx = self._best
        d = self.designs[idx]
        self._spend(n, "robustness_check", {"design": idx, "n": n})
        rows = hp.walk_seeds(self._plant, d["body"], d["vector"], self.view_seeds["robust"][:n], variation=self.variation,
                             pool=self.pool)
        sc = [walk_score(r) for r in rows]
        ps = [bool(r.get("ok") and r["walking"]) for r in rows]
        prev = self.scores.get(idx)
        if prev is None or prev["n"] <= n:
            self.scores[idx] = {"n": n, "scores": sc, "pass": ps}
        return {"ok": True, "design_index": idx, "n": n, "walking": int(sum(1 for r in rows if r.get("ok") and r["walking"])),
                "errors": int(sum(1 for r in rows if not r.get("ok"))), "labels": [r.get("label") for r in rows],
                "scores": sc}

    def baseline(self) -> dict | None:
        """The faulty design (design 0) on the first 16 robust seeds, once per investigation (charged 16 plant rollouts)."""
        if self._baseline is not None:
            return self._baseline
        if self.remaining < BASELINE_N:
            return None
        d = self.designs[0]
        self._spend(BASELINE_N, "baseline_check", {"design": 0, "n": BASELINE_N})
        rows = hp.walk_seeds(self._plant, d["body"], d["vector"], self.view_seeds["robust"][:BASELINE_N],
                             variation=self.variation, pool=self.pool)
        self._baseline = {"scores": [walk_score(r) for r in rows], "pass": [bool(r.get("ok") and r["walking"]) for r in rows]}
        return self._baseline

    def displacement(self, idx: int) -> dict | None:
        """Displacement evidence of design idx from its largest check (needs the 16-seed check; buys the baseline once)."""
        s = self.scores.get(int(idx))
        if s is None or s["n"] < 16:
            return None
        base = self.baseline()
        if base is None:
            return None
        return displacement_evidence(base["scores"], s["scores"], base["pass"], s["pass"])
