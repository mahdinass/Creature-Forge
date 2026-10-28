"""No-physics tests of the DO-1 demo exporter (scripts/do1_demo_export.py).

They read the committed, audited DO1-L4-r0 record and drive the fidelity gate with fake replays. No dynamics are
simulated: hidden_plant.plant_rollout and recovery.run_walk_seeds are patched to fail if anything reaches them. The
pose tests use MuJoCo forward kinematics only (mj_kinematics on a built model).
"""
from __future__ import annotations

import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)

import do1_demo_export as dx  # noqa: E402

RECORD = os.path.join(ROOT, dx.RECORD_REL)
LINUX_ENV = {"system": "Linux", "machine": "x86_64", "python": "3.12.3", "numpy": "2.5.4", "mujoco": "3.15.0"}


def _no_physics(*a, **k):
    raise AssertionError("a no-physics test reached a simulation")


class _Fixture:
    loaded = dx.load_record(RECORD)
    st = dx.stored_rows(loaded)


def _inst(st, loaded, **over):
    faulty = dx.designs_of(loaded)["faulty"]
    inst = {"seeds": {"validate": list(st["seeds"]["validate"]), "confirm": list(st["seeds"]["confirm"])},
            "robot": {"body": faulty["body"], "vector": faulty["vector"]}, "plant": {"deviation": []}}
    inst.update(over)
    return inst


def _fakes(st, *, bad_production=None, bad_trace=None, bad_frames=None):
    """Replays that return the stored rows, optionally with one field changed (to prove the gate fails closed)."""
    stored = {"validate": {k: st["rows"][k] for k in dx.DESIGNS}, "confirm": {"do1": st["rows"]["do1_confirm"]}}

    def which(design, seeds):
        name = next(k for k, v in dx.designs_of(_Fixture.loaded).items() if dx.ta1.design_hash(v) == dx.ta1.design_hash(design))
        part = "confirm" if list(seeds) == st["seeds"]["confirm"][:len(seeds)] and len(seeds) and seeds[0] == st["seeds"]["confirm"][0] else "validate"
        return name, part

    def production(inst, design, seeds, duration, variation, pool):
        name, part = which(design, seeds)
        rows = copy.deepcopy([r for r in stored[part][name] if r["seed"] in seeds])
        if bad_production and bad_production[0] == (name, part):
            rows[bad_production[1]]["score"] = rows[bad_production[1]]["score"] + 1e-12
        return rows

    def traced(inst, design, seeds, seed, duration, variation):
        name, part = which(design, seeds)
        row = copy.deepcopy(next(r for r in stored[part][name] if r["seed"] == seed))
        trow = {k: row[k] for k in dx.METRIC_FIELDS + ("seed", "walking", "perturb", "push_time", "friction_used")}
        if bad_trace and bad_trace == (name, part, seed):
            trow["label"] = "fall" if trow["label"] != "fall" else "walking"
        return {"t": [0.0, duration]}, trow, design["body"], {"name": name, "part": part, "seed": seed}

    def frames(inst, body, tr, states, max_hz):
        if bad_frames and bad_frames == (states["name"], states["part"], states["seed"]):
            raise dx.FidelityError("logged pitch / joint angles differ from the observed post-step state")
        return {"fk_max_err_m": 0.0}

    def payload(name, design, body, seed, duration, tr, fr, row):
        return {"seed": seed, "do1_demo": {"design": name, "fk_max_err_m": fr["fk_max_err_m"], "evidence_row": row}}

    return {"production_fn": production, "traced_fn": traced, "frames_fn": frames, "payload_fn": payload}


