# Walking recovery — research iteration 3 proposal (2026-10-17, for owner approval)

## 1. What the development evidence says (re-examined)
| Layer | Evidence | Effect size |
|---|---|---|
| **Representation** (what the controller can express) | Adding one balance mechanism, swing-foot placement, raised recoveries from 1/12 to 5/12 (ctrl15 → ctrl17, M1). The stilts gait features pointed straight at it: forward runaway, landing foot behind the capture point. | **largest observed** |
| **Search stochasticity and selection** | The same method on the same creature agrees with itself across budgets only 6/12 (RAND) or 8/12 (FIX) times. M1 replicates often disagree. The train-to-validation gap is +0.21. | dominates differences between methods |
| **Decisions inside a fixed action space** (which subspace, body or not, shares) | v1 → v2 doubled AI recoveries by fixing measurable mistakes. AI v2, FIX and RAND then lie within the noise band (4, 4 and 7 of 12 at 2k). | small relative to noise |
| **Verification artifact (shared by all methods)** | gen-0006 walks 24/24 in several arms yet never "recovers": the frozen walk score is distance before a fall, and the original runs 4.2 m forward before falling, so a stable slower walker misses the +0.5 m `verdict_v1` bar. No method is told this, and none selects for it. | systematic, method-independent |
| **Learning (L2)** | Reusing past solutions raises walking (0.39 → 0.6–0.73) but not full recoveries. The neural surrogate adds nothing over a medoid. | none beyond simple reuse |

**Diagnosis of the AI bottleneck.** Nemotron's choices act on a lever that barely matters. Inside the current action space,
decisions are drowned by optimiser noise. Its evidence-reading skill is real but modest: a census top-2 probe in 13/24
pipelines against 8.7 expected by chance. The lever that does matter is changing the *structure* of the controller, and
the AI has no access to it. The one structural change we made (foot placement) was designed by the orchestrating
assistant after reading the gait diagnostics, not by Nemotron.

## 2. Candidate directions compared
| Direction | Expected effect | Learnable from data we can get? | Verdict |
|---|---|---|---|
| A. **Mechanism invention**: Nemotron reads the physical failure signature and writes new control laws in a safe DSL; CMA-ES tunes their gains; MuJoCo verifies | potentially large (the foot-placement precedent); clearly beyond what an optimiser can do, since it changes structure | n/a (reasoning) | **recommended (core)** |
| B. **Verified mechanism library** (experience): mechanisms that achieved verified recoveries are stored with the failure signature they fixed; on a new robot the agent decides whether a stored mechanism applies, reuses it, or invents a new one | grows with experience; testable on held-out families | yes: built from the dev runs themselves | **recommended (experience)** |
| C. Learned budget allocation (learning-curve extrapolation, racing) | modest; exploits noise; mostly classical | yes (optimiser traces) | defer, or give the same mechanism to every arm |
| D. Fine-tune a small LLM on oracle decisions | unclear. Nemotron itself is **not fine-tunable** on Token Factory (supported: Qwen3, Llama 3.x, Gemma 4, GPT-OSS, DeepSeek). Serving costs for fine-tuned models are unpublished. Supervision would be a few hundred labels, which a small classifier learns as well | weakly | **not now**; staged option: distil verified invention trajectories once the library is large |
| E. Transformer/attention policy over experiments | needs thousands of (creature × strategy) outcomes | only with a large new census | not before the deadline |

## 3. Proposed mechanism (A + B)
- **Controller hook**: a `MechanismController` adds up to 2 mechanisms to the existing 15-D phase-gait controller.
  - Each mechanism is `target_offset = Σ_i p_i · feature_i`, with up to 4 terms.
  - Targets: hip, knee or ankle reference of the swing leg, the stance leg or both, or an additive torque, gated by phase.
  - Features: expressions in a whitelisted DSL over proprioceptive signals: pitch and its rate, leg phase, swing and
    load flags, joint angles and rates, and the stance hip-to-ankle offset d and its rate v (both normalised by leg
    length), torso height. Allowed operations: + − × ÷, tanh, clip, abs, min, max, sin, cos.
  - Gains p_i are signed and bounded, and start at 0, so the start controller is bit-identical. Sign errors are therefore
    harmless: the optimiser picks the sign.
  - Code safety: AST whitelist; no names outside the signal list; no attribute access, calls outside the list, imports
    or loops.
- **Director v3 (Nemotron)**: on top of choosing probes and plans, it may *propose mechanisms* with a cited hypothesis.
  Each proposed mechanism becomes a probe (a short CMA search over its gains) and can enter plans jointly with
  control subspaces and body parameters. Everything is charged to the same total budget.
- **Expressiveness check**: the human-designed foot-placement law is one DSL program (`swing hip += p1·d + p2·v`). It
  serves as an *expert reference* arm, run through the same machinery.
- **Library (experience)**: every mechanism that took part in a FULL_RECOVERY is stored with its DSL, the creature's
  failure signature (gait features) and the measured gain. The director sees the library as a menu, with signatures, and
  decides; reusing an entry costs a probe like any other.

## 4. Experiments (fresh development panel; the S3 creatures stay untouched)
**S4a: does AI mechanism invention beat compute-matched non-AI structure?**
- Panel: 24 new dev creatures (campaign `walkrec-dev2`), starting from the 15-D family (no foot placement), equal
  total budget 2,000 each.

