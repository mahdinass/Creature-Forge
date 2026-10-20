# DS-1 report: dual-signal development iteration (development evidence)

Date: 2026-10-20. Branch `feature/has-scientist`. Protocol: `docs/DS1_PROTOCOL.md` (pre-declared, amendments 1 and 2).
Plan: `docs/DUAL_SIGNAL_PLAN.md`. Raw tables: `experiments/causal_engineer/dev/hdb/DS1_RESULTS.md`.

Status: **DRAFT — LLM dev-eval and learning stream still running on the main VM; sections marked PENDING are filled from
their records when they finish.**

Everything below is development evidence on dev mechanisms and dev-side robots. It is not a registered result and supports no
claim. The sealed test split, the held-out families and Stage 3 were not touched. The frozen HDB v2 modules, `verdict_v1`,
`full_recovery_v1` and the pinned modules are byte-identical.

## 1. What was built

- **Engine v6** (`belief_engine`, flag `--v6 engine_v6_settings.json`; without the flag the engine is exactly v5, verified
  bit-identical to the Stage-2 A1e records):
  - tempered likelihood, T = 6 (leave-one-base-out on init bases);
  - structural misfit statistic (threshold −6.532, 5th percentile on correctly diagnosed init singles) → composite pair
    hypotheses under a hard twin budget of min(500, twin remaining − 1,750);
  - open-world "unmodelled" reserve (counts against diagnosis confidence, never used to design repairs);
  - relative assimilation of every plant robustness check of a repaired design (only differential predictions move the
    belief), with re-screen when the leader changes;
  - budget guard: diagnosis ends when the twin budget would fall below the repair reserve (added after the DS-1 smoke
    showed the reserve and tempering could starve the repair).
- **Displacement-aware evidence** (`hdb_evidence.EvidenceWorkbench`, new subclass; frozen workbench untouched): per-seed
  forward displacement on robust seeds, one charged faulty-design baseline, paired wins/losses and a proxy of
  `verdict_v1`'s rule on robust seeds only.
- **Stop map v2** (logistic P(FULL | robust16, stress4, displacement evidence)), fitted on 678 init-base designs.
- **Repair learning** (`repair_learning.py`, R-head) and the **shared causal experience store** (`has_cases.py`) with
  dual-scored dossiers (diagnostic precision/recall; repair lift).
- **Agent v5** (A3v5): informative constraint feedback in the single repair call and a registered P(success) on every
  repair decision.
- **Stage scripts:** `ds1_stop_map.py`, `ds1_stream.py` (updating vs frozen, chronological rounds, resumable), `ds1_pilot.py`,
  `ds1_report.py`, `ds1_launch.sh` (detached tmux, checkpointed outputs, VM-side finalisation and power-off).

## 2. Offline stage (`experiments/causal_engineer/dev/hdb/ds1/OFFLINE.md`)

- **Temperature:** T = 6 raised LOBO mean log P(true structure) from −2.392 (T = 1) to −1.884 on 219 init singles;
  confidently wrong (≥ 0.95 on a wrong structure) 56 → 7.
- **Stop map v2 beats v1** on leave-one-base-out (678 designs, 20 bases): Brier 0.099 vs 0.166, AUROC 0.935 vs 0.832. At
  τ = 0.75 it accepts 190 designs, of which 85 % verify (v1: 142, 77 %). As pre-declared, v6 uses map v2.
- **Gate G-a: NOT PASSED.** The R-head has better LOBO log loss than the engine-evidence baseline B1 (0.568 vs 0.609), but
  on comparable support its choices verify less often than the engine's own (85.7 vs 89.3 expected FULL of 194; base
  bootstrap 90 % CI of R-head − engine [−9.3, 1.9]). Consequences (amendment 1): A1x not run; the R-head never orders
  tools; A4x shows it only as calibrated evidence; the non-LLM updating-vs-frozen stream pair is dropped. **Repair learning
  is reported as null.**

## 3. Pilot gates (`experiments/causal_engineer/dev/hdb/ds1/PILOT.md`)

