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

VERSION = "belief_engine_v5"   # v2: warm-started plant optimisation with the remaining budget + selection by robustness evidence; v3: 4-level generic magnitudes, two-step refinement; v4: calibrated scales + seed-level contamination likelihood; v5: tool screen by short ensemble twin CMA
VERSION_V6 = "belief_engine_v6"  # DS-1 (docs/DS1_PROTOCOL.md §1), enabled by Episode(v6={...}); without it the engine is v5 exactly:
                                 # tempered likelihood, structural misfit -> composite hypotheses under a hard twin budget with an
                                 # open-world reserve, automatic assimilation of plant checks of repairs (relative update),
                                 # displacement-aware evidence, a learned tool ranker hook and submission by mapped P(FULL)
UNMODELLED = (("unmodelled", "any"),)             # the open-world reserve's structure label (v6)
DIAGNOSTIC_KINDS = ("observe", "counterfactual", "floor")   # experiments that measure the fault (plant checks of repairs do not)
V6_DEFAULTS = {"temperature": 1.0, "misfit_threshold": None, "repair_twin_reserve": 1750, "composite_cap": 500,
               "max_composite_rounds": 2, "auto_assimilate": True, "assimilate_seeds": 8, "select_by_p": True}

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
    if kind == "logistic_v2":       # v6: + displacement evidence on the robust seeds (hdb_evidence), scripts/ds1_stop_map.py
        x = v2_features(ev, model)
        if x is None:
            return None
        z = sum(a * b for a, b in zip(model["w"], x))
        return 1.0 / (1.0 + math.exp(-z))
    raise ValueError(f"unsupported stopping model {kind!r}")


def v2_features(ev: dict, model: dict) -> list[float] | None:
    """Feature vector of stop map v2: bias, empirical logits of robust16 and stress4, displacement pass flag, clipped median
    paired displacement difference (m)."""
    x = [1.0]
    for f in ("robust16", "stress4"):
        v, n = ev.get(f), model["n_by_feature"][f]
        if v is None:
            return None
        x.append(math.log((v + 0.5) / (n - v + 0.5)))
    if ev.get("disp_pass") is None or ev.get("disp_median_m") is None:
        return None
    lo, hi = model.get("disp_clip", (-1.5, 1.5))
    x += [1.0 if ev["disp_pass"] else 0.0, min(hi, max(lo, float(ev["disp_median_m"])))]
    return x


def calibrated_accept(model: dict, tau: float):
    """accept_fn from a dev-fitted mapping: accept iff mapped P(FULL) >= tau. Needs the evidence the map uses (the engine runs
    the 20 s stress test for promising candidates when the map uses it)."""
    mapped_p_full(model, {"robust16": 16, "stress4": 4, "disp_pass": True, "disp_median_m": 1.0})   # validates the model

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


def neighbours(dev: list, step: float = 0.35, *, multi: bool = False) -> list[list[dict]]:
    """Local refinements of a hypothesis: each parameter moved by +-step (log for factors and masses, linear otherwise).
    The engine's own refinement covers 1-primitive hypotheses only. `multi` (fitting an externally proposed 2-primitive
    hypothesis) moves each parameter of each primitive in turn."""
    if len(dev) != 1 and not multi:
        return []
    out = []
    for i, p in enumerate(dev):
        lo_hi = hp.PRIMITIVES[p["kind"]]["params"]
        for name, v in p["params"].items():
            lo, hi = lo_hi[name]
            if name in ("factor", "mass_kg"):
                cands = (v * math.exp(step), v * math.exp(-step))
            else:
                span = hi - lo
                cands = (v + 0.35 * step * span, v - 0.35 * step * span)
            for c in cands:
                if lo <= c <= hi and abs(c - v) > 1e-9:
                    q = copy.deepcopy(dev)
                    q[i]["params"][name] = float(round(c, 6))
                    out.append(q)
    return [hp.validate_deviation(d) for d in out]


