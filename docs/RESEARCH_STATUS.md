# Research status (frozen 2026-10-27)

Research for the hackathon stopped on 2026-10-27. This page lists every completed study with its registered decision and
where its evidence lives. It separates the **release product** (this branch) from **research prototypes** (separate
branches and draft PRs, not merged into the release).

**Reading the labels.**
- *Confirmatory*: protocol and analysis fixed and pushed before the outcome data existed; one registered primary test.
- *Registered secondary / development / feasibility*: fixed gates, but exploratory in scope; not a general claim.
- *NO_AI*: no language model in any arm. *AI*: Nemotron on Nebius Token Factory made decisions in at least one arm.
- "Not evaluable" and "NO-GO" are gate decisions about whether a study could answer its question; they are not
  evidence that the idea is false.

## 1. What the release can say
| Claim | Status | Evidence |
|---|---|---|
| The Forge Loop pipeline runs end to end with live Nemotron and rejects, verifies or refutes proposals by physics | Demonstrated (implemented and recorded live) | `experiments/forge_loop/demo_capture/`, `docs/submission/evidence/live_acceptance_2026-10-24.json` |
| Nemotron's redesigns verify more often than matched random edits | Pre-registered, small: 6/12 vs 1/12, p = 0.031, mostly push challenges | `experiments/forge_loop/scoreboard/REPORT.md` |
| Nemotron's scientific decisions beat the deterministic engine | **Not supported:** parity (15 vs 14 of 36, p = 0.50) | `docs/STAGE2_REPORT.md`, `docs/NEMOTRON_CONTRIBUTION.md` |
| Nemotron as walking-recovery director beats a fixed rule | **Not supported:** 9/48 vs 19/48, p = 0.996 | `docs/WALK_RECOVERY.md` |
| A fixed non-AI procedure recovers walking in fresh failing robots | Confirmatory: 19/48 (40 %) | `docs/WALK_RECOVERY.md` |
| The DO-1 objective repairs the demo robot reliably | Pre-registered replication on that robot: 5/5 vs 0/5, p = 0.031 | `docs/DO1_REPLICATION_REPORT.md` |
| DO-1 is a general improvement | **Not supported** (R0, development, 18 bases) | §2, R0 |
| Physics diagnosis beats exhaustive repair search on unseen damage | Confirmatory primary **inconclusive** (56 vs 46 of 160, p = 0.061) | `docs/E1_RESULTS.md` |
| Diagnosis carries the engine's advantage | Supportive: registered secondary met (Holm over 2, 0.034), not study-wide (0.050 over 3) | `docs/E1_RESULTS.md` §1.1 |
| The system learns from experience and improves across failures | **Not demonstrated.** Every direct test was null, failed its gate or was not evaluable | §2 |

## 2. Completed studies
Dates are 2026. "Release" means the evidence is on this branch; otherwise the branch and commit are given, and the link
opens the report at that commit.

