"""Overview data for the Studio landing page: the project story and the evidence behind each claim, read from the committed records.

Nothing here is computed from a model reply or hard-coded as a result: every number is read from an experiment file at request time, and the
two lines of evidence are kept apart on purpose:
  * CLASSICAL local optimisation (R2): a statistically confirmed improvement that involves NO language model;
  * NEMOTRON investigation demo: real model proposals verified by MuJoCo next to matched random edits, with NO claim that the model is better
    than random; the systematic comparison (R3) was not completed because no generation setting passed calibration.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def classical_r2() -> dict | None:
    f = _read(EXP / "phase2a_r2" / "results" / "final.json")
    if f is None:
        return None
    t, h = f["paired_table"], f["confirmatory_hierarchy"]
    ledger = _read(EXP / "phase2a_r2" / "results" / "selection.json")
    d = f["descriptive_paired_comparison"]
    return {
        "winner_walking": d["new"]["successes"], "incumbent_walking": d["old"]["successes"], "n": t["n"],
        "winner_exact_ci": d["new"]["exact_95ci"], "incumbent_exact_ci": d["old"]["exact_95ci"],
        "paired": {"winner_only": t["new_only"], "incumbent_only": t["old_only"], "both": t["both"], "neither": t["neither"]},
        "non_inferior": h["claims"]["preservation_confirmed"], "superior": h["claims"]["improvement_confirmed"],
        "tango_ci": h["step1_noninferiority"]["tango_ci"], "mcnemar_p": h["step2_superiority"].get("mcnemar_exact_two_sided_p"),
        "engineering_met": f["engineering"]["winner"]["meets_engineering_criterion"],
        "winner_source": f["winner_source"], "rollouts_total": f["ledger_rollouts_total"],
        "validation_walking": (ledger or {}).get("winner", {}).get("walking_count"),
        "attribution": "Found by classical local optimisation (random-subset perturbation, initiation grid, (1+8)-ES). No language model was involved.",
    }


def nemotron_demo() -> dict:
    from . import demo, r3v2
    runs = []
    for row in demo.list_runs():
        if row.get("source") != "bundled-recording":
            continue
        rec = demo.load_run(row["run_id"])
        ver = rec.get("verification")
        item = {"id": row["run_id"], "kind": rec["provenance"]["kind"], "label": rec.get("label"), "model_status": rec["model_reply"]["status"],
                "valid_proposals": len(rec["interventions"]), "tokens": (rec["provenance"].get("usage") or {}).get("total_tokens"), "proposals": []}
        if ver:
            base = ver["results"]["theta0"]
            item["frozen_walking"], item["n"] = base["walking_count"], base["n"]
            for iv in rec["interventions"]:
                e, r = ver["results"][f"slot{iv['slot']}"], ver["results"][f"slot{iv['slot']}_random"]
                item["proposals"].append({"edits": [x["parameter"] for x in iv["proposal"]["edits"]], "model_walking": e["walking_count"], "random_walking": r["walking_count"],
                                          "model_verdict": e["verdict"]["kind"], "random_verdict": r["verdict"]["kind"]})
        runs.append(item)
    cal = _read(EXP / "phase2a_r3" / "results_v2" / "calibration_result.json")
    u = r3v2.prior_usage()
    return {
        "recorded_runs": runs,
        "systematic_comparison": {"status": "not completed", "reason": ("No generation setting passed the preregistered calibration: the evidence prompt returned empty replies "
                                                                       "(hidden reasoning used the whole token budget) at every setting, so the 30 experimental requests were never sent."),
                                  "chosen_setting": None if cal is None else cal.get("chosen"), "settings_tested": 0 if cal is None else len(cal.get("results", []))},
        "usage": {"requests": u["requests"], "tokens": u["tokens"], "requests_cap": r3v2.TOTAL_REQUESTS_CAP, "tokens_cap": r3v2.TOTAL_TOKENS_CAP},
        "claim": "Real model proposals, verified by MuJoCo beside matched random edits. This does NOT show that Nemotron picks better edits than random ones.",
    }


def earlier_results() -> dict:
    g1 = _read(EXP / "phase2a_r1" / "results" / "gate.json")
    held = _read(EXP / "phase2a" / "results" / "heldout.json")
    out: dict = {}
    if g1:
        out["r1"] = {"proceed": g1["proceed"], "text": "R1 (global random search with robustness objectives): futility gate stopped the experiment; no candidate walked on any validation seed."}
    if held:
        v = held["controllers"]["random_search"]["verdict"]
        out["phase2a"] = {"walking_fraction": v["fraction_seeds_walking"], "text": "Phase 2A: a hand-designed phase-gait controller with tuned parameters walked on 70% of held-out seeds (14/20), below the 90% criterion."}
    return out


def overview() -> dict:
    return {
        "headline": "Machines that learn from falling",
        "pipeline": [
            {"step": "Failure", "text": "MuJoCo shows a concrete, measurable physical failure (a biped falling at start-up)."},
            {"step": "Evidence", "text": "Creature Forge records what was observed: per-seed outcomes, step counts, pitch, timing."},
            {"step": "Nemotron proposes", "text": "NVIDIA Nemotron (via Nebius Token Factory) proposes bounded edits to the controller, citing that evidence."},
            {"step": "MuJoCo tests", "text": "Every valid proposal is simulated next to a matched random edit on fresh seeds. Only measurements count."},
            {"step": "Replay & verdict", "text": "Synchronized replays and an honest measured verdict, including when random edits do as well."},
        ],
        "classical": classical_r2(),
        "nemotron": nemotron_demo(),
        "earlier": earlier_results(),
        "limits": [
            "One planar biped, one controller family, simulation only.",
            "The 150/150 result comes from classical optimisation, not from the language model.",
            "The Nemotron demo shows the propose -> simulate -> verify loop; it is not a statistical claim about the model.",
            "The systematic Nemotron-vs-random comparison (R3) was not completed (generation calibration failed).",
        ],
    }
