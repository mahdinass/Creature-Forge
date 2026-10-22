# Experience-learning P0: evidence publication and independent-audit handoff

- **Date:** 2026-10-22.
- **Branch:** `feature/experience-learning`. Read this with `docs/EXPERIENCE_P0_REPORT.md`, which holds the verdict and errata
  E1–E2, and `docs/plans/EXPERIENCE_LEARNING_PLAN.md` (revision 2).
- **No new experimental data:** no MuJoCo rollouts, no model training or calls, no Nebius, no sealed data, no V1 change.
- **Every row-level table** in `experiments/causal_engineer/dev/experience_p0/evidence/` was re-derived from the stored records
  by `scripts/exp_p0_evidence.py`. That script fails closed unless the re-derived rows equal the committed `outcomes.csv` and
  every aggregate equals the committed `analysis.json`; it passed.
- **Determinism:** before any export, `exp_p0_audit.py inventory` and `analyse` were re-run, and git showed no change to the
  six committed outputs.

## 1. Repository state

| commit | full SHA | parent | timestamp (author = commit) |
|---|---|---|---|
| plan revision 2 | `85aef4f532fa79b47a54d6a042afe3c0463ef7cc` | `63b688be8b66984c958c25159c9bc5d70a898811` | 2026-10-22T14:26:54+02:00 |
| audit code + outputs | `8aa3a166f3047fbdec3c51409993a8688421d2c3` | `85aef4f532fa79b47a54d6a042afe3c0463ef7cc` | 2026-10-22T14:51:53+02:00 |
| P0 report | `a181ddfe567b44bc63995ac91f46e863c1f22ceb` | `8aa3a166f3047fbdec3c51409993a8688421d2c3` | 2026-10-22T14:55:08+02:00 |

- **Ancestry:** `git merge-base --is-ancestor 3a740a74af4bdcafbc0b3dd7a012bc78d0fc0322 a181ddf` succeeds. Between the frozen V1
  commit and HEAD there are only `8cae193` (old proposal), `63b688b` (state record) and the three P0 commits.
- **V1 untouched:** `release/v1` and tag `v1.0.0-rc1` (tag object `a037194`) still resolve to `3a740a7…` on the remote. The
  P0 commits change no file outside the experience-learning paths, `docs/PROJECT_STATE.md` and `docs/memory/`.
- **Publication:** this handoff is committed and pushed in a fourth commit, a normal fast-forward push with no force. Its SHA
  and the remote ref are reported in the closing message of the session. History was not rewritten.

## 2. File index

`experiments/causal_engineer/dev/experience_p0/evidence/FILE_INDEX.sha256` holds the SHA-256 of every file listed here, except
this document. The hashes are of LF-normalised content, as git stores it; verify from the repository root of an LF checkout with `sha256sum -c experiments/causal_engineer/dev/experience_p0/evidence/FILE_INDEX.sha256`.

