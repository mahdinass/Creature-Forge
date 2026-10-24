"""P05-SV1 aggregation (proposal sections 2A, 5, 6, 6A, 6B; review fixes R1-R11 in section 14).

    "$V/bin/python" -I -B sv1_aggregate.py --phase {pilot,confirm} --out <repo>/<sv1>/out --pre ~/sv1/pre
    python -I -B sv1_aggregate.py --phase {pilot,confirm} --out DIR --local-test [--decisions JSON]   (smoke only)

Both phases first check provenance (outside --local-test: code and config sha256 against expected.json; this --out's
sv1_selftest PASS with the approved hashes and fingerprint), then completeness: the set of record keys must equal
sv1_lib.work_units exactly, every record must carry the frozen parameters, no unit may have errored, no two records may
conflict, and a replay file (if present) must match byte-for-byte.
pilot   : BLINDED. Engineering quantities only, plus the harness checks C0 coverage and bias(theta_hat - theta_cond).
confirm : truths, every metric, the frozen admission rule with the owner's decisions, the M5 composite check, selection of the
          widest admissible interval (M6) and its independent evaluation. sv1_results.json is deterministic (no timings).
--local-test writes sv1_results_SMOKE.json / sv1_report_SMOKE.md and never touches the real result files.
"""
import os
import sys

_HERE = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
sys.path.insert(0, _HERE)
import sv1_guard as GD  # noqa: E402


def _args(argv):
    a, out, flags = list(argv), {}, set()
    while a:
        k = a.pop(0)
        if k == "--local-test":
            flags.add(k)
            continue
        if k not in ("--phase", "--out", "--decisions", "--pre", "--override") or not a or k in out:
            raise SystemExit("usage: sv1_aggregate.py --phase {pilot,confirm} --out DIR (--pre DIR | --local-test [--decisions JSON])")
        out[k] = a.pop(0)
    if out.get("--phase") not in ("pilot", "confirm") or "--out" not in out:
        raise SystemExit("bad arguments")
    if ("--decisions" in out or "--override" in out) and "--local-test" not in flags:
        raise SystemExit("--decisions / --override are allowed only with --local-test")
    if "--local-test" not in flags and "--pre" not in out:
        raise SystemExit("--pre is required outside --local-test")
    return out, flags


ARGS, FLAGS = _args(sys.argv[1:])
LOCAL = "--local-test" in FLAGS
GD.install(os.path.realpath(ARGS["--out"]), ARGS.get("--pre"))

import json  # noqa: E402
import math  # noqa: E402
import statistics  # noqa: E402

import numpy as np  # noqa: E402

import sv1_lib as S  # noqa: E402
from sv1_lib import _mean_se, admission, method_metrics, truths, widest  # noqa: E402

GD.secondary()
SUFFIX = "_SMOKE" if LOCAL else ""


