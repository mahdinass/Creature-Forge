# Phase 3 Stage 2 report: the autonomous HaS scientist (development evidence)

Date: 2026-10-20. Branch `feature/has-scientist`. Agent frozen at tag `stage2-agent-v4-frozen`.
Status: **Stage 2 complete; Stage 3 (registered evaluation) awaits the owner's approval.**

Everything below is development evidence on dev mechanisms and dev-side robots. It is not a registered result and supports no
claim. Raw numbers: `experiments/causal_engineer/dev/hdb/STAGE2_TRANSFER_agent_v4.md`. Build log: `docs/HAS_SCIENTIST.md`.

## 1. What was built

- **The scientist (`creature_forge/has_agent.py`).**
  - Nemotron reads a lab notebook and calls one tool per turn. The notebook holds the measurements, the engine's posterior,
    a model check that lists unexplained residuals, candidate experiments with their EIG and per-hypothesis predictions,
    the tool screen, designs with their evidence and mapped P(pass), retrieved memory, and the engine's recommendation.
  - Tools: experiment (from the candidate list or designed by Nemotron), propose, delegate_diagnosis, screen_tools,
    repair (twin or plant), check, assimilate, apply_dossier, use_learned, delegate_repair (optionally with Nemotron's tool
    order, start edits or design), conclude.
  - Capabilities 1–9 of the directive are implemented as tools.
  - Deterministic instruments: MuJoCo, the belief engine, EIG, CMA-ES, verification. They do the inference and the
    optimisation; Nemotron decides what to do with them.
- **Faithful baseline.** With no scientist, the agent loop (A1e) reproduces the frozen engine A1c5 exactly: identical
  verification, plant and twin ledgers, and design vectors on 4/4 checked instances.
- **Experience (`has_memory.py`).**
  - Nemotron writes executable dossiers: mechanism structure and parameter ranges, measurable signature, failure cases,
    repair tools and start edits, and a principle.
  - Support statistics and contested/retired status are computed deterministically.
  - Retrieval ranks dossiers by the engine's belief in their mechanism. Memory is frozen during evaluation.
- **Learned amortised posterior (`amortized_posterior.py`).** Softmax over 10 dev structures, ridge magnitudes and
  Mahalanobis OOD, trained on 3,628 simulated failures. Cross-validated top-1 / top-3: 0.37 / 0.67 from observation only,
  0.50 / 0.81 with floor and weigh tests.
- **Operations.**
  - Fail-fast `AuthFailure`.
  - No-browser Nebius CLI with an `AUTH_BLOCKED` stop.
  - Per-episode flushed records.
  - Studio "AI scientist" tab with 3 recorded investigations; the e2e flow passes.

## 2. Protocol

- Fixed on 2026-10-19, before any agent pilot:
  - tune only on 30 *experience* bases;
  - evaluate once on 18 unseen *transfer* bases with the agent frozen.
- Pilots: 3 iterations of the agent (v1 → v4) on experience bases. Every change was made from traces, never from transfer
  outcomes.
- Transfer evaluation:
  - 36 single-mechanism instances (9 dev families × 4) and 16 two-mechanism development compositions (the addendum was
    declared before any LLM transfer run);
  - two memory probes: leave-family-out memory, and a deliberately corrupted dossier.
- 124 LLM-arm episodes, all valid. A first launch was invalidated by a stale key on the batch VM (312 × HTTP 401). Those
  records were quarantined, never analysed, and the run was repeated after a passed authentication check.

## 3. Evidence

### 3.1 Outcomes (verified recovery under `full_recovery_v1`; paired, same instances and seeds)

| Population | A1e engine | A2 engine + learned | A3 Nemotron scientist | A4 A3 + memory + learned |
|---|---|---|---|---|
| Single mechanism, n = 36: FULL | 14 | 12 | **15** | 14 |
| PARTIAL / NOT | 13 / 9 | 14 / 10 | 8 / 13 | 13 / 9 |
| Compositions, n = 16: FULL | **8** | – | 6 | 6 |
| Mean plant / twin rollouts (single) | 586 / 2,022 | 597 / 2,180 | 545 / 2,420 | 581 / 2,493 |

**Paired contrasts (one-sided exact McNemar on FULL; Wilcoxon on validation walking fraction):**
- **A3 vs A1e, single:** discordant 4 vs 3, p = 0.50. Walking −0.07 (p(A3 > A1e) = 0.69).
- **A4 vs A1e, single:** 2 vs 2. Walking +0.015 (p = 0.28).
- **A3 vs A1e, compositions:** 0 vs 2. A4 vs A1e: 1 vs 3.
- **A2 vs A1e:** 3 vs 5.

