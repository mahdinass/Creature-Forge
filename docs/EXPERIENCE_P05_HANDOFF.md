# Experience learning P0.5: handoff for a new Claude Code session

**Prepared:** 2026-10-23 (A0 documentation-only commit).
**Read first:**
1. this file;
2. `docs/plans/EXPERIENCE_P05_PROTOCOL.md` (the current rules);
3. `docs/EXPERIENCE_P0_REPORT.md` and `docs/EXPERIENCE_P0_HANDOFF.md` (the P0 evidence).

**Start in Plan mode.** Nothing in this file authorises compute, physics, spend or a new phase.

## 1. Research objective

Determine whether **intervention-informed experience** (memory of how other robots responded to standardised diagnostic
interventions) gives a **verifiable, decision-relevant repair benefit on unseen robot bases**. Better prediction of what the
old policy chose does not count.
- **Outcome:** FULL_VERIFIED (`full_recovery_v1`) only.
- **Comparison:** against no-memory and observation-only baselines.
- **Unit of inference:** independent bases.

## 2. Current evidence

| item | status |
|---|---|
| **P0 (offline identifiability audit)** | **INSUFFICIENT-DATA.** The historical HDB records identify no FULL-verified tool effect: one assigned-tool instance (TA-1 L1), with no outcome difference. Policy-chosen outcomes are missing not at random. On the only adequate (proxy) tier, the pre-declared interventional-vs-observational decision contrast was null (−0.006, 90 % CI [−0.052, 0.034]). The auditor conditionally accepted P0 as an identifiability audit; the decision-relevant hypothesis is **not validated**. |
| P0.5 | Design only. The protocol is consolidated and nothing has been run. |
| Memory transfer | **No evidence yet establishes decision-relevant memory transfer.** |

## 3. Exact refs and locations

| what | where |
|---|---|
| V2 branch | `feature/experience-learning` = `e3caf8121da84523c36449e353a84bd05977ea9a` (GitHub identity independently verified 2026-10-23). Worktree: `cf-experience`, beside the main checkout `Creature-Forge`. |
| Frozen V1 (never modify) | tag `v1.0.0-rc1` (object `a0371946…`) → `3a740a74af4bdcafbc0b3dd7a012bc78d0fc0322`; branch `release/v1`. `main` = `e58dbdf…`. |
| P0 code and outputs | `creature_forge/experience_audit.py`, `creature_forge/experience_p0.py`, `scripts/exp_p0_audit.py`, `scripts/exp_p0_evidence.py`, `tests/test_experience_audit.py`, `experiments/causal_engineer/dev/experience_p0/` (evidence, provenance, `FILE_INDEX.sha256`) |
| P0.5 protocol | `docs/plans/EXPERIENCE_P05_PROTOCOL.md` |
| P0.5 archive | `experiments/causal_engineer/dev/experience_p05/design_archive/`: 33 files, 32 byte-identical to the delivered sources and 1 sanitised (B12). `SHA256SUMS` holds the published hashes; `PROVENANCE.tsv` holds source vs published hashes. EOL conversion is disabled in `.gitattributes`. |
| A0 calculations | `experience_p05/a0_cost_model/` (cost and precision) and `experience_p05/a0_review/` (P05-SV1 admission-rule resolution) |
| Raw historical records | git-ignored `..\Creature-Forge\artifacts\vm` (`<VM_ROOT>`). Every file's sha256 is in `experience_p0/evidence/raw_source_provenance.csv`. |
| Notion | Project HQ `https://app.notion.com/p/3fe5d357b5ad812186d1fe1ded3757fc`; V2 journal (P0.5 owner decisions) `https://app.notion.com/p/4025d357b5ad8144b231e1fbcfa5c41c` |
| Older context | `docs/PROJECT_STATE.md`, `docs/memory/DECISIONS.md`, `docs/memory/INCIDENTS.md`, `docs/plans/EXPERIENCE_LEARNING_PLAN.md` (P0 plan; P0.5 now points here) |

## 4. Owner planning settings (2026-10-23; not authorisations)

| setting | value |
|---|---|
| D1 | minimum meaningful effect m = **0.10** FULL probability |
| D2 | **P-B** (hdb-v1, T1 + T3), **28 confirmatory bases** |
| D7′ | pilot = **4 T1-panel + 2 T3** bases, excluded from confirmatory work |
| D3 | **B = 300**, **8 train seeds** |
| D5 | **3 instances per base**, **2 severity bins** |

