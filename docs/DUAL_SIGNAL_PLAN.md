# Dual-signal learning with bidirectional causal feedback: analysis and plan (Stage 2b proposal)

Date: 2026-10-20. Status: **proposal; owner approval needed before any run.** No experiment has been started.

Basis:
- `experiments/causal_engineer/dev/hdb/STAGE2_FAILURE_ANALYSIS.md`, produced by `scripts/stage2_failure_analysis.py`
  (read-only, development records only). §-numbers below refer to its sections.
- The analysis is exploratory and post hoc.

## 1. Where useful information is lost (Stage 2 records, 212 transfer episodes + experience corpus)

### 1.1 Diagnosis

**Single mechanisms: diagnosis is not the bottleneck.**
- Observation alone already puts 0.71 posterior mass on the truth. 20 of 36 instances are below 0.1 nats of entropy before
  any experiment.
- The final leading explanation is right in 80 %.
- Recovery barely depends on it: FULL is 41 % with the correct leading explanation and 30 % with a wrong one (§2).
- This matches MKV, where exact deviation knowledge (K2) recovers only 8/21.

**Compositions: diagnosis fails structurally.**
- The engine has no two-cause structure unless one is proposed.
- Its synthetic likelihood is overconfident: the posterior is ≥ 0.99 on a wrong structure in 39/48 episodes (§2).

**Tempering alone does not fix this (§10, experience bases only, offline from stored log-likelihoods).**
- On single mechanisms, a temperature of 4–8 helps:
  - confident-but-wrong posteriors drop from 58 to 4–11 of 211;
  - mean log P(truth) improves from −2.50 to −2.04.
- On compositions it does nothing. The mass on structures that share an injected primitive stays at about 0.44. The
  hypothesis space itself must grow.

### 1.2 Experiment selection

**Single mechanisms: little information left to gain.**
- After observation the posterior is mostly settled.
- Paired A1e vs A3 on the same instances:
  - end entropy is 0.05 for both;
  - the truth mass was higher for A3 on 5 instances and lower on 4;
  - Nemotron ran 1.9 experiments vs the engine's 0.7, which costs only about 5 extra plant rollouts (§7A).
- Nemotron's experiments are not wasteful. They cannot matter much here.

**Compositions: the information is destroyed upstream.**
- Because the posterior has already collapsed onto a wrong structure, all 98 of Nemotron's experiments on compositions
  moved the truth's mass zero times (§3).
- The overconfident likelihood leaves experiment choice no room to work.
- **Loss point: the likelihood, not the chooser.**

**Twin budget cost.** Fitting Nemotron's proposals costs twin budget:
- A3 used 2,420 vs 2,022 twin rollouts;
- the twin budget ran out in 3/36 single and 4/16 composition episodes, leaving less for repair (§4).

### 1.3 Repair delegation: where the arms actually differ

- **The tool choice decides outcomes.**
  - When two arms submitted the same tool, they disagreed on FULL in only 1–2 instances.
  - For A1e vs A3, 5 of the 7 discordant instances had different submitted tools (§7C).
- **The engine's tool screen saturates.** 3 or more tools tie at the top in 24 % of screens, and the CMA re-ranking ties
  in 28 %. In about a quarter of episodes the order of tools tried is arbitrary (§5).
- **Failures are mostly budget exhaustion with visibly weak designs.**
  - 89 of 128 non-FULL episodes failed validation walking. Their submitted design had robust16 of median 12/16, and only
    15/76 reached 15 or more.
  - The agent submitted a design that its own evidence showed was weak, because the search ran out (§7B).
- **A verification criterion is invisible to the agent.**
  - 32 of 128 failures walked well (robust16 median 16) but failed `verdict_v1` on forward displacement against the faulty
    robot.
  - 14 of these were *accepted* by the calibrated stop, which never sees displacement (§5, §7B).
- **The ceiling at this budget is low.**
  - Only 21/36 single and 9/16 composition instances were recovered by any of the arms (§8).
  - Of 100 single non-FULL episodes, 67 were on instances no arm recovered.
  - Better tool choice could have converted at most about 19 (the tool worked in another arm but was never tried or not
    submitted).