| gate | result |
|---|---|
| G-b reply validity ≥ 95 % | 26/26 model role calls ok — **pass** |
| Equivalence: A4x with no scientist = A1e6 | identical verification, ledgers, design vectors, leading explanation — **pass** |
| G-m (1) composite work within the repair reserve | 15/15 v6 composition episodes — **pass** |
| G-m (2) leading explanation shares an injected primitive no less often than v5 (13 init-base compositions) | v5 7/13, v6 5/13 — **FAIL** (FULL v5 6/13, v6 4/13; the unmodelled reserve led in 5/13) |

Amendment 2 (written before any stream or dev-eval outcome was read) declares: no credit for the composite mechanism; no
engine fix inside DS-1; the stream and dev-eval continue because their learning and Nemotron contrasts compare arms on the
identical engine v6; Stage 3 does not adopt v6's composite mechanism without a new gate on independent compositions.

## 4. Engine result: v6 vs v5 without the LLM (dev-eval-2, 18 transfer bases, complete)

A1e (engine v5 with stop map v1, the exact Stage-2 configuration) vs A1e6 (engine v6 with stop map v2). Same instances,
seeds, plant budget 700 and twin cap 2,800. Batch VM, no inference key used.

| measure | single mechanism (n 30): A1e6 / A1e | compositions (n 6): A1e6 / A1e |
|---|---|---|
| mean log P(true structure) | **−2.54** / −2.93 | **−4.61** / −9.21 |
| confidently wrong (≥ 0.95 on a wrong structure) | **4** / 9 | **0** / 6 |
| ECE of leading mass | **0.27** / 0.39 | **0.35** / 0.98 |
| leading explanation correct | 19 / 18 | 3 / 0 |
| leading explanation shares a true primitive | 21 / 18 | 4 / 3 |
| FULL recovery | 8 / 9 (discordant 1 vs 2, p(A1e6 > A1e) = 0.875) | 1 / 1 |
| mean validation walking | 0.70 / 0.67 | 0.76 / 0.67 |
| plant / twin rollouts per episode | 621 / 2,508 vs 604 / 1,980 | 584 / 2,575 vs 697 / 2,026 |
| stop-map Brier on submitted designs | 0.19 / 0.21 | 0.16 / 0.36 |

- **Diagnostic signal: better calibrated.** v6 is far less often confidently wrong and puts more probability on the truth,
  on singles and on compositions. This is the effect of tempering and the open-world reserve (on compositions v5 was
  confidently wrong in 6/6).
- **Repair signal: no improvement.** FULL is 8 vs 9 and 1 vs 1. Better calibrated belief did not turn into better repairs.
- **Cross-feedback was inert.** 76 + 12 plant checks were assimilated; the leading explanation never changed, so no
  re-screen was triggered (11 assimilations skipped for twin budget). Across the 88 assimilations:
  - the competing hypotheses' predicted walking (of 8 robust seeds) was identical in 28 and differed by ≤ 1 seed in 39;
  - the observed walking lay inside the hypotheses' predicted range in 75;
  - the median posterior shift (total variation) was 0.003, and only 8 shifts exceeded 0.1.

  Repair outcomes on the plant carried little differential information about the mechanism, so the relative update had
  little to move.
- This does not contradict G-m: the 6 dev-eval compositions are a different, smaller set, and the composite mechanism is
  given no credit (amendment 2).

## 5. Nemotron contrast: A3v5 vs A1e6 (identical engine v6, complete)

| measure | single mechanism (n 30): A3v5 / A1e6 | compositions (n 6): A3v5 / A1e6 |
|---|---|---|
| FULL recovery | 8 / 8 (discordant 2 vs 2, p = 0.69 either way) | 2 / 1 (discordant 1 vs 0, p = 0.50) |
| mean validation walking | 0.64 / 0.70 (Wilcoxon p(A1e6 > A3v5) = 0.11) | 0.76 / 0.76 |
| mean log P(true structure) | −2.84 / −2.54 | −4.61 / −4.61 |
| leading explanation correct | 15 / 19 | 3 / 3 |
| confidently wrong | 6 / 4 | 1 / 0 |
| shares a true primitive | 21 / 21 | 4 / 4 |
| plant / twin rollouts per episode | 540 / 2,632 vs 621 / 2,508 | 567 / 2,689 vs 584 / 2,575 |
| assimilated checks (skipped for twin budget) | 33 (42) vs 76 (7) | 3 (8) vs 12 (4) |