| file | content |
|---|---|
| `docs/plans/EXPERIENCE_LEARNING_PLAN.md` | revision 2: estimands, evidence taxonomy, outcome hierarchy, S/P/X levels, D1/D2, Phase-3 protocol, decision rules |
| `docs/EXPERIENCE_P0_REPORT.md` | P0 decision report (INSUFFICIENT-DATA), with errata E1–E2 |
| `docs/EXPERIENCE_P0_HANDOFF.md` | this handoff |
| `docs/memory/INCIDENTS.md` (last entry) | the walker-file incident note |
| `creature_forge/experience_audit.py` | registry, hashing, exclusions, normalisation, comparability, gates, whitelist |
| `creature_forge/experience_p0.py` | grouped/nested kNN, scores, decision value, risk–coverage, controls, bootstrap, datasets |
| `scripts/exp_p0_audit.py` | `inventory` / `analyse` (writes the committed outputs) |
| `scripts/exp_p0_evidence.py` | read-only, fail-closed evidence export (this publication) |
| `tests/test_experience_audit.py` | 22 no-physics tests, including the MuJoCo tripwire and the data-gated `RecordedGates` |
| `experience_p0/INVENTORY.md`, `inventory.json` | hash-pinned source manifest, support counts, gates, provenance checks |
| `experience_p0/outcomes.csv`, `comparability.csv` | committed outcome rows and the S/P/X comparability table |
| `experience_p0/ANALYSIS.md`, `analysis.json` | committed Phase-3 aggregates |
| `evidence/p0_outcome_rows.csv` | all 2,587 outcome rows with file, line, file SHA-256, arm, engine, settings hashes, stop rule, plant/twin budget and use, verifier fields (status, walking fraction, validation/confirmation rollouts, reasons), harness arm/replicate/noise seed, stop-calibration origin/design source/condition |
| `evidence/p0_exclusions.csv` | 160 record-level exclusions (ineligible plants) and every file-level exclusion with its reason |
| `evidence/p0_comparison_exclusions.csv` | 456 outcome rows kept as outcomes but excluded from comparisons (324 oracle-informed, 132 with no resolvable tool) |
| `evidence/p0_level_SP_instances.csv`, `p0_level_SP_rows.csv` | every level-S/P comparable instance and each contributing row with full procedure, budget, verifier and source |
| `evidence/ds1_cases_init_rows_with_sources.csv` | the 947 DS-1 `cases_init.json` rows rebuilt with source file and line, mapped to P0 rows |
| `evidence/ds1_same_label_candidates.csv` | the 103 (instance, DS-1 label) groups on 70 instances, with rows, procedures and the reason none is level S |
| `evidence/ce_per_case_predictions.csv` | proxy-tier decision analysis: fold (held-out group), k, pick, π0, values, gates, P(repair) per tool and the measured outcome, for 3 schemes × 8 methods × 165 cases |
| `evidence/ce_shuffled_permutations.csv`, `ce_hard_negative_queries.csv` | 20 shuffle permutations per method; the 105 hard-negative queries with their positive and negative neighbours |
| `evidence/ident_per_case_predictions.csv`, `ident_model_posteriors.csv`, `ident_exclusions.csv` | HDB diagnostic precondition per case (2 schemes × 6 methods × 302), the stored model posteriors, and the 38 excluded panel rows |
| `evidence/raw_source_provenance.csv` | sanitized provenance of every raw source (paths as `<VM_ROOT>/…` or `<REPO>/…`, SHA-256, bytes, records); excluded files listed without being opened |
| `evidence/reconciliation_summary.json` | reconciliation counts, dependency versions, and the passed check list |
| `evidence/test_results.txt` | captured test run (§4) |

## 3. Reproduce

Run from the worktree, with the main checkout's `.venv`. The worktree has no venv.

```
..\Creature-Forge\.venv\Scripts\python.exe scripts\exp_p0_audit.py inventory  --vm-root ..\Creature-Forge\artifacts\vm
..\Creature-Forge\.venv\Scripts\python.exe scripts\exp_p0_audit.py analyse    --vm-root ..\Creature-Forge\artifacts\vm
git status --short     # expect no change to experiments/causal_engineer/dev/experience_p0/*
..\Creature-Forge\.venv\Scripts\python.exe scripts\exp_p0_evidence.py         --vm-root ..\Creature-Forge\artifacts\vm
..\Creature-Forge\.venv\Scripts\python.exe -m unittest tests.test_experience_audit tests.test_frozen_records tests.test_frozen_paths tests.test_ds1 -v
```

- **Runtimes, locally:** about 15 s, 2 min, 3 min and 10 s.
- **Environment:**
  - Python 3.11.9, numpy 2.4.6, on Windows 10.0.26200;
  - MuJoCo 3.15.0 is installed but never called (tripwire);
  - the code is pure Python + numpy; no other dependency.
- **Without the raw records** (anyone working only from GitHub): the first three commands need the git-ignored records (§6).
  Every aggregate can still be recomputed from the committed per-case CSVs. For example, for the primary contrast: take
  `ce_per_case_predictions.csv`, scheme `LOBO`, and compare the mean of `v_mem` for `interv` with that for `obs_morph`.