- **Nemotron rarely takes the repair decision.**
  - It customised the final repair in 6/33 A3 episodes (FULL 3/6 vs 11/27 when delegated).
  - The engine ran the final repair in 33 of 36 A3 episodes.

### 1.4 Cross-feedback: absent

- Plant outcomes of repair attempts are never fed back into the belief. `assimilate` was called 0 times in every arm,
  and the engine never assimilates by itself (§5).
- Within an episode, a failed repair does not change which mechanism the agent believes, or how it ranks the other tools.
- Across episodes, nothing records the conditions under which a tool fails.

### 1.5 Memory retrieval: retrieved, but carried nothing better than the engine

- The dossier for the true mechanism was ranked first on the first turn in 15/27 eligible A4 episodes.
- Nemotron cited a dossier in 4/36 episodes and applied one once.
- **Ignoring it was rational:**
  - the dossier's tools matched the submitted tool in 8/23 instances, which verified 3/8, vs 6/15 when the engine picked
    another tool (§6);
  - offline, on 290 experience instances with at least 2 verified tools, a pure mechanism → tool lookup chosen
    leave-one-base-out picks a recovering tool in 120, against 141 for the engine's own choice and 107 for random (§9).
- **The two signals are mixed in one status.**
  - The right-side-weakness dossier was *retired* for diagnostic precision 0.09, although its recommended repairs verified
    19/24 vs 23/34 for other repairs.
  - The pitch-bias dossier stayed *contested*, although its repair advice was harmful: 3/22 vs 10/32.
  - Diagnostic quality and repair quality need separate scores.
- **The experience corpus has real repair signal.**
  - 880 verified (instance, tool) outcomes on 340 experience-base instances; tools disagree on 109 of them.
  - Strong mechanism-conditional differences: pitch-sensor bias, feedback 12/19 vs torso mass 3/23; short feet, leg length
    6/7 vs posture 2/11; clock fault, feedback 4/4 vs torso mass 0/4.
  - Used as a *correction* to the engine's own ranking (not a replacement), it raises the pick rate from 114 to 124 of
    253, with headroom to 145 (§9).
  - The weight was chosen in-sample, so this is optimistic.

### 1.6 Noise floor

- A1e and A2 differ only by a prior on diagnosis, yet they disagree on 8/36 instances (§7C).
- At n = 36, development comparisons cannot resolve effects smaller than about ±4 instances. Stage 2's 4 vs 3 sits
  inside this floor.

### 1.7 Summary

Diagnostic improvements cannot reach verified recovery for three reasons:
1. On single mechanisms the posterior is already good.
2. On compositions the likelihood blocks every gain.
3. The decisions that do matter (which tool, when to stop, what verification needs) are taken without the experience that
   exists, and without feeding back the outcomes they produce.

Memory failed because it stored diagnosis-shaped knowledge, scored by diagnostic precision, for a problem whose leverage
is in repair.

## 2. The smallest dual-signal implementation (DS-1)

DS-1 links three parts through one shared causal experience store. Every component is deterministic except Nemotron.

### 2.1 Shared causal experience store (`has_cases.py`; built from experience-base records only)
- One **case** per repair attempt. About 1,500 attempts exist, of which 880 have a verified outcome. Each case holds:
  - **situation:** observation features relative to nominal, the posterior over structures with fitted magnitudes, its
    entropy, and the nominal design features;
  - **action:** tool, mode (twin/plant), start edits;
  - **visible evidence:** twin walking, robust16, stress4, the new displacement ratio (§2.4);
  - **verified outcome:** FULL / PARTIAL / NOT and the failure category;
  - in development only, the injected structure, for scoring.
- Investigations link their cases. This is the store Nemotron's principles cite.

### 2.2 Diagnostic signal (D): what mechanism, on which evidence
- **Score:** log P(true equivalence class) and calibration (ECE) of the leading explanation's mass. These are separate
  from any repair score.
- **Learned part (approved fix 2):**
  - a likelihood temperature T fitted by base-clustered cross-validation on experience bases;
  - a *misfit reserve*: when the model check leaves residuals beyond the dev noise model, mass is held back from every
    modelled structure, and pairs of the top single structures are enumerated and fitted automatically.
  - This is engine-level, so it applies to every arm.
