"""DO-1 demo export: the L4 robot as it really ran in DO1-L4-r0. Faulty design, frozen-optimizer repair and DO-1 repair, all
on the hidden plant, as Studio viewer payloads. Every rendered frame is checked against the audited experiment record.

Source of truth: experiments/do1/l4_r0/do1_l4_r0.jsonl. The exporter refuses unless this file and its manifest match the
SHA-256 values from the independent audit. Instance hdb-v1-gen-0137:low_ground_friction:0, harness commit e9d2379.
  faulty   designs[0] (identical in both arms; the verifier's "original")
  frozen   the frozen arm's submitted design (design hash 66053dae8e): PARTIAL_IMPROVEMENT, 19/24 walking
  do1      the DO-1 arm's submitted design (design hash 9aa66e0f04): FULL_RECOVERY, 21/24 walking, 20 s confirmation 22/24
No Nemotron was involved: both arms are A1e6 (provenance NO_AI). This is one technical replicate on one robot, not a rate.

Fidelity gate (fail-closed; nothing is written unless every check passes):
  1. production path: recovery.run_walk_seeds with job_fn = hidden_plant.seed_job on the instance's plant, under the
     stored variation preset. This is exactly what hidden_plant.verify runs. Every stored per-seed field must be equal
     (==, no tolerance): 3 designs x 24 validation seeds, plus DO-1 on the 24 confirmation seeds (20 s).
  2. frame path: the same per-seed job is rebuilt and run with hidden_plant.plant_rollout exactly as seed_job calls it.
     That trace must give the same row. While it runs, mujoco.mj_step is only observed: the state before and after every
     step is copied. No frozen code changes.
     - Why pre-step: inside one mj_step the kinematics, contacts and forces are computed from the state *before*
       integration, and qpos/time are advanced afterwards. The trace therefore logs torso x/z, foot positions and
       forces from the pre-step state, but pitch, joint angles and t after the step.
     - Frames are rendered from the single, consistent pre-step state of every logged step.
     - Checks: sample count; logged t, pitch and q equal to the post-step state of the same step; step-to-step
       continuity (each step starts where the previous one ended); one stepped MjData; and forward kinematics of the
       pre-step qpos reproducing the logged torso and foot positions (<= 1e-9 m).
  3. environment: --execute and --smoke refuse unless OS, machine, Python, numpy and MuJoCo equal the recorded run
     (Linux x86_64, 3.12.3 / 2.5.4 / 3.15.0). Windows does not reproduce the Linux per-seed rows (2026-10-21, W1a).
     The dry run and the no-physics tests work anywhere.
Output is written to a temporary directory next to --out. It is verified against its own SHA256SUMS, then renamed into
place; on any failure nothing is published. Frozen modules are imported, never edited (tests/test_frozen_paths.py).

  python scripts/do1_demo_export.py                          # dry run (default): plan from the stored record; nothing simulated
  python scripts/do1_demo_export.py --smoke   --approved-by "<owner, date>" --artifacts-root <dir> [--workers 2]
  python scripts/do1_demo_export.py --execute --approved-by "<owner, date>" --artifacts-root <dir> [--workers 2]
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import platform
import shutil
import statistics
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ta1_tool_access as ta1  # noqa: E402

EXPORTER_VERSION = "do1_demo_export_v2"   # v2: pre-step frame state, alignment checks, environment gate, smoke mode
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD_REL = "experiments/do1/l4_r0/do1_l4_r0.jsonl"
RECORD_SHA256 = "00a8db20b9b3ab186b935f2062a9a78d411a4d2a512e289e8aa1e4c39a5e263b"
MANIFEST_SHA256 = "55fe2aa85d772bab7b70623279721ac46de62087246fc9b8b84a5ac2a8fa9a17"
HARNESS_COMMIT = "e9d2379def2546cedcc9ce5c3cc2aa22b9746392"
INSTANCE_ID = "hdb-v1-gen-0137:low_ground_friction:0"
DESIGN_HASHES = {"frozen": "66053dae8e", "do1": "9aa66e0f04"}
DESIGNS = ("faulty", "frozen", "do1")
EXPECTED = {"frozen_walking": 19, "do1_walking": 21, "do1_confirm_walking": 22,
            "frozen_status": "PARTIAL_IMPROVEMENT", "do1_status": "FULL_RECOVERY"}
ROW_FIELDS = ("seed", "outcome", "score", "walking", "fell", "label", "fall_time", "forward_disp_upright", "speed_upright",
              "body_contact_frac", "valid_steps", "error", "perturb", "push_time", "friction_used")
METRIC_FIELDS = ("fell", "label", "fall_time", "forward_disp_upright", "speed_upright", "body_contact_frac", "valid_steps")
FK_TOL_M = 1e-9
SMOKE_SEEDS = 2          # per design: the first 2 validation seeds (and DO-1's first 2 confirmation seeds)
DEFAULT_OUT = "experiments/do1/demo"
CAPTIONS = {
    "attribution": "Deterministic optimizer-objective change (DO-1). No Nemotron in this repair.",
    "scope": "One technical replicate on one robot; not a recovery rate.",
    "seed": "Selected illustrative seed (rule: first validation seed where the frozen repair does not walk and DO-1 does). "
            "Every seed can be inspected; the aggregate counts are the result.",
}


class FidelityError(RuntimeError):
    """A replay disagreed with the experiment record: nothing may be exported."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_record(path: str) -> dict:
    """The two DO1-L4-r0 episodes keyed by arm, after the audited-hash check of the JSONL and its manifest."""
    for p, want in ((path, RECORD_SHA256), (ta1.manifest_path(path), MANIFEST_SHA256)):
        got = sha256_file(p)
        if got != want:
            raise FidelityError(f"{p}: sha256 {got} is not the audited {want}")
    with open(ta1.manifest_path(path), encoding="utf-8") as fh:
        manifest = json.load(fh)
    if manifest.get("git_commit") != HARNESS_COMMIT or manifest.get("phase") != "DO1-L4-r0":
        raise FidelityError(f"manifest pins {manifest.get('git_commit')} / {manifest.get('phase')}, not {HARNESS_COMMIT} / DO1-L4-r0")
    arms = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            arms[rec["harness"]["do1"]["arm"]] = rec
    if sorted(arms) != ["do1", "frozen"] or any(r["instance_id"] != INSTANCE_ID for r in arms.values()):
        raise FidelityError(f"expected one frozen and one do1 episode of {INSTANCE_ID}, got {sorted(arms)}")
    if any(r["provenance"] != "NO_AI" or r["nemotron"] is not None for r in arms.values()):
        raise FidelityError("an episode is not NO_AI; this exporter only shows the engine-only DO-1 pilot")
    return {"manifest": manifest, "arms": arms}