- **Repair signal: no Nemotron effect.** FULL is equal on singles and differs by one discordant pair on compositions;
  validation walking is slightly lower with Nemotron. A3v5 spends fewer plant rollouts and more twin rollouts.
- **Diagnostic signal: Nemotron's experiments and hypotheses made the engine's belief slightly worse on singles**
  (lower log P(truth), fewer correct leaders, more confidently wrong) and left compositions unchanged.
- **Registered P(success):** present on 30/30 single and 6/6 composition repair decisions; mean 0.52 on singles, Brier
  0.329. A constant forecast at the observed base rate (8/30) would score 0.196, so Nemotron's success forecasts were
  worse than uninformative. The stop map on the same submitted designs: Brier 0.157.
- **Deviations from the engine default:** 9 of 30 singles (FULL 2/9) and 1 of 6 compositions (FULL 1/1); delegated
  episodes FULL 6/21 and 1/5.
- Nemotron's extra twin use left the cross-feedback step short of budget more often (42 skipped vs 7).

## 6. Experience contrast: A4x vs A3v5 and A4x vs A1e6 (M_final memory) — PENDING

## 7. Learning stream: A4x-updating vs A4x-frozen (20 instances, 4 rounds, stream bases, complete)

Same instances in the same order; the updating arm appends its verified outcomes after each round (R-head, dossier support
and track record refreshed); the frozen arm keeps the init memory.

| round | n | FULL upd / frz | mean log P(truth) upd / frz | Nemotron P(success) Brier upd / frz | repair-model Brier on the round, store before the round: upd / init |
|---|---|---|---|---|---|
| 0 | 5 | 1 / 1 | −2.10 / −2.61 | 0.348 / 0.229 | 0.290 / 0.290 |
| 1 | 5 | 2 / 2 | −3.62 / −1.86 | 0.187 / 0.213 | 0.231 / 0.231 |
| 2 | 5 | 1 / 1 | −2.15 / −1.92 | 0.430 / 0.451 | 0.264 / 0.267 |
| 3 | 5 | 3 / 3 | −1.89 / −1.86 | 0.149 / 0.251 | 0.369 / 0.393 |

- **No learning effect.** Over the stream FULL is 7 vs 7 (discordant 2 vs 2, p = 0.69 either way); validation walking
  differs by 0.04 in favour of the frozen arm (Wilcoxon p = 0.21).
- **Repair signal:** the refreshed repair-outcome model scored the next round no better than the init model (differences
  ≤ 0.03 Brier). Twenty new outcomes on top of 947 init cases barely move it.
- **Diagnostic signal:** no trend; the updating arm's log P(truth) was lower in 3 of 4 rounds.
- **Nemotron's success forecasts:** Brier lower for the updating arm in rounds 1–3, higher in round 0; with 5 episodes per
  round this is not distinguishable from noise.
- In round 0 both arms use the identical init memory, so its differences are LLM run-to-run variation alone; they are
  as large as the differences in later rounds.

## 8. Gate G-c (Stage-3 eligibility of A4x) — PENDING

A1x was not run (G-a failed). With G-a failed the R-head never orders tools, so A1x would be the A1e6 engine; the
equivalence check showed A4x without a scientist reproduces A1e6 exactly. A1e6 is therefore the comparator for the
"not worse than A1x by more than 2 discordant pairs" clause.

## 9. Costs — PENDING

## 10. Operational notes

- `extend --hours H` sets the deadline to now + H (not additive); it briefly cut the main VM to 4 h and was corrected.
- The batch VM has carried a pre-existing inference-key line in `~/dev/.env` (mode 600, dated 2026-10-16, before DS-1). It
  was not read or changed; the batch runs had no live flag and made no inference calls. Removal is the owner's decision.
- Stream round 0 singles initially failed (the stream driver did not pass all severities to the runner, which then failed
  loudly); the driver was fixed (`9ae1d84`) and the round resumed with the completed compositions kept.

## 11. Limitations

- Development evidence only; n = 30 + 6 per arm and 20 stream instances cannot confirm small effects.
- The Stage-2 failure analysis read aggregate records on the transfer bases.
- R-head rows are missing not at random (offline §3).
- Arm comparisons share instances and seeds but LLM episodes are not deterministic.

## 12. Recommendation and Stage-3 decision — PENDING
