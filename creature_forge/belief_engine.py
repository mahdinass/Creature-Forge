"""Belief engine (phase 3, HaS): deterministic simulation-based inference over hidden deviations, experiment choice, repair.

Particles are hypotheses (a DSL deviation: 1-2 `hidden_plant` primitives) with log-weights. The likelihood of plant data under
a particle comes from the TWIN: the nominal design simulated with the particle's deviation on the SAME seeds and conditions
(paired), compared feature by feature with a heavy-tailed (Student-t) noise model. Proposals come from
  * the generic library (`generic_particles`: every DSL kind and coarse target at a coarse magnitude grid) - arm A1,
  * external proposers (Nemotron, dossiers, a learned posterior), added with `add_particles` and tagged by source.
Experiments are chosen by expected information gain per plant rollout, estimated from twin predictions of the top particles.
Repair is posterior-robust: screen tools on the twin under the leading hypotheses, optimise the design on the twin, then check
it on the plant (robustness check) and fine-tune on the plant only if needed.

Everything is deterministic given the bench (seeds) and the proposals; every twin and plant call is ledgered by the bench.
The record (`Episode.record`) keeps particles, weights after every update and each experiment's twin predictions, so the
posterior can be replayed offline with different proposal sets (attribution, docs/HAS_SCIENTIST.md).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

import numpy as np

from . import hidden_plant as hp

VERSION = "belief_engine_v4"   # v2: warm-started plant optimisation with the remaining budget + selection by robustness evidence; v3: 4-level generic magnitudes, two-step refinement; v4: calibrated scales + seed-level contamination likelihood

# per-seed summary features in the likelihood and their noise scales (provisional; calibrated on dev, frozen before comparisons)
# v4 (dev noise calibration, scripts/hdb_noise_calibration.py, 175 dev instances, plant vs twin with the TRUE deviation): the
# residuals are ~0 on most seeds with heavy tails from occasional chaotic divergence that hits all features of a seed together
# (p95 |r|: walking 1.0, time_upright 1.3 s, step_freq 0.73 Hz, ankle saturation 0.20, friction use 0.25). Hence the seed-level
# contamination model below and wider scales where the measured tails exceeded the provisional ones.
FEATURES = {"walking": 0.35, "time_upright": 1.5, "fall_direction": 0.7, "pitch_mean": 0.04, "com_vx_mean": 0.08,
            "step_freq_hz": 0.4, "step_length_over_L": 0.03, "slip_fraction": 0.03, "double_support_fraction": 0.05,
            "capture_margin_over_L_mean": 0.02, "saturation_frac_hip": 0.05, "saturation_frac_knee": 0.05,
            "saturation_frac_ankle": 0.1, "friction_utilisation_p95": 0.12}
SEED_OUTLIER = 0.1           # probability that a seed diverged chaotically (all its features together)
OUTLIER_FEATURE_LOGP = -3.0  # uniform contamination: an outlier seed's features have a constant log-density each (bounded cost)
MISSING_PENALTY = 1.0        # nats when exactly one of observed/simulated is undefined (e.g. no steps before a fall)
NU = 3.0                     # Student-t degrees of freedom
WEIGH_SIGMA = {"mass_frac": 0.025, "com_x_m": 0.008}   # weigh-test noise incl. the reality gap (torso mass +-3 %)

# generic library: coarse magnitudes per kind (declared a priori from physical plausibility, identical for every arm)
GENERIC = {      # v3 (2026-10-18, dev): 4 log-spaced magnitudes per kind from small to large (v2 dev runs: threshold-level faults
    # are small, e.g. payloads of 1-15 % of body mass, and the v1/v2 coarse grid could not reach them)
    "segment_length": {"targets": ("feet", "legs", "shank_l", "shank_r", "thigh_l", "thigh_r"), "values": {"factor": (0.5, 0.7, 0.85, 1.2)}},
    "actuator_strength": {"targets": ("all", "left", "right", "hips", "knees", "ankles"), "values": {"factor": (0.2, 0.4, 0.6, 0.8)}},
    "joint_damping": {"targets": ("all", "left", "right", "hips", "knees", "ankles"), "values": {"factor": (3.0, 8.0, 20.0, 50.0)}},
    "torso_mass": {"targets": ("torso",), "values": {"factor": (1.15, 1.4, 1.8, 2.4)}},
    "payload": {"targets": ("torso",), "values": {"mass_frac": (0.04, 0.1, 0.25), "x_m": (-0.12, 0.0, 0.12)}},
    "contact_friction": {"targets": ("feet",), "values": {"factor": (0.15, 0.3, 0.5, 0.75)}},
    "gain_scale": {"targets": ("balance_feedback", "placement"), "values": {"factor": (0.1, 0.3, 0.6, 0.85)}},
    "sensor_delay": {"targets": ("pitch", "joints", "all"), "values": {"seconds": (0.01, 0.03, 0.06, 0.1)}},
    "sensor_bias": {"targets": ("pitch",), "values": {"rad": (-0.3, -0.15, -0.07, -0.03, 0.03, 0.07, 0.15, 0.3)}},
    "clock_scale": {"targets": ("clock",), "values": {"factor": (0.6, 0.8, 1.25, 1.6)}},
}
# candidate plant experiments (generic): design-parameter counterfactuals (one level each way) plus the condition tests
CANDIDATE_CFS = ("pitch_ref@+0.1R", "pitch_ref@-0.1R", "hip_bias@+0.1R", "hip_bias@-0.1R", "foot_length@x1.5",
                 "foot_length@x0.7", "torque_limit@x2", "freq@x0.85", "freq@x1.2", "balance_gain@x0.5",
                 "balance_gain@x2", "fp_kd@+0.2R", "foot_friction@x2", "torso_mass@x0.7")
# quick twin screen of each repair tool: a few edits along the tool's parameters
TOOL_PROBES = {"posture": ("pitch_ref@+0.1R", "pitch_ref@-0.1R", "hip_bias@+0.1R", "hip_bias@-0.1R"),
               "timing": ("freq@x0.85", "freq@x0.7", "duty@+0.1R"),
               "feedback": ("balance_gain@x2", "balance_gain@x0.5", "pitch_kp@x2", "pitch_kp@x0.5"),
               "stride": ("hip_amp@x0.7", "hip_amp@x1.2"),
               "placement": ("fp_kd@+0.2R", "fp_kv@+0.2R"),
               "foot_length": ("foot_length@x1.5", "foot_length@x2"),
               "torso_mass": ("torso_mass@x0.7", "torso_mass@x0.5"),
               "torque_limit": ("torque_limit@x2", "torque_limit@x3"),
               "foot_friction": ("foot_friction@x2", "foot_friction@x3"),
               "leg_length": ("leg_length@x0.85", "leg_length@x1.2")}


# generic manufacturing-tolerance prior for posterior-robust design (declared a priori; deliberately wider than, and independent
# of, the bench's sealed reality-gap generator): real robots differ from their designs by a few percent
TOLERANCE = {"torso_mass": (0.95, 1.05), "actuator_strength": (0.92, 1.08), "joint_damping": (0.7, 1.4),
             "contact_friction": (0.9, 1.1)}


def tolerance_draws(k: int, seed: int) -> list[list[dict]]:
    """k deterministic nuisance deviations from the tolerance prior (per-joint actuator draws)."""
    rng = np.random.default_rng(np.random.SeedSequence([int(seed) % (2 ** 32), 0x701]))
    out = []
    for _ in range(k):
        d = [{"kind": "torso_mass", "target": "torso", "params": {"factor": float(rng.uniform(*TOLERANCE["torso_mass"]))}},
             {"kind": "joint_damping", "target": "all", "params": {"factor": float(rng.uniform(*TOLERANCE["joint_damping"]))}},
             {"kind": "contact_friction", "target": "feet", "params": {"factor": float(rng.uniform(*TOLERANCE["contact_friction"]))}}]
        d += [{"kind": "actuator_strength", "target": j, "params": {"factor": float(rng.uniform(*TOLERANCE["actuator_strength"]))}}
              for j in hp.JOINTS]
        out.append(hp.validate_deviation(d))
    return out


def provisional_accept(ev: dict) -> bool:
    """Development stop rule until the calibrated mapping exists: 15/16 on the robust seeds."""
    return ev.get("robust16") is not None and ev["robust16"] >= 15


def mapped_p_full(model: dict, ev: dict) -> float | None:
    """P(full_recovery_v1 | visible evidence) from a dev-fitted map (scripts/hdb_stop_calibration.py fit)."""
    kind = model.get("kind")
    if kind == "isotonic_robust16":
        k = ev.get("robust16")
        return None if k is None else float(model["p"][int(k)])
    if kind == "logistic_robust16_stress4":
        x = [1.0]
        for f in model["features"]:
            v, n = ev.get(f), model["n_by_feature"][f]
            if v is None:
                return None
            x.append(math.log((v + 0.5) / (n - v + 0.5)))      # empirical logit, as in the fit
        z = sum(a * b for a, b in zip(model["w"], x))
        return 1.0 / (1.0 + math.exp(-z))
    raise ValueError(f"unsupported stopping model {kind!r}")


def calibrated_accept(model: dict, tau: float):
    """accept_fn from a dev-fitted mapping: accept iff mapped P(FULL) >= tau. Needs the evidence the map uses (the engine runs
    the 20 s stress test for promising candidates when the map uses it)."""
    mapped_p_full(model, {"robust16": 16, "stress4": 4})        # validates the model

    def accept(ev: dict) -> bool:
        p = mapped_p_full(model, ev)
        ev["p_full"] = p
        return p is not None and p >= tau
    accept.model, accept.tau, accept.needs_stress = model.get("fitted_on"), tau, "stress4" in model.get("features", [])
    return accept


def SPEND_ALL(ev: dict) -> bool:          # noqa: N802 - arm A1f: never accept early, spend the budget, select by evidence
    return False


# ---------------------------------------------------------------------------------------------------------
# features and likelihood
# ---------------------------------------------------------------------------------------------------------
def seed_features(row: dict) -> dict:
    out = {}
    for k in FEATURES:
        v = row.get(k)
        if k == "walking":
            v = 1.0 if row.get("walking") else 0.0
        out[k] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None
    return out


def obs_features(observation: dict) -> dict:
    """{seed: features} from an observe() output (per_seed rows carry their seed)."""
    return {int(r["seed"]): seed_features(r) for r in observation.get("per_seed", [])}


def _t_logpdf(r: float) -> float:
    return -0.5 * (NU + 1.0) * math.log1p(r * r / NU)


def _seed_terms(fo: dict, fs: dict) -> tuple[float, float]:
    """(inlier, outlier) log-densities of one seed's features, up to the same constant."""
    inl = out = 0.0
    for k, sd in FEATURES.items():
        a, b = fo.get(k), fs.get(k)
        if a is None and b is None:
            continue
        out += OUTLIER_FEATURE_LOGP
        if a is None or b is None:
            inl -= MISSING_PENALTY
            continue
        inl += _t_logpdf((a - b) / sd)
    return inl, out