**Balances** (owner-reported, unverified): Nebius VM **$40.04**, Token Factory **$47.00**.
- They are separate pools. **They are not spending authority.**
- The existing infrastructure cap is $96, with a ledger of $89.405, so **$6.595** remains until the owner decides A10.

## 5. Verified versus Claude-reported

| claim | status |
|---|---|
| GitHub `feature/experience-learning` = `e3caf81` | **independently verified** (owner, GitHub compare, 2026-10-23) |
| DS-1 cohort counts 947 / 231 / 194 / 70 / 21 / 27 / 18 / 2 / 0 | **independently reproduced** (auditor) |
| Revision-2 arithmetic: 25 tests pass; G = 24 synthetic inflation +0.0686 / 2.25 / coverage 0.662 | **independently reproduced** (auditor); synthetic, not a Creature Forge property |
| Minimum repair budgets 104 / 152 / 176 / 200; achieved ICC 0.096 / 0.188 | **independently found** (auditor); reproduced by Claude |
| Revision-2.1 arithmetic; amendment-2.2 permutation mathematics, population arithmetic, sample-size and Stage-0 structure | **accepted by the auditor** subject to erratum 2.2a |
| Amendment 2.2 / erratum 2.2a tests (12) and the 52-test pass from the archive copy | Claude-reported (run 2026-10-23, read-only) |
| Archive provenance: 32 files byte-identical to source; 1 sanitised (only line 11 changed); published hashes verified | Claude-reported (`sha256sum -c SHA256SUMS`: 0 failures; source hashes in `PROVENANCE.tsv` re-checked against the scratchpad) |
| A0 cost and precision model | Claude-reported arithmetic; every input is [ASSUMP] |
| P0 internal checks (byte-identical re-run, evidence export fail-closed) | Claude-reported; published for audit |
| **No physics, calibration, P05-SV0/SV1 or G = 46 computation has been run for P0.5** | fact. **G = 46 is NOT COMPUTED.** |

## 6. Execution boundaries (A0–A11; none approved)

The dependency table and blocker map are in protocol §12. In short:
- **A0:** commit the documentation and archive (pending review).
- **A1–A5:** design gates. **A5 includes running P05-SV0/SV1**, which is offline compute with its own approval.
- **A6:** harness implementation, with no physics.
- **A7:** local Stage 0b physics.
- **A8:** Stage E.
- **A9:** pilot.
- **A10:** cap.
- **A11:** campaign.

**Each needs explicit owner approval. Nothing auto-advances.**

**Never:**
- touch V1 or the sealed or held-out data;
- glob archive directories, or open `walkers_all.jsonl` (2026-10-22 incident);
- call `hdb_bench.load_bases`;
- use paid inference or Nebius without approval.

## 7. Remaining blockers and limitations

**Blockers B1–B11 and B13** (protocol §12.2; B12 resolved by sanitisation):
- δ_large;
- severity-bin definition;
- pilot instances per base;
- the eligibility-shortfall policy;
- the seed namespace;
- the confirmation stage;
- the analysis runner;
- the plant-aware `cma_fn`;
- the bounds-screen compile question;
- the SV compute caps;
- the cap decision;
- the reconciliation of E3 with D7′.

**Limitations that must stay in every report** (protocol §11):
1. A 10-point benefit is likely below reliable detection with about 28 bases. Power at δ = 0.10 is about 0.11–0.70 across the assumption grid (0.16–0.59 at ρ = 0.3, q ≤ 0.42) [ASSUMP].
2. With no validated inference method, there is no confirmatory claim.
3. Stage 0 independence holds only for the tested families and harness versions.
4. An early safety STOP is not a fixed-G analysis.
5. T3 eligibility UNKNOWN is never PASS.
6. There is no evidence yet of decision-relevant memory transfer.

## 8. Bounded next task: P05-SV0 / P05-SV1, offline statistical-method validation (proposal for audit)

**Purpose:** decide whether *any* interval method has adequate coverage for the LOBO-refitted P0 learner at the planned
design. If none does, all confirmatory results become "inference not validated" (E1).

**Inputs:** the exact P0 learner (`creature_forge/experience_p0.py`, with its blob hash verified) on **synthetic data only**.
- The generators are those of calc §E: null; observation sufficient; interventions add information.
- Design: **m_inst = 3** (D5) and G ∈ {12, 28}.
- No Creature Forge records, no physics.