| Study | Date | Type | AI | Question | Registered decision | Evidence |
|---|---|---|---|---|---|---|
| Phase 1 live batch | 13 Oct | Pre-registered pilot | AI | Do Nemotron Nano's single-shot fixes beat random and heuristic proposers? | No outperformance claim possible (2 valid replies, both failed) | release: `experiments/phase1/REPORT.md` |
| R1 robustness | 14 Oct | Registered | NO_AI | Does robustness search improve a walking controller? | NULL (futility stop) | release: `experiments/phase2a_r1/REPORT.md` |
| R2 local robustness | 14 Oct | Registered | NO_AI | Same, local search | Confirmed: 150/150 vs 91/150 walking on held-out seeds | release: `experiments/phase2a_r2/REPORT.md` |
| R3 Nemotron investigation | 14 Oct | Registered | AI | Nemotron investigation vs baselines | Attempt 1 aborted; v2 calibration failed; no statistical result | release: `docs/R3_ATTEMPT1_AND_V2_OPTIONS.md` |
| Forge Loop scoreboard | 15 Oct | Pre-registered | AI | AI redesign vs matched random edit | 6/12 vs 1/12, p = 0.031 | release: `experiments/forge_loop/scoreboard/REPORT.md` |
| Forge memory evaluation | 16 Oct | Pre-registered | AI | Do text lessons from earlier investigations help? | Null: 6/12 vs 7/12, p = 0.773 | release: `docs/NEMOTRON_CONTRIBUTION.md` |
| Walking recovery S3 | 17 Oct | Confirmatory | both | AI director vs best non-AI rule, 48 fresh robots | FIX 19, AI 9; AI > FIX not supported (p = 0.996) | release: `docs/WALK_RECOVERY.md` |
| HaS Stage 2 transfer | 20 Oct | Development | AI | Nemotron scientist vs engine alone | Parity: 15 vs 14 of 36 singles; 6 vs 8 of 16 compositions | release: `docs/STAGE2_REPORT.md` |
| DS-1 dual-signal | 20 Oct | Development, gated | AI | Cross-feedback and experience arms | Gates G-a, G-m, G-c failed; no Stage 3 | release: `docs/DS1_REPORT.md` |
| DO-1 L4 r0 and W3/W4 replication | 21 Oct | Pre-registered replication | NO_AI | Does the DO-1 objective repair the demo robot reliably? | W3 5/5 vs 0/5 (p = 0.031); W4 pilot 1 of 2 | release: `docs/DO1_REPLICATION_REPORT.md` |
| Experience P0 / P0.5 (SV0, SV1) | 22–24 Oct | Audit and method validation | NO_AI | Is there identifiable data for experience learning? | P0 INSUFFICIENT-DATA; SV1 admitted one bootstrap method only | `feature/experience-learning` @ `cea00b5` |
| **E-1 held-out** | 24 Oct | **Confirmatory** | NO_AI | Engine vs exhaustive search vs engine without diagnosis, 160 sealed robots | Primary inconclusive (p = 0.061); diagnosis ablation supportive (registered secondary only) | release: `docs/E1_PROTOCOL.md`, `docs/E1_RESULTS.md`, `experiments/e1/` |
| RL-1 repair learning | 24 Oct | Development, gated | NO_AI | Does memory of verified repairs choose better repair tools? | Gate G-RL1 FAILED (0.512 vs 0.521) | `research/rl1-repair-learning` @ `0828cbd`, [`RL1_DEV_REPORT.md`](https://github.com/mahdinass/Creature-Forge/blob/0828cbd0ea556fb31630e275b444b0197671185e/docs/RL1_DEV_REPORT.md) |
| R0 coordinated repair | 25 Oct | Development, gated | NO_AI | Does joint multi-group optimisation recover robots that single and sequential search cannot? | Advancement gate FAILED (2 rescue bases of 3 required; 3 control regressions). DO-1 was not a general improvement | `codex/repair-strategy-r0` @ `2adff9e`, [`EXECUTION_REPORT.md`](https://github.com/mahdinass/Creature-Forge/blob/2adff9e6e0eb8dbe73f2acbe4aa828f4996efc4e/experiments/causal_engineer/dev/repair_strategy_r0/EXECUTION_REPORT.md) |
| EM-1 model correction | 25 Oct | Feasibility | NO_AI | Can learned physics-model corrections improve repair decisions? | NOT EVALUABLE; NO-GO (no decision-relevant target identified) | `codex/experience-model-correction-em1` @ `536c32d`, [`EM1_DECISION.md`](https://github.com/mahdinass/Creature-Forge/blob/536c32d2e361d3402b4a109925f006f8ebfc3340/docs/EM1_DECISION.md) |
| DI-1 decision investigation | 25 Oct | Engineering pilot | NO_AI | Is there exploitable opportunity in investigation decisions? | NOT EVALUABLE; NO-GO (1 rescue base of 5; powered study infeasible) | `codex/decision-investigation-di1` @ `2c4c409`, [`DI1_DECISION.md`](https://github.com/mahdinass/Creature-Forge/blob/2c4c40966a7c5fce574fafed922c34a9fe5f88f6/docs/DI1_DECISION.md) |
| VEL-1 verification experience | 26 Oct | Feasibility | NO_AI | Does relevant history predict verification failure? | INSUFFICIENT EVIDENCE (history adds nothing over calibration) | `codex/verification-experience-vel1-feasibility` @ `1d7e3e0`, [`VEL1_DECISION.md`](https://github.com/mahdinass/Creature-Forge/blob/1d7e3e0af4d47262b523cff7305c3f43d800e1ee/docs/VEL1_DECISION.md) |
| VEL-2 label repeatability | 26 Oct | Registered measurement study | NO_AI | Are single-panel FULL labels stable enough to learn from? | NO-GO: 9/15 labels stable (12 required) | `codex/verification-reliability-vel2` @ `4ce8a6f`, [`VEL2_DECISION.md`](https://github.com/mahdinass/Creature-Forge/blob/4ce8a6fb16dc3aa973517edbe4f767ac2159c622/docs/VEL2_DECISION.md) |
| H1 repair selection | 26 Oct | Registered, staged | NO_AI | Is there selection headroom, and does a fixed physical rule capture it? | Stage A passed (headroom 5.9 pp); Stage B gate FAILED (+0.6 pp); NOT EVALUABLE for experience learning | draft PR #22, `codex/h1-bounded-investigation` @ `8ed1ead`, [`H1_DECISION.md`](https://github.com/mahdinass/Creature-Forge/blob/8ed1ead41196d76da73390c96ed20fa6c8d5979a/docs/H1_DECISION.md) |
| H3 stance-residual capability | 26 Oct | Registered pilot | NO_AI | Does a new asymmetric stance controller rescue unilateral faults? | Native identity PASS; acquisition NO-GO (4/48 qualified, 12 required); efficacy untested | draft PR #23, `codex/h3-capability-audit` @ `64e3ed4`, [`H3_RESULTS.md`](https://github.com/mahdinass/Creature-Forge/blob/64e3ed406c13b7331ae4cb0e6ec1c44298918d01/docs/H3_RESULTS.md) |

Not run: **E-2R** (a proposed diagnosis-ablation replication on a fresh cohort). It remains a research-only proposal
(an uncommitted analysis draft exists in the owner's research checkout) and is not part of the release.

## 3. Hypotheses that remain unproven
- **Experience learning** in any form tested: text lessons, dossiers, learned posteriors, repair memory (RL-1), model
  correction (EM-1), investigation-decision learning (DI-1), verification-risk history (VEL-1), selection rules (H1).
- **Nemotron outperforming the deterministic engine** in the scientist setting, or a fixed rule in walking recovery.
- **Diagnosis-led repair beating exhaustive search** on unseen damage (E-1 primary inconclusive).
- **A new controller class** rescuing unilateral faults (H3 efficacy untested).
- **Generality of DO-1** beyond the demo robot (R0 negative).

The repeated obstacle, recorded by VEL-2 and H1, is that single-panel verification labels change between independent
seed panels on a sizeable share of cases. Learning from such labels needs repeated panels or margin-based targets first.

## 4. Release product vs research prototypes
- **Release (`release/v1-submission`, PR into `main`):** the Studio and its live Forge Loop, the recorded demo pages, the
  completed studies above whose evidence is on this branch, and E-1.
- **Not in the release, kept for transparency:** RL-1, R0, EM-1, DI-1, VEL-1, VEL-2, H1, H3 (research branches and draft
  PRs #22 and #23) and the unexecuted E-2R draft. Their negative and inconclusive results are summarised here so that the
  release does not hide them; their code is not part of the product.

## 5. Note on the earlier research write-up
An earlier research article (maintained outside this repository) covered E-1, RL-1, R0, EM-1, DI-1, VEL-1 and VEL-2. It
predates H1 and H3 and should not be read as the final comprehensive study. A revision that adds H1 and H3, and that
reframes the label-instability finding as the common obstacle, is recommended after the hackathon. This page is the
current summary until then.
