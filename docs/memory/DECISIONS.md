# Creature Forge — durable decisions

This is the Git-visible decision index. Add one dated section per consequential choice, with status (`active`, `superseded`, or `proposed`), alternatives, reason and concrete evidence. Prefer succinct entries linking to ADRs/commits instead of copying large discussions.

## 2026-10-13 — Memory architecture

- **Status:** active as repository policy; external MCP not yet connected.
- **Decision:** use `AGENTS.md` + `CLAUDE.md` + verified `PROJECT_STATE.md` for every agent; Git-tracked decisions/incidents for fallback; Basic Memory MCP as an optional semantic/linked cross-tool store.
- **Why:** memory notes must never override filesystem or tests; remote connection cannot be assumed.
- **Evidence:** `docs/MEMORY_SYSTEM.md`, `scripts/context_preflight.py`, `.claude/settings.json`.
- **Revisit if:** cross-tool authentication, retrieval quality or maintenance overhead fails evaluation.

## 2026-10-13 — Physics and AI separation

- **Status:** design decision, not implemented.
- **Decision:** MuJoCo is authoritative for physics; NVIDIA Nemotron through Nebius proposes falsifiable hypotheses and experiments; deterministic verifier adjudicates outcomes.
- **Evidence:** `docs/PROJECT_SPEC.md` sections 4–5 and 9–11.
- **Revisit if:** new backend exhibits better validated physical accuracy and comparable reproducibility.

## 2026-10-13 — Phase 0 creature and environment
- **Status:** active, implemented.
- **Decision:** planar (xz) biped with hip/knee/ankle motors, parameters bounded in `creature_forge/morphology.py` (`BipedParams`, `BOUNDS`), generated MJCF; baseline = joint PD + ankle balance feedback (`controller.py`). Dedicated `.venv` (none existed; verified by preflight and `guard_venv.py` dirs) created with `uv venv --python 3.11`, deps from `pyproject.toml` (`mujoco`, `numpy`). Tests use stdlib `unittest` (no new test dependency).
- **Why:** a biped exposes slip, saturation and tipping failures; planar keeps contact physics inspectable. Hopper deferred.
- **Evidence:** measured push-recovery frontier (3 seeds): default 8 cm foot falls at 20 N, 16 cm foot survives up to 30 N and falls at 40 N, 26 cm foot survives 40 N; torque limit (20 vs 150 N·m) and friction (0.1-0.3) did not change the outcome in that range. Foot length is the dominant lever for this disturbance.
- **Revisit if:** 3D or contact-richer morphologies replace the planar model.

## 2026-10-13 — Nebius base URL not hardcoded as fact
- **Status:** active. `scripts/nebius_check.py` default `https://api.studio.nebius.com/v1` is an **unverified assumption** from memory; confirm against current Nebius docs before the first live call. `NEBIUS_API_KEY` unset at this date, so no inference was attempted.

## 2026-10-13 — Studio architecture (Phase 0.5)
- **Status:** active, implemented on branch `feature/phase0.5-studio`.
- **Decision:** MuJoCo rollouts are recorded server-side (`run_rollout(record_poses=True)`: geom world pose + foot contact points per 200 Hz frame), converted once in Python to three.js Y-up (`render_export.py`: (x,y,z)->(x,z,-y), quaternion conjugated; unit-tested) and replayed by a React + React Three Fiber client (`studio/`). FastAPI (`creature_forge/studio/app.py`) exposes `/api/schema`, `/api/simulate`, `/api/experiments/phase0`, `/api/sketch/*` and contains no physics. One zustand clock drives all viewports (sim time and wall replay time shown separately). Bounds violations return 422 (never clipped). Sketch boundary: `creature_forge/sketch.py` compiles only the straight-leg biped template and rejects everything else with reasons.
- **Alternatives rejected:** frontend physics (violates MuJoCo authority); WASM MuJoCo in the browser (possible later for live interactivity).
- **Revisit if:** live interactive stepping or larger payloads are needed (binary frames / WebSocket).

## 2026-10-13 — Nebius endpoint and model verified (supersedes "base URL not hardcoded")
- **Status:** active. Base URL `https://api.tokenfactory.nebius.com/v1` (stated in Nebius quickstart docs and owner-verified catalog; old `api.studio.nebius.com` guess was wrong/obsolete). OpenAI-compatible `POST /chat/completions`, Bearer auth.
- **Evidence:** one live call, `scripts/nebius_connectivity_test.py`: HTTP 200, model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, 1.17 s, usage 23 prompt + 51 completion tokens for a one-word reply (reasoning tokens are billed and count toward `max_tokens`; budget for it), finish_reason `stop`. Redacted record in `artifacts/nebius/` (gitignored). Structured-output/JSON-schema support: **not yet verified**.

