"""Evidence-grounded experience memory for the HaS scientist (phase 3, Stage 2): mechanism dossiers.

A dossier is a principle the lab learned from earlier investigations, in an executable, checkable form:
  mechanism     an executable explanation template (DSL structure + parameter ranges). Applying it adds hypotheses to the belief,
                and the data can veto them like any other hypothesis.
  signature     deterministic predicates on measurements (experiment, feature, statistic, op, value). They are checked against
                the current robot's data before the dossier is trusted (applicability).
  fails_when    predicates under which the principle is known NOT to transfer.
  repair        the intervention the principle recommends (tools, optional start edits) and why it works (mechanism text).
  principle     "under these conditions this intervention helps because of this mechanism; it does not transfer when ...".
  support       deterministic statistics computed by code from the investigation records, never written by the model:
                signature precision/recall for the mechanism, verified outcomes of the recommended repair vs other repairs,
                uses and their outcomes (negative-transfer accounting).
  status        active | contested | retired, with a revision history.

Writing and revising dossiers is Nemotron's job (`Consolidator`). Counting is the code's job. Only DEV investigations feed the
memory. During an evaluation the memory is frozen.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from . import belief_engine as be
from . import hidden_plant as hp

VERSION = "has_memory_v1"
STATS = ("median", "walking_frac")
OPS = (">", "<")
MAX_PREDICATES = 4
FEATURE_NAMES = tuple(be.FEATURES)
EXTRA_FEATURES_ALL = FEATURE_NAMES + ("walking_frac", "mass_kg", "com_x_m", "mass_ratio", "mechanism_weight")
BELIEF = "belief"          # pseudo-experiment: {"mechanism_weight": the engine's posterior weight on the dossier's mechanism}


def struct_key(structure) -> str:
    return "+".join(f"{k}:{t}" for k, t in sorted(tuple(x) for x in structure)) or "nominal"


def with_belief(table: dict, belief: dict, mechanism) -> dict:
    """The measurement table plus the engine's current weight on `mechanism` (a dossier-specific pseudo-measurement)."""
    t = dict(table)
    t[BELIEF] = {"mechanism_weight": float((belief or {}).get(struct_key(mechanism), 0.0))}
    return t


# ------------------------------------------------------------------------------------------------ measurements and predicates
def exp_key(exp_id: str) -> str:
    """'X0:observe' -> 'observe'; 'X3:floor_test@x3' -> 'floor_test@x3'; 'X2:cf:freq@x0.85' -> 'cf:freq@x0.85'."""
    return exp_id.split(":", 1)[1] if ":" in exp_id else exp_id


