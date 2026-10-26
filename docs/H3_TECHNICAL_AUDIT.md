# H3 technical audit — 26 October 2026

Status: saved-evidence audit and non-physics engineering only. No H3 physical outcome exists. H3 here means repair capability research, not specification workstream H3 (Cloud parallelism).

## Provenance and boundaries

Research branch `codex/h3-capability-audit` starts at H1 closeout `a2619c7dfc6513e55184bbc15baba7d288ff1dcf`; prior evidence pin `e8d5fa6730ecf6d2db67021a9d3d0f08cce03310` resolves locally. Read H1 [results](H1_RESULTS.md), [decision](H1_DECISION.md), recovered Stage 0 under `artifacts/h1_stage0_20261026/`, and source at the pin. No historical evidence, sealed raw data, release branch or submission material changed. User's untracked `scripts/e2r_analysis.py` is unrelated and preserved.

The named Notion page and Basic Memory `creature-forge` project are accessible. Text searches and relevant H1/controller research notes were checked against code. The separately named `CREATURE_FORGE_PROJECT_SPEC.md` attachment is absent: the supplied attachment directory contains the H3 request only. Relevant sections of tracked `docs/PROJECT_SPEC.md` supply aspirational context. `docs/NEMOTRON_CONTRIBUTION.md` is absent; actual evidence is in `has_agent.py`, `HAS_SCIENTIST.md` and `STAGE2_REPORT.md`. These are explicit source limitations.

The initial provider API check at epoch 1793029993.9952765 reports main `computeinstance-e01g6rhpgcpnf1bfbr` and batch `computeinstance-e01efb17k9jbzct0m0` STOPPED, unchanged H1 compute counters. H3 authorizes no new physics, training, VM starts or Token Factory calls. H1 financial permission does not carry over.

## Actual system and intervention points

| Layer | Implemented facts / implication | Source |
|---|---|---|
| Physics and morphology | Planar x/z/pitch biped, six hip/knee/ankle hinges; 1 ms MuJoCo steps; bounded body parameters and actuator controls. Per-leg lengths are available in sandbox bodies. No hardware or 3D validity follows. | `morphology.py`, `sandbox.py`, `creature_walk.py` |
| Phase gait | Thirteen parameters already implement clocked stance/swing, contact-dependent phase correction, joint PD, loaded hip pitch and ankle balance feedback. | `phasegait.py`, `contact.py` |
| Initiation | Fifteen parameters add amplitude ramp time and decaying initial lean. | `phasegait_init.py` |
| Foot placement | Seventeen parameters add proprioceptive swing-hip placement, filtered stance kinematics, slew limit, swing blend and touchdown latch. This is already deployed research machinery. | `phasegait_fp.py` |
| Mechanism DSL | Safe arithmetic, bounded reference/torque offsets, stance/swing/both gates, at most two mechanisms/eight gains. It extends the 15-D class, cannot compose with 17-D FP; hidden-plant verifier explicitly rejects mechanism controllers. | `mechanisms.py`, `walk_opt.SearchSpace`, `hidden_plant.seed_job` |
| Hidden plant | Gear strength, damping, mass/payload, friction, segment length, gain loss, sensor bias/delay and clock errors. Delay actually buffers pitch/joint state; contact sensing is not delayed by that wrapper. Controller geometry remains nominal. | `hidden_plant.py` |
| Search | Bounded CMA-ES, controller subspaces, joint body/controller repair and sequential repairs already exist. R0 uses train/select screens and two finalists within its policy budget. | `walk_opt.py`, `repair_strategy.py` |
| Diagnosis | Deterministic posterior, model checks, EIG and tool screening; robust paired-displacement checks already exist in v6. A new capability selector would enter before choosing repair space/tool; a new class enters at controller construction and candidate evaluation. | `belief_engine.py`, `hdb_evidence.py`, `hdb_workbench.py` |
| Nemotron | Reads lab notebook and chooses/proposes/delegates tools. MuJoCo, posterior/EIG, optimizer and verifier supply actual numerical evidence. Published Stage 2 did not isolate a verified recovery advantage over its engine. | `has_agent.py`, `STAGE2_REPORT.md` |
| Experience | Executable dossiers, amortized posterior, warm starts and calibrated repair-memory risk/rankers already exist. Their existence is not proof of incremental benefit. | `has_memory.py`, `amortized_posterior.py`, `repair_memory.py`, `repair_learner.py` |