## 2026-10-13 — Physics Investigator trust boundary
- **Status:** active, implemented (fake-model verified; no live investigation yet).
- **Decision:** model output is limited to {claim, cited evidence paths, prediction(metric,direction), confidence, ONE body-parameter intervention}. All fields validated locally (exact keys, finite numbers, `BOUNDS`, existing evidence paths, non-noop); out-of-range is rejected, never clipped. Verdict = deterministic matched-seed MuJoCo comparison (`accepted` = prediction held AND fall rate decreased, or equal with ≥0.02 m mean-min-height gain); model confidence is never used. Every outcome (accepted, rejected, invalid, error, budget) is saved as a `Trial` JSON in `artifacts/investigations/`. Max one model request per investigation; client has no retries. Gait parameters are out of scope for interventions in v1.
- **Reasoning:** `reasoning_effort` is a per-call setting, recorded in each trial. "none" is accepted by Nebius for Nemotron 3 Nano but returned null content on a trivial prompt (2026-10-13) — do not assume it is usable or scientifically equivalent.

## 2026-10-13 - Phase 1 evaluation protocol and trust rules
- **Status:** active, implemented. Candidates from ANY proposer are judged only by `evaluation.py`: held-out seeds 200-209, pushes 15-35 N, tier rule fixed before live calls (`experiments/phase1/protocol.json`). A better secondary metric alone never counts; a push level where the candidate is worse blocks success.
- **Forensic-variant validation:** a mechanism label and >=2 distinct scalar citations under `forensics.` (not definitions) are required. Labels are recorded, never used by the verifier.
- **Baselines:** random is uninformed (seeded uniform parameter and value); heuristic prior knowledge is disclosed in `proposers.py`. Compare per-proposal success and budgets, not one model call against best-of-many.
- **History rewrite:** AI co-author trailers removed from two unpublished commits (filter-branch, trees identical, identity preserved, backup branch kept). New commits omit those trailers at the owner's request.

## 2026-10-13 - Cross-platform reproducibility policy
- **Status:** active. Phase 1 prompt hashes differ on Linux because MuJoCo float low-order bits differ (max rel 3.9e-14; no categorical or structural difference; independent of NumPy 2.4.6 vs 2.5.4).
- **Decision:** keep `protocol.json` untouched; test A re-hashes the stored frozen prompts exactly on every platform; test B regenerates evidence and compares it to the registered reference with exact categorical/structural matching and rtol 1e-9 / atol 1e-12 for floats. No platform-scoped skip, no rounding to match hashes. The `run_phase1_live.py` safeguard is unchanged. Pin `mujoco==3.15.0`, `numpy>=2.4.6,<2.6`. Details: `docs/REPRODUCIBILITY.md`.

## 2026-10-13 - Investigation Lab (Phase 1.5) design rules
- **Status:** active, implemented on `feature/phase1.5-investigation-lab`.
- **Decisions:** (1) Studio shows saved trials read-only; MuJoCo stays authoritative and the frontend computes nothing. (2) Real demo data = byte-identical copies of the 4 actual 2026-10-13 live trials in `experiments/demo_trials/` (hash manifest, `-text` attribute); no accepted trial exists and none is fabricated; the manual 16 cm foot is labelled a human reference. (3) Origin is encoded visually and in text: solid = MuJoCo-measured, dashed = model-written, dotted = self-reported confidence. (4) Replay re-runs MuJoCo from saved parameters and reports whether fresh per-seed numbers match the saved record (tolerance policy of `docs/REPRODUCIBILITY.md`); held-out recompute is a script. (5) The lab never imports the Nebius client.
- **Fix found on the way:** drei `<Html>` push label caused `removeChild` page errors on viewport unmount (pre-existing); replaced by a DOM overlay.

## 2026-10-13 - Phase 2A locomotion design rules
- **Status:** active, on `feature/phase2a-locomotion`.
- **Decisions:** (1) Forward displacement never counts as walking: hard physical gates (upright, valid alternating forward steps, chatter, flight, slip, body contact, saturation) plus a separate continuous fitness so failing candidates stay rankable. (2) Controller = compact phase clock with duty factor, debounced force-based contact estimator (shared online/offline), guarded phase sync, stance-gated torso-pitch and ankle feedback; the Phase 0 controllers are unchanged. (3) Random search and bounded DE (no polishing) at an identical 600-rollout budget, shared initial population, worker-count-independent results. (4) Pre-registration: protocol committed before optimisation; held-out seeds touched once after the selection was committed (script-enforced). (5) Reported honestly as partial (70% held-out walking vs 90% required).
- **Not decided / open:** FSM vs phase controller (no evidence yet for an FSM); larger budgets (need review).

## 2026-10-14 - Run R1 on a Nebius CPU VM (eu-west1)
- **Decision:** CPU-only `cpu-d3` 8vcpu-32gb in eu-west1 (quota 0 in eu-north1/us-central1); Nebius CLI via WSL Ubuntu; dedicated SSH key; code shipped as git bundle (no GitHub token on VM); deadman timer + Windows watchdog task for cost control; `core.autocrlf=true` on the VM to reproduce registered hash bytes. See `docs/NEBIUS_CLOUD_R1.md`.

