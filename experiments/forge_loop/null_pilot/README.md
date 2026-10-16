# Null pilot for `verdict_v1` (S3)

Question: can the paired sign test of `creature_forge/verdict.py` be trusted when per-seed scores are near-deterministic?
Raw record: `null_pilot.json` (regenerate on the VM with `python scripts/forge_null_pilot.py`, 265 s). 6,156 MuJoCo rollouts
(cap 8,000), 6 workers, Linux, commit `9a52006` plus the S3 files, no model call, no registered seed. Nothing here is a
registered result; thresholds in `verdict.MIN_EFFECT` are still the DRAFT of contracts section 6.3.

Creatures (`tests/fixtures/forge_zoo.json`): default, balanced, bird-knees (stand and survive pushes) and tiny-feet (weak:
falls; a positive control). Challenges: stand (8 s) and push (5 s, 5-step bisection in 0..80 N, resolution 2.5 N). Walk was not
run. Seeds: `arena.seed_sets` blocks (validate 16 + probe 8 per creature, all >= 100000).
Ties: |paired diff| <= resolution (push 2.5 N, stand 0.05 s). Sign test: one-sided exact binomial on the non-tied pairs.

## (a) A/A on the same seeds
The original run a second time as an extra arm: 8/8 cells (4 creatures x stand/push) have **identical per-seed scores**, all
pairs tie, verdict INCONCLUSIVE (0 non-tied pairs). Never VERIFIED. This also shows `run_seed` + pool are deterministic.

## (b) A/A on different seed draws (seed-to-seed variability)
Three disjoint 8-seed draws of the same original, 6 ordered comparisons per cell (48 comparisons):

| challenge | VERIFIED | WORSE | NOT_VERIFIED | INCONCLUSIVE | tie fraction | >= 6 non-tied |
|---|---|---|---|---|---|---|
| stand | 0 | 0 | 6 (all tiny-feet) | 18 | 0.76 | 25 % |
| push  | 0 | 0 | 0 | 24 | 0.96 | 0 % |

**Zero seed-noise false alarms** (0/48). The reason is that there is almost no noise to false-alarm on:
* Standing creatures stand for the full 8.0 s on **every** seed (one distinct score). Stand cannot discriminate between
  creatures that already stand; it is a pass/fail gate, not a continuous score, for them.
* Push critical force takes 2-3 distinct values (default and bird-knees: 7.5 or 10 N; balanced 5, 7.5, 10 N). One bisection
  step (2.5 N) is a tie, so the seed spread is invisible to the test. Tiny-feet falls without a push (score 0) on every seed.
* Only tiny-feet **stand** has a continuous spread (16 distinct survival times 1.2-3.1 s); there the sign test is a real test
  and stays correctly non-significant (best case 1 win vs 6 losses, p = 0.06).

## (c) Random-edit null (matched-magnitude random edits judged by `verdict_v1`)
Edits: `baselines.matched_random` applied to synthetic "AI" edits (1-2 edits, log-ratio 0.2-0.3 or control |du| 0.1-0.25).
These edits are not a true null: random edits really change a creature, so VERIFIED/WORSE here are mostly **real effects**
(for example `stand.stand_hip` +0.09 raised the default body's backward limit from 10 N to 17.5 N on 8/8 seeds, and a
foot_length x1.34 raised bird-knees from 10 to 15 N). The A/A cells above are the true null.

| cell | n edits | VERIFIED | WORSE | NOT_VERIFIED | INCONCLUSIVE | mean tie fraction | all pairs tied |
|---|---|---|---|---|---|---|---|
| push, standing creatures, validate 8 | 26 | 4 (15 %) | 9 (35 %) | 0 | 13 (50 %) | 0.45 | 35 % |
| push, tiny-feet (falls), validate 8 | 14 | 0 | 0 | 0 | 14 | 1.00 | 100 % |
| stand, standing creatures, validate 8 | 60 | 0 | 19 (32 %) | 0 | 41 (68 %) | 0.65 | 55 % |
| stand, tiny-feet, validate 8 | 20 | 0 | 0 | 8 | 12 | 0.41 | 15 % |
| stand, tiny-feet, validate 16 | 20 | 0 | 0 | 17 | 3 | 0.37 | 15 % |

Median paired difference (push, standing): quartiles -9.4 / -1.3 / 0 N, range -10..+7.5 N; 73 % of edits move the median by a
non-zero amount, most of them downward (a random control edit of 0.2-0.3 usually breaks a tuned PD). Stand on standing creatures
can only get worse (8.0 s is the ceiling): 19 of 60 random edits are WORSE (the creature falls on most seeds), 0 improve.
Tiny-feet stand: no random edit reached the 1.0 s minimum effect; one (stand.kp, shank x1.23) had 12 wins/3 losses (p = 0.018)
with median +0.35 s and was correctly NOT_VERIFIED.

