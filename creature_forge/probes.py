"""Diagnostic probes: counterfactual MuJoCo experiments the model may request BEFORE it proposes a redesign (active experimentation).

A probe is a fixed, deterministic transformation of the CURRENT creature (or of the challenge) used for diagnosis only. It is never a
proposal, never enters the arena and never changes the creature. The model chooses 1-3 probe ids from the fixed catalogue below to tell
its own hypotheses apart; `run_probes` runs the original and every probe on the SAME probe seeds (role `probe`, disjoint from the
arena seeds) and returns per-seed scores plus a summary; `evaluate_expectations` decides DETERMINISTICALLY whether what the model
expected (increase / decrease / no_change) was observed. Nothing here is a verdict (`verdict_v1` is not involved) and nothing here is
clipped: a probe whose transformation would leave the mode's hard bounds is simply unavailable (with the reason).

Probes may exceed the edit-rule ratio caps (they are not edits that can be adopted) but never the mode's hard bounds
(`interventions.apply_edits` raises, we report `unavailable`).

Catalogue (heel_x2_rear / heel_x2_front are omitted on purpose: the body has no heel parameter; `foot_length` moves heel and toe together):

  id                 transformation                                     kinds
  friction_x2        foot_friction x2                                   stand push walk
  torque_x1_5        torque_limit x1.5                                  stand push walk
  foot_x1_5          foot_length x1.5 (both feet)                       stand push walk
  torso_mass_x0_7    torso_mass x0.7                                    stand push walk
  balance_gain_x1_5  stand.balance_gain x1.5                            stand push
  stiffer_pd         stand.kp x1.5 and stand.kd x1.5                    stand push
  neutral_start      the challenge starts from the neutral pose         stand push walk
  no_push            push challenge run WITHOUT a push (stand rollout   push
                     of the same duration): separates static stability
                     from the response to the shove

`no_push` is a measurement of the unchanged creature, not a paired change: it reports `median` survival seconds and `static_fall_frac`
and has no delta; its expectation is never evaluated (`confirmed: null`).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from . import interventions as iv

PROBES_VERSION = "probes_v1"
MAX_PROBES = 3                   # per investigation
MAX_PROBE_SEEDS = 4
EXPECTATIONS = ("increase", "decrease", "no_change")
ROLE = "probe"
_ALL = ("stand", "push", "walk")
_STAND_LIKE = ("stand", "push")
DEFAULT_RESOLUTION = {"push": 2.5, "stand": 0.05, "walk": 0.05}   # same tie tolerances as verdict.DEFAULT_RESOLUTION (push: overridden by the spec)


class ProbeUnavailable(ValueError):
    """The probe cannot be run for this creature / challenge (message = reason)."""


@dataclass(frozen=True)
class Probe:
    id: str
    description: str
    kinds: tuple
    edits: tuple = ()                                  # interventions.Edit tuples (hard bounds enforced by apply_edits, ratio caps NOT)
    spec_patch: dict = field(default_factory=dict)     # challenge-spec fields changed for this probe
    measurement: str = "paired"                        # "paired": delta vs the original on the same seeds | "static": measurement only
    transformation: str = ""                           # human-readable exact transformation
    adapt_budget: int = 0                              # walk: re-adapt the walking controller with this many rollouts on TRAIN seeds


def _e(param: str, value: float) -> "iv.Edit":
    return iv.Edit(param, "scale", float(value), "both")


PROBES: dict[str, Probe] = {p.id: p for p in (
    Probe("friction_x2", "Foot-floor friction doubled: tests whether the feet slip.", _ALL, (_e("foot_friction", 2.0),),
          transformation="foot_friction x 2"),
    Probe("torque_x1_5", "Motor torque limit raised by 50%: tests whether actuation strength limits the result.", _ALL,
          (_e("torque_limit", 1.5),), transformation="torque_limit x 1.5"),
    Probe("foot_x1_5", "Both feet 50% longer (heel and toe): tests whether the support base is too short.", _ALL,
          (_e("foot_length", 1.5),), transformation="foot_length x 1.5, both feet"),
    Probe("torso_mass_x0_7", "Torso mass reduced by 30%: tests whether the upper-body inertia is the problem.", _ALL,
          (_e("torso_mass", 0.7),), transformation="torso_mass x 0.7"),
    Probe("balance_gain_x1_5", "Ankle balance feedback gain raised by 50%: tests whether the ankle feedback is too weak.", _STAND_LIKE,
          (_e("stand.balance_gain", 1.5),), transformation="stand.balance_gain x 1.5"),
    Probe("stiffer_pd", "Joint PD gains kp and kd both raised by 50%: tests whether the joints are too soft.", _STAND_LIKE,
          (_e("stand.kp", 1.5), _e("stand.kd", 1.5)), transformation="stand.kp x 1.5 and stand.kd x 1.5"),
    Probe("neutral_start", "Start from the neutral pose instead of the drawn pose: tests whether the drawn start pose causes the failure.", _ALL,
          spec_patch={"start": "neutral"}, transformation="challenge start = neutral"),
    Probe("retune_controller", "Walking controller re-adapted to this body (the arena's 48-rollout (1+8)-ES on separate training seeds, "
          "body unchanged): tests whether the controller, rather than the body, limits walking. To act on it in a proposal, set "
          "retune_controller: true (alone or with body edits): every arena arm then gets the same adaptation.", ("walk",), adapt_budget=48,
          transformation="walk controller adapted to this body, budget 48 rollouts, training seeds disjoint from the probe seeds"),
    Probe("no_push", "Same creature, no shove at all: tests whether it is already unstable without the disturbance.", ("push",),
          spec_patch={"kind": "stand"}, measurement="static", transformation="stand rollout of the push duration, no push"),
)}
PROBE_IDS = tuple(PROBES)


# ------------------------------------------------------------------------------------------------------------------ transformation
def transformation(version: dict, kind: str, spec: dict, probe_id: str) -> dict:
    """{body, controllers, spec}: the probe's creature and challenge spec (inputs are not mutated).
    Raises ProbeUnavailable (with the reason) if the probe does not apply to this challenge kind, the start is already neutral, or the
    transformed value would leave the mode's hard bounds."""
    if probe_id not in PROBES:
        raise ProbeUnavailable(f"unknown probe {probe_id!r}")
    p = PROBES[probe_id]
    if kind not in p.kinds:
        raise ProbeUnavailable(f"{probe_id} applies only to {'/'.join(p.kinds)} challenges (this is {kind})")
    out_spec = {**spec, **p.spec_patch}
    if p.spec_patch.get("start") == "neutral" and spec.get("start", "drawn") == "neutral":
        raise ProbeUnavailable("the challenge already starts from the neutral pose")
    if p.edits:
        try:
            body, controllers = iv.apply_edits(version, list(p.edits))
        except ValueError as exc:
            raise ProbeUnavailable(f"{probe_id}: {exc}") from None
    else:
        body = iv.full_body(version)
        controllers = {"stand": iv.stand_params(version), "walk": (version.get("controllers") or {}).get("walk")}
    return {"body": body, "controllers": controllers, "spec": out_spec}


