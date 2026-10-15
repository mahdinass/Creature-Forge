# Screen-capture plan (Forge Loop)

Story: a user draws a robot. NVIDIA Nemotron investigates its physical failures, proposes structural and controller redesigns, and MuJoCo independently verifies whether the changes work. Verified improvements become new creature versions.

Goal: >= 1 minute of genuine module operation inside a < 3 minute video (`STORYBOARD.md`, about 1:50 of live Studio in shots 2-8). Capture at 1920x1080, 30 fps, one browser window at 100% zoom, dark theme (the app default), cursor visible and slow. Everything on screen must come from the running Studio; no mock-ups.

## Where the software runs

The whole Studio runs on the Nebius VM, bound to `127.0.0.1:8000` there. The local machine runs only the browser: no local server, no local build, no local Python or MuJoCo. The browser reaches the VM through an SSH tunnel at `http://127.0.0.1:8765`.

## Prepare (about 10 minutes, plus VM start)

1. Make sure the VM is running (start it with the usual cloud helper within the infrastructure budget; stop it through the API when the capture session ends).
2. Sync the code and start Studio on the VM with live Nemotron calls enabled: `python infra/nebius/forge_dev.py serve --slot <slot> --live` (the `--live` flag exports `CREATURE_FORGE_ENABLE_LIVE=1` on the VM only; the API key stays on the VM and is never typed or shown locally).
3. Open the tunnel: `python infra/nebius/forge_dev.py tunnel`. Then open `http://127.0.0.1:8765` in the browser. Check the page loads and the "Investigate with AI" button is enabled once a challenge has run (it is disabled when live mode is off).
4. Use a clean browser profile, signed out of everything, bookmarks hidden, notifications off, no other windows. Record only the browser window (not the desktop), so no terminal can slip into frame.
5. Confirm no secrets can appear: no `.env` open, no terminal showing environment variables or SSH config, no cloud console, no request headers (do not open the browser dev tools).
6. Optional: use a fresh slot (or clear the creature list) so the "Investigations" list on the left shows only the clips you want.

## Shots in storyboard order

Real labels are quoted from `studio/src/forge/` and `studio/src/sketch/`. The Forge workspace banner reads "YOUR CREATURE - LIVE MuJoCo".

| Shot | Storyboard | Studio screen and action | Must be visible |
|---|---|---|---|
| 1 | 0:00-0:12 drawn biped tips over | Forge workspace after a Push challenge: in the seed strip, click a `FAIL` seed; the "Seed N - fresh MuJoCo replay" viewport plays the fall. (Cut from the replay captured in shot 3; do not stage anything else.) | the falling biped, the FAIL badge |
| 2 | 0:12-0:27 draw a creature, "Use this creature" | Sketch tab (`/?tab=sketch`): either pick the starter "Balanced biped" or draw with the pens "Torso", "Leg", "Foot"; then press "Use this creature". The Forge page opens with the creature bar showing chip `v1` and "Version history: just the one you drew". | drawing in progress, `v1` chip |
| 3 | 0:27-0:42 push challenge, FAIL, replay | In "Choose a challenge" select "Push" (leave "Target force (N)" and "Seeds" at defaults), press the run button ("Run push challenge on v1"). While running: "Running in MuJoCo". Result: outcome badge `FAIL`, headline, counts (pass / poor / fail), median score, the seed strip with per-seed outcome and score; click a FAIL seed and let the replay play. | FAIL badge, per-seed scores, fall replay |
| 4 | 0:42-1:07 "Investigate with AI", LIVE, probes, wait cut | In the "Investigate with AI" card tick "Run diagnostic probes first (...)". Leave the loop and engineering-memory options unticked. Press "Investigate with AI". Show the stage list (Evidence, Model, Build arms, Screen, Validate, Verdict) and the live "Model call" card (model name, request id, latency, tokens, finish). The wait for Nemotron may be cut; add the caption "(wait cut)". | provenance banner reading LIVE once the record opens; the model name `nvidia/nemotron-3-super-120b-a12b` in the "Model call" card |
| 5 | 1:07-1:30 probe cards | In the record timeline, "Diagnostic probes (counterfactual runs, not proposals)": each probe row shows its probe id, a CONFIRMED or REFUTED chip, "Changed:", "Expected:", "Observed:". Use the values of the run actually shown (the development run `i-140b1435cb84` had friction x2 REFUTED and foot x1.5 CONFIRMED). | CONFIRMED and REFUTED chips with values |
| 6 | 1:30-1:55 proposal, arena table, AI vs twin | Scroll the timeline: "Hypotheses (written by the model, unverified)" with cited evidence values, "Proposals checked by the validator", "Arms" table, then "Validation on N held-out seeds" with the three cards "AI change" (chip NEMOTRON), "Matched random twin" (chip RANDOM BASELINE) and "Best baseline". Then the "The original and nemotron ..., same held-out seed" section with the original and the AI arm side by side; tick "Also show the matched random twin (...)" for the third viewport; hold on the "Median score on the held-out seeds" bars and the verdict text ("Verified improvement on N held-out seeds (...)"). | AI arm verdict and the twin verdict side by side, with the real values |
| 7 | 1:55-2:10 Accept, v2, challenge v2 | In "What this change does" press "Accept as a new version" (enabled only for a verified improvement). The banner "Accepted as v2." appears, the creature bar shows chip `v2` and a lineage row attributed to Nemotron; press "Challenge v2" and let the result load. | v2 chip, Nemotron attribution in the lineage, the v2 run result |
| 8 | 2:10-2:25 honest negative | See "Honest-negative clip" below. Keep the verdict label visible and note that "Accept as a new version" is disabled with the explanation in the panel. | NOT_VERIFIED (or INCONCLUSIVE) label, disabled accept button |
| 9 | 2:25-2:50 scoreboard slide and end card | Not screen capture: a title-safe slide made from the exact text in `STORYBOARD.md`, with every caveat line. Source numbers: `experiments/forge_loop/scoreboard/REPORT.md`. | all caveat lines |