def loglik(obs: dict, sim: dict) -> float:
    """Paired log-likelihood (up to a constant) of observed per-seed features given simulated ones, with a seed-level
    contamination model (v4): each seed is twin-consistent (Student-t per feature) or, with probability SEED_OUTLIER, a chaotic
    outlier with a constant density per feature (uniform contamination: one divergent seed costs a bounded amount). Seeds missing in either are skipped (they cost nothing and say nothing)."""
    total = 0.0
    li, lo = math.log1p(-SEED_OUTLIER), math.log(SEED_OUTLIER)
    for s, fo in obs.items():
        fs = sim.get(s)
        if fs is None:
            continue
        inl, out = _seed_terms(fo, fs)
        a, b = li + inl, lo + out
        m = max(a, b)
        total += m + math.log(math.exp(a - m) + math.exp(b - m))
    return total


def weigh_loglik(meas: dict, pred: dict, design_mass: float) -> float:
    r1 = (meas["mass_kg"] - pred["mass_kg"]) / (WEIGH_SIGMA["mass_frac"] * design_mass)
    r2 = (meas["com_x_m"] - pred["com_x_m"]) / WEIGH_SIGMA["com_x_m"]
    return _t_logpdf(r1) + _t_logpdf(r2)


def distance(a: dict, b: dict) -> float:
    """Squared standardised distance between two predicted per-seed feature sets (same seeds); for EIG."""
    d = 0.0
    for s, fa in a.items():
        fb = b.get(s)
        if fb is None:
            continue
        for k, sd in FEATURES.items():
            x, y = fa.get(k), fb.get(k)
            if x is None and y is None:
                continue
            if x is None or y is None:
                d += 2.0 * MISSING_PENALTY
                continue
            d += ((x - y) / sd) ** 2
    return d


