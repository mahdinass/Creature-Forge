"""Experience bank for the Nemotron scientist: Level A (episodic memory) and Level B (mechanism cards).

Purpose. The scientist consumes memory through ONE interface, `memory.retrieve(obs_evidence, features) -> [{"id", "kind", "text"}]`
(`MemoryAdapter` here). Level A stores one compact record per finished investigation of a TRAINING instance and retrieves the nearest ones
(kNN on a standardised observation signature plus body features). Level B groups training episodes into cards: per-group signature
conditions, verified per-tool repair rates and counter-examples. Pure Python + numpy: deterministic, no network, no MuJoCo.

Trust boundaries (physics-integrity).
- NO LABEL LEAKAGE. Nothing derived from the injected fault name, severity, matching tool, `diagnosis.injected_category`, the
  scientist's diagnosis-vs-injected comparison, the instance id or the base creature name is stored, hashed into readable text or
  returned. Ids are opaque (`EP-<8 hex of sha256(instance_id|policy)>`, `CARD-<n>`); the instance is kept only as a salted-free opaque
  `instance_key` hash used to deduplicate. The scientist's own hypothesis texts are model outputs and are kept as written.
- Allowed supervision: robot features, the observation, what a policy did and measured, the verified outcome status, and the measured
  repair matrix of TRAINING instances. The caller is responsible for adding ONLY training instances (never held-out ones) to a bank.
- Cards state measured counts, never new physics. `status` is computed deterministically; `principle` is a factual sentence until
  Nemotron rephrases it (`principle_prompt` / `set_principle`, provenance recorded); `established_physics` stays None unless filled.
- Hints (`applicability_hint`) come only from the distance relative to the bank's typical nearest-neighbour distance; they are not
  decisions. The scientist still has to assess each item (applies / needs_adaptation / test_first / does_not_apply).
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np

# Chosen from physics_probe.PROBE_DOCS (medians of the initial observation) plus body features. cp_ahead_of_front_edge_over_L_end is
# omitted on purpose: in the pilot data it equals -capture_margin_over_L_end exactly, so it would double-weight one quantity.
OBS_KEYS = ("fall_direction", "time_upright", "pitch_end", "pitch_rate_end", "com_vx_end", "com_ahead_of_cop_over_L_end",
            "capture_margin_over_L_end", "step_freq_norm", "step_length_over_L", "swing_peak_clearance_min_over_L", "sat_max",
            "slip_fraction", "max_friction_utilisation", "angmom_norm_end")
FEATURE_KEYS = ("foot_to_leg", "torso_frac", "tau_ratio", "friction")
SIGNATURE_KEYS = OBS_KEYS + FEATURE_KEYS
SAT_KEYS = ("saturation_frac_hip", "saturation_frac_knee", "saturation_frac_ankle")
REPAIR_THRESHOLD = 0.75        # a tool "repairs" a robot if it walks on >= 75% of the check seeds
HEURISTIC_SUPPORT, HEURISTIC_RATE = 3, 0.7
MAX_TEXT = 700
G = 9.81


# ------------------------------------------------------------------------------------------------------- helpers
def _num(v) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _r(v, n: int = 3):
    """Round to n significant digits (None stays None)."""
    v = _num(v)
    return None if v is None else float(f"{v:.{n}g}")


def _s(v) -> str:
    """Signed 3-significant-digit number as text."""
    return f"{_r(v):+g}" if _num(v) is not None else "n/a"


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: max(0, n - 3)].rstrip() + "..."


def _opaque(prefix: str, *parts: str) -> str:
    return f"{prefix}-" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:8]


def compute_signature(median: dict, features: dict) -> dict | None:
    """Selected, dimensionless signature of an observation; values None when unavailable. None if there is no observation at all."""
    med = {k: _num(v) for k, v in (median or {}).items()}
    med = {k: v for k, v in med.items() if v is not None}
    if not med:
        return None
    feats = features or {}
    L = med.get("leg_length_m") or _num(feats.get("L"))
    sig: dict = {k: med.get(k) for k in OBS_KEYS}
    f = med.get("step_freq_hz")
    sig["step_freq_norm"] = f / math.sqrt(G / L) if (f is not None and L and L > 0) else None
    sats = [med[k] for k in SAT_KEYS if k in med]
    sig["sat_max"] = max(sats) if sats else None
    for k in FEATURE_KEYS:
        sig[k] = _num(feats.get(k))
    return {k: _r(sig[k], 6) for k in SIGNATURE_KEYS}


class Norm:
    """Mean/std per signature key fitted on the non-missing values of a set of signatures."""

    def __init__(self, sigs: list[dict]):
        self.mean, self.std = {}, {}
        for k in SIGNATURE_KEYS:
            v = np.array([s[k] for s in sigs if s.get(k) is not None], dtype=float)
            self.mean[k] = float(v.mean()) if len(v) else 0.0
            sd = float(v.std()) if len(v) > 1 else 0.0
            self.std[k] = sd if sd > 1e-9 else 1.0

    def vec(self, sig: dict) -> tuple[np.ndarray, list[str]]:
        """Standardised vector; missing values are imputed at the mean (z = 0) and listed."""
        z, missing = np.zeros(len(SIGNATURE_KEYS)), []
        for i, k in enumerate(SIGNATURE_KEYS):
            v = _num(sig.get(k))
            if v is None:
                missing.append(k)
            else:
                z[i] = (v - self.mean[k]) / self.std[k]
        return z, missing

    def to_dict(self) -> dict:
        return {k: [self.mean[k], self.std[k]] for k in SIGNATURE_KEYS}

    @classmethod
    def from_dict(cls, d: dict) -> "Norm":
        n = cls([])
        for k in SIGNATURE_KEYS:
            n.mean[k], n.std[k] = d[k]
        return n


def _hint(dist: float, typical: float | None, missing: list[str]) -> str:
    """Purely distance-based wording; not a decision."""
    if typical is None or typical <= 0:
        base = f"distance {_r(dist)}, no typical nearest-neighbour distance available"
    else:
        label = "close" if dist <= typical else "moderate" if dist <= 2 * typical else "far"
        base = f"{label} (distance {_r(dist)}, typical {_r(typical)})"
    return base + (f"; {len(missing)} of {len(SIGNATURE_KEYS)} signature values missing in the query" if missing else "")


# ------------------------------------------------------------------------------------------------ Level A: episodes
def _top_changes(quantities: dict, k: int = 4) -> list[list]:
    """The k largest changes in units of the quantity's noise tolerance (|z| >= 1 preferred; at least 3 kept when any exist)."""
    rows = []
    for q, x in sorted((quantities or {}).items()):
        d, tol = _num(x.get("delta")), _num(x.get("tolerance"))
        if d is None or not tol or tol <= 0 or q in ("leg_length_m", "n_swing_phases", "fall_direction"):
            continue
        rows.append((abs(d / tol), q, d / tol))
    rows.sort(key=lambda t: (-t[0], t[1]))
    big = [r for r in rows[:k] if r[0] >= 1.0]
    return [[q, _r(z)] for _, q, z in (big or rows[:3])]