@mock.patch("creature_forge.hidden_plant.plant_rollout", _no_physics)
@mock.patch("creature_forge.recovery.run_walk_seeds", _no_physics)
class Do1DemoExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="do1demo_test_")
        self.loaded, self.st = _Fixture.loaded, _Fixture.st

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _leftovers(self):
        return [p for p in os.listdir(self.tmp) if p.startswith(".do1demo_tmp_")]

    def test_record_hash_refusal(self):
        bad = os.path.join(self.tmp, "do1_l4_r0.jsonl")
        shutil.copy(RECORD, bad)
        shutil.copy(dx.ta1.manifest_path(RECORD), dx.ta1.manifest_path(bad))
        self.assertEqual(dx.load_record(bad)["manifest"]["phase"], "DO1-L4-r0")   # an exact copy passes
        with open(bad, "ab") as fh:
            fh.write(b"\n")
        with self.assertRaisesRegex(dx.FidelityError, "not the audited"):
            dx.load_record(bad)

    def test_designs_and_hashes(self):
        d = dx.designs_of(self.loaded)
        self.assertEqual({k: dx.ta1.design_hash(v) for k, v in d.items() if k != "faulty"}, dx.DESIGN_HASHES)
        self.assertEqual(len(d["faulty"]["vector"]), 17)

    def test_aggregates_match_the_audit(self):
        agg = dx.aggregates(self.st)
        self.assertEqual((agg["walking"]["frozen"], agg["walking"]["do1"], agg["walking"]["do1_confirm"]), (19, 21, 22))
        self.assertAlmostEqual(agg["median_score_m"]["faulty"], 2.336818, places=6)
        self.assertAlmostEqual(agg["median_score_m"]["frozen"], 3.429721, places=6)
        self.assertAlmostEqual(agg["median_score_m"]["do1"], 3.052606, places=6)
        self.assertEqual(agg["status"], {"frozen": "PARTIAL_IMPROVEMENT", "do1": "FULL_RECOVERY"})

    def test_default_seed_rule(self):
        s = dx.default_seed(self.st["rows"])
        fr = next(r for r in self.st["rows"]["frozen"] if r["seed"] == s)
        do = next(r for r in self.st["rows"]["do1"] if r["seed"] == s)
        self.assertFalse(fr["walking"])
        self.assertTrue(do["walking"])
        earlier = [i for i, r in enumerate(self.st["rows"]["frozen"]) if r["seed"] == s][0]
        for f, d in zip(self.st["rows"]["frozen"][:earlier], self.st["rows"]["do1"][:earlier]):
            self.assertFalse(not f["walking"] and d["walking"])
        with self.assertRaises(dx.FidelityError):
            dx.default_seed({"frozen": [{"seed": 1, "walking": True}], "do1": [{"seed": 1, "walking": True}]})

    def test_row_mismatches_are_exact(self):
        rows = self.st["rows"]["do1"]
        self.assertEqual(dx.row_mismatches(rows, copy.deepcopy(rows)), [])
        tweaked = copy.deepcopy(rows)
        tweaked[3]["score"] += 1e-15
        self.assertEqual(len(dx.row_mismatches(rows, tweaked)), 1)
        self.assertIn("seed lists differ", dx.row_mismatches(rows, rows[:-1])[0])
        self.assertIn("seed lists differ", dx.row_mismatches(rows, rows + rows[:1])[0])

    def test_jobs_full_and_smoke(self):
        full = dx.jobs_of(self.st)
        self.assertEqual([(j[0], len(j[1]), j[2]) for j in full], [("faulty", 24, 10.0), ("frozen", 24, 10.0), ("do1", 24, 10.0), ("do1", 24, 20.0)])
        sm = dx.jobs_of(self.st, dx.SMOKE_SEEDS)
        self.assertEqual([len(j[1]) for j in sm], [2, 2, 2, 2])
        self.assertEqual(sm[0][1], self.st["seeds"]["validate"][:2])
        self.assertEqual(sm[3][1], self.st["seeds"]["confirm"][:2])
        self.assertEqual([r["seed"] for r in sm[3][3]], self.st["seeds"]["confirm"][:2])

    def test_smoke_passes_on_exact_rows_and_writes_nothing(self):
        res = dx.smoke(self.loaded, self.st, _inst(self.st, self.loaded), pool=None, **_fakes(self.st))
        self.assertTrue(res["passed"])
        self.assertEqual((res["rows_checked"], res["framed"]), (8, 8))
        self.assertEqual(os.listdir(self.tmp), [])

    def test_smoke_fails_on_any_mismatch(self):
        res = dx.smoke(self.loaded, self.st, _inst(self.st, self.loaded), pool=None,
                       **_fakes(self.st, bad_production=(("do1", "validate"), 1)))
        self.assertFalse(res["passed"])
        self.assertIn("production do1 10s", res["problems"][0])

    def test_export_writes_only_when_every_row_matches(self):
        out = os.path.join(self.tmp, "demo")
        index = dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None, environment=LINUX_ENV, **_fakes(self.st))
        self.assertEqual(index["fidelity"]["trace_rows_exact"], 96)
        self.assertEqual(index["default_seed"], dx.default_seed(self.st["rows"]))
        self.assertEqual(len(index["files"]), 96)
        self.assertEqual(index["frame_state"], "pre-step")
        self.assertEqual(index["provenance"]["environment"], LINUX_ENV)
        with open(os.path.join(out, "index.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["provenance"]["arms_provenance"], "NO_AI (A1e6, no Nemotron)")
        with open(os.path.join(out, "SHA256SUMS"), encoding="utf-8") as fh:
            sums = [ln.split(" *") for ln in fh.read().splitlines()]
        self.assertEqual(len(sums), 97)
        for h, rel in sums:
            self.assertEqual(dx.sha256_file(os.path.join(out, rel)), h)
        self.assertIn(dx.CAPTIONS["attribution"], json.dumps(index))
        self.assertEqual(self._leftovers(), [])
        with self.assertRaisesRegex(dx.FidelityError, "refusing to overwrite"):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None, **_fakes(self.st))

    def test_production_mismatch_writes_nothing(self):
        out = os.path.join(self.tmp, "demo")
        with self.assertRaisesRegex(dx.FidelityError, "production frozen"):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None,
                      **_fakes(self.st, bad_production=(("frozen", "validate"), 5)))
        self.assertFalse(os.path.exists(out))
        self.assertEqual(self._leftovers(), [])

    def test_trace_mismatch_writes_nothing(self):
        out = os.path.join(self.tmp, "demo")
        seed = self.st["seeds"]["confirm"][7]
        with self.assertRaisesRegex(dx.FidelityError, "trace do1 20s"):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None,
                      **_fakes(self.st, bad_trace=("do1", "confirm", seed)))
        self.assertFalse(os.path.exists(out))

    def test_frame_check_failure_writes_nothing(self):
        out = os.path.join(self.tmp, "demo")
        seed = self.st["seeds"]["validate"][11]
        with self.assertRaisesRegex(dx.FidelityError, "frames frozen 10s seed"):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None,
                      **_fakes(self.st, bad_frames=("frozen", "validate", seed)))
        self.assertFalse(os.path.exists(out))

    def test_failure_while_writing_publishes_nothing(self):
        out = os.path.join(self.tmp, "demo")
        fakes = _fakes(self.st)
        good_payload = fakes["payload_fn"]

        def poisoned(name, design, body, seed, duration, tr, fr, row):
            p = good_payload(name, design, body, seed, duration, tr, fr, row)
            if name == "do1" and duration == 20.0 and seed == self.st["seeds"]["confirm"][-1]:
                p["bad"] = float("nan")          # json.dump(allow_nan=False) fails on the last file
            return p
        fakes["payload_fn"] = poisoned
        with self.assertRaises(ValueError):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None, **fakes)
        self.assertFalse(os.path.exists(out))
        self.assertEqual(self._leftovers(), [])

    def test_instance_must_match_the_record(self):
        out = os.path.join(self.tmp, "demo")
        wrong = _inst(self.st, self.loaded)
        wrong["seeds"]["validate"] = wrong["seeds"]["validate"][::-1]
        with self.assertRaisesRegex(dx.FidelityError, "verification seeds"):
            dx.export(self.loaded, self.st, wrong, out, pool=None, **_fakes(self.st))
        d = dx.designs_of(self.loaded)["do1"]
        with self.assertRaisesRegex(dx.FidelityError, "nominal robot"):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded, robot=d), out, pool=None, **_fakes(self.st))

    def test_environment_gate(self):
        man = self.loaded["manifest"]
        self.assertEqual(dx.environment_problems(man, LINUX_ENV), [])
        win = {"system": "Windows", "machine": "AMD64", "python": "3.11.9", "numpy": "2.4.6", "mujoco": "3.15.0"}
        probs = dx.environment_problems(man, win)
        self.assertEqual(len(probs), 4)
        self.assertTrue(any(p.startswith("numpy") for p in probs))
        self.assertEqual(len(dx.environment_problems(man, {**LINUX_ENV, "numpy": "2.5.5"})), 1)

    def test_dry_run_simulates_nothing(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dx.main(["--out", os.path.join(self.tmp, "demo")])
        self.assertEqual(rc, 0)
        self.assertIn("Dry run: nothing was simulated", buf.getvalue())
        self.assertIn("walking 21/24", buf.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "demo")))

    def test_physics_modes_refuse_without_approval_inputs_or_recorded_environment(self):
        for flag in ("--execute", "--smoke"):
            buf = io.StringIO()
            with redirect_stdout(buf), mock.patch.object(dx, "current_environment", return_value={**LINUX_ENV, "system": "Windows"}):
                rc = dx.main([flag, "--out", os.path.join(self.tmp, "demo")])
            self.assertEqual(rc, 2)
            text = buf.getvalue()
            self.assertIn("--approved-by is required", text)
            self.assertIn("--artifacts-root is required", text)
            self.assertIn("system: this environment has 'Windows'", text)


