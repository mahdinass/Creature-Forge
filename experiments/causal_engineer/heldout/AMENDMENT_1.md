# Amendment 1 to ce-heldout-eval-v1: re-run of the AI arms after the authentication outage

**Status:**
- Approved by the owner on 2026-10-18 and registered before any amendment episode ran.
- Post-hoc: it was decided AFTER the registered run's results were known (`REPORT.md`): the non-AI arms, and the 4–15 AI
  episodes per arm that ran before the outage.

## Reason
The Token Factory key was rotated 50 minutes into the registered run. Every later model call failed with HTTP 401, so the AI
arms measured an infrastructure outage, not the scientist.

## What is re-run
- **Arms:** only `scientist_think`, `scientist_1shot_think`, `scientist_think_mem` and `scientist_think_mem_learned`.
- **Instances:** the same 40 instances of `protocol.json`. All 40 episodes per arm are re-run, including the ones that ran
  cleanly before the outage, so every arm is one complete, homogeneous run.
- **Unchanged from the registered run:**
  - budget 700, n_train 4, n_obs 4, MAX_STEPS 12;
  - model and thinking configuration;
  - scientist v2.3 prompts and schemas;
  - memory inputs and the Level C model (same SHA-256 as `protocol.json`);
  - verification and the analysis script.
- **Code changes since the registered commit:** only `scripts/ce_eval.py`, which gains a read-only key check before the run and
  a fail-fast stop at the first authentication error.
- **Not re-run:** the non-AI arms. Their registered results are complete and are reused unchanged.

## Analysis
- `scripts/ce_heldout_analysis.py` runs once on the amendment AI results plus the registered non-AI results, with the same
  tests (C1–C5b) and the same Holm correction.
- C5a involves no AI arm, so its registered result stands.
- The amendment report shows the registered result next to the amendment result and labels the amendment as post-hoc.

## Outputs
- Results: `results_amend1/`, with SHA-256 values.
- If an authentication error still occurs, the shard stops. The episodes completed so far stay. A resumed shard continues
  with `--resume`, and any gap is reported.