- **Principles:** Nemotron's dossiers keep their diagnostic signature, scored only by diagnostic precision and recall.

### 2.3 Repair signal (R): which intervention works, under which conditions, with what verified outcome
- **Score:** verified FULL, the Brier / log loss of the predicted P(FULL), and repair lift over the engine's default
  choice. These are separate from the diagnostic score.
- **Learned part, the R-head (simplest strong baseline):**
  - P(FULL | tool, situation) = logistic combination of:
    - the engine's own twin evidence for that tool (CMA rank, twin walking, fitness);
    - a hierarchical Beta-Binomial mechanism × tool prior from verified cases;
    - the magnitude band.
  - It is evaluated under the **posterior mixture**, Σ_s w_s P(FULL | tool, s), not under the leading explanation alone.
  - It reorders the engine's top tools. It breaks the saturated ties and corrects the screen where experience disagrees.
- **Principles:** dossier repair advice is scored only by repair lift. Status (active / contested / retired) is kept per
  signal, so a dossier can be diagnostically weak but repair-useful, or the reverse.

### 2.4 Bidirectional coupling
- **Repair → diagnosis (within an episode):**
  - every plant check of a twin-optimised design is assimilated automatically. Under each hypothesis the twin predicts the
    design's walking, and the plant result reweights the hypotheses (`assimilate_check` already exists);
  - a large twin-plant surprise raises the misfit reserve, which triggers pair hypotheses and new experiments.
- **Diagnosis → repair:** the R-head uses the full posterior. Under structural uncertainty it prefers tools that are
  expected to work across the plausible mechanisms.
- **Verification → repair objective:**
  - the forward displacement of the candidate and the faulty design on the policy-visible robust seeds (charged plant
    rollouts) enters the evidence;
  - the stop map is refitted on experience designs with this feature. This targets the 32 displacement failures.
- **Outcome → memory (across episodes):**
  - each finished development episode appends its cases;
  - the R-head counts and the dual scores of the dossiers update, and the deterministic support rules re-rate each
    principle per signal;
  - memory is frozen for every evaluation.

### 2.5 Nemotron's role (so the system is not an imitation of the solver)
- The notebook gets a **case-evidence** section for the mechanisms currently believed. It shows the verified outcomes of
  each tool in past cases and the R-head's expected success per tool, next to the engine's twin ranking, and highlights
  disagreements (e.g. "engine: posture first; 19 past pitch-bias cases: feedback 12/19, posture 12/31").
- Nemotron decides the tool order, start edits and when to deviate from the engine. For every repair decision it registers
  P(FULL), scored after verification.
- It sees a running **self-score** from earlier development episodes, e.g. "your 7 deviations from the engine verified
  3/7; the engine default verified 5/9". It can therefore learn *when its own judgement beats the instruments*, which is
  experience about the scientist rather than about the robot.
- Consolidation writes principles that must cite cases. Their two scores are attached deterministically. Nemotron revises
  them; it never sets the scores itself.

### 2.6 Approved fixes (part of DS-1)
1. **Invalid replies:** one repair call carrying the validation error, counted in the inference budget (the
   physics-integrity rule allows exactly one). Target ≥ 95 % valid.
2. **Structural uncertainty:** temperature T and the misfit reserve with automatic pair enumeration (§2.2), plus automatic
   assimilation of plant checks (§2.4).
   - These change the engine for every arm, as engine v6.
   - The v5 path stays reproducible behind a flag and is tested to be bit-identical.
   - Frozen HDB v2, `verdict_v1`, `full_recovery_v1` and all pinned modules are untouched.

The displacement-aware stop (§2.4) is a third engine change. It was not in the two approved fixes, so **it needs your
approval**. It is cheap and deterministic, and it applies to every arm.

## 3. Fair development test (no sealed data)

### 3.1 Data separation
- **Learning data:** cases, R-head, temperature and stop-map refit come only from the 30 experience bases.
- **Evaluation set dev-eval-2:**
  - new instances on the 18 transfer bases, sampled with a new fixed seed before any run;
  - all 52 Stage-2 transfer instances are excluded;
  - limitation: the failure analysis above read Stage-2 records on these bases in aggregate, so dev-eval-2 is development
    evidence, not an untouched set.