class StepAlignmentTests(unittest.TestCase):
    """align_states / record_steps on synthetic step sequences (no simulation)."""

    @staticmethod
    def _states(n=12, log_every=5):
        rng = np.random.default_rng(0)
        q = np.cumsum(rng.normal(size=(n + 1, 9)), axis=0)
        t = np.arange(n + 1) * 0.001
        states = {"pre_qpos": q[:-1], "pre_time": t[:-1], "post_qpos": q[1:], "post_time": t[1:], "n_data": 1}
        idx = np.arange(0, n, log_every)
        tr = {"t": t[1:][idx], "pitch": q[1:][idx, 2], "q": q[1:][idx, 3:9]}
        return states, tr, idx

    def test_aligned_samples_are_the_pre_step_states(self):
        states, tr, idx = self._states()
        al = dx.align_states(tr, states, log_every=5)
        np.testing.assert_array_equal(al["qpos"], states["pre_qpos"][idx])
        np.testing.assert_array_equal(al["t"], states["pre_time"][idx])
        self.assertEqual(len(al["t"]), 3)

    def test_sample_count_timestamp_pose_and_continuity_are_enforced(self):
        cases = {
            "logged samples": lambda s, tr: tr.update(t=tr["t"][:-1], pitch=tr["pitch"][:-1], q=tr["q"][:-1]),
            "timestamps": lambda s, tr: tr.update(t=tr["t"] + np.array([0.0, 1e-12, 0.0])),
            "pitch / joint": lambda s, tr: tr["q"].__setitem__((1, 2), tr["q"][1, 2] + 1e-12),
            "did not start": lambda s, tr: s["pre_qpos"].__setitem__((7, 0), s["pre_qpos"][7, 0] + 1e-12),
            "one stepped MjData": lambda s, tr: s.update(n_data=2),
        }
        for msg, mutate in cases.items():
            states, tr, _ = self._states()
            states = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in states.items()}
            tr = {k: v.copy() for k, v in tr.items()}
            mutate(states, tr)
            with self.assertRaisesRegex(dx.FidelityError, msg):
                dx.align_states(tr, states, log_every=5)

    def test_record_steps_observes_without_changing_the_step(self):
        import mujoco
        calls = []

        def fake_step(m, d):
            calls.append(1)
            d.qpos = d.qpos + 1.0
            d.time += 0.001

        d = SimpleNamespace(qpos=np.zeros(9), time=0.0)
        with mock.patch.object(mujoco, "mj_step", fake_step):
            out, states = dx.record_steps(lambda: [mujoco.mj_step(None, d) for _ in range(3)] and "done")
            self.assertIs(mujoco.mj_step, fake_step)                        # restored after the run
        self.assertEqual((out, len(calls), states["n_data"]), ("done", 3, 1))
        np.testing.assert_array_equal(states["pre_qpos"][:, 0], [0.0, 1.0, 2.0])
        np.testing.assert_array_equal(states["post_qpos"][:, 0], [1.0, 2.0, 3.0])
        np.testing.assert_allclose(states["post_time"], [0.001, 0.002, 0.003])


