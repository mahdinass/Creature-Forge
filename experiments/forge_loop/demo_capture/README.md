# Demo capture takes (2026-10-16) — provenance and edit guide

Raw footage for the submission video, recorded on the Nebius VM by `studio/e2e/forge-demo-capture.mjs`: one continuous take
per attempt of the real Studio (headless Chrome 1920x1080, Chrome DevTools screencast, encoded to 30 fps H.264 CRF 16). The
script only clicks, types and scrolls; every result on screen came from the server (live Nemotron on Nebius Token Factory,
MuJoCo on the VM). The only overlay is a white cursor dot (headless Chrome draws no cursor). Nothing was re-run or selected
after the fact: **every live attempt made is listed below**.

| take | mode | creature / challenge | outcome | model calls | file (not in Git) |
|---|---|---|---|---|---|
| `dry1` | SCRIPTED MOCK (no model) | stubby biped / push, target 10 N | pacing test only; v1 PASSED the default 10 N target, so the target for the live take was raised by the user on screen | 0 | `artifacts/vm/capture/dry1/take.mp4` |
| `live1` | **LIVE** | stubby biped / push, **target 15 N typed on screen** | v1 POOR (0/8 seeds reach 15 N, median 12.5 N; replay shows the fall at 15 N backward) -> Nemotron `foot_length x1.35` **VERIFIED** (12/0/0 on 12 held-out seeds, +6.56 N; matched twin INCONCLUSIVE) -> accepted as **v2** -> v2 **PASS** 8/8 (median 17.5 N) | 2 (`9df79116...f451`, `4b046be5...6bb7`), $0.0043 | `artifacts/vm/capture/live1/take.mp4` (589 s) |
| `live3-walk-stilts` | **LIVE** | stilts drawing (legs 0.55 + 0.55 m, foot 0.07 m; chosen by the screening below) / walk | v1 **FAIL** 8/8 (falls at ~2-3.5 s, median 2.15 m). Probes went against the model's expectations (foot x1.5 -0.03 m, torque x1.5 +0.03 m); it blamed the controller. P1 `walk.pitch_kp x0.7`; P2 `walk.balance_gain x1.2` **rejected by the validator** (159.6 outside the control bound [0, 150]; rejected, never clipped). Validation on 24 held-out seeds: P1 **NOT_VERIFIED** (12 wins / 2 losses / 10 ties, p = 0.006, but median +0.04 m, below the pre-declared 0.5 m minimum; both still fall in the replay); matched twin `walk.kd set 5.79` NOT_VERIFIED (+0.26 m). No controller retune chosen by the model. Accept disabled | 2 (`35a17100...07b7`, `03141931...a820`), $0.0036 | `artifacts/vm/capture/live3-walk-stilts/take.mp4` (211 s) |
| `live2-walk` (archived negative; superseded for shot 8) | **LIVE** | same drawing as live1 / walk | v1 PASS (8/8 seeds, median 4.79 m). Probes contradicted the model's opening hypotheses (longer feet -4.84 m, retune -0.17 m, torque ~0). Nemotron `walk.balance_gain x0.9` **NOT_VERIFIED** (+0.12 m median on 24 held-out seeds, bar 0.5 m); twin and baseline NOT_VERIFIED; Accept stays disabled | 2 (`1cb66068...8b19`, `331dc3b5...9db4`), $0.0036 | `artifacts/vm/capture/live2-walk/take.mp4` (302 s) |

Records (unedited, as written by the server): `live1/i-957877ed1690.json`, `live2-walk/i-6628ccc1705c.json`, `live3-walk-stilts/i-2ed39b130df0.json`; each take's
`capture_manifest.json` holds chapter timestamps, request ids, verdicts, ledger before/after and the code commit (snapshot
`e42e64e` / `3165725` / `2235243`, clean; Forge Loop code identical to `main` @ `e58dbdf`). SHA-256 in `MANIFEST.json`. Inference ledger:
140 -> 146 requests, $0.5412 -> $0.5527 (cap $15 / 1,500). The PNG stills of each take are next to the video.

