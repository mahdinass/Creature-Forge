"""P05-SV1-0 implementation self-tests (proposal section 8): correctness gates only, no statistics.

    python -I -B sv1_selftest.py --out <dir>          (local or VM; seconds to a few minutes)

(a) fast path bit-identity against p0.predict / p0.choose_k / sv0_lib.replicate (>= 20 cases), plus the speed ratio
(b) coverage-indicator arithmetic on a closed-form quantile grid      (c) truths: identical policies give exactly 0
(d) record determinism and order independence (shard invariance)      (e) exact admission operating characteristics vs A0
(f) Wilson identities   (g) section-4 partition   (h) half-sampling variance   (i) section-6B verdicts   (j) guard probes
Exit code 0 iff every gated item passes. The timing file is separate and non-deterministic.
"""
import os
import sys

_HERE = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
sys.path.insert(0, _HERE)
import sv1_guard as GD  # noqa: E402

if len(sys.argv) != 3 or sys.argv[1] != "--out":
    raise SystemExit("usage: sv1_selftest.py --out DIR")
OUT = os.path.join(os.path.realpath(sys.argv[2]), "selftest")
GD.install(os.path.realpath(sys.argv[2]))

import json  # noqa: E402
import time  # noqa: E402
from statistics import NormalDist  # noqa: E402

import numpy as np  # noqa: E402

from creature_forge import experience_p0 as p0  # noqa: E402
import sv0_lib as L  # noqa: E402
import sv1_fast as F  # noqa: E402
import sv1_lib as S  # noqa: E402

ITEMS, TIMING = [], {}


def item(name, expected, observed, ok=None):
    ok = (expected == observed) if ok is None else ok
    ITEMS.append({"name": name, "expected": expected, "observed": observed, "result": "PASS" if ok else "FAIL"})


def same_pred(a, b):
    return all(np.array_equal(a[k], b[k]) for k in ("P", "prior", "gate_sim")) and a["k"] == b["k"]


def test_fast():
    cases, datasets, t_p0, t_fast = 0, 0, 0.0, 0.0
    for cell, n in (("B-info", 8), ("B-null", 6), ("A-info", 4), ("A-obs", 2)):
        G, scen = S.CELLS[cell]
        fixed = S.fixed_params(scen)
        for s in range(n):
            X, Q, Y, base = S.dataset(fixed, G, S.rng_for("selftest", cell, "data", s))
            datasets += 1
            sp = p0.Space(X, L.BLOCKS)
            for pol, use in L.POLICIES.items():
                t0 = time.process_time()
                a = p0.predict(sp, use, Y, base, base)
                t1 = time.process_time()
                b = F.predict(sp, use, Y, base, base)
                t2 = time.process_time()
                if G == 28:
                    t_p0, t_fast = t_p0 + (t1 - t0), t_fast + (t2 - t1)
                item(f"(a) fast predict == p0.predict [{cell} s{s} {pol}]", True, same_pred(a, b))
                cases += 1
                if s == 0:
                    relab = 1000 + 7 * base
                    item(f"(a) relabelled fast == p0 [{cell} {pol}]", True,
                         same_pred(p0.predict(sp, use, Y, relab, relab), F.predict(sp, use, Y, relab, relab)))
                    tr = np.arange(len(Y))
                    item(f"(a) fast choose_k == p0.choose_k on all G [{cell} {pol}]",
                         p0.choose_k(sp, use, Y, tr, base), F.choose_k(sp, use, Y, tr, base))
                    cases += 2
            rng = S.rng_for("selftest", cell, "boot", s)
            idx = rng.integers(0, G, G)
            ra, rb = L.replicate(X, Y, base, idx), F.replicate(X, Y, base, idx)
            item(f"(a) fast replicate == sv0_lib.replicate [{cell} s{s}]", True,
                 all(same_pred(ra["pred"][p], rb["pred"][p]) for p in L.POLICIES) and L.theta(ra["eval"]) == L.theta(rb["eval"]))
            cases += 1
    item("(a) number of bit-identity datasets >= 20", True, datasets >= 20)
    item("(a) number of bit-identity cases >= 20", True, cases >= 20)
    TIMING["fast_path"] = {"G28_p0_cpu_s": t_p0, "G28_fast_cpu_s": t_fast, "speedup": t_p0 / t_fast if t_fast else None}


def test_coverage_arithmetic():
    z = NormalDist().inv_cdf(0.95)
    K = 999
    xs = [NormalDist().inv_cdf(i / (K + 1)) for i in range(1, K + 1)]
    ivs = [[x - z, x + z] for x in xs]
    item("(b) closed-form grid: covered count (i = 50..950 of 999)", 901, sum(S.covered(iv, 0.0) for iv in ivs))
    item("(b) lower and upper misses", [49, 49], [sum(0.0 < iv[0] - S.TOL for iv in ivs), sum(0.0 > iv[1] + S.TOL for iv in ivs)])


