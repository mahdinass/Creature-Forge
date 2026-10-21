"""W2 damaged-plant export: the robot of hdb-v1-gen-0137:one_side_weakness:4 WITH its hidden damage, as Studio viewer payloads,
for the "Nemotron's experiment" page. Every exported rollout is checked against the recorded Stage 2 episodes.

Source of truth: experiments/w2/gen0137_one_side_weakness/{A3,A1e}.jsonl (byte-exact, pinned lines of the Stage 2 transfer
records; scripts/w2_case_build.load_excerpt refuses anything else). What is exported:
  observe   X0: the nominal design on the damaged plant, 4 obs seeds (identical in every arm)
  x1_nem    X1 of the Nemotron arm (A3): cf:freq@x0.85, 4 obs seeds
  x1_eng    X1 of the engine-alone arm (A1e): cf:freq@x1.2, 4 obs seeds
  nominal / a3_submitted / a1e_submitted   the verifier's 24 validation seeds (10 s) of the original and each submitted design

Fidelity gate (fail-closed; nothing is written unless every check passes):
  0. instance: rebuilt as scripts/hdb_agent_run.py built it (hdb_bench.make_instance_v2 on the dev base with
     thresholds_dev.json, then check_eligibility). Its eligibility labels, injected structure, strength, nominal design and
     obs seeds must equal the record.
  1. experiments (per seed, exact ==): hidden_plant.observe -> belief_engine.obs_features on each recorded experiment design
     must reproduce the recorded per-seed features of X0 and both X1 experiments.
  2. verification (aggregate, exact ==): hdb_bench.verify of both submitted designs must reproduce the recorded status,
     walking fraction and reasons. Stage 2 stored no per-seed verification rows, so the validation replays are
     aggregate-matched to the record and per-seed matched to this run's own production rows (stated in the index).
  3. frames: every exported rollout is re-run under an observer of the production function (hidden_plant.plant_rollout is
     wrapped to keep its trace; mujoco.mj_step to copy the pre/post-step state). The trace must give the production row
     (features for experiments; the verifier's row for validation seeds), and forward kinematics of the pre-step state must
     reproduce the logged torso and foot positions (<= 1e-9 m), exactly as scripts/do1_demo_export.py.
  4. environment: --execute refuses unless OS/Python/numpy/MuJoCo equal the recorded Linux environment (Windows does not
     reproduce the Linux per-seed physics, W1a). The dry run and the no-physics tests work anywhere.
No model is called. Nemotron's decisions are read from the record; the physics is MuJoCo's.

  python scripts/w2_damaged_plant_export.py                     # dry run (default): plan from the record; nothing simulated
  python scripts/w2_damaged_plant_export.py --smoke   --approved-by "<owner, date>" --artifacts-root <dir> [--workers 2]
  python scripts/w2_damaged_plant_export.py --execute --approved-by "<owner, date>" --artifacts-root <dir> [--workers 2]
      <dir> holds thresholds_dev.json and walkers_all.jsonl (the pinned TA-1 inputs).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import w2_case_build as wcb  # noqa: E402

EXPORTER_VERSION = "w2_damaged_plant_export_v1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = "experiments/w2/gen0137_one_side_weakness/plant_replays"
INPUT_SHA256 = {"thresholds_dev.json": "12ca21cbf85d054f9aa4aa08beb184b0f497b52e205184c264609aeedfc37d89",
                "walkers_all.jsonl": "151801a5187aabf8ad1dade4e41c47ea07c57007c590ffdb235df83f19aaf1fd"}
RECORDED_ENV = {"system": "Linux", "machine": "x86_64", "python": "3.12.3", "numpy": "2.5.4", "mujoco": "3.15.0"}
EXPERIMENTS = {"observe": ("A3", 0), "x1_nem": ("A3", 1), "x1_eng": ("A1e", 1)}     # name -> (arm, experiment index)
VALIDATION = {"nominal": ("A3", 0), "a3_submitted": ("A3", None), "a1e_submitted": ("A1e", None)}  # None = submitted
FK_TOL_M = 1e-9


class FidelityError(RuntimeError):
    """A replay disagreed with the record: nothing may be exported."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _design(rec: dict, index: int) -> dict:
    d = next(d for d in rec["designs"] if d["index"] == index)
    return {"body": d["body"], "vector": [float(x) for x in d["vector"]]}