def episode_from_record(rec: dict, instance: dict | None = None) -> dict:
    """Compact, label-free episode from a ce_eval episode record (any policy) and, optionally, its (training) instance record."""
    pol = str(rec.get("policy"))
    pr = rec.get("policy_record") or {}
    iid = str(rec.get("instance_id", ""))
    inst = instance or {}
    feats = {k: _r(v, 6) for k, v in (inst.get("features") or {}).items() if _num(v) is not None}
    io = pr.get("initial_observation") or inst.get("initial_observation")
    sig = compute_signature(io.get("median"), feats) if isinstance(io, dict) else None
    exps: list[dict] = []
    for e in pr.get("experiments") or []:
        if e.get("kind") == "counterfactual" and e.get("status") == "ok" and isinstance(e.get("outcome"), dict):
            o = e["outcome"]
            exps.append({"kind": "counterfactual", "change": str(e.get("change")), "n_walking": [o.get("n_walking_base"), o.get("n_walking")],
                         "n_total": rec.get("n_obs"), "top_changes": _top_changes(o.get("quantities"))})
        elif e.get("kind") == "repair" and e.get("status") == "ok":
            exps.append({"kind": "repair", "tool": e.get("tool"), "budget": e.get("budget"),
                         "train_walking": [e.get("start_walking"), e.get("train_walking")], "n_train": e.get("n_train")})
    if not any(x["kind"] == "repair" for x in exps):      # non-scientist policies: repairs only, "after" count only
        exps += [{"kind": "repair", "tool": r.get("tool"), "budget": r.get("budget"), "train_walking": [None, r.get("train_walking")],
                  "n_train": rec.get("n_train")} for r in pr.get("repairs") or [] if r.get("ok")]
    hyps = []
    for hid, h in sorted((pr.get("hypotheses") or {}).items()):
        hist = [f"{x.get('status')}: {_clip(x.get('reason', ''), 60)}" for x in (h.get("history") or []) if x.get("reason") != "created"][-3:]
        hyps.append({"id": hid, "mechanism": _clip(h.get("mechanism", ""), 160), "status": h.get("status"), "reasons": hist})
    ver = rec.get("verification") or {}
    fin = pr.get("final") or {}
    matrix = inst.get("repair_matrix")
    return {"id": _opaque("EP", iid, pol), "instance_key": _opaque("IK", iid)[3:], "policy": pol, "features": feats, "signature": sig,
            "experiments": exps, "hypotheses": hyps, "outcome": {"status": ver.get("status"), "walking_frac": _r(ver.get("walking_frac"))},
            "explanation": _clip(fin["explanation"], 300) if fin.get("explanation") else None,
            "repair_matrix": {t: _r(v) for t, v in sorted(matrix.items())} if isinstance(matrix, dict) else None}