def _design(rec: dict, index: int) -> dict:
    d = next(d for d in rec["designs"] if d["index"] == index)
    return {"body": d["body"], "vector": [float(x) for x in d["vector"]]}


def designs_of(loaded: dict) -> dict:
    """faulty / frozen / do1 designs with their hashes; the faulty design must be identical in both arms."""
    fr, do = loaded["arms"]["frozen"], loaded["arms"]["do1"]
    out = {"faulty": _design(fr, 0), "frozen": _design(fr, fr["submitted"]), "do1": _design(do, do["submitted"])}
    if ta1.design_hash(_design(do, 0)) != ta1.design_hash(out["faulty"]):
        raise FidelityError("the faulty design differs between the two arms")
    for k, want in DESIGN_HASHES.items():
        if ta1.design_hash(out[k]) != want:
            raise FidelityError(f"{k} design hash {ta1.design_hash(out[k])} is not the recorded {want}")
    return out


def stored_rows(loaded: dict) -> dict:
    """The verifier's stored per-seed rows: what every replay must reproduce exactly."""
    fr, do = (loaded["arms"][a]["verification"]["full"] for a in ("frozen", "do1"))
    if fr["seeds"] != do["seeds"] or fr["variation"] != do["variation"]:
        raise FidelityError("the two arms were verified on different seeds or conditions")
    if fr["validation"]["original"] != do["validation"]["original"]:
        raise FidelityError("the faulty robot's validation rows differ between the arms")
    rows = {"faulty": fr["validation"]["original"], "frozen": fr["validation"]["candidate"],
            "do1": do["validation"]["candidate"], "do1_confirm": do["confirmation"]["per_seed"]}
    seeds = {"validate": [int(s) for s in fr["seeds"]["validate"]], "confirm": [int(s) for s in fr["seeds"]["confirm"]]}
    for k in DESIGNS:
        if [r["seed"] for r in rows[k]] != seeds["validate"]:
            raise FidelityError(f"{k}: stored rows are not the 24 validation seeds in order")
    if [r["seed"] for r in rows["do1_confirm"]] != seeds["confirm"]:
        raise FidelityError("do1 confirmation rows are not the confirmation seeds in order")
    return {"rows": rows, "seeds": seeds, "variation": fr["variation"],
            "status": {"frozen": fr["status"], "do1": do["status"]}}


