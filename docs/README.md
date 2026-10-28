# Documentation index

Files are grouped by purpose. Nothing has been moved: many reports are cited by frozen records, tests and commit
messages by their current path.

## Start here
| Document | For |
|---|---|
| [`../README.md`](../README.md) | What Creature Forge is, quick start, results and limits |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Components and data flow, as implemented |
| [`RESEARCH_STATUS.md`](RESEARCH_STATUS.md) | Every completed study, its registered decision and its evidence |
| [`submission/JUDGE_TESTING.md`](submission/JUDGE_TESTING.md) | Step-by-step testing guide for judges |

## Product (the release)
- [`FORGE_LOOP.md`](FORGE_LOOP.md), [`FORGE_LOOP_CONTRACTS.md`](FORGE_LOOP_CONTRACTS.md): the live draw → challenge →
  AI redesign → verify → evolve loop.
- [`DO1_DEMO.md`](DO1_DEMO.md): the *Verified repair* page (NO_AI).
- [`NEMOTRON_CONTRIBUTION.md`](NEMOTRON_CONTRIBUTION.md): the *Nemotron's experiment* page and every measured Nemotron
  contribution, favourable or not.
- [`INVESTIGATION_LAB.md`](INVESTIGATION_LAB.md), [`INVESTIGATION_DEMO.md`](INVESTIGATION_DEMO.md),
  [`CAUSAL_ENGINEER.md`](CAUSAL_ENGINEER.md), [`HAS_SCIENTIST.md`](HAS_SCIENTIST.md), [`UX_REDESIGN.md`](UX_REDESIGN.md):
  the other Studio pages and the systems behind them.
- [`RELEASE_V1.md`](RELEASE_V1.md): release record, provenance and freeze policy.

## Setup, operations and reproducibility
- [`submission/SETUP_AND_REPRODUCTION.md`](submission/SETUP_AND_REPRODUCTION.md): environment variables, live mode,
  reproduction levels and tests.
- [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md): cross-platform float differences and the exact-prompt checks.
- [`NEBIUS_SETUP.md`](NEBIUS_SETUP.md), [`NEBIUS_CLOUD_R1.md`](NEBIUS_CLOUD_R1.md): Token Factory and AI Cloud setup.
- [`NONGIT_ASSETS_2026-10-21.md`](NONGIT_ASSETS_2026-10-21.md), `ARTIFACT_ARCHIVE_*.md`, `archive/`: large files kept
  outside Git, with their hashes.
- [`MODEL_AND_SERVICE_TERMS.md`](MODEL_AND_SERVICE_TERMS.md), [`submission/LICENSE_REVIEW.md`](submission/LICENSE_REVIEW.md):
  model, service and dependency terms.

## Research reports and protocols (completed studies)
Summarised with their decisions in [`RESEARCH_STATUS.md`](RESEARCH_STATUS.md).
- Locomotion and robustness: [`PHASE2A_LOCOMOTION.md`](PHASE2A_LOCOMOTION.md),
  [`PHASE2A_FAILURE_DIAGNOSIS.md`](PHASE2A_FAILURE_DIAGNOSIS.md), [`R1_SEARCH_ANALYSIS.md`](R1_SEARCH_ANALYSIS.md),
  [`R2_DESIGN_PROPOSAL.md`](R2_DESIGN_PROPOSAL.md), [`R3_DESIGN.md`](R3_DESIGN.md),
  [`R3_ATTEMPT1_AND_V2_OPTIONS.md`](R3_ATTEMPT1_AND_V2_OPTIONS.md).
- Walking recovery: [`WALK_RECOVERY.md`](WALK_RECOVERY.md), [`WALK_RECOVERY_ITERATION3.md`](WALK_RECOVERY_ITERATION3.md).
- Hidden-damage studies: [`HDB_SPEC.md`](HDB_SPEC.md), [`STAGE2_REPORT.md`](STAGE2_REPORT.md),
  [`DUAL_SIGNAL_PLAN.md`](DUAL_SIGNAL_PLAN.md), [`DS1_PROTOCOL.md`](DS1_PROTOCOL.md), [`DS1_REPORT.md`](DS1_REPORT.md).
- DO-1: [`DO1_REPLICATION_PROTOCOL.md`](DO1_REPLICATION_PROTOCOL.md), [`DO1_REPLICATION_REPORT.md`](DO1_REPLICATION_REPORT.md).
- E-1 (registered, held-out): [`E1_PROTOCOL.md`](E1_PROTOCOL.md), [`E1_RESULTS.md`](E1_RESULTS.md),
  [`ROADMAP_REASSESSMENT_2026-10-24.md`](ROADMAP_REASSESSMENT_2026-10-24.md).
- Later studies (RL-1, R0, EM-1, DI-1, VEL-1, VEL-2, H1, H3) live on their research branches; see
  [`RESEARCH_STATUS.md`](RESEARCH_STATUS.md) §2.

## Submission package
`submission/`: [`DEVPOST.md`](submission/DEVPOST.md) (paste-ready text), [`FEEDBACK.md`](submission/FEEDBACK.md),
[`JUDGE_TESTING.md`](submission/JUDGE_TESTING.md), [`SUBMISSION_CHECKLIST.md`](submission/SUBMISSION_CHECKLIST.md)
(compliance), [`VIDEO_HANDOFF.md`](submission/VIDEO_HANDOFF.md) (video asset package), plus the earlier storyboard,
cut list and production notes.

## Project history and planning (internal)
- [`PROJECT_SPEC.md`](PROJECT_SPEC.md): the original vision. It is a plan, not a description of what was built.
- [`PROJECT_STATE.md`](PROJECT_STATE.md): append-only engineering log.
- [`memory/DECISIONS.md`](memory/DECISIONS.md), [`memory/INCIDENTS.md`](memory/INCIDENTS.md): decisions and incidents.
- [`MILESTONE_PLAN.md`](MILESTONE_PLAN.md), [`HAS_PLAN_2026-10-18.md`](HAS_PLAN_2026-10-18.md),
  [`RESEARCH_HANDOFF_2026-10-18.md`](RESEARCH_HANDOFF_2026-10-18.md), [`RESUME_CHECKPOINT.md`](RESUME_CHECKPOINT.md),
  [`RESUME_PROMPT.md`](RESUME_PROMPT.md), [`MEMORY_SYSTEM.md`](MEMORY_SYSTEM.md),
  [`FREE_MEMORY_QUICKSTART.md`](FREE_MEMORY_QUICKSTART.md): plans and handoffs for the development agents.