## 4. Test results (captured in `evidence/test_results.txt`)
- **Run:** under a global MuJoCo tripwire (`mj_step`, `mj_forward` and `MjModel.from_xml_*` raise).
- **Result:** 45 tests, 0 failures, 0 errors, 0 skipped, 0 tripwire calls. The suites were `test_experience_audit` (22,
  including `RecordedGates` against the local records), `test_frozen_records`, `test_frozen_paths` and `test_ds1`.
- **Not run:** the full 1,614-test suite, because it contains physics tests and new rollouts are not authorised.

## 5. D1/D2: exact definitions and chronology

**Definitions** (plan §4; code `experience_audit.adequacy`):
- **D1:** level-S support with no outcome missing by policy choice, ≥ 10 informative bases and ≥ 30 informative instances.
- **D2:** additionally FULL_VERIFIED, with ≥ 20 informative bases, ≥ 40 informative instances and ≥ 3 fault families each on
  ≥ 2 bases.
- **Level P** never qualifies. A proxy tier never gives a GO.

**Chronology** (CEST; times from file modification times of the session scratch scripts and from commit timestamps):

| time | event |
|---|---|
| 14:17:29 / 14:17:53 | schema profiling of named HDB files (`profile.py`, `peek.py`) |
| 14:18:20 | `xprof.py`: record counts per HDB file (the walker-file parse, §7) |
| 14:21:26 | `multi.py`: preliminary HDB feasibility count of instances with ≥ 2 verified tools (engine v6: 27 with 10 differing; v5 excluding MKV: 41 / 16; any procedure: 363 / 136; none of them on the identifiability panel within one engine version) |
| 14:21–14:26 | inline inspection of the causal-engineer dev builds and probe set (165 complete 10-tool matrices on 12 bases; repairing-tool distribution) and reading of the existing `LEVEL_C_LOBO.md` results |
| **14:26:54** | **plan revision 2 committed with D1/D2** |
| ~14:37–14:47 | first module runs: inventory; a first `analyse` aborted on a whitelist false positive (a family name in a column label, fixed by indexing); the analysis outputs |
| 14:51:53 / 14:55:08 | code + outputs commit; report commit |

**Disclosure.**
- When D1 was written, the causal-engineer tier was already known to have 12 bases and complete matrices. D1's base threshold
  of 10 therefore did not constrain that tier independently.
- The HDB verdict does not depend on any threshold. Level S has 0 informative instances, so every positive threshold fails.
- The proxy-tier analysis protocol and its primary contrast were fixed before any Phase-3 metric was computed.

## 6. Cohort reconciliation

### 6.1 DS-1 `cases_init.json`
Rebuilt row by row with the DS-1 offline construction (`scripts/ds1_offline.py` §3).

| measure | value |
|---|---|
| rows | 947 (engine_final 231, engine_old 304, a0 219, diverse 193) |
| instances; bases | 231; 20 |
| multi-tool instances | 194 |
| same-label groups (instance, label, ≥ 2 tools) | 103 (engine_old 54, diverse 49) |
| … on instances; bases | 70; 8 |
| … instances with differing recorded FULL | 21 (groups: diverse 17, engine_old 8) |
| rows found in the P0 corpus (same file and line) | 947 / 947 |
| DS-1 instance ids in the P0 corpus | 231 / 231 |
| stop-calibration rows DS-1 excluded as MKV-origin | 259 |

- **Order and content:** the rebuilt rows match `cases_init.json` in order and content (instance, tool, label, FULL). This is
  checked in code.
- **Why none of the 70 same-label instances is level S.** A DS-1 label is not a single procedure.
  - `engine_old` pools four arms: `vs4_A1c` (engine v4, calibrated stop), `vs4_a1` (v4, provisional stop), `vs4_A1f`
    (v4, spend all) and `vs2_a1` (engine v2). Each arm chose its tool from its own belief and remaining budget.
  - `diverse` holds stop-calibration designs re-verified by `full_recovery_v1`. They were produced inside engine-v2 episodes
    by different steps (`twin:…`, `counterfactual:…`, `repair:…`), and none has a per-design budget.
  - No tool was assigned. Row-level evidence for every group is in `ds1_same_label_candidates.csv`.