def aggregates(st: dict) -> dict:
    r = st["rows"]
    walk = {k: sum(bool(x["walking"]) for x in r[k]) for k in r}
    med = {k: statistics.median(x["score"] for x in r[k]) for k in r}
    out = {"walking": walk, "median_score_m": med, "n": {k: len(r[k]) for k in r}, "status": st["status"]}
    for k, want in (("frozen", EXPECTED["frozen_walking"]), ("do1", EXPECTED["do1_walking"]),
                    ("do1_confirm", EXPECTED["do1_confirm_walking"])):
        if walk[k] != want:
            raise FidelityError(f"{k}: {walk[k]} walking seeds in the record, expected {want}")
    if st["status"] != {"frozen": EXPECTED["frozen_status"], "do1": EXPECTED["do1_status"]}:
        raise FidelityError(f"recorded statuses {st['status']} are not the audited ones")
    return out


def default_seed(rows: dict) -> int:
    """Pre-declared: the first validation seed (stored order) where the frozen repair does not walk and DO-1 walks."""
    for f, d in zip(rows["frozen"], rows["do1"]):
        if not f["walking"] and d["walking"]:
            return int(f["seed"])
    raise FidelityError("no validation seed where the frozen repair does not walk and DO-1 walks")


def row_mismatches(stored: list, fresh: list, fields=ROW_FIELDS) -> list[str]:
    """Exact comparison (==) of replayed rows with the stored rows, seed by seed."""
    if [r.get("seed") for r in fresh] != [r.get("seed") for r in stored]:
        return [f"seed lists differ: replay {[r.get('seed') for r in fresh]} vs record {[r.get('seed') for r in stored]}"]
    out = []
    for s, f in zip(stored, fresh):
        bad = [k for k in fields if f.get(k) != s.get(k)]
        if bad:
            out.append(f"seed {s['seed']}: " + ", ".join(f"{k} {f.get(k)!r} != {s.get(k)!r}" for k in bad))
    return out


def jobs_of(st: dict, n_seeds: int | None = None) -> list[tuple]:
    """(design, seeds, duration_s, stored rows) per replay group; `n_seeds` keeps only the first n seeds (smoke test)."""
    k = slice(None) if n_seeds is None else slice(0, n_seeds)
    jobs = [(name, st["seeds"]["validate"][k], 10.0, st["rows"][name][k]) for name in DESIGNS]
    jobs.append(("do1", st["seeds"]["confirm"][k], 20.0, st["rows"]["do1_confirm"][k]))
    return jobs


def plan(loaded: dict, st: dict, out_dir: str) -> dict:
    n_val, n_conf = len(st["seeds"]["validate"]), len(st["seeds"]["confirm"])
    per_path = {"rollouts_10s": len(DESIGNS) * n_val, "rollouts_20s": n_conf}
    eq = per_path["rollouts_10s"] + 2 * per_path["rollouts_20s"]
    smoke_eq = 2 * (len(DESIGNS) * SMOKE_SEEDS + 2 * SMOKE_SEEDS)
    return {"instance": INSTANCE_ID, "designs": {k: ta1.design_hash(v) for k, v in designs_of(loaded).items()},
            "seeds": st["seeds"], "variation": st["variation"], "aggregates": aggregates(st),
            "default_seed": default_seed(st["rows"]),
            "rollouts": {"per_path": per_path, "paths": 2, "rollout_equivalents": 2 * eq, "smoke_rollout_equivalents": smoke_eq,
                         "note": "plus 8 eligibility rollouts per instance build (ta1.build_instance, as the runner)"},
            "out": out_dir}


# ---------------------------------------------------------------------------------------------------------
# recorded-environment gate
# ---------------------------------------------------------------------------------------------------------
def current_environment() -> dict:
    import mujoco
    import numpy as np
    return {"system": platform.system(), "machine": platform.machine(), "python": sys.version.split()[0],
            "numpy": np.__version__, "mujoco": mujoco.__version__, "platform": platform.platform()}


