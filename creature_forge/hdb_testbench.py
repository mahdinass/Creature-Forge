"""Test-side Hidden-Damage Bench builder for the registered study E-1 (docs/E1_PROTOCOL.md). Bench builder only: never imported
by agent-facing code (belief_engine, scientist_has, hdb_policies, hdb_workbench; guarded by tests/test_e1.py).

It composes the frozen HDB v2 definitions without changing them (docs/HDB_SPEC.md):
- dev families (hdb_bench.FAMILY_SPECS) and the sealed held-out families (hdb_heldout.HELDOUT_FAMILY_SPECS) share one
  threshold rule: bisection on the gap-free plant, BISECT_STEPS steps on the variant's own check seeds (= hdb_bench.threshold,
  generalised to the union of specs);
- singles use strength MULTS x s*, capped at the variant's maximum (= hdb_bench.make_instance_v2);
- sealed compositions use each component at COMPOSITION_FRACTIONS x its own threshold on the base (hdb_heldout docstring);
- every instance carries the frozen per-instance reality gap and campaign-hdb-v1 seeds; eligibility is hdb_bench.check_eligibility.

Sampling (physics only; no arm, oracle or verification result is ever read): each stratum's candidates are put in a fixed
pseudo-random order (sha256 of the registered seed), strata are visited round robin, and a candidate is accepted iff it is
eligible and its base has room under the per-base caps. Physics may be evaluated for candidates that end up skipped by a cap;
acceptance depends only on the fixed order and on deterministic physics, so the sample does not depend on batching.
"""
from __future__ import annotations

import hashlib

from . import hdb_bench as hb
from . import hdb_heldout as hh
from . import hidden_plant as hp

VERSION = "hdb_v2_testbench_e1"
SPECS: dict[str, dict] = {**hb.FAMILY_SPECS, **hh.HELDOUT_FAMILY_SPECS}
if len(SPECS) != len(hb.FAMILY_SPECS) + len(hh.HELDOUT_FAMILY_SPECS):
    raise RuntimeError("dev and held-out family names overlap")


def variant_max(base: dict, family: str, variant: str) -> float:
    if family in hb.FAMILY_SPECS:
        return hb.variant_max(base, family, variant)
    v = SPECS[family]["variants"][variant]
    if v["max"] is None:
        raise ValueError(f"held-out variant {family}/{variant} has no maximum")
    return v["max"]


def threshold(base: dict, family: str, variant: str, pool=None) -> dict:
    """hdb_bench.threshold over SPECS (identical algorithm, seeds and output schema)."""
    smax = variant_max(base, family, variant)
    seeds = hb.instance_seeds(base["base_id"], f"{family}{variant}", -1)["check"]
    make = SPECS[family]["variants"][variant]["make"]

    def walking(s):
        rows = hp.walk_seeds({"deviation": make(s, base)}, base["body"], base["vector"], seeds, pool=pool)
        return int(sum(1 for r in rows if r.get("ok") and r["walking"]))
    trace = []
    w = walking(smax)
    trace.append((smax, w))
    if w > hb.FAIL_MAX_WALKING:
        return {"base_id": base["base_id"], "family": family, "variant": variant, "s_star": None, "s_max": smax,
                "trace": trace, "reason": "the nominal design still walks at the strongest allowed fault",
                "rollouts": hb.CHECK_N * len(trace)}
    lo, hi = 0.0, smax
    for _ in range(hb.BISECT_STEPS):
        mid = 0.5 * (lo + hi)
        w = walking(mid)
        trace.append((mid, w))
        if w <= hb.FAIL_MAX_WALKING:
            hi = mid
        else:
            lo = mid
    return {"base_id": base["base_id"], "family": family, "variant": variant, "s_star": hi, "s_max": smax, "trace": trace,
            "rollouts": hb.CHECK_N * len(trace)}


def th_key(base_id: str, family: str, variant: str) -> str:
    return f"{base_id}|{family}|{variant}"


# ------------------------------------------------------------------------------------------------------------------ candidates
def comp_family(comp: tuple) -> str:
    a, va, b, vb = comp
    return f"heldcomp:{a}{('.' + va) if va else ''}+{b}{('.' + vb) if vb else ''}"