def _describe_signature(s: dict) -> str:
    parts = []
    fd = s.get("fall_direction")
    if fd is not None:
        # fall_direction is a median of per-seed +1 / -1 / 0, so 0 can mean mixed directions (not "no fall")
        word = "fell FORWARD" if fd > 0 else "fell BACKWARD" if fd < 0 else "median fall direction 0 (mixed or no falls)"
        parts.append(word + (f", upright {_r(s['time_upright'])} s" if s.get("time_upright") is not None else ""))
    for k, label in (("pitch_end", "end pitch {} rad"), ("capture_margin_over_L_end", "capture margin/L {}"),
                     ("com_vx_end", "end COM vx {} m/s"), ("step_freq_norm", "norm. step freq {}"), ("slip_fraction", "slip {}"),
                     ("sat_max", "max saturation {}")):
        if s.get(k) is not None:
            parts.append(label.format(_s(s[k]) if k in ("pitch_end", "capture_margin_over_L_end", "com_vx_end") else _r(s[k])))
    return ", ".join(parts) or "no observation summary"


def _episode_text(ep: dict, hint: str, budget: int = MAX_TEXT) -> str:
    """Most decision-relevant facts first (signature, measured repair matrix, verified outcome), then what was tried, so clipping to
    the budget drops the least important part."""
    seg = [f"Earlier robot, {hint}: {_describe_signature(ep['signature'] or {})}."]
    m = ep.get("repair_matrix")
    if m:
        ok = sorted(((v, t) for t, v in m.items() if v >= REPAIR_THRESHOLD), key=lambda t: (-t[0], t[1]))
        bad = sorted(t for t, v in m.items() if v < REPAIR_THRESHOLD)
        seg.append("Measured repair matrix (walking fraction on check seeds after a 160-rollout repair): repaired by "
                   + (", ".join(f"{t} {v:g}" for v, t in ok) or "no tool") + "; not by " + (", ".join(bad) or "none") + ".")
    if ep["outcome"].get("status"):
        seg.append(f"Verified outcome of that investigation: {ep['outcome']['status']}, walking fraction {ep['outcome']['walking_frac']}.")
    tried = []
    for x in ep["experiments"]:
        if x["kind"] == "counterfactual":
            ch = ", ".join(f"{q} {_s(z)}x tol" for q, z in x["top_changes"][:2])
            tried.append(f"{x['change']}: walking {x['n_walking'][0]}->{x['n_walking'][1]}" + (f" ({ch})" if ch else ""))
        else:
            a, b = x["train_walking"]
            tried.append(f"repair {x['tool']}: train walking {'?' if a is None else a}->{b}")
    if tried:
        seg.append("Measured experiments: " + "; ".join(tried) + ".")
    return _clip(" ".join(seg), budget)