def _read_lines(path: str) -> tuple[list, int]:
    """Parsed JSON lines; an unterminated or unparsable line is counted and skipped (never silently used)."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().split("\n")
    rows, bad = [], 0
    for ln in raw:
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except ValueError:
            bad += 1
    return rows, bad


def _read_records(phase_dir: str) -> tuple[dict, list, int, list]:
    recs, conflicts, partial, errors = {}, [], 0, []
    for f in sorted(os.listdir(phase_dir)):
        if f.startswith("records_") and f.endswith(".ndjson"):
            rows, bad = _read_lines(os.path.join(phase_dir, f))
            partial += bad
            for r in rows:
                key = (r["cell"], r["kind"], r["s"])
                if key in recs and recs[key] != r:
                    conflicts.append(list(key))
                recs[key] = r
        elif f.startswith("errors_") and f.endswith(".ndjson"):
            errors += _read_lines(os.path.join(phase_dir, f))[0]
    return recs, conflicts, partial, errors


def provenance(out_root: str) -> dict:
    """Code/config hashes, fingerprint and the SV1-0 gate. Outside --local-test every mismatch is a failure."""
    code = GD.code_hashes()
    st_path = os.path.join(out_root, "selftest", "selftest_results.json")
    st = json.loads(open(st_path, encoding="utf-8").read()) if os.path.exists(st_path) else {"status": "MISSING", "items": []}
    prov = {"code_sha256": code, "selftest_status": st["status"], "failures": []}
    if not LOCAL:
        exp = json.loads(open(os.path.join(ARGS["--pre"], "expected.json"), encoding="utf-8").read())
        prov["expected_head"] = exp["head"]
        if code != exp["code_sha256"]:
            prov["failures"].append("code/config sha256 differ from expected.json")
        if st["status"] != "PASS" or st.get("code_sha256") != exp["code_sha256"] or st.get("fingerprint") != exp["fingerprint"]:
            prov["failures"].append("SV1-0 self-test is not a PASS with the approved code hashes and fingerprint")
        prov["fingerprint"] = exp["fingerprint"]
    return prov


def completeness(cfg: dict, phase: str, recs: dict, conflicts: list, partial: int, errors: list, phase_dir: str) -> dict:
    units = S.work_units(cfg, phase, json.loads(ARGS.get("--override", "{}")) if LOCAL else None) if not (LOCAL and phase == "confirm") else None
    out = {"conflicts": conflicts, "partial_lines": partial, "errors": errors[:20], "n_errors": len(errors)}
    if units is not None:
        expected = {(c, k, s): par for c, k, s, par in units}
        fast = cfg["engineering"]["fast_path"] is True
        missing = sorted(set(expected) - set(recs))
        extra = sorted(set(recs) - set(expected))
        wrong = sorted([list(k), S.record_problems(r, phase, expected[k], r.get("fast") if LOCAL else fast)]
                       for k, r in recs.items() if k in expected and S.record_problems(r, phase, expected[k], r.get("fast") if LOCAL else fast))
        out.update({"n_expected": len(expected), "n_present": len(recs), "missing": [list(m) for m in missing[:20]],
                    "n_missing": len(missing), "n_extra": len(extra), "wrong_parameters": wrong[:20], "n_wrong": len(wrong)})
    rp = os.path.join(phase_dir, "replay.ndjson")
    need = math.ceil(0.02 * out.get("n_expected", 0)) if (phase == "confirm" and not LOCAL) else 1
    if os.path.exists(rp):
        rows, bad = _read_lines(rp)
        mism = [[r["cell"], r["kind"], r["s"]] for r in rows if recs.get((r["cell"], r["kind"], r["s"])) != r]
        out["replay"] = {"n": len(rows), "required": need, "unparsable": bad, "mismatches": mism,
                         "ok": bad == 0 and not mism and len(rows) >= need}
    elif phase == "confirm" and not LOCAL:
        out["replay"] = {"n": 0, "required": need, "ok": False}            # section 7: the replay is mandatory for confirm
    if not LOCAL:                                                       # every worker of this phase ran preflighted, not local
        pfs = [json.loads(open(os.path.join(phase_dir, f), encoding="utf-8").read()) for f in sorted(os.listdir(phase_dir))
               if f.startswith("preflight_") and f.endswith(".json")]
        out["preflights"] = {"n": len(pfs), "ok": bool(pfs) and all(not p["local_test"] and not p["failures"] for p in pfs)}
    # Recovery policy (engineering, documented in section 14): a killed worker's fragment or a logged error does not void
    # the run when every expected unit is present exactly once with the frozen parameters; both stay reported.
    out["ok"] = (not conflicts and out.get("n_missing", 0) == 0 and out.get("n_extra", 0) == 0 and out.get("n_wrong", 0) == 0
                 and out.get("replay", {}).get("ok", True) and out.get("preflights", {}).get("ok", True)
                 and (units is not None or LOCAL))
    return out


def main() -> int:
    phase = ARGS["--phase"]
    out_root = os.path.realpath(ARGS["--out"])
    phase_dir = os.path.join(out_root, phase)
    cfg = json.loads(open(os.path.join(GD.SV1_DIR, "sv1_config.json"), encoding="utf-8").read())
    fx = cfg["fixed"]
    dec = None
    if phase == "confirm":
        dec = json.loads(ARGS["--decisions"]) if "--decisions" in ARGS else cfg["decisions"]
        if any(v == "PENDING" for v in dec.values()):
            raise SystemExit("confirm aggregation refused: owner decisions pending")
    z = dec["wilson_z"] if dec else 1.645
    recs, conflicts, partial, errors = _read_records(phase_dir)
    res = {"proposal": cfg["proposal"], "phase": phase, "smoke": LOCAL, "provenance": provenance(out_root),
           "completeness": completeness(cfg, phase, recs, conflicts, partial, errors, phase_dir), "cells": {}}
    harness_ok = res["completeness"]["ok"] and not res["provenance"]["failures"]
    for cell in sorted({c for c, _, _ in recs}):
        tru = truths(recs, cell)
        cov = [r for (c, kind, _), r in sorted(recs.items()) if c == cell and kind == "cov"]
        n_rep = sum(r["B"] for r in cov)
        degen = sum(r["boot"]["n_degenerate_redrawn"] for r in cov)
        ent = {"truth": tru, "n_cov": len(cov), "degenerate_replicates_redrawn": degen,
               "degenerate_flag_over_1pct": bool(n_rep) and degen / (n_rep + degen) > 0.01,
               "cr1_zero_se": sum(r["se_cr1"] == 0.0 for r in cov)}
        if tru and cov:
            pooled = cov + [r for (c, k, _), r in recs.items() if c == cell and k == "truth"]
            b, b_se = _mean_se(r["theta_hat"] - r["theta_cond"] for r in pooled)
            ent["bias_check"] = {"n": len(pooled), "mean": b, "mcse": b_se, "ok": abs(b) <= 3 * b_se if b_se == b_se else True}
            c0 = method_metrics(cov, tru, "C0", z, fx["margin_m"])
            ent["C0_coverage"] = c0["coverage_theta_G"]
            harness_ok &= ent["bias_check"]["ok"]
        if phase == "confirm" and tru and cov:
            ent["methods"] = {mt: method_metrics(cov, tru, mt, z, fx["margin_m"]) for mt in S.METHODS}
            ent["cr1_se_calibration"] = (statistics.fmean(r["se_cr1"] ** 2 for r in cov) /
                                         statistics.variance([r["theta_hat"] for r in cov])) if len(cov) > 1 else None
            boots = [r for r in cov if r["boot"]["mean"] is not None]
            ent["bootstrap_bias"] = _mean_se(r["boot"]["mean"] - r["theta_hat"] for r in boots)[0] if boots else None
        res["cells"][cell] = ent
    if phase == "pilot":
        g = fx["c0_gate"]                                           # reported only: pilot sizes give the test no power
        res["c0_gate_diagnostic"] = S.c0_gate({c: (e["C0_coverage"]["k"], e["C0_coverage"]["n"]) for c, e in res["cells"].items()
                                               if e.get("C0_coverage")}, tuple(g["band"]), g["alpha_per_side"])
        res["blinded"] = "M1-M6 coverage and width are not computed in the pilot (proposal 2A item 6)"
        res["harness_ok"] = harness_ok
        res["classification"] = "PILOT OK (engineering)" if harness_ok else "PILOT NOT OK (see completeness/provenance/bias)"
        _write(phase_dir, res)
        return 0 if harness_ok else 1
    g = fx["c0_gate"]                                               # amendment A-SV1-1: exact per-cell + pooled C0 test
    counts = {c: (e["C0_coverage"]["k"], e["C0_coverage"]["n"]) for c, e in res["cells"].items() if e.get("C0_coverage")}
    res["c0_gate"] = S.c0_gate(counts, tuple(g["band"]), g["alpha_per_side"])
    harness_ok &= len(counts) == len(res["cells"]) == len(dec["admission_cells"]) + len(fx["diagnostic_cells"]) and res["c0_gate"]["ok"]
    res["harness_ok"] = harness_ok
    if not harness_ok:
        res["classification"] = ("INCOMPLETE OR UNPROVEN RUN" if not (res["completeness"]["ok"] and not res["provenance"]["failures"])
                                 else "INVALID-HARNESS")
        _write(phase_dir, res)
        return 1
    cands = list(fx["frozen_candidates"]) + (["M3"] if dec["m3_candidate"] else [])
    adm = {c: admission(res["cells"], c, dec, fx) for c in cands}
    m5 = admission(res["cells"], "M5", dec, fx)
    admitted = [c for c in cands if adm[c]["admitted"]]
    res["admission"] = {"candidates": cands, "per_method": adm, "admitted": admitted,
                        "composite_M5": m5, "composite_rule_valid": m5["admitted"],
                        "note": "admission-sample coverages of admitted methods are selection-biased upward (6A)"}
    if not admitted:
        res["classification"] = "NO METHOD ADMITTED: inference not validated (E1)"
        _write(phase_dir, res)
        return 0
    res["selected"] = {"procedure": "M6 = widest admissible per dataset (frozen E1)", "pool": admitted,
                       "composite_rule_valid": m5["admitted"]}
    ev = {}
    for cell in dec["admission_cells"]:
        tru = res["cells"][cell]["truth"]
        rows = [r for (c, kind, _), r in sorted(recs.items()) if c == cell and kind == "eval"]
        for r in rows:
            r["intervals"]["M6"] = widest(r, admitted)
        mm = {mt: method_metrics(rows, tru, mt, z, fx["margin_m"]) for mt in admitted + ["M5", "M6"]}
        for mt, m in mm.items():
            m["verdict"] = S.verdict(m["coverage_theta_G"]["k"], m["coverage_theta_G"]["n"], z, False)
        ev[cell] = mm
    confirmed = all(ev[c]["M6"]["coverage_theta_G"]["wilson"][1] >= 0.85 for c in ev)
    res["evaluation"] = {"per_cell": ev, "admission_confirmed": confirmed,
                         "note": "independent evaluation datasets; the only coverage figures quoted as validity estimates (6A)"}
    res["classification"] = ("ADMITTED and confirmed on the independent evaluation set" if confirmed
                             else "ADMITTED but admission not confirmed on the independent evaluation set")
    _write(phase_dir, res)
    return 0


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, np.integer, np.bool_)):
        return x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return repr(x)
    return x


def _report(res: dict) -> str:
    L = [f"# P05-SV1 {res['phase']} report{' (SMOKE)' if res['smoke'] else ''}", "", f"**Classification: {res.get('classification')}**", "",
         f"- provenance failures: {res['provenance']['failures'] or 'none'}; self-test: {res['provenance']['selftest_status']}",
         f"- completeness ok: {res['completeness']['ok']} (missing {res['completeness'].get('n_missing')}, errors "
         f"{res['completeness']['n_errors']}, conflicts {len(res['completeness']['conflicts'])}, partial lines "
         f"{res['completeness']['partial_lines']}, replay {res['completeness'].get('replay', {}).get('ok', 'not run')})", "",
         "| cell | n_cov | T | bias check | C0 coverage | degenerate redrawn |", "|---|---|---|---|---|---|"]
    for c, e in sorted(res["cells"].items()):
        c0 = e.get("C0_coverage") or {}
        L.append(f"| {c} | {e['n_cov']} | {e['truth'].get('T')} | {e.get('bias_check', {}).get('ok')} | "
                 f"{c0.get('k')}/{c0.get('n')} | {e['degenerate_replicates_redrawn']} |")
    if res["phase"] == "confirm" and "admission" in res:
        L += ["", f"Admitted: {res['admission']['admitted'] or 'none'}; composite rule (M5) valid: {res['admission']['composite_rule_valid']}"]
        if "evaluation" in res:
            L.append(f"Independent evaluation confirms admission: {res['evaluation']['admission_confirmed']}")
    L += ["", "SV1 establishes coverage properties only for the synthetic calc section-E generator family and the certified "
          "fingerprint; it is necessary, not sufficient, for real-data validity.", ""]
    return "\n".join(L)


def _write(phase_dir: str, res: dict) -> None:
    res = _clean(res)
    with open(os.path.join(phase_dir, f"sv1_results{SUFFIX}.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, sort_keys=True, indent=1) + "\n")
    with open(os.path.join(phase_dir, f"sv1_report{SUFFIX}.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_report(res))


if __name__ == "__main__":
    sys.exit(main())
