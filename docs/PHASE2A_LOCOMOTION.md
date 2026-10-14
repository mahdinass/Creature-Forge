# Phase 2A - learning locomotion (diagnostic search)

Branch `feature/phase2a-locomotion`, from main `9ac6f72`. Scope: one fixed planar biped, a compact controller, two optimisers at a matched 600-rollout budget each, one run each. No Nebius calls. Everything below was measured in MuJoCo and is reproducible from the committed scripts and `experiments/phase2a/`.

## Result in one paragraph

A hybrid phase-based, contact-aware controller reached **genuine, gate-validated walking** (about 0.5 m/s, 0.30 m steps, alternating feet, ~3 steps/s matching the commanded cadence, no slip, no saturation) but **not robustly**. The frozen random-search controller walked on **14/20 held-out seeds (70%)** and fell on 6; the pre-registered walking criterion needed >= 90%, so the outcome is **partial, not a success**. The frozen DE controller walked on 2/20. Standing and both open-loop gaits do not walk. On the diagnostic seeds that failed, the gait never got going and the robot fell backward within ~2-3 s (a startup problem, not a steady-state one); the held-out failures were not inspected individually.

## Stage A - feasibility (before any optimisation)

| Question | Evidence |
|---|---|
| Can the Phase 0 sinusoidal PD gait walk forward? | No. 500 random samples over its full bounds (3 diagnostic seeds, 5 s): 0 walk on all seeds, 0 survive-and-move-forward; best survivor -0.16 m/s. 103 "falling forward", 26 contact chatter. Gains are already varied in that search, so gain changes alone do not help. |
| Does one extra parameter (hip-knee phase lag) give forward walking? | It gives forward *displacement* but not walking: 26/500 samples move > 0.2 m/s without passing the gates; 0 walk. |
| The exploit | Rounded parameters of the earliest forward candidate (`tests/test_locomotion.py`): ~11 touchdowns/s per foot against a commanded 0.82 Hz, 32-65% flight, 96% saturated torque, falls on some seeds. A distance objective would have chosen it. It is a regression test and must fail classification. |
| Why do open-loop gaits drift backward? | Not isolated. Observed: driving the stance hip rearward reacts on the torso and pitches it backward; the untuned phase gait falls backward (pitch to -1.24 rad). The Phase 0 backward shuffle also drags the left shank on the floor (43/1000 samples), so `body_dragging` is correct. |

Results: `experiments/phase2a/results/diagnosis.json`, `scripts/diagnose_locomotion.py` (note: the first scratch search used a simpler loop, so the committed numbers differ slightly).

## Controller (`creature_forge/phasegait.py`, `contact.py`)

Existing `GaitParams` / `compute_torque` are untouched; `OpenLoopController` only adapts them.

- **Phase clock** with duty factor (stance fraction 0.5-0.8). Hip: raised-cosine stroke; knee: sin^2 swing-lift bump with adjustable hip-knee timing (`knee_shift`); amplitudes ramp in over 0.5 s. Position and velocity are continuous at stance/swing transitions (tested on a fine phase grid).
- **Contact estimator**: foot normal force with hysteresis (5%/2% of body weight) and 20 ms minimum duration; same class online and offline. Raw (hysteresis-only) and debounced states are kept so chatter can be *measured* and steps *decided*.
- **Guarded contact sync**: an early touchdown late in swing advances the clock once per 150 ms refractory period, rate-limited to 2x clock speed; one-sample spikes cannot reset the oscillator (tested).
- **Stance feedback**: hip torque regulating torso pitch to `pitch_ref` and ankle balance torque, both only on loaded feet and capped at 50% of the actuator limit.
- 13 parameters (`phasegait.BOUNDS`).

Touchdown detection was validated against physics: free-fall touchdown time within 15 ms of the analytic value, standing normal force within 5% of body weight, measured cadence (3.1 steps/s) equal to commanded cadence (1.65 Hz x 2 feet), foot placement (0.30 m advance) and stance/swing durations.

## Evaluator (`creature_forge/locomotion.py`)

Hard gates define a walking seed (`WalkingCriteria`, frozen in the protocol): upright, speed >= 0.20 m/s, >= 0.8 valid alternating forward steps/s, alternation >= 0.9, <= 3 raw touchdowns/foot/s, flight <= 10%, slip <= 15% of loaded time (contact-point velocity), body-ground contact <= 0.5%, saturation <= 10%, |pitch| <= 0.8. A valid step needs alternation, >= 0.10 s airborne, >= 0.12 s preceding stance and a >= 0.05 m forward placement. Falls stop crediting displacement at fall onset. Labels: walking, fall, falling_forward, body_dragging, contact_chatter, hopping, torque_saturated, foot_sliding, backward_shuffle, stationary, sliding_without_steps, slow_or_few_steps. A separate continuous fitness (survival + validity-weighted progress and steps - effort/pitch + walking bonus) ranks candidates that fail gates.

## Optimisation (`creature_forge/optimize.py`)

