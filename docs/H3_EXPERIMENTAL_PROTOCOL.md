# H3-SR pilot v1 — frozen before physical outcomes

Date: 26 October 2026. Status: **PROPOSED; NOT AUTHORIZED TO EXECUTE.** This protocol and machine-readable `experiments/causal_engineer/dev/h3/plan.json` must be committed/pushed before any H3 physics. Subsequent scientific changes require a new version before affected outcomes; never overwrite this version or prior evidence. Exact plan SHA and normalized source hashes bind execution. H3 financial authorization is currently zero. H1 permission is inapplicable.

## Question, scope and population

Test [H3-SR](H3_SELECTED_HYPOTHESIS.md), an engineering controller-class hypothesis. No neural learning, memory benefit, Nemotron advantage or full A1-system improvement is claimed. Primary comparison is body-fixed current17D versus nested19D at equal physical search budget;17D double-budget is the stronger search-explanation control.

Generate48 new guided symmetric nominal bodies with existing `creature_gen.sample_body`; draw seed202610260300+i, i=0..47. Each is a new root lineage, not a perturbation or descendant of a historical robot. The plan stores exact bodies, initial controller, fault side and all seeds before qualification. Check exact body hash uniqueness and exclude exact known H1/R0 nominal-body matches using the pinned H1 candidate packet; record the checked historical hashes. Any collision stops for a pre-outcome amendment, never silent replacement. This check does not open sealed morphology records. Independence comes from fresh root generation, not proof of distance from all possible historical bodies. No old outcome becomes an untouched test.

Initial controller is frozen R2 transferred15D plus FP gains(0.5,0.5); no nominal-controller optimization. Fault is one primitive: `actuator_strength`0.4 for all left motors on even draws/right on odd draws. No gap, delay or sealed-family data. Side/magnitude are evaluator-only: the search/score function receives responses but no diagnostic label/side feature. Controller has no hidden-plant access. This isolates a known developmental unilateral family, not general unknown-fault diagnosis.

Qualification, once per attempted draw on dedicated seeds:

1. Nominal10-second walk: at least7/8 walking, no errors.
2. Nominal20-second walk on8 different seeds: at least7/8 walking, no errors.
3. Damaged10-second walk on8 different seeds: at most1/8 walking, no errors.

Use existing arena variation/conditions. Retain first six eligible lineages per side, skipping remaining draws on a side after its quota. Qualification outcomes never tune parameters or thresholds. No replacement outside the48-draw stream. Fewer than6+6 yields **NO-GO / insufficient acquisition**, with all rejected/unattempted draws reported and no adaptation run. Qualification yield is unknown; severe0.4 loss may make this target sparse or infeasible. This conditional target excludes healthy failures and does not estimate population-wide recoverability.

## Gates before adaptation

T0: current source hashes/environment/permissions verified; both VMs API-confirmed STOPPED and no prior executor active; fresh Cloud balance usable with$5 reserve; explicit new H3 approval; batch-only cap/deadline and existing external shutdown supervision configured. No Cloud launch is performed by the research runner.

T1: native zero-gain equivalence on draw0, nominal and damaged, three seeds each. Compare every numeric rich trajectory array exactly between current17D and19D gains(0,0), including NaN positions represented as null; controller name metadata is expected to differ and excluded. Compare complete seed-job response rows for both paths using identical arena conditions. No native errors allowed. Budget24 expected10-second rollouts, conservative maximum240 equivalents. FAIL => NO-GO; preserve evidence, stop, no optimization. This is **new physics** and has not been run.

T2: qualification passes6+6 and measured runtime forecasts the whole remaining study within dollars/time with25% slowdown and shutdown/retrieval reserve. An original optimistic throughput forecast cannot waive this gate. Stop if it does not fit; use no extra funds or shortened panels.

## Adaptation and controls

Two conventional optimizer replicates per lineage; same predefined train/select/optimizer seed roles across arms within replicate. Four10-second training seeds and eight disjoint10-second selection seeds. Native arena conditions remain unchanged. Same CMA implementation (`walk_opt._CMA`), population12, sigma0.2, existing17D bounds, lexicographic walking/survival/fitness ranking and frozen ordinal rank update. Added gains only in residual arm, bounds[−1,1]. No learned model, warm-start history, post-outcome rule, body modification or IPOP in any arm.