def test_truths():
    G, scen = S.CELLS["B-info"]
    fixed = S.fixed_params(scen)
    X, Q, Y, base = S.dataset(fixed, G, S.rng_for("selftest", "B-info", "truth", 0))
    same = {"interv": L.POLICIES["obs_morph"], "obs_morph": L.POLICIES["obs_morph"]}
    tn, _ = S.deploy(fixed, X, Y, base, S.rng_for("selftest", "B-info", "new", 0), 50, False, uses=same)
    item("(c) theta_new of identical policies is exactly 0", 0.0, tn)
    sp = p0.Space(X, L.BLOCKS)
    ev = {p: p0.decision_eval(p0.predict(sp, L.POLICIES["obs_morph"], Y, base, base), Y) for p in ("interv", "obs_morph")}
    item("(c) theta_cond of identical policies is exactly 0", 0.0, S.theta_cond(ev, Q))
    ev = S.fit(X, Y, base, False)
    r = np.arange(len(Q))
    direct = float(np.mean(Q[r, ev["interv"]["pick"]]) - np.mean(Q[r, ev["obs_morph"]["pick"]]))
    item("(c) theta_cond equals the direct mean of Q at the picks (1e-12)", True, abs(S.theta_cond(ev, Q) - direct) <= 1e-12)
    tu = S.truth_unit("selftest", "B-info", 0, 50, False)
    item("(c) truth_unit theta_fix equals mean(Q0 - Q1)", float(np.mean(Q[:, 0] - Q[:, 1])), tu["theta_fix"])


def test_determinism():
    a = [json.dumps(S.coverage_unit("selftest", "B-null", "cov", s, 3, 2, 30, False), sort_keys=True) for s in (0, 1, 2)]
    b = [json.dumps(S.coverage_unit("selftest", "B-null", "cov", s, 3, 2, 30, False), sort_keys=True) for s in (2, 0, 1)]
    item("(d) records identical regardless of order (shard invariance)", True, a == [b[1], b[2], b[0]])
    f = json.dumps(S.coverage_unit("selftest", "B-null", "cov", 0, 3, 2, 30, True), sort_keys=True)
    item("(d) fast-path record identical to P0-path record (except the 'fast' flag)", True,
         json.loads(f) == {**json.loads(a[0]), "fast": True})


def test_oc():
    got = {z: [round(S.p_admit(40, c, z, 2), 3) for c in (0.90, 0.85, 0.80)] for z in (1.645, 1.282)}
    item("(e) P(admit), S = 40, 2 cells, two-sided z = 1.645 (A0: 0.630 / 0.187 / 0.026)", [0.630, 0.187, 0.026], got[1.645])
    item("(e) P(admit), S = 40, 2 cells, one-sided z = 1.282 (A0: 0.811 / 0.368 / 0.082)", [0.811, 0.368, 0.082], got[1.282])
    item("(e) k_min at S = 40: 35 (z 1.645), 34 (z 1.282)", [35, 34], [S.admit_k_min(40, 1.645), S.admit_k_min(40, 1.282)])
    TIMING["oc_S200"] = {c: round(S.p_admit(200, c, 1.645, 3), 4) for c in (0.90, 0.85, 0.80)}


def test_small():
    ok = all(S.wilson(k, 40, 1.645)[0] <= k / 40 <= S.wilson(k, 40, 1.645)[1] and
             abs(S.wilson(k, 40, 1.645)[0] - (1 - S.wilson(40 - k, 40, 1.645)[1])) <= 1e-15 for k in range(41))
    item("(f) Wilson: lower <= k/n <= upper and lower(k) = 1 - upper(n - k)", True, ok)
    cases = {(0.01, 0.2): "supported benefit", (-0.1, 0.05): "no meaningful gain", (-0.2, -0.01): "supported harm",
             (-0.05, 0.2): "inconclusive", (0.0, 0.2): "inconclusive"}
    item("(g) section-4 partition hand cases", list(cases.values()), [S.partition(list(k)) for k in cases])
    item("(h) half-sampling variance: diffs (0.2, -0.2, 0, 0.4) -> 0.24 / 16", True,
         abs(S.half_variance([0.2, -0.2, 0.0, 0.4]) - 0.015) <= 1e-15)
    item("(i) verdicts: 176/200 not validated, 170/200 evidence of undercoverage, 150/200 material, admitted",
         ["not validated", "evidence of undercoverage", "evidence of material undercoverage", "validated"],
         [S.verdict(176, 200, 1.645, False), S.verdict(170, 200, 1.645, False), S.verdict(150, 200, 1.645, False),
          S.verdict(170, 200, 1.645, True)])