## 2026-10-14 - R2 approved, executed; R3 prepared offline
- **R2:** local robustness around the frozen walker, arms S/I/T, 150 final seeds, 12,000-rollout cap, Tango non-inferiority (margin 5 pp) then exact McNemar in a fixed sequence, frozen training seeds and selection committed before dependent stages. Result: gate PROCEED, winner T1#101 150/150 vs incumbent 91/150, both claims confirmed, engineering criterion met; Linux-only evidence. See `experiments/phase2a_r2/REPORT.md`.
- **R3 (Nemotron):** kept separate from R2; strict proposal schema, matched-random / heuristic / no-evidence baselines, ITT accounting, no live call until the protocol and cap (~121k tokens) are approved. See `docs/R3_DESIGN.md`; schedule in `docs/MILESTONE_PLAN.md`.
- **Lesson:** a lexicographic gate-pass-count criterion with a preservation constraint worked where R1's continuous worst-k fitness did not; local search from a working controller succeeded where a global 149-point random search found nothing.

## 2026-10-14 - Studio repair, guided AI story, constrained direct-manipulation sketching (branch `feature/studio-ux-repair`)
- **Unknown `/api/*` is a JSON 404** (never the SPA's HTML); `index.html` is `no-cache`; the frontend turns non-JSON into an actionable "server is older than this page" message; `GET /api/version` identifies the running build. Launch with `scripts/start_studio.ps1`. See INCIDENTS 2026-10-14.
- **AI Investigation defaults to a guided story** over the same recorded records (no new data, no new model call). Parameter changes are derived from the *realised* normalised step the verifier applied, not from the model's request. Honesty text is part of the page: one instance, matched random edits did as well, classical optimiser produced 150/150, R3 not completed.
- **Sketch = constrained direct manipulation, not freeform.** The compiler builds only a planar two-leg biped with straight legs, flat feet, fixed torso shape. `normalize_sketch` projects near-valid drawings deterministically (translate to ground, straighten <= 0.12 m, level foot <= 0.06 m, clamp <= 0.10 m beyond a bound, lengths rounded to 1 um) and reports each change; beyond tolerance it refuses with a reason. Extra limbs/tails/heads are refused and named, never converted. Freeform anatomy needs a new morphology compiler (future work, not attempted before submission).

## 2026-10-14 - Creative redesign: journey IA, freehand sketching, sandbox bodies (branch `feature/creative-redesign`, stacked on `feature/studio-ux-repair`)
- **IA:** Create -> Simulate -> Investigate (+ Home). Legacy `?tab=` values unchanged. Technical detail sits behind disclosure (`Advanced results`, `Research notes and caveats`, `Evidence, raw replies and statistical caveats`); no scientific caveat was removed, each is still reachable and the key ones are on the main surface.
- **Sandbox is separate from science.** `morphology.BOUNDS`, `BipedParams` and every registered experiment are untouched; `tests/test_sandbox.py` pins `BOUNDS` and the default MJCF by SHA-256. `creature_forge/sandbox.py` adds `SandboxBody` (subclass: wider finite positive bounds, per-leg lengths, real initial pose), compiled by its own MJCF builder; `run_rollout` gained a no-op-for-scientific-bodies hook (`pose`, whole-body lowest point). Safety is not relaxed: finite/positive checks, structured MuJoCo compile errors, bounded duration/payload sizes, non-finite telemetry rejected.
- **Freehand interpretation is deterministic and server-side** (`creature_forge/freehand.py`): resample -> RDP simplify -> role (pen or auto; ambiguities are returned, never guessed) -> torso (mass from drawn area, 139 kg/m2 so the default torso is 5 kg), legs (knee = point of greatest bend, else halfway and flagged), feet (chord and tilt; toe is the end away from the ankle; facing left is mirrored and reported) -> body + real initial pose via MuJoCo joint angles. Findings: in this model a knee only bends *backward* (the lower leg swings forward, like a bird); a human-style forward knee is unrepresentable and says so. A knee bent < 0.1 rad the wrong way (hand wobble in a "straight" leg) is clamped and reported.
- **Guided ON/OFF are different validators, not a cosmetic toggle:** ON snaps (vertical legs <= 6 deg, level feet <= 8 deg, upright torso <= 5 deg, near-equal legs <= 15%) and validates against the scientific bounds; asymmetric legs are refused (the verified model is symmetric) with an approximation offer. OFF applies no snapping, validates against sandbox bounds, labels "questionable but buildable" creatures and simulates them as drawn. An approximation is only ever simulated after an explicit consent checkbox, with before/after.
- **No fake AI claims:** the recorded Nemotron investigation was run on the standard walking robot; the UI says so on every drawn-creature result and offers the link only as exploration.

## 2026-10-14 - Forge Loop (Draw -> Challenge -> AI Redesign -> Verify -> Evolve), M0 (branch `feature/forge-loop`)
- **Architecture:** one NVIDIA model with a structured reply contract + a deterministic executor (validation, MuJoCo, optional controller adaptation, verdict); no LLM multi-agent swarm. Binding interfaces: `docs/FORGE_LOOP_CONTRACTS.md`. New behaviour only in new modules; pinned modules and `experiments/**` (except `experiments/forge_loop/`) are read-only, guarded by `tests/test_frozen_records.py` (105 git blob ids, line-ending independent).
- **Execution topology:** code is edited on Windows (Claude Code + in-process Sonnet/Haiku subagents in git worktrees); every test, build, browser flow, MuJoCo batch and live model call runs on the Nebius VM via `infra/nebius/forge_dev.py` (temp-index snapshot of the worktree pushed to a bare repo on the VM, per-slot checkout with `core.autocrlf=false` and its own venv; heavy commands serialized by a VM-wide lock). No Claude credentials and no GitHub credentials on the VM. Studio for demos runs on the VM bound to 127.0.0.1, reached through an SSH tunnel.
- **Budgets:** infra spend ledger `infra/nebius/spend_ledger.jsonl` (git-ignored) with a $10 cap enforced by `forge_cloud.py start/extend`; Forge inference ledger on the VM (`~/dev/ledger/inference_ledger.jsonl`) capped at $15 / 1,500 requests, separate from the frozen R3 41/300k cap.
- **Model choice (calibration, not a quality claim):** `nvidia/nemotron-3-super-120b-a12b`, thinking disabled (`chat_template_kwargs.enable_thinking=false`), strict `json_schema` whose enums list the hypothesis ids, editable params and every citable evidence path; max_tokens 8k. Optional deep mode: Nemotron-3-Ultra-550B, reasoning low, max 24k (valid but 28-61 s and up to 14.5k completion tokens). Evidence: `experiments/forge_loop/calibration/REPORT.md` (v1 0/12 valid because of contract defects; v2 9/12 + 6/6).
- **Physics decisions from the plan red-team (measured):** stand/push use `GaitParams()` defaults with the drawn pose only as the start (targeting a bent-knee drawn pose made harmless drawings fall < 1 s); failure rules after a 0.3 s settle window; push score = critical force by bisection (binary push outcomes flip in blocks, so McNemar over seeds would be meaningless); walk starts neutral by default; normalised edit space is log-scale for positive physical parameters.
- **Git:** PR #14 and #15 merged into main with merge commits after a full VM regression and green CI (a fixed-delay race in `freehand-flow.mjs` was replaced by a condition wait). Owner authorship, no AI co-author trailers.

## 2026-10-15 - Forge Loop verification and AI protocol decisions (branch `feature/forge-loop`)
- **verdict_v1 frozen after the A/A null pilot:** paired sign test + minimum effect (push 3 N and 10 %, stand 0.5 s, walk 0.5 m); validation conditions varied for push/walk; per-kind seed sizes (push 6/12, stand 8/16, walk 12/24). Because ~15 % of random push edits verify, an AI verdict is never shown alone: the arena always validates the selected AI arm's own matched-random twin on the same held-out seeds.
- **Push measured at 0.625 N in investigations** (7 bisection steps for every arm): a real +2.5 N effect was a tie at 2.5 N.
- **Evidence and prompt facts, not hints:** foot heel/toe extents from the compiled model; the acceptance rule; per-probe CONFIRMED/REFUTED with the method rule for refuted mechanisms (added after a live run proposed a mechanism its own probe had refuted).
- **Loop:** patience 2 (falsified proposals become history), max 8 model calls, never auto-accepts; rounds 2+ evaluate a hypothetical parent and cannot be accepted until the parent is.
- **Claims:** only the pre-registered scoreboard supports a comparison claim (AI 6/12 vs twin 1/12, p = 0.031, push-dominated, small); development live records are worked cases.

## 2026-10-16 - Engineering memory: no measured benefit; stays off by default
- `forge-memory-eval-v1` (12 pairs, registered before running): memory 6/12 vs no memory 7/12 verified, McNemar p = 0.773; the
  model never cited a lesson (0/12) although lessons were in the prompt and in the citation enum. Decision: memory remains an
  opt-in experimental feature (API `memory=false` default, `CF_MEMORY` off); submission text may mention it only as tried
  with a null result. Any further memory work needs a different design (e.g. past edits offered as arena candidates) and a
  new registration; the v1 protocol, bank and records are frozen.
- Interrupted evaluations are paused only at pair boundaries and resumed with `--resume` (never rerun a recorded pair); the
  driver for long runs is launched in a remote `tmux` session so it survives the local machine disconnecting.

## 2026-10-16 Walking recovery: G1 = PROCEED (M1, development data)
- M1 (`experiments/walk_recovery/oracle/REPORT_M1.md`): joint body+controller CMA with the new foot-placement controller (17-D, `phasegait_fp.py`) fully recovers 6/12 dev creatures at 8k rollouts (ctrl15 1/12, ctrl17 5/12, joint15 4/12); union 8/12. Pre-declared G1 rule (>= 50%) met exactly -> proceed to the AI-director stage.
- Decisions for M2: every method uses the 17-D family with optional 4-parameter body co-design; final candidates are selected on held-out screening seeds (train-validation gap +0.21 median; 8k worse than 4k); training on 8 seeds under the validation-variation preset (H7: 3 nominal seeds generalise worse); similarity transfer dropped as a fix (never helped). R* chosen on the method pilot by the plan's 25-60% rule.
- Not claimed: impossibility for the 4 unrecovered creatures (walking 0.62-0.96, "not within 8k"); anything about Nemotron (no model calls in M1).

## 2026-10-17 Walking recovery: confirmatory result and what the project claims
- S3 (frozen walkrec-confirm-v1 + pre-data amendment 1; `experiments/walk_recovery/confirmatory/REPORT.md`): equal total budget 2,000, 48 fresh failing robots: FIX 19, CMA-joint 11, RAND 11, ai_v2 9, CMA-ctrl 8 full recoveries. Primary ai_v2 > FIX NOT supported (4 vs 14, p = 0.996).
- Claim: the classical procedure (foot-placement controller + body co-design + diagnostic subspace probes + verdict-aware selection) makes 40% of genuinely failing never-seen robots walk under the strict criterion. Not claimed: AI decision value. Summary: `docs/WALK_RECOVERY.md`.
- Development negatives kept: S2/S2b director, L2 learned experience (G3 FAIL), S4a control-law invention and closed loop (G4 FAIL).

## 2026-10-18 Phase 3: Hypothesis-as-Simulation scientist on a hidden-damage bench (owner-approved plan, revision 2)
- **Plan of record:** `docs/HAS_PLAN_2026-10-18.md`; living spec and log: `docs/HAS_SCIENTIST.md`; branch `feature/has-scientist`.
- **Architecture:**
  - Nemotron writes executable deviation hypotheses (a generic DSL), experiments and repair strategies.
  - A deterministic engine weighs the hypotheses by paired same-seed twin simulation, chooses experiments by EIG, runs
    posterior-robust repair, and stops on a dev-validated evidence→`full_recovery_v1` mapping.
- **Benchmark integrity:**
  - The agent sees the nominal design. The plant adds a hidden deviation and a reality gap.
  - Eligibility is physics-only. Oracle R/U and ambiguity are labels, never filters.
  - An identifiability study runs before any comparative run. Families are frozen before comparative dev runs.
- **Hypotheses:**
  - Primary, fixed in every protocol variant: FULL(A3 HaS) > FULL(A1 engine-only), one-sided exact McNemar.
  - Separate confirmatory C-MKV: K1 (true mechanism structure) > K0 (none).
  - Variants: P-main / P-reduced (if Tier B slips) / P-fallback.
- **Attribution:** arms A0/A1/A1f/A2/A3h/A3hx/A3/A4/A5, plus deterministic replay. Nemotron's predictive distributions are
  compared with the engine-only posterior predictive.
- **Spending:** staged. Stage 1 approved: infra $35 (cap 38 → 72) and inference ≤ $5 within the $40 cap. Real credit on
  2026-10-18 was Cloud $66, Token Factory $52. Later stages need owner approval with advance notice.
- **Elicit:** API access was denied; no Elicit result is used anywhere.


## 2026-10-25 — R0 capability registration before learning (isolated research)

- **Status:** active registration; physical execution pending current-credit verification. Owner authorized the bounded run, so no additional run approval is needed.
- **Decision:** six conditions (single, standardized sequential, joint × frozen, byte-exact DO-1); 12 historically failed dev cases and six controls, all distinct bases; three technical replicates; exactly 3,000 policy rollouts including selection. Eight predeclared physically motivated pairs, original-relative bounds, unchanged verifier, opaque policy inputs, fresh role-separated seeds.
- **Reason:** existing tools are parameter groups and the engine already chains edits; coordinate optimization and objective alignment must be separated from additional search budget. Sequential is a plant-only standardized comparator, not the full diagnosis/twin engine. Equal rollout counts do not remove portfolio/dimension/overhead differences. No Nemotron learning or transfer claim follows from R0 alone.
- **Evidence:** `docs/R0_REPAIRABILITY_PROTOCOL.md`, `scripts/r0_experiment.py`, `creature_forge/r0_repair.py`, `experiments/causal_engineer/dev/repair_strategy_r0/protocol.json`, `tests/test_r0.py`. Gate, cluster analysis, source and case hashes frozen before any physical R0 outcome.
- **Operational boundary:** no test/reserve data, release/PR #20/E-2R work or global manifest repair. $35 and ten campaign hours are independent of current credit. Missing balance is a blocker; do not infer it from a historical balance or local ledger. Both VMs STOPPED; no R0 compute started. Real remote engineering gates remain unverified.
- **Next:** establish current credit, prove actual SA self-stop and physics equivalence, measure full-study fit with 25% margin, then execute all 324 units. No selective unfavorable reruns or silent sample reduction. Basic Memory unavailable; this tracked decision has not been synced remotely.

## 2026-10-25 — R0 failed its frozen development advancement gate

- **Decision:** stop advancement. All 324 units are complete/valid; do not substitute joint/frozen after seeing its higher total, alter thresholds or proceed to R1. No Nemotron-learning/transfer conclusion exists.
- **Evidence:** source `d29cdce`, R0 `EXECUTION_REPORT.md`, `results/analysis.json`, unit hashes/CSV and shutdown receipts. Joint/DO-1 failed-cohort FULL 16/36 vs 12/36 for both restricted arms; primary +11.1 pp, descriptive 95% [-5.6,+27.8], exploratory p=.40625. Gate: two rescues/two families, net zero vs per-base best restricted, three control regressions, zero errors.
- **Interpretation:** some coordinated capability exists on selected bases, but it did not meet the required repeatability/net benefit/control protection. DO-1 has mixed effects. Search failure is not physical impossibility; investigate allocation/initialization and selection-versus-verification mismatch under a separately authorized prospective study before pursuing strategy learning.
- **Operations:** 84 real-VM tests and six exact serial/pooled smoke comparisons passed; main source/physics/protocol frozen. Raw SHA-256 `6dcda839b60a401831a46efd760b2702e65e42fda65e8391e87d7018e8520806`; 337 files and 324 units audited. Both VMs STOPPED; conservative additional $10.349/4.877 paid batch hours, not an invoice. No release, sealed, E-2R or R1 work.
- **Sync verified:** results commit `2adff9e6e0eb8dbe73f2acbe4aa828f4996efc4e` is on origin; Notion proposal has one appended completed-result section with history preserved. Basic Memory `creature-forge/research/r0-completed-development-study-frozen-advancement-gate-failed-2026-10-25` read back with checksum `0ba9d63a4ae59dbfb027dcf972b50bcb61175f2aa05b16f82154333008a8505a`. Git/raw evidence remains authoritative.

## 2026-10-25 — EM-1 G0 NO-GO: mismatch is not identified repair benefit

- **Verdict:** EM-1 NOT EVALUABLE; NO-GO for further learner/online implementation with current evidence. G0 physical pairing completed, but decision-relevant transfer is not established. Do not describe this as a failed fitted learner, a causal learning null or proof correction cannot help.
- **Evidence:** source `f70549d`, 804 exact interventions/324 historical episodes/30 independent bases/nine dev families, 11,632 twin responses. Mean observed−predicted robustness walking +5.18pp, descriptive cluster95[1.58,8.97]. Actual B0 already selects an observed walking maximizer in every candidate set; 480 alternative FULL labels are missing. Raw audit ranker is not B0/B1 and its86 changed FULL outcomes are unknown.
- **Decision:** stop at the mission's identifiability gate rather than fit tool success from verifier labels or call better numerical calibration improved repair. No B1/B2/B3, LOBO/LOFO/prequential learner, applicability/negative-transfer or Nemotron effect was tested. No fresh prospective or sealed data work. A valid follow-up needs pre-observation paired forecasts/interventions, rich plant response and comparable FULL support, then prospective grouped power/registration and equal-resource controls.
- **Preservation:** full archive SHA-256 `dbfc677101a6430ce7fa829d0a3e22ac07697f24b90fae3b9ad5db6317b14236`, 818 files verified, raw disk/local archives and previous negative studies retained. Original Python3.12 repeat exact; Python3.11 last-bit float difference max1.77636e-15 disclosed. Both VMs STOPPED; conservative additional$1.097/0.517paid hours, TF$0. Reports `docs/EM1_RESULTS.md`, `EM1_FEASIBILITY.md`, `EM1_DECISION.md`; dedicated evidence/manifests under dev/em1.
- **Sync verified:** results `536c32d2e361d3402b4a109925f006f8ebfc3340` pushed; Notion proposal contains one appended EM-1 completed section with history preserved. Basic Memory `creature-forge/research/em-1-g0-audit-physics-mismatch-measured-repair-benefit-not-identifiable-no-go-2026-10-25` readback checksum `7adf4c272c6e70f6a685be6b41c1e394fdfc1a962975bffb13b4e5f196772cb6`; primary raw/Git evidence remains authoritative.

## 2026-10-25 — DI-1 opportunity pilot NOT EVALUABLE / NO-GO

- **Decision:** stop after complete engineering evidence and prospective resource audit; do not implement a learning agent or run an underpowered main. Eight frozen new local morphology attempts yielded five eligible independent bases. V1 original/raw/random3/5 FULL each; uniformly amended stop-or-probe pilot original3/5, raw3/5, random4/5. Eleven distinct final designs, not eleven independent bases. Same bases across versions/repeats count once.
- **Evidence:** base003 random floor probe plus standard repair reached independent FULL on original fault/conditions at700plant/2800twin caps; raw reached PARTIAL. Random worsened base000 from PARTIAL to NONE. One useful allocation path does not establish an isolated probe effect, multiple-base transfer, predecision prediction or Nemotron learning. Raw versus random−20pp, descriptive whole-base95[−60,0]; opportunity reference95[0.5%,71.6%]; raw loss upper95 52.2%. Fixed strata/exclusions prevent confirmatory population interpretations.
- **Feasibility:** unchanged10pp useful gain; conservative paired planningN768 for both contrasts. Full-cap three-path forecast43.78additionalhours/$92.69 plus already spent work exceeds6h/$12 authorization. This is a working-model design forecast, not a universal minimum or a null learning result. Zero prospective evaluation bases, no changed thresholds/subgroup, sealed data or R1.
- **Validation/operations:** five baseline equivalences plus default-repeat proof; all8attempts uniformly replayed384jobs, retainedfailed64overlap exact except timing;8guards; native exact analysis repeat;200archive entries/hash checks; no policy/FULL audit reruns. Both VMs API STOPPED22:36:47UTC; conservative additional$4.124/1.943paidbatchhours, actualTF$0. Reports `docs/DI1_RESULTS.md`, `DI1_DECISION.md`; small evidence in dev/di1/results and raw ignored archives/stopped persistent disk.
- **Next scientific question:** separately register whether observable misfit/early stopping predicts useful charged investigation on disjoint broader training/evaluation bases, with random/shuffled control, original FULL and adequate base-level power. Establish a defensible efficient measurement design first; do not fit an always-floor policy or hindsight entropy threshold from one rescue. No next study is initiated.
- **Sync verified:** results `2c4c40966a7c5fce574fafed922c34a9fe5f88f6` pushed and remote ref matched; 32 report/small-evidence checksums and three source snapshots verified. Notion proposal has exactly one completed DI-1 section with gate/commit and prior history preserved. Basic Memory `creature-forge/research/di-1-opportunity-pilot-not-evaluable-no-go-2026-10-25` readback checksum `934311ab70080fa5731e983fee4aa812536ef7e79ce025b465d9b38b3efdea35`. This completed sync supersedes the earlier running-pilot snapshot; primary evidence remains in Git/raw archives.


## 2026-10-26 — VEL-1: verification-risk target exists; incremental experience remains insufficient

- **Verdict:** INSUFFICIENT EVIDENCE; do not implement/deploy a full experience-guided risk system or initiate another paid/sealed experiment. This differs from NO-GO for no practical headroom: there is a measurable warning target and some grouped prediction signal, while relevant memory/action benefit remains unidentified.
- **Target/timing:** selected robust16>=15 fixed before fitting from existing rule. Primary115 apparent submissions/17 physical base groups,27 later non-FULL on14 bases,88 FULL. Future validation23/24 is forbidden as a predictor/apparent-success definition. Existing charged20s stress and learned stopping map are already verification-aware; novelty must be incremental and tested, not attributed to a Nemotron label.
- **Evidence:** plan63df2c1, source8c65b44, `docs/VEL1_DATA_AUDIT.md`, `VEL1_FEASIBILITY_RESULTS.md`, `VEL1_DECISION.md`; separate RL-1/R0/DI-1 inventories preserve overlap, duplicate designs, selective FULL labels and incompatible budgets. Old stop-map training12 bases are disjoint from primary18 by nominal body hash. Compressed v5 verifier reasons give requirement labels but no independent repeated-panel reliability.
- **Prediction:** V1 physical/state Brier.17687 vs robustness-only.19741; paired gain.02054 with95[-.00393,.04460]. Relevant residual memory.17720 vs shuffled mean.17567; V2 gain overV1-.00033[-.02187,.01918], family-blocked-.00914[-.03010,.00845]. No incremental history benefit demonstrated; several bases/families and false-alarm behavior worsen. Context-matched prevalence.19025 is an explicitly post-fit stronger trivial diagnostic, not a selected positive method. No feature/threshold/hyperparameter changes for GO.
- **Interpretation:** statistical prediction from past labels is learning, but the tested additional memory mechanism does not beat calibration/control; external memory is not Nemotron weight training. Existing deterministic verification already governs FULL. Abstention changes coverage/claims, not physical recovery. Missing comparable warning-action counterfactual outcomes prevent a FULL improvement claim.
- **Repro/resources:**12 guards,324 historical seed routes/358 charged stress entries,324 R0+30 DI-1 source checks, exact local analysis/stdout repeat and fold-model equality. Both VMs API STOPPED26October00:39:57Oslo; unchanged compute counters,0new Cloudcompute/0TF. Local ledger+$0.003 existing storage, not invoice/currentcredit. No further paid work.
- **Next:** separately authorized repeated verifier panels and broader disjoint, richly logged candidate/action evidence before a new powered risk/experience or equal-budget recovery design. Small diagnostic proposals do not certify transfer; illustrative614-821-base Brier planning is not a validated requirement or FULL power. No next study initiated; primary-source literature positioning avoids a generic monitoring/LLM novelty claim.

- **Sync verified:** results `1d7e3e0af4d47262b523cff7305c3f43d800e1ee` pushed and remote ref matched.27 report/evidence hashes match staged/working bytes, plan/source hashes checked. Notion has one completed VEL-1 INSUFFICIENT EVIDENCE section with commit and earlier history preserved. Basic Memory `creature-forge/research/vel-1-feasibility-insufficient-evidence-2026-10-26` readback checksum `93c6aa38513ac3d4d124f40be220038104c6b6daed6ae9814ad32927cf702422`. No next experiment or full learner is initiated.


## 2026-10-26 - VEL-2 Stage A preregistration

Owner authorized $6 additional Cloud / $0 Token Factory; fresh available Cloud credit $21.34. Isolated codex/verification-reliability-vel2 from 8f3c621. Frozen outcome-blind one-candidate/base R0 panel:15 known development lineages, two new full-verifier panels each,1,440 unique disjoint seeds, unchanged full_recovery_v1, max2,880 equivalents. Gate:12/15 three-panel FULL agreements,85% pairwise,80% validation requirement agreement,3 persistent successes/failures. Stage B conditional on reliability AND full30 genuinely new lineages fitting budget with margin; no partial substitute. Eight guards pass in existing local environment. Both VMs initially API STOPPED; watchdog Ready. Protocol docs/VEL2_PROTOCOL.md; frozen inputs/source hashes experiments/causal_engineer/dev/vel2/. Next: commit/push preregistration, bounded native real-VM verification, independent audit and final three-way decision. No new outcomes yet.


## 2026-10-26 - VEL-2 completed: NO-GO for stable single-panel FULL-label prerequisite

Preregistered/pushed e04d3ecc1d6ee56e593eac8aaab0ddf7648f060c before outcomes.15 known R0 lineages, zero newly generated lineages;30 new unchanged full_verifier panels,1,440 new disjoint seeds,2,016 response rows,2,592 equivalents,182.138s physics. No optimizer/learner/Nemotron calls. All panels completed,0simulator errors.

Frozen gate FAILED:9/15 all-three FULL agreement (required12),33/45 pairwise73.33% (required85%),7persistent FULL and2persistent non-FULL (required3 each). Improvement45/45agreement, validation walking37/45; onlyone improvement-failure base. Six label flips:3validation-walking,2confirmation-walking,1contact. Stable fraction Wilson reference95[35.75%,80.18%], selected15known bases not IID new-robot inference. Cannot extrapolate this to VEL-1's predominant improvement failure. Stage B correctly not entered; broad H-VEL2 prediction/history/action claims remain insufficient evidence, not disproved. No shifted gate/stable-only cohort or automatic follow-up.

Eight guards pass local+VM;107source hashes pinned; independent audit replays all verdict/confirmation calculations and frozen gate;43native manifest entries verified; native analysis repeat and local analysis byte-exact. Full native archive228,957bytes SHA aac3a50a713da2615a9798743ae63fe49a71ce02eb7d195c61f9033eaa9f5d20; complete small portable arrays/receipts in experiments/causal_engineer/dev/vel2/results/. Allfive required docs exist:VEL2_PROTOCOL/REPEATABILITY/DATA_AUDIT/RESULTS/DECISION. Prior scientific code/frozen study paths unchanged vs8f3c621.

Initial root service ownership error exit128 occurred before physics; native archived/API-stopped; identical source relaunched asforge. Error504-byte archive/journal preserved. Multiprocessing semaphore-cleanup warnings retained; root cause unresolved, no missing/ERROR seed and native exit0. No warning-free-runtime claim.

Both VMs API STOPPED00:22:10UTC, reconfirmed00:23:56UTC /01:23:56Oslo. Initial/final local ledgers122.985->123.324:conservative additionalCloud$0.339, batch+0.160h/mainunchanged, TokenFactory$0/0calls. Notinvoice/currentcredit; local spend interval closed at retainedAPIstop observation. Original ownercredit$21.34, authorizedcap$6; no morepaidwork. Nextonlyseparatelyauthorized requirement-specific repeat-panel probability study with adequate failure support and predecision improvement measurements; no deploy/R1/sealed/release changes. Documentation sync pending verified readback.


- **VEL-2 results and documentation sync verified:** results commit4ce8a6fb16dc3aa973517edbe4f767ac2159c622 pushed; remote branch refmatched. All74 report/input/output/source hashes matched working and staged bytes; full107 frozen scientific source hashes matched. Working source-hash JSON newline conversion was aligned to exact preregistered Git bytes with unchanged semantic contents; scientific freeze unchanged. Notion researchpage4035d357-b5ad-813e-84d4-de5fd8928f41 readback has exactlyone VEL-2 NO-GO stable-label section, correctresultcommit, broad-H-VEL2 insufficient-evidence caveat and earlierVEL-1 history; lastedit2026-10-26T00:31:06.134Z. BasicMemory creature-forge note creature-forge/research/vel-2-repeatability-no-go-for-stable-labels-2026-10-26 readback matchesverdict/scope/commit, checksum1889f429f028905b81e0213e2754f291ef7e9ce40dcab100e01d9526e9788ea6. Bothsyncs verified. Reproduction from committed native evidence independentlypassed. No furtherphysics/modelcalls/studies scheduled; bothVMs remainSTOPPED atlastAPIcheck.


## 2026-10-26 — H1 exact missing-counterfactual prerequisite

Recovered Stage0 confirms 320 missing R0 candidate/condition identities on18 historical bases. Freeze exact alternatives and original matched development conditions before outcomes; preserve full_recovery_v1 and sealed boundaries. StageA advances only with complete error-free outcomes, >=3 missed-FULL bases and >=5pp base-equal oracle headroom. This measures the R0 finalist selector opportunity, not production A1 or historical-experience benefit. Source: `docs/H1_PROTOCOL.md`, `experiments/causal_engineer/dev/h1/`. No learner unless independent reliability, support, power and prospective gates justify it.


## 2026-10-26 — H1 bounded investigation stops at B decision-value gate

Available exact finalist opportunity is established (A19misses/9bases; Bpersistentmisses4bases), but frozen legal physical rules fail useful independent decision-value screen. Best+0.617pp95[-0.309,+1.698], not5pp. NOT EVALUABLE for experience-learning recovery; no learner/C/D or Nemotron claim.18historical bases do not provide powered independent prospective evidence; conditional confirmation remains missing. Preserve negative/insufficient-evidence result, all raw outcomes and current production behavior. Evidence: docs/H1_RESULTS.md, docs/H1_DECISION.md, experiments/causal_engineer/dev/h1/results/independent_stdlib.json. New paid studies need separate justified registration and authorization.

- H1 final evidence commit8ed1ead41196d76da73390c96ed20fa6c8d5979a and draftPR22 published. BasicMemory and existing Notionresearchpage readbacks match finalsignal/counts/commit; verifiedchecksums and timestamps in `experiments/causal_engineer/dev/h1/results/sync_receipt.json`. No merger or further paid stage authorized by this closeout.