def environment_problems(manifest: dict, env: dict) -> list[str]:
    """Differences between this environment and the one that produced the record (empty list = may run physics)."""
    rec_platform = str(manifest.get("platform", ""))
    want = {"system": "Linux" if rec_platform.startswith("Linux") else rec_platform.split("-")[0],
            "machine": "x86_64" if "x86_64" in rec_platform else None,
            "python": manifest.get("python"), "numpy": manifest.get("numpy"), "mujoco": manifest.get("mujoco")}
    return [f"{k}: this environment has {env.get(k)!r}, the record was produced with {v!r}"
            for k, v in want.items() if v is not None and env.get(k) != v]


# ---------------------------------------------------------------------------------------------------------
# physics (only with --smoke / --execute)
# ---------------------------------------------------------------------------------------------------------
def production_rows(inst: dict, design: dict, seeds: list, duration: float, variation: dict, pool) -> list:
    """Exactly hidden_plant.verify's per-seed path (recovery.assess -> run_walk_seeds -> hidden_plant.seed_job)."""
    from creature_forge import hidden_plant as hp
    from creature_forge import recovery
    return recovery.run_walk_seeds(design["body"], design["vector"], seeds, duration=duration, variation=variation,
                                   pool=pool, job_fn=functools.partial(hp.seed_job, plant=hp.normalize_plant(inst["plant"])))


def record_steps(run):
    """Call run() while observing mujoco.mj_step. Every call is passed through unchanged; the state before it (qpos, time)
    and after it is copied. Returns (run's result, states)."""
    import mujoco
    import numpy as np
    pre_q, pre_t, post_q, post_t, datas = [], [], [], [], set()
    real = mujoco.mj_step

    def observed(m, d, *args):
        datas.add(id(d))
        pre_q.append(np.array(d.qpos, dtype=float, copy=True))
        pre_t.append(float(d.time))
        real(m, d, *args)
        post_q.append(np.array(d.qpos, dtype=float, copy=True))
        post_t.append(float(d.time))

    mujoco.mj_step = observed
    try:
        out = run()
    finally:
        mujoco.mj_step = real
    return out, {"pre_qpos": np.array(pre_q), "pre_time": np.array(pre_t), "post_qpos": np.array(post_q),
                 "post_time": np.array(post_t), "n_data": len(datas)}


def align_states(tr: dict, states: dict, log_every: int | None = None) -> dict:
    """The pre-step state of every logged sample, after proving that `states` are the steps that produced `tr`."""
    import numpy as np
    if log_every is None:
        from creature_forge.locomotion import LOG_EVERY as log_every
    pre_q, post_q, pre_t, post_t = states["pre_qpos"], states["post_qpos"], states["pre_time"], states["post_time"]
    n = len(pre_t)
    if states["n_data"] != 1 or n == 0:
        raise FidelityError(f"expected one stepped MjData with at least one step, saw {states['n_data']} / {n} steps")
    if np.any(pre_q[1:] != post_q[:-1]) or np.any(pre_t[1:] != post_t[:-1]):
        raise FidelityError("a step did not start from the state the previous step ended in")
    idx = np.arange(0, n, log_every)
    if len(idx) != len(tr["t"]):
        raise FidelityError(f"{len(tr['t'])} logged samples for {n} steps (expected {len(idx)} at one per {log_every} steps)")
    if not np.array_equal(post_t[idx], np.asarray(tr["t"], dtype=float)):
        raise FidelityError("logged timestamps differ from the observed post-step times")
    if not np.array_equal(post_q[idx, 2], np.asarray(tr["pitch"], dtype=float)) or \
            not np.array_equal(post_q[idx, 3:9], np.asarray(tr["q"], dtype=float)):
        raise FidelityError("logged pitch / joint angles differ from the observed post-step state")
    if not np.all(np.diff(pre_t[idx]) > 0):
        raise FidelityError("pre-step sample times are not strictly increasing")
    return {"qpos": pre_q[idx], "t": pre_t[idx]}