def strata() -> dict[str, dict]:
    """Stratum name -> {"kind": single|comp, ...}. Singles: one stratum per family (all variants x MULTS). Compositions: one
    stratum per sealed pair (both fractions)."""
    out = {f: {"kind": "single", "family": f, "heldout": f in hh.HELDOUT_FAMILY_SPECS} for f in SPECS}
    for comp in hh.COMPOSITIONS:
        out[comp_family(comp)] = {"kind": "comp", "comp": comp, "heldout": True}
    return out


def candidates(stratum: str, bases: list[dict], seed: int) -> list[dict]:
    """Every (base, variant, multiple) or (base, fraction) candidate of a stratum, in the registered pseudo-random order."""
    st = strata()[stratum]
    out = []
    for b in bases:
        if st["kind"] == "single":
            for sev, (variant, mult) in enumerate(severities(st["family"])):
                out.append({"stratum": stratum, "base_id": b["base_id"], "family": st["family"], "severity": sev,
                            "variant": variant, "mult": mult})
        else:
            for sev, frac in enumerate(hh.COMPOSITION_FRACTIONS):
                out.append({"stratum": stratum, "base_id": b["base_id"], "family": comp_family(st["comp"]), "severity": sev,
                            "comp": list(st["comp"]), "mult": frac})
    return sorted(out, key=lambda c: hashlib.sha256(f"{seed}:{c['stratum']}:{c['base_id']}:{c['severity']}".encode()).hexdigest())


def severities(family: str) -> list[tuple[str, float]]:
    return [(v, m) for v in SPECS[family]["variants"] for m in hb.MULTS]


def needed_thresholds(cand: dict) -> list[tuple[str, str]]:
    if "comp" in cand:
        a, va, b, vb = cand["comp"]
        return [(a, va), (b, vb)]
    return [(cand["family"], cand["variant"])]


# ------------------------------------------------------------------------------------------------------------------ instances
def make_instance(base: dict, cand: dict, thresholds: dict, *, gap: bool = True) -> dict | None:
    """The hidden instance record for a candidate (before eligibility); None when a needed threshold does not exist or a single's
    multiple exceeds the variant's maximum strength (the same rules as hdb_bench.make_instance_v2 / hdb_devcomp)."""
    devs, s_star, strength = [], None, None
    for fam, var in needed_thresholds(cand):
        th = thresholds.get(th_key(base["base_id"], fam, var))
        if not th or th.get("s_star") is None:
            return None
        if "comp" in cand:
            devs += SPECS[fam]["variants"][var]["make"](cand["mult"] * th["s_star"], base)
        else:
            s = cand["mult"] * th["s_star"]
            if s > th["s_max"] + 1e-12:
                return None
            devs += SPECS[fam]["variants"][var]["make"](s, base)
            s_star, strength = th["s_star"], s
    fam = cand["family"]
    key = hb.instance_key(base["base_id"], fam, cand["severity"])
    seeds = hb.instance_seeds(base["base_id"], fam, cand["severity"])
    hb.assert_disjoint(seeds)
    plant = {"deviation": devs, "gap": hb.reality_gap(key) if gap else []}
    spec = SPECS.get(fam)
    return {"version": VERSION, "instance_id": key, "base_id": base["base_id"], "family": fam, "stratum": cand["stratum"],
            "pair": spec["pair"] if spec else "HC", "split": "test",
            "heldout": fam in hh.HELDOUT_FAMILY_SPECS or "comp" in cand, "severity": int(cand["severity"]),
            "variant": cand.get("variant", ""), "strength": strength if strength is not None else cand["mult"],
            "mult": cand["mult"], "s_star": s_star, "plant": hp.normalize_plant(plant),
            "robot": {"body": dict(base["body"]), "vector": [float(x) for x in base["vector"]]}, "seeds": seeds}


def evaluate_candidate(base: dict, cand: dict, thresholds: dict) -> dict:
    """Physics for one candidate (inline, for a pool worker): missing thresholds, the instance and its eligibility.
    Returns {"thresholds": {key: rec}, "instance": inst-with-eligibility | None}."""
    new = {}
    for fam, var in needed_thresholds(cand):
        k = th_key(base["base_id"], fam, var)
        if k not in thresholds:
            new[k] = threshold(base, fam, var)
    inst = make_instance(base, cand, {**thresholds, **new})
    return {"thresholds": new, "instance": None if inst is None else hb.check_eligibility(inst)}


def cand_id(c: dict) -> str:
    return f"{c['stratum']}|{c['base_id']}|{c['severity']}"