- **Where they land in P0:**
  - 27 of the 70 are level P (two or more tools among engine-v4 arms that differ only in stop rule) and 43 are level X;
  - of the 21 with differing FULL, 9 are level P (2 of them informative at level P) and 12 are level X only;
  - of the 194 multi-tool instances, all 194 are level X, 31 are level P (6 informative), and 0 are level S.

### 6.2 The P0 counts
- **2,587 outcome rows.** Every verified submitted repair in the registered development files: Stage 1 1,120, MKV 298,
  Stage 2 268, DS-1 212, TA-1 4, DO-1 17, plus 668 stop-calibration re-verifications.
  - Several rows can describe one plant, for example deterministic equivalence re-runs.
  - DS-1's 947 are a subset: init bases only, three procedure labels and one label per source file, with MKV-origin
    stop-calibration designs excluded.
- **476 plants:** unique (bench version, instance): hdb_v1 20, hdb_v2 413, hdb_v2_devcomp 43. An instance id under HDB v1 and
  v2 is two plants.
- **46 bases:** the 48 declared development bases minus `hdb-v1-gen-0101` and `hdb-v1-gen-0117`, which have no verified
  outcome in any registered file.
- **124 / 39 / 22:**
  - level-P instances: ≥ 2 tools within one engine version among non-oracle engine or Nemotron rows;
  - of these, 39 informative instances on 22 bases;
  - by engine: v4 39, v5 36 + 15 compositions, v6 24 + 6 compositions, v1 4.
  - 33 of the 124 lie on the DS-1 init bases; the other 90 come from Stage-2 and DS-1 multi-arm runs on transfer and stream
    bases.
- **165 / 12:** the causal-engineer probe set, an older bench. All 10 tools were assigned at budget 160, and the outcome is
  the walking proxy, not the verifier.

### 6.3 Exclusions
Each one is listed with its reason in the evidence CSVs.
- **Record level:**
  - 160 plants not eligible by physics;
  - 0 records off the 48 development bases;
  - 38 identifiability-panel rows (skipped or ineligible).
- **Comparison level (rows kept as outcomes):**
  - 324 oracle-informed (MKV K1–K4, and stop-calibration designs from those conditions);
  - 132 with no resolvable tool (an initial design was submitted).
- **File level:**
  - 6 superseded partial files;
  - 24 mirrors (23 identical; `hdb/artifacts/hdb/ds1/pilot_A1e.jsonl` has one extra FULL record,
    `hdb-v1-gen-0040:short_feet:2`, and the canonical copy was used);
  - 18 fault-bench instance builds;
  - 2 stop-data files (evidence only).
- **Never opened:** the walker file, the causal-engineer held-out shards, ledgers, the noise calibration and the LLM pilots.
- **No counterfactual outcome was inferred anywhere.**

## 7. The earlier `walkers_all.jsonl` access
See the incident note in `docs/memory/INCIDENTS.md` (2026-10-22). The exact script, preserved from the session scratch area
and never re-run:

```python
import json, glob, os, collections, sys
sys.path.insert(0, "<WORKTREE>")
from creature_forge.has_cases import final_tool
H = "<VM_ROOT>/hdb/artifacts/hdb"
D = "<VM_ROOT>/ds1"
split = json.load(open("<WORKTREE>/experiments/causal_engineer/dev/hdb/stage2_split.json"))
dev = set(split["experience_bases"]) | set(split["transfer_bases"])
files = sorted(glob.glob(H+"/*.jsonl")) + sorted(glob.glob(H+"/stage2_final/s2_*.jsonl")) + sorted(glob.glob(D+"/eval/*.jsonl")) + sorted(glob.glob(D+"/*.jsonl")) + sorted(glob.glob(H+"/ds1/stream/*.jsonl"))
for f in files:
    n=0; arms=collections.Counter(); benches=collections.Counter(); offbase=0; ver=0; tools=collections.Counter()
    for l in open(f, encoding="utf-8"):
        if not l.strip(): continue
        try: r=json.loads(l)
        except Exception: continue
        n+=1
        iid=r.get("instance_id","")
        b=iid.split(":")[0]
        if b not in dev: offbase+=1
        arms[r.get("arm") or r.get("condition") or r.get("source","")[:12]]+=1
        benches[r.get("bench")]+=1
        if isinstance(r.get("verification"),dict) or "status" in r: ver+=1
    print(f"{os.path.relpath(f,'<VM_ROOT>'):60s} n={n:4d} ver={ver:4d} off={offbase:3d} bench={dict(benches)} arms={dict(arms.most_common(6))}")
```