Uniform random search and DE/rand/1/bin (pop 20, F 0.6, CR 0.8, bounds by clipping, no polishing) on the same morphology, training seeds (1000-1002), 6 s episodes and **600 rollouts each (200 candidates x 3 seeds)**; both start from the same 20 candidates. Windows-safe `spawn` pool, results independent of worker count (tested), worker exceptions recorded not dropped, pool timeout raises. Every candidate (including failures) is in `history_*.jsonl`.

## Pre-registration and seeds

`experiments/phase2a/protocol.json` was committed (`2f3df1c`) before any optimisation. Seeds: train 1000-1002, diagnostic 2000-2009 (analysis only), held-out 3000-3019 (evaluated once, after `selection.json` was committed; `scripts/eval_phase2a_heldout.py` refuses otherwise). Selection rule: highest mean training fitness.

## Results

Training (single run each; **one run per method is anecdotal, not a significant comparison**):

| | random search | differential evolution |
|---|---|---|
| rollouts / candidates | 600 / 200 | 600 / 200 |
| best training fitness | 5.46 | 2.45 |
| candidates walking on all 3 training seeds | 0 | 0 |
| candidates labelled walking (majority of 3 seeds) | 1 | 0 |
| outcome mix | 185 fall, 7 falling forward, 4 chatter | 177 fall, 16 falling forward, 2 body dragging |

Walking candidates are rare (~0.5% of the space), and 9 DE generations of 20 is little for a 13-D search; no conclusion about DE in general follows.

Held-out (20 unseen seeds x 10 s):

| controller | walking seeds | survived | median speed | verdict |
|---|---|---|---|---|
| standing | 0% | 100% | 0.00 | stationary |
| open-loop reference (Phase 0 1 Hz) | 0% | 100% | -0.89 | body dragging, backward |
| open-loop best of 500 | 0% | 100% | -1.12 | chatter / dragging, 67% saturated |
| **random search (frozen)** | **70%** | 70% | **+0.48** | **partial** (criterion needed 90%) |
| differential evolution (frozen) | 10% | 10% | 0.00 | does not walk |

Best feasible result: none by the "all training seeds" definition. Best walking behaviour: the random-search controller on its walking seeds (4.8 m in 10 s, 28 valid steps, 0% slip, 0% saturation). Best rejected results: see the diagnostic table in `diagnostic_eval.json` (training-fitness ranks 2-4 of random search were contact chatter, sliding without steps and falling forward, and none walked on the diagnostic seeds).

Selected controller: freq 1.65 Hz, duty 0.57, hip_amp 0.06 rad (very small stroke), knee_amp 0.69, hip_bias 0.14, pitch_kp 85, pitch_ref 0.155, balance_gain 107, sync_gain 0.84. The small hip stroke and forward bias mean it is a leaning, short-stepping gait.

Ablation on diagnostic seeds (`ablation.json`, analysis only): without pitch feedback 0/10 walk; without ankle balance 0/10; without knee lift stationary; **without contact sync 8/10 walk (vs 6/10 with it)**. So stance-gated torso/ankle feedback is essential; the contact-informed phase correction is not shown to help (n = 10, within noise).

## Failed attempts and corrections

- Sign flip of the hip amplitude was tried first and does nothing (equivalent to swapping legs).
- Phase-lag feasibility candidate: displacement without walking (see exploit above).
- Untuned phase-gait default falls backward (kept as evidence for stance pitch feedback).
- Regression I introduced and fixed: adding a fifth Studio tab made the header overflow by 44 px at phone width (caught by the existing lab browser check).
- A placeholder `peak_torso_vx = 0` in the replay payload was caught in the screenshot and replaced by the measured value (tested).
- Test expectation errors fixed while writing the evaluator tests (initial stance counts as a foot's first stance; slip label).

## Limitations

- One fixed planar (2-D) biped, one morphology; no 3-D, no terrain; steps are 0.2-0.3 m, hip stroke tiny.
- One optimiser run per method; the comparison RS vs DE is anecdotal. 3 training seeds gave a seed-fragile winner (2/3 seeds walking).
- The gait is startup-fragile: 6/20 held-out and 3/10 diagnostic seeds fell; on the diagnostic seeds I inspected, all three fell backward within 1.8-3.2 s (the held-out falls were not individually inspected).
- Contact-informed phase sync has no demonstrated benefit; "contact-aware" value comes from stance-gated feedback.
- Backward drift of the open-loop family is characterised, not root-caused.
- Gates are physically motivated but chosen by me before the run; thresholds were not sensitivity-tested.
- Studio replay is a fresh deterministic rollout, not a stored animation; training-progress panel is basic.

## Is a contact-triggered FSM or another family warranted?

Not yet shown. The failure is a startup transient (backward-leaning torso), not mistimed contacts, and the existing contact-triggered correction is not demonstrably useful, so swapping the phase clock for an FSM has no evidence behind it. Untested next steps, in order of cost: (1) robustness-aware training (more seeds per candidate, e.g. 5-8, and optimiser replicates) - cheapest and addresses the seed-fragile winner; (2) a gait-initiation / startup strategy; (3) only then an FSM. These need review before any larger budget is spent.
