# Phase 2A - post-hoc failure diagnosis and proposed follow-up experiment (R1)

Status: **diagnostic + proposal only. The R1 experiment below is NOT approved and has NOT been run.** Phase 2A's result is unchanged: random search 14/20 held-out seeds (70%), DE 2/20 (10%), full-success threshold 90%, outcome **partial**. No protocol, history, frozen controller or original held-out file was modified.

## 1. What was examined, and its status

The six frozen random-search failures on held-out seeds 3006, 3009, 3010, 3014, 3018, 3019 were re-examined as **post-hoc diagnostic cases**. Seeds 3000-3019 are now consumed: nothing here is untouched evaluation data, and nothing was used to select or tune anything.

- Saved metrics first (`heldout.json`), then time-resolved physics: 10 distinct deterministic rollouts (the 6 failures + 4 walking seeds 3000, 3001, 3012, 3016) with a read-only recording wrapper around the frozen controller (`scripts/diagnose_phase2a_failures.py` -> `results/failure_diagnosis.json`). All 10 reproduced the saved outcomes and fall times exactly.
- **Budget overrun, disclosed:** the review allowed at most 20 additional rollouts. I executed the same 10 deterministic rollouts three times (30 executions): a second pass to add fields, and a third that should have been a no-physics refresh (my mistake). Results are identical across passes, only 10 distinct trajectories exist, and the script now has `--perturbation-only` so this cannot recur. The overrun is also recorded inside `failure_diagnosis.json`.
- Not available in the trace: whole-body COM (a "support offset" = torso x minus loaded-foot x is used as a proxy), and individual leg phase before the controller's clock (the wrapper logs the clock phase).

## 2. Findings (descriptive; correlation only)

**Saved metrics.** Walking seeds have 25-34 valid steps. Every failure has **0-1 valid steps**, with mean upright velocity -0.12 to -0.45 m/s (backward). None of the six ever established forward stepping, including 3009.

| seed | fell at | valid steps | x displacement at 1.0 s / 1.5 s | pitch at 1.0 s | pre-onset torso minus support-foot x |
|---|---|---|---|---|---|
| 3006 | 2.35 s | 0 | -0.08 / -0.16 m | -0.07 | -0.08 m |
| 3009 | 7.07 s | 1 | -0.05 / -0.06 m | -0.02 | -0.07 m |
| 3010 | 2.12 s | 0 | -0.09 / -0.21 m | -0.15 | -0.15 m |
| 3014 | 1.50 s | 0 | -0.15 / -0.68 m | -0.19 | -0.09 m |
| 3018 | 2.05 s | 1 | -0.09 / -0.25 m | -0.10 | -0.15 m |
| 3019 | 1.80 s | 0 | -0.08 / -0.33 m | -0.18 | -0.13 m |
| walking 3000, 3001, 3012, 3016 | - | 25-34 | +0.01..+0.18 / -0.04..+0.43 m | -0.04..+0.02 | (n/a; 0-1 s mean about 0.00) |

**Startup vs late.** Five failures began (pitch last above -0.15 rad) at 0.8-1.5 s, i.e. after only 3-6 touchdowns, before any forward-advancing steps. Seed 3009 is different in time but not in kind: it stepped for about 6 s (about 20 touchdowns) with only one forward-advancing step, drifting just -0.05 m by 2 s and then -0.86 m by the fall, which was backward at 7.07 s. **No failure was a collapse of established forward walking.** The 6 s training episodes could not have observed 3009's fall.