| arm | structure | decisions |
|---|---|---|
| FIX15 | none | fixed rule |
| GENERIC | blind linear feedback from every signal to every target (a large structural expansion) | fixed rule |
| RANDMECH | random DSL mechanisms with the same term count as the AI's | fixed rule |
| **AI-MECH** | Nemotron-invented mechanisms | Nemotron |
| EXPERT (reference) | the human foot-placement law (= FIX17) | fixed rule |

Report the structures Nemotron invented, including whether it rediscovers foot placement without being told.

Go/no-go G4: AI-MECH > max(FIX15, GENERIC, RANDMECH) by at least 3 creatures out of 24 (dev, descriptive) → it becomes
the S3 AI arm, with that best non-AI arm as the S3 primary comparator. Otherwise S3 runs as drafted (ai_v2 vs FIX) and
mechanism invention is reported as a negative result.

**S4b: does verified experience improve decisions on unfamiliar robots?** (only if G4 passes)
- Library: built from S4a's verified mechanisms on the training-region creatures.
- Test: 12 held-out-family creatures (`L2-f0-*` style, new draws), at equal budget.
- Arms: AI-MECH without the library vs **AI-MECH with the library** vs **non-AI reuse** (FIX15 + probe every library entry).
- This separates "experience helps" from "AI knows when experience applies".

**Shared pipeline fix (every arm, S4 and S3):**
- The final-candidate screening also checks the verdict's distance requirement (screen median score ≥ original median
  + 0.5 m), as well as walking.
- The goal statement given to the AI states the full acceptance rule.
- This removes the method-independent artifact. `verdict_v1` itself is unchanged.

## 5. Schedule (internal target 10-21 for this stage)
- **10-17:** DSL plus controller hook and baselines (Sonnet A); director v3 (Sonnet B); panel, driver and pipeline fix
  (Opus); smoke tests.
- **10-18:** S4a run (about 1.5 h batch) → analysis → G4.
- **10-19:** S4b if G4 passes → analysis.
- **10-20/21:** revise and freeze S3 (fresh 48 creatures), run S3.
- **10-22 onward:** demo take and submission.

## 6. Spending authorization requested
- **Infra cap:** $20 → **$35** cumulative (spent $15.19).
  - S4a about $4: 0.25M rollouts; mechanism evaluation may cost up to 1.5× per rollout.
  - S4b about $1.5.
  - S3 about $5.
  - Main VM regression and demo about $2.
  - The rest is margin.
- **Inference:** keep the $15 ledger cap (spent $2.71, of which Ultra was $1.69). S4 needs about 300 Super calls, about $0.6.
- **No fine-tuning job.**
- Safeguards unchanged: deadman timer, watchdog, stop after each block, per-stage rollout caps.

## 7. Risks
- Nemotron may write useless or wrong mechanisms. That is a valid negative result, and the signed gains limit the harm.
- Python-level evaluation of the DSL slows rollouts.
- Time: if S4a slips past 10-19, S3 runs as drafted.
- Leakage: Nemotron knows the robotics literature (for example Raibert foot placement). That is legitimate engineering
  knowledge, and the prompt never names a mechanism.

## 8. Owner clarification (2026-10-17) and resulting design
The owner asked for genuine **closed-loop investigation**: when a proposed law fails in MuJoCo, Nemotron must receive the
physical evidence, reconsider and decide what to do next, within the same investigation and budget, without being forced
to continue. The design now separates three capabilities and evaluates each on its own:

| # | Capability | Mechanism | How it is measured (development) |
|---|---|---|---|
| 1 | **Within-investigation adaptation** | director v3 `iterative`: up to 4 rounds. After every mechanism probe it gets delta walking/fitness on the train seeds, the fitted gains (≈ 0 or at a bound = evidence against), and post-probe gait features on the diag seeds next to the baseline. It may revise a law (`revises`, with a reason tied to the measurement), switch cause, request standard probes, or stop. | (a) AI-ITER vs AI-1SHOT (same director, one round, no feedback) at equal total budget; (b) process metric: how often a revision improves on the version it replaces, against the base rate of new proposals |
| 2 | **Cross-investigation experience reuse** | verified mechanism library (S4b) | AI with vs without the library on a held-out family; AI choosing library entries vs non-AI "probe every entry" |
| 3 | **Trainable learning across experiences** | staged: a mechanism critic trained on S4a's (failure signature, mechanism structure, measured probe outcome) tuples from AI, random and generic proposals, successes and failures, used to rank which proposed or library mechanisms to probe first | only if S4a yields enough tuples (about 300 expected); held-out-family evaluation against an unranked order and an LLM-only order; reported as exploratory |

**Data separation.** Feedback uses only the train seeds (optimisation) and diag seeds (post-probe diagnostics). Screening
seeds are used once, for the final selection. Validation and confirmation seeds are never seen by any method. All
feedback rollouts are charged to the method's total budget, the same for every arm.

**Arms (S4a, 24 fresh dev creatures, 15-D start, equal total budget 3,000):**
- FIX15
- GENERIC
- RANDMECH
- AI-1SHOT
- **AI-ITER**
- EXPERT (FIX17 reference)

Go/no-go G4: AI-ITER exceeds the best non-AI structure arm (FIX15, GENERIC, RANDMECH) by at least 3/24 full recoveries.
Capability 1 is reported from AI-ITER vs AI-1SHOT and from the revision metric, whatever G4's outcome.
