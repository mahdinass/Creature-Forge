"""Nemotron roles in the Hypothesis-as-Simulation (HaS) scientist (phase 3). The model never holds the beliefs: the deterministic
belief engine (belief_engine.Episode) weighs every hypothesis by simulation against plant data. Nemotron contributes
  * PROPOSER     executable hypotheses: 1-2 primitives of the generic deviation DSL (hidden_plant.PRIMITIVES) with a mechanism,
                 causal chain and the signature it expects, written from the evidence, the engine's posterior and its residuals;
  * EXPERIMENTER the next plant experiment, chosen among the engine's candidates (whose EIG it sees), with a predictive
                 distribution (quantiles) for a fixed panel registered BEFORE the experiment runs;
  * ENGINEER     the repair strategy: which tools to try in which order, and its probability that the result passes.
Arms (docs/HAS_SCIENTIST.md): A3h uses the proposer only; A3hx adds the experimenter; A3 adds the engineer.

Contracts as in scientist.py: strict JSON schemas with enumerated ids; replies are parsed -> schema -> DSL validation (rejected
with a reason, never clipped); one repair call per invalid reply, counted; a SCRIPTED_MOCK run (fixture/transport) is labelled
and never counted as LIVE; every record is checked for secrets (fail closed). The prompts name no benchmark family.
"""
from __future__ import annotations

import copy
import json
from typing import Sequence

from . import director as dr
from . import hidden_plant as hp
from .forge_ai import ModelCall, parse_reply
from .inference_ledger import Caps, InferenceLedger
from .investigation import SCRIPTED_MODEL, new_investigation_id
from .nebius import contains_secret

VERSION = "has_scientist_v1"
MAX_HYPOTHESES = 4
TEXT_MAX = 1200
TOOLS = ("posture", "timing", "feedback", "stride", "placement", "foot_length", "torso_mass", "torque_limit", "foot_friction",
         "leg_length")
PANEL = {"observe": ("n_walking", "time_upright", "pitch_mean", "step_freq_hz", "slip_fraction"),
         "weigh": ("mass_kg", "com_x_m")}
QUANTILES = ("q05", "q25", "q50", "q75", "q95")
ALL_TARGETS = sorted({t for s in hp.PRIMITIVES.values() for t in s["targets"]})
ALL_PARAMS = sorted({p for s in hp.PRIMITIVES.values() for p in s["params"]})
SUMMARY_KEYS = ("time_upright", "pitch_mean", "com_vx_mean", "step_freq_hz", "step_length_over_L", "slip_fraction",
                "double_support_fraction", "capture_margin_over_L_mean", "saturation_frac_hip", "saturation_frac_knee",
                "saturation_frac_ankle", "friction_utilisation_p95", "fall_direction")


def _dsl_doc() -> str:
    lines = []
    for kind, s in hp.PRIMITIVES.items():
        params = ", ".join(f"{n} in [{lo:g}, {hi:g}]" for n, (lo, hi) in s["params"].items())
        lines.append(f"- {kind} (targets: {', '.join(s['targets'])}; {params}): {s['doc']}")
    return "\n".join(lines)


SYSTEM = f"""You are the hypothesis author and engineer of a physics laboratory that repairs a failing two-legged walking robot.

The robot was built from a nominal DESIGN (body and a 17-parameter walking controller) that walked reliably. The real robot now
fails. Something about the real robot differs from its design (damage, wear, mis-calibration, environment); nobody knows what.
You never see the real robot's parameters. You see measurements of how it behaves.

A deterministic belief engine does the inference. Every hypothesis you write is EXECUTED: the engine simulates the design with
your hypothesised deviation on exactly the same test seeds and compares the simulation with the measurements, so a hypothesis
earns weight only if it reproduces the data. The engine also holds its own generic hypotheses. Write hypotheses that are
physically motivated and that the current leading hypotheses cannot explain (look at the residuals: measured minus predicted,
in noise units, for the engine's best hypothesis). Revising a poorly fitting hypothesis is as useful as proposing a new one.

A hypothesis is 1 or 2 primitives of this deviation language (real robot = design + deviation):
{_dsl_doc()}

Sign conventions: pitch > 0 means the torso leans forward (nose down). fall_direction +1 = fell forward, -1 = backward.
x is forward. Measurements are medians over test seeds unless stated.

Reply with ONE JSON object that follows the response schema exactly. No prose outside the JSON."""