Take-away for the loop: **a VERIFIED random edit occurs for about 1 in 7 standing-creature push cases and a WORSE for about 1 in
3**, so a VERIFIED AI proposal alone is not evidence of model skill; it only says "this change helped on held-out seeds". Skill
claims must use the pre-declared AI vs matched-random-twin aggregate comparison, never a single VERIFIED.

## (d) Validation variation (`ArenaConfig.validation_variation`, off by default)
Preset `arena.VARIATION_PRESET` = initial perturbation x2, push-time jitter +-0.15 s (on top of the built-in +-0.1 s), foot
friction +-10 %, drawn per seed and **identical for every arm of that seed**; friction is clipped to the sandbox hull and the
value used is recorded per seed (`validation_conditions`). Screening seeds are never varied.
* Push, default body: the original then has 4 distinct scores on 16 seeds instead of 2 (including one seed that falls without a
  push at perturbation 0.04), so there is real spread; A/A new draws stay non-significant (1 win/2 losses, INCONCLUSIVE),
  A/A same seeds all ties.
* Random edits on default (first 6 edits, push): plain WORSE/INCON/VERIFIED/INCON/INCON/WORSE vs varied
  WORSE/INCON/VERIFIED/WORSE/INCON/WORSE. Same direction every time; one marginal edit (w0 l4 t4 plain) becomes a clear WORSE.
  Mean tie fraction 0.40 vs 0.40, so variation does not add many non-tied pairs for strong edits; it makes marginal edits
  decidable and tests robustness to conditions rather than to one perturbation draw.
* Stand: no change for creatures that stand (still 8.0 s everywhere; balanced had 1 fall at the stronger perturbation); the
  continuous tiny-feet spread is unchanged.
* Rollout cost is identical (same number of jobs).

## Is the sign test meaningful?
Partly. What it can say: "the candidate beat the original by a consistent margin on N held-out perturbation seeds". What it
cannot say: anything about conditions the seeds do not vary. Because all seeds share the same physics, the p-value of a real
effect is almost always tiny (8 wins of 8 = 0.004) and of no effect is undefined (all ties); the test acts as a **consistency
filter**, not a sampling-uncertainty estimate. Use "verified on 8 held-out seeds", not "statistically significant".
No false alarm was observed from seed noise (0/48), so the rule is safe in that direction.

Weaknesses found:
1. **Resolution vs minimum effect.** Push ties at 2.5 N and the draft minimum effect is 3 N, so in practice an improvement
   needs a median of at least 5 N (two bisection steps). A consistent +2.5 N on 8/8 seeds (balanced, leg_density x1.25) is
   all ties. Acceptable (it is below the effect bar anyway) but the 3 N constant is misleading; say 5 N or refine the bisection.
2. **Stand ceiling.** For a creature that already stands the stand verdict is INCONCLUSIVE for any edit that does not break it.
   Offer the stand challenge verdict only when the original does not stand on most seeds.
3. **Stand minimum effect 1.0 s is large** for weak creatures (tiny-feet survives 1.2-3.1 s): an edit that is worse on 16/16
   seeds with median -0.96 s is NOT_VERIFIED rather than WORSE.
4. **Validate 8 is thin for stand on weak creatures:** 60 % INCONCLUSIVE at 8 seeds vs 15 % at 16 (ties 0.4).

## Recommendation for verdict_v1 and validation
* Keep the rule (zero seed-noise false alarms, deterministic, ties handled); adopt the wording above.
* Enable `validation_variation=VARIATION_PRESET` for push (and walk) validation, decided by the orchestrator: same cost,
  makes the claim about robustness not one draw, no false alarms in the A/A test. Leave off for stand on standing creatures.
* Seeds: push screen 4 / validate 8; stand screen 4 / validate **16** (1 rollout per seed); walk per the zoo pilot (12 / 24).
* Thresholds to consider (not changed in code, DRAFT per contracts): push abs 5 N (document the bisection step) or add a
  bisection-step option to `ChallengeSpec` for validation (e.g. 7 steps, 0.6 N) which would make the 3 N bar real; stand abs 0.5 s.
* Always show the matched-random twin's verdict next to every AI verdict.

## Honest limits
4 creatures, 80 stand + 40 push random edits, one platform, no walk. The random edits are not a calibrated null; they are real
perturbations. Tie rates depend on the creature set (strong standers are tie-dominated). Not a registered result.