def experiment_design(rec: dict, exp_index: int) -> dict:
    """The design an experiment ran: X0 = designs[0]; a counterfactual = the design the bench added for it."""
    e = rec["engine"]["experiments"][exp_index]
    if e["kind"] == "observe":
        return _design(rec, 0)
    src = f"counterfactual:{e['id'].split(':', 1)[1].split(':', 1)[1]}"
    hit = [d for d in rec["designs"] if d["source"] == src]
    if len(hit) != 1:
        raise FidelityError(f"{rec['arm']}: no unique design for {e['id']} (looked for source {src!r})")
    return {"body": hit[0]["body"], "vector": [float(x) for x in hit[0]["vector"]]}


def plan(recs: dict) -> dict:
    """Everything the export will reproduce, read from the record. No physics."""
    a3, a1 = recs["A3"], recs["A1e"]
    exps = {}
    for name, (arm, i) in EXPERIMENTS.items():
        e = recs[arm]["engine"]["experiments"][i]
        exps[name] = {"arm": arm, "id": e["id"], "seeds": [int(s) for s in e["seeds"]],
                      "design_hash": wcb.design_hash(experiment_design(recs[arm], i)),
                      "features": {int(s): f for s, f in e["features"].items()}}
    if exps["observe"]["features"] != {int(s): f for s, f in a1["engine"]["experiments"][0]["features"].items()}:
        raise FidelityError("X0 differs between the arms in the record")
    val = {}
    for name, (arm, idx) in VALIDATION.items():
        r = recs[arm]
        d = _design(r, r["submitted"] if idx is None else idx)
        val[name] = {"arm": arm, "design_hash": wcb.design_hash(d),
                     "recorded": None if idx == 0 else {k: r["verification"][k] for k in ("status", "walking_frac", "reasons")}}
    n_val = 24
    eq = 8 + 4 * len(EXPERIMENTS) + 2 * (2 * n_val + 2 * n_val) + (len(EXPERIMENTS) * 4 + len(VALIDATION) * n_val)
    return {"instance": wcb.INSTANCE_ID, "experiments": exps, "validation": val,
            "injected_structure": a3["injected_structure"], "strength": a3["strength"], "check": a3["check"],
            "rollout_equivalents": eq,
            "rollout_note": "8 eligibility + 12 experiment + 2 verifications (24 x 10 s original + candidate, 24 x 20 s "
                            "confirmation each) + 84 traced re-runs; plant only, no twin, no model call"}


def current_environment() -> dict:
    import platform

    import mujoco
    import numpy as np
    return {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version(),
            "numpy": np.__version__, "mujoco": mujoco.__version__}


def environment_problems(env: dict) -> list[str]:
    return [f"{k}: this environment has {env.get(k)!r}, the recorded runs used {v!r}" for k, v in RECORDED_ENV.items() if env.get(k) != v]


# ---------------------------------------------------------------------------------------------------- physics (--execute)
def build_instance(artifacts_root: str, pool=None) -> dict:
    """The instance exactly as scripts/hdb_agent_run.py built it. PHYSICS: check_eligibility runs 8 plant rollouts."""
    from creature_forge import hdb_bench as hb
    for name, want in INPUT_SHA256.items():
        got = sha256_file(os.path.join(artifacts_root, name))
        if got != want:
            raise FidelityError(f"{name}: sha256 {got} is not the pinned {want}")
    base_id, family, sev = wcb.INSTANCE_ID.rsplit(":", 2)
    bases = {b["base_id"]: b for b in hb.load_bases("dev", walkers_glob=os.path.join(artifacts_root, "walkers_all.jsonl"))}
    with open(os.path.join(artifacts_root, "thresholds_dev.json"), encoding="utf-8") as fh:
        th = json.load(fh)
    raw = hb.make_instance_v2(bases[base_id], family, int(sev), th)
    if raw is None:
        raise FidelityError("the instance could not be rebuilt (no threshold)")
    return hb.check_eligibility(raw, pool=pool)