| Arm | Parameters | Total policy rollouts per replicate, including16 finalist-selection rollouts |
|---|---|---|
| current | Existing17D FP | 3,000 |
| residual | Existing17D + two residual gains | 3,000 |
| current2x | Existing17D FP, same kernel | 6,000 |

Initial candidate uses four training rollouts. Full12-candidate generations follow; remaining training budget is filled with a partial population without CMA update. Two distinct finalists are selected by saved training scores, then evaluated on eight independent selection seeds; choose one using the same lexicographic rule, stable ties in generation order. All six final policies are persisted **before any FULL evaluation**. This is a matched current-family implementation, not a claim that this kernel dominates every existing optimizer. The larger control explicitly spends more budget and is secondary as a budget-matched contrast, but must also be beaten for PASS-PILOT.

## Independent evaluation and reliability

For each frozen policy, run unchanged `recovery.assess(full_recovery_v1)` on three independent panels, shared across arms/replicates within lineage. Each panel has24 paired original/candidate10-second validation seeds and, when native validation qualifies,24 independent candidate20-second confirmation seeds. Panels are disjoint from train, selection and qualification. Seed ranges/roles are explicit in the plan. Candidate selection never sees these results.

Preserve unchanged FULL conditions: paired sign-test improvement with at least6 non-ties, one-sided p<.05 and median displacement gain≥0.5 m; validation walking≥20/24; conditional confirmation walking≥20/24, morphology-scaled median speed and every-seed body contact≤0.005. Any error is inconclusive, never success. Independently replay every assessment from saved rows using the existing stdlib H1 verifier replay; do not rerun physics to repair labels. Unexecuted confirmations stay missing with their conditional denominator.

Healthy guard: each frozen policy gets eight new20-second nominal seeds, common across arms. Diagnostics: each gets two new10-second damaged rich trajectories, with all arms logging current phase, loaded flag, base demand and added demand. Preserve raw joint/demand/delivered-torque/contact/slip arrays. Pre-step controller samples and post-step physics traces are separate time bases; do not treat them as exactly simultaneous. `tracking_error` remains demand/Kp, not true tracking error. Rich diagnostics are collected after candidate freezing and cannot drive reselection.

## Outcomes, analysis and decision

Primary: lineage-equal mean FULL probability estimated from six technical outcomes per arm (two optimizer replicates×three panels). Primary contrasts: residual−current and residual−current2x. **n=12 independent lineages**, never72 or216 independent robots. Report side strata, all per-base outcomes, persistent FULL patterns and optimization replicate variation.

Stratified whole-lineage bootstrap: independently resample the six left and six right bases10,000 times, seed2026102603; preserve all arms/repeats per sampled base. Report descriptive90% and95% percentile intervals. These small-pilot intervals are not a powered confirmatory test or a verifier's per-panel sign-test uncertainty. No test-data tuning or threshold updates.

Secondary: paired physical displacement/walking/speed/contact requirements, actual rollouts/equivalents, wall/cost; harmful-intervention rate (`WORSE` versus the original); healthy nominal walking. Report first-panel FULL that fails to remain FULL on all three panels as **label-instability proxy**, with numerator/denominator, not a ground-truth false-success estimate. Generalization is only to qualified new lineages drawn here; no hardware,3D, other faults or learning-transfer inference. No probabilistic model is trained, so no learned calibration claim is planned.

**PASS-PILOT** requires all of:

- Both primary contrasts≥0.15, with each descriptive90% lower bound>0.
- At least three bases with one residual optimizer replicate FULL on all three panels and no such current2x replicate.
- Residual healthy walking≥0.80 overall, and residual−each control healthy-walking difference≥−0.05.
- Residual−each control harmful-intervention rate≤0.05.
- Valid complete evidence and residual activity on≥4 bases (at least1% of pre-step samples with nonzero residual on an inspected diagnostic trace); all logged residual components≤0.15*nominal torque limit. Demand clipping and slip summaries must be reported; they do not alone identify causal mechanisms.

PASS-PILOT permits a proposal for a larger confirmatory experiment, **not release, AI-learning claims, additional spending or automatic follow-on work**.