Keep the provenance banner (LIVE, or SCRIPTED MOCK for fixtures) in frame whenever a model reply is on screen. A cut wait must carry the "(wait cut)" caption.

## Honest-negative clip (shot 8)

Pick one, whichever you can show with its verdict label visible:

- Walking investigation, NOT_VERIFIED: choose the "Walk" challenge on a creature such as "Tiny feet" and investigate with probes on. In the development records the probes confirmed the feet but the gains stayed below the 0.5 m bar (`experiments/forge_loop/dev_live_records/README.md`, walking section, for example `i-b9adf9d9a843`). Open it from the "Investigations" list if the record is present in the slot; otherwise run it live (a walk challenge is slower and costs more rollouts).
- INCONCLUSIVE AI arm: development record `i-c2c4c48729d3`, or a scoreboard cell such as bird-knees / push replicate 2 (AI arm INCONCLUSIVE).
- Matched-random twin: any record where the twin card shows INCONCLUSIVE, NOT_VERIFIED or WORSE next to the AI card; the twin is the comparison, so showing it failing or being undecided is part of the honest picture.
## Scripted capture option (reproducible raw runs)

`studio/e2e/forge-live-flow.mjs` drives the complete live flow in a real (headless Chrome) browser against the Studio on the VM: draw a torso, leg and foot, "Use this creature", select the Push challenge and run it, tick the probes option, "Investigate with AI", wait for the record, check the LIVE provenance, check the matched twin is shown, accept only if the verdict is a verified improvement, then challenge the new version. It prints PASS/FAIL checks, writes 1920x1080 screenshots when `SHOT_DIR` is set, and writes a JSON summary with the investigation id and request ids.

- It makes real paid Nemotron calls (about 2-3 per run, about $0.005 in the development acceptance run). They count against the $15 / 1,500-request inference ledger cap. Run it only deliberately.
- It does nothing unless `LIVE_OK=1` is set, and it needs `BASE_URL`. Run it on the VM against the Studio started with `--live` (for example with `forge_dev.py exec --slot <slot> ...`). It is never part of CI.
- It does not record video. It gives (a) a reproducible live run, (b) screenshots, and (c) a persisted LIVE investigation record on the VM. For footage, the owner opens that record in the Studio over the tunnel (the "Investigations" list on the creature page) and screen-records the relevant parts: the probe cards, arena, verdict and the accepted v2. The owner does the voice-over and the edit.
- The reference result for this flow is `experiments/forge_loop/dev_live_records/ui_live/` (investigation `i-140b1435cb84`, 15/15 checks passing). That is a functional acceptance test of the development creature, not new evidence.
- Because the script follows the verdict, a run can end without a verified redesign; it then keeps "Accept" disabled and says so. Treat that run as a legitimate honest-negative source.

## Safety checklist before publishing the video

- [ ] No API key, token, account id, balance, SSH detail or request header visible at any frame (scrub the exported file).
- [ ] No NVIDIA or Nebius logos or marks; no endorsement wording ("partner", "sponsored by", "endorsed by"). Name them in text only; say "built for the Nebius x NVIDIA Global AI Hackathon".
- [ ] Audio is original voice-over; any music is licensed for this use and credited in the description (preferred: none).
- [ ] Length < 3:00 and >= 1:00 of live software.
- [ ] LIVE / RECORDED / SCRIPTED MOCK banner is visible whenever a model reply is on screen; cut waits are captioned "(wait cut)".
- [ ] The scoreboard slide shows every caveat line from `STORYBOARD.md`.
- [ ] Description links the repository and states the limits of the evidence (small sample, tested creatures and challenges only).
