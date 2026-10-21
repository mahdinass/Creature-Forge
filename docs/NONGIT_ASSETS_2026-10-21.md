# Git-ignored assets: inventory and backup (2026-10-21)

The video takes, rough cuts, screen captures and raw scientific archives are deliberately not in Git: they are large, and
some raw files are not redacted. Git holds only this record and the per-file checksums.

- Per-file inventory: `docs/archive/nongit_assets_2026-10-21.inventory.tsv` (path, bytes, SHA-256, category; 1,994 files,
  846,227,094 bytes). Paths start at `artifacts/` (inside the main checkout) or at `creature_forge_runs/` (a sibling of
  the main checkout, outside every worktree).
- Archive checksums: `docs/archive/nongit_assets_2026-10-21.SHA256SUMS`.
- The text files were scanned for API keys, bearer and IAM tokens and private keys before packaging: no hits.

## What is covered
| Directory | Files | MB |
|---|---|---|
| `artifacts/vm` (DS-1 / HDB bench, causal-engineer and stage runs, VM captures, ledger backups) | 621 | 576.4 |
| `artifacts/capture` (W1/W2 Studio captures, video takes 2 and 3, rough cut v1) | 70 | 133.8 |
| `artifacts/nebius_r1` (R1 runs, 2026-10-14) | 760 | 79.9 |
| `artifacts/runs` (TA-1/DO-1 run archive, W1a check, W1/W2 exports) | 302 | 29.3 |
| `creature_forge_runs/` (DO-1 r0 pilot, FA-1C phases, DO-1 source review, demo exports) | 182 | 17.8 |
| `artifacts/screenshots-redesign` | 34 | 8.2 |
| `artifacts/phase0`, `demo_runs`, `investigations`, `nebius` | 14 | 0.8 |

The video files that matter for the submission are these:
- `artifacts/capture/video_2026-10-21/rough_cut_v1/rough_cut.mp4` (17,855,770 bytes, sha256 `83b75cba9cd0ac1c…`);
- `rough_cut_clean.mp4` (18,362,355 bytes, `60f1f5152c575aeb…`);
- the source take `take3-gpu/take.mp4` (39,847,919 bytes, `b13f4d9cf9c869ea…`).

The full hashes are in the inventory.

## Archives
They live on the owner's laptop, outside every repository, at `%USERPROFILE%\CreatureForge-archive\2026-10-21\`.

| File | Bytes | SHA-256 | Contents |
|---|---|---|---|
| `creature-forge-science-raw-2026-10-21.tar.gz` | 120,762,422 | `d1142916cc4d600b8f70f9b653134b20df19051f946be8f29372b6f5ddcb78a9` | every scientific raw file above: 1,832 files, `artifacts/vm/capture` excluded |
| `creature-forge-capture-2026-10-21.tar` | 273,520,640 | `befa715a536f682ca039fca3b05e0693a1777ef2023588931e5d80b35c6d67fd` | `artifacts/capture`, `artifacts/vm/capture`, `artifacts/screenshots-redesign`: 162 files, including all video |

The same folder holds `INVENTORY.tsv`, `INVENTORY_SUMMARY.json` and `ARCHIVES.sha256`.

## Off-machine copies: OWNER ACTION, not done yet
On 2026-10-21 the agent's attempt to upload the scientific archive as a private draft release was blocked by the
tool-permission policy, so nothing was uploaded. No other storage destination is configured or approved, so the owner
copies both archives.
1. Copy the whole folder `%USERPROFILE%\CreatureForge-archive\2026-10-21\` (about 395 MB, 5 files) to a private
   destination the owner controls, such as an external disk or a personal private cloud drive. The video is in
   `creature-forge-capture-2026-10-21.tar`; do not put it anywhere public.
2. On the copy, run `sha256sum -c ARCHIVES.sha256` (Git Bash); both lines must print `OK`.
3. Optional, for the scientific archive only: a draft release of the private repository, as in
   `ARTIFACT_ARCHIVE_2026-10-18.md`. Run `gh release create archive-raw-2026-10-21 --draft -R mahdinass/Creature-Forge
   creature-forge-science-raw-2026-10-21.tar.gz ARCHIVES.sha256 INVENTORY.tsv`, and never publish it.

## Recovery (Git Bash, from the main checkout)
```bash
D=$(mktemp -d)
cp ~/CreatureForge-archive/2026-10-21/creature-forge-*-2026-10-21.tar* ~/CreatureForge-archive/2026-10-21/ARCHIVES.sha256 "$D"/
( cd "$D" && sha256sum -c ARCHIVES.sha256 )
cmp <(tr -d '\r' < "$D/ARCHIVES.sha256") <(tr -d '\r' < docs/archive/nongit_assets_2026-10-21.SHA256SUMS)
tar -xzf "$D/creature-forge-science-raw-2026-10-21.tar.gz" -C "$D"
tar -xf "$D/creature-forge-capture-2026-10-21.tar" -C "$D"
```
Each extracted file's SHA-256 must equal its row in the inventory.
