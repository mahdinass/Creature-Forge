# Plan: `feature/experience-learning`: does Creature Forge learn from past experiments? (proposal, not started)

- **Status:** a proposal for owner review, with nothing implemented.
- **Branch:** `feature/experience-learning`, from `v1.0.0-rc1`.
- **Freeze:** V1 is frozen and this work never modifies `release/v1`.
- **Spend:** none until each phase is approved.

## 0. Why this design, and not a chat history or vector database
Four earlier memory attempts were null or weak:
- **Forge Loop text lessons:** p = 0.773, and the model never cited a lesson.
- **Held-out scientist + memory:** 16 vs 14 of 40.
- **Stage-2 dossiers:** used in 1 of 36 episodes.
- **DS-1 shared case store:** 10 vs 8, p = 0.31; updating vs frozen, 7 vs 7.

The consistent pattern is that **the LLM does not use prose memory**, and the leverage is in **repair-tool choice and
stopping**, not diagnosis (`docs/DS1_REPORT.md`, `docs/DUAL_SIGNAL_PLAN.md`).

So V2 memory is a **deterministic instrument**. It stores **measured causal evidence**, and its consumers are the belief
engine and the repair planner. Nemotron may read it, but the primary test does not depend on the model choosing to use it.

The scientific question:
> Do structured records of past investigations (hypotheses, experiments and their measured outcomes, repairs and their
> verifier outcomes, including failures) improve recovery on **new robots**, and can the system **predict when a lesson
> applies**, abstaining when it does not?

## 1. What one "experience record" is (no free text)
One record per completed, verified episode. All of it is already present in the HaS/DS-1 episode records.
- **Pre-intervention signature** (the retrieval key):
  - the observation features from the first floor/observe test;
  - the nominal-body morphology features.

  Instance ids, base ids, seeds, verifier outcomes and any post-hoc labels are never part of the key.
- **Causal trace:** the posterior over mechanisms after each experiment; each experiment, with its predicted and measured
  outcome (the model-check residuals); and the hypotheses refuted.
- **Repair outcomes:** for each repair, the tool, the parent design, the plant rollouts used, the train/robust evidence and
  the verifier label. That label is stored **only for experience-split episodes**, and only after their verification is
  complete.
- **Provenance:** the source record path and SHA-256, the arm, and the commit.

**Reuse:**
- `creature_forge/has_cases.py`, the shared case store (DS-1), is the base. It is extended, not duplicated.
- `experience_bank.py` (kNN) and `has_memory.py` (dossiers) serve as baselines.
- `amortized_posterior.py` serves as the learned-prior comparator.

## 2. Consumers (what memory is allowed to change), each ablated separately
| Channel | Effect | Budget accounting |
|---|---|---|
| **M-prior** | Retrieved cases give an informative prior over mechanism structures for the belief engine, weighted by an applicability score | No rollouts |
| **M-repair** | Retrieved cases reorder the repair tools and warm-start the CMA from a verified past repair delta | Every rollout counts inside the same 700 plant / 2,800 twin budget |
| **M-abstain** | If the applicability score is below a threshold calibrated on development data only, memory is not used at all | No rollouts |

**Applicability model.**
- Predicts P(the lesson transfers) from signature distance and mechanism agreement.
- Calibrated only on the experience split, by leave-base-out.
- Reported with a Brier score and ECE against a constant forecast and against plain kNN.

## 3. Experiment arms (paired on identical instances, seeds and budgets)
| Arm | Description |
|---|---|
| **M0** | Engine v6 + repair; no memory. This is the baseline, identical to the frozen DS-1 A1e6 configuration |
| **M1** | M0 + experience memory (M-prior + M-repair + M-abstain), with the store frozen before the evaluation |
| **M1-shuffled (placebo)** | M1 with each signature→record link permuted within the store (same amount of "prior information", wrong case). Controls for "any prior helps" |
| **M1-oracle (diagnostic only)** | Memory restricted to the case with the true mechanism. An upper bound, labelled, never a comparator |
| Secondary | **M1-update** (the store grows during evaluation, in a fixed order) vs M1-frozen; and **Nemotron + M1** vs M1 (does the scientist add anything once memory is an instrument?) |

## 4. Leakage controls (fail-closed checks in code, each with a test)
1. **Disjoint bases.**
   - The store is built only from experience-split bases. Evaluation bases are disjoint, and an assertion checks every
     retrieval.
   - Confirmatory evaluation uses a **fresh slice of the sealed test split**, which only the owner can release. The 18
     transfer bases are already spent (Stage 2, DS-1, W4).
