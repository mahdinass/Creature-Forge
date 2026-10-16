# Forge Loop zoo pilot (S1 challenge system)

`zoo_pilot.json` is the raw record; regenerate with `python scripts/forge_zoo_pilot.py --heavy` on the VM (about 4 minutes).
Bodies: `tests/fixtures/forge_zoo.json` (default body, the six Studio starters interpreted by `freehand.interpret`, one
hand-built "doomed" body). Seeds: sha256 blocks in the >= 100000 namespace (8 challenge seeds, 3 training seeds per creature,
disjoint). 4,080 MuJoCo rollouts in 223 s with 6 workers (18.3 rollouts/s), Linux, mujoco 3.15.0. Nothing here is a registered
result and no model was involved.

Protocol per creature: stand (8 s, 8 seeds); push (5 s, 8 seeds, both directions, 5-step bisection in 0..80 N, resolution
2.5 N); walk with the R2 winner ("r2-transfer", 10 s, 8 seeds); adaptation = (1+8)-ES from the R2 winner on 3 training seeds,
two noise seeds, evaluated on the same 8 challenge seeds. K = 48 / 96 / 192 are nested checkpoints of one 192-rollout run
(the same noise stream makes a smaller budget the exact prefix of a larger one; unit-tested), plus 3 rollouts to score the
starting vector.

## Headline (pass counts are of 8 seeds)

| creature | stand | push crit. force fwd / bwd (median N, min..max) | walk transfer | walk after adapt. K=48 / 96 / 192 (2 noise seeds) |
|---|---|---|---|---|
| default | PASS 8/8 | 32.5 (32.5..32.5) / 10.0 (7.5..10) | PASS 8 | 7,8 / 7,7 / 7,8 |
| balanced | PASS 8/8 | 32.5 (32.5..35) / 10.0 (5..10) | PASS 8 | 7,8 / 7,7 / 7,7 |
| bird-knees | PASS 8/8 | 32.5 / 10.0 (7.5..10) | PASS 8 | 8,8 / 8,8 / 8,8 |
| weak-slippery | PASS 8/8 | 35.0 / 10.0 (10..12.5) | FAIL 0 (chatter, falls) | 0,0 / 0,0 / 0,0 |
| tiny-feet | FAIL (survives 1.2..3.1 s) | falls with no push on 8/8 | FAIL 0 | 3,4 / 3,4 / 2,4 |
| top-heavy | FAIL (1.6..2.9 s) | falls with no push 8/8 | FAIL 0 | 0,0 / 0,0 / 0,1 |
| stilts | FAIL (1.5..3.7 s) | falls with no push 8/8 | FAIL 0 | 0,0 / 0,0 / 0,0 |
| doomed | FAIL (1.3..2.3 s) | falls with no push 8/8 | FAIL 0 (score 0 on every seed) | 0,0 / 0,0 / 0,0 |

## What we learned

* **Stand and push are near-deterministic in blocks.** Good bodies: stand survives 8.0 s on every seed; forward critical
  force is 32.5 N on 7-8 of 8 seeds (range one bisection step, 2.5 N); backward 10 N on most seeds (range 2.5-5 N).
  Bad bodies fall at 1.2-3.7 s with an IQR of 0.3-0.5 s; the outcome (FAIL) never varies. Three to four seeds would
  already give the same outcome class for stand and push; extra seeds only tighten the critical-force estimate.
* **Backward is the weak direction for every standing body (8/8 seeds).** The foot extends 0.04 m behind the ankle and 0.12 m
  ahead, so the PD stand tolerates only about a third as much force backward as forward. With `score = min(fwd, bwd)` and the
  contract default `target_force = 25 N`, **the default body itself FAILS the push challenge** (score 10 N, POOR threshold
  15 N). This is physics, not a bug. Recommendation: set the default push target to about 8 N (POOR below 5 N) or define
  PASS per direction; 25 N is only reachable for the forward half. Open decision for the orchestrator.
* **Walking varies more.** For walkers the distance in 10 s has IQR 0.15-0.2 m (range about 0.5 m). Marginal walkers flip
  outcome seed by seed (tiny-feet after adaptation: 2-4 of 8 walk). Use more seeds for walking than for stand/push.
* **Adaptation helps only where the transferred controller is broken but nearly workable.** tiny-feet went 0/8 -> 3-4/8
  (both noise seeds), with gain already at K=48; K=96 and 192 added nothing. top-heavy (0 -> 0, 0 -> 1 at K=192), stilts,
  weak-slippery (0/8, chatter) and doomed did not improve. On creatures that already walk (default, balanced) the search
  has nothing to gain on 3 training seeds (all 3 already walk, only tiny fitness differences are "improvements") and it
  **lost a seed** in 9 of 12 evaluations on default and balanced (8 -> 7): it overfits the three training seeds. Adaptation should therefore be
  offered only to creatures that fail to walk, and its result must be judged on held-out seeds, which is what the verdict
  rule does.
* **Replicate noise is large** (e.g. tiny-feet K=192: 2 vs 4 of 8), so a single adaptation run is weak evidence; matched
  noise seeds across arms (as the contract requires) are essential.

## Recommended settings (from 8 creatures, 2 replicates: treat as guidance, not proof)

* Adaptation budget **K = 48** (2 generations x 8 offspring x 3 training seeds) as the default, **96** at most; 192
  bought nothing here. Add 3 rollouts for scoring the starting vector, or pass `init_score` when known.
* Seeds: **stand/push screen 4, validate 8**; **walk screen 12, validate 24** (contract defaults for walking are fine; the
  walk pass rate of marginal creatures moves by +-2 of 8 between replicates). A sign test needs at least 6 non-tied pairs,
  so validate counts below 8 cannot reach significance.
* Cost: stand 1 rollout/seed, push up to 13 rollouts/seed (1 when the body falls without a push), walk 1 rollout/seed;
  the pilot averaged 18.3 rollouts/s on 6 workers (a standing creature cost about 560 rollouts / 48 s, a creature that falls
  immediately about 460 rollouts / 7-18 s).

## Caveats

* Single platform, 8 challenge seeds per cell, 2 noise seeds per adaptation: counts are descriptive, not tests.
* Starters `top-heavy` and `stilts` could not be interpreted with the Studio's 0.05 m leg gap
  (`freehand.interpret` attached a longer foot to the neighbouring leg and refused the drawing as "feet point in opposite
  directions"); the fixture widens the gap to 0.10-0.15 m and records it per creature. Worth a look by the freehand owner.
* `weak-slippery` stands and survives pushes like the default body but cannot walk with the transferred controller (its
  5 N m motors and mu = 0.05 feet): the clearest case of a creature whose controller, not shape, is the limit.