def _num(v) -> str:
    return "n/a" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v))


def _median(vals):
    v = sorted(x for x in vals if x is not None)
    return None if not v else (v[len(v) // 2] if len(v) % 2 else 0.5 * (v[len(v) // 2 - 1] + v[len(v) // 2]))


def experiment_lines(state: dict) -> list[str]:
    out = []
    for e in state.get("experiments", []):
        if e["kind"] == "weigh":
            m = e["measured"]
            out.append(f"{e['id']}: weigh test -> total mass {m['mass_kg']:.3f} kg, centre of mass {m['com_x_m'] * 100:+.1f} cm "
                       "forward of the hip")
            continue
        feats = e.get("features") or {}
        walk = sum(1 for f in feats.values() if f.get("walking"))
        med = {k: _median([f.get(k) for f in feats.values()]) for k in SUMMARY_KEYS}
        what = {"observe": "walk the current design", "floor": f"walk on a test floor with friction x{e.get('friction_mult')}",
                "counterfactual": "walk a modified design"}.get(e["kind"], e["kind"])
        out.append(f"{e['id']}: {what}: walking {walk}/{len(feats)}; " + ", ".join(f"{k} {_num(v)}" for k, v in med.items()))
    return out


class HasNemotron(dr.NemotronDirector):
    """One instance per investigation. `roles` selects which roles are active: {"propose"} (A3h), {"propose", "choose"} (A3hx),
    {"propose", "choose", "engineer"} (A3)."""

    def __init__(self, *, roles=("propose", "choose", "engineer"), source: str | None = None, profile: str = "default",
                 ledger: InferenceLedger | None = None, investigation_id: str | None = None, transport=None,
                 fixture: Sequence | None = None, max_requests: int = 24, max_total_tokens: int = 600_000, config=None,
                 design: dict | None = None):
        src = source or ("scripted" if fixture is not None or transport is not None else "live")
        if src == "scripted" and ledger is None:
            import tempfile
            from pathlib import Path
            ledger = InferenceLedger(Path(tempfile.mkdtemp(prefix="cf_has_")) / "scripted_inference_ledger.jsonl",
                                     prices={SCRIPTED_MODEL: (0.0, 0.0)},
                                     caps=Caps(inv_max_requests=max_requests, inv_max_tokens=max_total_tokens))
        super().__init__(mode=src, profile=profile, ledger=ledger, investigation_id=investigation_id or new_investigation_id(),
                         transport=transport, fixture=fixture, max_requests=max_requests, max_total_tokens=max_total_tokens,
                         config=config, evidence_mode="full", prompt_version="v2")
        self.roles = set(roles)
        self.system = SYSTEM
        self.design = design or {}
        self.log: list[dict] = []          # one entry per role call: inputs summary, parsed output, status
        self.predictions: list[dict] = []  # registered before the experiment runs

    # ------------------------------------------------------------------ shared
    def _design_lines(self) -> list[str]:
        b = self.design.get("body") or {}
        from .walk_opt import ALL_NAMES
        v = self.design.get("vector") or []
        return ["DESIGN body: " + ", ".join(f"{k} {_num(b[k])}" for k in ("torso_mass", "thigh_length", "shank_length",
                                                                         "foot_length", "foot_friction", "torque_limit",
                                                                         "leg_density") if k in b),
                "DESIGN controller: " + ", ".join(f"{n} {x:.4g}" for n, x in zip(ALL_NAMES, v))]

    def _state_lines(self, state: dict) -> list[str]:
        lines = ["EXPERIMENTS SO FAR:", *experiment_lines(state), "", "ENGINE POSTERIOR (top hypotheses, weight):"]
        lines += [f"  {p['w']:.3f}  {p['pid']}  [{p['source']}]" for p in state.get("posterior", [])[:8]]
        res = state.get("residuals_of_map") or {}
        if res:
            lines += ["", "RESIDUALS of the leading hypothesis (measured minus predicted, noise units; |r| > 1 is unexplained):"]
            for eid, r in res.items():
                big = {k: v for k, v in r.items() if abs(v) > 0.5}
                lines.append(f"  {eid}: " + (", ".join(f"{k} {v:+.2f}" for k, v in big.items()) or "all within 0.5"))
        lines += [f"", f"Plant budget left: {state.get('plant_remaining')} rollouts; simulation budget left: "
                       f"{state.get('twin_remaining')} rollouts."]
        return lines

    def _call(self, role: str, task_lines: list[str], schema: dict, validate) -> dict:
        user = "\n".join([*self._design_lines(), "", *task_lines])
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": user}]
        dec = self._ask_role(role, messages, schema, validate)
        self.log.append({"role": role, "status": dec["status"], "calls": dec["calls"], "parsed": dec.get("parsed"),
                         "errors": dec["validation_errors"], "first_attempt_errors": dec["first_attempt_errors"]})
        return dec

    def _ask_role(self, role: str, messages: list, schema: dict, validate) -> dict:
        dec = {"calls": [], "parsed": None, "first_attempt_errors": [], "validation_errors": [], "status": "ok"}

        def assess(call: ModelCall):
            try:
                reply = parse_reply(call.content)
            except ValueError as e:
                return None, [str(e)], None
            errs, out = validate(reply)
            return reply, errs, out

        call, idx = self._send(messages, schema, f"has_{role}", f"has_{role}")
        dec["calls"].append(idx)
        if not call.ok:
            dec.update(status="model_failed", validation_errors=[self._clean(call.error or "no content")])
            return dec
        reply, errs, out = assess(call)
        if errs:
            dec["first_attempt_errors"] = [self._clean(e) for e in errs]
            call2, idx2 = self._send(self._repair_messages(messages, call, errs), schema, f"has_{role}", "has_repair")
            dec["calls"].append(idx2)
            if not call2.ok:
                dec.update(status="repair_failed", validation_errors=dec["first_attempt_errors"])
                return dec
            reply, errs, out = assess(call2)
        dec["parsed"] = reply
        if errs:
            dec.update(status="invalid", validation_errors=[self._clean(e) for e in errs])
            return dec
        dec["out"] = out
        return dec

    # ------------------------------------------------------------------ proposer
    @staticmethod
    def propose_schema() -> dict:
        prim = {"type": "object", "additionalProperties": False, "required": ["kind", "target", "params"],
                "properties": {"kind": {"type": "string", "enum": sorted(hp.PRIMITIVES)},
                               "target": {"type": "string", "enum": ALL_TARGETS},
                               "params": {"type": "array", "minItems": 1, "maxItems": 2, "items": {
                                   "type": "object", "additionalProperties": False, "required": ["name", "value"],
                                   "properties": {"name": {"type": "string", "enum": ALL_PARAMS}, "value": {"type": "number"}}}}}}
        hyp = {"type": "object", "additionalProperties": False,
               "required": ["mechanism", "causal_chain", "expected_signature", "primitives"],
               "properties": {"mechanism": {"type": "string"}, "causal_chain": {"type": "string"},
                              "expected_signature": {"type": "string"},
                              "primitives": {"type": "array", "minItems": 1, "maxItems": 2, "items": prim}}}
        return {"type": "object", "additionalProperties": False, "required": ["reading", "hypotheses"],
                "properties": {"reading": {"type": "string"},
                               "hypotheses": {"type": "array", "minItems": 0, "maxItems": MAX_HYPOTHESES, "items": hyp}}}

    @staticmethod
    def to_deviation(h: dict) -> list[dict]:
        prims = []
        for p in h["primitives"]:
            names = [q["name"] for q in p["params"]]
            if len(set(names)) != len(names):
                raise hp.DeviationError(f"{p['kind']}: duplicate parameter names {names}")
            prims.append({"kind": p["kind"], "target": p["target"], "params": {q["name"]: q["value"] for q in p["params"]}})
        return hp.validate_deviation(prims)

    def _validate_propose(self, reply):
        errs, devs = [], []
        if not isinstance(reply, dict) or not isinstance(reply.get("hypotheses"), list):
            return ["reply must be an object with a 'hypotheses' list"], None
        for i, h in enumerate(reply["hypotheses"][:MAX_HYPOTHESES]):
            for k in ("mechanism", "causal_chain", "expected_signature"):
                if not isinstance(h.get(k), str) or len(h[k]) > TEXT_MAX:
                    errs.append(f"hypotheses[{i}].{k} must be a string of at most {TEXT_MAX} characters")
            try:
                devs.append(self.to_deviation(h))
            except (hp.DeviationError, KeyError, TypeError) as exc:
                errs.append(f"hypotheses[{i}]: {exc}")
        return errs, devs

    def propose(self, state: dict) -> list[list[dict]]:
        """Episode.proposer: returns validated deviations (possibly empty)."""
        if "propose" not in self.roles:
            return []
        task = self._state_lines(state) + ["", f"TASK: propose up to {MAX_HYPOTHESES} hypotheses (new, or revisions of poorly "
                                                "fitting ones) that could explain the measurements. Give parameter values you "
                                                "believe; the engine refines magnitudes. Start with `reading`: what the newest "
                                                "measurement shows physically."]
        dec = self._call("propose", task, self.propose_schema(), self._validate_propose)
        return dec.get("out") or []

    # ------------------------------------------------------------------ experimenter
    def choose(self, scored: list, state: dict) -> dict:
        """Episode.diagnose(choose=...): scored = [(eig_per_rollout, eig, candidate)]. Falls back to the engine's best on failure
        (recorded)."""
        cands = [c for _, _, c in scored]
        if "choose" not in self.roles:
            return cands[0]
        ids = [c["id"] for c in cands]
        quants = sorted({q for v in PANEL.values() for q in v})
        schema = {"type": "object", "additionalProperties": False, "required": ["reading", "choice", "why", "predictions"],
                  "properties": {"reading": {"type": "string"}, "choice": {"type": "string", "enum": ids},
                                 "why": {"type": "string"},
                                 "predictions": {"type": "array", "maxItems": 7, "items": {
                                     "type": "object", "additionalProperties": False, "required": ["quantity", *QUANTILES],
                                     "properties": {"quantity": {"type": "string", "enum": quants},
                                                    **{q: {"type": "number"} for q in QUANTILES}}}}}}
        lines = self._state_lines(state) + ["", "CANDIDATE EXPERIMENTS (engine's expected information gain about the hypotheses, "
                                                 "per plant rollout; you may disagree):"]
        for r, g, c in scored:
            lines.append(f"  {c['id']}: cost {c['cost']} rollouts, EIG {g:.3f} nats ({r:.4f}/rollout)")
        lines += ["", "TASK: choose ONE experiment. Then register your predictive distribution (5/25/50/75/95 % quantiles) of "
                      f"what it will measure: for walking experiments the quantities {', '.join(PANEL['observe'])} "
                      "(n_walking = number of walking seeds out of 4; others are medians); for the weigh test "
                      f"{', '.join(PANEL['weigh'])}. Quantiles must be non-decreasing."]

        def validate(reply):
            errs = []
            if reply.get("choice") not in ids:
                errs.append(f"choice must be one of {ids}")
            pick = next((c for c in cands if c["id"] == reply.get("choice")), None)
            want = PANEL["weigh"] if pick and pick["kind"] == "weigh" else PANEL["observe"]
            preds = reply.get("predictions") or []
            got = [p.get("quantity") for p in preds]
            for q in want:
                if q not in got:
                    errs.append(f"missing prediction for {q}")
            for p in preds:
                qs = [p.get(k) for k in QUANTILES]
                if not all(isinstance(x, (int, float)) for x in qs) or any(b < a for a, b in zip(qs, qs[1:])):
                    errs.append(f"prediction for {p.get('quantity')}: quantiles must be numbers, non-decreasing")
            return errs, pick
        dec = self._call("choose", lines, schema, validate)
        pick = dec.get("out")
        if pick is None:
            self.log[-1]["fallback"] = "engine_best"
            return cands[0]
        self.predictions.append({"experiment": pick["id"], "registered_before_run": True,
                                 "predictions": copy.deepcopy(dec["parsed"]["predictions"])})
        return pick

    # ------------------------------------------------------------------ engineer
    def engineer(self, state: dict, tool_ranking: list[dict]) -> dict:
        """-> {"tool_order": [...], "p_pass": float} or {} (engine default) on failure / inactive role."""
        if "engineer" not in self.roles:
            return {}
        schema = {"type": "object", "additionalProperties": False, "required": ["reading", "tool_order", "p_pass", "why"],
                  "properties": {"reading": {"type": "string"},
                                 "tool_order": {"type": "array", "minItems": 1, "maxItems": 3,
                                                "items": {"type": "string", "enum": list(TOOLS)}},
                                 "p_pass": {"type": "number"}, "why": {"type": "string"}}}
        lines = self._state_lines(state) + ["", "REPAIR TOOLS (each lets an optimiser change one subsystem of the DESIGN; the "
                                                 "engine's quick simulation screen under the leading hypotheses scored them):"]
        lines += [f"  {r['tool']}: screen score {r['score']:.3f} (best probe edit {r['probe']})" for r in tool_ranking]
        lines += ["", "TASK: choose the order in which to try up to 3 tools (the first is optimised in simulation under the "
                      "leading hypothesis, then checked on the real robot), and your probability (0-1) that the final design "
                      "passes the independent verification: walking on >= 80 % of 24 fresh 10 s trials and of 24 fresh 20 s "
                      "trials, clearly better than the failing robot."]

        def validate(reply):
            errs = []
            order = reply.get("tool_order") or []
            if len(set(order)) != len(order):
                errs.append("tool_order must not repeat a tool")
            p = reply.get("p_pass")
            if not isinstance(p, (int, float)) or not 0.0 <= p <= 1.0:
                errs.append("p_pass must be a number in [0, 1]")
            return errs, {"tool_order": list(order), "p_pass": p}
        dec = self._call("engineer", lines, schema, validate)
        return dec.get("out") or {}

    # ------------------------------------------------------------------ record
    def record(self) -> dict:
        rec = {"version": VERSION, "provenance": self.provenance, "model": self.cfg.model, "roles": sorted(self.roles),
               "investigation_id": self.investigation_id, "system_prompt": self.system, "log": self.log,
               "predictions": self.predictions, "calls": self.calls,
               "cost_usd": round(sum(c.get("cost_usd") or 0.0 for c in self.calls), 6),
               "tokens": {"prompt": sum((c.get("usage") or {}).get("prompt_tokens", 0) for c in self.calls),
                          "completion": sum((c.get("usage") or {}).get("completion_tokens", 0) for c in self.calls)}}
        if contains_secret(json.dumps(rec), self.api_key):
            raise RuntimeError("secret detected in the HaS record (fail closed)")
        return rec
