<!-- Archived verbatim from the planning session on 2026-10-23 (N1). This is the SV0 proposal of record as executed:
revision 4 plus 4a/4b changes. Attempt 1 = FAIL (sv0/attempt1/), attempt 2 = PASS (sv0/out/). Do not edit; see MANIFEST.md. -->

# Creature Forge V2: P05-SV0 proposal (bounded offline correctness check)

**Document:** CF-V2-P05-SV0-PROPOSAL, revision 4 (2026-10-23). It is a standalone proposal for independent scientific review.

**Revision 4 resolves four internal inconsistencies and clarifies U7** (auditor review of revision 3). Every frozen fixture,
expected value, seed, tolerance, gate, scientific definition and resource limit is unchanged.

| # | issue | fix | sections |
|---|---|---|---|
| R4-1 | F6 has G\* = 2 and is evaluated with fixed k, but the wrapper must reject G\* ≤ 2 | Two entry points. `refit_eval_fixed_k` is the fixture path: fixed k, no inner CV, needs G\* ≥ 2. `replicate` is the production path and the only one SV1 may call: inner-CV k, raises `DegenerateReplicate` at G\* ≤ 2. SV0-3b uses the first; SV0-3e calls the second on F6's own idx and expects the raise | §3.2 item 7, §5, SV0-1 F6, SV0-3b, SV0-3e |
| R4-2 | C3/V-a2 demanded an empty `git status` after the documentation edits | The block now requires `git status --porcelain --ignored` to be identical before and after, so it writes nothing. V-a2 separately requires that exactly the two intended files are modified | §2 C3, §8 V-a1/V-a2 |
| R4-3 | It was unclear how the isolated process imports P0, checks HEAD and the worktree, and verifies its own files without subprocesses or disallowed reads | New §5.1. A `sys.addaudithook` guard is installed first. Imports are explicit, from the approved checkout. The process reads git state by parsing `.git` files directly; git status comes from a launcher capture outside the process. The process fails closed if any `creature_forge` module resolves outside the checkout | §4 HEAD/transfer, §5, §5.1, SV0-0, §7A.3 |
| R4-4 | `pip freeze` might come from whichever pip is on PATH | Always `"$V/bin/python" -I -m pip freeze --all`, plus an in-process `importlib.metadata` manifest from the same interpreter. Both must match c1; if c1 found no pip in the venv, the manifest alone is the fingerprint | §7A.2, SV0-0 |
| U7 | Do uncommitted documentation edits change HEAD? | No. c2 pins `afe33ca…` unless a commit of (a) is separately approved; the SV0 code travels as three untracked files | §4, §10 U7, §11 |
| R4b | Attempt 1 (2026-10-23) classified **FAIL**. L4 was vacuous on B2: 0 of 36 queries kept their neighbour set. All other checks PASS | The gated L4 is now the hand-built fixture L4F (Case A invariance, Case B positive control), and the B2 loop is a non-gated diagnostic. `sv0_run.py` goes from `0708b7e8…` to `03e7a2f02ff8b03ddfbd383c60007ab22bdcc15721aedd1c6406588d198ee6a0`; `sv0_lib.py` and `sv0_reference.py` are unchanged. Attempt-1 code and outputs are preserved read-only in `sv0/attempt1/` (PROVENANCE.txt) and on the VM in `~/sv0_attempt1` | SV0-5 L4 only |
| R4a-1 | Setup steps after SV0-0 (secondary guards, dataset generation, and the monitor start) ran outside the failure reporting (static audit) | Each is wrapped. An unexpected exception writes an explicit `classification: FAIL` with `failed_at` set to that stage, and nothing further runs. The audit hook is unaffected | `sv0_run.py` `main` |
| R4a-2 | The status allow-list admitted any file under `out/run1/`, and a VM global excludes file could turn `??` into `!!` (static audit) | The launcher status now uses `-c core.excludesFile=/dev/null`. The run-2 allowance is exactly the three named run-1 outputs as `??` | §4, §5.1, `sv0_run.py` `_allowed_status_lines` |
| R4-5 | §7A.3 cloned without `--no-checkout` (review of revision 4) | §7A.3 step 4 now runs the §4 bundle clone procedure exactly: `--no-checkout`, with `core.autocrlf=false` configured before the first checkout | §7A.3 |
| — | Current VM state and prerequisite P | Both updated to the verified facts of 2026-10-23 (both VMs STOPPED; watchdog OK; AC-power condition) | §4 table, §7A.1 |

