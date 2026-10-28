# Setup and reproduction (V1)

The levels run from "look at the demo" to "run it live on Nebius". Only live model calls and cloud VMs cost money;
everything else is free and runs offline.

## Prerequisites
- **Software:** Python 3.11 or 3.12 (CI uses 3.12), Node 22+, Git. Chrome or Edge is needed only for the browser checks.
- **Platforms:** the Studio runs on Linux, macOS and Windows.
- **Recorded experiments:** all were produced on Linux (Nebius VMs) with Python 3.12.3, numpy 2.5.4 and MuJoCo 3.15.0.

## Environment variables (all optional)
| Variable | Purpose |
|---|---|
| `NEBIUS_API_KEY` | Nebius Token Factory key; needed only for live Nemotron calls. Keep it in a git-ignored `.env` (see `.env.example`) or the environment; never commit it. |
| `NEBIUS_BASE_URL` | Defaults to `https://api.tokenfactory.nebius.com/v1` (https only). |
| `CREATURE_FORGE_ENABLE_LIVE=1` | Lets the Studio make live calls (the key is also required). |
| `CREATURE_FORGE_PORT` | Studio port (default 8000). |
| `TA1_RECORDS_ROOT` | Optional folder of the git-ignored DS-1 stored records. Without it, the 24 DO-1 tests that need them skip. |

## 1. The demo, offline (no key, no cloud)
```sh
python -m venv .venv
.venv/bin/pip install -e ".[studio]"            # Windows: .venv\Scripts\pip install -e ".[studio]"
npm --prefix studio ci && npm --prefix studio run build
.venv/bin/python scripts/run_studio.py          # http://127.0.0.1:8000
```
On Windows you can instead run `powershell -ExecutionPolicy Bypass -File scripts\start_studio.ps1`.

**The two demo-video pages** play back hash-pinned recorded files. They make no simulation and no model call.
- **Verified repair**, `http://127.0.0.1:8000/?tab=recovery`. The server checks `experiments/do1/demo/SHA256SUMS` before it
  serves anything.
- **Nemotron's experiment**, `http://127.0.0.1:8000/?tab=nemotron`. Recorded LIVE playback from `experiments/w2/`.

**Everything else in the Studio** (Draw, Playground, Compare, My creature) simulates in MuJoCo on your machine. Without a
key, each AI action runs as a labelled **SCRIPTED MOCK** and is never promoted to LIVE.

## 2. Live Nemotron (Nebius key; paid)
Create `.env` in the repository root:
```
NEBIUS_API_KEY=<your key>
CREATURE_FORGE_ENABLE_LIVE=1
```
Restart the Studio. Live calls are then allowed in these places:
- **My creature → Investigate with AI** (and *Recover walking* with the AI director):
  - model `nvidia/nemotron-3-super-120b-a12b`, settings in `experiments/forge_loop/model_config.json`;
  - 1–4 calls per investigation, about $0.002–0.004 each in our records, plus MuJoCo verification.
- **AI investigation → Run live:** the original Nano demo path, `creature_forge/demo.py`.

The HaS scientist shown on the *Nemotron's experiment* and *AI scientist* pages is a command-line study,
`scripts/hdb_agent_run.py`. We ran it on a Nebius VM. The Studio only plays back its records.

**Safeguards.**
- Every call goes through `creature_forge/nebius.py`: request, token and dollar caps, no blind retries, the key never
  logged.
- Every call is written to the inference ledger, `creature_forge/inference_ledger.py`. Its caps are 8,000 requests and
  $52.78 in total, plus 4 requests and 80,000 tokens per investigation.
- A call whose worst-case cost would exceed a cap is refused before it is sent.

## 3. Nebius VM workflow (how all heavy simulation was run)
Requires the Nebius CLI and the VM set up as in `docs/NEBIUS_CLOUD_R1.md` (ids in `infra/nebius/forge_cloud.py`).
```sh
python infra/nebius/forge_cloud.py start        # refuses beyond the infra cap (SPEND_CAP_USD, $96); sets a deadline
python infra/nebius/forge_cloud.py spend        # conservative infra spend so far
python infra/nebius/forge_dev.py sync           # mirror the worktree to a VM slot
python infra/nebius/forge_dev.py test py        # also: fe | e2e | smoke | all
python infra/nebius/forge_cloud.py stop         # ALWAYS stop through the API; an in-VM poweroff gets restarted
```

## 4. Reproduce the V1 evidence without physics (any OS, minutes)
```sh
# W3/W4 replication statistics from the raw records (must equal analysis_output.txt)
.venv/bin/python scripts/do1_replication_analysis.py --w3 experiments/do1/w3w4_2026-10-21/do1_l4_rep.jsonl \
  --w4 experiments/do1/w3w4_2026-10-21/do1_x.jsonl
# integrity of the frozen records and the demo exports
(cd experiments/do1/w3w4_2026-10-21 && sha256sum -c SHA256SUMS)
(cd experiments/do1/demo && sha256sum -c SHA256SUMS)
(cd experiments/w2/gen0137_one_side_weakness/plant_replays && sha256sum -c SHA256SUMS)
.venv/bin/python -m unittest tests.test_frozen_records tests.test_evidence_tracked tests.test_do1_api tests.test_w2_case
# Forge Loop scoreboard analysis (12 committed records; restore any rewritten generated file with git checkout)
.venv/bin/python scripts/forge_scoreboard.py --analyze --records experiments/forge_loop/scoreboard/results/records
```

## 5. Re-run physics experiments (Linux, recorded environment, costs VM time)
- **W3/W4:**
  1. Check out the pre-registration commit `3b8a8b1` clean.
  2. Provide the DS-1 artifacts and the stored records, with the hashes in `scripts/ta1_tool_access.py` `REFERENCE`.
  3. Run `bash scripts/run_do1_w3w4.sh 3b8a8b1e12bccddb2573a21c2717d3c36ae15dd5 <out>`.

  The sentinel checks the environment first. Later commits add records under `experiments/`, and the runner's preflight
  then refuses by design.
- **Demo exports:** `scripts/do1_demo_export.py` and `scripts/w2_damaged_plant_export.py`, on the main VM. Each is
  fail-closed against the recorded rows.
- **Older studies (R1/R2, scoreboard):** `docs/NEBIUS_CLOUD_R1.md` and the protocols in `experiments/`. All protocols are
  immutable.

## 6. Tests
```sh
.venv/bin/python -m unittest discover -s tests          # about 1,600 tests
npm --prefix studio test && npm --prefix studio run build
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/lab_browser_check.py           # 11 real-browser flows, incl. both demo-video pages
```
CI (`.github/workflows/context-guards.yml`, Ubuntu, clean checkout) runs all four. Run them on the VM
(`forge_dev.py test ...`) if the local machine is short of memory.

## Budgets
| What | Value |
|---|---|
| Infra cap | `SPEND_CAP_USD` $96. The infra ledger was $89.405 after W3/W4; the W3/W4 session itself cost $0.41 |
| Inference | See §2. The recorded scientist calls cost about $0.003 each; the Forge Loop scoreboard cost $0.05 in total |
| Scripted and recorded modes | Free |