Reading: on single mechanisms, the Nemotron scientist is at parity with the engine it directs. On the dev compositions,
where pilots suggested Nemotron's two-cause hypotheses could help, it did slightly worse (not significant). Nothing here
shows that Nemotron improves verified recovery.

### 3.2 What Nemotron actually did (process metrics)

**Turns.** A3 single: 159 Nemotron turns and 10 fallback turns (invalid reply → engine recommendation, recorded).

**Overall reply validity.** 664 of 718 role calls were valid (92.5 %). The planned G2 gate (≥ 95 %) is **not met**:
- single mechanism: 94 %;
- compositions: 89 %.

**Experiments.**
- Nemotron chose 67 (A3) and 73 (A4) experiments on single mechanisms.
- 15 and 19 of them it designed itself, outside the engine's candidate list.
- The median EIG of its choice divided by the best available EIG is 1.0: it usually picked the engine's top experiment.

**Hypotheses.**

| | Proposed | Entered the top 3 | Became the leading explanation | Matched the injected structure |
|---|---|---|---|---|
| Single A3 | 44 | 8 | 5 | 2 |
| Single A4 | 58 | 10 | 6 | 4 |
| Compositions A3 | 72 | 17 | 7 | 0 |
| Compositions A4 | 64 | 14 | 7 | 1 |

**Identification (MAP = injected structure).**
- Single: A1e 29/36, A2 31, A3 28, A4 29. Mean posterior on the truth: 0.80 / 0.85 / 0.78 / 0.81.
- **Compositions:**
  - 0/16 for every arm;
  - the leading explanation contained at least one injected primitive in 7 (A1e), 9 (A3) and 6 (A4) of 16;
  - the posterior was ≥ 0.95 on a **wrong** structure in 12 / 15 / 16 of 16. The engine is confidently wrong when the
    failure has two causes, and Nemotron's hypotheses did not fix that.

**Repair strategy.**
- Nemotron customised the final repair (tool order, start edits or design) in 6 of 33 A3 single episodes: FULL 3/6, vs
  11/27 when it delegated as recommended.
- No sign of benefit (too few to judge).
- Most episodes end with `delegate_repair`. The verified recoveries are therefore the engine's and optimiser's, and are
  not attributed to Nemotron.

**Registered predictions** (90 % interval coverage, A3 single):

| Quantity | Coverage | Reading |
|---|---|---|
| walking count | 25/30 | Reasonable |
| time upright | 14/30 | Overconfident |
| pitch | 17/28 | Overconfident |

**One instructive win.** On `gen-0137 one_side_weakness`:
- the engine alone settled on the wrong side;
- Nemotron chose a different discriminating experiment (gait-frequency counterfactual), the posterior moved to the
  injected right-side weakness, and the episode verified.

This is a single instance. Engine-only A1e won 3 instances that A3 lost.

### 3.3 Learning and transfer

**Memory is retrieved but not used.**
- In A4, 27 of the 36 instances have a dossier for their mechanism. That dossier was ranked first on the first turn in
  15/27, and on some turn in 17/27.
- Nemotron's reasoning cited a dossier in 4/36 episodes, applied one once, and never adopted a dossier's repair.
- A4 ≈ A3 is therefore expected and is not evidence about the value of experience.

**Leave-family-out (A4lfo, 8 instances of the 2 families excluded from memory).**
- FULL 4/8 vs A4 3/8 and A3 4/8; discordant 1/0 vs A4.
- No negative transfer, but memory was not used.

**Corrupted-dossier probe (A4bad, 12 instances).**
- The false "low friction explains every failure" dossier ranked first on some turn in 6/12 episodes.
- It was never applied as a hypothesis and its repair was never adopted (0/12).
- FULL 5/12 vs A4 6/12 (discordant 2/3).
- Nemotron did not follow wrong experience. With memory this rarely used, that is weak evidence of an applicability check.

**Learned posterior (A2).**
- It adds a little identification: 31 vs 29 correct, mass 0.85 vs 0.80.
- It does not add verified recovery: 12 vs 14.
- Identification is not the binding constraint on single mechanisms.

**Consolidation.**
- Memory v5 has 7 dossiers.
  - The payload, clock and feedback-gain dossiers have precision 0.78–0.93. Their recommended repairs did better than
    other repairs in dev records (17/22 vs 14/25; 7/10 vs 2/4; 3/4 vs 2/5).
  - Two were contested and one was retired by the deterministic rules.
