# Forge Loop — development live records (2026-10-15)

The first **real** Nemotron investigations of user-drawn creatures (nine without probes, then four with diagnostic probes; see the tables), run on the Nebius VM through the Studio API
(`scripts/forge_acceptance.py`, `scripts/forge_run_loop.py`). Kept unedited for provenance (raw prompts, raw responses, request
ids, usage, arms, seeds, per-seed results, verdicts). `INDEX.json` lists each record with its SHA-256.

**These are development runs, not an experiment.** The pipeline was improved between runs, so they must not be pooled into any
statistic. Model: `nvidia/nemotron-3-super-120b-a12b`, thinking off, strict JSON schema (calibration v2). Every run: 1–2 model
calls, ≈ $0.002 each.

| records | protocol at the time |
|---|---|
| i-d62a72f585fb (tiny-feet, stand), i-6a16174a72ae (balanced, push) | first live runs; push measured at 2.5 N steps; no foot geometry in the evidence |
| i-8cd662cb2a51, i-9d734f7a54a5 (loop) | + heel/toe-vs-ankle geometry in the evidence; loop patience 2 |
| i-7dbe0c20b190, i-8b8dfc87d27d (loop) | + push measured at 0.625 N (7 bisection steps) for every arm |
| i-eb2d953f2c8e, i-f9873480e42a, i-50af182da352 (loop) | + the prompt states the deterministic acceptance rule |

Findings (one creature, one challenge, n = 1 per protocol state — anecdotal):
- The model's hypotheses were physically plausible but inconsistent across runs (torque, friction, heel geometry).
- First **VERIFIED_IMPROVEMENT** of a drawn creature: `i-f9873480e42a`, round 2 of a loop, after round 1's friction proposal was
  falsified (0 wins / 8 losses). Hypothesis: "heel is too close to ankle, reducing backward base of support"; edit: rear
  `foot_length ×1.25`; median +3.125 N critical push force, 12 wins / 0 losses / 0 ties on 12 held-out seeds (p = 0.00024).
- In that record the validated baseline was `random:P2` (NOT_VERIFIED), **not** the AI arm's own twin `random:P1`. The arena
  now always validates the selected AI arm's own matched-random twin (commit after these runs), because the A/A null pilot
  showed ~15 % of random push edits verify. No claim of AI superiority is made from these records.
- Round 3 evaluated the proposed (not accepted) body as a hypothetical parent; nothing was accepted automatically.

## With diagnostic probes (2026-10-15, after the probe commits)

| records | protocol at the time |
|---|---|
| i-c2c4c48729d3 (single) | probes on; step B saw raw probe numbers only. Both probes refuted the model's hypotheses, yet it proposed a refuted mechanism (torque/balance): INCONCLUSIVE. |
| i-47bc91e407c2, i-f2ac2a96792d, i-172b6a48a0ad (loop) | + step B states each probe's measured verdict (CONFIRMED/REFUTED) and the method rule for refuted mechanisms. |

Loop on the balanced creature, push (twin validated on the same held-out seeds in every round):
- Round 1: probes foot ×1.5 **CONFIRMED** (+8.75 N), torque ×1.5 **refuted** (no change). Proposal rear `foot_length ×1.25`:
  **VERIFIED_IMPROVEMENT** +3.125 N, 12/0/0; its matched-random twin: INCONCLUSIVE (0/0/12).
- Round 2 (hypothetical parent = round-1 body): torque and friction probes refuted; balance-gain proposal INCONCLUSIVE; twin WORSE (−10 N).
- Round 3 (same parent, patience): foot ×1.5 probe confirmed (+11.25 N); rear `foot_length ×1.25` again: **VERIFIED** +4.375 N, 12/0/0;
  twin INCONCLUSIVE.
One creature, one challenge: a worked case, not a statistic. 2 model calls per round, ≈ $0.002 each.

## Walking (2026-10-15): tiny-feet creature, walk challenge (24 held-out seeds per validation)

| records | protocol |
|---|---|
| i-80d07dde758e | no probes: controller-only `walk.knee_amp ×0.8` → NOT_VERIFIED, worse on 12/24 seeds (0 wins) |
| i-b9adf9d9a843, i-7ef344a03dd2 (loop) | probes: foot ×1.5 CONFIRMED (+0.90 m), torso/torque refuted; `foot_length ×1.5` then `×1.4`: 13–14 wins / 1–2 losses, median +0.07–0.10 m → NOT_VERIFIED (min effect 0.5 m). In i-7ef344a03dd2 the random twin drew the AI's identical edit (v1 rule) — fixed as `matched_random_v2`. |
| i-105c4c50be98, i-fd78f195f334 (loop) | + `retune_controller` probe (48-rollout adaptation on training seeds): round 1 −0.76 m (refuted), round 2 +1.79 m (CONFIRMED); the model still proposed hand-edited walk parameters (`stance_knee`, `hip_bias`): +0.26 m, 15/0/9 → NOT_VERIFIED |
| i-26f00f643708, i-0a274446ce1a (loop) | + probe text says how to act on it (`retune_controller: true`); probes again confirmed feet and adaptation; the model chose body edits (foot ×1.4, torso ×0.7): small consistent gains, NOT_VERIFIED |

Findings: the model repeatedly identifies the support base and the probes confirm it, but its edits are too small to clear
the 0.5 m walking bar; it never chose morphology-controller co-design (`retune_controller`) even after the adaptation probe was
confirmed. Probe and arena seeds are deterministic per creature version and round, so the three loops are replications of
the model's behaviour on the same measurements, not independent physics samples. No walking redesign was verified.