class ExperienceBank:
    def __init__(self):
        self.episodes: dict[str, dict] = {}
        self._fit_ok = False

    # ---- store
    def add(self, episode: dict) -> None:
        """Idempotent on the episode id (a second add replaces the first)."""
        self.episodes[episode["id"]] = copy.deepcopy(episode)
        self._fit_ok = False

    def save(self, path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for ep in self.episodes.values():
                f.write(json.dumps(ep, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path) -> "ExperienceBank":
        bank = cls()
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    bank.add(json.loads(line))
        return bank

    # ---- fit
    def _fit(self) -> None:
        if self._fit_ok:
            return
        self._ids = [i for i, e in self.episodes.items() if e.get("signature")]
        sigs = [self.episodes[i]["signature"] for i in self._ids]
        self.norm = Norm(sigs)
        self._z = np.array([self.norm.vec(s)[0] for s in sigs]).reshape(len(sigs), len(SIGNATURE_KEYS))
        keys = [self.episodes[i]["instance_key"] for i in self._ids]
        nn = []
        for a in range(len(self._ids)):
            d = np.linalg.norm(self._z - self._z[a], axis=1)
            d = [d[b] for b in range(len(d)) if keys[b] != keys[a]]
            if d:
                nn.append(min(d))
        self.typical_nn = float(np.median(nn)) if nn else None
        self._fit_ok = True

    def _query(self, obs_evidence: dict, features: dict) -> tuple[np.ndarray, list[str]]:
        sig = compute_signature((obs_evidence or {}).get("median"), features) or {k: None for k in SIGNATURE_KEYS}
        return self.norm.vec(sig)

    def retrieve(self, obs_evidence: dict, features: dict, k: int = 3) -> list[dict]:
        self._fit()
        if not self._ids or k <= 0:
            return []
        q, missing = self._query(obs_evidence, features)
        d = np.linalg.norm(self._z - q, axis=1)
        order = sorted(range(len(self._ids)), key=lambda i: (round(float(d[i]), 12), self._ids[i]))
        out, seen = [], set()
        for i in order:                       # at most one episode per instance (the nearest)
            ep = self.episodes[self._ids[i]]
            if ep["instance_key"] in seen:
                continue
            seen.add(ep["instance_key"])
            hint = _hint(float(d[i]), self.typical_nn, missing)
            out.append({"id": ep["id"], "kind": "episode", "text": _episode_text(ep, hint), "distance": _r(d[i]),
                        "applicability_hint": hint})
            if len(out) >= k:
                break
        return out

    def item_provenance(self, item_id: str) -> dict:
        if item_id in self.episodes:
            return {"kind": "episode", "record": copy.deepcopy(self.episodes[item_id])}
        raise KeyError(item_id)

    def subset(self, exclude_groups=()) -> "ExperienceBank":
        """A new bank without the episodes whose opaque `group_key` (set by the builder, e.g. a hash of the base robot) is excluded:
        development evaluation retrieves only experience from OTHER morphologies than the robot under investigation."""
        ex = set(exclude_groups)
        b = ExperienceBank()
        for ep in self.episodes.values():
            if ep.get("group_key") not in ex:
                b.add(ep)
        return b


# --------------------------------------------------------------------------------------------- Level B: cards
def _agglomerate(z: np.ndarray, g: int) -> list[int]:
    """Deterministic average-linkage agglomerative clustering to g groups; returns labels 0..g-1 ordered by first member."""
    clusters = [[i] for i in range(len(z))]
    dm = np.linalg.norm(z[:, None, :] - z[None, :, :], axis=2)
    while len(clusters) > g:
        best = None
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                d = float(np.mean([dm[i, j] for i in clusters[a] for j in clusters[b]]))
                if best is None or d < best[0] - 1e-12:
                    best = (d, a, b)
        _, a, b = best
        clusters[a] = clusters[a] + clusters[b]
        del clusters[b]
    labels = [0] * len(z)
    for lab, members in enumerate(sorted(clusters, key=min)):
        for i in members:
            labels[i] = lab
    return labels


def n_groups(n: int, min_support: int) -> int:
    """Rule: g = round(sqrt(n / 2)), at least 1 and at most n // min_support (so groups can reach the minimum support)."""
    return max(1, min(int(round(math.sqrt(n / 2.0))), n // max(1, min_support)))


def build_cards(episodes: list[dict], min_support: int = 3, n_condition: int = 5) -> list[dict]:
    """Mechanism cards from TRAINING episodes that have a signature and a measured repair matrix (one episode per instance).

    Grouping: average-linkage agglomerative clustering on the standardised signature (norm fitted on the eligible episodes), cut at
    `n_groups` groups; groups smaller than `min_support` are dropped. Conditions: the `n_condition` keys with the smallest ratio of
    within-group to global spread. Status: `empirical heuristic` iff support >= 3 and best-tool repair rate > 0.7, else `hypothesis`.
    """
    pool: dict[str, dict] = {}
    for ep in sorted(episodes, key=lambda e: e["id"]):
        if ep.get("signature") and ep.get("repair_matrix"):
            pool.setdefault(ep["instance_key"], ep)
    eps = sorted(pool.values(), key=lambda e: e["id"])
    if len(eps) < max(1, min_support):
        return []
    norm = Norm([e["signature"] for e in eps])
    z = np.array([norm.vec(e["signature"])[0] for e in eps])
    labels = _agglomerate(z, n_groups(len(eps), min_support))
    cards = []
    for lab in sorted(set(labels)):
        idx = [i for i, l in enumerate(labels) if l == lab]
        if len(idx) < min_support:
            continue
        mem = [eps[i] for i in idx]
        cond = []
        for k in SIGNATURE_KEYS:
            allv = np.array([e["signature"][k] for e in eps if e["signature"].get(k) is not None], dtype=float)
            v = np.array([e["signature"][k] for e in mem if e["signature"].get(k) is not None], dtype=float)
            if len(v) < max(2, (len(mem) + 1) // 2) or len(allv) < 2 or allv.std() < 1e-9:
                continue
            cond.append((float(v.std() / allv.std()), SIGNATURE_KEYS.index(k), k, v))
        cond.sort(key=lambda t: (t[0], t[1]))
        condition = {k: {"min": _r(v.min()), "max": _r(v.max()), "median": _r(np.median(v)), "n_known": int(len(v))}
                     for _, _, k, v in cond[:n_condition]}
        centroid = {}
        for k in SIGNATURE_KEYS:
            v = [e["signature"][k] for e in mem if e["signature"].get(k) is not None]
            centroid[k] = _r(np.median(v), 6) if v else None
        tools = sorted({t for e in mem for t in e["repair_matrix"]})
        rates = {t: [sum(1 for e in mem if e["repair_matrix"].get(t, 0) >= REPAIR_THRESHOLD), sum(1 for e in mem if t in e["repair_matrix"])]
                 for t in tools}
        mean_wf = {t: float(np.mean([e["repair_matrix"][t] for e in mem if t in e["repair_matrix"]])) for t in tools}
        best = max(tools, key=lambda t: (rates[t][0] / max(1, rates[t][1]), mean_wf[t], [-ord(c) for c in t])) if tools else None
        cz = norm.vec(centroid)[0]
        counter = []
        for e in mem:
            if best and e["repair_matrix"].get(best, 1.0) < REPAIR_THRESHOLD:
                counter.append({"id": e["id"], "walking_frac": _r(e["repair_matrix"][best]),
                                "distance_to_centroid": _r(np.linalg.norm(norm.vec(e["signature"])[0] - cz))})
        counter.sort(key=lambda c: (c["distance_to_centroid"], c["id"]))
        rate = rates[best][0] / rates[best][1] if best and rates[best][1] else 0.0
        heuristic = len(mem) >= HEURISTIC_SUPPORT and rate > HEURISTIC_RATE
        card = {"id": f"CARD-{len(cards) + 1}", "support": len(mem), "members": [e["id"] for e in mem], "condition": condition,
                "centroid": centroid, "norm": norm.to_dict(), "best_tool": best, "tool_repair_rates": rates,
                "counterexamples": counter, "status": "empirical heuristic" if heuristic else "hypothesis",
                "principle": None, "principle_source": None, "established_physics": None}
        card["principle"], card["principle_source"] = _default_principle(card), {"source": "deterministic"}
        if not heuristic:
            card["validation_experiment"] = (
                f"On additional robots whose signature satisfies the condition, apply the {best} repair and measure the walking fraction on "
                f"fresh check seeds (>= {REPAIR_THRESHOLD:g} counts as repaired); this card is supported only if most of them are repaired, "
                f"and rejected if the counterexample pattern repeats.")
        cards.append(card)
    return cards


def _cond_text(card: dict, n: int = 5) -> str:
    return "; ".join(f"{k} in [{_s(c['min'])}, {_s(c['max'])}]" for k, c in list(card["condition"].items())[:n])


def _rates_text(card: dict) -> str:
    items = sorted(card["tool_repair_rates"].items(), key=lambda kv: (-kv[1][0] / max(1, kv[1][1]), kv[0]))
    return ", ".join(f"{t} {r}/{n}" for t, (r, n) in items[:4])


def _default_principle(card: dict) -> str:
    b = card["best_tool"]
    r, n = card["tool_repair_rates"][b] if b else (0, 0)
    return (f"In {card['support']} similar robots (conditions: {_cond_text(card, 3)}), {b} repaired {r}/{n}; "
            f"counterexamples {len(card['counterexamples'])}.")


def principle_prompt(card: dict) -> str:
    """Prompt for Nemotron to phrase the card's physical principle. No API call here; contains only measured card facts."""
    return (
        "You are phrasing a hypothesis about biped-robot locomotion physics from measured data. Facts about a group of similar robots:\n"
        f"- Support: {card['support']} robots. Condition on the observation signature: {_cond_text(card)}.\n"
        f"- Measured repair counts (repaired on >= {REPAIR_THRESHOLD:g} of check seeds / tried): {_rates_text(card)}.\n"
        f"- Counterexamples for the best tool ({card['best_tool']}): {len(card['counterexamples'])}.\n"
        f"- Status: {card['status']}.\n"
        "Write ONE or TWO sentences stating the physical mechanism that could explain why the best tool repairs these robots and under which "
        "conditions it should work. Do not claim a discovery; if the statement restates a textbook relation (e.g. capture point, friction "
        "cone, inverted pendulum) name that relation. Do not invent numbers. Reply as JSON: "
        '{"principle": "<text>", "established_physics": "<textbook relation or null>"}.')


def set_principle(card: dict, text: str, source: str, established_physics: str | None = None) -> dict:
    """Store a (model-written) principle with provenance; mutates and returns the card."""
    card["principle"] = _clip(text, 400)
    card["principle_source"] = {"source": str(source)}
    card["established_physics"] = _clip(established_physics, 200) if established_physics else None
    return card


def card_item(card: dict, hint: str | None = None, distance: float | None = None) -> dict:
    head = f"Mechanism card {card['id']} [{card['status']}, support {card['support']}]" + (f", {hint}" if hint else "") + ". "
    est = f" Textbook relation: {card['established_physics']}." if card.get("established_physics") else ""
    tail = (f" Counterexamples to {card['best_tool']}: {len(card['counterexamples'])}."
            + (" To validate: test the best tool on a new matching robot." if card["status"] == "hypothesis" else "") + est)
    body = f"Applies when: {_cond_text(card)}. Measured repairs: {_rates_text(card)}. {card['principle'] or ''}"
    text = _clip(head + _clip(body, MAX_TEXT - len(head) - len(tail)) + tail, MAX_TEXT)
    item = {"id": card["id"], "kind": "card", "text": text}
    if hint is not None:
        item.update({"distance": distance, "applicability_hint": hint})
    return item


# ------------------------------------------------------------------------------------------------------ adapter
class MemoryAdapter:
    """`.retrieve(obs_evidence, features)` for `Scientist.investigate(memory=...)`. Modes: episodes | cards | episodes+cards."""

    def __init__(self, bank: ExperienceBank, cards: list[dict], k_episodes: int = 2, k_cards: int = 1, mode: str = "episodes+cards"):
        if mode not in ("episodes", "cards", "episodes+cards"):
            raise ValueError(f"unknown mode {mode!r}")
        self.bank, self.cards, self.k_episodes, self.k_cards, self.mode = bank, list(cards), k_episodes, k_cards, mode
        self._card_by_id = {c["id"]: c for c in self.cards}

    def _retrieve_cards(self, obs_evidence: dict, features: dict) -> list[dict]:
        sig = compute_signature((obs_evidence or {}).get("median"), features) or {k: None for k in SIGNATURE_KEYS}
        scored = []
        for c in self.cards:
            norm = Norm.from_dict(c["norm"])
            q, missing = norm.vec(sig)
            scored.append((float(np.linalg.norm(q - norm.vec(c["centroid"])[0])), c["id"], c, missing))
        scored.sort(key=lambda t: (round(t[0], 12), t[1]))
        # typical distance for cards: median member-to-centroid distance of the nearest card's own members is not stored; use the bank's
        # typical nearest-neighbour distance so the hint is on the same scale as the episode hints.
        self.bank._fit()
        out = []
        for d, _, c, missing in scored[: max(0, self.k_cards)]:
            out.append(card_item(c, _hint(d, self.bank.typical_nn, missing), _r(d)))
        return out

    def retrieve(self, obs_evidence: dict, features: dict) -> list[dict]:
        out = []
        if self.mode in ("cards", "episodes+cards"):
            out += self._retrieve_cards(obs_evidence, features)
        if self.mode in ("episodes", "episodes+cards"):
            out += self.bank.retrieve(obs_evidence, features, k=self.k_episodes)
        return out

    def item_provenance(self, item_id: str) -> dict:
        """Full underlying episode or card (card: plus its member episodes) for the frontend's link to evidence."""
        if item_id in self._card_by_id:
            c = copy.deepcopy(self._card_by_id[item_id])
            return {"kind": "card", "record": c,
                    "members": [copy.deepcopy(self.bank.episodes[m]) for m in c["members"] if m in self.bank.episodes]}
        return self.bank.item_provenance(item_id)