def traced_rollout(inst: dict, design: dict, seeds: list, seed: int, duration: float, variation: dict):
    """The job run_walk_seeds builds for `seed`, run with hidden_plant.plant_rollout exactly as seed_job calls it, under
    record_steps. Returns (trace, row fields recomputed from that trace, the job's body, observed step states)."""
    from creature_forge import creature_walk as cw
    from creature_forge import hidden_plant as hp
    from creature_forge import locomotion as loc
    from creature_forge.arena import _body_with_friction, _condition
    from creature_forge.challenges import ChallengeSpec, _as_body, default_spec
    base = ChallengeSpec.from_dict({**default_spec("walk", [int(s) for s in seeds]).to_dict(), "duration": float(duration)})
    c = _condition(int(seed), base, variation)
    b, used = _body_with_friction(design["body"], c["friction_factor"])
    spec = ChallengeSpec.from_dict({**base.to_dict(), "seeds": [int(seed)], "perturb": c["perturb"], "push_time": c["push_time"]})
    body = _as_body(b)
    tr, states = record_steps(lambda: hp.plant_rollout(
        hp.normalize_plant(inst["plant"]), body.as_dict(), [float(x) for x in design["vector"]], int(seed),
        duration=spec.duration, perturb=spec.perturb, rich=False, settle_s=spec.settle_s))
    m = loc.compute_metrics(tr, cw.creature_criteria(body))
    row = {k: m[k] for k in METRIC_FIELDS}
    row.update({"seed": int(seed), "walking": bool(m["walking"]), "perturb": c["perturb"], "push_time": c["push_time"],
                "friction_used": used})
    return tr, row, body.as_dict(), states


def frames_from_states(inst: dict, body: dict, tr: dict, states: dict, max_hz: int) -> dict:
    """Geom poses by forward kinematics (mj_kinematics; no dynamics) of the pre-step qpos of each logged sample, on the
    plant model. The logged torso and foot positions must be reproduced (<= FK_TOL_M)."""
    import mujoco
    import numpy as np
    from creature_forge import creature_walk as cw
    from creature_forge import hidden_plant as hp
    from creature_forge.challenges import _decimate
    from creature_forge.contact import replay as contact_replay
    from creature_forge.morphology import build_model
    from creature_forge.render_export import export_scene, mj_to_three_pos, mj_to_three_quat
    aligned = align_states(tr, states)
    prims = hp._prims(hp.normalize_plant(inst["plant"]))
    model = build_model(cw._body(hp.plant_body(cw._body(body).as_dict(), prims)))
    data = mujoco.MjData(model)
    if hp.apply_model(model, prims):
        mujoco.mj_setConst(model, data)
    floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    feet = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"foot_{s}") for s in "lr"]
    torso = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
    render = [i for i in range(model.ngeom) if i != floor]
    worst = 0.0
    for i, q in enumerate(aligned["qpos"]):
        data.qpos[:] = q
        mujoco.mj_kinematics(model, data)
        worst = max(worst, abs(data.xpos[torso][0] - tr["x"][i]), abs(data.xpos[torso][2] - tr["z"][i]),
                    *(abs(data.geom_xpos[g][0] - tr["foot_x"][i][k]) for k, g in enumerate(feet)),
                    *(abs(data.geom_xpos[g][2] - tr["foot_z"][i][k]) for k, g in enumerate(feet)))
    if worst > FK_TOL_M:
        raise FidelityError(f"forward kinematics of the pre-step state differs from the logged torso/foot positions by {worst:.3g} m")
    _, _, deb = contact_replay(tr["t"], tr["force"], tr["meta"]["weight"])
    d = _decimate({**{k: v for k, v in tr.items() if k != "meta"}, "deb": deb, "qpos": aligned["qpos"],
                   "t_pre": aligned["t"]}, max_hz)
    quat = np.zeros(4)
    pos, qts, cpos = [], [], []
    for q in d["qpos"]:
        data.qpos[:] = q
        mujoco.mj_kinematics(model, data)
        xq = []
        for g in render:
            mujoco.mju_mat2Quat(quat, data.geom_xmat[g])
            xq.append(mj_to_three_quat(quat))
        pos.append([mj_to_three_pos(data.geom_xpos[g]) for g in render])
        qts.append(xq)
        cpos.append([mj_to_three_pos([data.geom_xpos[g][0], data.geom_xpos[g][1], 0.0]) for g in feet])   # presentation only
    return {"scene": export_scene(model), "d": d, "pos": pos, "quat": qts, "contact_pos": cpos, "fk_max_err_m": worst,
            "n_steps": int(len(states["pre_time"])), "n_samples": int(len(aligned["t"]))}


