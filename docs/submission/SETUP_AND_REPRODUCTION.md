# Setup and reproduction

Levels from "look at it" to "run it live on Nebius". Only live calls and the VM cost money; everything else is free.

## Prerequisites
Python 3.11+ (CI uses 3.12), Node 22+, Git. Chrome or Edge for the browser checks. The Studio runs on Linux, macOS and Windows; the Forge Loop scoreboard and live records were produced on a Linux Nebius VM.

## Environment variables (all optional)
| variable | purpose |
|---|---|
| `NEBIUS_API_KEY` | Nebius Token Factory key; only for live Nemotron calls. Put it in a git-ignored `.env` (see `.env.example`) or the environment; never commit it. |
| `NEBIUS_BASE_URL` | defaults to `https://api.tokenfactory.nebius.com/v1` (https only) |
| `CREATURE_FORGE_ENABLE_LIVE=1` | lets the Studio accept live investigations (also needs the key) |
| `CREATURE_FORGE_PORT` | Studio port (default 8000) |

## 1. Local scripted run (no key)
```sh
python -m venv .venv
.venv/bin/pip install -e ".[studio]"            # Windows: .venv\Scripts\pip install -e ".[studio]"
npm --prefix studio install && npm --prefix studio run build
.venv/bin/python scripts/run_studio.py          # http://127.0.0.1:8000
```
Open the **My creature** tab: draw (or pick a starter), *Use this creature*, run a challenge, *Investigate with AI*. Without live mode only the **scripted mock** runs; it is labelled SCRIPTED MOCK and is never promoted to LIVE. The **Overview** and AI Investigation tabs show the earlier recorded Nemotron demo.

## 2. Live mode (Nebius key)
Create `.env` in the repository root:
```
NEBIUS_API_KEY=<your key>
CREATURE_FORGE_ENABLE_LIVE=1
```
Restart `scripts/run_studio.py`. *Investigate with AI* then calls `nvidia/nemotron-3-super-120b-a12b` (settings in `experiments/forge_loop/model_config.json`). One investigation is 1-2 model calls (about $0.002 each in our records) plus MuJoCo rollouts.

## 3. Nebius VM workflow (what we used for all simulation and testing)
Requires the Nebius CLI and the VM set up as in `docs/NEBIUS_CLOUD_R1.md` (project and subnet ids in `infra/nebius/forge_cloud.py`).
```sh
python infra/nebius/forge_cloud.py start        # refuses beyond the infra spend cap; sets a deadline
python infra/nebius/forge_cloud.py spend        # conservative infra spend so far
python infra/nebius/forge_dev.py sync           # mirror the worktree (incl. uncommitted changes) to a VM slot
python infra/nebius/forge_dev.py test py        # also: fe | e2e | smoke | all
python infra/nebius/forge_dev.py serve --slot integ --live   # Studio on the VM
python infra/nebius/forge_dev.py tunnel         # then open http://127.0.0.1:8765
python infra/nebius/forge_cloud.py stop         # always stop when finished (it bills while running)
```
`sync` pushes to a bare repo on the VM and leaves the registered research clone untouched. Use `forge_dev.py pull` to copy VM outputs back (pull before the next `sync`, which cleans untracked files in the slot).

## 4. Reproduce the scoreboard analysis (no key, no rollouts)
```sh
python scripts/forge_scoreboard.py --analyze --records experiments/forge_loop/scoreboard/results/records
```
This recomputes the pre-registered analysis (exact one-sided McNemar, Wilson intervals) from the 12 committed records, whose SHA-256 values are in `MANIFEST.json`. It writes `results/summary.json` and may rewrite the generated section of the report: check `git diff` and restore, since the registered outputs are frozen. Report and limits: `experiments/forge_loop/scoreboard/REPORT.md`. Re-running the live scoreboard is not supported: the protocol is registered and `--run` refuses to run against a changed or uncommitted protocol.

## 5. Acceptance and live UI flows
```sh
python scripts/forge_acceptance.py --base http://127.0.0.1:8000 --starter balanced --kind push --mode scripted
python scripts/forge_run_loop.py --cid <cid> --n <version> --run-id <run_id> --mode live
node studio/e2e/forge-live-flow.mjs              # real browser, real Nemotron call; set LIVE_OK=1; never in CI
```
`forge_acceptance.py` runs draw, challenge, investigate, verdict and accept-if-verified over HTTP and writes a report under `artifacts/forge/acceptance/`. Neither script accepts a design that is not VERIFIED. The archived live UI run (15/15 checks) is described in `experiments/forge_loop/dev_live_records/README.md`. (The exact invocation of `forge-live-flow.mjs` was not re-verified for this document; see the header of that file.)

## 6. Tests
```sh
.venv/bin/python -m unittest discover -s tests
npm --prefix studio test && npm --prefix studio run build
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/lab_browser_check.py        # real-browser flows
```
Run these on the VM (`forge_dev.py test ...`) if the local machine is short of memory. Older evidence checks (`scripts/verify_demo_trials.py --full`, `scripts/analyze_r2.py`) are unchanged.

## Budgets and caps
- Inference ledger: 1,500 requests and $15.00 in total; per investigation 4 requests and 80,000 tokens. A call whose worst-case cost would exceed a cap is refused before it is sent.
- Infra spend cap: $10 (`forge_cloud.py` refuses `start`/`extend` beyond it); a deadline powers the VM off, and the VM should still be stopped through the API.
- The Studio refuses live calls unless the flag and key are present; scripted runs cost nothing.
- Totals to date: see `docs/PROJECT_STATE.md` (latest recorded: 24 model calls and $0.05 for the scoreboard).
- Older R1/R2 cloud experiments: `docs/NEBIUS_CLOUD_R1.md`; their protocol is immutable.
