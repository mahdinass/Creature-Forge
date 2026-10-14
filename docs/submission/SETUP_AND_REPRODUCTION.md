# Setup and reproduction

Three levels, from "look at it" to "re-run the cloud experiment". Only level 3 costs money (< $1) and needs a Nebius account.

## Prerequisites
Python 3.11+ (CI uses 3.12), Node 22+, Git. Chrome or Edge for the browser checks. Linux, macOS or Windows (the Studio and tests run on all; the evidence in `experiments/phase2a_r2` was generated on Linux).

## Environment variables (all optional)
| variable | purpose |
|---|---|
| `NEBIUS_API_KEY` | Nebius Token Factory key; only for live Nemotron calls. Put it in the environment or a git-ignored `.env` (see `.env.example`); never commit it. |
| `NEBIUS_BASE_URL` | defaults to `https://api.tokenfactory.nebius.com/v1` |
| `CREATURE_FORGE_ENABLE_LIVE=1` | lets the Studio server accept *Run live with Nemotron* (also needs the key and an explicit confirmation tick) |

## Level 1 — look at it (no key, ~5 minutes)
```sh
python -m venv .venv
.venv/bin/pip install -e ".[studio]"            # Windows: .venv\Scripts\pip install -e ".[studio]"
npm --prefix studio install && npm --prefix studio run build
.venv/bin/python scripts/run_studio.py          # http://127.0.0.1:8000
```
Open **Overview**, then **AI Investigation** → *Recorded live run 2* → step through the five stages → *Replay and verdict* → *Load synchronized replay*. The recordings are real earlier Nemotron calls (hash-verified); the replays are fresh MuJoCo rollouts.

## Level 2 — verify the evidence (no key)
```sh
.venv/bin/python -m unittest discover -s tests           # 300+ tests
npm --prefix studio test
.venv/bin/python scripts/smoke_test.py                   # rollout, determinism, fall detection
.venv/bin/python scripts/lab_browser_check.py            # real-browser flows (Overview, AI Investigation, Locomotion, Lab)
.venv/bin/python scripts/verify_demo_trials.py --full    # recorded Phase 1 trials reproduce
.venv/bin/python scripts/analyze_r2.py                   # descriptive analysis from the committed R2 records (no rollouts)
```
Recompute the confirmatory R2 statistics and verify the ledger from the committed records:
```python
import json
from creature_forge import r2
f = json.load(open("experiments/phase2a_r2/results/final.json"))
a = r2.final_analysis(f["per_seed"]["winner"], f["per_seed"]["incumbent"])
print(a["paired_table"], a["confirmatory_hierarchy"]["claims"])        # 59 / 0 discordant; preservation and improvement confirmed
led = r2.Ledger(); led.verify(); print(led.total_rollouts(), "rollouts; hash chain verified")
```

Frozen-input hashes (protocols, selections) are verified by every runner (`require_preregistration`), which also refuses to run if a registered file changed. Note: registered hashes of Phase 2A/R1 files are of the Windows (CRLF) bytes; on Linux the runners' bootstrap sets `git config core.autocrlf true`.

## Level 3 — live Nemotron call (needs a Nebius key; ≈ 8k tokens)
```sh
export NEBIUS_API_KEY=...            # PowerShell: $env:NEBIUS_API_KEY = "..."
export CREATURE_FORGE_ENABLE_LIVE=1
.venv/bin/python scripts/run_studio.py   # tick the confirmation box, press "Run live with Nemotron"
# or: .venv/bin/python scripts/run_demo.py live --confirm-live
```
One model call (30–90 s), then 160 MuJoCo rollouts (1–4 minutes on a laptop). The shared budget file records every live call (`experiments/phase2a_r3/results_v2/demo_requests.jsonl`). A mock run (`scripts/run_demo.py mock`) uses scripted text, is labelled SCRIPTED MOCK, and cannot be saved as live.

## Level 4 — re-run the R1/R2 cloud experiments (Nebius AI Cloud, ≈ $0.5)
1. Install the Nebius CLI (Linux/macOS; on Windows use WSL Ubuntu), `nebius profile create`, pick a region where your non-GPU vCPU quota is non-zero.
2. Edit the project/subnet ids in `infra/nebius/forge_cloud.py` (`CFG`), create an SSH key `~/.ssh/creature_forge_nebius`.
3. `python infra/nebius/forge_cloud.py plan` → `create` → `ssh-config` → `bootstrap` → `check` (compatibility + frozen-controller reproducibility).
4. Run stages with `forge_cloud.py run run_r2.py <stage> ...` and `wait`; `sync-down` after each stage; `stop` when done; `delete --yes` removes the VM and disk after syncing results. A 6-hour deadman timer and a Windows scheduled watchdog stop an unattended VM.
Details and findings: `docs/NEBIUS_CLOUD_R1.md`. R2's protocol (`experiments/phase2a_r2/protocol.json`) is immutable: re-running it from scratch requires a new protocol id.

## Cost and safety
Level 1–2: free. Level 3: ≈ $0.01–0.05 of inference at plausible list prices (price unverified). Level 4: ≈ $0.27/h while running, ≈ $0.12/day for the disk while stopped. Quotas: the Studio server refuses live calls without the flag and confirmation and caps live calls per process (10).
