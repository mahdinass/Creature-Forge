"""Shared causal experience store (phase 3, DS-1; docs/DS1_PROTOCOL.md §3).

One store links the two learning signals, which are scored separately:
  * DIAGNOSTIC: what explained the failure, on which evidence (posterior over explanations, its calibration against the dev
    post-mortem truth, the dossiers' diagnostic precision);
  * REPAIR: which intervention verified under which belief (verified outcomes of submitted repairs, the R-head's calibrated
    P(FULL), the dossiers' repair lift).
Each repair case keeps the agent-visible situation it was decided in (the engine's belief by deviation kind, the engine's tool
evidence), so the experience can be retrieved for a new robot by similarity (case attention) and fitted (R-head).
The store also keeps the scientist's own track record: when Nemotron overrode the engine's default, and how that verified,
and how well its registered P(success) predicted verification.

Built only from development records on the allowed bases (init bases; stream outcomes are appended chronologically).
"""
from __future__ import annotations

import collections
import json
import math
import os

import numpy as np

from . import repair_learning as rl
from .belief_engine import TOOL_PROBES
from .has_memory import Memory, compute_support, episode_summary, struct_key

VERSION = "has_cases_v1"
PROBE_TOOL = {p: t for t, ps in TOOL_PROBES.items() for p in ps}


def base_of(iid: str) -> str:
    return iid.split(":")[0]


def ds1_stream_bases(split: dict) -> list[str]:
    """DS-1 stream bases, pre-declared hash rule (docs/DS1_PROTOCOL.md §5): 4 old dev + 6 fresh dev experience bases."""
    import hashlib
    exp = split["experience_bases"]
    key = lambda b: hashlib.sha256(("ds1-stream:" + b).encode()).hexdigest()   # noqa: E731
    old = sorted([b for b in exp if not b.startswith("hdb-v1-gen")], key=key)[:4]
    fresh = sorted([b for b in exp if b.startswith("hdb-v1-gen")], key=key)[:6]
    return old + fresh


def ds1_init_bases(split: dict) -> list[str]:
    return sorted(set(split["experience_bases"]) - set(ds1_stream_bases(split)))


def structures_at(particles: list[dict], T: float) -> list:
    """Structure posterior from stored particles (pid, structure, loglik) at temperature T."""
    m = max(p["loglik"] for p in particles)
    agg: dict = collections.defaultdict(float)
    for p in particles:
        agg[tuple(sorted(tuple(x) for x in p["structure"]))] += math.exp((p["loglik"] - m) / T)
    z = sum(agg.values())
    return sorted(((list(map(list, k)), v / z) for k, v in agg.items()), key=lambda t: -t[1])


def decision_structures(rec: dict, T: float) -> list:
    """The belief a repair was decided in. v5 records: the stored particles re-tempered at T (no plant checks were assimilated).
    v6 records: the last posterior snapshot before the first assimilated plant check."""
    eng = rec["engine"]
    if eng.get("version") == "belief_engine_v6":
        snaps = [h for h in eng["history"] if "check@" not in h["label"]]
        return [(x["structure"], x["w"]) for x in snaps[-1]["structures"]] if snaps else []
    return structures_at(eng["particles"], T)


def final_tool(rec: dict) -> str | None:
    rep = rec.get("repair") or {}
    tool = None
    for e in rep.get("log") or []:
        if e.get("design") == rep.get("design"):
            tool = e.get("tool")
    sub = rec.get("submitted")
    if tool is None:
        src = [d.get("source") for d in rec.get("designs") or [] if d.get("index") == sub]
        if src and src[0] and src[0] != "initial":
            tool = src[0].split(":")[-1]
    return tool if tool in rl.TOOLS else PROBE_TOOL.get(tool or "")


def screens(rec: dict) -> tuple:
    ev = rec["engine"]["events"]
    probe = next((e["ranking"] for e in ev if e["kind"] == "tool_screen"), None)
    cma = next((e["ranking"] for e in ev if e["kind"] == "tool_screen_cma"), None)
    return probe, cma


def repair_case(rec: dict, T: float, procedure: str, situation_rec: dict | None = None, tool: str | None = None,
                status: str | None = None) -> dict | None:
    """One verified repair case: agent-visible situation + tool evidence of `situation_rec` (default: rec itself)."""
    s = situation_rec or rec
    tool = tool or final_tool(rec)
    if tool not in rl.TOOLS or "engine" not in s:
        return None
    probe, cma = screens(s)
    status = status or rec["verification"]["status"]
    return {"iid": rec["instance_id"], "base": base_of(rec["instance_id"]), "arm": rec.get("arm"), "tool": tool,
            "procedure": procedure, "full": status == "FULL_RECOVERY", "status": status,
            "sit": rl.situation_features(decision_structures(s, T)), "ev": rl.tool_evidence(probe, cma)[tool]}