def availability(version: dict, kind: str, spec: dict) -> dict[str, str | None]:
    """{probe_id: None if available else the reason}, in catalogue order."""
    out: dict[str, str | None] = {}
    for pid in PROBE_IDS:
        try:
            transformation(version, kind, spec, pid)
            out[pid] = None
        except ProbeUnavailable as exc:
            out[pid] = str(exc)
    return out


def available_probes(version: dict, kind: str, spec: dict) -> list[str]:
    return [pid for pid, why in availability(version, kind, spec).items() if why is None]


def catalogue_lines(ids) -> list[str]:
    """Prompt lines for the given probe ids."""
    return [f"- {i}: {PROBES[i].description} [{PROBES[i].transformation}]" +
            (" (measurement only: reports survival without a push, no change to compare)" if PROBES[i].measurement == "static" else "")
            for i in ids]


# ------------------------------------------------------------------------------------------------------------------ running
def resolution_for(kind: str, spec: dict) -> float:
    if kind == "push":
        return float(spec.get("max_force", 80.0)) / 2 ** int(spec.get("bisection_steps", 5))
    return DEFAULT_RESOLUTION[kind]


def _num(x):
    return None if x is None else round(float(x), 6)


RETUNE_NOISE_SEED = 0   # identical to arena.ArenaConfig.noise_seed default, so a probe and a later retune arm adapt alike