- Consolidation is stochastic: one early dossier had the wrong direction, with 9 % precision.

### 3.4 Earlier Stage 1–2 context that bears on Stage 3

- **The engine beats exhaustive screening on fresh dev robots.**
  - A1c5 109 vs A0 62 of 211, paired 61 vs 14 (Stage 1).
  - This is still the strongest effect in the programme and is credited to the engine, not to Nemotron.
- **MKV dev.** Exact deviation knowledge (K2) vs nominal model (K0n): FULL 4 vs 1 (p = 0.19), walking +0.17 (Wilcoxon
  p = 0.003).

## 4. Costs (full)

| | Stage 2 envelope | Stage 2 actual | Ledger now / cap | Programme cumulative |
|---|---|---|---|---|
| Nebius AI Cloud (infra) | $20 | **$7.82** ($75.48 → $83.30) | $83.30 / $96 | $83.30 (ledger, conservative) |
| Token Factory (inference) | $10 | **$3.75 billed** (1,220 calls since 19 Oct) | $46.02 / $52.78 | ≈ $29.2 billed (+ $16.80 of unbilled 401 settlements in the ledger) |

- **Infra.**
  - Both VMs were confirmed STOPPED through the control plane at 01:38 UTC on 20 Oct.
  - The boot disks keep accruing about $0.23 a day.
- **Inference.**
  - The 124 LLM transfer episodes cost $2.64, $0.021 per episode: single $0.016–0.018, compositions $0.030–0.032.
  - The rest went to pilots, consolidation and the composition pilot.
- **Estimated real credit remaining** (please confirm in the console; the CLI cannot read balances):
  - Cloud ≈ $66 − ($83.30 − $33.29) ≈ **$16**;
  - Token Factory ≈ $52 − $3.77 ≈ **$48**.

## 5. Limitations

1. **No evidence that Nemotron improves verified recovery.** Single mechanisms: parity (4 vs 3 discordant). Compositions: 0
   vs 2. The final repair is almost always delegated to the engine.
2. **Reply validity is 92.5 %, below the G2 gate of 95 %.** Invalid turns fall back to the engine and are recorded, but they
   cut Nemotron's real control of the episode.
3. **Memory is effectively unused (1 application in 36),** so neither the value of experience nor real negative-transfer
   detection has been tested. The corrupted-dossier result (0/12 adopted) cannot tell resistance from neglect.
4. **The engine is confidently wrong on two-cause failures** (posterior ≥ 0.95 on a wrong structure in 12–16 of 16). The
   sealed test set contains held-out compositions, so this affects every arm there.
5. **Predictive intervals are overconfident** for time upright and pitch.
6. **Small dev samples** (36 + 16 + 8 + 12). The transfer bases are unseen, but the robots come from the same generator and
   the mechanisms are all dev families.
7. **Wall-time comparisons are invalid.** The LLM arms ran 40 sessions on 8 vCPUs.
8. **Operations.**
   - The stale key on the batch VM invalidated the first LLM transfer launch ($9.38 of worst-case settlements booked,
     none billed).
   - The Nebius CLI login expired overnight. The guard stopped all attempts, and the owner re-logged in.
   - The VM's own deadline timer powers the guest off but may not stop billing; only an API stop does.

## 6. Proposed Stage 3: registered evaluation

### 6.1 Population and arms
- **Population:** N = 160 fresh instances from the 99 sealed test-side bases, stratified by family as declared in
  `docs/HDB_SPEC.md`. It includes the held-out families (sensor latency, joint damping wear, leg-length asymmetry) and
  held-out compositions. The bench (eligibility, R/U oracle and ambiguity labels, response rows) is built after
  registration.
- **Arms** (identical instruments: plant budget 700, twin cap 2,800, same seeds):
  - A0 (generic exhaustive);
  - A1 (engine, calibrated stopping = A1c5/A1e);
  - A3 (Nemotron scientist);
  - A4 and A2 (descriptive);
  - C-MKV conditions K0n, K1, K2, K3 (K4 = A1).
  - That makes 9 conditions, 1,440 episodes, of which 320 are LLM episodes.
  - Planned arms A3h/A3hx are dropped. Process attribution uses the per-turn trace metrics in §3.2: EIG ratio,
    hypothesis entry and leadership, deterministic replay.