class Sampler:
    """Round-robin stratified sampler with per-base caps. Call `next_needed(k)` for up to k candidate ids whose physics must be
    evaluated before the sampler can advance, feed results with `feed`, repeat until `done`."""

    def __init__(self, ordered: dict[str, list[dict]], quotas: dict[str, int], *, per_base: int, per_base_family: int):
        if set(ordered) != set(quotas):
            raise ValueError("ordered candidates and quotas must cover the same strata")
        self.ordered, self.quotas = ordered, dict(quotas)
        self.per_base, self.per_base_family = int(per_base), int(per_base_family)
        self.pos = {s: 0 for s in ordered}
        self.accepted: dict[str, list[dict]] = {s: [] for s in ordered}
        self.base_n: dict[str, int] = {}
        self.base_fam_n: dict[tuple, int] = {}
        self.results: dict[str, dict] = {}
        self.log: list[dict] = []
        self.names = list(ordered)          # registered stratum order (dict insertion order)
        self.turn = 0                       # index into names of the stratum whose turn it is

    def _room(self, c: dict) -> bool:
        return (self.base_n.get(c["base_id"], 0) < self.per_base
                and self.base_fam_n.get((c["base_id"], c["stratum"]), 0) < self.per_base_family)

    def _is_active(self, s: str) -> bool:
        return len(self.accepted[s]) < self.quotas[s] and self.pos[s] < len(self.ordered[s])

    def _active(self) -> list[str]:
        return [s for s in self.names if self._is_active(s)]

    def advance(self) -> None:
        """Strict round robin: strata take turns in registered order; on its turn a stratum skips cap-blocked candidates and then
        decides its head (accept if eligible, else reject). If the head's physics is unknown, everything waits, so the decision
        sequence never depends on evaluation timing."""
        while True:
            act = self._active()
            if not act:
                return
            n = len(self.names)
            s = next(self.names[(self.turn + j) % n] for j in range(n) if self._is_active(self.names[(self.turn + j) % n]))
            while self.pos[s] < len(self.ordered[s]) and not self._room(self.ordered[s][self.pos[s]]):
                self.log.append({"cand": cand_id(self.ordered[s][self.pos[s]]), "decision": "skip_cap"})
                self.pos[s] += 1
            if self.pos[s] >= len(self.ordered[s]):
                self.turn = (self.names.index(s) + 1) % n
                continue
            c = self.ordered[s][self.pos[s]]
            r = self.results.get(cand_id(c))
            if r is None:
                self.turn = self.names.index(s)
                return
            inst = r["instance"]
            if inst is not None and inst["eligible"]:
                self.accepted[s].append(inst)
                self.base_n[c["base_id"]] = self.base_n.get(c["base_id"], 0) + 1
                self.base_fam_n[(c["base_id"], s)] = self.base_fam_n.get((c["base_id"], s), 0) + 1
                self.log.append({"cand": cand_id(c), "decision": "accept", "instance_id": inst["instance_id"]})
            else:
                why = "no_instance" if inst is None else ("ineligible: " + str(inst["reason"]))
                self.log.append({"cand": cand_id(c), "decision": "reject", "why": why})
            self.pos[s] += 1
            self.turn = (self.names.index(s) + 1) % n

    def next_needed(self, k: int) -> list[dict]:
        """Up to k not-yet-evaluated candidates, taken round robin from the head of each active stratum (lookahead). Candidates
        currently blocked by a cap are not requested."""
        out, seen = [], set()
        act = self._active()
        depth = 0
        while len(out) < k and any(self.pos[s] + depth < len(self.ordered[s]) for s in act):
            for s in act:
                i = self.pos[s] + depth
                if i >= len(self.ordered[s]):
                    continue
                c = self.ordered[s][i]
                cid = cand_id(c)
                if cid in self.results or cid in seen or not self._room(c):   # caps only tighten: blocked stays blocked
                    continue
                out.append(c)
                seen.add(cid)
                if len(out) >= k:
                    break
            depth += 1
        return out

    def feed(self, cid: str, result: dict) -> None:
        self.results[cid] = result
        self.advance()

    @property
    def done(self) -> bool:
        return not self._active()

    def summary(self) -> dict:
        return {s: {"quota": self.quotas[s], "accepted": len(self.accepted[s]), "examined": self.pos[s],
                    "candidates": len(self.ordered[s])} for s in self.ordered}
