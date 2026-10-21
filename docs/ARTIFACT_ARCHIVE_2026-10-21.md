# TA-1 / DO-1 run archive (2026-10-21)

This archive preserves the raw outputs of the FA-1C TA-1 / RV-1 phases and the DO-1 pilot. Before 21 October these lived only
in `C:\Users\<user>\.vscode\creature_forge_runs\`, outside every repository.

They are now kept in three places. The sources are unchanged.

| Copy | Where | Contents |
|---|---|---|
| Original | `..\creature_forge_runs\` (next to the repository) | 76 files, 2,378,965 bytes. Left untouched. |
| Git-ignored archive | `artifacts/runs/2026-10-20_21/` in the main checkout | Byte-identical copy of all 76 files, including `vm_copy/` and the DO-1 source-review bundle. |
| Tracked evidence | `experiments/do1/l4_r0/` and `experiments/ta1/*/` | The run records, manifests, logs, launch scripts and analysis scripts (7 with local account paths redacted, see below). Each directory has a `SHA256SUMS` of the tracked copies. The records are stored byte-exact (`-text` in `.gitattributes`) and frozen by `experiments/FROZEN_MANIFEST.json`. |

`docs/archive/runs_2026-10-21.SHA256SUMS` lists the SHA-256 of all 76 original files, by path relative to `creature_forge_runs\`.

## Independently audited hashes
ChatGPT's raw-artifact audit of DO1-L4-r0 (21 Oct 2026, Notion FA-1C record) checked these. The tracked and staged copies match.
- `experiments/do1/l4_r0/do1_l4_r0.jsonl`: `00a8db20b9b3ab186b935f2062a9a78d411a4d2a512e289e8aa1e4c39a5e263b` (507,277 bytes)
- `experiments/do1/l4_r0/do1_l4_r0.jsonl.manifest.json`: `55fe2aa85d772bab7b70623279721ac46de62087246fc9b8b84a5ac2a8fa9a17`
- The manifest pins harness commit `e9d2379def2546cedcc9ce5c3cc2aa22b9746392`.

## Tracked directories
| Directory | Source run | What it is |
|---|---|---|
| `experiments/do1/l4_r0/` | `do1_l4_r0_pilot_2026-10-21` | DO1-L4-r0, main VM. Frozen r0 PARTIAL 19/24; DO-1 r0 FULL 21/24, confirmation 22/24. `vm_copy/` is omitted because it duplicates the files; `vm_sha256.txt` verifies the tracked copy. |
| `experiments/ta1/phase1a_2026-10-20/` | `fa1c_phase1a_2026-10-20` | RV-1 Phase 1A re-verification, local Windows run. PASS. |
| `experiments/ta1/phase1b_2026-10-20/` | `fa1c_phase1b_2026-10-20` | TA-1 Phase 1B, L1 paired pilot, main VM. |
| `experiments/ta1/phase1b_followup_2026-10-21/` | `fa1c_phase1b_followup_2026-10-21` | Read-only follow-up analysis of Phase 1B. |
| `experiments/ta1/x1_d3_2026-10-21/` | `fa1c_x1_d3_2026-10-21` | X1 post-hoc verification of the discarded candidate d3, local run. |
| `experiments/ta1/a1_l4_pilot_2026-10-21/` | `fa1c_a1_l4_pilot_2026-10-21` | Amendment A1, L4 paired control and treatment pilot, main VM. |

Archive only (not tracked):
- `do1_source_review_2026-10-21/`: the review ZIP for `7bced24` plus its staged copy. It is a source snapshot; the source itself is already in Git.
- `do1_l4_r0_pilot_2026-10-21/vm_copy/`.

## Checks run on 2026-10-21
- `sha256sum -c` of every VM list (`vm_sha256.txt`) and local list (`local_sha256.txt`) against the tracked copies: all OK before the redaction below. Afterwards, `experiments/do1/l4_r0/local_sha256.txt` fails by design on the redacted `analysis_do1_l4_r0.py` only; it still verifies the archived original.
- The archive copy matches the originals: 76/76.
- `python scripts/freeze_manifest.py --check`: 316 frozen records match.
- **Secret scan of the tracked copies:**
  - Patterns: Bearer tokens, `v1.` key shapes, `sk-`, `ghp_`/`gho_`, AWS, private keys, `NEBIUS_API_KEY=` assignments.
  - Result: 0 hits.
- **Publication redaction (2026-10-21, owner-approved).** Seven files, as copied, contained absolute local Windows paths with the account name:
  - the manifests and logs of the two locally run phases (RV-1 1A, X1);
  - three analysis scripts.

  Their **tracked copies** replace only the account segment after `C:\Users\` with `<user>`, in all three spellings. That is 35 replacements, and nothing else changes.
  - The byte-exact originals stay in the git-ignored archive; their SHA-256 are in `docs/archive/runs_2026-10-21.SHA256SUMS`.
  - Per file, `docs/archive/redactions_2026-10-21.json` records the original SHA-256, the redacted SHA-256 and the replacement count.
  - `python scripts/redact_local_paths.py --check` and `tests/test_redactions.py` verify the tracked copies, and re-derive them from the originals when the archive is present.
  - The per-directory `SHA256SUMS` cover the tracked copies. The run's own `local_sha256.txt` / `vm_sha256.txt` are kept byte-exact and verify the originals: in `experiments/do1/l4_r0/`, `local_sha256.txt` lists the original `analysis_do1_l4_r0.py`.
  - No audited file was affected. `do1_l4_r0.jsonl` (`00a8db20…`) and its manifest (`55fe2aa8…`) contain no local Windows path.
  - No pinned commit contains these files. Older, already-pushed docs and tests (`ea9e729`) still contain local paths; this redaction does not touch them.

## Recovery
1. **Tracked copies:** check out the branch, then run `sha256sum -c SHA256SUMS` in each directory.
2. **Full set:** from `artifacts/runs/2026-10-20_21/`, run `sha256sum -c ../../../docs/archive/runs_2026-10-21.SHA256SUMS`.
3. **Off-machine copy** (owner action): zip `creature_forge_runs\` to a drive and check it against `docs/archive/runs_2026-10-21.SHA256SUMS`.