def run_probes(version: dict, kind: str, spec_dict: dict, probe_ids, seeds, pool=None, *, job_fn=None, train_seeds=None,
               adapt_fn=None) -> dict:
    """Run the original and each probe on the SAME `seeds` and summarise. Deterministic for identical inputs.
    `spec_dict`: the challenge spec (its own seeds are ignored; push uses its `bisection_steps`). `pool`: anything with `imap(fn, jobs)`
    (default: in-process). `job_fn` (tests): replaces `challenges.seed_job`. Raises ValueError for unknown/duplicate/too many probes or
    seeds, or for a probe that is unavailable (the caller chooses only from `available_probes`)."""
    ids = list(probe_ids)
    seeds = [int(s) for s in seeds]
    if not ids or len(ids) > MAX_PROBES or len(set(ids)) != len(ids):
        raise ValueError(f"1-{MAX_PROBES} distinct probe ids required, got {ids}")
    if not seeds or len(seeds) > MAX_PROBE_SEEDS or len(set(seeds)) != len(seeds):
        raise ValueError(f"1-{MAX_PROBE_SEEDS} distinct probe seeds required, got {seeds}")
    from . import challenges as ch   # lazy: heavy
    from .forge_pool import InlinePool
    pool = pool or InlinePool()
    job_fn = job_fn or ch.seed_job

    def spec_json(d: dict) -> dict:
        return ch.ChallengeSpec.from_dict({**{k: v for k, v in d.items() if k != "seeds"}, "seeds": seeds}).to_dict()

    arms: dict[str, dict] = {}
    base_spec = spec_json(spec_dict)
    if any(PROBES[i].measurement == "paired" for i in ids if i in PROBES):
        arms["original"] = {"body": iv.full_body(version), "controllers": {"stand": iv.stand_params(version), "walk": (version.get("controllers") or {}).get("walk")},
                            "spec": base_spec}
    adapt_rollouts, adapted = 0, {}
    for pid in ids:
        t = transformation(version, kind, spec_dict, pid)
        if PROBES[pid].adapt_budget:
            # Controller-adaptation probe: adapt on TRAIN seeds (never the probe seeds it is measured on), then measure on the probe seeds.
            train = [int(x) for x in (train_seeds or [])]
            if not train or set(train) & set(seeds):
                raise ValueError(f"{pid} needs training seeds disjoint from the probe seeds")
            if adapt_fn is None:
                from . import creature_walk as cw
                adapt_fn = cw.adapt_controller
            init = iv.walk_vector({"controllers": t["controllers"]})
            res = adapt_fn(iv.sandbox_body({"body": t["body"]}), init, budget=PROBES[pid].adapt_budget, train_seeds=train,
                           noise_seed=RETUNE_NOISE_SEED, pool=pool)
            adapt_rollouts += int(res["rollouts_used"])
            adapted[pid] = {"budget": PROBES[pid].adapt_budget, "rollouts_used": int(res["rollouts_used"]), "train_seeds": train,
                            "improved_on_train": res.get("improved")}
            t["controllers"] = {**t["controllers"], "walk": {"vector": [float(x) for x in res["vector"]],
                                                             "provenance": {"kind": "adapted", "probe": pid, "adaptation": adapted[pid]}}}
        arms[pid] = {"body": t["body"], "controllers": t["controllers"], "spec": spec_json(t["spec"])}
    jobs, index = [], []
    for name, a in arms.items():
        for k, s in enumerate(seeds):
            jobs.append({"body": a["body"], "controllers": a["controllers"], "spec": a["spec"], "seed": s})
            index.append((name, k))
    raw: dict[str, list] = {n: [None] * len(seeds) for n in arms}
    for i, res in pool.imap(job_fn, jobs):
        name, k = index[i]
        if isinstance(res, tuple) and len(res) == 2 and res[0] == "error":
            res = {"seed": seeds[k], "outcome": "ERROR", "score": 0.0, "metrics": {"error": res[1]}, "rollouts": 0, "error": res[1]}
        raw[name][k] = res
    rollouts = sum(int((r or {}).get("rollouts") or 0) for rs in raw.values() for r in rs) + adapt_rollouts
    tol = resolution_for(kind, spec_dict)

    def scores(name: str):
        rs = raw[name]
        if any(r is None or r.get("outcome") == "ERROR" for r in rs):
            return None
        return [float(r["score"]) for r in rs]

    orig = scores("original") if "original" in raw else None
    out = {"version": PROBES_VERSION, "kind": kind, "seeds": seeds, "resolution": tol, "rollouts": rollouts, "probe_ids": ids,
           "bisection_steps": base_spec.get("bisection_steps") if kind == "push" else None,
           "original": ({"scores": [_num(x) for x in orig], "median": _num(statistics.median(orig)), "status": "ok"} if orig is not None
                        else ({"scores": None, "median": None, "status": "error"} if "original" in raw else None)),
           "results": {}}
    for pid in ids:
        p = PROBES[pid]
        sc = scores(pid)
        res: dict = {"probe_id": pid, "measurement": p.measurement, "transformation": p.transformation, "status": "ok",
                     "scores": None if sc is None else [_num(x) for x in sc]}
        if pid in adapted:
            res["adaptation"] = adapted[pid]
        if sc is None:
            res["status"] = "error"
            res["error"] = next((r.get("error") for r in raw[pid] if r and r.get("error")), "a probe rollout could not run")
        elif p.measurement == "static":
            res.update(median=_num(statistics.median(sc)), n_seeds=len(sc),
                       static_fall_frac=_num(sum(1 for r in raw[pid] if (r.get("metrics") or {}).get("fell")) / len(sc)))
        elif orig is None:
            res["status"] = "error"
            res["error"] = "the unchanged creature could not be run on the probe seeds"
        else:
            d = [a - b for a, b in zip(sc, orig)]
            res.update(median=_num(statistics.median(sc)), median_delta=_num(statistics.median(d)), mean_delta=_num(statistics.fmean(d)),
                       deltas=[_num(x) for x in d], n_seeds=len(sc), wins=sum(1 for x in d if x > tol + 1e-9),
                       losses=sum(1 for x in d if x < -tol - 1e-9), ties=sum(1 for x in d if abs(x) <= tol + 1e-9))
        out["results"][pid] = res
    return out


