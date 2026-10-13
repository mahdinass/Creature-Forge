"""Presentation model of a saved Trial for a future Studio panel. READ-ONLY: it reshapes recorded data and
never runs physics or changes any measured number.

Sections: observed (what MuJoCo measured), rationale (the model's claim + the evidence it cited, resolved
to the actual measured values), design_change (original vs modified body), predicted_vs_measured, outcome.
"""
from __future__ import annotations

from .investigator import resolve_path


def trial_view(trial: dict) -> dict:
    ev, hyp, out = trial.get("observed_evidence") or {}, trial.get("hypothesis"), trial.get("measured_outcome")
    f = (ev.get("forensics") or {}).get("detailed")
    observed = {"scenario": ev.get("scenario"), "matched_seed_results": ev.get("matched_seed_results"),
                "forensic_highlights": None if f is None else {
                    "fall_time_s": f["failure"]["fall_time_s"],
                    "instability_onset_s": f["failure"]["instability_onset_s"],
                    "xcom_margin_recovered_s": f["failure"]["xcom_margin_recovered_s"],
                    "support_length_before_push_m": f["support"]["support_length_before_push_m"],
                    "com_margin_before_push_m": f["support"]["com_margin_before_push_m"],
                    "peak_abs_pitch_within_1s_rad": f["disturbance"]["peak_abs_pitch_within_1s_rad"],
                    "ankle_demand_over_limit_peak": f["actuation"]["ankle_demand_over_limit_peak"],
                    "peak_slip_speed_mps": f["contacts"]["peak_slip_speed_mps"]},
                "timeline": None if f is None else f["timeline"]}
    rationale = None
    if hyp:
        cited = []
        for path in hyp["cited_evidence"]:
            try:
                cited.append({"path": path, "value": resolve_path(ev, path)})
            except (KeyError, IndexError, ValueError):
                cited.append({"path": path, "value": None, "missing": True})
        rationale = {"source": "model (untrusted hypothesis)", "mechanism": hyp.get("mechanism"),
                     "claim": hyp["claim"], "confidence": hyp["confidence"], "cited": cited}
    change = None
    if hyp and out:
        p = hyp["intervention"]["parameter"]
        change = {"parameter": p, "original": ev["body"][p],
                  "modified": hyp["intervention"]["value"], "original_body": ev["body"],
                  "modified_body": out["candidate_body"]}
    proto = (out or {}).get("protocol")
    predicted = None
    if hyp and out:
        predicted = {"metric": hyp["prediction"]["metric"], "direction": hyp["prediction"]["direction"],
                     "held_on_screening_seeds": out["prediction_held"],
                     "held_on_heldout_primary": proto and proto["prediction_held_heldout_primary"],
                     "screening_observed": out["observed"],
                     "heldout_by_push": proto and {k: {"baseline": proto["baseline"]["by_push"][k],
                                                       "candidate": proto["candidate"]["by_push"][k]}
                                                   for k in proto["baseline"]["by_push"]}}
    return {"trial_id": trial["trial_id"], "mode": trial.get("mode"), "label": trial["config"].get("label"),
            "variant": trial["config"].get("variant", "legacy"), "observed": observed, "rationale": rationale,
            "design_change": change, "predicted_vs_measured": predicted,
            "outcome": {"status": trial["status"], "reason": trial.get("rejection_reason"),
                        "tier": proto and proto["verdict"]["tier"]},
            "model_call": trial.get("model_call")}