# ---------------------------------------------------------------------------------------------------------
# particles
# ---------------------------------------------------------------------------------------------------------
@dataclass
class Particle:
    pid: str
    deviation: list
    source: str
    logw: float = 0.0
    loglik: float = 0.0
    seen: dict = field(default_factory=dict)       # experiment id -> twin prediction (features by seed, or weigh dict)

    @property
    def structure(self) -> tuple:
        return tuple(sorted((p["kind"], p["target"]) for p in self.deviation))

    def as_dict(self) -> dict:
        return {"pid": self.pid, "deviation": copy.deepcopy(self.deviation), "source": self.source,
                "structure": [list(x) for x in self.structure], "loglik": self.loglik}


def _pid(dev: list) -> str:
    parts = []
    for p in sorted(dev, key=lambda q: (q["kind"], q["target"])):
        vals = ",".join(f"{k}={v:.4g}" for k, v in sorted(p["params"].items()))
        parts.append(f"{p['kind']}:{p['target']}({vals})")
    return "+".join(parts) or "nominal"


def generic_particles(design_mass: float) -> list[list[dict]]:
    """The A1 proposal library: every generic (kind, target) at each coarse magnitude, plus the nominal hypothesis."""
    out = [[]]
    for kind, spec in GENERIC.items():
        for tgt in spec["targets"]:
            if kind == "payload":
                for f in spec["values"]["mass_frac"]:
                    for x in spec["values"]["x_m"]:
                        out.append([{"kind": kind, "target": tgt,
                                     "params": {"mass_kg": round(min(15.0, f * design_mass), 4), "x_m": x}}])
                continue
            (pname, vals), = spec["values"].items()
            for v in vals:
                out.append([{"kind": kind, "target": tgt, "params": {pname: v}}])
    return [hp.validate_deviation(d) for d in out]


