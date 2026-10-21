# Research and engineering handoff — 2026-10-18

Written at the end of the causal-engineer session, for a fresh Claude Code session. Every fact below was re-checked on
2026-10-18 against Git, GitHub (`gh`), the Nebius API (`forge_cloud.py status` / `spend`, read-only), the local inference
ledger backup and the frozen records. No experiment was run and no cloud cost was incurred to write it. Where an older
document disagrees, §13 says which one is right.

**Source of truth, in order:** code and frozen records > Git history > this handoff > `docs/PROJECT_STATE.md` (append-only
log) > persistent memory notes. Re-run the checks in §12 before acting on anything here.

---

## 1. Current project status

### What Creature Forge implements
| Area | State | Where |
|---|---|---|
| MuJoCo planar biped, telemetry, fall/slip/saturation detection | working, on `main` | `creature_forge/{morphology,simulate,failures}.py` |
| Studio (React/R3F + FastAPI): draw or sketch creatures, stand/push/walk challenges, replays | working, on `main` | `studio/`, `creature_forge/studio/` |
| Forge Loop: Nemotron proposes bounded edits, MuJoCo arena with matched-random twins, frozen `verdict_v1`, accept-if-verified, lineage, diagnostic probes | working, on `main` (PR #16) | `investigation.py`, `arena.py`, `verdict.py`, `probes.py` |
| Engineering memory v1 (Forge Loop lessons) | implemented, **off by default**; no measured benefit | `memory.py` |
| Walking recovery: 17-D foot-placement controller, budget-exact CMA-ES co-design, equal-budget pipelines, `full_recovery_v1` | working, **research branch only** | `phasegait_fp.py`, `walk_opt.py`, `walk_pipelines.py`, `recovery.py` |
| Studio "Recover walking" (AI director LIVE / SCRIPTED MOCK, or the NO-AI fixed rule; accept only on FULL_RECOVERY) | working, research branch only | `studio/src/recovery/*`, `/api/forge/recoveries` |
| Causal engineer: fault bench, physics instruments, Nemotron scientist v2.3, non-AI policies, Level A/B/C experience | working as research code, research branch only; **no demonstrated advantage over the fixed procedure** | §3, §4 |
| Studio "Causal engineer" tab | shows **recorded** investigations only (7 dev records); it cannot launch a live scientist run | `studio/src/causal/*`, `creature_forge/studio/causal_api.py` |

Experimental (research code, not product features): the control-law DSL and director v3 (S4a), the L2 experience model,
the scientist and its memory/learner arms.

### Git state (verified 2026-10-18)
| Ref | Commit | Relation | PR |
|---|---|---|---|
| `main` | `e58dbdf` (merge of PR #16) | protected; untouched since 2026-10-16 | — |
| `feature/walk-recovery` | `f96b9d9` | 65 commits ahead of `main`, 0 behind | none |
| **`feature/causal-engineer`** | `192c000` before this handoff; the handoff commit sits on top | contains all of `feature/walk-recovery` plus 51 commits; 116 ahead of `main`, 0 behind; **does not** contain `feature/demo-capture` | none |
| `feature/demo-capture` | `29e8e50` | 4 ahead of `main` | **PR #17, Draft, open** ("submission PR"); CI failing on `test_license` (fixed by PR #18) |
| `fix/ci-license-and-workflow` | `e583f41` | 1 ahead of `main`; worktree `cf-ci-fix` (sibling of the main checkout) | **PR #18, open**, CI green 2026-10-17, mergeable, awaiting owner review |

- The repository is **PRIVATE**. Default branch `main`.
- Stale refs: `origin/wip/s8-engineering-memory-UNVERIFIED` and `origin/wip/s9-security-hardening-UNVERIFIED` (content
  integrated in PR #16), the merged `feature/*` branches, and 27 leftover agent worktrees under `.claude/worktrees/` (one is
  locked). All their work is integrated. Deleting them needs the owner's agreement.

---

## 2. Research history: results and lessons

### Before the Forge Loop (2026-10-13/14, all on `main`, frozen)
- **Phase 1:** random edits verify 22/100; 3 live Nemotron calls, both valid replies failed. No AI claim.
- **Phase 2A:** a phase-gait controller walks 14/20 held-out seeds, against a pre-registered 90% target. Partial result.
- **R1:** null result (futility STOP).
- **R2:** local robustness search gives a walker that holds 150/150 seeds vs 91/150 for the incumbent. Classical
  optimisation, not attributed to Nemotron.
- **R3:** attempt 1 aborted (empty replies, `finish_reason=length`); v2 generation calibration failed, so no statistical
  experiment ran.
- **Lesson:** constrain identifiers by construction (strict JSON schema with enumerated ids and paths). Reasoning models need
  large token limits.

### Forge Loop (2026-10-14/16, merged in PR #16)
- **Scoreboard v1 (registered):** AI verified 6/12 vs matched-random twin 1/12 (5 vs 0 discordant, exact one-sided McNemar
  p = 0.031); heuristic 0/12. Push-dominated, small, but the only registered positive AI result in the project.
  `experiments/forge_loop/scoreboard/REPORT.md`.
- **Memory evaluation (registered):** with memory 6/12 vs without 7/12 (p = 0.773). Lessons were cited in 0/12 runs.
  `experiments/forge_loop/memory_eval/REPORT.md`.
- **Walking investigations:** nothing verified in 7 dev records plus `live2-walk` and `live3-walk-stilts`. The model never
  chose controller co-design.
- **Lesson:** on push, the easy fix (a longer foot) needed no AI. Memory as optional text is ignored.

### Walking recovery (2026-10-16/17, `feature/walk-recovery`; summary `docs/WALK_RECOVERY.md`)
| Stage | Result | Lesson |
|---|---|---|
| M1a/M1 (dev) | The old 48-rollout retune was a near no-op. Foot placement raised controller-only recovery 1/12 → 5/12; joint co-design 6/12 at 8k. G1 PROCEED | Representation (a missing balance mechanism) mattered most. Search failure is never called impossibility |
| S2/S2b (dev) | AI director v1 2/12, v2 4/12 vs FIX 4, RAND 7, CMA-joint 3 at 2k. Ultra failed the validity gate | Decisions inside a fixed action space are drowned by optimiser noise. The AI under-used body co-design |
| L2 (dev) | G3 FAIL. A learned surrogate warm start is no better than reusing the medoid of past solutions | Learned components must beat retrieval baselines |
| S4a (dev) | Control-law invention in a safe DSL: FIX15 11/24, closed-loop AI 4/24, one-shot AI 5/24. G4 FAIL | The loop ran (self-stops, revisions) but did not help. Invented laws were mostly redundant stance torques |
| **S3 (confirmatory, frozen)** | Equal total budget 2,000, 48 fresh robots: FIX 19, CMA-joint 11, RAND 11, AI director 9, CMA-ctrl 8. AI > FIX not supported (4 vs 14 discordant, p = 0.996) | The classical procedure recovers 40% of genuinely failing unseen robots. Nemotron's decisions added nothing at equal compute |

The foot-placement mechanism was designed by the orchestrating assistant from gait diagnostics, not by Nemotron.

### Causal engineer (2026-10-17/18, `feature/causal-engineer`; summary `docs/CAUSAL_ENGINEER.md` §0)
- **Design change:** stop asking the AI to allocate optimiser budget. Instead, give it robots with a single injected fault
  whose diagnosis decides the repair (§3), so its decisions must be right about a cause.
- **Development (dev robots, prompts tuned on them):**
  - The pilot1 audit (`experiments/causal_engineer/dev/AUDIT_PILOT1.md`) found interface and evidence defects first:
    - 5/13 runs ended on invalid replies;
    - 0 hypothesis revisions;
    - no healthy reference;
    - a one-directional experiment catalogue;
    - "experiments are expensive" wording;
    - non-identifiable diagnoses (7/13 robots are repaired by 3–7 tools).
  - Fixes v2 → v2.3. Paired FULL recoveries on 7 dev robots: v2.1 0, v2.2 1, v2.3 3, against exhaustive 5.
- **Held-out evaluation (registered; 40 robots on 22 unseen bases).** The registered run lost its AI arms to a mid-run key
  rotation. Amendment 1 (owner-approved, post-hoc) re-ran the 4 AI arms on the same frozen inputs.

  | arm | FULL of 40 | mean walking | rollouts used of 700 | chose a repairing tool | first repair repairs | LLM $ |
  |---|---|---|---|---|---|---|
  | exhaustive (fixed procedure) | **23** | 0.85 | 689 | 38 | 36 | 0 |
  | learned (Level C ranking) | 18 | 0.83 | 688 | 37 | 33 | 0 |
  | scientist + memory | 16 | 0.74 | 359 | 35 | 29 | 4.23 |
  | scientist (closed loop) | 14 | 0.69 | 317 | 34 | 23 | 3.70 |
  | scientist + memory + Level C advice | 14 | 0.75 | 362 | 34 | 26 | 4.17 |
  | random | 12 | 0.62 | 690 | 28 | 17 | 0 |
  | one-shot scientist | 8 | 0.60 | 381 | 30 | 21 | 0.29 |
  | expert rules | 6 | 0.61 | 690 | 31 | 22 | 0 |

  **No registered hypothesis is supported after Holm correction:**
  - C1: prediction accuracy is below the majority baseline (14 vs 23 episodes).
  - C2: closed loop vs one-shot, 10/4 discordant, p = 0.090.
  - C3: closed loop vs exhaustive, 2/11.
  - C4: memory, 6/4, p = 0.38.
  - C5a: learned vs exhaustive, 1/6.
  - C5b: advice, 5/7.

  Reports: `experiments/causal_engineer/heldout/REPORT.md` and `REPORT_AMEND1.md`.
- **Lesson:**
  - Nemotron genuinely runs an experiment–revise–repair loop on unseen robots: 369 status updates, experiments it designed
    itself, applicability judgements.
  - It beats random choices and hand-written rules, but not systematic screening.
  - The held-out set is now spent for these hypotheses.

---

## 3. Current AI architecture (causal engineer)

### Benchmark (`creature_forge/fault_bench.py`, `scripts/fault_bench_build.py`)
- **Bases:** verified walkers from earlier stages; 17-D `phasegait_fp` controllers. Dev bases come from S2/S2b, held-out
  bases from S3 (28 bases, never used in development).
- **8 injected faults, each with a matching tool:**

  | fault | matching tool |
  |---|---|
  | `posture_lean` | posture |
  | `cadence_fast` | timing |
  | `feedback_loss` | feedback |
  | `placement_loss` | placement |
  | `short_feet` | foot_length |
  | `heavy_torso` | torso_mass |
  | `weak_motors` | torque_limit |
  | `slippery` | foot_friction |
- **10 repair tools:**
  - control: posture, timing, feedback, stride, placement;
  - body: foot_length, torso_mass, torque_limit, foot_friction, leg_length.
- **Repair matrix:** the walking fraction on 8 check seeds after a 160-rollout CMA repair with each tool, measured per
  instance. It shows that many robots are repaired by several tools.
- Seed roles are disjoint: check, train, obs, validate, confirm.
- **The model never sees the fault label.** Labels are used only to score diagnosis afterwards.

### Instruments (`creature_forge/eng_tools.py` Workbench, `physics_probe.py`, `physics_digest.py`)
One budget-exact ledger per episode: 700 rollouts, n_train 4, n_obs 4.
- **`observe`** (cost n_obs): physics summary on the obs seeds. It covers:
  - COM state, angular momentum, CoP and support interval, capture point;
  - contacts, slip, friction use, torque saturation, tracking error, swing clearance;
  - cadence vs pendulum frequency, Froude number;
  - a pre-fall block.

  `physics_digest.key_facts` adds KEY FACTS with signs in words and healthy-reference p10–p90 ranges from 12 dev bases
  (`experiments/causal_engineer/dev/healthy_reference.json`).
- **`counterfactual`** (cost n_obs; the first one 2 × n_obs):
  - catalogue entries, or model-designed parametric changes `param@level[&param@level]`;
  - scale levels ×0.33 … ×3; additive levels ±0.05/0.1/0.2 R;
  - out-of-range requests are refused at zero cost, never clipped.
- **`stress_test`** (v2.3; cost 2 × n_obs): the current best design for 20 s on the obs seeds.
- **`repair(tool, budget)`:** budget-exact numpy CMA-ES over that tool's subspace on the train seeds. It is refused unless
  the budget covers the initial point and at least 3 generations.

### Nemotron scientist (`creature_forge/scientist.py`, `causal_scientist_v2`, REVISION v2.3)
- **Model:** `nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory, with thinking enabled
  (`chat_template_kwargs.enable_thinking`); max_tokens 32,000; timeout 600 s; temperature 0.6; strict JSON schema.
- **Limits:** MAX_STEPS 12, MAX_REQUESTS 24; one repair call per invalid reply.
- **Each step's reply, in order:**
  1. `result_reading` of the newest measurement;
  2. `status_updates`, required for every scored hypothesis;
  3. `new_hypotheses`;
  4. `memory_assessments`, in the memory arms;
  5. exactly one action from `ACTIONS = ("counterfactual", "test", "repair", "conclude")`.
- **Predictions:** registered before each experiment (at most 12) and scored deterministically with tolerances.
- **Prompt facts:**
  - BUDGET: unused rollouts have no value, and the repair budget sets the number of CMA generations;
  - "N rollouts would stay unused";
  - VERIFICATION: the exact `full_recovery_v1` criteria.
- **One-shot ablation:** a single call from the initial observation, then repairs.
- **Secret guard:** `nebius.contains_secret` is checked fail-closed on every record.

### Independent verification (hidden from every policy)
- `fault_bench.verify` applies `full_recovery_v1`: at least 80% of 24 validate seeds walking at 10 s, `verdict_v1`
  VERIFIED_IMPROVEMENT against the faulty robot, and a 20 s confirmation on 24 more seeds.
- Thresholds, `WalkingCriteria` and `verdict_v1` are frozen.

### Non-AI policies (`creature_forge/ce_policies.py`) on the same Workbench
- **exhaustive:** every catalogue counterfactual, a fixed ranking table, top-2 repairs.
- **learned:** exhaustive with the Level C ranking.
- **expert:** hand-written telemetry rules.
- **random**, and **blind** (dev only).

### Evaluation driver
`scripts/ce_eval.py`:
- a pre-run read-only key check;
- fail-fast on the first authentication error;
- `--resume`, sharding, `--instance-ids`.

Analysis: `scripts/ce_analysis.py` (dev) and `scripts/ce_heldout_analysis.py` (registered: exact McNemar, sign test,
Wilcoxon, Holm).

### Studio integration
- **"Causal engineer" tab** (`studio/src/causal/CausalLab.tsx` and others):
  - API: `GET /api/causal/records`, `/records/{id}`, `/records/{id}/replay` (replays are re-simulated).
  - It shows the timeline, hypothesis ledger, predictions, memory verdicts, stress tests and independent verification.
  - It holds 7 hand-picked dev records (3 FULL, 1 PARTIAL, 1 NOT, plus 2 memory-arm records), labelled as examples, not
    rates.
  - Export: `scripts/ce_export_records.py`; records in `experiments/causal_engineer/demo_records/`.
- **"Recover walking"** is the only Studio flow with a live or NO-AI choice; it runs the S3 pipeline, not the scientist.
- **Gap:** there is no live scientist run and no NO-AI causal run from the Studio.

---

## 4. Experience-learning system

Supervision comes only from outcomes the system measured itself: investigations, and the repair matrices of training
instances. Fault labels are never training input.

| Level | Implementation | How it is used | Evaluation | Status |
|---|---|---|---|---|
| **A, episodic memory** | `experience_bank.py` (`ExperienceBank`, `compute_signature`, kNN over a standardised physics signature plus robot features), `ce_memory.py` (`build_bank`, `adapter_for`, `group_key` excludes a robot's own base family). Bank: 165 dev "probe" episodes (initial observation, catalogue counterfactual responses, measured repair matrix) plus pilot1–5 investigation episodes. Episode text leads with the measured repair matrix. | k = 2 nearest episodes in the `scientist_think_mem*` arms. The scientist must give each item a verdict: `applies`, `does_not_apply`, `needs_adaptation` or `test_first` | Held-out C4: 16 vs 14 FULL, p = 0.38. 117 verdicts: 33 applies, 38 does_not_apply, 44 needs_adaptation, 2 test_first. Negative transfer in 1 episode; memory followed and correct in 3 | **works**; real applicability judgements; **no demonstrated benefit** |
| **B, mechanism cards** | `experience_bank.build_cards`: agglomerative groups of training signatures, with condition ranges, per-tool verified repair rates, counter-examples and support counts. Status is deterministic: `empirical heuristic` (support ≥ 3 and best-tool rate > 0.7), else `hypothesis`. `principle` is a deterministic factual sentence. `principle_prompt` / `set_principle` (Nemotron rephrasing) exist but **have no caller**, so no card was phrased by Nemotron | Retrieved alongside episodes ("episodes+cards") | Not separable from Level A in the held-out run, which has one memory arm | **works**; benefit not demonstrated; not evaluated separately |
| **C, trained repair-effect predictor** | `repair_learner.py` (numpy logistic, MLP ensemble, kNN). Target: the repair matrix (walking ≥ 6/8 check seeds) per tool. Features: the faulty robot's own body (`robot_features`; the stale pre-recovery features were fixed, v0 results kept). Runtime model `experiments/causal_engineer/dev/level_c_logistic.json` (165 instances, 12 bases, 10 tools); training `scripts/ce_train_level_c.py` | (1) the `learned` policy: exhaustive with the learned ranking from observation + counterfactuals; (2) one advice item `LEARNED-1` (observation-only model, labelled with its held-out accuracy) in `scientist_think_mem_learned` | Dev LOBO (`LEVEL_C_LOBO.md`): top-1 0.66 vs CF heuristic 0.59 (+0.07 [0.02, 0.14]); vs kNN only +0.03 [−0.06, 0.12]; MLP spread is no uncertainty signal (AUROC 0.55). Held-out: C5a learned 18 vs exhaustive 23 (not supported); advice top-1 repairs 31/40, but it was the scientist's first repair only 9 times (C5b 14 vs 16) | **works and is accurate**; better dev ranking did **not** become more recoveries; advice is mostly ignored |

**Working features vs demonstrated learning benefits.** All three levels run end to end, are deterministic, and are tested:
`tests/test_experience_bank.py`, `test_repair_learner.py`, `test_ce_policies.py`. No level produced a statistically
supported improvement on held-out robots. The banks are static: nothing is updated online during an evaluation.

---

## 5. Critical negative findings

1. **Underperformance against exhaustive engineering (C3: 2 vs 11 discordant).** Exhaustive spends the whole budget on
   two large repairs. With single-tool faults, a broad screen plus top-2 repairs is a very strong baseline.
2. **Premature stopping.** The scientist arms use only 317–362 of 700 rollouts, against 689. They conclude once the 4 train
   seeds walk; the hidden 24-seed, 20 s verification then fails. This was seen in pilots 2–5 and was only partly fixed by
   v2.1 (budget facts), v2.2 (verification criteria) and v2.3 (stress test).
3. **The first decision is also weaker; it is not only budget.** The scientist eventually picks a repairing tool about as
   often (34/40 vs 38/40). But its **first** repair repairs only 23/40, against 36/40 for exhaustive (29/40 with memory).
   `REPORT_AMEND1.md`'s heading "decision quality is not the gap" understates this.
4. **Poor prediction calibration.**
   - Accuracy is 438/1178 = 0.37; chance is 0.33 for three directions.
   - It is below the per-episode majority baseline in 23 of 37 episodes. Most measured changes fall within tolerance, and
     the model predicts changes.
   - Diagnosis label match: 11/34 closed loop, 9/40 one-shot. This is partly a benchmark property, since many robots are
     repaired by several tools.
5. **Weak memory benefit.** C4 gives 16 vs 14 (p = 0.38). The applicability verdicts are real, but they do not translate
   into recoveries. In the Forge Loop memory evaluation (p = 0.773), lessons were never cited.
6. **Underuse of learned advice.** The advice was right 31/40 times, marked "applies" 36 times, and followed first 9 times
   (8 of those repaired). Simply following the ranking (`learned`) recovers 18, still below exhaustive at 23.
7. **Across the whole project,** no Nemotron decision layer has beaten the best non-AI procedure at equal compute (S3, S4a,
   causal held-out). The only registered AI win is the small, push-dominated Forge Loop scoreboard against random twins.

---

## 6. Research direction

**Objective:** an AI engineering scientist with:
- (a) **predictive physical understanding**: calibrated, quantitative predictions of what an intervention will do;
- (b) **active causal investigation**: it chooses informative experiments, revises hypotheses and knows when it knows
  enough;
- (c) **transferable experience**: memory and learned models that change its decisions on unfamiliar robots.

Numerical optimisers (CMA-ES), MuJoCo and the frozen verifier remain its instruments and judge. **The goal is not an LLM
replacing numerical optimisers**, and an optimiser's recovery must never be attributed to Nemotron.

Success has to be shown against strong simple baselines (exhaustive screening, learned ranking, kNN retrieval) at equal
total compute, on fresh registered held-out data.

---

## 7. Infrastructure (verified 2026-10-18, read-only; no credentials here)

| | main VM | batch VM |
|---|---|---|
| Instance id | `computeinstance-e01g6rhpgcpnf1bfbr` | `computeinstance-e01efb17k9jbzct0m0` |
| Name / preset | `creature-forge-r1-cpu`, cpu-d3 `8vcpu-32gb` (4 physical cores) | `creature-forge-batch`, cpu-d3 `64vcpu-256gb` |
| Region / disk | eu-west1, 50 GiB network_ssd | eu-west1, 50 GiB network_ssd |
| State | **STOPPED** | **STOPPED** |
| Rate when running | about $0.27/h | about $2.11/h |
| Stopped cost | disk about $0.117/day | disk about $0.117/day |
| Infra ledger | 30.9 compute-h, $8.58 | 11.6 compute-h, $24.70 |

- **Lifecycle:** `infra/nebius/forge_cloud.py` (Nebius CLI via WSL); select the batch VM with `CF_VM=batch`. Commands:
  `status`, `start`, `extend --hours H`, `stop`, `spend`, `plan`.
  - `start` refuses when the projected spend would exceed `SPEND_CAP_USD` (currently 38.0), and sets a verified deadline.
  - `create` and `delete` need owner approval.
  - The `est_spend_usd_if_running_since_create` field in `status` is a hypothetical figure, not spend.
- **Dev loop:** `infra/nebius/forge_dev.py`: `sync --tree . --slot <s>`, `test --slot <s> py|fe|e2e|smoke|all`,
  `exec --slot <s> [--heavy] "<cmd>"`, `pull --slot <s> <path>`, `serve` / `tunnel`.
  - Studio binds to 127.0.0.1 on the VM; ufw allows only SSH.
  - **`sync` runs `git clean -fd` in the slot:** pull untracked results first (incident 2026-10-16).
  - Causal-engineer slots: `ce`, `ce2`, `ce3`, `ceh` (held-out run), `cehb` (held-out bench build, batch VM).
- **Safeguards:**
  - the guest deadman timer powers the VM off at the deadline;
  - the Windows task `CreatureForgeNebiusWatchdog` (status Ready, "interactive only", so it runs only while the PC is on
    and logged in) stops the VM through the API;
  - on-VM tmux watchers power off after a run;
  - always run an explicit API `stop` at the end of a work block. A guest power-off once left the instance RUNNING
    (incident 2026-10-15).
- **Inference:**
  - Nebius Token Factory, base URL `https://api.tokenfactory.nebius.com/v1` (`nebius.DEFAULT_BASE_URL`; HTTPS enforced).
  - Research model `nvidia/nemotron-3-super-120b-a12b`. `nvidia/Nemotron-3-Ultra-550b-a55b` was used only in S2b (it
    failed the validity gate).
  - `nebius.DEFAULT_MODEL` is the legacy Nano id; research scripts set Super explicitly.
  - Prices in `inference_ledger.PRICES` (fetched via `GET /v1/models` on 2026-10-14): Super $0.30 / M prompt and $0.90 / M
    completion tokens. An unknown model price refuses (fail closed).
- **Inference ledger:**
  - `~/dev/ledger/inference_ledger.jsonl` on the main VM (`CF_INFERENCE_LEDGER`), with reserve and settle entries.
  - A failed call is settled at worst case.
  - Local backup: `artifacts/vm/ledger_backup/inference_ledger_20261018_after_amend1.jsonl` (git-ignored). It is the last
    state; no call was made after it.
- **Secrets:**
  - `NEBIUS_API_KEY` lives only in the Windows `.env` and in `~/dev/.env` on the VM (mode 600).
  - **Never `source` the `.env` in a shell.** It has CRLF line endings, which caused the 2026-10-17 leak; the Python
    `load_env` reads it.
  - The key was rotated by the owner on 2026-10-17 at 21:02 UTC; the new key was verified on the VM (read-only check).
  - Never rotate credentials during a live run (incident 2026-10-18).
- **Reproducible run command:** the held-out run is in `docs/CAUSAL_ENGINEER.md` ("Held-out run command"). Use
  `CREATURE_FORGE_ENABLE_LIVE=1` for live calls; the `ce_eval.py` flags are listed there.

---

## 8. Budgets

### Verified ledger figures (2026-10-18)
- **Infra ledger:** **$33.28 of the $38.00 cap**: main $8.58, batch $24.70.
  - The ledger is conservative: it charges until an explicit API stop and includes disk accrual.
  - It grows about $0.23/day while both disks exist.
- **Inference ledger:** **$32.88 of the $40.00 cap**, with 4,724 settled entries against an 8,000-request cap. Breakdown:
  - successful calls $23.32 (Super $22.10, Ultra $1.22);
  - 30 legacy-format entries $0.31;
  - failed-call settlements $9.25.
    - About $7.42 of that is the 231 HTTP 401 failures of 2026-10-17, which were never sent successfully and **not
      billed**.
    - About $1.8 is other failures settled at worst case; whether they were billed is unknown.

### Real spend and real balances (not fully verifiable from here)
- **Real inference spend** lies between **$23.6** (successful calls only) and **$25.5** (all non-401 settlements). An
  earlier session reported "$24.75 real". That figure cannot be reproduced exactly from the ledger and falls inside the
  bounds; use the bounds.
- **Token Factory credit:**
  - The owner reported about **$49 remaining** on 2026-10-17, when the ledger stood at about $3.9.
  - The estimate now is **about $27–29 remaining**.
  - Only the Token Factory console is authoritative.
- **Infra credit:**
  - The owner reported about **$11 remaining** on 2026-10-17, when the infra ledger stood at $28.9 (comment on
    `SPEND_CAP_USD`).
  - The estimate now is **about $6–7 remaining**, minus disk accrual since then.
  - The Nebius CLI does not show the balance; the owner must check the billing console.
- **Historical spending (cumulative ledger readings):**
  - End of the Forge Loop (2026-10-15/16): infra about $3.9; inference about $0.55.
  - After S3 of walking recovery (2026-10-17): infra about $26; inference about $3.7.
  - Causal engineer since then: infra about $7; real inference about $20–22. Of that, the registered held-out run cost
    $2.36 and amendment 1 cost $12.39 (1,978 requests).

### Authorization: available credit is not authorized spending
- The caps (`SPEND_CAP_USD = 38.0`, inference `Caps(max_usd=40.0, max_requests=8000)`) are **ceilings**, not budgets to
  spend.
- **Standing authority (owner, 2026-10-17):** work within the existing approved budgets without exceeding them, and adjust
  caps as needed for the stated goal, keeping enough for the hackathon demonstration. Authorization must be requested
  before any experiment that would exceed the funds actually available.
- That directive's experiments are complete. The owner should confirm whether this authority carries over to a new
  research phase before the next paid run.
- **"I can add more" is not an authorization.** Ask for a top-up and approval with a cost estimate first.
- **Infra headroom** is only $4.72 under the cap, and about $6–7 of real credit is left. Keep about $2 for the demo.
- **Inference headroom under the cap** is $7.12. The $7.42 phantom settlements count against the cap, so raising the cap to
  match real credit is possible, but it needs a recorded reason.

---

## 9. Repository operations
- **Do not merge anything without the owner's explicit approval** (merge commit, never squash). Do not change repository
  visibility, rewrite history or force-push.
- **PR #18** (CI fix, `fix/ci-license-and-workflow`):
  - It makes the license test check the disclaimer by meaning, and makes the workflow run on push only for `main` and on
    pull requests, with concurrency cancellation, permissions, timeouts and caching.
  - Green on 2026-10-17. Awaiting review.
  - After it merges, PR #17 and any research PR need `main` merged in to pick up the fix.
- **PR #17** (Draft, `feature/demo-capture`; the submission PR): failing only on the `test_license` brittleness that PR #18
  fixes. **Do not touch it** without the owner.
- **CI status of `feature/causal-engineer`:**
  - This branch carries the **old** workflow, so every push runs the full CI.
  - Run 39081285902 (`8fa4bd1`):
    - Python suite, preflight and smoke PASS; vitest and build PASS;
    - one browser assertion failed: "a budget bar shows rollouts used / total" in the Recover-walking flow.
    - The same check passed on `8644e2f`, whose code differs only in ledger cap constants, so this is probably a timing
      flake of a live-progress check. It was not diagnosed.
  - Run 39088125876 (`192c000`) **never started**. GitHub reports "recent account payments have failed or your spending
    limit needs to be increased".
  - **The owner must fix GitHub billing before CI can run** for any branch or PR.
  - Also expected soon: `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19, and the Node 20 action runtimes are deprecated.
- **No PR exists for `feature/walk-recovery` or `feature/causal-engineer`.** Opening one is the owner's call. The base
  should be `main`; `feature/causal-engineer` subsumes `feature/walk-recovery`.
- **Protected research artifacts:**
  - everything listed in `experiments/FROZEN_MANIFEST.json` (279 files), guarded by `tests/test_frozen_records.py`;
  - this includes all of `experiments/causal_engineer/heldout/` (53 files), `experiments/walk_recovery/*`, `phase1`,
    `phase2a*` and `demo_trials`.
  - Living (excluded) directories: `experiments/forge_loop/`, `experiments/causal_engineer/dev/`,
    `experiments/causal_engineer/demo_records/`.
  - The registered protocols are `protocol.json` / `PROTOCOL.md` in each study, `AMENDMENT_1.md`, and the S3
    `walkrec-confirm-v1`.
- **Commit rule:** commits are authored by Mahdi, with **no AI co-author trailers** (owner rule:
  `docs/memory/DECISIONS.md`, `docs/FORGE_LOOP_CONTRACTS.md`).
- **Safe next steps:**
  - the owner fixes GitHub billing and reviews or merges PR #18;
  - then merge `main` into the research branch (or open a research PR) so CI uses the new workflow;
  - the owner decides on deleting the batch VM;
  - clean up the agent worktrees and WIP branches after a check.

---

## 10. Immediate next research priorities

### Evidence-backed opportunities
1. **Stopping and budget policy (largest measured gap).**
   - Let the scientist set a budget plan and use the stress test, plus "rollouts unused", as an explicit stopping rule, or
     require robustness spending before `conclude`.
   - Test whether this closes the 14–16 vs 23 gap.
   - First do a **free** offline analysis of the existing held-out records: stop reasons, remaining budget at `conclude`,
     and stress-test outcomes before stopping.
2. **First-repair choice.** It is right 23/40 vs exhaustive's 36/40.
   - Analyse from records which evidence the scientist had when its first repair missed (no new runs).
   - Then test "screen broadly first" prompts, or a hybrid: AI chooses the experiments, while the repair order is informed
     by the Level C ranking.
3. **Advice uptake.**
   - Present Level C advice as a measured hit rate with per-robot-type calibration.
   - Optionally make following or overriding it an explicit, justified decision.
   - Measure the uptake rate and its effect.
4. **Calibrated predictions.**
   - Use magnitude predictions with stated tolerances and feedback on calibration within the episode.
   - Score against the majority baseline (C1 failed).
5. **Learning from investigation traces** (which experiments were informative), rather than from repair outcomes only.

### Technical risks
- **The held-out set is spent.** Any confirmatory claim needs **fresh registered instances**. Unused held-out bench
  instances exist (124 kept, 40 used), but using them needs a new protocol and must avoid instances already seen.
- **Reproducibility of the memory arms (resolved 2026-10-18):**
  - The pinned memory inputs (`probe_dev.jsonl`, `pilot1..5_shard*.jsonl`) and the other git-ignored causal-engineer
    artifacts are archived after a secret scan with 0 hits.
  - There are two copies: a local folder outside the repository, and a draft release of the private repository. Both were
    verified by SHA-256.
  - Locations and the recovery procedure: `docs/ARTIFACT_ARCHIVE_2026-10-18.md`; checksums in
    `docs/archive/ce_artifacts_2026-10-18.SHA256SUMS`.
  - VM-only logs were not inventoried, because the VMs were not started.
- **Low power:** N = 40 detects only large effects (C2 p = 0.09).
- **The benchmark favours screening:** single faults with matching tools, and repairs often non-identifiable.
- **Prompt tuning:** prompts were tuned on dev instances (v2 → v2.3).
- **Money:** about $6–7 of infra credit and about $27–29 of inference credit are left, and the demo must be preserved.
- **CI** is blocked by GitHub billing; a runner image change is coming.
- **Single operator:** the Windows PC has very little free RAM. Run heavy work on the VM, and wait with on-VM watchers,
  not local background processes.

### Unresolved scientific questions
- Does closed-loop feedback improve repair (directionally yes, p = 0.09)? Answering it needs a larger fresh set.
- Is the scientist's deficit a stopping problem, a first-choice problem, or both? Would fixing stopping alone reach the
  exhaustive procedure?
- Can an LLM's physical predictions become calibrated through within-episode feedback?
- Why are accurate advice and appropriate memory verdicts not acted on, and does presentation change that?
- Does the fault bench generalise to multi-fault or non-tool-aligned failures?

---

## 11. Reproducibility map
| Item | Location |
|---|---|
| Causal held-out build spec / protocol / registration | `experiments/causal_engineer/heldout/BUILD_SPEC.md`, `PROTOCOL.md`, `protocol.json` (code commit `5ca165c`; registration commits `5ca165c`, `c4c2c87`) |
| Held-out instances (frozen) | `experiments/causal_engineer/heldout/instances/heldout_shard0..7.jsonl` (448 rows; 124 kept, 40 used) |
| Registered-run results | `experiments/causal_engineer/heldout/results/` (16 shards, `heldout_eval.sha256`, `analysis.json`, `ANALYSIS_OUTPUT.md`), `REPORT.md`; commit `42a061c` |
| Amendment 1 | `AMENDMENT_1.md` (registered `8fa4bd1`), `results_amend1/` (16 shards, `heldout_amend1.sha256`, `nonai_from_registered.jsonl`, analysis), `REPORT_AMEND1.md`; commit `db9f722` |
| Frozen manifest | `experiments/FROZEN_MANIFEST.json` (`scripts/freeze_manifest.py`), guard `tests/test_frozen_records.py` (passes locally 2026-10-18) |
| Analysis scripts | `scripts/ce_heldout_analysis.py` (+ `tests/test_ce_heldout_analysis.py`), `ce_heldout_select.py`, `ce_heldout_register.py`, `ce_analysis.py`, `ce_learn_eval.py` |
| Dev evidence | `experiments/causal_engineer/dev/` (`AUDIT_PILOT1.md`, `LEVEL_C_LOBO*.md/json`, `healthy_reference.json`, `level_c_logistic.json`); pilot raw files git-ignored under `artifacts/vm/ce*/ce/` |
| Causal-engineer tests | `tests/test_{scientist,ce_policies,fault_bench,experience_bank,repair_learner,physics_digest,causal_api,ce_export_records,ce_heldout_analysis,inference_ledger,nebius_client}.py`, `studio/src/causal/causalLogic.test.ts` |
| Walking-recovery studies | `experiments/walk_recovery/{oracle,dev_pilot,experience,mech_pilot,confirmatory}/` (protocols, results, REPORTs); scripts `walk_*` |
| Forge Loop studies | `experiments/forge_loop/{scoreboard,memory_eval,calibration,null_pilot,dev_live_records}/` |
| Key commits on `feature/causal-engineer` | `09ac73e` v2.3; `705a5b5` thinking limits; `5ca165c`/`c4c2c87` registration; `42a061c` registered results; `fc4ba6a` fail-fast; `8fa4bd1` amendment; `db9f722` amendment results; `192c000` summary |
| Narrative docs | `docs/CAUSAL_ENGINEER.md` (§0 summary, §4 execution log), `docs/WALK_RECOVERY.md`, `docs/WALK_RECOVERY_ITERATION3.md`, `docs/FORGE_LOOP.md`, `docs/memory/{DECISIONS,INCIDENTS}.md` |

**Last test evidence:**
- CI on `8fa4bd1`: full Python unittest suite, preflight and smoke PASS; frontend vitest and build PASS; browser checks 1
  FAIL, as described in §9.
- The last full VM regression on the walking branch (2026-10-17): 1,178 Python tests, frontend and build, 314 browser
  checks PASS.
- No full regression has been run since on `feature/causal-engineer`.

---

## 12. New-session instructions

### Read first, in this order
1. This file.
2. `AGENTS.md` and `CLAUDE.md`.
3. `docs/CAUSAL_ENGINEER.md` §0, then `experiments/causal_engineer/heldout/REPORT_AMEND1.md`.
4. The last 5 sections of `docs/PROJECT_STATE.md`.
5. `docs/memory/INCIDENTS.md` (the last 4 entries).

### Verify before acting
Read-only, no cost:
```
git fetch; git status -sb; git log -5 --oneline
gh pr view 17 --json state,isDraft; gh pr view 18 --json state,statusCheckRollup
.venv\Scripts\python infra\nebius\forge_cloud.py status      (and with CF_VM=batch)
.venv\Scripts\python infra\nebius\forge_cloud.py spend
```

### Do not modify
- Anything in `experiments/FROZEN_MANIFEST.json`.
- Registered protocols and amendments.
- `verdict_v1`, `WalkingCriteria` and the `full_recovery_v1` thresholds.
- Historical records and reports.
- `main`, PR #17 and its branch.
- `.env` files and credentials.

New work goes into new directories with new registrations. Never reuse the 40 held-out instances for a confirmatory claim.

### Requires owner approval
- Any merge, or changing a PR's state.
- Repository visibility.
- Deleting a VM, branch or worktree.
- Creating cloud resources.
- Any paid experiment beyond the funds actually available, or a new research phase's spend (§8).
- Raising caps beyond real credit.
- Credential changes. Never rotate during a run.
- Amendments to registered studies.
- Major scientific decisions, such as a new confirmatory design or the submission framing.

### Working rules
- Run heavy work on the VM, and stop the VM through the API after every block.
- Never source `.env` in a shell.
- No AI co-author trailers.
- Report null results as they are.
- Never attribute optimiser recoveries to Nemotron.
- Do not tune on held-out data.

---

## 13. Outdated or conflicting descriptions, resolved
| Document says | Actual (2026-10-18) |
|---|---|
| `docs/PROJECT_STATE.md` header: "Updated 2026-10-13", no scaffolding, no key | The file is an append-only log; its latest sections are current. This handoff supersedes the header |
| `docs/RESUME_CHECKPOINT.md` / `RESUME_PROMPT.md` (2026-10-15): branch `feature/forge-loop`, Draft PR #16, caps $10 / $15 | PR #16 is merged (`e58dbdf`); the work branch is `feature/causal-engineer`; caps are $38 infra and $40 / 8,000 inference. Both files are historical; they are now marked superseded |
| `docs/CAUSAL_ENGINEER.md` header: infra $26.77 of $35, inference $3.67 of $15 | $33.28 of $38; $32.88 of $40 (§8). Header annotated |
| `docs/CAUSAL_ENGINEER.md` last section: amendment 1 "pending the owner's decision" | Approved, registered (`8fa4bd1`) and complete (`db9f722`). Annotated |
| `docs/CAUSAL_ENGINEER.md` §5: actions include `observe_more` and `conclude(category, …)` | Implemented actions: `counterfactual`, `test`, `repair`, `conclude` (`scientist.ACTIONS`) |
| `docs/CAUSAL_ENGINEER.md` §6: Nemotron writes card principles; verdicts APPLIES / ADAPT / TEST-FIRST / REJECT | Principles are deterministic (the Nemotron phrasing has no caller); verdicts are `applies`, `needs_adaptation`, `test_first`, `does_not_apply` |
| `REPORT_AMEND1.md` / §0: "decision quality is not the gap" | Partly true: "eventually chose a repairing tool" is close (34 vs 38), but the first repair repairs only 23 vs 36 (§5.3). The frozen report is not edited |
| `.claude/skills/nebius-ops/SKILL.md`: infra cap $10 | `SPEND_CAP_USD = 38.0`. Skill corrected |
| PROJECT_STATE (2026-10-17 evening): "owner should rotate the key" | Rotated 2026-10-17 21:02 UTC; the new key is installed on the VM |
| Earlier reported "real inference $24.75" | Ledger-derived bounds $23.6–$25.5 (§8) |
| Memory note `budget-authorization`: inference caps $30 / 4,000 | $40 / 8,000 (2026-10-18). Note updated |
| `docs/submission/*` and README (on `main` and the branches) | They predate the walking and causal results (0 mentions). The submission framing is an owner decision |