class FramePoseTests(unittest.TestCase):
    """frames_from_states and payload on a real model with kinematics only (mj_kinematics, no mj_step)."""

    @classmethod
    def setUpClass(cls):
        import mujoco
        from creature_forge import creature_walk as cw
        from creature_forge import hidden_plant as hp
        from creature_forge.morphology import build_model
        body = dx.designs_of(_Fixture.loaded)["do1"]["body"]
        cls.inst = {"plant": {"deviation": []}}
        model = build_model(cw._body(hp.plant_body(cw._body(body).as_dict(), [])))
        data = mujoco.MjData(model)
        torso = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
        feet = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"foot_{s}") for s in "lr"]
        n_steps, log_every = 60, 5
        t = np.arange(n_steps + 1) * 0.001
        q = np.zeros((n_steps + 1, model.nq))
        q[:, 0] = np.linspace(0.0, 0.05, n_steps + 1)
        q[:, 2] = 0.1 * np.sin(np.linspace(0, 3, n_steps + 1))
        q[:, 3:9] = 0.2 * np.sin(np.linspace(0, 3, n_steps + 1))[:, None] * np.array([1, -1, 0.5, -0.5, 0.3, -0.3])
        cls.states = {"pre_qpos": q[:-1], "pre_time": t[:-1], "post_qpos": q[1:], "post_time": t[1:], "n_data": 1}
        idx = np.arange(0, n_steps, log_every)
        tr = {k: [] for k in ("x", "z", "foot_x", "foot_z")}
        for k in idx:                                      # logged positions = kinematics of the pre-step state
            data.qpos[:] = q[k]
            mujoco.mj_kinematics(model, data)
            tr["x"].append(data.xpos[torso][0])
            tr["z"].append(data.xpos[torso][2])
            tr["foot_x"].append([data.geom_xpos[g][0] for g in feet])
            tr["foot_z"].append([data.geom_xpos[g][2] for g in feet])
        m = len(idx)
        tr = {k: np.asarray(v, dtype=float) for k, v in tr.items()}
        tr.update(t=t[1:][idx], pitch=q[1:][idx, 2], q=q[1:][idx, 3:9], force=np.zeros((m, 2)), slip=np.zeros((m, 2)),
                  tau=np.zeros((m, 6)), meta={"weight": 300.0, "torque_limit": 100.0})
        cls.tr, cls.body = tr, body

    def test_pose_is_exact_and_payload_is_consistent(self):
        fr = dx.frames_from_states(self.inst, self.body, self.tr, self.states, max_hz=200)
        self.assertEqual(fr["fk_max_err_m"], 0.0)
        self.assertEqual((fr["n_steps"], fr["n_samples"]), (60, 12))
        row = {"fell": False, "fall_time": None}
        p = dx.payload("do1", dx.designs_of(_Fixture.loaded)["do1"], self.body, 1, 10.0, self.tr, fr, row)
        n = len(p["time"])
        self.assertEqual(n, len(p["frames"]["pos"]))
        self.assertEqual(n, len(p["frames"]["quat"]))
        self.assertEqual(n, len(p["series"]["torso_pitch"]))
        self.assertEqual(len(p["frames"]["pos"][0]), len(p["scene"]["geoms"]))
        self.assertTrue(all(b > a for a, b in zip(p["time"], p["time"][1:])))
        self.assertAlmostEqual(p["time"][-1], round(self.states["pre_time"][55], 4))   # last logged sample kept
        self.assertEqual(p["series"]["torso_pitch"], np.round(self.states["pre_qpos"][::5, 2], 4).tolist())
        self.assertEqual(p["do1_demo"]["frame_state"], "pre-step")

    def test_post_step_pose_or_a_moved_foot_fails(self):
        moved = {**self.tr, "foot_x": self.tr["foot_x"].copy()}
        moved["foot_x"][4, 1] += 1e-6
        with self.assertRaisesRegex(dx.FidelityError, "forward kinematics"):
            dx.frames_from_states(self.inst, self.body, moved, self.states, max_hz=200)
        shifted = {**self.states, "pre_qpos": self.states["post_qpos"], "post_qpos": np.vstack([self.states["post_qpos"][1:], self.states["post_qpos"][-1:]])}
        with self.assertRaises(dx.FidelityError):
            dx.frames_from_states(self.inst, self.body, self.tr, shifted, max_hz=200)


if __name__ == "__main__":
    unittest.main()