# ------------------------------------------------------------------------------------------------------------------ evidence + expectations
def evidence_block(out: dict) -> dict:
    """The scalar-only `probes` section added to the step-B evidence pack: citable as `probes.<id>.median_delta` etc."""
    block: dict = {"n_seeds": len(out["seeds"]), "resolution": out["resolution"]}
    if out.get("original"):
        block["original"] = {"median": out["original"]["median"]}
    for pid, r in out["results"].items():
        keep = ("status", "median", "median_delta", "mean_delta", "wins", "losses", "ties", "static_fall_frac")
        block[pid] = {k: r[k] for k in keep if r.get(k) is not None}
    return block


def observed_direction(median_delta, resolution: float) -> str | None:
    if median_delta is None:
        return None
    if median_delta > resolution + 1e-9:
        return "increase"
    if median_delta < -resolution - 1e-9:
        return "decrease"
    return "no_change"


def evaluate_expectations(requests: list[dict], out: dict) -> list[dict]:
    """Per requested probe: {probe_id, hypothesis, expect, observed, confirmed}. Deterministic, never done by the model.
    observed = increase / decrease when the median per-seed delta exceeds the score resolution, else no_change; `observed` and
    `confirmed` are None for a probe that errored or is a measurement-only probe (no_push)."""
    res = []
    for r in requests:
        pr = out["results"].get(r["probe_id"], {})
        obs = observed_direction(pr.get("median_delta"), out["resolution"]) if pr.get("status") == "ok" else None
        res.append({"probe_id": r["probe_id"], "hypothesis": r.get("hypothesis"), "expect": r.get("expect"), "observed": obs,
                    "confirmed": None if obs is None else obs == r.get("expect")})
    return res