def check_instance(inst: dict, recs: dict, pl: dict) -> None:
    a3 = recs["A3"]
    problems = []
    if inst["check"] != pl["check"]:
        problems.append(f"eligibility check {inst['check']} != recorded {pl['check']}")
    if wcb.design_hash({"body": inst["robot"]["body"], "vector": inst["robot"]["vector"]}) != wcb.design_hash(_design(a3, 0)):
        problems.append("the rebuilt nominal design is not the recorded designs[0]")
    if [int(s) for s in inst["seeds"]["obs"]] != pl["experiments"]["observe"]["seeds"]:
        problems.append("the rebuilt obs seeds differ from the recorded experiment seeds")
    for k in ("injected_structure", "strength"):
        if inst.get(k) is not None and inst[k] != pl[k]:
            problems.append(f"{k} {inst[k]} != recorded {pl[k]}")
    if problems:
        raise FidelityError("rebuilt instance differs from the record: " + "; ".join(problems))


@contextlib.contextmanager
def observing(capture: list):
    """Observe hidden_plant.plant_rollout (keep each returned trace) and mujoco.mj_step (copy the state before and after
    every step). Calls pass through unchanged; frozen code is not edited."""
    import mujoco
    import numpy as np

    from creature_forge import hidden_plant as hp
    real_roll, real_step = hp.plant_rollout, mujoco.mj_step
    states = {"pre_qpos": [], "pre_time": [], "post_qpos": [], "post_time": [], "datas": set()}

    def roll(*a, **k):
        tr = real_roll(*a, **k)
        capture.append(tr)
        return tr

    def step(m, d, *a):
        states["datas"].add(id(d))
        states["pre_qpos"].append(np.array(d.qpos, dtype=float, copy=True))
        states["pre_time"].append(float(d.time))
        real_step(m, d, *a)
        states["post_qpos"].append(np.array(d.qpos, dtype=float, copy=True))
        states["post_time"].append(float(d.time))

    hp.plant_rollout, mujoco.mj_step = roll, step
    try:
        yield states
    finally:
        hp.plant_rollout, mujoco.mj_step = real_roll, real_step


def _states(st: dict) -> dict:
    import numpy as np
    return {"pre_qpos": np.array(st["pre_qpos"]), "pre_time": np.array(st["pre_time"]), "post_qpos": np.array(st["post_qpos"]),
            "post_time": np.array(st["post_time"]), "n_data": len(st["datas"])}


def production_features(inst: dict, design: dict, seeds: list, pool) -> dict:
    """Exactly the bench's observe path: hidden_plant.observe on the plant, then belief_engine.obs_features."""
    from creature_forge import belief_engine as be
    from creature_forge import hidden_plant as hp
    return be.obs_features(hp.observe(design["body"], design["vector"], seeds, plant=inst["plant"], pool=pool))


def traced_observe(inst: dict, design: dict, seeds: list, seed: int):
    """One seed of hidden_plant.observe, run through its own observe_job under `observing`. -> (trace, features, states, body)."""
    from creature_forge import belief_engine as be
    from creature_forge import creature_walk as cw
    from creature_forge import hidden_plant as hp
    from creature_forge.arena import VARIATION_PRESET
    i = [int(s) for s in seeds].index(int(seed))
    c = hp._conditions([int(s) for s in seeds], VARIATION_PRESET)[i]
    body = cw._body(design["body"]).as_dict()
    if "pose" in body:
        body["pose"] = list(body["pose"])
    job = {"vector": [float(x) for x in design["vector"]], "body": body, "seed": int(seed), "duration": 10.0,
           "perturb": c["perturb"], "friction_factor": c["friction_factor"], "plant": hp.normalize_plant(inst["plant"])}
    cap: list = []
    with observing(cap) as st:
        out = hp.observe_job(job)
    if not out.get("ok") or len(cap) != 1:
        raise FidelityError(f"traced observe seed {seed}: {out.get('error', f'{len(cap)} rollouts captured')}")
    return cap[0], be.seed_features(out["summary"]), _states(st), body