def agent_decision(rec: dict) -> dict | None:
    """Nemotron's repair-level decision in one investigation: did it override the engine's default repair, its registered
    P(success) for the submitted design, and the verified outcome (for the scientist's track record)."""
    ag = rec.get("agent") or {}
    if not rec.get("nemotron"):
        return None
    acts = [t for t in ag.get("trace") or [] if t["actor"] == "nemotron"]
    deviated = any(t["action"].get("action") in ("repair", "conclude") or t["action"].get("tool_order")
                   or t["action"].get("start_edits") for t in acts)
    ps = [t["action"].get("p_success") for t in acts if t["action"].get("action") in ("delegate_repair", "conclude", "repair")
          and isinstance(t["action"].get("p_success"), (int, float))]
    return {"iid": rec["instance_id"], "base": base_of(rec["instance_id"]), "arm": rec.get("arm"), "deviated": bool(deviated),
            "p_success": float(ps[-1]) if ps else None, "full": rec["verification"]["status"] == "FULL_RECOVERY"}


class CaseStore:
    def __init__(self, cases: list[dict] | None = None, decisions: list[dict] | None = None, *, T: float = 1.0,
                 meta: dict | None = None, frozen: bool = True):
        self.cases, self.decisions = list(cases or []), list(decisions or [])
        self.T, self.meta, self.frozen = float(T), dict(meta or {}), frozen
        self.rhead: rl.RHead | None = None
        self.summaries: list[dict] = []

    # ------------------------------------------------------------------ persistence
    def save(self, path: str) -> None:
        json.dump({"version": VERSION, "T": self.T, "meta": self.meta, "cases": self.cases, "decisions": self.decisions,
                   "summaries": self.summaries}, open(path, "w", encoding="utf-8"))

    @classmethod
    def load(cls, path: str, *, frozen: bool = True) -> "CaseStore":
        d = json.load(open(path, encoding="utf-8"))
        s = cls(d["cases"], d["decisions"], T=d["T"], meta=d.get("meta"), frozen=frozen)
        s.summaries = d.get("summaries") or []
        s.refit()
        return s

    # ------------------------------------------------------------------ learning (development only)
    def refit(self) -> None:
        self.rhead = rl.RHead.fit(self.cases, "full", meta={"T": self.T, "n_cases": len(self.cases)}) if self.cases else None

    def append_records(self, recs: list[dict]) -> None:
        """Chronological update after a finished development round: the new verified cases, the scientist's decisions and the
        investigation summaries (for dossier support); then the R-head is refitted."""
        if self.frozen:
            raise RuntimeError("case store is frozen (evaluation): no updates")
        for r in recs:
            c = repair_case(r, self.T, "engine_final")
            if c:
                self.cases.append(c)
            d = agent_decision(r)
            if d:
                self.decisions.append(d)
            self.summaries.append(episode_summary(r))
        self.meta.setdefault("appended", []).append([r["instance_id"] for r in recs])
        self.refit()

    # ------------------------------------------------------------------ retrieval for the scientist
    def similar(self, sit: dict, k: int = 12, tau: float = 0.2) -> list[tuple[float, dict]]:
        """Case attention: the k most similar past cases by belief over deviation kinds (softmax similarity weights)."""
        q = np.array(sit["kind_w"] + [sit["entropy"], sit["lead"]])
        sc = [(-float(np.sum((q - np.array(c["sit"]["kind_w"] + [c["sit"]["entropy"], c["sit"]["lead"]])) ** 2)) / tau, c)
              for c in self.cases]
        sc.sort(key=lambda t: -t[0])
        top = sc[:k]
        if not top:
            return []
        m = top[0][0]
        w = [math.exp(s - m) for s, _ in top]
        z = sum(w)
        return [(wi / z, c) for wi, (_, c) in zip(w, top)]

    def evidence_lines(self, structures: list, probe: list | None, cma: list | None, engine_order: list[str]) -> list[str]:
        sit = rl.situation_features(structures)
        L = []
        if self.rhead is not None:
            p = self.rhead.scores(structures, probe, cma)
            top = sorted(p.items(), key=lambda t: -t[1])[:5]
            L.append("  Learned repair-outcome model (calibrated on verified past repairs; predicts, does not choose): "
                     "P(verified recovery) if submitted with " + ", ".join(f"{t} {v:.2f}" for t, v in top))
        sim = self.similar(sit)
        if sim:
            per = collections.defaultdict(lambda: [0.0, 0.0, 0])
            for w, c in sim:
                per[c["tool"]][0] += w * c["full"]
                per[c["tool"]][1] += w
                per[c["tool"]][2] += 1
            rows = sorted(per.items(), key=lambda t: -t[1][1])
            L.append(f"  {len(sim)} most similar past robots (by the engine's belief): verified recoveries by submitted tool: " +
                     "; ".join(f"{t} {v[0] / v[1]:.0%} of {v[2]}" for t, v in rows if v[1] > 0))
        if engine_order:
            L.append(f"  Engine's own tool order (twin screen): {', '.join(engine_order[:5])}")
        return L

    def track_record_lines(self) -> list[str]:
        ds = [d for d in self.decisions]
        if not ds:
            return ["  (no earlier investigations of yours are recorded yet)"]
        dev = [d for d in ds if d["deviated"]]
        dl = [d for d in ds if not d["deviated"]]
        L = [f"  {len(ds)} earlier investigations: when you overrode the engine's default repair, {sum(d['full'] for d in dev)}"
             f"/{len(dev)} verified; when you delegated it, {sum(d['full'] for d in dl)}/{len(dl)} verified."]
        ps = [d for d in ds if d["p_success"] is not None]
        if ps:
            brier = float(np.mean([(d["p_success"] - d["full"]) ** 2 for d in ps]))
            L.append(f"  Your registered P(success): mean {np.mean([d['p_success'] for d in ps]):.2f} vs actual rate "
                     f"{np.mean([d['full'] for d in ps]):.2f}; Brier {brier:.3f} on {len(ps)} (0.25 = uninformative).")
        return L