2. **Signature purity.** Signatures contain only pre-intervention observables. A test checks the feature list against a
   whitelist, and none of these can enter: base or instance id, seeds, severity, injected structure, verifier fields.
3. **Seeds.** Validation and confirmation seeds are never stored, and the verifier is unchanged (`full_recovery_v1`).
4. **Frozen store.** The store snapshot is hashed and committed **before** any evaluation episode. The runner refuses a
   store with a different hash.
5. **Placebo arm.** M1-shuffled must not beat M0. If it does, the effect is an artefact of the prior, not of
   case-specific knowledge.
6. **No outcome-based tuning.** Thresholds and weights are fixed on experience bases. A held-out "transfer-dev" fold is
   used once for the gates, then frozen.

## 5. Objective evaluation
- **Primary:** FULL_RECOVERY under `full_recovery_v1`, M1 vs M0, paired by instance; exact one-sided McNemar on the
  discordant pairs.
  - The pre-registered N comes from a power check on the development effect.
  - The effects seen so far are small, so N is planned for a meaningful minimum (e.g. ≥ 8 discordant pairs expected), or
    the study is labelled exploratory.
- **Secondary:**
  - plant rollouts to the first verified repair (efficiency);
  - posterior mass on the injected mechanism after the first experiment;
  - applicability calibration (Brier/ECE);
  - the **negative-transfer rate**: instances where M0 is FULL and M1 is not. It is reported with its examples.
- **Placebo and oracle** results are reported alongside. The null wording is pre-set.
- **Reporting:** intention to treat, every assigned episode counted, NOT_EXPOSED (memory abstained) kept and reported.

## 6. Phases, gates, cost (each phase needs its own approval; none auto-advances)
| Phase | What | Physics / model | Gate to continue | Cost / time |
|---|---|---|---|---|
| **P0 Offline replay** | Build the store from **existing** recorded episodes (DS-1, Stage 2, CE dev). Then, by leave-base-out replay, measure whether memory predicts the verified repair tool and the mechanism better than a frequency prior, plain kNN and the amortized posterior; also measure calibration | None, $0 | Applicability beats kNN and the frequency prior on dev, with calibration better than constant | ~1 day local |
| **P1 Harness** | Arms M0/M1/M1-shuffled behind a fail-closed runner; leakage tests; frozen-store hash; dry runs | None | All no-physics tests pass; M0 reproduces the stored A1e6 records exactly (sentinel) | ~1 day |
| **P2 Dev pilot** | ~12 experience-split instances × 3 arms = 36 episodes, paired | ~130k rollout-eq; no paid model calls | Exposure > 0; no leakage alarms; the placebo does not beat M0 | Main VM ≈ 4 h ≈ $1.2 |
| **P3 Registered study** | Fresh sealed slice (owner releases N bases), M0 vs M1 (+ placebo); protocol and analysis committed and pushed before running | ~N × 3 × 3.6k rollout-eq | — | E.g. N = 40 → ~430k rollout-eq; batch VM ≈ 3–4 h ≈ $8–10 |
| P4 (optional) | Nemotron + M1 vs M1 | Paid inference | Only if P3 shows a memory effect | To be estimated |

**Parallelism.** P0 and P1 run in parallel locally. P2 needs P1. P3 needs owner approval of P2 and of the sealed slice.

## 7. Files (planned)
- **Extend:**
  - `creature_forge/has_cases.py`: signature, record schema, frozen-store hash;
  - a new `creature_forge/experience_applicability.py`: the calibrated applicability model;
  - a new `scripts/exp_memory_replay.py` (P0) and `scripts/exp_memory_ablation.py` (P1–P3; a runner in the
    `do1_repair_ablation.py` pattern).
- **Tests:** `tests/test_exp_memory_leakage.py`, `tests/test_exp_memory_ablation.py`.
- **Docs:** `docs/EXPERIENCE_LEARNING_PROTOCOL.md` (pre-registration) and a report after the run.
- **No change** to `creature_forge` frozen modules used by V1 evidence. New behaviour lives in new modules, or behind
  arm-specific subclasses, as `Do1Workbench` did.

## 8. Exact scope of the first implementation step (only after approval)
**P0 only.** It is offline and uses no physics and no model calls:
1. Build the experience store from existing recorded episodes on the experience split, with a hash-pinned manifest.
2. Implement the signature with its whitelist and leakage tests.
3. Run the leave-base-out replay metrics:
   - tool and mechanism prediction accuracy vs the frequency prior, kNN and the amortized posterior;
   - Brier/ECE.
4. Write a short P0 report.

**Then stop for review.**