All source paths above are under `creature_forge/` unless a document is named. The H3 plan pins the complete Python package, runner, analysis, verifier replay and protocol, without editing these prior implementations.

## Controller mathematics and the narrow missing capability

For leg l, phi_l = (phi + l/2) mod 1, with stance phi_l < duty. Raised-cosine hip trajectories and a swing knee bump generate references; ankle reference flattens the foot, clipped to ±0.8 rad. Joint demand is Kp(q_ref−q)−Kd*qdot, with no reference-velocity term. Loaded hips additionally receive clipped pitch/rate feedback; loaded ankles receive clipped balance feedback. Feedback terms each cap at half the nominal torque limit. Actual simulator command clipping remains ±nominal limit; actuator gear then determines delivered torque.

The FP estimate uses d = thigh*sin(pitch+hip) + shank*sin(pitch+hip+knee), with its differentiated velocity. It prefers loaded clock-stance legs, filters over 0.03 s, and adds swing hip offset clip(−kd*d/L−kv*v/sqrt(gL), ±0.5). The target slews at 20 rad/s; touchdown offset decays smoothly over stance. A contact-triggered late-swing clock advance has refractory and rate limits. Therefore “add contact-aware, phase-dependent control or foot placement” is not a new H3 contribution.

Both legs share reference/gain parameters and a half-cycle clock offset. Their observed states/contact can already differ, so existing outputs need not be symmetric. What the 17-D family lacks is an independently tunable signed left/right stance feedforward term. The general DSL has other expressive possibilities, but is not composed with FP or supported in the hidden-plant evaluator. This is an implementation-level capability gap, **not evidence that a particular robot requires the new term**.

## Recomputed development evidence

Reproduction: `python scripts/h3_saved_audit.py --prior-root <existing-prior-worktree> --out <new-file>`. The stdlib script reads explicit development paths only. Its committed output is `experiments/causal_engineer/dev/h3/saved_audit.json`, with source hashes. It verifies RL1 archive members, R0 outcomes, both H1 raw manifests and M1 manifest; recomputes M1 final counts from 108 raw records; reads saved VEL1 predictions, VEL2 panels, and existing EM1/DI1 raw records from the prior worktree. No outcome replay through physics, fitting or sealed loader occurs.

| Study | Verified finding | What it does not establish |
|---|---|---|
| E-1 | Published primary 56 vs 46/160 FULL, p=.060725; primary null not rejected. Published latency repair1/18; damping repair3/18. Read reports only: sealed raw stays closed. | Reports describe a diagnosis-to-repair gap; reserved families cannot become H3 development data. |
| RL-1 | 2,110 cells, 211 fault instances, **18 bases**; 81 instances have no FULL among ten interventions. Only 337/903 train-4/4 cells are FULL. Low friction: 1/17 instances has any FULL; one-side weakness: **26/34 do**, 8 do not. | No-FULL within sampled finite searches is not an impossibility or expressiveness certificate. Fault instances are not independent robot lineages. |
| R0 | 324 runs =18 bases×18 technical screens; each uses 3,000 policy rollouts, total 972,000. FULL per 54 runs: single/frozen20, single/do1 26, sequential/frozen28, sequential/do1 24, joint/frozen32, joint/do1 27. Recorded optimizer restarts 0 across 3,672 small searches. | Differences confound choices/optimization noise; absence of restarts is not proof more search would help. Counting 324 independent robots is invalid. |
| EM-1 | 804 candidate measurements, 324 instance groups, 30 historical bases; 480 alternative FULL labels absent; observed robustness-walking regret of selected submissions is zero. Raw candidate-mean twin minus plant walking =−5.434 pp (different weighting from published discrepancy statistic). | Dynamics discrepancy or calibration opportunity does not imply useful repair-selection headroom. |
| DI-1 | Both saved pilot panels: five eligible bases, three rejected attempts. Baseline FULL3/5 and raw-EIG3/5; random3/5 then4/5. The extra rescue is one lineage, with multi-probe/repair-path differences. | No isolated per-probe causal benefit or broad transfer result. |
| VEL-1 | Saved cross-fit predictions:211 rows;115 apparent submissions on17 contributing groups. Base-equal Brier: physical .176873, relevant experience .177203, shuffled .175667. | Relevant experience did not beat physical or sham control; these are warning predictions, not new FULL recovery results. |
| VEL-2 | Raw recount:9/15 bases stable over three FULL panels. Registered gate failed. | Single-panel success is not immutable ground truth. |
| H1 | 640 candidate identities×3 panels on18 bases; only477 labels stable (H1 audit). Best fixed physical rule +.617 pp, interval including zero; no learner advancement. Recount finds 14/18 bases with at least one all-three-FULL candidate,17/18 with any-panel FULL. The remaining no-FULL lineage is one unilateral-weakness base:34 candidates,102 panels,0 FULL. | The hard lineage is **one** base; RL1 already rescues other unilateral instances. No general unilateral controller inadequacy is proven. Post-outcome oracle choice is not an available selector. |
| Older M1 development | Final any-replicate FULL:ctrl15 1/12,ctrl17 5/12,joint15 4/12,joint17 6/12. Raw records and stored summary agree. joint15 has one replicate versus two for several alternatives. | Historical evidence supports testing controller structure, but is not a matched new H3 causal effect or an AI benefit. |