def traced_validation(inst: dict, design: dict, seeds: list, seed: int):
    """One validation seed through hidden_plant.seed_job (the verifier's job), under `observing`. -> (trace, row, states, body)."""
    import functools

    from creature_forge import hidden_plant as hp
    from creature_forge import recovery
    cap: list = []
    with observing(cap) as st:
        rows = recovery.run_walk_seeds(design["body"], design["vector"], [int(seed)], duration=10.0,
                                       variation=recovery.VARIATION_PRESET, pool=None,
                                       job_fn=functools.partial(hp.seed_job, plant=hp.normalize_plant(inst["plant"])))
    if len(rows) != 1 or len(cap) != 1:
        raise FidelityError(f"traced validation seed {seed}: {len(rows)} rows / {len(cap)} rollouts")
    return cap[0], rows[0], _states(st), design["body"]


def row_mismatch(a: dict, b: dict, fields) -> list[str]:
    return [f"{k} {a.get(k)!r} != {b.get(k)!r}" for k in fields if a.get(k) != b.get(k)]


def replay(recs: dict, pl: dict, inst: dict, *, pool, production_fn=production_features, verify_fn=None,
           traced_obs_fn=traced_observe, traced_val_fn=traced_validation, frames_fn=None, max_hz: int = 30) -> tuple[list, dict, dict]:
    """All gate layers -> (problems, payloads, fresh verification). Physics functions are injectable for no-physics tests."""
    import do1_demo_export as dx
    from creature_forge import hdb_bench as hb
    verify_fn = verify_fn or (lambda d: hb.verify(inst, d, pool=pool))
    frames_fn = frames_fn or (lambda body, tr, states: dx.frames_from_states(inst, body, tr, states, max_hz))
    check_instance(inst, recs, pl)
    problems, payloads, fresh_v = [], {}, {}
    for name, (arm, i) in EXPERIMENTS.items():
        e = pl["experiments"][name]
        design = experiment_design(recs[arm], i)
        fresh = production_fn(inst, design, e["seeds"], pool)
        if fresh != e["features"]:
            bad = [s for s in e["seeds"] if fresh.get(s) != e["features"].get(s)]
            problems.append(f"production {name}: features differ on seeds {bad}")
        for s in e["seeds"]:
            tr, feat, states, body = traced_obs_fn(inst, design, e["seeds"], s)
            if feat != e["features"].get(s):
                problems.append(f"trace {name} seed {s}: features differ from the record")
                continue
            try:
                fr = frames_fn(body, tr, states)
            except Exception as exc:  # noqa: BLE001 - every frame failure blocks the export
                problems.append(f"frames {name} seed {s}: {exc}")
                continue
            payloads[(name, s)] = (design, body, tr, fr, {"features": feat})
    for name, (arm, idx) in VALIDATION.items():
        r = recs[arm]
        design = _design(r, r["submitted"] if idx is None else idx)
        if name != "nominal":
            v = verify_fn(design)
            fresh_v[name] = v
            got = {k: v[k] for k in ("status", "reasons")} | {"walking_frac": v["validation"]["walking_frac"]}
            if got != pl["validation"][name]["recorded"]:
                problems.append(f"verification {name}: {got} != recorded {pl['validation'][name]['recorded']}")
    if "a3_submitted" in fresh_v and "a1e_submitted" in fresh_v and \
            fresh_v["a3_submitted"]["validation"]["original"] != fresh_v["a1e_submitted"]["validation"]["original"]:
        problems.append("the nominal design's validation rows differ between the two verifications")
    rows = {"nominal": (fresh_v.get("a3_submitted") or {}).get("validation", {}).get("original") or [],
            "a3_submitted": (fresh_v.get("a3_submitted") or {}).get("validation", {}).get("candidate") or [],
            "a1e_submitted": (fresh_v.get("a1e_submitted") or {}).get("validation", {}).get("candidate") or []}
    for name, (arm, idx) in VALIDATION.items():
        r = recs[arm]
        design = _design(r, r["submitted"] if idx is None else idx)
        seeds = [int(x["seed"]) for x in rows[name]]
        for prow in rows[name]:
            tr, trow, states, body = traced_val_fn(inst, design, seeds, int(prow["seed"]))
            bad = row_mismatch(trow, prow, ("seed", "outcome", "score", "walking", "fell", "label", "fall_time", "forward_disp_upright"))
            if bad:
                problems.append(f"trace {name} seed {prow['seed']}: " + ", ".join(bad))
                continue
            try:
                fr = frames_fn(body, tr, states)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"frames {name} seed {prow['seed']}: {exc}")
                continue
            payloads[(name, int(prow["seed"]))] = (design, body, tr, fr, {"row": prow})
    return problems, payloads, fresh_v