Only the local root paths are replaced by placeholders.

- **Output for the file:** `n= 250 ver= 250 off=250 bench={None: 250} arms={'': 250}`.
- **Effect on P0:** it did not influence splitting (the pre-existing `stage2_split.json`), the D1/D2 thresholds or any feature.
- **Contamination:** no P0 population is treated as contaminated. For the sealed HDB test split, log a schema-level exposure:
  250 rows, plus the presence or absence of the listed keys.
- **What the file contains:** "test-split walker designs" is inferred from `hdb_bench.load_bases`; it was not inspected.

## 8. Known failures and defects
- **Report errata** (P0 report, top):
  - E1: the level-S instance is TA-1 L1, not L4;
  - E2: `outcomes.csv` leaves `plant_used` / `twin_used` empty for A0 and MKV rows.
  - Neither changes a count, gate or conclusion.
- **Fixed before the commit:**
  - a whitelist false positive;
  - a provenance-check tolerance bug (rounded morphology table, which reported 0/N body matches); after the fix, 85/85
    controller-only faults match.
- **Not run:** the full test suite, which includes physics. CI cannot run `RecordedGates` or the evidence export, because the
  records are git-ignored.
- **Unavailable this session:** the `basic-memory` and GitHub MCP servers failed to connect. Git CLI was used.
- **Pyright warnings:** "import not resolved" in the worktree, because the worktree has no venv. These are environment-only.

## 9. Source artifacts that are not in the repository
- **The VM pull** `<VM_ROOT>` = `<main checkout>/artifacts/vm`. It is git-ignored, and every file's SHA-256 is in
  `raw_source_provenance.csv`. It includes `ds1_all.tgz`, whose hash is also listed.
  - Not committed: size, DS-1 Nemotron prompts and responses inside the records, and the fact that it is not part of the
    reviewed record set.
- **`mkv2.jsonl`:** the stop-calibration origin file. Only `mkv2_partial.jsonl` was pulled, and its bench label is applied
  through `ORIGIN_ALIAS`.
- **Missing in historical records:**
  - per-seed validation rows (discarded at run time; FA-1B);
  - source commit;
  - optimizer seeds.
- **Sealed or never opened:** the walker file, the causal-engineer held-out shards and the HDB test split.
- **Not committed:** the owner-supplied literature review ("Causal Experience Learning for Creature Forge"). The plan cites it
  by title.

## 10. Outstanding scientific uncertainties
1. **Proxy vs verifier:** the only D1 tier uses the walking proxy on an older bench, where the fault is visible in the body.
   Transport to FULL was contradicted once (causal-engineer held-out, learned 18 vs exhaustive 23 of 40).
2. **D1 chronology:** the base threshold was set with the proxy tier's size known (§5).
3. **Tool attribution:** the tool is the last repair step's. Multi-step designs are not decomposed.
4. **Level P** pools stop-rule variants of one engine version. It is descriptive only.
5. **MKV records** store no verification-stage breakdown. Their FULL statuses could not be checked for the confirmation stage;
   every other FULL row shows confirmation rollouts > 0.
6. **HDB diagnostic retrieval** used raw panel features, not nominal-twin residuals. The weak cross-robot result may reflect
   that representation, not a lack of transportable information.
7. **Fixed equal block weights** may have hidden the counterfactual-only signal (exploratory, LOBO +0.121). That needs fresh
   data.
8. **Campaign cost** (report §8.4) is extrapolated from W3 and DS-1 throughput. The pilot is designed to measure it.
9. **Effective sample sizes are small:** 12 bases (Kish 10.8) on the proxy tier, and 22 informative bases at level P.
