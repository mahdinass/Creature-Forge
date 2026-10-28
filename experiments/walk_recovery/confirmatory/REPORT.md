# S3 confirmatory study (walkrec-confirm-v1, amendment 1): does Nemotron's engineering direction beat a strong non-AI strategy at equal compute?

**Answer: no.** On 48 fresh, genuinely failing robots, under equal total rollout budgets:
- the Nemotron director fully recovered **9/48**;
- the pre-declared primary comparator, a fixed engineering rule, recovered **19/48**.

The primary hypothesis (AI > FIX) is **not supported** (exact one-sided McNemar: 4 vs 14 discordant pairs, p = 0.996), and no
secondary hypothesis was supported. This is the only confirmatory evidence of the walking-recovery research. Everything
else (M1, S2, S2b, L2, S4a) is development data.

## Registration and conduct
- **Protocol** `protocol.json` was frozen with the owner's approval in `45c0825` (code `bfca67d`).
- **Amendment 1**, approved by the owner before any confirmatory creature existed, is `protocol_amend1.json`
  (`700924f`/`b44f863`). Its only change is the director's free-text length limit, 500 → 1500 characters. A pre-run smoke
  had shown that limit rejecting otherwise valid final plans. The original frozen file is unchanged.
- **Panel.** 48 failing creatures generated after the freeze (`walkrec-confirm-v1-gen`; 103 draws, all recorded;
  `panel.json` sha256 `4e45f5de…`).
  - Leg-length bands: L0 6, L1 22, L2 20.
  - Every creature walks on ≤ 1/8 selection seeds with the transferred controller; the aggregate outcome is FAIL.
- **Execution.** One execution on the batch VM (slot `s3`, snapshot `77981e2`).
  - 240/240 units; 0 unit errors; 0 missing; accounting exact in every unit (ledger == sum of lines ≤ budget).
  - Nothing was rerun.
  - The analysis `scripts/walk_confirm_analysis.py` (frozen) ran once, on the VM, against `protocol_amend1.json`
    (sha256 `41ad66b2…`) → `results/analysis_output.txt`.
- **Records.** `results/` (12 shard files, panel, summary, analysis output, SHA-256 `MANIFEST.json`; key scan: 0 hits).
- **Cost.** 219 Nemotron calls, $0.38. Infra for this stage is about $5; cumulative infra $26 of the $35 cap.
- **Incident.** The batch VM came within 7 minutes of its deadman deadline mid-run and was extended in time. No unit was
  interrupted (`docs/memory/INCIDENTS.md`).

## Design (as frozen)
- **Arms.** Every arm gets an equal TOTAL budget of 2,000 rollouts. Probes, plans, rejected plans, screening and every
  round are charged.
  - `ai_v2`: Nemotron-3-Super director, prompt v2.
  - `fix`: fixed rule; the primary comparator.
  - `cma_joint`: blind CMA-ES over controller and body.
  - `cma_ctrl`: blind CMA-ES over the controller only.
  - `rand`: the same pipeline as ai_v2 with random decisions.
- **Shared settings.** Family 17 (foot-placement controller available to every arm). Selection v2 for every arm.
- **Outcome.** `full_recovery_v1`, all three required:
  - ≥ 80% walking on 24 held-out seeds under perturbation and friction variation;
  - `verdict_v1` VERIFIED against the unmodified robot;
  - a 20 s confirmation on 24 more seeds.
- **Tests.**
  - Primary: one-sided exact McNemar, α = 0.05.
  - Secondary: Holm across ai_v2 vs cma_joint, rand and cma_ctrl.

## Results
| arm | FULL | PARTIAL | NOT | mean validation walking | mean budget used |
|---|---|---|---|---|---|
| **fix** (rule: probe placement / body / posture, search the best two subspaces + body) | **19** | 23 | 6 | 0.70 | 0.98 |
| cma_joint | 11 | 21 | 16 | 0.55 | 0.96 |
| rand | 11 | 27 | 10 | 0.59 | 0.98 |
| **ai_v2** (Nemotron director) | **9** | 25 | 14 | 0.50 | 0.86 |
| cma_ctrl | 8 | 20 | 20 | 0.47 | 0.98 |

| test | discordant (first-arm-only vs second-arm-only) | p | decision |
|---|---|---|---|
| **primary: ai_v2 > fix** | 4 vs 14 | 0.996 | **not supported** |
| secondary: ai_v2 > cma_joint | 7 vs 9 | 0.773 | not rejected (Holm) |
| secondary: ai_v2 > rand | 6 vs 8 | 0.788 | not rejected |
| secondary: ai_v2 > cma_ctrl | 6 vs 5 | 0.500 | not rejected |
| exploratory: fix vs cma_joint (two-sided) | 14 vs 6 | 0.115 | — |
| exploratory: rand vs fix (two-sided) | 4 vs 12 | 0.077 | — |
| exploratory: cma_joint vs cma_ctrl (two-sided) | 9 vs 6 | 0.607 | — |
| region-cluster sign test (ai_v2 − fix) | 1 region favours ai, 9 favour fix, 8 tied | 0.999 | — |

AI process measures:
- A valid plan in 48/48 pipelines.
- Body co-design in 50 of 112 plans.
- 86% of the budget used, against 96–98% for every other arm.

## What can and cannot be claimed
- **Claimable (classical engineering; no AI attribution).** A simple, fixed engineering procedure on top of a strong optimiser
  makes **40% (19/48)** of genuinely failing, never-seen robots walk, under the strict, independently confirmed criterion.
  The procedure: the foot-placement controller, body co-design, a short diagnostic search of a few control subspaces, and
  verdict-aware selection.
- **Not claimable.** That Nemotron's engineering decisions add value. At equal compute the AI director was worse than
  the rule. Exploratory: it was also not better than random decisions or blind joint search.
- **Consistent with development.** The same pattern appeared across every development stage and AI design:
  - S2/S2b: v1 2/12, v2 4/12 vs FIX 4/12;
  - S4a: closed-loop control-law invention 4/24 vs FIX15 11/24.

  The measured mechanisms are the same each time:
  - the model under-uses body co-design;
  - it prefers controller-centric changes;
  - it leaves budget unspent.
- **Limits.**
  - One simulator (planar MuJoCo biped), one controller family, one model (Nemotron-3-Super, thinking off).
  - Budget 2,000 rollouts, one optimiser noise seed per creature.
  - The FIX rule was designed by us with development knowledge (as was the AI's prompt).
  - Recovery outcomes are stochastic at this budget.