- **Sealed test split and held-out families:** never touched.

### 3.2 Arms (identical instruments, budgets and seeds)

| Arm | Content | Purpose |
|---|---|---|
| A1e | engine v5, frozen | historical anchor |
| A1e6 | engine v6 = v5 + approved fixes | new deterministic baseline |
| A1x | A1e6 + R-head ranking + displacement-aware stop | dual-signal learning without an LLM |
| A3v5 | Nemotron agent v5 (retry) on engine v6, no memory | Nemotron vs engine, same engine |
| A4x | A3v5 + case evidence, R-head, dual-scored dossiers, self-score | Nemotron with dual-signal experience |

### 3.3 Contrasts (paired, development only)

| Contrast | Measures |
|---|---|
| A1e6 − A1e | the fixes |
| A1x − A1e6 | learning without an LLM |
| A3v5 − A1e6 | Nemotron on the same engine (the agreed primary comparison, in development form) |
| **A4x − A1x** | **Nemotron's added value given identical learned experience (the "not an imitation" test)** |
| A4x − A3v5 | the value of experience for Nemotron |

### 3.4 Size
- 60 instances per arm (48 single across 9 families + 12 development compositions).
- A learning-curve stream: A4x on 30 experience-base episodes with memory updated after each. Its decision quality is
  measured against the episode index; memory is then frozen.

### 3.5 Scored separately
- **Diagnosis:** log P(truth class), ECE, confident-wrong rate, compositions with at least one primitive identified.
- **Experiments:** information gain per plant rollout, paired against the engine.
- **Repair:** FULL; validation walking (Wilcoxon); failure category; the R-head and Nemotron P(FULL) Brier; lift over the
  engine default; how often Nemotron deviated and how those deviations verified.
- **Cross-feedback:** surprises assimilated, belief changes after a repair, and the outcome after a revision.
- **Memory:** retrieval relevance, use, per-signal status changes, and the corrupted-dossier probe (reused).
- **Learning:** the slope of decision quality over the stream; R-head offline base-clustered CV against the engine's
  ranking.

### 3.6 Pre-declared development gates (before any outcome is seen)
- **G-a:** if the R-head does not beat the engine's ranking in offline base-clustered CV on the experience corpus (log loss
  and pick rate), A1x and A4x are not built, and the iteration reports a null for repair learning.
- **G-b:** reply validity ≥ 95 %.
- **G-c:** A4x enters Stage 3 as a registered secondary arm only if:
  - Nemotron registered P(FULL) on at least 80 % of its repair decisions;
  - it deviated from the engine in at least 15 % of episodes;
  - A4x is not worse than A1x by more than 2 discordant pairs.
  - Otherwise A4x is descriptive only.
- **No superiority threshold is used.** n = 60 cannot confirm small effects (§1.6), and all results are reported.

## 4. Time, compute and cost (within the remaining Stage-2 envelope; no cap change)

| Work | Engineering | Compute | Infra | Inference |
|---|---|---|---|---|
| Fix 1 (retry) + tests | 0.5 day | – | – | – |
| Engine v6: temperature (offline CV, free), misfit reserve + pair enumeration, auto-assimilation, v5 bit-identity test | 1 day | composition check on experience bases, 32 episodes | $0.7 | – |
| Displacement evidence + stop-map refit (needs approval) | 0.5 day | about 11k rollouts | $0.2 | – |
| Case store, R-head, offline CV incl. kernel-attention variant (free) | 1 day | local | – | – |
| Notebook case evidence, P(FULL) registration, self-score, dual-scored dossiers | 0.5 day | – | – | $0.3 (one consolidation) |
| Experience-base pilots (A1x, A4x, about 10 each) + one iteration | 0.5 day | 40 episodes | $0.9 | $0.5 |
| dev-eval-2 (5 arms × 60) + learning stream (30) | 1.5 days wall | 330 episodes | $7 | $3.8 |
| Disks and idle | – | – | $1.2 | – |
| **Total** | **about 4.5 days (20–24 Oct)** | | **≈ $10 of $12.18 left** | **≈ $4.6 of $6.25 left** |