**FAIL:** residual−current2x primary point estimate≤0, or any healthy/harm guardrail fails, given otherwise valid complete study. This rejects this pilot advancement, not every asymmetric control law. **INSUFFICIENT EVIDENCE:** positive effect fails size/interval/persistent-rescue gates. **NO-GO:** failed identity, insufficient qualification, hashes/errors/incomplete records, unexercised mechanism, unaffordable forecast or budget/deadline stop. Report partial results descriptively; do not drop bases, count errors as failures, repeat spent units or choose a favorable subset.

## Resource envelope and future operations

| Component | Maximum10-second equivalents |
|---|---:|
| Native engineering gate | 240 |
| Qualification48×(8+16+8) | 1,536 |
| Policy search12×2×(3,000+3,000+6,000) | 288,000 |
| Three FULL panels12×6×3×96 | 20,736 |
| Healthy guard12×6×8×2 | 1,152 |
| Rich diagnostics12×6×2 | 144 |
| **Total** | **311,808** |

Per-case cap25,836 equivalents. Every attempted/error job reserves duration/10 before dispatch and journals the cumulative counter with fsync. Confirmation savings do not fund new searches or replacement lineages. **Cloud proposed maximum$8 additional and three paid batch hours; main VM stays STOPPED; Token Factory$0.** No approval has been given for this proposal.

Provider read-only quote:64-vCPU batch$2.112 compute/h plus$0.00486 disk/h, quoted total$2.1169/h. Historical conservative six-worker path throughput0.118528 s/equivalent (`H1_PROTOCOL.md`) is a forecast, not a new H3 measurement. Eight independent six-worker case processes (48 workers total), two waves for12 cases, plus serial gate/qualification: about1.76 physics hours;25% slowdown plus0.5 hour startup/retrieval/shutdown gives **~2.70 batch hours / ~$5.72**, before any taxes/provider differences. Three-hour quote~$6.35, with$8 cap for slack. CMA/diagnostic I/O may be slower than H1 verification; T2 and in-run forecasts must stop if they cannot fit. Quote/balance/timing must be refreshed before approval execution; old$21.04 balance is not a fresh H3 billing verification.

Future operator must use existing `infra/nebius` service-account lifecycle/deadline/watchdog tools, after a separately reviewed H3 campaign cap is configured from fresh ledger—not `h1_ops.py start` or an inherited campaign. Max eight concurrent cases, one canonical campaign directory, no duplicate unit launches; set OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1 before launching Python. Runner never starts/stops VMs or calls models. An authorization receipt is a workflow record of the owner's new message, not an independent access-control guarantee. It must bind exact plan SHA, human-message reference, phases, campaign directory, epoch/deadline (≤3h from authorization),$8 and$0 token cap. The old spending limit must not be raised without new approval.

After authorization, commands run in the existing pinned project environment and frozen checkout:

```text
python scripts/h3_run.py gate --execute --authorization <fresh-H3-receipt> --plan <frozen-plan> --out <campaign>
python scripts/h3_run.py qualify --execute --authorization <fresh-H3-receipt> --plan <frozen-plan> --out <campaign> --gate-receipt <campaign>/gate/result.json
python scripts/h3_run.py case --case <qualified-id> --execute --authorization <fresh-H3-receipt> --plan <frozen-plan> --out <campaign> --gate-receipt <campaign>/gate/result.json --qualification <campaign>/qualify/result.json
python scripts/h3_analyze.py --plan <frozen-plan> --campaign <campaign> --out <new-analysis-file>
```

Any existing unit directory refuses replay, including a partially spent failure. Retries require a new documented authorization/protocol amendment and cumulative accounting. A hard API shutdown timer independent of guest processes must be active; the runner refuses dispatch within120 seconds of its deadline. Stop immediately on success/error, unresponsive supervision, unexpected process, budget/ledger inconsistency, hash drift or unsafe remaining-runtime forecast. Retrieve bounded archives with SHA manifests if time permits; do not restart merely to repeat outcomes. Stop batch using provider API and verify **both VMs STOPPED**; guest shutdown is not billing proof. Record final ledger/compute counters and retain disks/evidence. No paid follow-on is implicit.

## Interpretation and deadline

Qualification and native compatibility remain unverified. The complete pilot could fit before October30 if fresh approval is prompt and gates pass, but a powered independent controller/selector study cannot responsibly be promised. Keep V1 release/submission frozen; any pilot result must be explicitly labeled exploratory engineering evidence.
