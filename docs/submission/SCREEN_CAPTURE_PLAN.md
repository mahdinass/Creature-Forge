# Screen-capture plan

Goal: ≥ 1 minute of genuine module operation inside a < 3 minute video (`STORYBOARD.md`). Capture at 1920×1080, 30 fps, one browser window at 100% zoom, dark theme (the app's default), cursor visible and slow.

## Prepare (≈ 10 minutes)
1. `git switch main && git pull`; `npm --prefix studio run build`; `.venv\Scripts\python scripts\run_studio.py` → `http://127.0.0.1:8000`.
2. Close other windows and notifications; hide bookmarks; sign out of accounts in the browser profile used for the capture (use a clean profile).
3. Confirm no secrets can appear: no `.env` file open, no terminal showing environment variables, no cloud console.
4. Make sure `artifacts/demo_runs/` does not contain local runs that would show as `local` in the list (move it away for the capture; it is git-ignored).
5. Free RAM ≥ 3 GB (close Docker Desktop and IDE) so replays load in ~5 s.

## Shots (in storyboard order)
| Shot | URL / action | Must show | Take notes |
|---|---|---|---|
| 1 | `/?tab=compare` — Play; scrub to the fall (~1.85 s) | the 8 cm biped falling after the push; "fall" marker | 10 s |
| 2 | `/` (Overview) — slow pan over the five steps | pipeline cards | 12 s |
| 3a | `/?tab=demo` → run *Recorded live run 2* → step 1 *Observed failure* | seed 9101 measured table | |
| 3b | step 2 *What the model saw* | context JSON (expand), prompt hash | |
| 4 | step 3 *Model proposal* | RECORDED LIVE banner, raw reply (expand), citations resolved to values, edits requested/realised | also show *Recorded live run 1* briefly (rejected reply) |
| 5 | step 4 *Verification* | the five-row table with per-seed bars | hold 8 s |
| 6 | step 5 *Replay and verdict* → *Load synchronized replay* → Play at 0.5× | frozen falls at ~3 s, edited keeps walking; height chart; verdict text | |
| 7 | `/` (Overview) | classical card, "no language model", "not completed" notice | |
| 8 | GitHub repo page (README top, LICENSE visible) | license + README tables | only if the repository is public by then |

Optional live clip: set `NEBIUS_API_KEY` and `CREATURE_FORGE_ENABLE_LIVE=1` only in the shell that starts the server (never display it), tick the confirmation, press *Run live with Nemotron*, speed-ramp the 1–4 minute wait in the edit, and keep the LIVE banner on screen.

## Safety checklist before publishing the video
- [ ] No API key, token, account id, balance, or request header visible at any frame (scrub the exported file).
- [ ] No NVIDIA/Nebius logos; no endorsement wording.
- [ ] Audio is original voice-over; any music is licensed for this use and credited in the description.
- [ ] Length < 3:00 and ≥ 1:00 of live software.
- [ ] Description links the repository, states the two separate results, and says the systematic comparison was not completed.
