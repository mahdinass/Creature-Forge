# P05-SV0 evidence manifest (closed 2026-10-23)

**Outcome:** SV0 is **PASS** on attempt 2. Attempt 1 was **FAIL** (a vacuous SV0-5 L4 fixture) and is preserved below as part
of the permanent audit history.

**Fixed wording:** "SV0 verifies implementation correctness and determinism on synthetic fixtures only; it establishes no
coverage, inference validity or transfer."

**Proposal of record:** `PROPOSAL_SV0_rev4b.md`.
- Verbatim source sha256: `567a14fee6deab29bc09de8ff03f2a39314a71c6ec1e53b0571a5a525e12d9a0`.
- Published (2026-10-24) sha256: `283d39a12dbd9fc40637744bf5f5ea71ba6d40106aac354dd90312d132cb4718`.
- The only difference: one local Windows profile path was replaced by `%USERPROFILE%\` before committing, so that no
  personal path is tracked. No other byte changed.

## Provenance

| item | value |
|---|---|
| repository commit (bundle, `--no-checkout`, `core.autocrlf=false`) | `afe33ca68b73da313d720db0939ef382bc1cae91` |
| P0 blobs (git sha1) | `experience_p0.py` `dcfb1f29…`, `experience_bank.py` `38aed182…`, `experience_audit.py` `12733798…`, `__init__.py` `e69de29b…`, `scripts/exp_p0_audit.py` `dbaa4d34…` |
| machine | Nebius main VM `computeinstance-e01g6rhpgcpnf1bfbr`, cpu-d3, 8 vCPU (4 cores × 2 SMT), AMD EPYC-Genoa |
| venv | `/home/forge/venvs/creature-forge` |
| fingerprint | Python `3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]`; numpy 2.5.4 (show_config sha256 `2ab35740851adcdddd763d6a5fef42309f1c7d9717e94fa653d4c3b006dba8f6`); `Linux-6.11.0-1016-nvidia-x86_64-with-glibc2.39`; CPU flags sha256 `2635ea8b7a00dd791d4e50e49ebdfcdf622915591fbd1f412e241445694db92b`; distribution manifest sha256 `af2cf766ac30a5fa1067ef865601d92e10a535907f29d942160b5dde34a7a38d` (29 dists); pip freeze sha256 `def4117c52a6141453c0402277d5877fa32651bc70b6a3a2f6deb7a5db9f29f2` |
| limits (active, from `sv0_env.json`) | systemd scope `memory.max` 1610612736, `memory.swap.max` 0, `cpu.max` 100000/100000, `pids.max` 32; `RLIMIT_CPU` 1800/1800 |

## Attempt 2: PASS (current evidence, in `out/`)

| file | sha256 |
|---|---|
| `sv0_lib.py` | `7ca9658df2fe3c22495b45a63f6f73c2e85316dbc7d06104632bbf354de8cde2` |
| `sv0_reference.py` | `ec34f409aa77647df097f0f1e32fdae8dc6ddd244de3a9f42e5ea19baf4c60f8` |
| `sv0_run.py` (revision 4b, with the L4F fixture) | `03e7a2f02ff8b03ddfbd383c60007ab22bdcc15721aedd1c6406588d198ee6a0` |
| `out/run1/sv0_results.json` = `out/run2/sv0_results.json` (byte-identical) | `861372bd1c0023cc0abccfddca66e649f601b40056f52a90481634e09d059088` |
| `out/SHA256SUMS` (9 entries: both runs plus the 3 code files) | `492e0297dc1dd4f74836d2c857ec985fd665c5cb8b20d01a9977690deea29e06` |
| `out/sv0_out.tgz` (as retrieved from the VM) | `86d3313f2b41350c413336c82839c782c6f24359e0d5ca2b0d8c05d5776a161a` |

**Results:**
- SV0-0 50/50, SV0-1 23/23, SV0-2 12/12, SV0-3 104/104, SV0-4 30/30 (4a 12, 4b 18; plus 18 4c diagnostics), SV0-5 36/36,
  SV0-6 34/34, SV0-7 10/10, SV0-8 10/10.
- Every item in SV0-1 to SV0-4, SV0-6 to SV0-8 and the 26 non-L4 items of SV0-5 is identical to attempt 1. In SV0-0 the only
  difference is the expected `sv0_run.py` hash.

## Attempt 1: FAIL (permanent audit history, in `attempt1/`, read-only)

| file | sha256 |
|---|---|
| `attempt1/sv0_run.py` (revision 4a) | `0708b7e8a810297c4e00d0749540d03fe4232f97647fe9aaf328f90464484ad8` |
| `attempt1/out/run1/sv0_results.json` = run 2 | `d73e46f6976d5ea0234eed20359b329976febdd18b1eca406a79780a3202a21e` |
| `attempt1/out/SHA256SUMS` | `d0150a74b236b4b4d6721bb8367075961aef4112d756bee8e429119787bd7cf9` |
| `attempt1/out/sv0_out.tgz` | `8bf78257820dbe0a3edebc49541603b672d5de814d6efe820888ee8e08a74cfa` |
| `attempt1/PROVENANCE.txt` | `b5be6e11153911da9026e4dcd2feb20c0424e448d9dcb91173f4636552be7274` |

**Failure:** SV0-5 L4 was gated on the B2 synthetic loop, in which 0 of 36 queries kept their k = 5 neighbour set. The test was
therefore vacuous. It was not a counterexample, and P0 was not at fault.

**Fix:** revision 4b, owner-approved. A hand-built fixture L4F (Case A invariance, Case B positive control) is now gated, and
the B2 loop is a non-gated diagnostic.

## Verification

```bash
cd experiments/causal_engineer/dev/experience_p05/sv0/out && sha256sum -c SHA256SUMS            # 9 OK (attempt 2)
cd ../attempt1/out && sha256sum -c SHA256SUMS                                                    # 9 OK (attempt 1, old code)
```

## Other copies and operations

- **VM copies:** `~/sv0` (attempt 2) and `~/sv0_attempt1` (read-only) on the main VM.
- **Cost:** the ledger went from $89.865 to $89.911 for c1, c2 and the rerun ($0.046).
- **Git:** the two `out/launcher/launcher.log` files are git-ignored (`*.log`), so any commit must force-add them. Nothing has
  been committed.