def test_admission():
    """(k) admission / selection arithmetic on constructed cases (truth theta_G = 0; interval [-1, 1] covers, [5, 6] is a
    lower-tail miss, [-1, 0.015] covers 0 but not 0 + 2 MC-SE = 0.02)."""
    fx = {"admission_coverage_min": 0.85, "admission_wilson_lower_min": 0.75}

    def cell(n_cover, n_lowmiss, n_edge=0, mcse=1e-9):
        ivs = [[-1.0, 1.0]] * n_cover + [[5.0, 6.0]] * n_lowmiss + [[-1.0, 0.015]] * n_edge
        recs = [{"intervals": {"M1": iv}, "theta_hat": 0.0, "theta_cond": 0.0, "theta_new": 0.0, "theta_fix_hat": 0.0} for iv in ivs]
        tru = {"theta_G": 0.0, "theta_G_mcse": mcse, "theta_fix_G": 0.0, "theta_fix_mcse": mcse, "theta_new_G": 0.0}
        return {"methods": {"M1": S.method_metrics(recs, tru, "M1", 1.645, 0.10)}}
    dec = {"wilson_z": 1.645, "admission_cells": ["X"], "lower_tail_max": 0.10}
    cases = {"180 covered / 20 lower misses (0.90; lower 0.10)": (cell(180, 20), dec, True, "validated"),
             "168 / 32 (0.84 < 0.85)": (cell(168, 32), dec, False, "evidence of undercoverage"),
             "178 / 22 (0.89 but lower tail 0.11 > 0.10)": (cell(178, 22), dec, False, "not validated"),
             "178 / 22 without D-4": (cell(178, 22), {**dec, "lower_tail_max": None}, True, "validated"),
             "160 + 10 edge / 30 (0.85 at theta_G, 0.80 at +2 MC-SE): truth-sensitive":
                 (cell(160, 30, 10, mcse=0.01), {**dec, "lower_tail_max": None}, False, "evidence of undercoverage")}
    for name, (pc, d, adm, verd) in cases.items():
        a = S.admission({"X": pc}, "M1", d, fx)
        item(f"(k) admission: {name}", [adm, verd], [a["admitted"], a["cells"]["X"]["verdict"]])
    a = S.admission({"X": cell(160, 30, 10, mcse=0.01)}, "M1", {**dec, "lower_tail_max": None}, fx)
    item("(k) the truth-sensitivity flag is set in the edge case", True, a["cells"]["X"]["truth_sensitive"])

    def cell_lt():                                                 # lower tail 20/200 at theta_G, 22/200 at theta_G - 2 MC-SE
        ivs = [[-1.0, 1.0]] * 178 + [[0.015, 6.0]] * 20 + [[-0.015, 6.0]] * 2
        recs = [{"intervals": {"M1": iv}, "theta_hat": 0.0, "theta_cond": 0.0, "theta_new": 0.0, "theta_fix_hat": 0.0} for iv in ivs]
        tru = {"theta_G": 0.0, "theta_G_mcse": 0.01, "theta_fix_G": 0.0, "theta_fix_mcse": 0.01, "theta_new_G": 0.0}
        return {"methods": {"M1": S.method_metrics(recs, tru, "M1", 1.645, 0.10)}}
    a = S.admission({"X": cell_lt()}, "M1", dec, fx)
    item("(k) lower-tail rule flipping inside +-2 MC-SE is truth-sensitive and not admitted", [False, True, "not validated"],
         [a["admitted"], a["cells"]["X"]["truth_sensitive"], a["cells"]["X"]["verdict"]])
    item("(k) selection: widest admissible interval per dataset",
         [-1.0, 1.5], S.widest({"intervals": {"M1": [0.0, 1.0], "M2": [-1.0, 1.5], "M4": [0.0, 0.2]}}, ["M1", "M2"]))