def fall_of(features: dict) -> dict:
    """Fall event of an experiment rollout from its recorded features (time upright < 10 s means it fell then)."""
    t = features.get("time_upright")
    fell = t is not None and t < 10.0 - 1e-9
    return {"fell": fell, "fall_time": t if fell else None}


def smoke(recs: dict, pl: dict, inst: dict, *, pool, production_fn=production_features, traced_obs_fn=traced_observe,
          frames_fn=None, max_hz: int = 30) -> dict:
    """Exact diagnostic smoke test, nothing written: instance gate, all three experiments on the production path
    (per-seed features ==), and one traced seed of Nemotron's experiment with the frame/FK checks."""
    import do1_demo_export as dx
    frames_fn = frames_fn or (lambda body, tr, states: dx.frames_from_states(inst, body, tr, states, max_hz))
    check_instance(inst, recs, pl)
    problems = []
    for name, (arm, i) in EXPERIMENTS.items():
        e = pl["experiments"][name]
        fresh = production_fn(inst, experiment_design(recs[arm], i), e["seeds"], pool)
        if fresh != e["features"]:
            problems.append(f"production {name}: features differ on seeds {[s for s in e['seeds'] if fresh.get(s) != e['features'].get(s)]}")
    e = pl["experiments"]["x1_nem"]
    design = experiment_design(recs["A3"], 1)
    tr, feat, states, body = traced_obs_fn(inst, design, e["seeds"], e["seeds"][0])
    fk = None
    if feat != e["features"][e["seeds"][0]]:
        problems.append("trace x1_nem: features differ from the record")
    else:
        try:
            fk = frames_fn(body, tr, states)["fk_max_err_m"]
        except Exception as exc:  # noqa: BLE001
            problems.append(f"frames x1_nem: {exc}")
    return {"passed": not problems, "problems": problems, "experiments_checked": len(EXPERIMENTS), "fk_max_err_m": fk}


