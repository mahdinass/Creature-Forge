"""Independent H1 evidence replay using only Python's standard library.

Does not import the experiment analyzers, verdict, physics or NumPy. Frozen
arrays are inputs, not new simulations. Audit failures raise before publication;
the requested JSON output is exclusively created and never overwritten.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STUDY = ROOT / "experiments/causal_engineer/dev/h1"
FULL = "FULL_RECOVERY"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def identity(iid, design, seeds, variation):
    return sha(canonical([iid, sha(canonical(design)), seeds, variation]))


def check_manifest(root):
    root = Path(root).resolve()
    entries = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        path = (root / name).resolve()
        require(path.is_relative_to(root) and name not in entries, "unsafe/duplicate manifest path")
        require(sha(path.read_bytes()) == digest, f"manifest mismatch: {name}")
        entries[name] = digest
    return len(entries)


def check_sources(study):
    values = read(Path(study) / "source_hashes.json")
    for name, digest in values.items():
        require(sha((ROOT / name).read_bytes().replace(b"\r\n", b"\n")) == digest,
                f"frozen executable/input source mismatch: {name}")
    return len(values)


def rows_checked(rows, seeds):
    require(len(seeds) == 24 and len(set(seeds)) == 24, "not 24 distinct seeds")
    require(len(rows) == 24 and [r["seed"] for r in rows] == seeds, "response seed order/count")
    for row in rows:
        require(row["outcome"] in ("PASS", "POOR", "FAIL") and not row.get("error"), "error/unknown outcome")
        require(row["walking"] == (row["outcome"] == "PASS"), "inconsistent walking flag")
        require(isinstance(row["score"], (int, float)) and not isinstance(row["score"], bool)
                and math.isfinite(row["score"]), "nonfinite/missing score")


def replay(verification, candidate, seeds, variation):
    """Independently derive the frozen walking recovery rule from response arrays."""
    v = verification
    require(v["rule"] == "full_recovery_v1" and not v.get("errors"), "verifier rule/errors")
    require(v["seeds"] == seeds and v["variation"] == variation, "verifier condition identity")
    require(not set(seeds["validate"]) & set(seeds["confirm"]), "validation/confirmation overlap")
    original, repaired = v["validation"]["original"], v["validation"]["candidate"]
    rows_checked(original, seeds["validate"])
    rows_checked(repaired, seeds["validate"])
    differences = [b["score"] - a["score"] for a, b in zip(original, repaired)]
    wins = sum(d > .05 + 1e-9 for d in differences)
    losses = sum(d < -.05 - 1e-9 for d in differences)
    non_tied = wins + losses
    p_better = sum(math.comb(non_tied, i) for i in range(wins, non_tied + 1)) / 2**non_tied
    p_worse = sum(math.comb(non_tied, i) for i in range(losses, non_tied + 1)) / 2**non_tied
    median = statistics.median(differences)
    improve = non_tied >= 6 and p_better < .05 and median >= .5 - 1e-9
    verdict = ("INCONCLUSIVE" if non_tied < 6 else "VERIFIED_IMPROVEMENT" if improve else
               "WORSE" if p_worse < .05 and median <= -.5 + 1e-9 else "NOT_VERIFIED")
    saved = v["validation"]["verdict"]
    require(saved["status"] == verdict and saved["wins"] == wins and saved["losses"] == losses
            and saved["ties"] == 24 - non_tied, "independent sign-test verdict mismatch")
    require(saved["p_one_sided"] == p_better and saved["p_worse"] == p_worse
            and saved["median_diff"] == median, "independent sign-test statistics mismatch")
    walking = sum(r["walking"] for r in repaired)
    walking_ok = walking >= 20
    require(v["validation"]["walking_frac"] == walking / 24
            and (v["validation"]["aggregate"] == "PASS") == walking_ok, "validation aggregate")
    conf = v["confirmation"]
    require(conf["run"] == (improve and walking_ok), "conditional confirmation execution")
    components = {"improvement": improve, "validation_walking": walking_ok,
                  "confirmation_walking_frac": None, "confirmation_median_speed_upright": None,
                  "confirmation_body_contact": None}
    if conf["run"]:
        rows = conf["per_seed"]
        rows_checked(rows, seeds["confirm"])
        body = candidate["body"]
        left = body["thigh_length"] + body["shank_length"]
        right = (body.get("thigh_length_r") if body.get("thigh_length_r") is not None else body["thigh_length"]) + \
                (body.get("shank_length_r") if body.get("shank_length_r") is not None else body["shank_length"])
        speed_needed = .20 * ((left + right) / 2 / .60)
        speeds = [r["speed_upright"] for r in rows]
        require(all(isinstance(x, (int, float)) and math.isfinite(x) for x in speeds), "invalid speed metric")
        speed = statistics.median(speeds)
        contact_ok = all(isinstance(r["body_contact_frac"], (int, float))
                         and math.isfinite(r["body_contact_frac"]) and r["body_contact_frac"] <= .005 for r in rows)
        components.update(confirmation_walking_frac=sum(r["walking"] for r in rows) >= 20,
                          confirmation_median_speed_upright=speed >= speed_needed,
                          confirmation_body_contact=contact_ok)
        for name in ("walking_frac", "median_speed_upright", "body_contact"):
            require(conf["checks"][name]["passed"] == components["confirmation_" + name],
                    f"independent confirmation mismatch: {name}")
        require(abs(conf["checks"]["median_speed_upright"]["need"] - speed_needed) < 1e-14
                and conf["checks"]["median_speed_upright"]["value"] == speed, "body-scaled speed")
        require(conf["checks"]["body_contact"]["max_frac"] == .005, "contact threshold")
    full = conf["run"] and all(components[name] for name in components if name.startswith("confirmation_"))
    status = FULL if full else "PARTIAL_IMPROVEMENT" if improve else "NOT_RECOVERED"
    require(v["status"] == status, "independent full-recovery status")
    require(not conf["run"] or conf["passed"] == full, "confirmation aggregate")
    n = 24 if conf["run"] else 0
    require(v["rollouts"] == {"validation": 48, "confirmation": n,
                              "confirmation_rollout_equivalents": 2 * n}, "rollout ledger")
    return {"status": status, "components": components}, 48 + 2 * n, 48 + n


def close_number(a, b):
    require(abs(a - b) < 1e-12, "independent numeric analysis mismatch")


def percentile_interval(integer_base_totals, denominator):
    # Integer sums avoid Python 3.11/3.12's last-bit floating summation difference.
    rng = random.Random(2026102612)
    totals = sorted(sum(rng.choices(integer_base_totals, k=len(integer_base_totals)))
                    for _ in range(10000))
    return [totals[249] / denominator, totals[9749] / denominator]


def audit(stage_a, stage_b=None, study=DEFAULT_STUDY, r0_raw=None):
    study, stage_a = Path(study), Path(stage_a)
    r0_raw = Path(r0_raw) if r0_raw else ROOT / "artifacts/r0_ops/r0_run_20261025"
    protocol = read(study / "protocol.json")
    require(protocol["evidence_pin"] == "e8d5fa6730ecf6d2db67021a9d3d0f08cce03310", "evidence baseline")
    for name, digest in protocol["files"].items():
        require(sha((study / name).read_bytes()) == digest, "frozen input bytes")
    candidates_list = read(study / "candidates.json")
    cc = {c["key"]: c for c in candidates_list}
    pairs, known = read(study / "pairs.json"), read(study / "known.json")
    require(len(cc) == len(candidates_list) == 640 and len(pairs) == 324 and len(known) == 320, "cohort size")
    require(collections.Counter(p["base_id"] for p in pairs) ==
            collections.Counter({b: 18 for b in {c["base_id"] for c in cc.values()}}), "base support")
    for k, c in cc.items():
        require(k == identity(c["instance_id"], c["candidate"], c["seeds"], c["variation"])
                and c["candidate_sha256"] == sha(canonical(c["candidate"])), "exact candidate identity")
    require(set(protocol["missing_keys"]) == set(cc) - set(known) and len(protocol["missing_keys"]) == 320,
            "frozen missingness")
    source_count = check_sources(study)
    cases = {c["instance_id"]: c for c in read(ROOT / "experiments/causal_engineer/dev/repair_strategy_r0/cases.json")}
    require(sha((r0_raw / "SHA256SUMS").read_bytes()) == protocol["original_manifest_sha256"], "original manifest")
    labels = {}
    original_replayed = 0
    original_pairs = {p["unit_id"]: p for p in pairs}
    for name, digest in protocol["original_unit_sha256"].items():
        path = r0_raw / "units" / name
        require(sha(path.read_bytes()) == digest, "original R0 unit bytes")
        r = read(path)
        c, z, v = cases[r["instance_id"]], r["result"], r["verification"]
        require(r["seeds"] == c["seeds"] and r["base_id"] == c["base_id"], "original instance")
        require(v["seeds"] == {role: c["seeds"][role] for role in ("validate", "confirm")}, "original seed routing")
        pair = original_pairs[r["unit_id"]]
        selected = max(range(2), key=lambda i: (z["selection"][i]["walking_count"],
                       z["selection"][i]["survival_count"], z["selection"][i]["mean_fitness"], -i))
        require(selected == pair["selected"] == z["selected"] and pair["preverification"] == z["selection"], "original selector")
        for i, k in enumerate(pair["keys"]):
            require(cc[k]["candidate_sha256"] == z["selection"][i]["design_hash"]
                    and cc[k]["original"] == c["robot"] and cc[k]["plant"] == c["plant"], "original candidate/plant")
        k = identity(r["instance_id"], z["design"], v["seeds"], v["variation"])
        require(k == pair["keys"][selected], "selected candidate join")
        label, _, _ = replay(v, z["design"], v["seeds"], v["variation"])
        require(k in known and known[k] == label and (k not in labels or labels[k] == label), "known-label replay")
        labels[k] = label
        original_replayed += 1
    require(original_replayed == 324 and set(labels) == set(known), "original coverage")
    require({f.stem for f in (stage_a / "outcomes").glob("*.json")} == set(protocol["missing_keys"]), "A outcome coverage")
    eq = rows = 0
    statuses = collections.Counter()
    for k in protocol["missing_keys"]:
        r = read(stage_a / "outcomes" / f"{k}.json")
        c = cc[k]
        require(r["key"] == k and r["candidate_sha256"] == c["candidate_sha256"], "A outcome identity")
        labels[k], e, n = replay(r["verification"], c["candidate"], c["seeds"], c["variation"])
        eq += e
        rows += n
        statuses[labels[k]["status"]] += 1
    missed, reverse = [], []
    for pair in pairs:
        a, b = [labels[pair["keys"][i]]["status"] == FULL for i in (pair["selected"], 1 - pair["selected"])]
        if b and not a:
            missed.append(pair["base_id"])
        if a and not b:
            reverse.append(pair["base_id"])
    gain = len(missed) / 324
    gate_a = len(set(missed)) >= protocol["gate"]["minimum_missed_full_bases"] and gain >= protocol["gate"]["minimum_base_equal_oracle_gain"]
    saved_a = read(stage_a / "analysis.json")
    require(saved_a["stage_a_signal"] == ("ADVANCE_TO_B" if gate_a else "NO-GO"), "A registered gate")
    for name, value in {"missed_full_screens": len(missed), "missed_full_bases": len(set(missed)),
                        "reverse_screens": len(reverse), "reverse_bases": len(set(reverse)),
                        "new_equivalents": eq, "new_response_rows": rows}.items():
        require(saved_a[name] == value, f"A summary: {name}")
    close_number(saved_a["base_equal_oracle_gain"], gain)
    result = {"version": "h1-independent-stdlib-v1", "imports_project_physics_or_verdict": False,
              "original_r0_assessments_replayed": original_replayed, "stage_a_source_hashes": source_count,
              "stage_a": {"new_assessments": 320, "new_status_counts": dict(statuses), "new_response_rows": rows,
                          "new_equivalents": eq, "missed_full_screens": len(missed), "missed_full_bases": len(set(missed)),
                          "reverse_screens": len(reverse), "reverse_bases": len(set(reverse)),
                          "base_equal_oracle_gain": gain, "gate": gate_a,
                          "manifest_entries": check_manifest(stage_a)}}
    if stage_b is None:
        return result
    stage_b, bstudy = Path(stage_b), study / "stage_b"
    bp, jobs = read(bstudy / "protocol.json"), read(bstudy / "jobs.json")
    require(gate_a and sha((bstudy / "jobs.json").read_bytes()) == bp["jobs_sha256"], "B entry/jobs")
    for name in ("analysis", "independent_audit"):
        require(sha((stage_a / f"{name}.json").read_bytes()) == bp[f"stage_a_{'audit' if name == 'independent_audit' else name}_sha256"], "bound A prerequisite")
    for k, digest in bp["stage_a_outcome_sha256"].items():
        require(sha((stage_a / "outcomes" / f"{k}.json").read_bytes()) == digest, "bound A outcome")
    require(len(jobs) == len({j["key"] for j in jobs}) == 1280, "B job count")
    require(collections.Counter(j["candidate_key"] for j in jobs) == collections.Counter({k: 2 for k in cc}), "complete B cohort")
    require({f.stem for f in (stage_b / "outcomes").glob("*.json")} == {j["key"] for j in jobs}, "B outcome coverage")
    old = {s for c in cases.values() for ss in c["seeds"].values() for s in ss}
    for c in read(ROOT / "experiments/causal_engineer/dev/vel2/stage_a_cases.json"):
        old.update(s for panel in c["panels"] for ss in panel.values() for s in ss)
    owners, panel_labels, statuses, requirements = {}, {}, collections.Counter(), collections.defaultdict(collections.Counter)
    eq = rows = 0
    for job in jobs:
        k, panel = job["candidate_key"], job["panel"]
        require(panel in (1, 2) and job["key"] == sha(canonical([k, panel - 1, job["seeds"]])), "B job identity")
        for role, seeds in job["seeds"].items():
            require(role in ("validate", "confirm") and len(set(seeds)) == len(seeds) == 24 and not set(seeds) & old, "B seed disjointness")
            for seed in seeds:
                owner = (cc[k]["base_id"], panel, role)
                require(seed not in owners or owners[seed] == owner, "cross-panel seed collision")
                owners[seed] = owner
        r = read(stage_b / "outcomes" / f"{job['key']}.json")
        require(all(r[name] == value for name, value in job.items()) and r["candidate_sha256"] == cc[k]["candidate_sha256"], "B record identity")
        label, e, n = replay(r["verification"], cc[k]["candidate"], job["seeds"], cc[k]["variation"])
        require((k, panel) not in panel_labels, "duplicate candidate panel")
        panel_labels[k, panel] = label
        statuses[label["status"]] += 1
        eq += e
        rows += n
        for name, value in label["components"].items():
            requirements[name]["missing" if value is None else "pass" if value else "fail"] += 1
    require(len(owners) == 1728 == bp["new_unique_seeds"], "B unique seeds")
    stable = sum(len({labels[k]["status"] == FULL, panel_labels[k, 1]["status"] == FULL,
                      panel_labels[k, 2]["status"] == FULL}) == 1 for k in cc)
    def label_at(k, j):
        return labels[k] if j == 0 else panel_labels[k, j]
    totals = collections.defaultdict(lambda: collections.defaultdict(int))
    persistent, reversals, opportunities = set(), 0, 0
    for pair in pairs:
        keys, selected, scores = pair["keys"], pair["selected"], pair["preverification"]
        full = [[label_at(k, j)["status"] == FULL for j in range(3)] for k in keys]
        diffs = [int(full[1 - selected][j]) - int(full[selected][j]) for j in range(3)]
        if all(d > 0 for d in diffs):
            persistent.add(pair["base_id"])
        reversals += min(diffs) < 0 < max(diffs)
        opportunities += sum(max(0, d) for d in diffs[1:])
        choices = {"incumbent": selected,
                   "walking_keep_incumbent_ties": max((selected, 1 - selected), key=lambda i: scores[i]["walking_count"]),
                   "fitness_keep_incumbent_ties": max((selected, 1 - selected), key=lambda i: scores[i]["mean_fitness"]),
                   "survival_walking_fitness": max((selected, 1 - selected), key=lambda i: (scores[i]["survival_count"], scores[i]["walking_count"], scores[i]["mean_fitness"])),
                   "first_training_rank": 0,
                   "walking_first_training_tie": max(range(2), key=lambda i: (scores[i]["walking_count"], -i))}
        for name, choice in choices.items():
            totals[name][pair["base_id"]] += sum(int(full[choice][j]) - int(full[selected][j]) for j in (1, 2))
    controls = {}
    for name, bases in totals.items():
        values = list(bases.values())
        controls[name] = {"gain": sum(values) / 648, "whole_base95": percentile_interval(values, 648),
                          "bases_improved": sum(v > 0 for v in values), "bases_harmed": sum(v < 0 for v in values)}
    require(set(controls) == set(bp["prediction_rules"]), "registered control coverage")
    oracle = opportunities / 648
    checks = {"complete_error_free": True,
              "persistent_missed_bases": len(persistent) >= bp["gate"]["persistent_missed_bases"],
              "fresh_panel_oracle_gain": oracle >= bp["gate"]["fresh_panel_oracle_gain"],
              "legal_physical_decision_signal": any(c["gain"] >= bp["gate"]["physical_rule_net_gain"] and
                  (not bp["gate"]["positive_whole_base_lower95"] or c["whole_base95"][0] > 0) for c in controls.values())}
    saved_b = read(stage_b / "analysis.json")
    require(checks == saved_b["gate_checks"], "independent B gate checks")
    require(saved_b["stage_b_signal"] == ("SUPPORTS_FEASIBILITY_REVIEW" if all(checks.values()) else "NOT EVALUABLE"), "B signal")
    require(eq == saved_b["new_equivalents"] and rows == saved_b["new_response_rows"] and dict(statuses) == saved_b["new_status_counts"], "B count summaries")
    require(stable == saved_b["three_panel_full_stable_candidates"] and reversals == saved_b["strict_pair_rank_reversals"] and
            len(persistent) == saved_b["persistent_missed_bases"], "B repeatability summaries")
    require({k: dict(v) for k, v in requirements.items()} == saved_b["requirement_observed_missing"], "conditional requirement missingness")
    close_number(oracle, saved_b["fresh_panel_base_equal_oracle_headroom"])
    for name, c in controls.items():
        saved = saved_b["fixed_physical_rules"][name]
        close_number(c["gain"], saved["fresh_panel_base_equal_net_full_gain"])
        for a, b in zip(c["whole_base95"], saved["descriptive_whole_base95"]):
            close_number(a, b)
        require(c["bases_improved"] == saved["bases_improved"] and c["bases_harmed"] == saved["bases_harmed"], "control base counts")
    result["stage_b"] = {"new_assessments": 1280, "new_status_counts": dict(statuses), "new_response_rows": rows,
                         "new_equivalents": eq, "new_unique_disjoint_seeds": len(owners),
                         "stable_candidates": stable, "strict_rank_reversals": reversals,
                         "persistent_missed_bases": len(persistent), "oracle_headroom": oracle,
                         "gate_checks": checks, "gate": all(checks.values()), "fixed_physical_rules": controls,
                         "requirement_observed_missing": {k: dict(v) for k, v in requirements.items()},
                         "manifest_entries": check_manifest(stage_b), "source_hashes": check_sources(bstudy)}
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--stage-a", required=True)
    parser.add_argument("--stage-b")
    parser.add_argument("--study", default=str(DEFAULT_STUDY))
    parser.add_argument("--r0-raw")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    require(not Path(args.out).exists(), "audit output already exists")
    result = audit(args.stage_a, args.stage_b, args.study, args.r0_raw)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"audit_passed": True, "stage_a_gate": result["stage_a"]["gate"],
                      "stage_b_gate": result.get("stage_b", {}).get("gate")}, sort_keys=True))


if __name__ == "__main__":
    main()