# ---------------------------------------------------------------------------------------------- dual-scored dossiers
def dual_status(sup: dict) -> dict:
    """Separate status per signal (Stage 2 mixed them: a repair-useful dossier was retired for weak diagnostic precision)."""
    prec, matched = sup.get("precision"), sup.get("matched") or 0
    rr, orr = sup.get("recommended_repair") or [0, 0], sup.get("other_repairs") or [0, 0]
    if prec is None or matched < 4:
        diag = "unproven"
    else:
        diag = "reliable" if prec >= 0.6 else ("weak" if prec < 0.4 else "mixed")
    if rr[1] >= 4 and orr[1] >= 4:
        lift = rr[0] / rr[1] - orr[0] / orr[1]
        rep = "helpful" if lift >= 0.1 else ("harmful" if lift <= -0.1 else "no better than alternatives")
    else:
        lift, rep = None, "unproven"
    return {"diagnostic": diag, "repair": rep, "repair_lift": None if lift is None else round(lift, 3)}


class DualMemory(Memory):
    """Dossiers with separately scored diagnostic and repair evidence; nothing is hidden for one weak signal."""

    def __init__(self, dossiers=None, *, frozen: bool = True):
        super().__init__(dossiers, frozen=frozen)

    def active(self) -> list[dict]:
        return list(self.dossiers.values())

    def rescore(self, summaries: list[dict]) -> None:
        for d in self.dossiers.values():
            d["support"] = compute_support(d, summaries)
            d["dual"] = dual_status(d["support"])
            d["status"] = "active"

    def view(self, session, k: int = 3) -> list[dict]:
        out = super().view(session, k)
        for o in out:
            d = self.dossiers[o["id"]]
            du = d.get("dual") or {}
            o["line"] = (f"[diagnosis: {du.get('diagnostic')}; repair: {du.get('repair')}"
                         + (f", lift {du['repair_lift']:+.2f}" if du.get("repair_lift") is not None else "") + "] "
                         + o["line"].split("] ", 1)[1])
        return out


def init_summaries(records: list[dict], bases: set[str]) -> list[dict]:
    return [episode_summary(r) for r in records if base_of(r["instance_id"]) in bases]


def load_records(paths: list[str]) -> list[dict]:
    out = []
    for p in paths:
        if os.path.exists(p):
            out += [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    return out


__all__ = ["CaseStore", "DualMemory", "repair_case", "agent_decision", "structures_at", "decision_structures", "final_tool",
           "screens", "dual_status", "struct_key"]