def payload(design_name: str, design: dict, body: dict, seed: int, duration: float, tr: dict, fr: dict, row: dict,
            ndigits: int = 4) -> dict:
    """A viewer RunPayload (studio/src/types.ts) plus the stored evidence row it reproduces. Time, pose and pitch come
    from the pre-step state. Torso x/z, contacts, slip and torque are logged from that same state."""
    import numpy as np
    from creature_forge.optimize import jsonable
    d = fr["d"]
    z = d["z"]
    pitch = d["qpos"][:, 2]
    rnd = lambda a: np.round(np.asarray(a, dtype=float), ndigits).tolist()   # noqa: E731
    events = [{"kind": "fall", "time": row["fall_time"], "evidence": {}}] if row["fell"] else []
    return jsonable({
        "scene": fr["scene"], "body": body, "gait": {"walk_vector": design["vector"]}, "seed": int(seed),
        "duration": float(tr["t"][-1]), "push": None, "sandbox": True,
        "time": np.round(d["t_pre"], 4).tolist(),
        "frames": {"pos": rnd(fr["pos"]), "quat": rnd(fr["quat"]), "contact_pos": rnd(fr["contact_pos"])},
        "series": {"torso_height": rnd(z), "torso_pitch": rnd(pitch), "torso_x": rnd(d["x"]),
                   "foot_contact": np.asarray(d["deb"]).astype(int).tolist(), "foot_slip_speed": rnd(d["slip"]),
                   "max_torque_frac": rnd(np.abs(d["tau"]).max(axis=1) / tr["meta"]["torque_limit"])},
        "events": events,
        "metrics": {"initial_torso_height": float(z[0]), "min_torso_height": float(np.min(z)), "final_torso_height": float(z[-1]),
                    "max_abs_pitch": float(np.max(np.abs(pitch))), "peak_torso_vx": 0.0, "fell": bool(row["fell"])},
        "do1_demo": {"design": design_name, "design_hash": ta1.design_hash(design), "plant": "hidden (instance plant applied)",
                     "duration_s": duration, "frame_state": "pre-step", "evidence_row": row,
                     "fk_max_err_m": fr["fk_max_err_m"], "steps": fr["n_steps"], "logged_samples": fr["n_samples"]}})


def _check_instance(loaded: dict, st: dict, inst: dict) -> None:
    from creature_forge import recovery
    if (recovery.TRAIN_DURATION, recovery.CONFIRM_DURATION) != (10.0, 20.0):
        raise FidelityError(f"verifier durations {recovery.TRAIN_DURATION}/{recovery.CONFIRM_DURATION} are not 10/20 s")
    if st["variation"] != dict(recovery.VARIATION_PRESET):
        raise FidelityError(f"stored variation {st['variation']} is not recovery.VARIATION_PRESET")
    if [int(s) for s in inst["seeds"]["validate"]] != st["seeds"]["validate"] or \
            [int(s) for s in inst["seeds"]["confirm"]] != st["seeds"]["confirm"]:
        raise FidelityError("the rebuilt instance's verification seeds differ from the record")
    if ta1.design_hash({"body": inst["robot"]["body"], "vector": inst["robot"]["vector"]}) != ta1.design_hash(designs_of(loaded)["faulty"]):
        raise FidelityError("the rebuilt instance's nominal robot is not the recorded faulty design")


def replay(loaded: dict, st: dict, inst: dict, jobs: list, *, pool, max_hz: int = 30, production_fn=production_rows,
           traced_fn=traced_rollout, frames_fn=frames_from_states, payload_fn=payload) -> tuple[list, dict]:
    """Both fidelity layers for every (design, seed) in `jobs` -> (problems, payloads). Physics functions are injectable
    so the no-physics tests can drive the gate."""
    _check_instance(loaded, st, inst)
    designs = designs_of(loaded)
    problems, payloads = [], {}
    for name, seeds, duration, stored in jobs:
        fresh = production_fn(inst, designs[name], seeds, duration, st["variation"], pool)
        problems += [f"production {name} {duration:g}s: {p}" for p in row_mismatches(stored, fresh)]
        for s, srow in zip(seeds, stored):
            tr, trow, body, states = traced_fn(inst, designs[name], seeds, s, duration, st["variation"])
            fields = [k for k in trow if k in ROW_FIELDS]
            problems += [f"trace {name} {duration:g}s: {p}" for p in row_mismatches([srow], [trow], fields)]
            try:
                fr = frames_fn(inst, body, tr, states, max_hz)
            except FidelityError as exc:
                problems.append(f"frames {name} {duration:g}s seed {s}: {exc}")
                continue
            payloads[(name, int(duration), int(s))] = payload_fn(name, designs[name], body, s, duration, tr, fr, srow)
    return problems, payloads


