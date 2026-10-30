# Testing guide for judges

Creature Forge runs locally. **No account, API key, GPU or cloud access is needed** to install it, run the physics and
inspect every recorded result. Live Nemotron calls are optional and need your own Nebius Token Factory key.

| You want to… | Time | Needs |
|---|---|---|
| See what the system does without installing | 5 min | Read the README and watch the [video](https://youtu.be/hPY-_cK5Oow) |
| Run the Studio and the recorded demos | about 10 min | Python 3.11 or 3.12, Node 22+, Git |
| Run the live MuJoCo loop on a drawn robot | +5 min | the same |
| Call Nemotron live | +5 min | a Nebius Token Factory key (fractions of a cent per call) |
| Re-check statistics from raw records | 2 min | the same Python environment |

## 1. Install and start
```sh
git clone https://github.com/mahdinass/Creature-Forge.git
cd Creature-Forge
python -m venv .venv
.venv/bin/pip install -e ".[studio]"          # Windows: .venv\Scripts\pip install -e ".[studio]"
npm --prefix studio ci
npm --prefix studio run build
.venv/bin/python scripts/run_studio.py        # Windows: .venv\Scripts\python scripts\run_studio.py
```
**Expected:** the server prints `Uvicorn running on http://127.0.0.1:8000` after about 10 to 20 seconds (it computes a
small set of start-up rollouts). Open <http://127.0.0.1:8000>.

Windows alternative: `powershell -ExecutionPolicy Bypass -File scripts\start_studio.ps1` frees port 8000, rebuilds a
stale frontend, checks the API and opens the browser.

**Suggested order:** *Nemotron's experiment* (section 2), the live loop (section 3), then *Verified repair* (section 2), a
supporting demonstration of independent verification with no AI.

## 2. The recorded results (no key; nothing is simulated or called)
**Nemotron's experiment:** <http://127.0.0.1:8000/?tab=nemotron>
- A recorded LIVE investigation of a robot with a hidden one-sided weakness, played back stage by stage.
- Stage 3 shows the decision: the engine's information estimates are tied, the engine picks gait frequency × 1.2 and
  Nemotron picks × 0.85. Nemotron's reply is shown verbatim with its request id, tokens and cost.
- Stages 4 to 7 show both experiments on the damaged robot, the beliefs ending on opposite sides, and the independent
  verification: Nemotron's lane FULL 23/24, the engine's PARTIAL 20/24.
- The later stages show how representative it is: a second run made the same choice and recovered only partly, and
  across 36 instances the result is parity (15 vs 14).

**Verified repair (no AI):** <http://127.0.0.1:8000/?tab=recovery>
- Three robots replayed in sync: the faulty robot, the frozen-objective repair (falls on the illustrative seed) and the
  DO-1 repair (walks).
- The counts: frozen 19/24 (PARTIAL), DO-1 21/24 plus the 20 s confirmation (FULL_RECOVERY). Every seed can be selected.

Both pages refuse to serve if a pinned file's SHA-256 does not match.

## 3. The live loop on your own drawing (no key: MuJoCo is real, the AI step is a labelled mock)
1. *Create → Draw*. Draw a torso, a leg and a foot with the three pens, then click **Use this creature**.
2. On *My creature*, choose **Push**, optionally type a target force, then **Run push challenge on v1**. MuJoCo runs one
   job per seed and shows PASS, POOR or FAIL with per-seed scores. Click a seed to replay it.
3. Tick the probes option and click **Run scripted mock (not a model)**. Without a key, *Investigate with AI* is disabled
   and says why. The scripted mock runs the whole pipeline (probes, arena, matched random twin, held-out validation,
   verdict) with fixture text and is never labelled as Nemotron.
4. Read the verdicts. **Accept** is enabled only for a VERIFIED_IMPROVEMENT; an accepted arm becomes v2, which you can
   challenge again.

## 4. Live Nemotron (optional; your key; costs money)
```sh
cp .env.example .env
# edit .env: NEBIUS_API_KEY=<your Token Factory key> and CREATURE_FORGE_ENABLE_LIVE=1
```
Restart the Studio. *Investigate with AI* is now enabled and calls `nvidia/nemotron-3-super-120b-a12b`: at most 4 calls
per investigation, about $0.002 to $0.004 per call in our records. The record shows LIVE provenance, request ids, tokens
and cost. An investigation takes a few minutes, mostly MuJoCo validation. The key is never logged; `.env` is git-ignored.

## 5. Inspect the evidence without the UI
```sh
# W3/W4 replication statistics from raw records (prints the registered analysis)
.venv/bin/python scripts/do1_replication_analysis.py \
  --w3 experiments/do1/w3w4_2026-10-21/do1_l4_rep.jsonl --w4 experiments/do1/w3w4_2026-10-21/do1_x.jsonl
# Integrity of the frozen records and of the demo exports
.venv/bin/python -m unittest tests.test_frozen_records tests.test_evidence_tracked tests.test_do1_api tests.test_w2_case
```
Live take records with request ids: `experiments/forge_loop/demo_capture/`. Pre-registered scoreboard:
`experiments/forge_loop/scoreboard/REPORT.md`. Every study and its decision: `docs/RESEARCH_STATUS.md`.

## 6. Automated checks (optional)
```sh
.venv/bin/python -m unittest discover -s tests      # about 1,600 tests; about 30 minutes on a laptop
npm --prefix studio test                            # 199 frontend tests
.venv/bin/python scripts/smoke_test.py              # MuJoCo determinism and fall detection
.venv/bin/python scripts/lab_browser_check.py       # real-browser flows (needs Chrome or Edge)
```
Some tests skip on a fresh clone because they need large git-ignored raw records; the skip message names the record.

## 7. Troubleshooting
| Symptom | Fix |
|---|---|
| `WARNING: studio/dist not built` and a blank page | Run `npm --prefix studio run build`, then restart |
| Port 8000 in use | `CREATURE_FORGE_PORT=8010 python scripts/run_studio.py` (PowerShell: `$env:CREATURE_FORGE_PORT=8010`) |
| `pip` cannot install `mujoco` | Use 64-bit Python 3.11 or 3.12, the versions this project is tested with (3.11 on Windows, 3.12 on Linux and in CI) |
| *Investigate with AI* is greyed out | Expected without a key: live mode needs `NEBIUS_API_KEY` and `CREATURE_FORGE_ENABLE_LIVE=1` |
| Browser check cannot find a browser | Set `BROWSER_PATH` to Chrome or Edge |
| Numbers differ in the last digits from the reports on Windows | Expected: the experiments ran on Linux; labels and verdicts match, some floats differ (`docs/REPRODUCIBILITY.md`) |

## 8. What is real and what is recorded
- **Real on your machine:** every MuJoCo challenge, replay, probe, arena validation and verdict on the interactive pages.
- **Real only with a key:** the Nemotron call on *Investigate with AI*.
- **Recorded:** *Nemotron's experiment*, *Verified repair*, *AI scientist*, *Causal engineer* and history pages replay
  stored records of runs we made (live model calls on Nebius Token Factory and batch physics on Nebius AI Cloud). They
  are labelled as recorded on the page.