- **Machines:** LLM arms on the main VM only, as you asked. Non-LLM arms on the batch VM for about 3 hours (no key on
  batch), or on the main VM if you prefer, which adds about 20 h of wall time.
- **Ledger effect:** both ledger caps stay as they are.

**Deferred to protect 29 October:**
- BiCAM and any neural memory;
- A3h/A3hx;
- A2 as a Stage-3 arm;
- new walker campaigns;
- the Ultra model;
- a second LLM machine;
- online learning during the registered run (memory frozen);
- Studio work beyond exporting 2–3 dual-signal records into the existing "AI scientist" tab.

## 5. BiCAM: no-go before 29 October (with a defined go criterion)

**Reasons for no-go:**
- **Data:** about 1,500 cases (880 verified) on 30 bases and about 20 situation features. A cross-attention memory would
  fit noise and could not be told apart from simpler kernel regression at this size.
- **Weak signal so far:** the simplest coupled prior gains about +4 points offline, with an in-sample weight.
- **Time:** registration needs everything frozen by 25 October.
- **Compute:** training would be cheap. The bottleneck is generating thousands more verified repairs, about 2–3 M rollouts
  and several days.

**What happens instead:**
- The offline CV includes a zero-parameter **case-attention** variant: a similarity-softmax over case embeddings, which is
  the nonparametric limit of an attention memory.

**Go criterion (after the deadline):**
1. At least 3,000 verified (situation, tool) outcomes across at least 60 bases.
2. The R-head shows a cross-validated lift.
3. The kernel-attention variant beats the parametric R-head.
4. Only then is a trained BiCAM tested, and it must beat kernel attention on held-out bases.

## 6. Revised Stage 3 schedule and budget

### 6.1 Schedule
- **20–24 Oct:** DS-1 development iteration. Results by 24 Oct 18:00 UTC.
- **25 Oct 12:00:** registration (commit, `protocol.json`, test-build spec hash, frozen temperature, stop map, R-head and
  memory).
- **25 Oct:** test-bench build on the batch VM, non-LLM, about 8 h.
- **25 Oct evening – 27 Oct:**
  - registered run, N = 160;
  - non-LLM arms on batch (about 12 h): A0, A1e6, A1x, C-MKV K0n/K1/K2/K3;
  - LLM arms on the main VM (about 25 h): A3v5, plus A4x if G-c passes.
- **27–28 Oct:** single analysis.
- **28–29 Oct:** protected (regression, Studio, submission).
- **Fallback:** if DS-1 slips past 24 Oct 18:00, register A1e6 vs A3v5 plus C-MKV, with DS arms descriptive.

### 6.2 Hypotheses
- **Primary (unchanged in substance):** FULL(A3) > FULL(A1), as A3v5 vs A1e6 on the same engine version. One-sided exact
  McNemar, α = 0.05.
- **C-MKV:** as agreed.
- **Secondary (Holm):**
  - A4x > A1x (Nemotron given the same experience);
  - A1x > A1e6 (learning without an LLM);
  - A3v5 > A0.
- **Descriptive:** diagnostic and repair scores separately, cross-feedback metrics, memory probes.

### 6.3 Budget (unchanged envelopes)

| | Envelope | Estimate |
|---|---|---|
| Infra | **$65** | about $57: 1,440 episodes + bench build + overheads |
| Inference | **$15** | about $10 |

**Funding:**
- After this iteration the estimated real Cloud credit is about $6 (≈ $16 − $10; please confirm in the console).
- **Cloud top-up needed for Stage 3: about $65** ($65 + $5 reserve − ≈ $6).
- Token Factory: no top-up (≈ $43 left).

## 7. Decisions requested
1. Approve the DS-1 development iteration within the **remaining Stage-2 envelope** (≈ $10 infra, ≈ $4.6 inference;
   no cap change), including the dev-eval-2 run.
2. Approve the third engine change: **displacement-aware evidence and stop-map refit**, applied to every arm.
3. Approve running the **non-LLM** dev arms on the batch VM (about 3 h, no key), or require main-VM only (about 20 h
   longer).
4. Agree the BiCAM no-go before 29 October and the stated go criterion.
5. Stage 3 itself stays unapproved until the iteration's results (24 Oct). The expected Cloud top-up then is about $65.