def write_export(pl: dict, payloads: dict, fresh_v: dict, out_dir: str, environment: dict, approved_by: str, max_hz: int) -> dict:
    """Transactional, as the DO-1 exporter: temporary sibling directory, verified against its own SHA256SUMS, then renamed."""
    import do1_demo_export as dx
    if os.path.exists(out_dir):
        raise FidelityError(f"{out_dir} exists; refusing to overwrite an export")
    index = {"schema": "w2_plant_replays_v1", "exporter": EXPORTER_VERSION, "instance": wcb.INSTANCE_ID,
             "approved_by": approved_by, "environment": environment, "frame_state": "pre-step", "max_hz": max_hz,
             "plant": "hidden (instance plant applied): the damaged robot",
             "fidelity": {"experiments": "per-seed features equal to the record (production and trace paths)",
                          "validation": "status, walking fraction and reasons equal to the record (Stage 2 stored no per-seed "
                                        "verification rows); each trace equal to this run's production row",
                          "fk_tol_m": FK_TOL_M,
                          "fk_max_err_m": max(p[3]["fk_max_err_m"] for p in payloads.values())},
             "experiments": {k: {kk: v[kk] for kk in ("arm", "id", "seeds", "design_hash")} for k, v in pl["experiments"].items()},
             "validation": {k: {"design_hash": pl["validation"][k]["design_hash"],
                                "rows": [{f: r.get(f) for f in ("seed", "outcome", "score", "walking", "fell", "label", "fall_time")}
                                         for r in ((fresh_v.get("a3_submitted") or {}).get("validation", {}).get("original") or [] if k == "nominal"
                                                   else fresh_v[k]["validation"]["candidate"])]} for k in VALIDATION},
             "files": {}}
    parent = os.path.dirname(os.path.abspath(out_dir))
    os.makedirs(parent, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".w2plant_tmp_", dir=parent)
    try:
        os.makedirs(os.path.join(tmp, "payloads"))
        for (name, seed), (design, body, tr, fr, ev) in sorted(payloads.items()):
            p = dx.payload(name, design, body, seed, 10.0, tr, fr, ev.get("row") or fall_of(ev["features"]))
            p["w2_demo"] = {**p.pop("do1_demo"), "evidence": ev, "plant": index["plant"]}
            rel = f"payloads/{name}_{seed}.json"
            with open(os.path.join(tmp, rel), "w", encoding="utf-8", newline="\n") as fh:
                json.dump(p, fh, separators=(",", ":"), allow_nan=False)
            index["files"][f"{name}/{seed}"] = rel
        with open(os.path.join(tmp, "index.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(index, fh, indent=1, allow_nan=False)
        rels = ["index.json", *sorted(index["files"].values())]
        sums = {rel: sha256_file(os.path.join(tmp, rel)) for rel in rels}
        with open(os.path.join(tmp, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(f"{h} *{rel}\n" for rel, h in sums.items()))
        os.replace(tmp, out_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return index


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--execute", action="store_true", help="run the physics and write the export (needs owner approval)")
    ap.add_argument("--smoke", action="store_true", help="exact diagnostic smoke test with physics; writes nothing")
    ap.add_argument("--approved-by", default=None)
    ap.add_argument("--artifacts-root", default=None)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args(argv)
    _, recs = wcb.load_excerpt()
    pl = plan(recs)
    if not (a.execute or a.smoke):
        print(json.dumps({k: v for k, v in pl.items() if k != "experiments"} |
                         {"experiments": {k: {kk: v[kk] for kk in ("arm", "id", "seeds", "design_hash")} for k, v in pl["experiments"].items()},
                          "out": a.out, "mode": "dry run: nothing simulated"}, indent=1))
        return 0
    if not a.approved_by or not a.artifacts_root:
        print("refusing: --execute/--smoke need --approved-by and --artifacts-root", file=sys.stderr)
        return 2
    env = current_environment()
    probs = environment_problems(env)
    if probs:
        print("refusing: not the recorded environment:\n  " + "\n  ".join(probs), file=sys.stderr)
        return 2
    from creature_forge.forge_pool import ForgePool
    with ForgePool(a.workers) as pool:
        inst = build_instance(a.artifacts_root, pool=pool)
        if a.smoke:
            res = smoke(recs, pl, inst, pool=pool)
            print(json.dumps(res, indent=1))
            return 0 if res["passed"] else 1
        problems, payloads, fresh_v = replay(recs, pl, inst, pool=pool)
    if problems:
        print(f"FIDELITY FAILED ({len(problems)}); nothing written:\n  " + "\n  ".join(problems[:40]), file=sys.stderr)
        return 1
    idx = write_export(pl, payloads, fresh_v, os.path.join(ROOT, a.out), env, a.approved_by, 30)
    print(json.dumps({"written": a.out, "payloads": len(idx["files"]), "fk_max_err_m": idx["fidelity"]["fk_max_err_m"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