def smoke(loaded: dict, st: dict, inst: dict, *, pool, **fns) -> dict:
    """Exact-reproduction smoke test on the first SMOKE_SEEDS seeds of every group. Nothing is written."""
    problems, payloads = replay(loaded, st, inst, jobs_of(st, SMOKE_SEEDS), pool=pool, **fns)
    return {"passed": not problems, "problems": problems, "rows_checked": sum(len(j[1]) for j in jobs_of(st, SMOKE_SEEDS)),
            "framed": len(payloads), "fk_max_err_m": max((p["do1_demo"]["fk_max_err_m"] for p in payloads.values()), default=None)}


def export(loaded: dict, st: dict, inst: dict, out_dir: str, *, pool, max_hz: int = 30, environment: dict | None = None,
           **fns) -> dict:
    """Full replay; writes the export only if all 96 rows and every frame check pass."""
    if os.path.exists(out_dir):
        raise FidelityError(f"{out_dir} exists; refusing to overwrite an export")
    problems, payloads = replay(loaded, st, inst, jobs_of(st), pool=pool, max_hz=max_hz, **fns)
    if problems:
        raise FidelityError(f"{len(problems)} mismatch(es) against the record:\n  " + "\n  ".join(problems[:40]))
    if len(payloads) != sum(len(j[1]) for j in jobs_of(st)):
        raise FidelityError(f"{len(payloads)} payloads for {sum(len(j[1]) for j in jobs_of(st))} replays")
    return _write(loaded, st, out_dir, payloads, max_hz, environment or {})


