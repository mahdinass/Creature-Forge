# Creature Forge: roadmap reassessment (2026-10-24)

**Scope.** This document compares the specification (`docs/PROJECT_SPEC.md`: §12 G, §17, §25 DoD) with the evidence that
actually exists in the repository and branches. It then chooses the next milestone.

**Constraints:**
- the deadline is **Fri 30 Oct 18:00 Oslo** (internal: Thu 29 Oct), six days from now;
- credit is **$37.49 Nebius AI Cloud** and **$47.00 Token Factory**;
- the infra ledger is $92.97 against an internal cap of $96.

**Sources:** `docs/PROJECT_STATE.md`, `docs/HAS_SCIENTIST.md`, `docs/STAGE2_REPORT.md`, `docs/DS1_REPORT.md`,
`docs/CAUSAL_ENGINEER.md` (branch `feature/causal-engineer`), `docs/DO1_REPLICATION_REPORT.md` (`release/v1`),
`cf-experience` P0/P0.5/SV0/SV1, and `experiments/causal_engineer/dev/hdb/ARMS_*.md`.

## 1. What has been demonstrated (real MuJoCo physics, recorded evidence)

| capability (spec) | evidence | strength |
|---|---|---|
| Physical simulation, telemetry, fall detection, Studio (§6–7, §14) | Phase 0–2; V1 `v1.0.0-rc1` @ `3a740a7`; CI: 1,614 Python tests, 199 vitest, 407 browser checks | **done, verified** |
| Nemotron used at runtime through Nebius (§10, compliance) | Forge Loop, causal engineer, HaS agent; W2 demo (the Nemotron experiment choice was right where the engine's was wrong, on one recorded case) | **done**; one honest example, no aggregate win (15 vs 14 of 36, p = 0.50) |
| Failure diagnosis from physics (§9) | Multi-class identifiability on dev: the injected family is the MAP in 282/302 with all instruments (observation alone: 245) | **demonstrated (dev)** |
| Verified repair of a failing robot, honest negative cases (§11, DoD) | W3: DO-1 FULL 5/5 vs frozen 0/5 (p = 0.031, one robot, technical replicates). W4: C1 FULL vs PARTIAL; B1 PARTIAL both | **demonstrated**, narrow (NO_AI; one or two robots) |
| **Physics-grounded investigation beats equally plant-budgeted exhaustive search** (§17 "smallest claim") | Engine v5 + calibrated stop (A1c5) vs generic exhaustive (A0) on **211 fresh dev robots** (18 bases unseen by tuning, all 9 dev families): FULL **109 vs 62**, paired 61 vs 14, one-sided p < 1e-6. Better or equal in every family | **strongest effect in the programme, but dev only**: the engine, stop map and families are development artefacts. **Never confirmed on the sealed test side** |
| Reproducible baselines, disclosed limits | Registered held-out causal-engineer run (40 robots): exhaustive 23 > learned 18 > scientist + memory 16 > scientist 14 > random 12; no hypothesis supported | **done** (negative for the AI arms) |
| Statistical validity of the experience-learning inference | SV0 PASS; SV1 ADMITTED: only the refit percentile bootstrap (M2) covers θ_G ≥ 0.90 at G = 28; CR1 undercovers (0.75) | **done** (synthetic only) |

## 2. What remains theoretical or unconfirmed

1. **Experience improves subsequent decisions (§12 G; owner objective 4): not demonstrated.** Every test to date is null:
   - memory evaluation (16 Oct): no benefit;
   - causal engineer held-out: scientist + memory 16 vs scientist 14;
   - Stage 2: memory used once in 36 episodes; learned posterior A2 12 vs 14;
   - DS-1: experience 10 vs 8 (p = 0.31); updating vs frozen 7 vs 7;
   - P0: INSUFFICIENT-DATA; the CE-proxy decision contrast was null (−0.006).
   - **Diagnosis:** wherever the system has a decent in-episode physics budget, verified recovery is bound by repair search
     quality. Better identification (A2, K2) does not convert into recoveries (MKV: exact knowledge gives only 8/21). Experience
     priors act mainly on identification, so they have had nothing to improve.
2. **Transfer to held-out morphologies or mechanisms.** Tested only for the causal-engineer arms (negative) and the Stage 2
   transfer bases (same generator, dev families). The sealed held-out families have never been run: sensor latency, joint
   damping wear, leg asymmetry and compositions.
3. **Nemotron adds verified value over the engine.** Parity on dev (Stage 2: 15 vs 14; DS-1: 8 vs 8). It delegates the
   repair. Its value is so far demonstrated as process (designing experiments, registering predictions, revising hypotheses),
   not outcome.
4. **The A1c5 > A0 effect generalises beyond development.** This is the single most valuable open question. It is the
   spec's smallest scientific claim, and it is the backbone of the "investigate the physical cause, then repair" story.
5. **P0.5 (interventional-experience campaign).** SV1 shows that, at the planned G = 28, the admitted interval detects an
   informative-scenario effect (θ_G = 0.108) only 5 % of the time. The pessimistic programme cost ($40–44) exceeds the
   current credit. **Recommendation:** do not run the P0.5 confirmatory campaign before the deadline. Keep its frozen design
   and SV0/SV1 evidence for later.
6. **Full-vision items (§25.2):**
   - not started or roadmap only: sketch/text creation, RL checkpoints, Pareto optimisation, Isaac/Cosmos adapters, hosted
     scalability;
   - these stay in the roadmap and out of any "Features" list.

## 3. Value ranking for the remaining six days

| option | scientific value | competition value | P(success) | cost | verdict |
|---|---|---|---|---|---|
| **E-1: registered held-out confirmation of the engine vs exhaustive, with a diagnosis-off attribution arm** | high: confirms or refutes the programme's strongest effect on unseen mechanisms | high: the only path to a registered positive claim about the core loop before the deadline | dev effect 61:14 → high if it generalises; a null is also decisive | ≈ $15–20 infra, $0–3 inference | **chosen** |
| P0.5 campaign | medium (low power at G = 28) | low before the deadline | low (power 5–20 %) | $40+ | defer |
| New experience mechanism (warm-start, budget-scarcity prior) | potentially high | medium | unknown; needs dev work first | small | exploratory dev in parallel only (§5) |
| Stage 3 as approved (primary A3 > A1) | low (power about 16 %) | medium | low | about $65 | not now (owner deferred) |
| Submission polish (video voice-over, Devpost, public repo) | none | **essential** | high | $0 | owner-critical path; I support it |

## 4. Chosen milestone: E-1

**Claim tested** (spec §17, "smallest claim"): on robots with hidden damage drawn from mechanisms **never used in
development**, the physics-grounded investigation engine reaches verified full recovery more often than an equally
plant-budgeted generic exhaustive repair search.

**Arms.** Identical instruments, plant budget 700, same seeds, paired on the same instances:
- **A0:** the generic exhaustive procedure (frozen);
- **A1:** the engine with calibrated stopping (A1c5, frozen code);
- **K0n:** the same engine with the **nominal model only** (no diagnosis). This is an attribution arm: does investigating
  the cause matter, or only the twin-robust repair machinery?

**Hypotheses:**
- **Primary H-E1:** FULL(A1) > FULL(A0), exact one-sided McNemar, α = 0.05.
- **Secondary (Holm):** H-E2 FULL(A1) > FULL(K0n); H-E3 per-stratum descriptive (held-out families, compositions,
  severity).

**Population:**
- sealed test-side bases and families per `docs/HDB_SPEC.md` §6, a stratified sample with quotas declared before the build;
- about half of the eligible sealed instances, so a reserve remains for a future registered Stage 3 (A3 > A1).

**Inference budget:** an optional exploratory A3 arm on a declared subset, reported whatever its result. It is not part of
the confirmatory family.

**Integrity:**
- the protocol, code hashes, seeds and quotas are committed and pushed **before** the test bench is built;
- eligibility is physics-only;
- ITT: every eligible sampled instance is analysed;
- no change after registration;
- a null is reported as a null.

**Credit:**
- A1 and K0n are deterministic engine arms, credited to the engine and not to Nemotron;
- twin compute is reported separately from plant compute (spec §12 G3: match the physics experiment budget, report compute
  separately).

**Why this serves the core objective.** It is the first registered test of the loop "failure → investigation of physical
cause → bounded improvement → independent verification" on unseen mechanisms. Experience (objective 4) remains open.
§5 is the parallel dev line aimed at it.

**Owner decision needed before the test bench is built** (escalated because it spends sealed held-out data and supersedes
the deferred Stage 3 primary for this run):
- approve E-1 on part of the sealed test side, keeping a reserve for A3 > A1 later.

Preparation that touches no sealed data starts immediately: protocol, freeze, dev smoke and cost benchmark.

## 5. Parallel exploratory line (dev only, no claim): experience under scarcity

**Hypothesis to explore:** experience helps where in-episode evidence is scarce.
- Run at a reduced plant budget (e.g. 200 instead of 700), on dev instances only.
- Compare the engine with a prior learned from earlier dev episodes against the engine with its default prior. The prior
  covers mechanism family and first tool, given the observation signature.
- If a dev effect appears, it becomes a registered hypothesis **after** the deadline, on a fresh draw. It is never folded
  into E-1 post hoc.

## 6. Infrastructure (done today)

- **Auth-horizon guard** (`infra/nebius/forge_cloud.py`, commit `d8e3727`):
  - the CLI federation token is a fixed ~12 h token;
  - `start` now shortens and `extend` refuses any deadline that outlives it;
  - the watchdog stops running VMs 30 min before expiry;
  - the watchdog task now also runs on battery.

  This closes the failure mode of the 2026-10-19 and 2026-10-24 overruns whenever the laptop is awake.
- **Remaining gap:** the laptop asleep or off. The fully login-independent fix is a VM-side API stop. It needs a dedicated
  service account with a narrow compute role and an authorised key; this is new IAM, so it is **owner approval**.
  Until then, unattended runs must fit inside one token window with the laptop awake.

## 7. Submission critical path (owner actions; unchanged and urgent)

The rough cut v2 already exists (173.5 s, captions):
1. voice-over, then export;
2. YouTube upload;
3. Devpost text;
4. repository visibility and judge access;
5. PR #19 merge;
6. off-machine backup.

If E-1 confirms, a `v1.0.0-rc2` adds one honestly worded result (README, Devpost, one narration line) through a PR. If it
does not, the null is reported the same way.