**P05-SV0** (deterministic; seconds):
- an identity resample reproduces the original LOBO fit bit for bit;
- duplicated bases share one LOBO group;
- relabelling bases is invariant;
- the H4 non-degeneracy calculator matches amendment 2.2 Lemmas 1–7;
- an optional faster re-implementation is accepted only if it is bit-identical to the P0 functions on 20 fixed datasets.

**P05-SV1a** (timing probe; ≤ 1 CPU-hour):
- one dataset per scenario at G = 28 and m_inst = 3, with naive CR1 and 5 refit-bootstrap replicates;
- it measures seconds per LOBO run and peak RSS.
- Estimate: about 40–60 s per run [ASSUMP: about 4× the section-E G = 24, m = 2 timing].

**P05-SV1b** (calibration; sized from SV1a):
- **Grid:** S datasets per (G, scenario) cell; scenarios {null, interventions add information}.
- **S must be decided before approval (B10).** At S = 40, the admission rule passes a method with true coverage 0.90 only 63 % of the time (2 cells, two-sided Wilson). S ≈ 87 per cell gives P(admit | 0.90) ≥ 0.90 and P(admit | 0.80) ≤ 0.05; S ≥ 100 is recommended, at about 2.5× the S = 40 compute (protocol §5; `a0_review/`).
- **B must match the confirmatory analysis:** the bootstrap refit count should be the same in P05-SV1 and the confirmatory run (B = 200 vs 40 is unresolved).
- **Methods:** naive CR1 t; base refit bootstrap (B to be matched to the confirmatory analysis); half-sampling of bases (40 splits).
- **Estimate at S = 40, B = 40:** about 50–60 CPU-hours at G = 28 plus about 3 h at G = 12 [ASSUMP]. This scales roughly
  linearly with S × B. **The SV1a measurement replaces it before approval.**

**Resource caps** (proposed; the owner sets the final values):
- ≤ 4 worker processes; peak RSS logged per process; abort if any process exceeds 1.5 GB or system free RAM falls below 4 GB.
- Per-dataset checkpoints; resumable.
- Wall-clock cap 24 h per approval.
- **No G = 46.** The G = 46 runs were lost to memory pressure with 9 processes.
- Prefer a separate terminal over a Claude background task, which can be reaped under memory pressure.

**Pre-declared decision:**
- A method is admissible if its coverage is ≥ 0.85 in every cell at G = 28, with the Wilson 90 % lower bound ≥ 0.75.
- The widest admissible method is the confirmatory interval.
- If none is admissible: "inference not validated".
- Monte Carlo SE ≈ 0.047, so only gross failures are detectable. That limitation is reported.

**Outputs:**
- a JSON per cell, with per-dataset estimates, intervals and timings;
- a short report;
- the hashes.
- **Nothing feeds a confirmatory result until the auditor reviews.**

## 9. Local environment

- **Python:** use the main checkout's environment, `..\Creature-Forge\.venv\Scripts\python.exe` (Python 3.11.9, numpy 2.4.6,
  **no scipy**; MuJoCo 3.15.0 is installed but must not run). The worktree has no venv. **Do not create one.**
- **MuJoCo guard:** analysis scripts block MuJoCo with `sys.modules["mujoco"] = None`.
  - `p05_min_budget_check.py` is the only archived script that imports MuJoCo. It traps every physics entry point and
    asserts that none ran.
- **Tests:**
  - CI runs `python -m unittest discover -s tests`;
  - the archived P0.5 tests run in place: `python -I -B <test file>` inside `design_archive/`.
  - `test_p05_amend22.py` finds the repository root relative to its own location; `CF_WORKTREE` overrides it.
- **MCP:** basic-memory may be available; the GitHub MCP has failed to connect in earlier sessions (use the `git` CLI).

## 10. Reproduce the A0 numbers (read-only, seconds)

```
cd experiments/causal_engineer/dev/experience_p05/design_archive
sha256sum -c SHA256SUMS
..\..\..\..\..\..\Creature-Forge\.venv\Scripts\python.exe -I -B test_p05_design_calc.py
..\..\..\..\..\..\Creature-Forge\.venv\Scripts\python.exe -I -B test_p05_design_calc_rev21.py
..\..\..\..\..\..\Creature-Forge\.venv\Scripts\python.exe -I -B test_p05_amend22.py
cd ..\a0_cost_model
..\..\..\..\..\..\Creature-Forge\.venv\Scripts\python.exe -I -B p05_a0_cost_model.py
cd ..0_review
..\..\..\..\..\..\Creature-Forge\.venv\Scripts\python.exe -I -B p05_sv1_admission_resolution.py
```