### 6.2 Hypotheses (unchanged from the approved plan and owner decisions)
- **Primary P:** FULL(A3) > FULL(A1), one-sided exact McNemar, α = 0.05.
  - **Expected power is low.** The dev discordant split is 4:3; at N = 160 there are about 31 discordant pairs, and the
    power is about 16 %.
  - About 70 % power would need a true split near 70:30.
  - A null is a legitimate, reportable result (plan F2). I recommend keeping the primary as approved: changing it now
    would be motivated by dev outcomes.
- **C-MKV (separate, α = 0.05):** primary K2 vs K0n; secondary K1 vs K3 and K2 vs K1; walking Wilcoxon for each.
- **Secondary (Holm):**
  - S2 A3 > A0 (dev evidence for the engine suggests this is likely; it would be credited to the engine-centred system,
    not to Nemotron);
  - S3 predictive skill;
  - S4 calibration of the frozen stopping map;
  - S5 A1 > A1f only if A1f is kept (proposed: drop it, since stopping variants differed by 1–4 discordant pairs on dev).
- **Descriptive:**
  - A4, A2;
  - per stratum (R/U/ambiguous, held-out families, compositions);
  - process metrics, negative-transfer probe, cost.
  - S6/S7 (experience, learned posterior) are not registered, because memory was unused on dev.

### 6.3 Pre-registration fixes (dev-motivated; small; documented as such; within the remaining Stage-2 envelope)
1. **Invalid replies:** add the single allowed repair call for schema-invalid replies, counted in the budget. Target
   ≥ 95 % valid.
2. **Composition overconfidence:** a likelihood-tempering / misspecification check in the engine. It is applied
   identically to A1, A3 and every arm, re-checked on experience-base compositions only, and frozen before registration.
3. A short smoke on experience bases (≤ 9 episodes per arm). Then freeze, register (code commit, `protocol.json`, test-build
   spec hash, frozen map and τ) and build the test bench.

The remaining Stage-2 envelope is about $12 infra and $6 inference; the estimated use is about $2 + $1. If you prefer no
further changes, Stage 3 runs agent v4 and engine v5 as frozen.

### 6.4 Schedule
- 20–21 Oct: fixes and smoke.
- 22 Oct: registration and test-bench build.
- 23–25 Oct: registered run.
  - Non-LLM arms on the batch VM: about 11 h.
  - LLM arms on the main VM: about 25 h, with no credential change on the batch VM.
  - Option: put the current key on the batch VM to finish the LLM arms in about 6 h at the same cost. This is your
    credential decision.
- 26 Oct: single analysis.
- 27–29 Oct: regression, Studio and buffer.

## 7. Funding needed for Stage 3

Measured rate: one episode ≈ 0.62 vCPU-hours ≈ $0.021 of compute (main VM, Stage 2). LLM episodes cost $0.016–0.032 of
inference.

| Item | Infra | Inference |
|---|---|---|
| Test-bench build on the sealed side (eligibility, R/U oracle incl. 4× union oracle, response rows) | ≈ $22 | – |
| Registered run, 1,440 episodes | ≈ $30 | 320 × ≈ $0.023 ≈ $7.5 |
| Repair calls, smoke, Studio demo | – | ≈ $1.5 |
| Disks, setup, regression, idle accrual | ≈ $5 | – |
| **Estimate** | **≈ $57** | **≈ $9** |
| **Requested envelope (contingency included)** | **$65** | **$15** |

**Cap edits after approval:**
- infra `SPEND_CAP_USD` $96 → $83.30 + $65 + $0.50 ≈ **$149**;
- inference USD cap $52.78 → $46.02 + $15 + $0.50 ≈ **$61.52**;
- requests 8,000 → **9,500** (6,265 used).

**Top-ups:**
- **Nebius AI Cloud: about $55** ($65 + $5 demo reserve − ≈ $16 estimated remaining). Please check the console balance; if
  it is higher than $16, the top-up shrinks by the difference.
- **Token Factory: none needed** (≈ $48 remaining vs $15).

## 8. Decisions requested

1. Approve Stage 3 (registered evaluation as in §6) with envelopes of **$65 infra and $15 inference**, and the Cloud top-up
   of about **$55** (after you confirm the balance).
2. Approve or decline the pre-registration fixes in §6.3: invalid-reply repair call and composition tempering, both applied
   to every arm.
3. Keep the primary A3 > A1 as approved, knowing its expected power is low (recommended), or name a change before
   registration.
4. LLM arms on the main VM only (recommended; no credential change), or the current key on the batch VM.