def measurement_table(experiments: list[dict], design_mass: float | None = None) -> dict:
    """{experiment key: {feature: median over seeds, 'walking_frac': ...}} from engine experiment records (agent-visible).
    The weigh test also gives mass_ratio = measured mass / the DESIGN's mass (comparable across robots)."""
    out = {}
    for e in experiments:
        k = exp_key(e["id"])
        if e["kind"] == "weigh":
            out[k] = {"mass_kg": e["measured"]["mass_kg"], "com_x_m": e["measured"]["com_x_m"],
                      "mass_ratio": e["measured"]["mass_kg"] / design_mass if design_mass else None}
            continue
        if e["kind"] == "check":
            continue
        f = e.get("features") or {}
        row = {}
        for name in FEATURE_NAMES:
            vals = sorted(x.get(name) for x in f.values() if x.get(name) is not None)
            row[name] = None if not vals else (vals[len(vals) // 2] if len(vals) % 2 else 0.5 * (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]))
        row["walking_frac"] = (sum(1 for x in f.values() if x.get("walking")) / len(f)) if f else None
        out[k] = row
    return out


def validate_predicate(p: dict) -> list[str]:
    errs = []
    if not isinstance(p, dict):
        return ["predicate must be an object"]
    if not isinstance(p.get("experiment"), str) or not p["experiment"]:
        errs.append("predicate.experiment must name an experiment (observe, floor_test@x3, weigh_test, cf:..., belief)")
    elif (p["experiment"] == BELIEF) != (p.get("feature") == "mechanism_weight"):
        errs.append("the feature mechanism_weight goes with the experiment 'belief' (and only there)")
    feat = p.get("feature")
    if feat not in EXTRA_FEATURES_ALL:
        errs.append(f"predicate.feature {feat!r} unknown")
    if p.get("op") not in OPS:
        errs.append(f"predicate.op must be one of {OPS}")
    if not isinstance(p.get("value"), (int, float)) or isinstance(p.get("value"), bool) or not math.isfinite(p["value"]):
        errs.append("predicate.value must be a finite number")
    return errs


def eval_predicate(table: dict, p: dict) -> bool | None:
    """True / False, or None when the experiment was not run or the feature is undefined (not evaluable)."""
    row = table.get(p["experiment"])
    if row is None:
        return None
    v = row.get(p["feature"])
    if v is None:
        return None
    return v > p["value"] if p["op"] == ">" else v < p["value"]


def eval_predicates(table: dict, preds: list[dict]) -> dict:
    res = [eval_predicate(table, p) for p in preds]
    return {"true": sum(r is True for r in res), "false": sum(r is False for r in res), "unknown": sum(r is None for r in res),
            "n": len(res), "detail": res}


def pred_text(p: dict) -> str:
    return f"{p['experiment']}.{p['feature']} {p['op']} {p['value']:g}"


# ------------------------------------------------------------------------------------------------ episode summaries
def episode_summary(rec: dict) -> dict:
    """Deterministic facts of one dev investigation for the memory (from an hdb_vs_run record of any arm)."""
    eng = rec.get("engine") or {}
    exps = eng.get("experiments") or []
    agent = rec.get("agent") or {}
    tools = []
    sub_tool = None
    designs = {d["index"]: d for d in rec.get("designs") or []}
    sub = rec.get("submitted")
    if sub is None and agent.get("conclusion"):
        sub = agent["conclusion"].get("design")
    if sub is None and rec.get("repair"):
        sub = rec["repair"].get("design")
    for step in (rec.get("repair") or {}).get("log") or []:
        if step.get("tool"):
            tools.append(step["tool"])
    for t in agent.get("trace") or []:
        if t["action"].get("action") == "repair" and t["result"].get("ok"):
            tools.append(t["action"].get("tool"))
    if sub is not None and sub in designs:
        src = designs[sub].get("source", "")
        sub_tool = src.split(":")[-1] if (src.startswith("repair:") or src.startswith("twin:cma:")) else None
    led = eng.get("ledger") or rec.get("ledger") or {}
    dm = None
    if designs.get(0):
        from .hdb_bench import design_mass
        dm = design_mass(designs[0]["body"])
    return {"instance_id": rec["instance_id"], "base_id": rec["instance_id"].rsplit(":", 2)[0], "arm": rec.get("arm"),
            "family": rec.get("family"), "measurements": measurement_table(exps, dm), "n_experiments": max(0, len(exps) - 1),
            "map_structure": rec.get("map_structure"), "map_mass": rec.get("map_mass"),
            "belief": {struct_key(x["structure"]): x["w"] for x in ((eng.get("history") or [{}])[-1].get("structures") or [])},
            "tools_tried": tools, "submitted_tool": sub_tool,
            "plant_used": led.get("used"), "twin_used": (led.get("twin") or {}).get("used"),
            # dev post-mortem (never available during an evaluated investigation)
            "outcome": (rec.get("verification") or {}).get("status"),
            "walking_frac": (rec.get("verification") or {}).get("walking_frac"),
            "true_structure": rec.get("injected_structure")}


def _structure(dossier: dict) -> list:
    return sorted([list(x) for x in dossier["mechanism"]["structure"]])


def compute_support(d: dict, summaries: list[dict]) -> dict:
    """Deterministic support statistics of a dossier on dev investigation summaries."""
    mech = _structure(d)
    sig = d.get("signature") or []
    fails = d.get("fails_when") or []
    matched, evaluable, mech_all = [], 0, 0
    for s in summaries:
        truth = sorted([list(x) for x in (s.get("true_structure") or [])])
        is_mech = truth == mech
        mech_all += is_mech
        table = with_belief(s["measurements"], s.get("belief"), mech)
        ev = eval_predicates(table, sig)
        if ev["unknown"] == ev["n"]:
            continue
        evaluable += 1
        fw = eval_predicates(table, fails)
        if ev["false"] == 0 and fw["true"] == 0:
            matched.append((s, is_mech))
    tools = set(d.get("repair", {}).get("tools") or [])
    rec_t = [s for s, _ in matched if s.get("submitted_tool") in tools]
    oth_t = [s for s, _ in matched if s.get("submitted_tool") not in tools]
    full = lambda xs: sum(1 for s in xs if s.get("outcome") == "FULL_RECOVERY")     # noqa: E731
    mech_matched = sum(m for _, m in matched)
    # magnitude coverage: do the true (dev post-mortem) parameters of this mechanism fall inside the dossier's ranges?
    cov_in = cov_n = 0
    rng = d["mechanism"].get("params") or {}
    for s in summaries:
        dev = s.get("true_deviation")
        if not dev or sorted([[p["kind"], p["target"]] for p in dev]) != mech or not rng:
            continue
        ok = True
        for p in dev:
            for name, v in p["params"].items():
                r = rng.get(f"{p['kind']}.{name}")
                if r is not None and not r[0] <= v <= r[1]:
                    ok = False
        cov_n += 1
        cov_in += ok
    return {"n_summaries": len(summaries), "evaluable": evaluable, "matched": len(matched),
            "matched_with_mechanism": mech_matched, "mechanism_total": mech_all,
            "precision": round(mech_matched / len(matched), 3) if matched else None,
            "recall": round(mech_matched / mech_all, 3) if mech_all else None,
            "recommended_repair": [full(rec_t), len(rec_t)], "other_repairs": [full(oth_t), len(oth_t)],
            "magnitude_coverage": [cov_in, cov_n]}


# ------------------------------------------------------------------------------------------------ dossier validation
def validate_dossier(d: dict) -> list[str]:
    from .scientist_has import TOOLS
    errs = []
    for k in ("title", "principle"):
        if not isinstance(d.get(k), str) or not d[k] or len(d[k]) > 1500:
            errs.append(f"{k} must be a non-empty string (<= 1500 chars)")
    m = d.get("mechanism") or {}
    st = m.get("structure")
    if not isinstance(st, list) or not 1 <= len(st) <= 2:
        errs.append("mechanism.structure must list 1-2 [kind, target] pairs")
    else:
        for x in st:
            if (not isinstance(x, list) or len(x) != 2 or x[0] not in hp.PRIMITIVES
                    or x[1] not in hp.PRIMITIVES[x[0]]["targets"]):
                errs.append(f"mechanism.structure entry {x!r} is not a DSL (kind, target)")
    pr = m.get("params") or {}
    if not isinstance(pr, dict):
        errs.append("mechanism.params must map 'kind.param' to [lo, hi]")
    else:
        for name, rng in pr.items():
            kind, _, pname = name.partition(".")
            if kind not in hp.PRIMITIVES or pname not in hp.PRIMITIVES[kind]["params"]:
                errs.append(f"mechanism.params key {name!r} must be '<kind>.<param>' of the DSL")
                continue
            lo, hi = hp.PRIMITIVES[kind]["params"][pname]
            if (not isinstance(rng, list) or len(rng) != 2 or not all(isinstance(v, (int, float)) for v in rng)
                    or not lo <= rng[0] <= rng[1] <= hi):
                errs.append(f"mechanism.params[{name}] must be [lo, hi] within [{lo}, {hi}]")
    for key in ("signature", "fails_when"):
        ps = d.get(key) or []
        if not isinstance(ps, list) or len(ps) > MAX_PREDICATES:
            errs.append(f"{key} must be a list of at most {MAX_PREDICATES} predicates")
            continue
        for p in ps:
            errs += [f"{key}: {e}" for e in validate_predicate(p)]
    if not d.get("signature"):
        errs.append("signature needs at least one predicate (a dossier must be checkable)")
    rep = d.get("repair") or {}
    if not rep.get("tools") or any(t not in TOOLS for t in rep["tools"]):
        errs.append(f"repair.tools must list tools from {list(TOOLS)}")
    if rep.get("start_edits"):
        from .eng_tools import parse_counterfactual
        try:
            parse_counterfactual(rep["start_edits"])
        except ValueError as exc:
            errs.append(f"repair.start_edits: {exc}")
    return errs


def mechanism_particles(d: dict, design_mass: float) -> list[list[dict]]:
    """The dossier's mechanism at low / mid / high magnitudes (parameters move together through their ranges)."""
    m = d["mechanism"]
    out = []
    for frac in (0.0, 0.5, 1.0):
        dev = []
        for kind, target in m["structure"]:
            params = {}
            for pname in hp.PRIMITIVES[kind]["params"]:
                rng = (m.get("params") or {}).get(f"{kind}.{pname}")
                if rng is None:
                    continue
                a, b = rng
                if a > 0 and b > 0:
                    v = math.exp(math.log(a) + frac * (math.log(b) - math.log(a)))
                else:
                    v = a + frac * (b - a)
                params[pname] = float(round(v, 6))
            if not params:
                continue
            dev.append({"kind": kind, "target": target, "params": params})
        try:
            out.append(hp.validate_deviation(dev))
        except hp.DeviationError:
            continue
    return out


# ------------------------------------------------------------------------------------------------ the memory
class Memory:
    def __init__(self, dossiers: list[dict] | None = None, *, frozen: bool = True):
        self.dossiers = {d["id"]: d for d in (dossiers or [])}
        self.frozen = frozen
        self.uses: list[dict] = []

    @classmethod
    def load(cls, path: str | Path, *, frozen: bool = True) -> "Memory":
        data = json.loads(Path(path).read_text("utf-8"))
        return cls(data["dossiers"], frozen=frozen)

    def save(self, path: str | Path, meta: dict | None = None) -> None:
        Path(path).write_text(json.dumps({"version": VERSION, "meta": meta or {}, "dossiers": list(self.dossiers.values())},
                                         indent=1), "utf-8")

    def get(self, did) -> dict | None:
        return self.dossiers.get(did) if isinstance(did, str) else None

    def active(self) -> list[dict]:
        return [d for d in self.dossiers.values() if d.get("status", "active") != "retired"]

    def applicability(self, d: dict, session) -> dict:
        belief = {struct_key(st): w for st, w in session.ep.structure_posterior()}
        table = with_belief(measurement_table(session.ep.experiments, session.ep.design_mass), belief,
                            d["mechanism"]["structure"])
        sig = eval_predicates(table, d.get("signature") or [])
        fw = eval_predicates(table, d.get("fails_when") or [])
        mech = sorted(tuple(x) for x in d["mechanism"]["structure"])
        w = sum(wt for s, wt in session.ep.structure_posterior() if sorted(s) == mech)
        return {"signature": sig, "fails_when": fw, "engine_weight": round(w, 4)}

    def view(self, session, k: int = 3) -> list[dict]:
        """Top-k dossiers by applicability to this robot, with their checks (shown every turn; recomputed as data arrive)."""
        rows = []
        for d in self.active():
            a = self.applicability(d, session)
            sig = a["signature"]
            ev = sig["true"] + sig["false"]
            score = (sig["true"] / ev if ev else 0.0) - 1.0 * (a["fails_when"]["true"] > 0)
            rows.append((score, d, a))
        rows.sort(key=lambda t: (-t[0], t[1]["id"]))
        out = []
        for score, d, a in rows[:k]:
            sig, fw, sup = a["signature"], a["fails_when"], d.get("support") or {}
            checks = "; ".join(f"{pred_text(p)}: {'yes' if r else ('no' if r is False else 'not measured')}"
                               for p, r in zip(d.get("signature") or [], sig["detail"]))
            warn = [pred_text(p) for p, r in zip(d.get("fails_when") or [], fw["detail"]) if r]
            rr, orr = sup.get("recommended_repair") or [0, 0], sup.get("other_repairs") or [0, 0]
            line = (f"[{d.get('status', 'active')}] {d['title']}. PRINCIPLE: {d['principle']} | MECHANISM "
                    f"{'+'.join(f'{a_}:{b_}' for a_, b_ in d['mechanism']['structure'])}; REPAIR {d['repair'].get('tools')}"
                    + (f" start {d['repair']['start_edits']}" if d['repair'].get('start_edits') else "")
                    + f" | APPLICABILITY here: signature {sig['true']}/{sig['n']} true ({checks})"
                    + (f"; DOES-NOT-TRANSFER condition holds: {warn}" if warn else "")
                    + f"; engine weight of its mechanism now {a['engine_weight']:.2f}"
                    + f" | EVIDENCE (dev): signature precision {sup.get('precision')} on {sup.get('matched')} matches; "
                      f"recommended repair verified {rr[0]}/{rr[1]} vs other repairs {orr[0]}/{orr[1]}")
            out.append({"id": d["id"], "line": line, "score": round(score, 3), "applicability": a})
        return out

    def retrieve(self, session) -> list[dict]:
        return self.view(session)

    def particles(self, did: str, design_mass: float):
        d = self.get(did)
        return None if d is None else mechanism_particles(d, design_mass)

    def note_use(self, did: str, session) -> None:
        self.uses.append({"dossier": did, "applicability": self.applicability(self.dossiers[did], session),
                          "turn": len(session.trace)})

    # -------------------------------------------------------------- learning (dev only)
    def refresh_support(self, summaries: list[dict]) -> None:
        if self.frozen:
            raise RuntimeError("memory is frozen (evaluation): no updates")
        for d in self.dossiers.values():
            old = d.get("support")
            d["support"] = compute_support(d, summaries)
            rr = d["support"]["recommended_repair"]
            orr = d["support"]["other_repairs"]
            prec = d["support"]["precision"]
            status = d.get("status", "active")
            # deterministic revision rules: a signature that rarely means the mechanism, or a recommended repair that verifies
            # worse than the alternatives on enough matched cases, makes the dossier contested (the consolidator revises it)
            if (prec is not None and d["support"]["matched"] >= 4 and prec < 0.4) or \
               (rr[1] >= 4 and orr[1] >= 4 and rr[0] / rr[1] + 0.15 < orr[0] / orr[1]):
                status = "contested"
            if d["support"]["matched"] >= 6 and prec is not None and prec < 0.2:
                status = "retired"
            if status != d.get("status", "active") or old != d["support"]:
                d.setdefault("history", []).append({"event": "support_refresh", "status": status,
                                                    "support": copy.deepcopy(d["support"])})
            d["status"] = status


# ------------------------------------------------------------------------------------------------ consolidation (Nemotron)
DIGEST_FEATURES = ("walking_frac", "time_upright", "fall_direction", "pitch_mean", "com_vx_mean", "step_freq_hz",
                   "step_length_over_L", "slip_fraction", "double_support_fraction", "capture_margin_over_L_mean",
                   "saturation_frac_hip", "saturation_frac_knee", "saturation_frac_ankle", "friction_utilisation_p95",
                   "mass_ratio", "com_x_m")


def _q(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    pick = lambda f: v[min(len(v) - 1, int(round(f * (len(v) - 1))))]     # noqa: E731
    return [round(pick(0.1), 4), round(pick(0.5), 4), round(pick(0.9), 4)]


def digest(summaries: list[dict], *, min_share: float = 0.3) -> list[str]:
    """Deterministic evidence digest for the consolidator, grouped by the dev post-mortem mechanism.
    Per experiment it gives the 10/50/90 % quantiles of each feature's median, and verified outcomes by submitted repair
    tool."""
    groups: dict[str, list] = {}
    for s in summaries:
        key = struct_key(s.get("true_structure") or [])
        groups.setdefault(key, []).append(s)
    L = []
    for key, ss in sorted(groups.items()):
        full = sum(s["outcome"] == "FULL_RECOVERY" for s in ss)
        hit = sum(1 for s in ss if s.get("map_structure") and struct_key(s["map_structure"]) == key)
        L.append(f"MECHANISM {key}: {len(ss)} dev investigations on {len({s['base_id'] for s in ss})} robots, "
                 f"verified recovery {full}/{len(ss)}; engine's leading explanation was this mechanism in {hit}/{len(ss)}")
        exps: dict[str, int] = {}
        for s in ss:
            for e in s["measurements"]:
                exps[e] = exps.get(e, 0) + 1
        for e, n in sorted(exps.items(), key=lambda t: (-t[1], t[0])):
            if n < max(2, min_share * len(ss)):
                continue
            parts = []
            for f in DIGEST_FEATURES:
                q = _q([s["measurements"].get(e, {}).get(f) for s in ss if e in s["measurements"]])
                if q is not None:
                    parts.append(f"{f} {q}")
            L.append(f"  {e} (n={n}): " + "; ".join(parts))
        L.append("  most distinctive vs all other mechanisms (experiment.feature: this mechanism 10/50/90 % | others "
                 "10/50/90 % | separation): " + "; ".join(contrasts(ss, [s for s in summaries if s not in ss])))
        tm = [p for s in ss for p in (s.get("true_deviation") or [])]
        if tm:
            names = sorted({(p["kind"], k) for p in tm for k in p["params"]})
            L.append("  true deviation magnitudes (post-mortem, 10/50/90 %): " + "; ".join(
                f"{kind}.{name} {_q([p['params'][name] for p in tm if p['kind'] == kind and name in p['params']])}"
                for kind, name in names))
        by_tool: dict[str, list] = {}
        for s in ss:
            by_tool.setdefault(s.get("submitted_tool") or "none", []).append(s["outcome"] == "FULL_RECOVERY")
        L.append("  submitted repair tool -> verified: " + ", ".join(f"{t} {sum(v)}/{len(v)}" for t, v in sorted(by_tool.items())))
    return L


def contrasts(group: list[dict], others: list[dict], k: int = 6) -> list[str]:
    """The k (experiment, feature) pairs whose medians separate this group from the others most (|median difference| over
    the pooled 10-90 % spread); experiments measured in at least 5 cases on both sides."""
    rows = []
    exps = {e for s in group for e in s["measurements"]}
    for e in sorted(exps):
        for f in DIGEST_FEATURES:
            a = [s["measurements"][e].get(f) for s in group if e in s["measurements"]]
            b = [s["measurements"][e].get(f) for s in others if e in s["measurements"]]
            a, b = [x for x in a if x is not None], [x for x in b if x is not None]
            if len(a) < 5 or len(b) < 5:
                continue
            qa, qb = _q(a), _q(b)
            spread = 0.5 * ((qa[2] - qa[0]) + (qb[2] - qb[0])) + 1e-9
            rows.append((abs(qa[1] - qb[1]) / spread, e, f, qa, qb))
    rows.sort(key=lambda t: -t[0])
    return [f"{e}.{f}: {qa} | {qb} | {sep:.2f}" for sep, e, f, qa, qb in rows[:k]]


CONSOLIDATOR_SYSTEM = """You are the knowledge curator of a physics laboratory that investigates and repairs failing two-legged
walking robots. From the lab's development investigations you write MECHANISM DOSSIERS: transferable engineering principles in a
checkable form, of the kind "under these measurable conditions, this intervention is likely to help because of this mechanism;
it will not transfer when these conditions are violated".

Rules:
- A dossier must be checkable. Its SIGNATURE is 1-4 predicates on measurements (experiment, feature, op, value) that should hold
  on a new robot with this mechanism and, ideally, not on robots with other mechanisms. Use the quantiles in the digest to choose
  thresholds that separate mechanisms. Experiments: observe (the failing design walking on 4 trials), floor_test@x3 (on a floor
  with 3x friction), weigh_test (mass_kg, com_x_m), or a design counterfactual id like cf:pitch_ref@+0.1R. Feature values are
  medians over trials; walking_frac is the fraction of trials walking. The pseudo-experiment `belief` with the feature
  mechanism_weight is the belief engine's posterior weight on the dossier's own mechanism (the engine identifies mechanisms
  by simulation far better than raw thresholds do), so a principle can read "once the engine believes mechanism X (weight
  > 0.5) and these measured conditions hold, use repair R"; the digest reports how often the engine's leading explanation
  matched each mechanism.
- FAILS_WHEN lists 0-4 predicates under which the principle should NOT be applied (known non-transfer conditions).
- MECHANISM is executable: 1-2 primitives of the deviation language with parameter ranges ([lo, hi] inside the DSL bounds),
  each named '<kind>.<param>'. The mechanism describes how the REAL robot DEVIATES from its design (e.g. weak actuators =
  actuator_strength factor below 1), never the repair. Use the post-mortem magnitudes in the digest for the ranges.
- Write one dossier for EACH mechanism with at least 8 investigations whose evidence allows a checkable signature. A
  signature may rely on a discriminating experiment (e.g. weigh_test.mass_ratio, floor_test@x3.walking_frac) that a new
  investigation would then run to check applicability.
- REPAIR names the tools that verified best for this mechanism and, optionally, start_edits (a counterfactual string such as
  pitch_ref@-0.1R) that a physically reasoned repair would start from ("" for none).
- The lab's code computes each dossier's support (signature precision/recall and verified outcomes); you will see it and revise.
- Do not write a dossier when the evidence is too thin; say so in `notes`.

Deviation language:
{dsl}

Reply with ONE JSON object following the schema."""


class Consolidator:
    """Nemotron writes and revises dossiers from deterministic evidence digests (dev only); the code counts their support."""

    def __init__(self, **kw):
        from .scientist_has import HasNemotron, _dsl_doc
        kw.setdefault("max_requests", 12)
        kw.setdefault("max_total_tokens", 400_000)
        self.n = HasNemotron(roles=("consolidate",), **kw)
        self.n.system = CONSOLIDATOR_SYSTEM.replace("{dsl}", _dsl_doc())

    @staticmethod
    def dossier_schema() -> dict:
        from .scientist_has import ALL_TARGETS, TOOLS
        pred = {"type": "object", "additionalProperties": False, "required": ["experiment", "feature", "op", "value"],
                "properties": {"experiment": {"type": "string"},
                               "feature": {"type": "string", "enum": list(EXTRA_FEATURES_ALL)},
                               "op": {"type": "string", "enum": list(OPS)}, "value": {"type": "number"}}}
        param = {"type": "object", "additionalProperties": False, "required": ["name", "lo", "hi"],
                 "properties": {"name": {"type": "string"}, "lo": {"type": "number"}, "hi": {"type": "number"}}}
        return {"type": "object", "additionalProperties": False,
                "required": ["title", "principle", "structure", "params", "signature", "fails_when", "tools", "start_edits"],
                "properties": {"title": {"type": "string"}, "principle": {"type": "string"},
                               "structure": {"type": "array", "minItems": 1, "maxItems": 2, "items": {
                                   "type": "object", "additionalProperties": False, "required": ["kind", "target"],
                                   "properties": {"kind": {"type": "string", "enum": sorted(hp.PRIMITIVES)},
                                                  "target": {"type": "string", "enum": ALL_TARGETS}}}},
                               "params": {"type": "array", "maxItems": 4, "items": param},
                               "signature": {"type": "array", "minItems": 1, "maxItems": MAX_PREDICATES, "items": pred},
                               "fails_when": {"type": "array", "maxItems": MAX_PREDICATES, "items": pred},
                               "tools": {"type": "array", "minItems": 1, "maxItems": 3,
                                         "items": {"type": "string", "enum": list(TOOLS)}},
                               "start_edits": {"type": "string"}}}

    @staticmethod
    def to_dossier(x: dict, did: str) -> dict:
        return {"id": did, "title": x["title"], "principle": x["principle"],
                "mechanism": {"structure": [[p["kind"], p["target"]] for p in x["structure"]],
                              "params": {p["name"]: [p["lo"], p["hi"]] for p in x.get("params") or []}},
                "signature": x["signature"], "fails_when": x.get("fails_when") or [],
                "repair": {"tools": x["tools"], "start_edits": x.get("start_edits") or None}, "status": "active", "history": []}

    def write(self, summaries: list[dict], memory: Memory) -> dict:
        """One call: new dossiers from the digest (existing dossiers are listed so they are not duplicated)."""
        existing = [f"{d['id']}: {d['title']} ({'+'.join(f'{a}:{b}' for a, b in d['mechanism']['structure'])})"
                    for d in memory.active()]
        schema = {"type": "object", "additionalProperties": False, "required": ["notes", "dossiers"],
                  "properties": {"notes": {"type": "string"},
                                 "dossiers": {"type": "array", "maxItems": 12, "items": self.dossier_schema()}}}
        start = len(memory.dossiers)

        def validate(reply):
            errs, out = [], []
            for i, x in enumerate(reply.get("dossiers") or []):
                try:
                    d = self.to_dossier(x, f"D{start + i + 1}")
                except (KeyError, TypeError) as exc:
                    errs.append(f"dossiers[{i}]: {exc}")
                    continue
                errs += [f"dossiers[{i}]: {e}" for e in validate_dossier(d)]
                out.append(d)
            return errs, out
        lines = ["EVIDENCE DIGEST (development investigations; quantiles 10/50/90 % over investigations):", *digest(summaries),
                 "", "EXISTING DOSSIERS:", *(existing or ["none"]), "",
                 "TASK: write dossiers for the mechanisms where the evidence supports a transferable, checkable principle."]
        dec = self.n._call("consolidate_write", lines, schema, validate)
        new = dec.get("out") or []
        for d in new:
            d["history"].append({"event": "created", "by": "nemotron"})
            memory.dossiers[d["id"]] = d
        return {"status": dec["status"], "created": [d["id"] for d in new], "notes": (dec.get("parsed") or {}).get("notes")}

    def revise(self, summaries: list[dict], memory: Memory) -> dict:
        """Show each dossier's deterministic support; Nemotron keeps, revises or retires it (evidence-based revision)."""
        rows = []
        for d in memory.dossiers.values():
            sup = d.get("support") or {}
            rows.append(f"{d['id']} [{d.get('status')}] {d['title']} | signature {[pred_text(p) for p in d['signature']]} "
                        f"fails_when {[pred_text(p) for p in d.get('fails_when') or []]} | mechanism {d['mechanism']} | "
                        f"repair {d['repair']} | SUPPORT: matched {sup.get('matched')} of {sup.get('evaluable')} evaluable; "
                        f"precision {sup.get('precision')}, recall {sup.get('recall')}; recommended repair verified "
                        f"{sup.get('recommended_repair')}, other repairs {sup.get('other_repairs')}; true magnitudes inside "
                        f"its ranges {sup.get('magnitude_coverage')}")
        ids = list(memory.dossiers) or ["none"]
        rev = {"type": "object", "additionalProperties": False, "required": ["id", "decision", "why"],
               "properties": {"id": {"type": "string", "enum": ids},
                              "decision": {"type": "string", "enum": ["keep", "revise", "retire"]}, "why": {"type": "string"},
                              "dossier": self.dossier_schema()}}
        schema = {"type": "object", "additionalProperties": False, "required": ["revisions", "new_dossiers"],
                  "properties": {"revisions": {"type": "array", "maxItems": 12, "items": rev},
                                 "new_dossiers": {"type": "array", "maxItems": 10, "items": self.dossier_schema()}}}
        start = len(memory.dossiers)

        def validate(reply):
            errs, out = [], []
            for i, r in enumerate(reply.get("revisions") or []):
                if r.get("id") not in memory.dossiers:
                    errs.append(f"revisions[{i}].id unknown")
                    continue
                if r.get("decision") == "revise":
                    if not r.get("dossier"):
                        errs.append(f"revisions[{i}]: revise needs `dossier`")
                        continue
                    d = self.to_dossier(r["dossier"], r["id"])
                    errs += [f"revisions[{i}]: {e}" for e in validate_dossier(d)]
                    out.append((r, d))
                else:
                    out.append((r, None))
            for i, x in enumerate(reply.get("new_dossiers") or []):
                d = self.to_dossier(x, f"D{start + i + 1}")
                errs += [f"new_dossiers[{i}]: {e}" for e in validate_dossier(d)]
                out.append(({"id": d["id"], "decision": "new"}, d))
            return errs, out
        lines = ["DOSSIERS WITH THEIR SUPPORT (computed by the lab's code on the development investigations):", *rows, "",
                 "EVIDENCE DIGEST:", *digest(summaries), "",
                 "TASK: for each dossier decide keep / revise / retire. Revise when the support shows the signature matches "
                 "other mechanisms (low precision), misses its mechanism (low recall), or the recommended repair verifies worse "
                 "than alternatives, or the true magnitudes fall outside its ranges. Retire a dossier the evidence contradicts. Add "
                 "new_dossiers for mechanisms with enough evidence that no active dossier covers."]
        dec = self.n._call("consolidate_revise", lines, schema, validate)
        changed = []
        for r, d in dec.get("out") or []:
            if r["decision"] == "new":
                d["history"].append({"event": "created", "by": "nemotron", "round": "revise"})
                memory.dossiers[d["id"]] = d
                changed.append(d["id"])
                continue
            old = memory.dossiers[r["id"]]
            if r["decision"] == "revise" and d is not None:
                d["history"] = old.get("history", []) + [{"event": "revised", "by": "nemotron", "why": r.get("why"),
                                                          "previous": {k: old[k] for k in ("signature", "fails_when", "mechanism",
                                                                                           "repair", "principle")}}]
                memory.dossiers[r["id"]] = d
                changed.append(r["id"])
            elif r["decision"] == "retire":
                old["status"] = "retired"
                old.setdefault("history", []).append({"event": "retired", "by": "nemotron", "why": r.get("why")})
                changed.append(r["id"])
        return {"status": dec["status"], "changed": changed}

    def record(self) -> dict:
        return self.n.record()
