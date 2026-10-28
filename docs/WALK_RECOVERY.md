# Walking recovery: research summary (2026-10-16/17, branch `feature/walk-recovery`)

**Question.** Can Creature Forge make robots that genuinely cannot walk walk, and does NVIDIA Nemotron directing the
engineering add value beyond strong non-AI methods at equal compute?

## Answer in four lines
1. **Yes, the system can recover walking.** A fixed engineering procedure fully recovers **19 of 48 fresh, never-seen
   failing robots (40%)** in the pre-registered confirmatory study. Its parts:
   - a new foot-placement balance mechanism in the controller;
   - morphology–controller co-design (body changes searched jointly with the controller);
   - short diagnostic searches over a few control subsystems;
   - verdict-aware selection.

   "Recovered" means ≥ 80% of 24 held-out perturbed seeds walk, `verdict_v1` verifies the gain against the original, and
   it holds for 20 s on 24 more seeds.
2. **No, Nemotron's decisions did not add value at equal compute.** The Nemotron director recovered 9/48; the primary test
   (AI > rule) was not supported (p = 0.996).
3. This held across every AI design we built and tested:
   - direct decisions (v1, v2);
   - a larger model (Ultra);
   - control-law invention in a safe DSL, one-shot and closed-loop with physical feedback;
   - a learned experience model.
4. The failure is specific and measured. The model under-uses body co-design, prefers controller-centric changes
   (timing, stance balance torques), and leaves budget unspent. With optimiser noise this large, those choices cost more
   than its diagnostic skill gains (a little above chance, H6).

## Stages (all records and reports under `experiments/walk_recovery/`)
| stage | question | result |
|---|---|---|
| M1a/M1 (dev) | Can a strong non-AI optimiser recover failing robots? Why did earlier runs fail? | The old 48-rollout retune was a near no-op, and the controller lacked foot placement. Adding it (5/12 vs 1/12) plus co-design: 6/12 at 8k. G1 PROCEED |
| S2 (dev) | Who should decide: AI, rule, random or blind search? | AI v1 2/12 vs FIX 4, RAND 7 at 2k; the AI ignored body co-design. R\* = 2,000, comparator FIX |
| S2b (dev) | One prompt revision; capacity check | v2 4/12 (= FIX); Ultra fails the validity gate |
| L2 (dev) | Can a learned surrogate reuse experience on held-out morphologies? | G3 FAIL. Reusing past solutions helps walking, but a medoid does as well as the network |
| S4a (dev) | Can Nemotron invent control laws, and does closing the loop help? | G4 FAIL. FIX15 11/24; closed-loop AI 4/24, one-shot 5/24. The loop runs (self-stops, revisions) but does not help |
| **S3 (confirmatory, frozen)** | AI director vs best non-AI at equal compute, 48 fresh robots | **FIX 19, CMA-joint 11, RAND 11, AI 9, CMA-ctrl 8. AI > FIX not supported** |

## What is new and verified in the product
- **Controller.** A foot-placement feedback mechanism (17-D controller, `phasegait_fp.py`). With zero gains it is
  bit-identical to the original controller.
- **Recovery machinery.**
  - A budget-exact CMA-ES co-design optimiser.
  - An equal-total-budget pipeline (`walk_pipelines.py`).
  - Gait diagnostics: capture margin, foot placement, fall direction.
  - A strict full-recovery criterion.
- **Studio "Recover walking".**
  - Runs the pipeline on the user's drawn robot, with the AI director (LIVE or SCRIPTED MOCK) or the fixed rule (NO AI).
  - Shows the reasoning, budget ledger, edits, per-seed verification and the side-by-side replay.
  - Accepts a new version only on FULL_RECOVERY.
- **Research instruments.** A safe control-law DSL, a closed-loop director, an experience model, and every protocol,
  record and analysis, kept for reproducibility.

## Integrity notes
- **Process.** Every stage was registered before it ran and analysed once. Records are stored byte-exact with SHA-256
  manifests. Nothing was rerun or selected.
- **Amendments** (all disclosed): S2b cap, approved before data; S3 text limit, approved before data. Also disclosed: one
  confounded dev arm (S2 `ai_nogait`).
- **Attribution.** Classical-optimiser recoveries are never attributed to Nemotron. The foot-placement mechanism was
  designed by the engineering assistant from the gait diagnostics, not by Nemotron.
