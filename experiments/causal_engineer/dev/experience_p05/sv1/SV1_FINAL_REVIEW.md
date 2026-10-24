# P05-SV1: final review (2026-10-24)

**Status of this note.** This note is derived and was written after the confirmatory run. It changes no frozen file, value,
rule or classification. The frozen outputs are:
- `confirm_evidence/s2/out/confirm/sv1_results.json` (sha256 `bab836ec…`);
- `sv1_report.md` (`56d0c3a6…`);
- the archives `sv1_n4_s1.tgz` (`0ebf2daa…`) and `sv1_n4_s2.tgz` (`0f9aee31…`).

The protocol of record is `docs/plans/EXPERIENCE_P05_SV1_PROPOSAL.md`, §§0–18.

## 1. Classification (frozen, unchanged)

**ADMITTED and confirmed on the independent evaluation set.**
- All harness gates passed: C0 (amendment A-SV1-1), the bias check, completeness, and the 2 % byte-identical replay.
- One method was admitted, **M2** (the refit percentile bootstrap, B = 200). The confirmatory interval for P0.5 is therefore
  **M6 = M2** (frozen E1).

## 2. Conclusions

**Coverage of θ_G.** Admission estimates (S = 200) are selection-biased upward for admitted methods.

| cell | θ_G | M1 CR1 | **M2 refit pct** | M3 basic | M4 half | M5 composite |
|---|---|---|---|---|---|---|
| A-null | 0.000 | 0.860 | **1.000** | 0.800 | 0.835 | 0.985 |
| A-info | 0.108 | 0.750 | **0.995** | 0.670 | 0.785 | 0.940 |
| A-obs | 0.004 | 0.875 | **1.000** | 0.805 | 0.910 | 0.975 |
| B-null (G = 12, diagnostic) | 0.000 | 0.670 | 1.000 | 0.840 | 0.910 | 0.970 |
| B-info (G = 12, diagnostic) | 0.035 | 0.690 | 0.990 | 0.650 | 0.740 | 0.900 |

**Independent evaluation** (S_eval = 100 per cell; these are the only figures to quote as validity estimates):

| | A-null | A-info | A-obs |
|---|---|---|---|
| M6 = M2 coverage | 1.00 (Wilson 90 %: 0.974–1.00) | 0.97 (0.927–0.988) | 1.00 (0.974–1.00) |
| lower-tail misses | 0/100 | 0/100 | 0/100 |
| mean width / sd(θ̂) | 4.68 | 3.36 | 4.34 |

For comparison, a nominal 90 % normal interval has width/sd = 3.29.

1. **What is established, for the calc §E synthetic generator family and the recorded VM fingerprint only:**
   - the M2 interval around the LOBO estimate of the P0 kNN learner covers the procedure estimand θ_G at ≥ the nominal 90 %
     at G = 28;
   - it never missed on the side that matters for "supported benefit".
2. **The frozen primary interval, CR1, undercovers for a learned policy.** Its coverage is 0.75 in A-info (SE calibration
   0.48) and 0.67–0.69 at G = 12. This reproduces the calc §E warning with S = 200, so no P0.5 claim may rest on CR1.
3. **The basic bootstrap (M3) is worse than the percentile bootstrap.** Its coverage is 0.67–0.81, and its lower tail
   misses up to 0.18. Mirroring the bootstrap bias (−0.023 in A-info) moves the interval the wrong way.
4. **M2 is conservative**, at width/sd 3.4–4.7. The width is about 1.5× CR1.
5. **Power consequence for P0.5 (the decision-relevant finding).** In A-info the true benefit is θ_G = 0.108. The admitted
   procedure yields "supported benefit" in only **5 %** of evaluation datasets; the rest are 93 % inconclusive and 2 % "no
   meaningful gain".
   - The M2 half-width (≈ 0.12) exceeds the effect itself.
   - At the planned G = 28, P0.5 can therefore exclude large effects, but it is very unlikely to *demonstrate* an
     experience benefit of the size that calc §E calls informative.
   - Halving the half-width needs about 4× the bases (G ≈ 110). Even then the effect would only be borderline detectable.
6. **Not established by SV1:**
   - validity on real Creature Forge data (generator mismatch);
   - θ_new coverage beyond the synthetic population;
   - any physical effect, eligibility, cost or transfer.

## 3. Reporting inconsistency in the evaluation section (clarification; frozen output not edited)

**The defect.**
- In `sv1_results.json`, `evaluation.per_cell.<cell>.<method>.verdict` reads **"not validated"** for M2, M5 and M6 in all
  three cells.
- The value comes from `sv1_aggregate.py` line 218, `S.verdict(k, n, z, admitted=False)`, applied to the evaluation
  datasets.
- In §6B, "not validated" is an *admission* verdict. It means "the admission rule failed and the Wilson upper bound is
  ≥ 0.90".
- No admission decision is made on evaluation data, so the label is inapplicable there. Read literally, it contradicts the
  classification.

**Correct reading.**
- For every evaluation entry, the Wilson upper bound is ≥ 0.988, so there is **no evidence of undercoverage** of any kind.
- For M2 and M6, `conservative: true` holds in all three cells (Wilson lower > 0.90), so they are **conservative**.
- For M5, `conservative: false` in A-info and A-obs.

**What is unaffected.** The classification, `evaluation.admission_confirmed = true` (frozen §6A rule: the evaluation Wilson
upper bound of the selected procedure ≥ 0.85) and every number. These are computed separately from the `verdict` string.

**Disposition.**
- The frozen file is kept byte-identical.
- Any report quoting the evaluation section must use the reading above.
- If the aggregator is reused, a later version must emit an evaluation-specific label: "no evidence of undercoverage /
  evidence of undercoverage / conservative". It must not reuse the admission verdict function, and must bump its code hash.

## 4. Incident

The confirmatory run cost $2.969 against a $1.50 authorisation. The cause was a Nebius CLI login that expired mid-run, which
blocked the watchdog. Details are in `docs/memory/INCIDENTS.md` (2026-10-24).
- The scientific result is unaffected: the records are complete, and the replay is byte-identical.
- The infrastructure fix is the auth-horizon guard in `infra/nebius/forge_cloud.py` (main checkout, commit `d8e3727`):
  - deadlines never outlive the CLI token;
  - the watchdog stops VMs 30 min before the token expires.