def _write(loaded: dict, st: dict, out_dir: str, payloads: dict, max_hz: int, environment: dict) -> dict:
    """Transactional: everything goes to a temporary sibling directory, is verified against its own SHA256SUMS, and only
    then is renamed to `out_dir`. On any error the temporary directory is removed and nothing is published."""
    if os.path.exists(out_dir):
        raise FidelityError(f"{out_dir} exists; refusing to overwrite an export")
    rows = st["rows"]
    index = {
        "schema": "do1_demo_v1", "exporter": EXPORTER_VERSION, "instance": INSTANCE_ID,
        "provenance": {"record": RECORD_REL, "record_sha256": RECORD_SHA256, "manifest_sha256": MANIFEST_SHA256,
                       "harness_commit": HARNESS_COMMIT, "arms_provenance": "NO_AI (A1e6, no Nemotron)",
                       "exporter_commit": ta1._git(ROOT, "rev-parse", "HEAD"), "environment": environment},
        "captions": CAPTIONS, "default_seed": default_seed(rows), "aggregates": aggregates(st), "variation": st["variation"],
        "seeds": st["seeds"], "max_hz": max_hz, "frame_state": "pre-step",
        "designs": {k: ta1.design_hash(v) for k, v in designs_of(loaded).items()},
        "rows": {k: [{f: r.get(f) for f in ROW_FIELDS} for r in v] for k, v in rows.items()},
        "fidelity": {"production_rows_exact": sum(len(v) for v in rows.values()), "trace_rows_exact": len(payloads),
                     "fk_max_err_m": max(p["do1_demo"]["fk_max_err_m"] for p in payloads.values()), "fk_tol_m": FK_TOL_M},
        "files": {},
    }
    parent = os.path.dirname(os.path.abspath(out_dir))
    os.makedirs(parent, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".do1demo_tmp_", dir=parent)
    try:
        os.makedirs(os.path.join(tmp, "payloads"))
        for (name, dur, seed), p in sorted(payloads.items()):
            rel = f"payloads/{name}_{dur}s_{seed}.json"
            with open(os.path.join(tmp, rel), "w", encoding="utf-8", newline="\n") as fh:
                json.dump(p, fh, separators=(",", ":"), allow_nan=False)
            index["files"][f"{name}/{dur}/{seed}"] = rel
        with open(os.path.join(tmp, "index.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(index, fh, indent=1, allow_nan=False)
        rels = ["index.json", *sorted(index["files"].values())]
        sums = {rel: sha256_file(os.path.join(tmp, rel)) for rel in rels}
        with open(os.path.join(tmp, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(f"{h} *{rel}\n" for rel, h in sums.items()))
        for rel, h in sums.items():                                   # re-read before publishing
            with open(os.path.join(tmp, rel), encoding="utf-8") as fh:
                json.load(fh)
            if sha256_file(os.path.join(tmp, rel)) != h:
                raise FidelityError(f"{rel} changed while being written")
        if os.path.exists(out_dir):
            raise FidelityError(f"{out_dir} appeared during the export; not overwriting it")
        os.replace(tmp, out_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return index


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--record", default=os.path.normpath(os.path.join(ROOT, RECORD_REL)))
    ap.add_argument("--out", default=os.path.normpath(os.path.join(ROOT, DEFAULT_OUT)))
    ap.add_argument("--artifacts-root", help="directory with thresholds_dev.json and walkers_all.jsonl (as the runner)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="exact-reproduction smoke test, writes nothing (needs approval)")
    mode.add_argument("--execute", action="store_true", help="full replay and export (needs the owner's approval)")
    ap.add_argument("--approved-by", default="")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--max-hz", type=int, default=30)
    a = ap.parse_args(argv)
    try:
        loaded = load_record(a.record)
        st = stored_rows(loaded)
        p = plan(loaded, st, a.out)
    except FidelityError as exc:
        print(f"REFUSED: {exc}")
        return 2
    print(f"{EXPORTER_VERSION}: {p['instance']} (DO1-L4-r0, harness {HARNESS_COMMIT[:7]}, record sha256 {RECORD_SHA256[:8]} OK)")
    agg = p["aggregates"]
    for k, h in p["designs"].items():
        print(f"  {k:7s} design {h}: walking {agg['walking'][k]}/{agg['n'][k]}, median score {agg['median_score_m'][k]:.6f} m")
    print(f"  do1 20 s confirmation: walking {agg['walking']['do1_confirm']}/{agg['n']['do1_confirm']}")
    print(f"  statuses (recorded): {agg['status']}")
    print(f"  validation seeds {p['seeds']['validate'][0]}..{p['seeds']['validate'][-1]} (24), "
          f"confirmation seeds {p['seeds']['confirm'][0]}..{p['seeds']['confirm'][-1]} (24); variation {p['variation']}")
    print(f"  default seed (pre-declared rule): {p['default_seed']}")
    print(f"  planned replays: {p['rollouts']['per_path']} on each of {p['rollouts']['paths']} paths = "
          f"{p['rollouts']['rollout_equivalents']} rollout-equivalents; smoke test {p['rollouts']['smoke_rollout_equivalents']} "
          f"({p['rollouts']['note']})")
    print(f"  output: {p['out']}")
    if not (a.execute or a.smoke):
        print("Dry run: nothing was simulated. --smoke / --execute run physics and need the owner's approval.")
        return 0
    refusals = []
    if not a.approved_by:
        refusals.append("--approved-by is required")
    if not a.artifacts_root:
        refusals.append("--artifacts-root is required")
    if a.execute and os.path.exists(a.out):
        refusals.append(f"{a.out} exists; refusing to overwrite an export")
    env = current_environment()
    refusals += environment_problems(loaded["manifest"], env)
    if refusals:
        print("REFUSED:\n  " + "\n  ".join(refusals))
        return 2
    print(f"  environment matches the record: {env}")
    inputs = ta1.config_inputs(ROOT, a.artifacts_root)
    for name, want in ta1.REFERENCE["artifact_inputs_sha256"].items():
        if ta1.sha256_file(inputs[name]) != want:
            print(f"REFUSED: input {name} ({inputs[name]}) is not the pinned file")
            return 2
    from creature_forge.forge_pool import ForgePool
    with ForgePool(max_workers=a.workers) as pool:
        inst = ta1.build_instance(INSTANCE_ID, inputs, pool=pool)
        try:
            if a.smoke:
                res = smoke(loaded, st, inst, pool=pool, max_hz=a.max_hz)
                print(("SMOKE PASSED: " if res["passed"] else "SMOKE FAILED: ") + json.dumps(res, default=str))
                return 0 if res["passed"] else 1
            index = export(loaded, st, inst, a.out, pool=pool, max_hz=a.max_hz, environment=env)
        except FidelityError as exc:
            print(f"FIDELITY GATE FAILED, nothing written:\n{exc}")
            return 1
    print(f"OK: {index['fidelity']} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