Prior reports: `E1_RESULTS.md`, `RL1_DEV_REPORT.md`, `R0_REPAIRABILITY_PROTOCOL.md` and `experiments/causal_engineer/dev/repair_strategy_r0/`, `EM1_RESULTS.md`, `DI1_RESULTS.md`, `VEL1_FEASIBILITY_RESULTS.md`, `VEL2_RESULTS.md`, `H1_RESULTS.md`, `WALK_RECOVERY.md`. Older M1 detail: `experiments/walk_recovery/oracle/REPORT_M1.md`. Raw EM1/DI1 remain in the prior worktree rather than duplicated into Git.

## Failure decomposition and identification limits

Across H1's 1,920 saved candidate-panel assessments, overlapping failures are: paired improvement395, validation walking885; confirmation observed909 and missing1011; among observed confirmations, walking172 failures, contact45, median speed0. Conditional missing confirmation is **missing**, not a failed long walk.

The 46,080 validation candidate seed rows include primary labels: walking34,883, fall4,843, contact_chatter2,170, falling_forward1,740, torque_saturated1,161, slow_or_few_steps1,126, and smaller categories. Labels follow priority rules and mask coexisting conditions. None of these saved rows contains the complete phase/joint/demand/delivered-torque/slip trace. Even a `torque_saturated` label does not show that saturation caused failure or that additional demand can help.

The saved VEL1 initial-probe summaries do not supply that missing candidate trajectory. Among apparent submissions,27 later non-FULL cases (14 groups) and88 FULL cases (17 groups) both have median initial ankle-saturation0 and initial walking0. Median initial slip is0.00691 versus0.00562, and initial capture summary−0.130 versus−0.161. These overlapping, unadjusted initial-state summaries are descriptive associations on repeated known bases; they do not identify saturation, traction or capture error as the cause of candidate failure. The committed receipt retains the exact values and denominators.

Rich plant/probe trajectories can expose contact, slip, commanded and delivered torque, joints, momentum and support. However their `tracking_error` is explicitly **demand/Kp**, a proxy combining damping/feedback, not actual q_ref−q (`physics_probe.py`). Do not infer a tracking-deficit mechanism from that field. The H3 logger adds controller phase, loaded flags and residual demand; it does not relabel that proxy.

Strongest supported bottleneck: insufficient independent, repeatable, decision-relevant evidence for learning; noisy verification and limited diagnostic retention. Search adequacy and controller class adequacy remain unresolved alternatives. Physical infeasibility is plausible for extreme traction/torque/morphology, but no saved record certifies it. The selected engineering experiment isolates one missing parameterization with strong search controls; it is not a declaration that expressiveness is the main cause.
