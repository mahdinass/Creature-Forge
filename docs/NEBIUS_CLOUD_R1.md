# Nebius CPU VM for the R1 experiment (2026-10-14)

No GPU, no inference API. Claude Code and Codex stay on the Windows machine and drive the VM over SSH.

## Resource
| | |
|---|---|
| Region / project | `eu-west1` (France), `default-project-eu-west1`. `eu-north1` and `us-central1` have a 0 vCPU quota on this tenant; quotas read with `nebius quotas quota-allowance list` |
| Instance | `creature-forge-r1-cpu`, platform `cpu-d3` (AMD EPYC Genoa 9654), preset `8vcpu-32gb`, Ubuntu 24.04 (driverless image), public IPv4, 50 GiB network SSD boot disk (VM-managed, deleted with the VM) |
| Rate (docs.nebius.com pricing, effective 2026-10-01) | 8 x $0.015 + 32 x $0.0045 = **$0.264/h** compute + $0.071/GiB-month disk (**$0.0049/h**, $0.117/day, billed while stopped) = **$0.269/h** |
| Not verified | public-IPv4 charge (not on the pricing page), actual credit balance (the CLI exposes none; check the console Billing page) |
| R1 cost | pilot + full plan fits in well under the 90-minute limit: ~$0.40 compute; the safeguard caps an unattended VM at 6 h = $1.61 |

## Access
- Nebius CLI 0.12.289 runs in WSL Ubuntu (no Windows build exists). Login is a federation (browser) profile `creature-forge`; tokens live in the CLI's own store in WSL, never in this repo.
- Dedicated SSH key `~/.ssh/creature_forge_nebius` (ed25519, no passphrase, used only for this VM; the other keys in `~/.ssh` are not offered: `IdentitiesOnly yes`). VM user `forge` with key-only login, ufw (22 only), fail2ban.
- `python infra/nebius/forge_cloud.py ssh-config` writes the `creature-forge-nebius` host block. Both agents then use `ssh creature-forge-nebius "<cmd>"` or the wrapper commands below. No GitHub token is on the VM: code arrives as a `git bundle` over scp.

## Commands (`python infra/nebius/forge_cloud.py ...`)
`plan` | `create` | `status` | `ssh-config` | `bootstrap` | `check` | `exec "<cmd>"` | `run-stage pilot|train|validate|gate|select [--rep N]` | `monitor` | `sync-down` | `extend --hours H` | `stop` | `start` | `delete --yes`

`bootstrap` ships the current branch, requires the registered commit `f33d429` to be an ancestor and `experiments/phase2a_r1/protocol.json` to be byte-identical to it, builds `~/venvs/creature-forge` (Python 3.12.3; the Windows `.venv` is untouched), and logs `pip freeze`.

## Cost safeguards
1. VM-side `forge-deadman.timer` powers the VM off when `/var/lib/forge/deadline` (default 6 h) passes.
2. Windows scheduled task `CreatureForgeNebiusWatchdog` (every 15 min, user level) calls `watchdog`, which asks the API to stop a running VM past its deadline, independent of any agent session; log in `infra/nebius/watchdog.log`. It only works while the PC is on and logged in.
3. `stop` ends compute billing; the 50 GiB disk still costs ~$0.12/day. `delete --yes` syncs and checksum-verifies results to `artifacts/nebius_r1/<timestamp>/`, then deletes the instance and any leftover `creature-forge-r1-cpu*` disk.

## Verification on the VM (2026-10-14, none counted in the R1 ledger)
`remote/check_env.py` (seeds 9000-9001, outside every registered partition): MuJoCo 3.15.0, NumPy 2.5.4, 30.5 GB free, 8 CPUs, pre-registration intact, incumbent hash matches, ledger chain valid, in-process and spawn-worker rollouts bit-identical, and the frozen incumbent matches the Windows reference within the documented tolerance (16 float diffs, max relative 5.5e-15, 0 structural). Unit tests: 207 of 208 pass.

## Findings
- **CRLF and the registered hashes.** The R1 protocol hashes the Windows worktree bytes (CRLF through `core.autocrlf`) of three Phase 2A files; git stores LF. On a default Linux checkout `preregistration_intact` and the incumbent hash fail. The bootstrap sets `core.autocrlf=true` and re-checks-out a clean tree, which restores the registered bytes. The protocol is untouched. A future registration should hash git blobs.
- **One test fails on Linux:** `test_r1.InitControllerTests.test_frozen_incumbent_reproduces_saved_heldout_results_exactly` requires bit-exact equality with Windows-saved metrics (4.7813531994158955 vs 4.781353199415885, ~2e-15 relative). This is the known platform libm effect (`docs/REPRODUCIBILITY.md`); the tolerance-based check passes. R1 results produced on Linux will carry that noise relative to Windows.
- Same Genoa price in all regions, so region choice was driven by quota only.

## Running R1 (after approval; not started)
`run-stage pilot`, inspect `results/pilot.json` (`recommended_workers`), then the stages in `scripts/run_r1.py`. Workers <= 4, 8,500-rollout cap, 4 GB free-memory floor and 90-minute limit are enforced by the registered code. Use `monitor`, then `sync-down` after every stage.