# ---------------------------------------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------------------------------------
class Episode:
    """One investigation by the engine on an HDBWorkbench. `proposer` (optional) is called with the engine's state summary and
    returns lists of deviations to add (Nemotron, a learned posterior, dossiers, or a SCRIPTED_MOCK)."""

    def __init__(self, bench, *, proposer=None, use_generic: bool = True, max_alive: int = 12, screen_seeds: int = 2,
                 diag_plant_budget: int = 120, eig_top: int = 6, refine_top: int = 3, settings: dict | None = None,
                 generic_kinds: tuple | None = None, v6: dict | None = None):
        self.b = bench
        unknown = set(v6 or {}) - set(V6_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown v6 options {sorted(unknown)}")
        self.v6 = None if v6 is None else {**V6_DEFAULTS, **v6}
        self.T = float(self.v6["temperature"]) if self.v6 else 1.0
        self._composite_rounds = 0
        self._assimilated: set[int] = set()
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
        u = self.unmodelled_mass()
        if u > 0.0:            # v6 open-world reserve: modelled structures share 1 - u
            agg = {s: w * (1.0 - u) for s, w in agg.items()}
            agg[UNMODELLED] = u
        return sorted(agg.items(), key=lambda t: -t[1])

    # ------------------------------------------------------------ v6: structural misfit
    def _diag_split(self, p: Particle) -> tuple[float, int]:
        """(log-likelihood of p on the diagnostic experiments, number of their observed seeds)."""
        ll, n = 0.0, 0
        for exp in self.experiments:
            if exp["kind"] not in DIAGNOSTIC_KINDS or exp["id"] not in p.seen:
                continue
            ll += self._score(p, exp, p.seen[exp["id"]])
            n += len(exp["features"])
        return ll, n

    def misfit_stat(self) -> float | None:
        """Mean log-likelihood per observed seed of the leading particle on the diagnostic experiments (plant checks of
        repaired designs are excluded: a repair that fails is not evidence of an unmodelled cause)."""
        if not self.particles:
            return None
        ll, n = self._diag_split(self.posterior()[0][0])
        return ll / n if n else None

    def unmodelled_mass(self) -> float:
        """Posterior mass of the open-world reserve: an explanation that fits every diagnostic seed at the dev-calibrated
        threshold level and is as good as the leader on everything else."""
        if not self.v6 or self.v6["misfit_threshold"] is None or not self.particles:
            return 0.0
        best = max(self.particles.values(), key=lambda q: q.logw)
        ll, n = self._diag_split(best)
        if n == 0:
            return 0.0
        lr = (self.v6["misfit_threshold"] * n + (best.loglik - ll)) / self.T
        m = max(lr, best.logw)
        z = sum(math.exp(p.logw - m) for p in self.particles.values())
        return math.exp(lr - m) / (z + math.exp(lr - m))

    def _particle_cost(self) -> int:
        """Twin rollouts needed to score one new particle against every experiment so far."""
        return sum(0 if e["kind"] == "weigh" else len(e.get("seeds") or e.get("features") or ()) for e in self.experiments)

    def expand_composites(self) -> dict | None:
        """v6: when the leader misfits the diagnostic data, enumerate two-primitive hypotheses from the leading distinct
        single-primitive structures (top 4 -> at most 6 pairs), weigh them with the same likelihood and fit the magnitudes
        of the two best, within min(composite_cap, twin remaining - repair reserve) twin rollouts."""
        import itertools
        if not self.v6 or self.v6["misfit_threshold"] is None or self._composite_rounds >= self.v6["max_composite_rounds"]:
            return None
        stat = self.misfit_stat()
        if stat is None or stat >= self.v6["misfit_threshold"]:
            return None
        self._composite_rounds += 1
        cap = min(int(self.v6["composite_cap"]), self.b.twin.remaining - int(self.v6["repair_twin_reserve"]))
        info = {"stat": round(stat, 3), "threshold": self.v6["misfit_threshold"], "cap": cap}
        if cap <= 0:
            self._event("composite_skipped", reason="twin budget reserved for repair", **info)
            return info
        singles: list[Particle] = []
        for p, _ in self.posterior():
            if len(p.deviation) == 1 and all(p.structure != q.structure for q in singles):
                singles.append(max((q for q in self.particles.values() if q.structure == p.structure), key=lambda q: q.loglik))
            if len(singles) >= 4:
                break
        pairs = []
        for a, b in itertools.combinations(singles, 2):
            try:
                pairs.append(hp.validate_deviation(copy.deepcopy(a.deviation + b.deviation)))
            except hp.DeviationError:
                continue
        start, per = self.b.twin.used, max(1, self._particle_cost())
        added = []
        for dev in pairs:
            if self.b.twin.used - start + per > cap:
                break
            added += self.add_particles([dev], "composite")
        fitted = []
        for pid in sorted(added, key=lambda q: -self.particles[q].loglik)[:2]:
            st = self.particles[pid].structure
            for step in (0.35, 0.15):
                best = max((q for q in self.particles.values() if q.structure == st), key=lambda q: q.loglik)
                neigh = neighbours(best.deviation, step, multi=True)
                if self.b.twin.used - start + per * len(neigh) > cap:
                    break
                self.add_particles(neigh, "composite+fit")
            fitted.append(pid)
        self.prune()
        info.update(pairs=[_pid(d) for d in pairs], added=added, fitted=fitted, twin_cost=self.b.twin.used - start)
        self._event("composite_expansion", **info)
        return info

    # ------------------------------------------------------------ v6: cross-feedback from interventions
    def assimilate_light(self, design: dict, labels: list, *, seeds: list[int], design_index: int) -> dict | None:
        """Fold a plant robustness check of a repaired design into the belief (v6, automatic). Every alive particle's twin
        predicts walking for that design on the same robust seeds; the walking-only likelihood reweights them. The update is
        relative: an outcome that every competing mechanism predicted alike moves no weight. No refinement (bounded cost)."""
        if not self.v6:
            return None
        n = min(int(self.v6["assimilate_seeds"]), len(labels), len(seeds))
        if int(design_index) in self._assimilated or n == 0:
            return None
        need = len(self.particles) * n
        if self.b.twin.remaining < need:
            self._event("assimilation_skipped", design=int(design_index), reason=f"needs {need} twin rollouts")
            return None
        self._assimilated.add(int(design_index))
        walk = {int(s): {"walking": 1.0 if lab == "walking" else 0.0} for s, lab in zip(seeds[:n], labels[:n])}
        exp = {"id": f"X{len(self.experiments)}:check@{int(design_index)}", "kind": "check", "role": "robust",
               "design": {"body": design["body"], "vector": design["vector"]}, "seeds": [int(s) for s in seeds[:n]],
               "features": walk, "keys": ["walking"], "cost": 0}
        before = self.structure_posterior()[:4]
        self._register(exp)
        predicted = {}
        for st, _ in before:
            if st == UNMODELLED:
                continue
            ps = [p for p in self.particles.values() if p.structure == st and exp["id"] in p.seen]
            if ps:
                best = max(ps, key=lambda q: q.loglik)
                predicted["+".join(f"{k}:{t}" for k, t in st)] = int(sum(1 for f in best.seen[exp["id"]].values()
                                                                           if f.get("walking")))
        self.prune()
        self.snapshot(f"after_{exp['id']}")
        after = self.structure_posterior()[:4]
        out = {"id": exp["id"], "observed_walking": int(sum(f["walking"] for f in walk.values())), "n": n,
               "predicted_walking": predicted,
               "before": [([list(x) for x in s], round(w, 4)) for s, w in before],
               "after": [([list(x) for x in s], round(w, 4)) for s, w in after],
               "leader_changed": bool(before and after and before[0][0] != after[0][0])}
        self._event("assimilated_check", design=int(design_index), **{k: v for k, v in out.items() if k != "id"})
        return out

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
            obs = self.b.twin_observe(p.deviation, exp["design"], role=exp.get("role", "obs"), n=seeds_n,
                                      friction_mult=exp.get("friction_mult", 1.0), tag=f"{p.pid}|{exp['id']}")
            if obs is None:
                return None
            pred = obs_features(obs)
        p.seen[key] = pred
        return pred

    def _score(self, p: Particle, exp: dict, pred) -> float:
        if exp["kind"] == "weigh":
            return weigh_loglik(exp["measured"], pred, self.design_mass)
        if exp.get("keys"):          # partial measurement (e.g. a robustness check records walking only)
            pred = {s: {k: f.get(k) for k in exp["keys"]} for s, f in pred.items()}
        return loglik(exp["features"], pred)

    def assimilate_check(self, design: dict, check: dict, *, seeds: list[int]) -> dict:
        """Fold a plant robustness check of a (repaired) design into the belief: per-seed walking on the robust seeds,
        compared with every particle's twin prediction of the same design on the same seeds (walking-only likelihood).
        A repair that fails on the plant although the leading hypotheses predicted success is evidence against them."""
        walk = {int(s): {"walking": 1.0 if lab == "walking" else 0.0} for s, lab in zip(seeds, check["labels"])}
        exp = {"id": f"X{len(self.experiments)}:check@{check['design_index']}", "kind": "check", "role": "robust",
               "design": {"body": design["body"], "vector": design["vector"]}, "seeds": [int(s) for s in seeds[:len(walk)]],
               "features": walk, "keys": ["walking"], "cost": 0}
        before = self.structure_posterior()[:3]
        self._register(exp)
        self.refine()
        self.prune()
        self.snapshot(f"after_{exp['id']}")
        return {"id": exp["id"], "before": [([list(x) for x in s], round(w, 4)) for s, w in before],
                "after": [([list(x) for x in s], round(w, 4)) for s, w in self.structure_posterior()[:3]]}

    def _update_particle(self, p: Particle) -> bool:
        """Bring p's log-likelihood up to date with every plant experiment. False if the twin budget ran out."""
        total = 0.0
        for exp in self.experiments:
            pred = self._predict(p, exp)
            if pred is None:
                return False
            total += self._score(p, exp, pred)
        p.loglik = total
        p.logw = total if self.T == 1.0 else total / self.T      # v6: tempered likelihood (v5: T = 1, identical)
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

    def fit_structures(self, pids: list[str], steps: tuple = (0.35, 0.15), rounds: int = 1) -> None:
        """Per-structure parameter fit of externally proposed hypotheses (has_agent): coordinate search around the best
        particle of each proposed structure. A proposal with the right mechanism but a wrong magnitude is not discarded
        before its magnitude is fitted to the data."""
        for pid in pids:
            p0 = self.particles.get(pid)
            if p0 is None:
                continue
            st, src = p0.structure, p0.source + "+fit"
            for step in steps:
                for _ in range(rounds):
                    best = max((q for q in self.particles.values() if q.structure == st), key=lambda q: q.loglik)
                    if not self.add_particles(neighbours(best.deviation, step, multi=True), src):
                        break

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
        self.start()
        for i in range(max_experiments):
            if self.diagnosis_done(confident):
                break
            scored = self.rank_experiments()
            if not scored:
                break
            pick = choose(scored, self.state()) if choose else scored[0][2]
            self.experiment_step(pick, by="external" if choose else "eig", scored=scored)
        return self.diagnosis_summary()

    # the steps of `diagnose`, also driven one at a time by an external scientist (has_agent)
    def start(self) -> None:
        """First observation, generic screen, first proposals, refinement."""
        self.run_observe()
        if self.use_generic:
            self._screen_generic()
        if self.proposer is not None:
            self.add_particles(self.proposer(self.state()), "proposer")
        self.refine()
        self.prune()
        self.expand_composites()
        self.snapshot("after_observation")

    def diagnosis_done(self, confident: float = 0.9) -> bool:
        """The engine's own stopping rule for diagnosis: a structure holds `confident` mass or the diagnosis budget is spent.
        (v6: the open-world reserve never counts as a confident diagnosis, and its mass counts against the others.)"""
        sp = [(s, w) for s, w in self.structure_posterior() if s != UNMODELLED]
        return bool(sp and sp[0][1] >= confident) or self.b.budget.used >= self.diag_budget

    def rank_experiments(self, extra: list[dict] | None = None) -> list[tuple]:
        """[(eig_per_rollout, eig, candidate)], best first, over the generic candidates plus `extra` (externally designed)."""
        top = self.posterior()[:self.eig_top]
        scored = []
        for c in self.candidate_experiments() + list(extra or []):
            g = self.eig(c, top)
            if g is None:
                break
            scored.append((g / c["cost"], g, c))
        scored.sort(key=lambda t: -t[0])
        return scored

    def experiment_step(self, pick: dict, *, by: str, scored: list | None = None) -> dict:
        self._event("experiment_chosen", id=pick["id"], by=by,
                    ranking=[{"id": c["id"], "eig": round(g, 4), "eig_per_rollout": round(r, 5)} for r, g, c in (scored or [])[:8]])
        res = self.run_experiment(pick)
        if self.proposer is not None:
            self.add_particles(self.proposer(self.state()), "proposer")
        self.refine()
        self.prune()
        self.expand_composites()
        self.snapshot(f"after_{pick['id']}")
        return res

    def diagnosis_summary(self) -> dict:
        sp = [(s, w) for s, w in self.structure_posterior() if s != UNMODELLED]
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

    def screen_tools_cma(self, hyps, ranking: list[dict], *, top: int = 5, budget: int = 150) -> list[dict]:
        """v5: re-rank the `top` tools of the probe screen by a short ensemble-robust twin optimisation each (probe edits are too
        small to reveal tools whose fix needs a large change, e.g. posture compensation of a sensor bias)."""
        from .hdb_workbench import min_budget
        start = self.b.best_design()
        ens = self.ensemble(hyps, k=4)
        out = []
        for r in ranking[:top]:
            tool = r["tool"]
            b = max(budget, min_budget(tool, 4))
            res = self.b.twin_cma(hyps[0][0].deviation, start, tool, b, role="twin", n_train=4, noise_seed=11,
                                  tag=f"screen_cma:{tool}", ensemble=ens)
            if res is None:
                out.append({**r, "cma_walking": None, "cma_fitness": None})
                continue
            best = res["best"]
            out.append({**r, "cma_walking": int(best["walking_count"]), "cma_fitness": float(best["mean_fitness"])})
        out.sort(key=lambda t: (-(t["cma_walking"] if t["cma_walking"] is not None else -1),
                                -(t["cma_fitness"] if t["cma_fitness"] is not None else -1e9)))
        rest = [r for r in ranking[top:]]
        self._event("tool_screen_cma", ranking=out)
        return out + rest

    def ensemble(self, hyps: list[tuple[Particle, float]], k: int = 8) -> list[dict]:
        """Plausible plants for posterior-robust design: the leading hypotheses (cycled in weight order) each combined with a
        tolerance draw."""
        tol = tolerance_draws(k, seed=len(self.design0["vector"]) * 7919 + int(1e6 * float(self.design0["vector"][0])))
        return [{"deviation": hyps[i % len(hyps)][0].deviation + tol[i]} for i in range(k)]

    def robust_repair(self, *, twin_budget: int = 800, plant_budget: int = 300, n_check: int = 8, accept: int = 7,
                      tool_order: list[str] | None = None, engineer=None, accept_fn=None, screen_cma: bool = True,
                      screen_top: int = 5, screen_budget: int = 150, prefer: list[str] | None = None, ranker=None) -> dict:
        """Posterior-robust repair (v2): (1) ensemble-robust twin optimisation of the first tool as a warm start, checked on the
        plant; (2) empirical plant optimisation from it with most of the remaining plant budget, chained over two tools; (3) the
        design with the best robustness evidence is submitted. Provisional stop rule (dev): accept on 15/16 robust seeds (the
        calibrated mapping replaces it before registration).
        `engineer(state, ranking) -> {"tool_order": [...], ...}` (optional) may reorder the tools after the twin screen.
        `accept_fn(evidence) -> bool` decides early acceptance from policy-visible evidence {"robust8", "robust16", "twin_walking",
        "train_walking", "remaining"}; default: provisional 15/16 on the robust seeds; `SPEND_ALL` never accepts early (arm A1f).
        v6 (`Episode(v6=...)`): plant checks of repaired designs are assimilated into the belief (and the tools re-screened if the
        leading explanation changes), displacement evidence joins the stopping evidence, and the submission is the checked
        design with the highest mapped P(FULL). `ranker(episode, hyps, ranking) -> ranking` (a learned tool ranker, arm A1x)
        reorders the engine's screened tools."""
        accept_fn = accept_fn or provisional_accept
        if self.v6 and hasattr(self.b, "baseline"):
            self.b.baseline()          # the faulty design on the robust seeds, once (displacement evidence; 16 plant rollouts)
        hyps = self._repair_hyps()
        ranking = self.screen_tools(hyps)
        if screen_cma and tool_order is None and not prefer:
            ranking = self.screen_tools_cma(hyps, ranking, top=screen_top, budget=screen_budget)
        if ranker is not None and tool_order is None and ranking:
            ranking = ranker(self, hyps, ranking)
        tools = tool_order or [r["tool"] for r in ranking]
        if prefer:       # an external scientist's tool choice goes first; the engine's ranking fills the rest (has_agent)
            tools = list(prefer) + [t for t in tools if t not in prefer]
            self._event("preferred_tools", prefer=list(prefer), engine_order=[r["tool"] for r in ranking])
        if not tools:    # no twin budget left for a screen (only reachable after external proposals used it): fixed order
            tools = list(TOOL_PROBES)
            self._event("tool_screen_unavailable", fallback_order=tools)
        if engineer is not None:
            plan = engineer(self.state(), ranking) or {}
            self._event("engineer_plan", plan=plan, engine_order=[r["tool"] for r in ranking])
            if plan.get("tool_order"):
                tools = list(plan["tool_order"]) + [t for t in tools if t not in plan["tool_order"]]
        log = []
        checked: dict[int, tuple] = {}            # design index -> (walking, n) from plant robustness checks
        pmap: dict[int, float] = {}               # v6: design index -> mapped P(FULL)
        assim: list[dict] = []

        def check(idx: int, n: int) -> int | None:
            self.b.select(idx)
            c = self.b.robustness_check(n)
            if not c.get("ok"):
                return None
            checked[idx] = (c["walking"], n)
            if self.v6 and self.v6["auto_assimilate"] and idx != 0:
                a = self.assimilate_light(self.b.designs[idx], c["labels"], seeds=self.b.view_seeds["robust"][:n],
                                          design_index=idx)
                if a:
                    assim.append(a)
            return c["walking"]

        def decide(idx: int, ev: dict) -> bool:
            if self.v6 and ev.get("robust16") is not None and hasattr(self.b, "displacement"):
                d = self.b.displacement(idx)
                if d is not None:
                    ev.update(disp_pass=d["pass"], disp_median_m=d["median_diff_m"], disp_status=d["status"])
            ok = accept_fn(ev)
            if ev.get("p_full") is not None:
                pmap[idx] = float(ev["p_full"])
            return ok

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
                if w16 is not None and decide(cur, ev):
                    return {"accepted": True, "design": cur, "log": log, **({"assimilated": assim} if self.v6 else {})}
        if self.v6 and assim and assim[-1]["leader_changed"] and tool_order is None and not prefer and self.b.twin.remaining >= 250:
            # the intervention's outcome moved the belief to another explanation: re-screen the tools under it
            hyps = self._repair_hyps()
            ranking = self.screen_tools(hyps)
            if ranker is not None and ranking:
                ranking = ranker(self, hyps, ranking)
            if ranking:
                self._event("rescreen_after_assimilation", old_order=tools[:4], new_order=[r["tool"] for r in ranking][:4])
                tools = [r["tool"] for r in ranking]
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
            if w16 is not None and decide(cur, ev):
                return {"accepted": True, "design": cur, "log": log, **({"assimilated": assim} if self.v6 else {})}
        # 3) submit the design with the best robustness evidence (walking fraction on its largest check); v6: the highest
        # mapped P(FULL) when any checked design has one (it includes the displacement evidence)
        if self.v6 and self.v6["select_by_p"] and pmap:
            best_idx = max(pmap, key=lambda i: (pmap[i], checked.get(i, (0, 1))[0] / checked.get(i, (0, 1))[1], i))
            self.b.select(best_idx)
        elif checked:
            best_idx = max(checked, key=lambda i: (checked[i][0] / checked[i][1], checked[i][1], i))
            self.b.select(best_idx)
        out = {"accepted": False, "design": self.b.best_design()["index"], "log": log,
               "checked": {str(k): list(v) for k, v in checked.items()}}
        if self.v6:
            out.update(assimilated=assim, p_full={str(k): round(v, 4) for k, v in pmap.items()})
        return out

    def _repair_hyps(self) -> list[tuple[Particle, float]]:
        """The leading hypotheses a repair is designed against: top particles up to 80 % mass or 3 particles."""
        hyps, mass = [], 0.0
        for p, w in self.posterior():
            hyps.append((p, w))
            mass += w
            if mass >= 0.8 or len(hyps) >= 3:
                break
        return hyps

    def record(self) -> dict:
        v6 = {"v6": dict(self.v6), "unmodelled_mass": round(self.unmodelled_mass(), 5)} if self.v6 else {}
        return {"version": VERSION_V6 if self.v6 else VERSION,
                "settings": {"max_alive": self.max_alive, "screen_seeds": self.screen_seeds,
                             "diag_plant_budget": self.diag_budget, "eig_top": self.eig_top,
                             "refine_top": self.refine_top, "use_generic": self.use_generic,
                             "generic_kinds": self.generic_kinds, **self.settings}, **v6,
                "particles": [p.as_dict() for p, _ in self.posterior()], "history": self.history, "events": self.events,
                "experiments": [{k: v for k, v in e.items() if k != "design"} for e in self.experiments],
                "ledger": self.b.ledger()}