def neighbours(dev: list, step: float = 0.35) -> list[list[dict]]:
    """Local refinements of a 1-primitive hypothesis: each parameter moved by +-step (log for factors, linear otherwise)."""
    if len(dev) != 1:
        return []
    p = dev[0]
    lo_hi = hp.PRIMITIVES[p["kind"]]["params"]
    out = []
    for name, v in p["params"].items():
        lo, hi = lo_hi[name]
        if name == "factor":
            cands = (v * math.exp(step), v * math.exp(-step))
        elif name == "mass_kg":
            cands = (v * math.exp(step), v * math.exp(-step))
        else:
            span = hi - lo
            cands = (v + 0.35 * step * span, v - 0.35 * step * span)
        for c in cands:
            if lo <= c <= hi and abs(c - v) > 1e-9:
                q = copy.deepcopy(p)
                q["params"][name] = float(round(c, 6))
                out.append([q])
    return [hp.validate_deviation(d) for d in out]


# ---------------------------------------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------------------------------------
class Episode:
    """One investigation by the engine on an HDBWorkbench. `proposer` (optional) is called with the engine's state summary and
    returns lists of deviations to add (Nemotron, a learned posterior, dossiers, or a SCRIPTED_MOCK)."""

    def __init__(self, bench, *, proposer=None, use_generic: bool = True, max_alive: int = 12, screen_seeds: int = 2,
                 diag_plant_budget: int = 120, eig_top: int = 6, refine_top: int = 3, settings: dict | None = None,
                 generic_kinds: tuple | None = None):
        self.b = bench
        self.generic_kinds = generic_kinds          # None = the whole generic library (smoke tests may restrict it)
        self.proposer = proposer
        self.use_generic = use_generic
        self.max_alive, self.screen_seeds, self.diag_budget = max_alive, screen_seeds, diag_plant_budget
        self.eig_top, self.refine_top = eig_top, refine_top
        self.settings = dict(settings or {})
        self.particles: dict[str, Particle] = {}
        self.experiments: list[dict] = []        # plant experiments with their observed features
        self.history: list[dict] = []            # posterior snapshots
        self.events: list[dict] = []
        self.design0 = bench.best_design()
        self.design_mass = float(__import__("creature_forge.hdb_workbench", fromlist=["static_mass_com"])
                                 .static_mass_com(None, self.design0["body"], design_only=True)["mass_kg"])

    # ------------------------------------------------------------ bookkeeping
    def _event(self, kind: str, **kw):
        self.events.append({"seq": len(self.events), "kind": kind, **kw})

    def posterior(self) -> list[tuple[Particle, float]]:
        ps = list(self.particles.values())
        if not ps:
            return []
        m = max(p.logw for p in ps)
        w = np.array([math.exp(p.logw - m) for p in ps])
        w /= w.sum()
        return sorted(zip(ps, w.tolist()), key=lambda t: -t[1])

    def structure_posterior(self) -> list[tuple[tuple, float]]:
        agg: dict[tuple, float] = {}
        for p, w in self.posterior():
            agg[p.structure] = agg.get(p.structure, 0.0) + w
        return sorted(agg.items(), key=lambda t: -t[1])

    def snapshot(self, label: str) -> None:
        self.history.append({"label": label, "plant_used": self.b.budget.used, "twin_used": self.b.twin.used,
                             "top": [{"pid": p.pid, "source": p.source, "w": round(w, 6)} for p, w in self.posterior()[:10]],
                             "structures": [{"structure": [list(x) for x in s], "w": round(w, 6)}
                                            for s, w in self.structure_posterior()[:8]]})

    # ------------------------------------------------------------ twin predictions for one experiment
    def _predict(self, p: Particle, exp: dict, *, n: int | None = None):
        """Twin prediction of experiment `exp` under particle p (cached per experiment id)."""
        key = exp["id"] if n is None else f"{exp['id']}#{n}"
        if key in p.seen:
            return p.seen[key]
        kind = exp["kind"]
        if kind == "weigh":
            pred = self.b.twin_weigh(p.deviation, exp["design"])
        else:
            seeds_n = n if n is not None else len(exp["seeds"])
            obs = self.b.twin_observe(p.deviation, exp["design"], role="obs", n=seeds_n,
                                      friction_mult=exp.get("friction_mult", 1.0), tag=f"{p.pid}|{exp['id']}")
            if obs is None:
                return None
            pred = obs_features(obs)
        p.seen[key] = pred
        return pred

    def _score(self, p: Particle, exp: dict, pred) -> float:
        if exp["kind"] == "weigh":
            return weigh_loglik(exp["measured"], pred, self.design_mass)
        return loglik(exp["features"], pred)

    def _update_particle(self, p: Particle) -> bool:
        """Bring p's log-likelihood up to date with every plant experiment. False if the twin budget ran out."""
        total = 0.0
        for exp in self.experiments:
            pred = self._predict(p, exp)
            if pred is None:
                return False
            total += self._score(p, exp, pred)
        p.loglik = total
        p.logw = total
        return True

    def add_particles(self, devs, source: str) -> list[str]:
        added = []
        for d in devs:
            try:
                dev = hp.validate_deviation(d)
            except hp.DeviationError as exc:
                self._event("proposal_rejected", source=source, reason=str(exc))
                continue
            pid = _pid(dev)
            if pid in self.particles:
                continue
            p = Particle(pid, dev, source)
            if not self._update_particle(p):
                self._event("twin_budget_exhausted", where="add_particles", pid=pid)
                break
            self.particles[pid] = p
            added.append(pid)
        return added

    def _screen_generic(self) -> None:
        """Generic library: screen every hypothesis on `screen_seeds` obs seeds of the first observation, keep the best
        `max_alive` for full evaluation (cost-aware; the screen counts against the twin budget)."""
        exp0 = self.experiments[0]
        sub = dict(exp0, id=exp0["id"] + "#screen", features={s: f for s, f in list(exp0["features"].items())[:self.screen_seeds]})
        scored = []
        for dev in generic_particles(self.design_mass):
            if self.generic_kinds is not None and dev and dev[0]["kind"] not in self.generic_kinds:
                continue
            p = Particle(_pid(dev), dev, "generic")
            pred = self._predict(p, sub, n=self.screen_seeds)
            if pred is None:
                self._event("twin_budget_exhausted", where="screen", pid=p.pid)
                break
            scored.append((loglik(sub["features"], pred), dev))
        scored.sort(key=lambda t: -t[0])
        self._event("generic_screen", n=len(scored), kept=[_pid(d) for _, d in scored[:self.max_alive]])
        self.add_particles([d for _, d in scored[:self.max_alive]], "generic")

    def refine(self) -> None:
        """Local parameter refinement around the best particle of each leading structure: a coarse step, then (after those
        are scored) a fine step around the new best (v3)."""
        for step in (0.35, 0.15):
            seen_struct = set()
            props = []
            for p, w in self.posterior():
                if p.structure in seen_struct:
                    continue
                seen_struct.add(p.structure)
                props += neighbours(p.deviation, step)
                if len(seen_struct) >= self.refine_top:
                    break
            self.add_particles(props, "refine")

    def prune(self) -> None:
        post = self.posterior()
        keep = {p.pid for p, w in post[:self.max_alive]} | {p.pid for p, w in post if w > 0.02}
        for pid in list(self.particles):
            if pid not in keep:
                del self.particles[pid]

    # ------------------------------------------------------------ plant experiments
    def _register(self, exp: dict) -> None:
        self.experiments.append(exp)
        for p in list(self.particles.values()):
            if not self._update_particle(p):
                self._event("twin_budget_exhausted", where="update", pid=p.pid)
                break

    def run_observe(self) -> dict:
        res = self.b.observe()
        d = self.b.best_design()
        exp = {"id": f"X{len(self.experiments)}:observe", "kind": "observe", "design": {"body": d["body"], "vector": d["vector"]},
               "seeds": list(self.b.obs_seeds), "features": obs_features(res["observation"]), "cost": self.b.n_obs}
        self._register(exp)
        return res

    def candidate_experiments(self) -> list[dict]:
        from .fault_bench import apply_changes
        from .eng_tools import parse_counterfactual
        d = self.b.best_design()
        base = {"body": d["body"], "vector": d["vector"]}
        out = [{"id": "floor_test@x3", "kind": "floor", "design": base, "friction_mult": 3.0, "cost": self.b.n_obs},
               {"id": "weigh_test", "kind": "weigh", "design": base, "cost": 1}]
        for cid in CANDIDATE_CFS:
            try:
                body, vec = apply_changes(base["body"], base["vector"], parse_counterfactual(cid))
            except Exception:   # noqa: BLE001 - unavailable for this design (bounds); not a candidate
                continue
            out.append({"id": f"cf:{cid}", "kind": "counterfactual", "cf": cid, "design": {"body": body, "vector": vec},
                        "cost": self.b.n_obs})
        done = {e["id"].split(":", 1)[1] for e in self.experiments if ":" in e["id"]}
        return [c for c in out if c["id"] not in done]

    def eig(self, cand: dict, top: list[tuple[Particle, float]]) -> float | None:
        """Expected information gain (nats) about the hypothesis among `top`, plug-in estimate from twin predictions on 2 seeds."""
        preds, ws = [], []
        probe = dict(cand, seeds=list(self.b.obs_seeds[:2]))
        for p, w in top:
            pred = self._predict(p, {**probe, "id": "eig:" + cand["id"]}, n=None if cand["kind"] == "weigh" else 2)
            if pred is None:
                return None
            preds.append(pred)
            ws.append(w)
        ws = np.array(ws) / sum(ws)
        if cand["kind"] == "weigh":
            def dist(a, b):
                return (((a["mass_kg"] - b["mass_kg"]) / (WEIGH_SIGMA["mass_frac"] * self.design_mass)) ** 2
                        + ((a["com_x_m"] - b["com_x_m"]) / WEIGH_SIGMA["com_x_m"]) ** 2)
        else:
            dist = distance
        total = 0.0
        for k in range(len(preds)):
            s = sum(ws[j] * math.exp(-0.5 * dist(preds[k], preds[j])) for j in range(len(preds)))
            total -= ws[k] * math.log(max(s, 1e-300))
        return float(total)

    def run_experiment(self, cand: dict) -> dict:
        kind = cand["kind"]
        if kind == "floor":
            res = self.b.floor_test(cand["friction_mult"])
            feats = obs_features(res["observation"]) if res.get("ok") else None
        elif kind == "weigh":
            res = self.b.weigh_test()
            feats = None
        else:
            res = self.b.counterfactual(cand["cf"])
            feats = obs_features(res["observation"]) if res.get("ok") else None
        if not res.get("ok"):
            self._event("experiment_refused", id=cand["id"], reason=res.get("refused"))
            return res
        exp = {"id": f"X{len(self.experiments)}:{cand['id']}", "kind": kind, "design": cand["design"],
               "seeds": list(self.b.obs_seeds), "cost": cand["cost"]}
        if kind == "floor":
            exp["friction_mult"] = cand["friction_mult"]
        if kind == "weigh":
            exp["measured"] = {"mass_kg": res["mass_kg"], "com_x_m": res["com_x_m"]}
        else:
            exp["features"] = feats
        self._register(exp)
        return res

    # ------------------------------------------------------------ diagnosis loop
    def diagnose(self, *, confident: float = 0.9, max_experiments: int = 6, choose=None) -> dict:
        """observe -> proposals -> (EIG experiment -> update -> refine)* until a structure holds `confident` mass, the diagnosis
        plant budget is spent or `max_experiments` ran. `choose(cands_with_eig, state)` lets an external experimenter pick."""
        self.run_observe()
        if self.use_generic:
            self._screen_generic()
        if self.proposer is not None:
            self.add_particles(self.proposer(self.state()), "proposer")
        self.refine()
        self.prune()
        self.snapshot("after_observation")
        for i in range(max_experiments):
            sp = self.structure_posterior()
            if sp and sp[0][1] >= confident:
                break
            if self.b.budget.used >= self.diag_budget:
                break
            top = self.posterior()[:self.eig_top]
            scored = []
            for c in self.candidate_experiments():
                g = self.eig(c, top)
                if g is None:
                    break
                scored.append((g / c["cost"], g, c))
            if not scored:
                break
            scored.sort(key=lambda t: -t[0])
            pick = choose(scored, self.state()) if choose else scored[0][2]
            self._event("experiment_chosen", id=pick["id"], by="external" if choose else "eig",
                        ranking=[{"id": c["id"], "eig": round(g, 4), "eig_per_rollout": round(r, 5)} for r, g, c in scored[:8]])
            self.run_experiment(pick)
            if self.proposer is not None:
                self.add_particles(self.proposer(self.state()), "proposer")
            self.refine()
            self.prune()
            self.snapshot(f"after_{pick['id']}")
        sp = self.structure_posterior()
        return {"map_structure": [list(x) for x in sp[0][0]] if sp else None, "map_mass": sp[0][1] if sp else 0.0,
                "map_particle": self.posterior()[0][0].as_dict() if self.particles else None}

    def state(self) -> dict:
        """Summary for external proposers/choosers: experiments run, leading hypotheses, unexplained residuals."""
        post = self.posterior()
        resid = {}
        if post and self.experiments:
            best = post[0][0]
            for exp in self.experiments:
                if exp["kind"] == "weigh":
                    pred = best.seen.get(exp["id"])
                    if pred:
                        resid[exp["id"]] = {"mass_kg": exp["measured"]["mass_kg"] - pred["mass_kg"],
                                            "com_x_m": exp["measured"]["com_x_m"] - pred["com_x_m"]}
                    continue
                pred = best.seen.get(exp["id"]) or {}
                r = {}
                for k, sd in FEATURES.items():
                    vals = [(fo.get(k), pred.get(s, {}).get(k)) for s, fo in exp["features"].items()]
                    z = [(a - b) / sd for a, b in vals if a is not None and b is not None]
                    if z:
                        r[k] = round(float(np.mean(z)), 3)
                resid[exp["id"]] = r
        return {"experiments": [{k: v for k, v in e.items() if k not in ("design",)} for e in self.experiments],
                "posterior": [{"pid": p.pid, "source": p.source, "w": round(w, 5)} for p, w in post[:10]],
                "residuals_of_map": resid, "plant_remaining": self.b.remaining, "twin_remaining": self.b.twin.remaining}

    # ------------------------------------------------------------ repair
    def screen_tools(self, hyps: list[tuple[Particle, float]], n_seeds: int = 2) -> list[dict]:
        """Twin screen: each tool's probe edits under the leading hypotheses; walking-weighted score."""
        from .fault_bench import apply_changes
        from .eng_tools import parse_counterfactual
        base = self.b.best_design()
        out = []
        for tool, probes in TOOL_PROBES.items():
            best = None
            for cid in probes:
                try:
                    body, vec = apply_changes(base["body"], base["vector"], parse_counterfactual(cid))
                except Exception:   # noqa: BLE001
                    continue
                score = 0.0
                for p, w in hyps:
                    rows = self.b.twin_walk(p.deviation, {"body": body, "vector": vec}, role="twin", n=n_seeds,
                                            tag=f"screen:{tool}:{cid}")
                    if rows is None:
                        return out
                    score += w * float(np.mean([(1.0 if r.get("walking") else 0.0) + 0.05 * (r.get("fitness") or 0.0)
                                                 for r in rows if r.get("ok")] or [0.0]))
                if best is None or score > best["score"]:
                    best = {"tool": tool, "probe": cid, "score": score}
            if best:
                out.append(best)
        out.sort(key=lambda t: -t["score"])
        self._event("tool_screen", ranking=out)
        return out

    def ensemble(self, hyps: list[tuple[Particle, float]], k: int = 8) -> list[dict]:
        """Plausible plants for posterior-robust design: the leading hypotheses (cycled in weight order) each combined with a
        tolerance draw."""
        tol = tolerance_draws(k, seed=len(self.design0["vector"]) * 7919 + int(1e6 * float(self.design0["vector"][0])))
        return [{"deviation": hyps[i % len(hyps)][0].deviation + tol[i]} for i in range(k)]

    def robust_repair(self, *, twin_budget: int = 800, plant_budget: int = 300, n_check: int = 8, accept: int = 7,
                      tool_order: list[str] | None = None, engineer=None, accept_fn=None) -> dict:
        """Posterior-robust repair (v2): (1) ensemble-robust twin optimisation of the first tool as a warm start, checked on the
        plant; (2) empirical plant optimisation from it with most of the remaining plant budget, chained over two tools; (3) the
        design with the best robustness evidence is submitted. Provisional stop rule (dev): accept on 15/16 robust seeds (the
        calibrated mapping replaces it before registration).
        `engineer(state, ranking) -> {"tool_order": [...], ...}` (optional) may reorder the tools after the twin screen.
        `accept_fn(evidence) -> bool` decides early acceptance from policy-visible evidence {"robust8", "robust16", "twin_walking",
        "train_walking", "remaining"}; default: provisional 15/16 on the robust seeds; `SPEND_ALL` never accepts early (arm A1f)."""
        accept_fn = accept_fn or provisional_accept
        post = self.posterior()
        hyps, mass = [], 0.0
        for p, w in post:
            hyps.append((p, w))
            mass += w
            if mass >= 0.8 or len(hyps) >= 3:
                break
        ranking = self.screen_tools(hyps)
        tools = tool_order or [r["tool"] for r in ranking]
        if engineer is not None:
            plan = engineer(self.state(), ranking) or {}
            self._event("engineer_plan", plan=plan, engine_order=[r["tool"] for r in ranking])
            if plan.get("tool_order"):
                tools = list(plan["tool_order"]) + [t for t in tools if t not in plan["tool_order"]]
        log = []
        checked: dict[int, tuple] = {}            # design index -> (walking, n) from plant robustness checks

        def check(idx: int, n: int) -> int | None:
            self.b.select(idx)
            c = self.b.robustness_check(n)
            if not c.get("ok"):
                return None
            checked[idx] = (c["walking"], n)
            return c["walking"]

        def stress(idx: int, w16) -> int | None:
            """20 s stress test (obs seeds, 2 x n_obs) for a promising candidate when the stopping map uses it."""
            if not getattr(accept_fn, "needs_stress", False) or w16 is None or w16 < 14 or self.b.remaining < 2 * self.b.n_obs:
                return None
            self.b.select(idx)
            t = self.b.stress_test()
            return t["observation"]["n_walking"] if t.get("ok") else None
        # 1) model-based warm start: ensemble-robust twin optimisation of the first tool
        t1 = tools[0]
        start = self.b.best_design()
        res = self.b.twin_cma(hyps[0][0].deviation, start, t1, min(twin_budget, self.b.twin.remaining), role="twin",
                              n_train=8, noise_seed=0, tag=f"robust:{t1}", ensemble=self.ensemble(hyps))
        cur = start["index"]
        if res is not None:
            best = res["best"]
            cur = self.b.add_twin_design(best["body"], best["vector"], source=f"cma:{t1}", tool=t1,
                                         twin_walking=int(best["walking_count"]))
            w = check(cur, n_check)
            log.append({"step": "twin", "tool": t1, "twin_walking": int(best["walking_count"]), "design": cur, "check": w})
            if w is not None and w >= accept and self.b.remaining >= 16:
                w16 = check(cur, 16)
                log[-1]["check16"] = w16
                ev = {"robust8": w, "robust16": w16, "stress4": stress(cur, w16), "twin_walking": int(best["walking_count"]),
                      "train_walking": None, "remaining": self.b.remaining}
                log[-1]["evidence"] = ev
                if w16 is not None and accept_fn(ev):
                    return {"accepted": True, "design": cur, "log": log}
        # 2) empirical plant optimisation from the warm start with most of the remaining plant budget, chained over the tools
        reserve = 16
        for k, tool in enumerate(tools[:2]):
            avail = self.b.remaining - reserve
            budget = int(avail * 0.6) if k == 0 else avail
            if budget < plant_budget // 3:
                break
            from .hdb_workbench import min_budget
            if budget < min_budget(tool, 4):
                continue
            rep = self.b.repair(tool, budget, n_train=4, init={"index": cur})
            if not rep.get("ok"):
                log.append({"step": "plant", "tool": tool, "refused": rep.get("refused")})
                continue
            cur = rep["design_index"]
            w16 = check(cur, 16) if self.b.remaining >= 16 else None
            log.append({"step": "plant", "tool": tool, "budget": budget, "design": cur,
                        "train_walking": rep["best"]["train_walking"], "check16": w16})
            ev = {"robust8": None, "robust16": w16, "stress4": stress(cur, w16), "twin_walking": None,
                  "train_walking": rep["best"]["train_walking"], "remaining": self.b.remaining}
            log[-1]["evidence"] = ev
            if w16 is not None and accept_fn(ev):
                return {"accepted": True, "design": cur, "log": log}
        # 3) submit the design with the best robustness evidence (walking fraction on its largest check)
        if checked:
            best_idx = max(checked, key=lambda i: (checked[i][0] / checked[i][1], checked[i][1], i))
            self.b.select(best_idx)
        return {"accepted": False, "design": self.b.best_design()["index"], "log": log,
                "checked": {str(k): list(v) for k, v in checked.items()}}

    def record(self) -> dict:
        return {"version": VERSION, "settings": {"max_alive": self.max_alive, "screen_seeds": self.screen_seeds,
                                                 "diag_plant_budget": self.diag_budget, "eig_top": self.eig_top,
                                                 "refine_top": self.refine_top, "use_generic": self.use_generic,
                                                 "generic_kinds": self.generic_kinds, **self.settings},
                "particles": [p.as_dict() for p, _ in self.posterior()], "history": self.history, "events": self.events,
                "experiments": [{k: v for k, v in e.items() if k != "design"} for e in self.experiments],
                "ledger": self.b.ledger()}