**Contact transitions.** At onset exactly one foot was loaded in all six cases, and onset was within 0.10-0.145 s of a contact event in all six (three of them 0.135-0.145 s before the loaded foot's liftoff, at clock phase 0.445-0.455, late stance). This is not evidence for a contact-transition mechanism: contact events occur roughly every 0.17 s at about 3 steps/s, so any time lies within about 0.09 s of an event by chance, and my onset definition is a threshold crossing that lags the true start.

**What did not separate failures from successes** (n = 6 vs 4, overlapping ranges): early-window (0.4-0.75 s) pitch, pitch rate, support offset, foot placement relative to the torso (-0.04..+0.10 m vs +0.005..+0.076 m), double-support and flight fractions, and the number of contact-sync corrections (0-1 vs 0-3). Early irregular touchdowns (the same foot twice in a row) also occur in walking seeds 3000 and 3016, and seed 3016 hovered near x = 0 for 2 s before walking away, so a slow start is recoverable.

**Torque.** No saturation in the first second or in the 0.3 s before onset (demand sat. fraction 0; applied equals demanded). Hip demand before onset was only 0.22-0.29 of the actuator limit, below the controller's own 50% feedback cap. The controller was not torque-limited at the moment of loss of balance. This does not say why the feedback was insufficient.

**Possibly different, untested:** peak foot force over body weight in the first second was mostly higher in failures (3.6-5.2 vs 3.1-3.7; ranges touch), which could indicate harder landings; n is too small to say.

**What does separate them, weakly:** after about 0.8-1.0 s the failures drift backward (x < 0 at 1.0 s in all six; positive or near zero in the walkers), the torso lean goes more negative (-0.07..-0.19 rad at 1.0 s, vs about 0 for walkers), and the torso trails the support foot by 0.07-0.15 m before onset. These are consequences-in-progress of the loss of balance as much as precursors.

**Initial perturbation (exploratory, no rollouts, 20 seeds).** The seed only sets the initial pose perturbation (std 0.03 rad). Initial pitch and the perturbation norm do not track outcome (p = 0.51 / 0.54). The right-knee initial offset is larger in failures (mean +0.035 vs +0.002 rad; permutation p = 0.016 uncorrected, 0.145 after Bonferroni over 9 features). It is a hypothesis to test on fresh seeds, not a finding.

## 3. What can and cannot be claimed

- Supported: the failures are **startup/transient failures to establish forward stepping**, ending in a backward fall during single support; walking, once established (25+ steps), did not collapse in any of the 14 successes. Torque saturation, flight, and the estimator's chatter flag are not what distinguished them.
- Not supported: any causal mechanism (why the stance feedback fails to prevent the backward lean; role of the knee offset; role of contact transitions), or that an FSM would fix it. The earlier ablation (contact sync not helping) and this diagnosis agree that contact-event handling is not the demonstrated bottleneck.
- Limits: 6 failures, 4 comparison successes, a COM proxy, one controller, one morphology.

## 4. Proposed R1 experiment (needs approval; not started)

**Question.** Does training for robustness (more seeds per candidate, a lower-tail objective, episodes long enough to see late failures) and a small evidence-motivated gait-initiation extension raise the fraction of seeds that reach established walking, measured on fresh seeds?

**Controller family.** Same modular hybrid controller. Arms A and B use the existing 13 parameters. Arm C adds two optional parameters that default to today's behaviour (so the frozen Phase 2A controller reproduces bit-identically, a regression test): `ramp_s` (amplitude ramp, now fixed 0.5 s; range 0.2-2.0 s) and `start_lean` (extra forward `pitch_ref` offset decaying over 1 s; range 0-0.15 rad). Motivation: all six failures lack forward progress during the first 1-1.5 s with backward lean. This is correlational. **No FSM, no RL, no neural controller.**

**Arms (one factor at a time):**
| arm | parameters | training objective |
|---|---|---|
| A | 13-D | mean fitness over 8 seeds (isolates "more seeds, longer episodes" vs Phase 2A's 3 seeds, 6 s) |
| B | 13-D | lower-tail: mean of the worst 2 of 8 per-seed fitnesses (isolates the objective) |
| C | 15-D | lower-tail (isolates initiation) |
| Control | frozen Phase 2A random-search controller, no training | replicates the 70% claim on fresh seeds |

**Optimiser.** Random search only (200 candidates is too few to learn from DE's anecdotal 2/20 result; DE can be a later arm). The Phase 2A frozen controller is injected as candidate 0 in every run (it counts toward the budget), so each arm starts from a guaranteed walker and the question becomes "can this beat the incumbent". Candidates 1..149 are shared across arms in the common 13 dimensions (common random numbers). Two independent replicates per arm (different RNG streams). No optimiser polishing.

**Seeds (all fresh; 3000-3019 are never reused as final evaluation):**
- train 4000-4007 (8 per candidate), 10 s episodes;
- validation 4100-4115 (16), 10 s, only to choose among each run's top 5 by training objective;
- diagnostic 5000-5009 (analysis only);
- final held-out 6000-6029 (30), 10 s, evaluated once after the selection file is committed.

**Rollout budget (hard cap 8,500, no automatic extension):**
| part | rollouts | sim-seconds |
|---|---|---|
| training: 3 arms x 2 replicates x 150 candidates x 8 seeds | 7,200 | 72,000 |
| validation: 6 runs x top-5 x 16 seeds (+ incumbent 16) | 496 | 4,960 |
| final: 6 selected + incumbent control = 7 controllers x 30 seeds | 210 | 2,100 |
| diagnostics (<= 20 unique rollouts, analysis only) + 40-rollout pilot | about 60 | about 600 |
| total | about 7,970 (cap 8,500) | about 80,000 |

Time estimate (extrapolated from Phase 2A: 600 rollouts x 6 s took about 40 s on 8 workers, i.e. about 0.09 core-s per simulated second): about 7,200 core-s, about 30 min on 4 workers; wall-time hard stop 90 min. Verify with the 40-rollout pilot first.

**Resources.** At most 4 workers (not 8: the last full-verification run was killed for low memory), spawn context, results independent of worker count, a pilot that records peak per-worker RSS, an abort if free system memory falls below 4 GB, every job accounted for (a lost or errored job stops the run).

**Pre-registered success criteria** (committed before any training, same gates as Phase 2A):
- Full success for an arm: >= 27/30 final seeds pass every walking gate (the 90% threshold is unchanged), median upright speed >= 0.25 m/s, zero body-dragging seeds.
- Partial: >= 18/30 (60%).
- "Better than the incumbent" requires an exact McNemar test on the 30 paired seeds, p < 0.05 two-sided, plus the point estimate above the incumbent's.
- Report Wilson 95% intervals; with n = 30 an observed 27/30 has a lower bound of about 74%.
- Secondary, single pre-registered hypothesis (no multiplicity): failure on the final seeds is associated with the right-knee initial offset (the exploratory p = 0.016 hint above).

**Controls.** Incumbent on the fresh seeds; A vs Phase 2A isolates seeds/episode length; A vs B isolates the objective; B vs C isolates initiation; two replicates per arm to expose optimiser variance; common random numbers and identical seed sets across arms; validation set separate from both training and final seeds to limit winner's curse.

**Stopping rules.**
1. Run replicate 1 of all three arms first (3,600 training rollouts) plus validation. If no arm's best validation walking fraction exceeds the incumbent's by >= 10 percentage points, **stop**: do not run replicate 2 or the final evaluation, and report a null result.
2. Any lost or errored job, a memory abort, or exceeding the wall limit stops the run; no silent retry.
3. The budget is never extended automatically; any extension needs a new approval.
4. The final held-out evaluation runs once; its result cannot be used to re-select.

**When an FSM would become justified (decision rule, not a plan).** Only if arm C (or B) still fails and the post-hoc analysis of the new failures shows a specific, repeated failure of the phase clock to align with contacts (for example fall onset consistently at contact transitions after controlling for event frequency) while stance feedback has torque headroom. The current evidence does not show that.

**Deliverable if approved:** a registered protocol commit (seeds, budget, gates, arms, success criteria), then the run, then selection committed, then one final evaluation, then a report in the same style as Phase 2A with the null result stated plainly if it is one.