Note on the target: 10 N is only the default. The stubby drawing survives 12.5 N, so at the default it passes; the live take
sets a 15 N requirement visibly in the challenge picker before running. Say "falls short of the 15 N target" (outcome POOR:
it survives smaller pushes), not "fails at everything".

## Edit guide: storyboard shot -> take and time (seconds into `take.mp4`)
| shot | content | take | from - to |
|---|---|---|---|
| 1 | a drawn biped tips over | live1 | 84 - 100 (replay of seed 633038 at 15 N backward; "FALL detected at sim t = 2.15 s") |
| 2 | draw, *Use this creature*, v1 chip | live1 | 2 - 40 (speed up the strokes if needed) |
| 3 | push challenge, target 15 N typed, POOR 0/8, per-seed bars, fall replay | live1 | 41 - 104 |
| 4 | *Investigate with AI* (probes on), stages | live1 | 100 - 115, then **cut the wait** (caption "(wait cut, about 5 min)") to 437 |
| 5 | LIVE banner, model calls (request ids), probe cards: friction x2 REFUTED, foot x1.5 CONFIRMED | live1 | 437 - 459 |
| 6 | hypotheses + arms, validation: NEMOTRON VERIFIED beside the INCONCLUSIVE matched twin; three-way replay | live1 | 459 - 523 |
| 7 | Accept -> v2 attributed to Nemotron -> v2 PASS 8/8 at 15 N | live1 | 523 - 589 |
| 8 | walking: the stilts robot falls (8/8); Nemotron probes, proposes a controller change; validator rejects an out-of-bounds edit; NOT_VERIFIED (+0.04 m vs 0.5 m bar), both still fall in the replay; Accept disabled | live3-walk-stilts | 47 - 80 (challenge + fall replay), 80 - 109 (investigation, no cut needed), 109 - 158 (model calls, probes), 158 - 210 (verdict, side-by-side falls, Accept disabled) |
| 8 (alternative, archived) | walking robot that already walks; small tweak NOT_VERIFIED | live2-walk | 222 - 301 |
| 9 | scoreboard slide with all caveats | (slide) | - |

Keep the LIVE / SCRIPTED MOCK labels visible whenever a model reply is on screen; never use `dry1` as model footage.

## Walking-creature screening (no model calls) -> `walk_screening/`
Goal (owner, 2026-10-16): a visibly different creature that genuinely fails the walk challenge. Four candidate drawings and
the selection rule were written to `walk_screening/candidates.json` **before** any run. Each was drawn by hand in the Studio
by the capture script (`STOP_AFTER=challenge`) against a server **without** live mode, put on the bench and given the default
8-seed walk challenge; nothing else (no probes, no redesigns, no model).

| candidate | result | per-candidate manifest |
|---|---|---|
| C1 top-heavy (torso 0.40 x 0.70 m) | not valid as drawn under the app's default Guided constraints (torso mass 38.9 kg > 15 kg; the app offers an approximation that needs consent) -> excluded by the rule, not run | `C1-top-heavy.manifest.json` |
| C2 short legs, big torso | same (torso mass outside [1, 15] kg) -> excluded, not run | `C2-short-legs-big-torso.manifest.json` |
| C3 stilts (legs 0.55 + 0.55 m, foot 0.07 m) | valid; walk **FAIL 8/8**, every seed a detected fall, median 2.11 m -> meets the rule (>= 6/8) | `C3-stilts.manifest.json` |
| C4 tall top-heavy | same as C1 -> excluded, not run | `C4-tall-top-heavy.manifest.json` |

Selected: **C3 stilts** (the only valid candidate; it satisfies the rule). No candidate was added after seeing results. The
live take drew the same figure; its interpreted body matched the screening exactly and the v1 walk challenge again failed 8/8.
One live attempt was made on it (`live3-walk-stilts`, NOT_VERIFIED); it was **not** repeated, so no outcome was selected by
re-rolling. Walking verification remains unachieved in this project (also true of the 7 earlier development walking
investigations and `live2-walk`); the model has never chosen controller retuning (co-design) for a walking redesign.