**Revision 3 changed only the execution environment** (owner request after the auditor's CONDITIONAL GO): SV0 runs on the
existing Nebius main VM instead of Windows. The changed sections are §4 (Environment, HEAD), §5 (guards, portability), the
environment items of SV0-0 and SV0-8, §7, the new §7A, §8 (output layout, V-c), §10 (U11–U15) and §11. Every fixture,
expected value, tolerance, seed, gate and statistical definition is unchanged.

**Status: preparation only.**
- **Nothing was executed:** no SV0/SV1, no simulation, no physics, no harness, no Stage E, pilot or campaign.
- **No external services were used:** no Token Factory, no paid inference, no sealed or held-out data. The only Nebius use was
  the owner's login and read-only status calls (2026-10-23). No VM was started.
- **Nothing was changed:** no repository file edited, no commit, no push. V1 is untouched.

**Repository:**
- `mahdinass/Creature-Forge`, branch `feature/experience-learning`, worktree `%USERPROFILE%\.vscode\cf-experience`.
- HEAD is `afe33ca68b73da313d720db0939ef382bc1cae91` (parent `e3caf8121da84523c36449e353a84bd05977ea9a`).
- The worktree is clean and equal to `origin/feature/experience-learning`.
- Every repository fact below was read with `git show afe33ca:<path>`.

**Changes from revision 1 of this proposal** (auditor review, 2026-10-23):
- reissued complete;
- independent reference fixtures with explicit expected outputs added (SV0-1, SV0-2, SV0-5, SV0-7);
- cluster-bootstrap semantics specified (§3);
- C1–C3 kept, with exact shell commands;
- checks renumbered: the old SV0-1/2 → SV0-3, old 3 → 4, old 4 → 5, old 5 + 8 → 8.

---

## 1. Purpose and non-claims

**SV0 tests whether the offline code that P05-SV1 would use computes what the protocol specifies, deterministically.** That code
is:
1. the exact P0 learner (`creature_forge/experience_p0.py`);
2. a new base-resampling and refit wrapper;
3. a new H4 non-degeneracy calculator (amendment 2.2 §1.2–1.4, corrected by erratum E2);
4. new interval-constructor helpers.

**What a PASS means:** the implementation matches hand-computed values, an independent reference implementation and the stated
semantics.

**What a PASS does not mean.** A PASS does **not** show:
- that the refit bootstrap, half-sampling or naive CR1 has adequate coverage;
- that bootstrap inference is valid for this non-smooth procedure;
- anything about Creature Forge physics, eligibility, costs or memory transfer.

Those questions belong to SV1 (synthetic only) and to later physical experiments.

**Fixed wording for any report:** "SV0 verifies implementation correctness and determinism on synthetic fixtures only; it
establishes no coverage, inference validity or transfer."

---

## 2. Handoff corrections C1–C3 (documentation only; proposed, not applied)

### C1. Outdated branch HEAD

**Defect** (verified):
- `docs/EXPERIENCE_P05_HANDOFF.md` §3 (line 32) and §5 (line 60) say `feature/experience-learning` = `e3caf81…`.
- `docs/plans/EXPERIENCE_P05_PROTOCOL.md` line 7 says "Branch … at `e3caf81…`".
- The published HEAD is `afe33ca`.
- No commit can contain its own hash, so the corrected text must not present a written hash as the current HEAD.

**Replacement for handoff §3, "V2 branch" row:**
> `feature/experience-learning`. **A0 publication commit `afe33ca68b73da313d720db0939ef382bc1cae91`** (independently verified by
> the auditor on GitHub 2026-10-23: one commit, 46 files, 33/33 archive hashes, 52/52 tests, byte-identical A0 outputs). Its
> parent is `e3caf8121da84523c36449e353a84bd05977ea9a` (P0 evidence publication). Later documentation-only commits may sit on
> top, so take the current HEAD from `git rev-parse HEAD` and `git log --oneline -3`, never from this file. Worktree:
> `cf-experience`, beside the main checkout `Creature-Forge`.

**Replacement for handoff §5, first row:**

| claim | status |
|---|---|
| A0 publication `afe33ca` (parent `e3caf81`) on GitHub | **independently verified** (auditor, 2026-10-23) |

**Replacement for protocol line 7:**
> **Branch:** `feature/experience-learning`. Drafted on `e3caf8121da84523c36449e353a84bd05977ea9a`; published in A0 commit
> `afe33ca68b73da313d720db0939ef382bc1cae91`. This document is the only new protocol text; …

The rest of the line is unchanged.

**Not changed:**
- Protocol line 99, "blob hashes at `e3caf81`", is correct. The three blobs are identical at `afe33ca`.
- The archived amendment and erratum also say "pinned at `e3caf81`". They are not edited, because editing them would break
  `SHA256SUMS`.

### C2. Corrupted `cd ..\a0_review` command

**Defect** (verified at the byte level):
- Handoff line 187 is `63 64 20 2E 2E 07 30 5F 72 65 76 69 65 77` (`cd ..<U+0007>0_review`).
- The backslash-a pair was escape-interpreted into a BEL character.
- A scan of all 46 files changed in `afe33ca` found **no other** control character.

**Fix:**
- Replace it as part of the C3 block below.
- After editing, run the scan in §8 (V-a1). The required result is 0 hits.

### C3. Shell-compatible, non-overwriting reproduction block (replaces handoff §10 in full)

**Defects** (verified):
- The block mixes a POSIX `sha256sum` with Windows backslash paths.
- `sha256sum` is not on the PowerShell PATH, and the `bash.exe` on PATH is WSL's (`C:\WINDOWS\system32\bash.exe`). Git's binary
  is at `C:\Program Files\Git\usr\bin\sha256sum.exe`.
- `p05_a0_cost_model.py` and `p05_sv1_admission_resolution.py` default `--out` to their **committed** output files, so the
  block as written overwrites tracked files.
- The archived tests write no files, and `-B` suppresses `__pycache__`.

**Replacement text for §10:**

````markdown
## 10. Reproduce the A0 numbers (read-only, seconds)

Run in **Windows PowerShell 5.1** from the `cf-experience` worktree root. Nothing is written inside the repository. Script
outputs go to `%TEMP%\cf_a0_repro` and are compared by hash with the committed files. The block does not require a clean
worktree. It requires that `git status --porcelain --ignored` is **identical before and after**, so the block itself changed
nothing, including ignored paths.

```powershell
$py  = (Resolve-Path ..\Creature-Forge\.venv\Scripts\python.exe).Path
$sha = 'C:\Program Files\Git\usr\bin\sha256sum.exe'
$tmp = Join-Path $env:TEMP 'cf_a0_repro'; New-Item -ItemType Directory -Force $tmp | Out-Null
$p05 = 'experiments\causal_engineer\dev\experience_p05'
$st0 = (git status --porcelain --ignored) -join "`n"

Push-Location "$p05\design_archive"
& $sha -c SHA256SUMS                        # 33 lines "OK"
& $py -I -B test_p05_design_calc.py         # OK
& $py -I -B test_p05_design_calc_rev21.py   # OK
& $py -I -B test_p05_amend22.py             # OK (12 tests)
Pop-Location

& $py -I -B "$p05\a0_cost_model\p05_a0_cost_model.py" --out "$tmp\p05_a0_cost_model_output.md"
& $py -I -B "$p05\a0_review\p05_sv1_admission_resolution.py" --out "$tmp\p05_sv1_admission_resolution_output.md"
foreach ($pair in @(@("$p05\a0_cost_model\p05_a0_cost_model_output.md", "$tmp\p05_a0_cost_model_output.md"),
                    @("$p05\a0_review\p05_sv1_admission_resolution_output.md", "$tmp\p05_sv1_admission_resolution_output.md"))) {
    $a = (Get-FileHash $pair[0] -Algorithm SHA256).Hash; $b = (Get-FileHash $pair[1] -Algorithm SHA256).Hash
    if ($a -eq $b) { "MATCH  $($pair[0])" } else { "DIFFER $($pair[0])" }
}
$st1 = (git status --porcelain --ignored) -join "`n"
if ($st0 -ceq $st1) { 'STATUS UNCHANGED' } else { 'STATUS CHANGED' }   # must print STATUS UNCHANGED
```

Git Bash equivalent: the same commands with forward slashes, `sha256sum -c SHA256SUMS`, `PY=../Creature-Forge/.venv/Scripts/python.exe`,
`--out "$TMP/..."`, `cmp` instead of `Get-FileHash`, and `st0=$(git status --porcelain --ignored)` … `[ "$st0" = "$st1" ]`.
````

**Notes on C3:**
- The expected committed-output hashes are those the auditor reproduced: cost `9f072cca…` and admission `a2628017…`. The full
  values are filled in from `Get-FileHash` at edit time.
- The PowerShell block is run as part of V-a2 (§8), on the edited, uncommitted worktree. There, both status snapshots list the
  two modified documents, and they must be identical.

---

## 3. Cluster-bootstrap semantics

This section is a specification that SV0 tests. It is **not** a claim of validity.

**Source rule** (revision 2 §4.4, unchanged):
- resample bases with replacement;
- duplicated bases keep **one group label**, so LOBO holds them out together;
- rerun the whole pipeline: standardisation, inner k choice, kNN, decision;
- take the percentile interval.

### 3.1 Construction of one replicate

Let the original sample have G bases, each with m = 3 instance rows.
- **The draw:** idx = (j_1, …, j_G), drawn i.i.d. uniformly from {0, …, G−1} with a declared `np.random.Generator`.
- **Multiplicity:** c_b = #{t : j_t = b}, so Σ c_b = G. The distinct bases drawn are G\* = #{b : c_b ≥ 1}.
- **Rows:** each draw contributes the base's 3 rows. The replicate has G·m rows in total.
- **Canonical layout:** rows are ordered by original base index, with copies adjacent. This makes the row order a deterministic
  function of the multiset {c_b}. It matters because `knn_rates` breaks distance ties by row position (stable argsort) and
  `nanmean`/`nanstd` sums in row order.
- **Group label:** each row keeps its **original base id**, used for both the outer and the inner LOBO.

### 3.2 Consequences that SV0 checks

1. **Number of outer LOBO folds = G\*,** not G.
   - E[G\*] = G·(1 − (1 − 1/G)^G): **7.78 at G = 12** and **17.89 at G = 28**.
   - Each fold trains on the other G\* − 1 distinct bases. Their rows enter with multiplicity c_b.
2. **Inner LOBO (k choice)** also has G\* − 1 folds, one per distinct training base, with copies held out together.
3. **Duplicate weighting** (all by multiplicity, none by de-duplication):
   - the fold standardisation (mean and sd) weights a base drawn c times c-fold;
   - the training prior and π0 use row frequencies including copies;
   - copies of one base are identical rows at identical distances, so they can fill up to c·m of the k neighbour slots. Because
     their Y rows are identical, the tie-break among them does not change P;
   - inner-CV log loss counts each copy row.
4. **The held-out side:**
   - all c_b copies of base b are predicted by the same fold, from identical features and the same training set;
   - so their predictions, picks and values are **identical**;
   - base b therefore contributes c_b · Σ_i d_bi to the replicate sum.
5. **The statistic estimated:**
   - θ̂\* = (1 / (G·m)) Σ_b c_b Σ_{i ∈ b} d\*_bi, where d = v(interv) − v(obs_morph);
   - d\*_bi comes from the fold that holds out all copies of b. It depends on the **other** bases' multiplicities, which is the
     "refit".
   - The bootstrap distribution of θ̂\* is intended to approximate the sampling variability of the LOBO cross-fitted estimate θ̂.
6. **What this implies, and why SV0 cannot validate it:**
   - Each replicate fits the procedure on about 0.64·G distinct bases with duplicated rows. That is structurally different from
     fitting on G distinct bases: fewer distinct neighbours, duplicates occupying k slots, and a k choice shifted by inner CV
     over G\* − 1 groups.
   - The procedure involves an argmax, a data-driven k and nearest-neighbour sets. It is non-smooth, and bootstrap inconsistency
     for such functionals is a known risk.
   - **Whether the percentile interval of θ̂\* covers the procedure estimand is an SV1 question, answered only for synthetic
     generators.** SV0 only checks that the wrapper implements items 1–5 exactly.
7. **Degenerate replicates:**
   - With G\* = 1, LOBO has an empty training set. With G\* = 2, inner LOBO has an empty training set: `choose_k` gets NaN losses
     and silently returns k = 1.
   - **The production entry point `replicate` raises `DegenerateReplicate` when G\* ≤ 2.** SV0 checks that it does (SV0-3e).
   - **The fixture entry point `refit_eval_fixed_k`** takes k from the caller and runs no inner CV, so only the outer LOBO needs a
     non-empty training set. It therefore accepts G\* ≥ 2 and raises `ValueError` at G\* = 1. It exists so that hand fixtures with
     G\* = 2 (F6) can test the duplicate semantics of items 1–5. It is never a bootstrap path; SV1 may call only `replicate`
     (§5).
   - P(G\* ≤ 2) ≤ C(G, 2)·(2/G)^G, which is about 3.0e-8 at G = 12.
   - How SV1 counts such replicates is an SV1 decision (U10).
8. **Rejected alternative:** labelling copies as separate groups would let a held-out base use its own copy at distance 0. That
   is leakage, and it is SV0-3's positive control.

---

## 4. Inputs (pinned; preflight fails closed on any mismatch)

### Code under test

The git blob sha1 values are recomputed in Python from the file bytes, as sha1(`"blob <n>\0"` + bytes), with no subprocess.

| file | blob | note |
|---|---|---|
| `creature_forge/experience_p0.py` | `dcfb1f29cc14ea05bb4bb80eb9d18240a81b3360` | protocol pin |
| `creature_forge/experience_bank.py` | `38aed182696d5d46cf992e7bd4e9d138e6a6a0f4` | protocol pin |
| `scripts/exp_p0_audit.py` | `dbaa4d34cb83bfc6fdfd0b456aaf3be72753ec98` | protocol pin (not imported) |
| `creature_forge/experience_audit.py` | `1273379810988db569e855aa8d954c2da038b04f` | **proposed new pin (U9):** it is imported by `experience_p0`, and its import-time code only defines constants (no I/O) |
| `creature_forge/__init__.py` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` | empty file |

### Synthetic generator and archive

- `design_archive/p05_design_calc.py` supplies `_synth`, `SCENARIOS` (calc §E) and `t_ppf`. It is imported read-only.
- Its sha256 must match `design_archive/SHA256SUMS`, and all 33/33 manifest entries are verified.
- **Scenarios:**
  - null: θ = 0, noise_o = 1, noise_c = 1;
  - observation sufficient: θ = 1.5, noise_o = 0.5, noise_c = 3;
  - interventions add information: θ = 1.5, noise_o = 3, noise_c = 0.5.
- **Fixed parameters:** drawn from `default_rng(20261023 + 7)` exactly as in calc §E.
- **Design:** m = 3 (D5); G ∈ {12, 28}; X has 42 columns (morph 0–6, obs 7–14, cf 15–41); Y has 10 tools.
- **Policies:** `interv` = (obs, morph, cf) and `obs_morph` = (obs, morph).

### Seeds

- **SV0 namespace:** `SV0_SEED = 2026102370`.
- **Offsets, declared in code:**
  - +1…+3: set A datasets (G = 28);
  - +11…+13: set B datasets (G = 12);
  - +21…+29: resample and relabel draws;
  - +31: half-sample splits.
- It is disjoint from calc §E (20261023 + 7, + 11). SV1 must declare its own namespace.
- Only `np.random.Generator` objects are used. There is no global RNG.

### Datasets

- **Set A:** G = 28, m = 3, one per scenario (3).
- **Set B:** G = 12, m = 3, one per scenario (3).
- **Hand fixtures:** F1–F7 (SV0-1).
- **H4 design tables:** H-a to H-f (SV0-5).

### Environment (revision 3: Nebius main VM, Linux)

**Machine:** the existing main VM.

| property | value | source |
|---|---|---|
| name and id | `creature-forge-r1-cpu`, `computeinstance-e01g6rhpgcpnf1bfbr` | `infra/nebius/state.json` |
| platform | cpu-d3, preset 8vcpu-32gb, Ubuntu 24.04 (`ubuntu24.04-driverless`), 50 GiB network SSD | `forge_cloud.py` `_BASE` / `PROFILES["main"]` |
| last recorded event | API stop at epoch 1792610270 (2026-10-21, about 19:18 UTC) | `spend_ledger.jsonl` |
| current state | **STOPPED** (read-only API check, 2026-10-23 16:08 local, after the owner's `forge_cloud.py login` cleared `AUTH_BLOCKED`). The project holds only main and batch, both STOPPED, with 2 boot disks READY. There is no public IP while stopped, so `start` re-reads it | Nebius API, `watchdog.log` |
| The batch VM | (`computeinstance-e01efb17k9jbzct0m0`, 64 vCPU) is never used. Its last ledger event is a stop | `state_batch.json` |

**Recorded VM environment** (2026-10-14, `artifacts/nebius_r1/20261014T125600/logs/`; not re-verified):

| property | Windows (A0 audit) | VM (recorded) |
|---|---|---|
| Python | 3.11.9 | **3.12.3** |
| numpy | 2.4.6 | **2.5.4** (inside the pinned range `>=2.4.6,<2.6`) |
| platform | Windows-10-10.0.26200 | Linux-6.11.0-1016-nvidia-x86_64, glibc 2.39 |
| CPUs, free RAM | 16 logical, 1.4 GB free of 15.7 GB | 8 vCPU, 30.6 GB free |
| scipy | absent | absent (`pip freeze`) |
| mujoco | installed, blocked | installed, blocked |

The dev-slot venvs (`~/dev/venvs/<slot>`) have no recorded version. They are inventoried in step c1 (§7A).

**Interpreter rule (no installs):**
- SV0 uses an **existing** VM venv, `$V/bin/python -I -B`.
- The venv is chosen in c1 by the pre-declared criteria of §7A and named by the owner in approval (c2).
- No `pip install`, no venv creation, no `forge_dev.py sync`. Its `remote_prepare` runs `pip install -e '.[studio]'` when the
  `pyproject.toml` hash changes, which could silently change numpy.

**Threads:** `OMP_NUM_THREADS = OPENBLAS_NUM_THREADS = MKL_NUM_THREADS = 1`, set in the launch environment (§7A).

**Reproducibility implications of the VM environment, and how they are handled:**
1. **The gates do not depend on the platform by construction.** Every gated comparison is one of:
   - within one environment: P0 vs wrapper, reference vs P0, run 1 vs run 2;
   - against hand values that are either exact dyadic results of exact IEEE-754 operations (the F5/F6 sums of 0/1 values
     divided by 2 and 4), or compared with the stated 1e-12 tolerance.

   None of these values changes between Windows/numpy 2.4.6 and Linux/numpy 2.5.4.
2. **What can change across environments:**
   - **Synthetic dataset bytes.** numpy guarantees bit-stream stability for the PCG64 bit generator, but not for `Generator`
     distribution methods across versions.
   - **Low-order bits** of numpy reductions (SIMD, libm).

   These affect dataset sha256 values and, at most, near-tie behaviour. That is why the SV0-2 near-tie rule exists. They do not
   affect any gate definition.
3. **Archived 52 tests:** verified on Windows (by Claude) and in the auditor's replica. On Linux they are a regression on a new
   platform. A failure is FAIL under SV0-6, with no tolerance change.
4. **Scope of a PASS:** an SV0 PASS certifies the code **in the recorded VM fingerprint**:
   - Python version, numpy version and BLAS from `numpy.show_config()`;
   - the platform string, CPU model and flags;
   - the venv path, its distribution-manifest sha256 and its `pip freeze` sha256 (both from the venv's own interpreter, §5.1).

   **SV1 must run under the identical fingerprint.** Any change requires an SV0 rerun. The archived calc-§E numbers (Windows)
   are not bit-reproducible on the VM, and SV0 does not use them.
5. **Recommended resolution:** reuse an existing venv with numpy in the pinned range (option 1) and freeze its fingerprint for
   SV1.
   - **Alternative (option 2, needs its own install approval; not requested):** a dedicated `~/sv0/venv` with only
     `numpy==2.4.6`, installed from PyPI with `--require-hashes`.
   - Option 2 aligns the numpy version with Windows, but the platform and Python still differ. Since SV0 does not compare across
     platforms, the benefit is small.

### HEAD and code transfer (revision 4)

**The pinned commit (U7):**
- Uncommitted edits do not change HEAD. If (a) stays uncommitted, as approved by default, `cf-experience` HEAD stays
  **`afe33ca68b73da313d720db0939ef382bc1cae91`**, and c2 pins that commit.
- c2 pins a different commit only if the owner separately approves a commit of (a). In that case c2 pins that documentation-only
  commit, whose hash the owner names in (c2).
- Either way, the 5 pinned blobs and the archive are byte-identical, because (a) touches only two documents. SV0 reads no
  documents.

**What travels to the VM, and how:**
- **Committed tree:** `git bundle create repo.bundle HEAD`, made locally only after checking
  `git rev-parse HEAD` = the pinned hash. Then `git bundle verify repo.bundle` and `git bundle list-heads repo.bundle`, which must
  show the pinned hash.
  - A bundle carries commits only. The uncommitted documentation edits of (a), and anything else in the local worktree, are
    **not** transferred.
- **SV0 code:** the three `sv0/*.py` files from approval (b). They are uncommitted, belong to no commit, and are copied by `scp`
  as plain files. Their sha256 must equal the hashes delivered at (b). After copying, they are set read-only (`chmod 444`).
- **On the VM:** `git -c core.autocrlf=false clone -q --no-checkout repo.bundle ~/sv0/repo`, then
  `git -C ~/sv0/repo config core.autocrlf false`, then `git -C ~/sv0/repo checkout -q --detach <pinned hash>`. Setting the
  option before the first checkout keeps the checked-out bytes equal to the blobs. The three files go into `experiments/causal_engineer/dev/experience_p05/sv0/`.
- **Expected-values file:** `~/sv0/pre/expected.json`, outside the repository. It is written from the (c2) approval text and
  holds the pinned hash, the three code sha256 values and the c1 fingerprint values (§5.1).
- **Allowed `git status`** (revision 4a). The status is taken as
  `git -c core.excludesFile=/dev/null status --porcelain=v1 --untracked-files=all --ignored`.
  - **Before run 1:** it must list **exactly** the three `?? experiments/causal_engineer/dev/experience_p05/sv0/sv0_{lib,reference,run}.py`
    lines.
  - **Before run 2:** it may also list `?? …/sv0/out/run1/sv0_results.json`, `?? …/sv0/out/run1/sv0_env.json` and
    `?? …/sv0/out/run1/sv0_report.md`, a subset of these three named files and nothing else.
  - **Every other line is stray and fails SV0-0.** That includes any `!!` (ignored) line and any other file under `out/run1/`,
    for example a watchdog `sv0_abort.json`.
  - **Why the outputs appear as `??`, verified on the tracked tree at `afe33ca`.**
    - The only tracked ignore file is the root `.gitignore`. None of its patterns match those paths. The closest ones,
      `runs/`, `env/`, `*.log`, `artifacts/` and `build/`, name other directories or extensions.
    - A fresh clone's `.git/info/exclude` holds only the default comments.
    - `-c core.excludesFile=/dev/null` disables any user-level global excludes file on the VM, including the default
      `~/.config/git/ignore`, which this session cannot inspect. The status therefore depends only on the tracked tree.
    - `-B` writes no `__pycache__`, so no ignored file is expected.
- With `core.autocrlf = false`, the checked-out bytes equal the git blobs, so the §4 blob pins are well defined. On a Windows
  checkout with `autocrlf = true` they would not be.
- Nothing is pushed to GitHub, and `~/creature-forge` and `~/dev/*` are not touched.

---

## 5. Code to be written (only after approval (b); new files only)

All new files go in `experiments/causal_engineer/dev/experience_p05/sv0/`.

| file | content |
|---|---|
| `sv0_lib.py` | `resample(X, Y, base, idx)`: §3.1, canonical layout, returns (X\*, Y\*, groups\*, c). `refit_eval(space, Y, groups, use)`: calls `p0.predict(space, use, Y, groups, groups)` (inner-CV k) then `p0.decision_eval`, unchanged; no G\* check. `refit_eval_fixed_k(space, Y, groups, use, k_fixed)`: **fixture entry point**; the same call with `k_fixed` passed through, with no inner CV. It requires `set(k_fixed) ==` the distinct groups and G\* ≥ 2, and raises `ValueError` otherwise. `replicate(X, Y, base, idx, use)`: **production entry point**; `resample`, then G\* ≤ 2 → `DegenerateReplicate`, then `refit_eval`. It is the only function SV1 may call. `leak_check(space, groups, use)`: flags test rows with a training row at block distance exactly 0. `h4_calc(table, control)`: per fold D = Π_{\|g\|≥2} !\|g\|, regime (E2), N1 F, N3, validity. `cr1_se`, `half_splits`, `percentile_ci`, `wilson_lower(k, n, z)`. |
| `sv0_reference.py` | **Independent pure-Python reference** of the P0 LOBO kNN pipeline, written from the specification (P0 docstrings and revision 2 §6). It uses lists and `math.fsum`, with no numpy and no import of `experience_p0`. It covers per-fold population mean/sd with NaN → z = 0 and sd ≤ 1e-9 → 1; equal block weighting (mean of squared z-differences within a block, summed over blocks); a stable tie-break by training row order; Laplace shrinkage (Σ Y + prior)/(k + 1); inner-LOBO k over (1, 3, 5, 9, 15, 25) with k ≤ n_train, log loss clipped at 1e-4 and weighted by fold size, and strict improvement by 1e-12; and pick = argmax(P + 1e-9·prior). It also includes a **brute-force H4 enumerator** (itertools over all joint derangements). |
| `sv0_run.py` | Preflight, guards, checks SV0-0 to SV0-8, watchdog, outputs. It contains no coverage loop, which SV0-8 asserts by AST. |

**Guards active for the whole run** (revision 4 states the mechanism; the guarded behaviours and the SV0-8 tests are unchanged):
- **Primary layer: a `sys.addaudithook`** installed as the first statement of `sv0_run.py`, before numpy or any repository module
  is imported. Audit hooks cannot be removed, and they see **every** file open, including those made by the import system
  (`io.open_code`), not only `builtins.open`.
  - **`open`, reads:** allowed only for
    - the 5 pinned files;
    - the 3 `sv0/*.py` files;
    - `design_archive/`;
    - `REPO/.git/HEAD` and `REPO/.git/index`;
    - `~/sv0/pre/expected.json` and `~/sv0/pre/run<N>.*`;
    - the interpreter's own `sys.prefix` / `sys.base_prefix` trees (stdlib and numpy), **excluding** any path containing
      `creature_forge` or `__editable__`;
    - on Linux, `/proc/self/status`, `/proc/meminfo`, `/proc/cpuinfo` and `/etc/os-release`.
  - **`open`, writes:** under `sv0/out/run<N>/` only.
  - **`os.listdir` / `os.scandir`:** only the directories of these allowed roots, which the import system needs.
  - **Always refused:** `artifacts/`, any `*.jsonl`, any `.env`, `~/dev/`, `~/creature-forge/`, `glob.glob`, `socket.__new__`,
    `socket.connect`, `subprocess.Popen`, `os.system`, `os.exec*`, `os.spawn*`, `os.posix_spawn` and `os.fork`.
- **Secondary layer** (defence in depth, after the imports): `sys.modules["mujoco"] = None`. `subprocess.Popen`,
  `multiprocessing.Process.start`, `os.fork` and `socket.socket` are replaced by functions that raise. A final assertion checks
  that no `mujoco*` module is loaded.
- **environment hygiene:** the process is launched with `env -i` (§7A), so no API key reaches it. SV0-0 also asserts that no
  variable name matching `KEY`, `TOKEN` or `SECRET` is present.

**Linux portability requirements for (b):**
- `pathlib` only, with paths derived from `__file__` relative to the repository root. No drive letters, no backslashes, no
  Windows APIs.
- **Memory and CPU monitor backend chosen by `sys.platform`:**
  - **`linux`** (the only one used in execution): `/proc/self/status` (`VmRSS`, `VmHWM`) and `/proc/meminfo` (`MemAvailable`).
    CPU time comes from `time.process_time()` and `resource.getrusage`.
  - **`win32`:** ctypes `GetProcessMemoryInfo` / `GlobalMemoryStatusEx`. It is kept only so the code is not Linux-locked, and is
    not approved for execution.
- **Outputs are byte-stable across platforms:** UTF-8, `newline="\n"`, `json.dumps(sort_keys=True, ensure_ascii=True)`, floats
  via `repr`. Platform details go only to `sv0_env.json`.
- **No dependence on string-hash order** (set or dict iteration of strings). `-I` ignores `PYTHONHASHSEED`, so the two SV0-8
  processes have different hash seeds, which strengthens the determinism check.
- **The archived tests run in-process** through `unittest` loaders: there are no subprocesses. Their repository-relative default
  root (5 parent directories up from the archive) resolves correctly on Linux.

**Implementation clarifications made in (b),** for review. No value, seed, tolerance or gate is changed.
- **Path rule.** A path is refused if either its literal or its symlink-resolved form is refused, and allowed if either form
  is allowed. Reason: Debian/Ubuntu stdlib files such as `sitecustomize.py` are symlinks into `/etc`, and `/proc/self`
  resolves to the pid.
- **Excluded from the interpreter trees.** The exclusion applies at the path-component level: a component equal to
  `creature_forge`, or a basename starting with `__editable__`. `*.dist-info` metadata stays readable, because the package
  manifest needs it.
- **Partial carve-out of the `~/dev/` refusal.** `~/dev/` is refused except inside the selected venv's own `sys.prefix`, in
  case c1 selects a dev-slot venv. `~/dev/.env` is refused always, because the `.env` rule applies everywhere.
- **Extra read-only paths for `sv0_env.json`.** `/proc/self/cgroup` and `/sys/fs/cgroup/**` are readable, for the cgroup
  limits recorded in §8.
- **`platform.platform()`.** It internally attempts `uname -p`, which the guard refuses. Python swallows the error, and the
  processor field is blank both in c1 and in-process, so the fingerprint is unaffected.
- **L3 "relative 1e-12".** Implemented as `|a − b| ≤ 1e-12 · max(|a|, |b|, mean|x| of the column)`. A column mean that is
  near 0 by chance has no meaningful self-relative error.
- **The c1 fingerprint.** It is the exact source string `FINGERPRINT_SRC` in `sv0_run.py`. In c1 it is fed to
  `"$V/bin/python" -I -B -` on stdin, and in SV0-0 it is executed in-process, so both produce identical keys.

**Not modified:** `creature_forge/`, `scripts/`, `tests/`, `design_archive/`, `a0_*`, V1, CI.

**Honest limit of the reference:** it was written by the same author after reading P0. It guards against plumbing,
vectorisation and indexing errors, not against a shared misreading of the specification. The hand fixtures (SV0-1) are the
specification-level check.

### 5.1 Startup, import and provenance procedure (revision 4; implements SV0-0)

The work is split between a **launcher**, a bash script in the tmux session (§7A.3), and the **SV0 process**. Only the launcher
runs git and pip. The SV0 process uses no subprocess and independently re-checks everything it can by reading files.

**Launcher, before run N** (outside the SV0 process, as user `forge`, with the working directory `~/sv0/repo`):
1. `git rev-parse HEAD > ~/sv0/pre/runN.head`
2. `git -c core.excludesFile=/dev/null status --porcelain=v1 --untracked-files=all --ignored > ~/sv0/pre/runN.status`
   (see §4, "Allowed `git status`")
3. `"$V/bin/python" -I -m pip freeze --all > ~/sv0/pre/runN.freeze`. This is the candidate venv's own pip, never a pip from
   PATH (R4-4).
4. Then the limited launch of §7A.3, which also passes `--expected ~/sv0/pre/expected.json`.

**SV0 process, in order** (any failure aborts with SV0-0 FAIL, writing only `out/runN/sv0_results.json` with the failure):
1. **Install the audit hook** (§5). This must be the first statement.
2. **Fix locations:**
   - `SV0_DIR = Path(__file__).resolve().parent` and `REPO = SV0_DIR.parents[4]`;
   - assert `REPO == Path.home()/"sv0"/"repo"` (resolved);
   - assert `(REPO/".git").is_dir()`, so `.git` is not a gitfile pointing at another repository.
3. **Interpreter flags:** assert `sys.flags.isolated`, `sys.flags.dont_write_bytecode` and `sys.flags.no_user_site`; assert
   `sys.prefix != sys.base_prefix` (a venv); assert `Path(sys.prefix).resolve()` equals the venv path in `expected.json`.
4. **Neutralise other installations before any repository import:**
   - assert that no `creature_forge*` module is in `sys.modules`;
   - set `sys.path = [str(SV0_DIR), str(REPO), str(ARCHIVE)] +` the original entries lying under `sys.prefix` /
     `sys.base_prefix`. This drops the path entries of legacy editable installs, such as `~/creature-forge` or `~/dev/<slot>`;
   - remove from `sys.meta_path` every finder whose type or module name contains `__editable__`.
5. **Explicit imports:** `creature_forge.experience_p0`, `p05_design_calc`, the three archived test modules, `sv0_lib` and
   `sv0_reference`, all in this phase. The archived tests insert their own directory and `REPO` (5 levels up; `CF_WORKTREE` is
   absent under `env -i`) into `sys.path` and reuse the cached modules.
6. **Fail closed on shadowing.** Every module named `creature_forge` or `creature_forge.*` in `sys.modules` must have a
   `__file__` that resolves to exactly `REPO/creature_forge/<name>.py`, and must be one of the 4 pinned `creature_forge` files.
   `creature_forge.__path__` must equal `[REPO/creature_forge]`. `p05_design_calc`, `sv0_lib` and `sv0_reference` must resolve
   to `ARCHIVE` and `SV0_DIR`.
   - An older editable or regular installation therefore causes one of three things: its open is refused by the hook, its path
     is pruned, or its `__file__` fails this check. **In all three cases the result is FAIL; it is never silently used.**
7. **Provenance without subprocess:**
   - **HEAD:** `REPO/.git/HEAD` must be a detached 40-hex hash equal to `expected.json["head"]`, and `runN.head` must equal it.
   - **Index:** parse `REPO/.git/index` (signature `DIRC`, version 2 or 3; any other version fails). For the 5 pinned paths, the
     index sha1 must equal the pin, and the blob sha1 of the worktree bytes must also equal it.
   - **Worktree:** every line of `runN.status` must be in the allowed set of §4 ("Allowed `git status`").
   - **Own code:** the sha256 of the bytes of `sv0_lib.py`, `sv0_reference.py` and `sv0_run.py` must equal
     `expected.json["code_sha256"]`.
   - **Archive:** 33/33 sha256 entries of `SHA256SUMS`.
8. **Fingerprint:**
   - Python version, numpy version, the `numpy.show_config(mode="dicts")` build and BLAS section, `platform.platform()`, and the
     CPU model and flags from `/proc/cpuinfo`;
   - the **distribution manifest**: sha256 of the sorted `Name==version` lines from
     `importlib.metadata.distributions(path=<site-packages under sys.prefix>)`;
   - all must equal the c1 values in `expected.json`;
   - the sha256 of `runN.freeze` must equal the c1 `pip freeze` sha256 (U11). If c1 recorded "pip absent", `runN.freeze` must
     be empty, and the manifest alone applies.
9. **Then** the remaining SV0-0 items (scipy absent via `importlib.util.find_spec`, threads, no `KEY`/`TOKEN`/`SECRET`
   variables, `MemAvailable` ≥ 3 GB), the secondary guard layer, and SV0-1 to SV0-8.

**What is checked where:**

| fact | launcher (git or pip, outside) | SV0 process (independent) |
|---|---|---|
| HEAD | `git rev-parse HEAD` | `.git/HEAD` parse |
| tracked files unmodified | `git status` | index sha1 = worktree blob = pin, for the 5 pinned files; `SHA256SUMS` for the archive |
| no unexpected files | `git -c core.excludesFile=/dev/null status --porcelain=v1 --untracked-files=all --ignored` | reads the launcher capture and requires the exact allowed set of §4 |
| packages | `$V/bin/python -I -m pip freeze --all` | `importlib.metadata` manifest |
| imported P0 is the approved copy | — | §5.1 steps 4–6 |

---

## 6. Checks SV0-0 to SV0-8: inputs, expected outputs, PASS and FAIL

### 6.0 Comparison conventions

- **Exact:** `np.array_equal`, or `==` for ints, dicts and bools.
  - It applies to discrete outputs: neighbour indices, k, picks, v values, fold names, D, regime and validity.
  - It also applies to values that are exact dyadic results of exact operations (for example 0.875).
- **Tolerance:** absolute 1e-12, applied only where floating-point summation order legitimately differs (stated per item).
- **Every expected value is written literally into `sv0_results.json` next to the observed value.**

### SV0-0: provenance and environment preflight

**Inputs:** §4 pins, HEAD, `SHA256SUMS`, the VM fingerprint, thread variables, free RAM.

**PASS iff:**
- all 5 blobs match, both in the index and in the worktree bytes (§5.1 step 7);
- 33/33 sha256 entries match;
- HEAD equals the approved hash in both `.git/HEAD` and the launcher's `git rev-parse` (§5.1 step 7);
- the launcher's `git status` lists only the allowed lines of §4, and the `sv0/*.py` sha256 equal the (b) hashes;
- **(revision 3, environment only)** the platform is `linux` x86_64, and the Python version, numpy version, BLAS and venv path
  equal the c1 fingerprint named in approval (c2). So do the distribution manifest and the `pip freeze` sha256, the latter
  obtained as `"$V/bin/python" -I -m pip freeze --all` (§5.1 step 8). numpy lies in `>=2.4.6,<2.6`;
- **(revisions 3–4)** every loaded `creature_forge*` module resolves to its pinned file inside `~/sv0/repo`, and no other
  installation is used (§5.1 steps 4–6). This matters because existing venvs hold editable installs that point at other clones;
- scipy is absent;
- the 3 thread variables equal 1;
- no `KEY`, `TOKEN` or `SECRET` variable is present;
- free RAM (`MemAvailable`) ≥ 3 GB.

*Revision-2 text was "Python is 3.11.9 and numpy is 2.4.6". It is replaced only because the execution machine changed (§4).*

**FAIL:** any mismatch. Nothing further runs.

### SV0-1: hand-computed reference fixtures on the exact P0 functions

These fixtures were computed by hand before implementation and are recorded here.

| id | call | input | expected output | compare |
|---|---|---|---|---|
| F1 | `knn_rates` | D = [[0, 1, 4]]; Ytr = [[1,0],[1,0],[0,1]]; k = 2; prior = [2/3, 1/3] | [[8/9, 1/9]] | tol 1e-12 |
| F2 | `knn_rates` stable tie | D = [[1.0, 1.0, 0.5]]; Ytr = [[1,0],[0,1],[0,0]]; k = 2; prior = [0, 0] | neighbours (2, 0); P = [[1/3, 0]] (not [0, 1/3]) | idx exact; P tol 1e-12 |
| F3 | `Space.dist` | blocks A = [col 0], B = [cols 1, 2]; training rows X = [[0,0,0],[2,0,0],[4,0,0]]; test [[2,1,3]]; use (A, B) | A: training mean 2, population sd √(8/3), so the z-distances are [1.5, 0, 1.5]. B: sd 0 is replaced by 1, so the mean squared diff is (1 + 9)/2 = 5. D = [[6.5, 5.0, 6.5]] | tol 1e-12 |
| F3n | `Space.dist`, NaN | as F3, but training column 0 all NaN and test col 0 = NaN | A contributes 0, so D = [[5, 5, 5]] | tol 1e-12 |
| F4 | `decide` | P = [[0.5, 0.5]], prior = [[0.3, 0.7]]; and P = [[0.6, 0.5]], prior = [[0, 1]] | 1; 0 | exact |
| F5 | full LOBO `predict` + `decision_eval` + `summarize_decision` | 1 block "obs" = [col 0]; X = [0, 0.1, 10, 10.1, 20, 20.1]; base = [0,0,1,1,2,2]; Y = [[1,0],[1,0],[0,1],[1,0],[1,1],[0,0]]; `k_fixed` = {"0": 1, "1": 1, "2": 1} | see the F5 detail below | P, prior, pick, v exact (dyadic); summary exact |
| F6 | `resample` + `refit_eval_fixed_k` on F5 (G\* = 2; fixture entry point, no inner CV) | idx = [0, 0, 2] (base 0 twice, base 1 absent); `k_fixed` = {"0": 1, "2": 1} | see the F6 detail below | exact |
| F7 | `leak_check` | F6 with the correct labels [0,0,0,0,2,2] vs mislabelled copies [0,0,1,1,2,2] | correct: 0 rows flagged; mislabelled: rows {0, 1, 2, 3} flagged (training twin at distance exactly 0.0) | exact |

**F5 detail:**
- prior per fold (rows): [.5, .5] ×2, then [.75, .25] ×4.
- P (rows 0–5): [.25, .75], [.25, .75], [.875, .125], [.875, .625], [.875, .125], [.875, .125].
- pick = [1, 1, 0, 0, 0, 0].
- v_mem = [0, 0, 0, 1, 1, 0]; v_pi0 = [1, 1, 0, 1, 1, 0].
- `summarize_decision`: value_mem 0.3333, value_pi0 0.6667, delta −0.3333, oracle 0.8333, regret 0.5, p_plus 0.0, p_minus
  0.3333.

**F6 detail:**
- rows: X\* = [0, 0.1, 0, 0.1, 20, 20.1]; groups\* = [0,0,0,0,2,2]; 2 folds ("0", "2").
- P\* = [.75, .75] ×4, then [1, 0] ×2.
- pick\* = [0,0,0,0,0,0]; v_mem\* = [1,1,1,1,1,0]; mean 5/6.
- the predictions for the two copies are bit-identical.

**SV0-1 PASS iff** every expected value is reproduced. **FAIL:** any deviation.

### SV0-2: independent reference implementation vs the exact P0 pipeline

**Inputs:**
- set B (3 datasets, G = 12) and 1 set-A dataset (G = 28, "interventions add information");
- both policies;
- full inner-LOBO k selection.

**Compared:**
- per-fold k: exact;
- per-row neighbour index sets: exact;
- pick, v_mem, v_pi0, prior: exact;
- P and gate_sim: tol 1e-12;
- the estimate mean(v_interv − v_obs_morph): exact.

**Near-tie rule:** the reference reports two margins:
- the smallest pick margin, top-1 minus top-2 of P + 1e-9·prior;
- the smallest inner-CV loss gap between the chosen k and the runner-up.

**PASS iff** all compared items agree.

**FAIL:**
- any disagreement where both margins are ≥ 1e-9;
- any disagreement with a margin < 1e-9 is **FAIL-INVESTIGATE**. Datasets are never swapped after the run.

### SV0-3: refit wrapper (identity, duplicates, edge cases)

| sub | input | PASS iff |
|---|---|---|
| 3a identity | sets A + B; idx = arange(G); original labels | the outputs (P, prior, gate_sim, k dict, pick, v_mem, estimate) are **exactly** equal to direct `p0.predict` + `decision_eval`, for both policies, on two consecutive calls |
| 3b hand duplicates | F6 through `resample` → `refit_eval_fixed_k(..., k_fixed={"0": 1, "2": 1})` | the F6 expected values (SV0-1) are reproduced exactly by this wrapper path. Fixed k means no inner CV runs, so G\* = 2 is legitimate here |
| 3c duplicates on synthetic data | set B, through `replicate`. The declared patterns give G\* = 11 and 9; the seeded draw gives about 8, and G\* ≤ 2 has probability ≈ 3e-8. 3 declared patterns per dataset: one base 2×, one 2× plus one 3×, and a seeded full bootstrap draw | (i) all copies share the original label; (ii) outer folds = G\*; (iii) in every outer **and** inner fold, all rows of the held-out base's copies are in the test set and none are in training; (iv) copies of one base have bit-identical P, pick and v; (v) θ̂\* = (1/(G·m)) Σ_b c_b Σ_i d\*_bi recomputed from per-base values equals the wrapper's estimate exactly; (vi) `leak_check` = 0 flagged rows |
| 3d positive control | 3c patterns with copies deliberately labelled as separate groups | `leak_check` flags every copied row: 100 % detection |
| 3e degeneracy | `replicate` (production entry point) on the F5 data with idx = [0, 0, 0] (G\* = 1) and with F6's own idx = [0, 0, 2] (G\* = 2); `replicate` on set B with an idx of G\* = 2; and `refit_eval_fixed_k` with G\* = 1 | every `replicate` call raises `DegenerateReplicate`, with no NaN result and no k = 1 fallback. `refit_eval_fixed_k` at G\* = 1 raises `ValueError`. The same F6 input therefore passes 3b on the fixture path and is rejected on the production path |
| 3f G\* moments | 10,000 seeded draws of idx only (no fitting) at G = 12 and G = 28 | the mean G\* is within 4 MC-SE of 7.776 and 17.886 |

**FAIL:** any sub-item not met.

### SV0-4: label relabelling

| sub | input | PASS iff | FAIL |
|---|---|---|---|
| 4a order-preserving | sets A + B; labels g → 1000 + 7g, rows fixed | all SV0-3a outputs exact (k compared per base identity) | any difference |
| 4b non-monotone | set B; 3 declared label permutations, rows fixed | all outputs exact | any difference is **FAIL-INVESTIGATE**. The only legitimate source is the order of summation over inner folds in `choose_k`; no tolerance is applied (U2) |
| 4c row-block reorder | set B; 3 declared block orders | **diagnostic only:** reports pick agreement, max\|ΔP\| and k agreement. Not gated, because the canonical layout (§3.1) removes row order from SV1 | — |

### SV0-5: H4 non-degeneracy calculator (amendment 2.2 Lemmas 1–7, erratum E2)

**Two independent routes:**
- closed-form expected values written below;
- the brute-force enumerator in `sv0_reference.py`, run on the small tables.

The calculator must equal both.

**Small tables** (3 training bases, m = 3, two abstract bins {0, 1}; no B2 mapping assumed):

| table | design | control | expected D | expected F (N1) | N3 | expected verdict |
|---|---|---|---|---|---|---|
| H-a | all rows distinct | S-base | 2³ = 8 | 1 | 1.0 | **limited exact set (D = 8 < 20)**, VALID |
| H-b | bins (2, 1) in every base, rows distinct | S-family-free | 1 | 6/9 = 2/3 | 1.0 | **single deterministic contrast**, VALID |
| H-c | as H-b, but one base's pair rows identical | S-family-free | 1 | 4/9 = 0.444 | 1.0 | **INVALID** (N1 < 0.50) |
| H-d | bins (3, 0) in one base, (2, 1) in two | S-family-free | 2 | 7/9 | 1.0 | limited exact set (D = 2), VALID |
| H-e | bins (1, 1, 1), K = 3 balanced | S-family-free | no group ≥ 2 | 0 | 0.0 | **INVALID** (identity control, Lemma 5; never labelled a "contrast") |
| H-f | all rows distinct | S-cf-conditional (cf block) | 8 | 1 | 1.0 | limited exact set, VALID |

**Planned-design tables** (27 training bases, m = 3; closed form only):
- S-base, distinct rows: D = 2^27 = 134,217,728, so a **genuine distribution** with 20 distinct draws; F = 1; N3 = 1.
- S-family-free, (2, 1) in every base: D = 1, F = 2/3, N3 = 1.
- The same with one identical-pair base: F = 52/81 = 0.6420.
- S-global over 81 records: D = !81, genuine; F = 1.

**Lemma checks on the exact P0 functions** (m = 3 fixture, seeded):
- **L1:** the prior is bit-identical under within-group permutation (binary Y gives exact sums).
- **L2:** with k = n_train, P is bit-invariant under within-base outcome derangement. With k = 1, at least one prediction
  changes (positive control).
- **L3:** the training mean and sd under row permutation are equal within relative 1e-12. Bit-identity is not claimed.
- **L4:** a cf-block swap keeping the set N unchanged leaves P bit-invariant.
  - **Revision 4b:** this is now gated on a deterministic hand-built fixture, L4F.
    - **The fixture.** Training rows (obs, cf) are (1, 1), (1, −1), (−1, 1) and (−1, −1), in bases 0, 0, 1, 1. Both columns
      have mean 0 and sd 1 exactly before and after the swap. The cf swap is r0↔r1 and r2↔r3. Y = [1,0], [0,1], [1,0],
      [0,1], and k = 2.
    - **Case A, query (1, 0.5).** D goes from [¼, 9⁄4, 17⁄4, 25⁄4] to [9⁄4, ¼, 25⁄4, 17⁄4]. The neighbours go from (0, 1) to
      (1, 0): the order changes, the set does not. P = [½, ½] and is bit-identical.
    - **Case B, the positive control, query (0, 1).** D goes from [1, 5, 1, 5] to [5, 1, 5, 1]. The set goes from {0, 2} to
      {1, 3}, and P goes from [5⁄6, 1⁄6] to [1⁄6, 5⁄6]. P must change.
    - The expected values were derived by hand and checked independently in exact rationals.
  - **The old synthetic version.** The B2 synthetic loop (k = 5) is kept as a **non-gated diagnostic**. It reports the
    unchanged and changed set counts and the invariance violations.
  - **Attempt 1.** Gated on the B2 loop, attempt 1 FAILED as vacuous: 0 of 36 queries kept their set. That evidence is preserved
    in `sv0/attempt1/`.
- **L5:** a singleton-stratum control gives V(π_M) − V(π_ctrl) = 0 exactly.
- **L6:** !1 = 0, !2 = 1, !3 = 2, !4 = 9 (by enumeration); 6^27 = 1.0235e21 (the amendment's "1.0e21").
- **L7:** m = 3, K = 2 gives N3 = 1 by pigeonhole; balanced m = 3, K = 3 gives N3 = 0.

**PASS iff** every value matches. **FAIL:** any mismatch.

This resolves the auditor's item 3 **for the arithmetic only**. Applying it to the actual frozen instance design needs the A2 draw
and the E-check (Stage 0a item 7, A6).

### SV0-6: generator and archived regression

**PASS iff:**
- `_synth(rng, fixed, G, 3)` returns X with shape (3G, 42) and base = repeat(arange(G), 3);
- Y is in {0, 1}, with shape (3G, 10);
- regeneration from the same seed is bit-identical (sha256 of X, Y and base bytes recorded);
- the archived suites pass in place: 52 tests (40 rev2/rev2.1 + 12 amendment).

**FAIL:** any deviation.

### SV0-7: interval constructors (fixtures; no coverage)

| item | input | expected | compare |
|---|---|---|---|
| CR1 SE (§E formula) | G = 3; d = base0 [1, 1], base1 [0, 0], base2 [1, 0] | √3/6 = 0.2886751345948129 | tol 1e-12 |
| t critical values | `t_ppf(0.95, df)`, df = 2 / 11 / 27 | 2.919986 / 1.795885 / 1.703288 (standard tables) | tol 1e-5 |
| percentile | values 1…20; 5 % and 95 % | 1.95 and 19.05 (linear) | tol 1e-12 |
| Wilson lower | (k, n, z) = (35, 40, 1.645), (34, 40, 1.645), (34, 40, 1.282), (33, 40, 1.282) | 0.7647, 0.7353, 0.7639, 0.7356 | tol 5e-4 |
| half-sample splits | G = 12 and 28; 40 splits; seed +31 | each split: two disjoint halves of ⌊G/2⌋ bases covering all bases; the 40 splits are distinct; identical on re-generation | exact |

**Note:** the Wilson helper takes z as a parameter. The one-sided versus two-sided choice (B10) is **not** made here.

**PASS iff** all items match. **FAIL:** any mismatch.

### SV0-8: guards and process determinism

**PASS iff:**
- within the run, each of these raises: `import mujoco`, `socket.socket()`, opening `artifacts/x`, opening `~/dev/.env`,
  writing outside `sv0/out/run<N>/`, `subprocess.run`, `multiprocessing.Process`;
- the AST scan of the `sv0/` files finds no `np.random.seed`, no `random.*` global calls and no coverage loop;
- after the run, no `mujoco*` module is loaded;
- **two separate processes** produce byte-identical `sv0_results.json` (timings live only in `sv0_env.json`).

**FAIL:** any guard does not fire, or any byte differs.

### 6.9 Overall classification

| result | condition | consequence |
|---|---|---|
| **PASS** | every gated item in SV0-0 to SV0-8 passes (4c is diagnostic) | an SV1 proposal may be **requested**. Requesting it is not approval |
| **FAIL** | any gated item fails | stop and report verbatim. Criteria are never edited after the run. A fix needs code re-review, and rerunning needs new approval |
| **FAIL-INVESTIGATE** | SV0-2 near-tie or SV0-4b | treated as FAIL until the owner and auditor rule |
| **ABORTED-RESOURCE** | a cap in §7 was breached | not a scientific result. One identical rerun is allowed, with no code change, after the cause is recorded. More needs new approval |

---

## 7. Resource limits (numeric; the owner may tighten them)

| limit | value |
|---|---|
| processes | 1 Python process per run; **2 runs** (SV0-8). No subprocesses or worker pools; the guards enforce this |
| threads | `OMP_NUM_THREADS = OPENBLAS_NUM_THREADS = MKL_NUM_THREADS = 1` |
| CPU time | ≤ **30 CPU-min per run**; ≤ **60 CPU-min total**, plus ≤ 5 CPU-min for the archived 52 tests |
| wall time | ≤ **10 min per check** and ≤ **30 min per run** (self-abort, checked inside the long loops); ≤ **75 min total** |
| RAM | start only if `MemAvailable` ≥ **3.0 GB**. Abort if `VmRSS` > **1.0 GB** or `MemAvailable` < **2.0 GB**. A 1-s watchdog thread reads `/proc/self/status` and `/proc/meminfo` (no new dependency); peak RSS (`VmHWM`) and minimum `MemAvailable` are logged |
| disk | outputs ≤ **50 MB**, all under `sv0/out/` |
| network | none from the SV0 process (socket guard); SSH and scp only for control and transfer |
| launch | on the VM, inside a detached `tmux` session `sv0` (it survives SSH drops and is not a local Claude background task) |

**Kernel-enforced backstops (revision 3)** sit above the in-process limits, so the in-process aborts fire first:

| mechanism | setting |
|---|---|
| `sudo systemd-run --scope` | `MemoryMax=1536M`, `MemorySwapMax=0`, `CPUQuota=100%` (1 core), `TasksMax=32` |
| `prlimit` | `--cpu=1800:1800` (30 CPU-min, SIGXCPU) |
| `timeout` | `--kill-after=60 1800` (30 min wall) |

- These tools are part of Ubuntu 24.04 (systemd, util-linux, coreutils). Their presence and cgroup-v2 controllers are verified in
  c1.
- **If `systemd-run` scopes are unavailable,** the pre-declared fallback is `prlimit` + `timeout` + the in-process watchdog
  (U12).
- The numeric caps are **unchanged from revision 2.** The 3 GB start threshold is trivially met on a 32 GB VM and is kept.

**Runtime estimate** [ASSUMP]:
- The handoff's "seconds" is probably optimistic.
- G = 28 exact-P0 fits occur in SV0-2 (1 dataset), SV0-3a and SV0-4a (3 datasets each, both policies): about 14 two-policy LOBO
  runs at an assumed 40–60 s each, which is about 10–14 min.
- The pure-Python reference at G = 28 is assumed to take ≤ 5 min.
- G = 12 work is about 10× cheaper.
- **Expected 15–22 min per run.** If the first run exceeds 30 min, the result is ABORTED-RESOURCE, not a silent cut.
- SV0 timings are **not** the SV1a measurement.

**VM timing caveat:** the per-thread speed of a cpu-d3 vCPU relative to the local i5-13500H is unknown, so the estimate stays
[ASSUMP].
- An ABORTED-RESOURCE caused by a **deterministic** time overrun is not rerun under the same caps; a revised cap needs new
  approval (U14).
- The one identical rerun of §6.9 applies only to a **transient external** cause, such as another process on the VM.

**The revision-2 local precondition (1.4 GB free) no longer applies:** SV0 does not run on Windows. Windows only edits files,
makes the bundle, runs SSH and scp, and verifies the returned hashes.

## 7A. VM execution procedure, cost and stop (revision 3)

### 7A.1 Owner prerequisite P (no cost)

**Status (2026-10-23): DONE.**
- Login was restored, and `AUTH_BLOCKED` is absent.
- `watchdog.log` shows `ok state=STOPPED` for `[main]` and `[batch]` at 16:18 and 16:27.
- **Remaining condition:** the scheduled task does not run on battery (`DisallowStartIfOnBatteries`). The PC must be on AC power
  during c1 and c2, and the operator checks this before each `start`.

1. Run `python infra/nebius/forge_cloud.py login` in a terminal (it opens the browser once and clears `AUTH_BLOCKED`).
2. Confirm that `infra/nebius/watchdog.log` then shows `ok state=STOPPED` for `[main]` and `[batch]`.
   - The Windows scheduled task `CreatureForgeNebiusWatchdog` runs every 15 min. Without a valid login it cannot stop the VM.
   - The PC must stay on and awake during c1 and c2.

### 7A.2 c1: read-only VM inspection session (paid)

Purpose: verify the environment live before approving execution. No code is transferred, nothing is installed, no SV0 code runs.

**Steps:**
1. `forge_cloud.py status` (main), and status with `CF_VM=batch`. Batch must not be RUNNING.
2. `forge_cloud.py start`. Then **immediately** `forge_cloud.py extend --hours 0.75`, which sets the deadline to now + 45 min,
   verified on the VM.
3. One read-only `forge_cloud.py exec` with these commands:
   - `uname -a`, `/etc/os-release`, `nproc`, `lscpu` (model and flags), `/proc/meminfo`, `df -h ~`;
   - list `~/venvs/*` and `~/dev/venvs/*`;
   - **every command below runs through the candidate's own interpreter, `"$V/bin/python"`**, never a `python` or `pip` from
     PATH (R4-4). Also recorded: `readlink -f "$V/bin/python"`, and `sys.prefix` (which must equal `$V`, with
     `sys.prefix != sys.base_prefix`);
   - `"$V/bin/python" -I -B -c` printing `sys.version`, `numpy.__version__`, `numpy.show_config(mode="dicts")` (build and BLAS
     section), `platform.platform()`, `importlib.util.find_spec("scipy")`, and `importlib.util.find_spec("creature_forge")`.
     The last one is the origin of any installed copy and **records the shadowing risk** that §5.1 neutralises; `find_spec` of
     a top-level package does not execute it;
   - the **distribution manifest** sha256, from the same snippet that §5.1 step 8 uses: sorted `Name==version` over
     `importlib.metadata.distributions(path=<site-packages under sys.prefix>)`;
   - `"$V/bin/python" -I -m pip freeze --all | sha256sum`. If `-m pip` is unavailable, the result is recorded as "pip absent", and
     the manifest alone is the package fingerprint;
   - `git --version`, `which sha256sum timeout prlimit systemd-run tmux`, `/sys/fs/cgroup/cgroup.controllers`;
   - `uptime`, `tmux ls`, `pgrep -a python` (observe only; nothing is killed).
4. `forge_cloud.py stop`. Then poll `status` until **STOPPED**. Never stop from inside the VM: the platform restarts the VM after
   a guest poweroff.
5. Record `forge_cloud.py spend` and deliver the fingerprint.

**Venv acceptance criteria** (pre-declared):
- Python 3.11 or 3.12;
- numpy in `>=2.4.6,<2.6`;
- scipy absent;
- a working `numpy.show_config()`.

**Preference order:** `~/venvs/creature-forge` first (recorded Python 3.12.3, numpy 2.5.4), then the dev-slot venvs in name
order. If none qualifies, report and stop. Option 2 (§4) would then need its own install approval.

**Also checked:**
- `MemAvailable` ≥ 3 GB;
- no heavy job running (1-min load < 1.0; a busy VM is reported, never disturbed);
- cgroup v2 has the `memory`, `cpu` and `pids` controllers.

### 7A.3 c2: SV0 execution session (paid)

1. **Preconditions:** P done; c1 fingerprint approved; (a) and (b) done; (b) code audited.
2. **Locally (Windows)**, per §4 "HEAD and code transfer":
   - check that `git -C cf-experience rev-parse HEAD` equals the pinned hash: `afe33ca…`, or the separately approved
     documentation commit. If it does not, stop;
   - `git -C cf-experience bundle create %TEMP%\sv0\repo.bundle HEAD`, then `git bundle verify` and `git bundle list-heads`,
     which must show the pinned hash. Uncommitted edits are not in the bundle;
   - record the sha256 of the bundle and the 3 `sv0/*.py` files, and write `expected.json` (pinned hash, code sha256 values, c1
     fingerprint values) from the (c2) approval text.
3. `forge_cloud.py start`, then **immediately** `forge_cloud.py extend --hours 2.0`, which sets the deadline to now + 2 h,
   verified.
4. `scp` the bundle and the code. On the VM:
   - verify the sha256 values;
   - run the bundle clone procedure of §4 exactly:
     - `git -c core.autocrlf=false clone -q --no-checkout repo.bundle ~/sv0/repo`;
     - then `git -C ~/sv0/repo config core.autocrlf false`;
     - then `git -C ~/sv0/repo checkout -q --detach <pinned hash>`.

     `autocrlf=false` is configured before the first checkout;
   - copy the code to `experiments/causal_engineer/dev/experience_p05/sv0/`.
5. **Launch both runs sequentially** in `tmux new -d -s sv0`. Before each run, the launcher writes `~/sv0/pre/runN.head`,
   `.status` and `.freeze` (§5.1). Each run is launched as:

   ```bash
   sudo systemd-run --scope --quiet --uid=forge --gid=forge -p MemoryMax=1536M -p MemorySwapMax=0 -p CPUQuota=100% -p TasksMax=32 \
     env -i HOME=/home/forge PATH=/usr/bin:/bin LC_ALL=C.UTF-8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
     prlimit --cpu=1800:1800 timeout --kill-after=60 1800 \
     "$V/bin/python" -I -B experiments/causal_engineer/dev/experience_p05/sv0/sv0_run.py --run N --expected /home/forge/sv0/pre/expected.json --out experiments/causal_engineer/dev/experience_p05/sv0/out/runN
   ```

   - The working directory is `~/sv0/repo`.
   - The operator monitors with `forge_cloud.py exec "tmux capture-pane -pt sv0"` and `/proc` readings. Polling is limited to the
     session.
6. **When both runs end:**
   - on the VM, compare `run1/sv0_results.json` with `run2/sv0_results.json` byte for byte (`cmp`);
   - write `out/SHA256SUMS`;
   - `scp -r` the `out/` directory back to `cf-experience/experiments/causal_engineer/dev/experience_p05/sv0/out/`;
   - verify locally with Git's `sha256sum.exe -c`.
7. **Stop:** `forge_cloud.py stop`, poll `status` until STOPPED, record `forge_cloud.py spend`, report.
8. **Left on the VM:** `~/sv0` (synthetic code and outputs only). Nothing is deleted without approval.

### 7A.4 Cost (main VM rates in `forge_cloud.py`: $0.264/h compute + $0.0049/h disk; quoted rates, not a billing statement)

| item | expected wall time | expected compute cost | deadline-bounded (deadline + 15 min watchdog lag) |
|---|---|---|---|
| c1 inspection | 15–20 min | $0.07–0.09 | 60 min → $0.27 |
| c2 execution | 65–90 min (boot 5, transfer and preflight 10, archived tests 2, 2 runs of about 20–30 min, pull and stop 10) | $0.29–0.40 | 2 h 15 min → $0.60 |
| **total** | about 1.4–1.8 h | **≈ $0.36–0.49** | **≈ $0.87** |

**Not incremental:** the stopped boot disk already accrues about $0.117/day.

**Budget state:**
- The ledger estimate now is **$89.819** (`forge_cloud.py spend`, local arithmetic only). The handoff's $89.405 predates the
  latest disk accrual.
- The headroom under the existing $96 `SPEND_CAP_USD` is **$6.18**. No cap change is requested.
- The owner-reported VM credit is $40.04 (unverified).
- Token Factory: $0, never used.

### 7A.5 Hard spending limit: $2.00 for c1 + c2 combined

**Measure:** the ledger delta from the pre-c1 baseline. It is conservative: disk accrual between sessions counts against the
limit.

**Rules:**
- After start, never leave a deadline above **0.75 h (c1)** or **2.0 h (c2)**.
- **No `extend` beyond these** without new approval.
- If the delta reaches **$1.50**, stop immediately through the API, whatever the progress.
- If SSH is lost, or any step fails, stop through the API, confirm STOPPED, then report.
- **The deadman timer is not a backstop.** It powers off from inside, and the platform has restarted the VM after a guest
  poweroff twice.

**Backstops, in order:**
1. operator stop through the API;
2. the Windows watchdog at the deadline (requires P);
3. the owner.

**Honest limit:**
- No provider-side automatic hard cap is configured in this tooling. Whether Nebius billing offers one is [UNVERIFIED].
- If every backstop failed (PC off, session lost), the VM would bill $0.269/h until stopped, reaching $2 after about 7.4 h.
- That is why P (a valid login, so the watchdog works) and an attended session are preconditions.

---

## 8. Outputs (uncommitted; in `sv0/out/`)

| file | content |
|---|---|
| `sv0_results.json` | per item: check id, input sha256 (dataset bytes, pinned blobs), expected value, observed value, comparison rule, PASS/FAIL, margins (SV0-2). Deterministic, with no timestamps |
| `sv0_env.json` | the full VM fingerprint (Python, numpy, `show_config` BLAS, platform, CPU model and flags, venv path, `pip freeze` sha256), pins, HEAD, thread variables, the active cgroup and prlimit settings, per-check wall and CPU seconds, peak RSS (`VmHWM`), minimum `MemAvailable`, start and end times |
| layout (revision 3) | `out/run1/` and `out/run2/` each hold `sv0_results.json`, `sv0_env.json` and `sv0_report.md`; `out/SHA256SUMS` covers both runs and the 3 code files |
| `sv0_report.md` | at most one page: the classification, the failures verbatim, the SV0-4c diagnostic, and the fixed wording of §1 |
| `SHA256SUMS` | the outputs plus the 3 code files |

**Verification of the approved items:**
- **V-a1:** a byte scan for `[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]` over all 46 A0 files plus the two edited documents finds 0 hits.
- **V-a2** (revision 4). It runs on the edited, uncommitted worktree and has two parts.
  1. **Reproduction:** the C3 PowerShell block runs as written and prints 33 OK, the 3 suites OK, 2 MATCH and
     `STATUS UNCHANGED`. The two regenerated outputs in `%TEMP%\cf_a0_repro` match the committed files by sha256.
  2. **Only the intended files changed:**
     - `git status --porcelain --ignored` must equal exactly ` M docs/EXPERIENCE_P05_HANDOFF.md` and
       ` M docs/plans/EXPERIENCE_P05_PROTOCOL.md`, plus the ignored (`!!`) lines recorded before editing, which are compared
       verbatim;
     - `git diff --name-only` must list exactly those two paths;
     - `git diff --numstat` is reported;
     - for the protocol, `git diff -U0` shows a change to line 7 only;
     - `git ls-files --others --exclude-standard` prints nothing;
     - `git rev-parse HEAD` is still `afe33ca…`.
- **V-b:** `git status` shows only new files under `sv0/`. The sha256 of the 3 code files is reported. Nothing has been
  executed.
- **V-c1:** the fingerprint table; VM STOPPED confirmed by `status`; spend delta reported.
- **V-c2:**
  - the SV0-0 output;
  - 2 runs with `sv0_results.json` byte-identical (`cmp` on the VM);
  - the classification of §6.9;
  - resource usage within §7;
  - the returned `SHA256SUMS` verified locally;
  - VM STOPPED confirmed;
  - spend delta ≤ $2.00 for c1 + c2.

---

## 9. What SV0 can and cannot resolve

| item | SV0 | needs |
|---|---|---|
| Correctness and determinism of the P0 pipeline, refit wrapper, H4 calculator and interval helpers on synthetic fixtures | **resolves** | — |
| Auditor item 3, the derangement regimes at D5 | **resolves the arithmetic** | the actual frozen design: A2 draw + E-check, then Stage 0a (A6) |
| B10: S per cell, Wilson sidedness, R_refit matching, SV1 caps | no (owner decisions) | owner, before SV1; SV1a timing |
| Coverage or admissibility of any interval method; bootstrap consistency; G = 28 behaviour | no | **SV1** (synthetic only) |
| B1, B2, B3, B4, B6 | no (owner decisions) | owner |
| B5 verification-seed namespace | no (the SV0 seeds are unrelated) | owner / A6 |
| B7 analysis runner | no | owner / A11 |
| B8 `cma_fn`, B9 bounds-screen compile | no | A6, Stage 0a / 0b |
| B13 | no | auditor |
| B11 cap | no | measured A9 costs |
| T3 eligibility, S8 diagnosis independence, q, ρ, p_pass, costs, bounds feasibility, real learning inflation, **any transfer effect** | no | **physical experiments**: Stage E, Stage 0b, pilot, campaign |

---

## 10. Owner settings preserved, and unresolved decisions

**Preserved unchanged:**
- D1 m = 0.10;
- D2 P-B, 28 confirmatory bases;
- D7′ pilot 4 T1-panel + 2 T3;
- D3 repair budget 300 with 8 training seeds;
- D5 3 instances per base, 2 severity bins.

SV0 uses only m = 3 and two abstract bins.

**Budget:** the $6.595 cap still binds. The reported balances ($40.04 VM, $47.00 Token Factory) are not spending authority. SV0
costs $0.

**Unresolved (flagged; the proposal is stated, nothing is decided silently):**

| id | question | proposal |
|---|---|---|
| U1 | Location and commit status of the SV0 code and outputs | `experience_p05/sv0/`, uncommitted until separately approved |
| U2 | SV0-4b strictness | exact; any deviation is FAIL-INVESTIGATE |
| U3 | Row order | canonical layout; SV0-4c is diagnostic |
| U4 | Optional fast re-implementation | excluded from SV0; reconsider after SV1a, with a bit-identity gate on 20 fixed datasets |
| U5 | "B" names both the repair budget (300) and the bootstrap refit count (200 vs 40) | label them B_repair and R_refit in future documents; no value changes |
| U6 | Final caps | §7 values |
| U7 | Order, and what c2 pins | (a) before (c), so the documents the auditor reads are correct first. (a) has **no effect on SV0-0**: uncommitted edits do not change HEAD and are not in the bundle. c2 pins `afe33ca68b73da313d720db0939ef382bc1cae91`, unless the owner separately approves a commit of (a); then it pins that commit. The SV0 code is never committed for c2; it travels as 3 untracked files by `scp`, verified by sha256 (§4, §5.1) |
| U8 | Inclusion of SV0-7 | include |
| U9 | Pin `experience_audit.py` | pin `12733798…` |
| U10 | SV1 handling of G\* ≤ 2 replicates | SV1 protocol decision; SV0 only checks the raise |
| U11 | Which existing VM venv | chosen in c1 by the §7A.2 criteria; named by the owner in (c2) |
| U12 | Use `sudo systemd-run` cgroup limits on the VM | yes; fall back to `prlimit` + `timeout` + the watchdog if unavailable |
| U13 | c1 and c2 as separate sessions | yes (staged). Merging saves one boot (about $0.03) but removes the review point |
| U14 | Rerun after ABORTED-RESOURCE | only for a transient external cause; a deterministic overrun needs a new cap approval |
| U15 | How the $2 limit is measured | ledger delta from the pre-c1 baseline, including disk accrual |
| — | B10 components | open; not needed for SV0 |

---

## 11. Approval request

> **CF-V2-P05-SV0-APPROVAL-REQUEST (2026-10-23)**
>
> **Preparation (complete; no approval needed):** this document. No code written, nothing executed, no file changed.
>
> Each item below is a separate approval. Approving one does not authorise another.
>
> **[ ] (a) Documentation edits:** apply C1–C3 (§2) to `docs/EXPERIENCE_P05_HANDOFF.md` and one line of
> `docs/plans/EXPERIENCE_P05_PROTOCOL.md`. Run V-a1 and V-a2. Show the diff. **No commit or push** unless separately approved.
>
> **[ ] (b) SV0 implementation (no execution):** create only `sv0_lib.py`, `sv0_reference.py` and `sv0_run.py` under
> `experiments/causal_engineer/dev/experience_p05/sv0/`, per §3–§6. Stop, then deliver the code and its sha256 for audit.
> **Not even the preflight is run.**
>
> **Owner prerequisite P (no cost, owner action):** run `python infra/nebius/forge_cloud.py login`, then confirm the watchdog
> logs `ok state=STOPPED` for main and batch.
>
> **[ ] (c1) VM inspection session (paid):** §7A.2 on the existing main VM only.
> - Deadline 45 min; read-only commands; no code transfer, no install, no SV0.
> - Stop through the API and confirm STOPPED.
> - Expected cost about $0.08.
> - Deliver the fingerprint and the venv choice (U11).
>
> **[ ] (c2) SV0 execution (paid):** run SV0-0 to SV0-8 per §6 under §7 and §7A.3.
> - HEAD = `afe33ca68b73da313d720db0939ef382bc1cae91` (or the separately approved documentation commit, named by the owner);
>   SV0 code = the 3 files with the (b) sha256 values, transferred uncommitted; venv and fingerprint = `<named from c1>`; U1–U15
>   as decided.
> - 2 sequential runs; deadline 2 h; no extensions.
> - Stop through the API and confirm STOPPED.
> - Report the §6.9 classification verbatim and stop.
>
> **Spending authority requested:** **≤ $2.00 combined for c1 + c2** (ledger delta, §7A.5), inside the existing $96 cap. The
> cap is not changed. Expected about $0.36–0.49.
>
> **Never covered by (a)–(c2):**
> - SV1a/SV1b or any coverage or timing calibration; G = 46;
> - harness, MuJoCo or physics; Stage 0a/0b, Stage E, pilot, campaign;
> - the batch VM; creating or deleting any VM;
> - `pip install` or venv creation;
> - Token Factory or paid inference;
> - sealed, held-out or `artifacts/vm` data;
> - V1; commit or push; destructive Git operations.
>
> **Recommended sequence:** (a) → (b) → auditor code review → P → (c1) → owner confirms the fingerprint → (c2).

*End of proposal. Stopped for review.*
