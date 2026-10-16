# M1a: can a strong non-AI optimizer make genuinely failing creatures walk? (development data, descriptive)

Protocol `protocol_m1a.json` (`walkrec-oracle-m1a-v1`) was committed before the run in `563f41c`; the run is the full, single
execution of that protocol, completed 2026-10-16 on the Nebius 8-vCPU VM (snapshot `454963c`; results
`results/m1a.jsonl`, sha256 `ed058137b56b7c32d2a392e7fde82e9a85633a60e9f17962adbe69cedabc8ab9`).
No model calls. This is **development data**. It informs the M1 design and the G1 gate, and it is never used as
confirmatory evidence.

## Conduct
- A first execution was interrupted by a bug: `walk_opt.encode` rejected a body lying exactly on a guided bound
  (tiny-feet, foot 0.06). Syncing the fix deleted the 6 completed units (see `docs/memory/INCIDENTS.md`, 2026-10-16). The
  whole protocol was then re-run from scratch.
- Units are deterministic. The re-run reproduced the deleted stilts units exactly (same statuses, verdicts, median gains
  and rollout counts), so nothing was selected by re-rolling.
- 33,016 rollouts of a 40,000 cap.

## Criteria
`recovery.full_recovery_v1`. **FULL_RECOVERY** requires all of:
- aggregate PASS (≥ 80% `walking`) on 24 held-out validation seeds under `VARIATION_PRESET`;
- `verdict_v1` VERIFIED against the unmodified original;
- a 20 s confirmation on 24 further seeds: ≥ 80% walking, median speed ≥ the creature's minimum, no body dragging.

**PARTIAL_IMPROVEMENT** = VERIFIED but not full. `verdict_v1` and `WalkingCriteria` are unchanged.

## Results (validation walking fraction of the candidate; the original walks on 0/24 for every creature)
| creature | R2 transfer | similarity transfer | controller CMA 250 / 1k / 4k | joint body+controller CMA 250 / 1k / 4k |
|---|---|---|---|---|
| stilts-drawn | 0.00 | 0.00 (WORSE, −0.97 m) | 0.00 / 0.00 / 0.38 PARTIAL | 0.00 / 0.04 / 0.25 |
| tiny-feet (guided: foot 0.06) | 0.00 | 0.00 | 0.04 / 0.54 PARTIAL / 0.71 PARTIAL | 0.42 / 0.42 / 0.67, all PARTIAL |
| top-heavy (guided: torso 15 kg) | 0.00 | 0.00 | 0.00 PARTIAL / 0.38 / 0.25 | 0.00 / 0.33 / 0.46 |
| weak-slippery (friction 0.05, torque 5 N·m) | 0.00 | 0.00 | 0.00 / 0.00 PARTIAL / 0.58 PARTIAL | 0.00 / 0.21 / **1.00 FULL_RECOVERY** (confirmation 24/24, 0.29 m/s) |

Status counts at 4k: controller-only 3 PARTIAL + 1 NOT_RECOVERED. Joint 1 FULL + 1 PARTIAL + 2 NOT_RECOVERED.

The recovered weak-slippery design: legs 0.43 m (thigh ×0.75, shank ×0.67), foot ×1.34, torso ×0.84, and a re-tuned
controller (gait frequency 1.01 Hz instead of 1.56 Hz).

## What this shows (and does not)
1. **All four development creatures genuinely fail**: 0/24 walking with the transferred controller, and most seeds fall
   before 1 s.
2. **Zero-rollout dynamic-similarity transfer does not help** on any creature. H2 is not supported as a standalone fix;
   on stilts it was worse.
3. **A strong optimizer moves every creature substantially toward walking within 4k rollouts.** Walking fractions reached
   0.38–1.00, compared with the old 48-rollout retune and the 0.04 m changes of the hand-edited proposals. One creature
   (weak-slippery, joint search) fully recovered.
4. **Signs of being budget-limited.** In 7 of 8 searches the best candidate was found in the last 15% of the budget
   (≥ 3,500 of 4,000), and no IPOP restart triggered.
5. **Signs of overfitting to the 8 training seeds.** On top-heavy the 250-rollout candidate validated (PARTIAL); the later,
   better-on-train candidates did not. The selection rule (best on train) and the number of training seeds need attention
   (H7).
6. **Not shown:** that these creatures cannot be recovered. Unrecovered means "not within 4k rollouts under the 15-D
   representation". Also not shown: anything about Nemotron (no model was involved).

Separately (`creature_forge/phasegait_fp.py`, 2 seeds, anecdotal): adding foot-placement feedback to the *unchanged* R2
controller removed stilts' forward fall for 5 of 6 untuned gain pairs. None walked yet (too slow). The gait features on
stilts show the forward-runaway signature this term targets: speed trend +0.6 m/s², the touchdown foot drifting to
−0.86 leg lengths behind the torso, and a capture margin of −1.44 L.

## Implication for M1 (proposal; needs the S1 approval)
Run on the 12-creature dev panel (4 named + 8 generated):
- controller-only and joint search at 8k;
- the same with the 17-D foot-placement controller (H3);
- 2 noise replicates for the main conditions;
- an H7 arm (3 nominal vs 8 varied training seeds).

G1 is decided on that panel.