def test_units():
    """(l) exact unit lists (frozen config) and the per-record parameter check used by the aggregator."""
    cfg = json.loads(open(os.path.join(GD.SV1_DIR, "sv1_config.json"), encoding="utf-8").read())
    conf, pil = S.work_units(cfg, "confirm"), S.work_units(cfg, "pilot")
    item("(l) confirm units = 3 x (200 cov + 100 eval + 2000 truth) + 2 x (100 cov + 1000 truth) = 9100", 9100, len(conf))
    item("(l) pilot units = 3 x (6 + 200) + 2 x (4 + 200) = 1026", 1026, len(pil))
    item("(l) confirm unit keys unique", len(conf), len({(c, k, s) for c, k, s, _ in conf}))
    item("(l) confirm coverage units use the frozen B = 200, R = 40", True,
         all(par["B"] == 200 and par["R"] == 40 for _, k, _, par in conf if k != "truth"))
    rec = S.coverage_unit("selftest", "B-null", "cov", 0, 3, 2, 30, False)
    par_ok = {"B": 3, "R": 2, "new": 30}
    item("(l) record_problems: matching record has none", [], S.record_problems({**rec, "phase": "confirm"}, "confirm", par_ok, False))
    item("(l) record_problems: wrong phase, B and fast are caught", ["phase", "G/fast", "B/R_half/m"],
         S.record_problems({**rec, "B": 200, "fast": True}, "confirm", par_ok, False))


def test_c0_gate():
    """(m) amendment A-SV1-1: exact thresholds (derived independently with math.comb sums before implementation) and the
    per-cell / pooled decisions on constructed counts."""
    def first_reject(n, side):
        ks = range(n + 1) if side == "low" else range(n, -1, -1)
        last = None
        for k in ks:
            if S.c0_gate({"x": (k, n)})["cells"]["x"]["reject"]:
                last = k
            else:
                break
        return last
    item("(m) C0 per-cell thresholds n = 200: reject k <= 157 or k >= 197", [157, 197], [first_reject(200, "low"), first_reject(200, "high")])
    item("(m) C0 per-cell thresholds n = 100: reject k <= 75 or k >= 100", [75, 100], [first_reject(100, "low"), first_reject(100, "high")])
    item("(m) C0 pooled thresholds n = 800: reject k <= 655 or k >= 775", [655, 775], [first_reject(800, "low"), first_reject(800, "high")])
    a = {"A-null": 200, "A-info": 200, "A-obs": 200, "B-null": 100, "B-info": 100}
    good = S.c0_gate({c: (int(0.9 * n), n) for c, n in a.items()})
    item("(m) C0 gate: every cell at 0.90 passes", True, good["ok"])
    one = S.c0_gate({**{c: (int(0.9 * n), n) for c, n in a.items()}, "A-obs": (157, 200)})
    item("(m) C0 gate: a single scenario-specific failure (A-obs 157/200) rejects with the pooled test passing",
         [False, True, False], [one["ok"], one["cells"]["A-obs"]["reject"], one["pooled"]["reject"]])
    common = S.c0_gate({c: (int(0.8 * n), n) for c, n in a.items()})
    item("(m) C0 gate: a common moderate defect (all cells 0.80) is caught by the pooled test although no cell rejects",
         [False, False, True], [common["ok"], any(v["reject"] for v in common["cells"].values()), common["pooled"]["reject"]])


def test_guard():
    import socket
    import subprocess
    GD.secondary()

    def raised(fn):
        try:
            fn()
        except GD.GuardViolation:
            return True
        except Exception:                                          # noqa: BLE001
            return False
        return False

    def opener(p, mode):
        with open(p, mode):
            pass
    probes = {"subprocess.run": lambda: subprocess.run(["true"], check=False), "socket.socket()": lambda: socket.socket(),
              "read artifacts/x": lambda: opener(os.path.join(GD.REPO, "artifacts", "x"), "r"),
              "write outside --out": lambda: opener(os.path.join(GD.SV1_DIR, "guard_probe.txt"), "w")}
    for name, fn in probes.items():
        item(f"(j) guard refuses {name}", True, raised(fn))
    item("(j) every creature_forge module is a file of this checkout", [], GD.module_provenance_ok())


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for fn in (test_coverage_arithmetic, test_oc, test_small, test_admission, test_units, test_c0_gate, test_truths, test_determinism, test_fast, test_guard):
        try:
            fn()
        except Exception as e:                                     # noqa: BLE001 - recorded as a FAIL item
            item(f"{fn.__name__} completed without exception", None, f"{type(e).__name__}: {e}", False)
    TIMING["wall_s"] = time.time() - t0
    status = "PASS" if all(i["result"] == "PASS" for i in ITEMS) else "FAIL"
    with open(os.path.join(OUT, "selftest_results.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"status": status, "items": ITEMS, "code_sha256": GD.code_hashes(), "fingerprint": GD.fingerprint()},
                            sort_keys=True, indent=1, default=str) + "\n")
    with open(os.path.join(OUT, "selftest_timing.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(TIMING, sort_keys=True, indent=1) + "\n")
    print(status, sum(i["result"] == "PASS" for i in ITEMS), "/", len(ITEMS))
    for i in ITEMS:
        if i["result"] != "PASS":
            print("FAIL:", i["name"], "| expected", i["expected"], "| observed", i["observed"])
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
