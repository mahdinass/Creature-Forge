# Video production handoff (2026-10-27)

For the separate production of the final demo video (storyboard, animation, narration, edit, music and upload are out of
scope here). This page says what authentic footage exists, what it proves, what must be disclosed and where every file
is. Older production notes remain in `STORYBOARD.md`, `VIDEO_PRODUCTION.md` and `video/`.

## 1. Rules the video must meet (official rules, checked 2026-10-27)
- Under **3 minutes**; judges need not watch past 3:00.
- Uploaded to **YouTube and publicly visible**; link pasted in the Devpost form.
- **Physical AI, no hardware:** at least **one minute of footage of the key application modules in action**.
- Shows the project functioning on the device it was built for (a desktop browser running the Studio).
- **No third-party trademarks or copyrighted music** without permission. Do not show NVIDIA or Nebius logos; write the
  names as plain text. Use only music you have the rights to.
- In English (or with an English translation).

## 2. The strongest authentic material
**Open with the live Forge Loop take `live1` (2026-10-16).** It is one continuous, unstaged recording of the real Studio
with live model calls:
1. a stubby biped is drawn by hand and put on the bench;
2. the user types a 15 N push target; MuJoCo runs the push challenge: POOR, 0 of 8 seeds reach 15 N (median 12.5 N),
   and the replay shows the backward fall;
3. *Investigate with AI* (LIVE): Nemotron 3 Super requests diagnostic probes (friction × 2 refuted, foot × 1.5
   confirmed) and proposes "both legs: foot length × 1.35";
4. held-out validation on 12 seeds: **VERIFIED_IMPROVEMENT, 12 wins / 0 losses, +6.56 N**, beside the matched random edit
   (foot grip × 0.741), **INCONCLUSIVE**, all 12 pairs tied;
5. Accept becomes enabled only because MuJoCo verified it; v2 then passes **8 of 8** (median 17.5 N).

Two model calls, request ids `9df79116…f451` and `4b046be5…6bb7`, cost $0.0043, code commit `e42e64e` (clean). Record:
`experiments/forge_loop/demo_capture/live1/`.

Outside the roughly five-minute investigation wait, this take alone holds about four minutes of genuine module footage,
so the one-minute requirement is comfortably met.

**Second: the recorded demo pages (take 3, 2026-10-21)** of *Verified repair* and *Nemotron's experiment*. These are real
Studio pages playing back hash-pinned records; label them as recorded runs.

**Third, for honesty and contrast: `live3-walk-stilts`.** A stilts robot falls in 8 of 8 walks; Nemotron's controller
change is NOT_VERIFIED (+0.04 m against a 0.5 m bar), and the validator rejects an out-of-bounds second proposal. This
shows the verifier saying no.

## 3. Shot list (every shot is real footage unless marked ILLUSTRATIVE)
Times are seconds into the file. LIVE = the model was called during the recording. RECORDED PLAYBACK = a Studio page
replaying stored records (no model call while filming). ILLUSTRATIVE = a designed graphic, not execution footage.

| # | Content | Label | File (package path) | From – to |
|---|---|---|---|---|
| L1 | A drawn biped tips over at 15 N ("FALL detected") | LIVE | `01_live_forge_loop/live1_push_verified/take.mp4` | 84 – 100 |
| L2 | Drawing, *Use this creature*, v1 chip | LIVE | same | 2 – 40 |
| L3 | 15 N target typed; push challenge; POOR 0/8; per-seed bars; fall replay | LIVE | same | 41 – 104 |
| L4 | *Investigate with AI* clicked; investigation stages (cut the wait, about 5 min; caption it) | LIVE | same | 100 – 115, then 437 |
| L5 | LIVE banner, model calls with request ids, probe cards | LIVE | same | 437 – 459 |
| L6 | Hypotheses and arms; validation: Nemotron VERIFIED beside the INCONCLUSIVE twin; three-way replay | LIVE | same | 459 – 523 |
| L7 | Accept → v2 attributed to Nemotron → v2 PASS 8/8 | LIVE | same | 523 – 589 |
| L8 | Walking: stilts robot falls; probes; out-of-bounds proposal rejected; NOT_VERIFIED; Accept disabled | LIVE | `01_live_forge_loop/live3_walk_not_verified/take.mp4` | 47 – 80, 80 – 109, 109 – 158, 158 – 210 |
| R1 | Verified repair: faulty / frozen / DO-1 robots side by side, real time | RECORDED PLAYBACK, NO_AI | `02_recorded_demo_pages/take3_gpu/take.mp4` | 0 – 16.3 |
| R2 | Validation and confirmation counts; "why the longer walk is not a full recovery" | RECORDED PLAYBACK, NO_AI | same | 16.3 – 57.0 |
| R3 | Nemotron's experiment: damaged robot, competing hypotheses | RECORDED PLAYBACK of a LIVE run | same | 57.0 – 87.3 |
| R4 | The fork: tied information gain; Nemotron picks freq × 0.85, the engine freq × 1.2; Nemotron's verbatim reply | RECORDED PLAYBACK of a LIVE run | same | 87.3 – 103.9 |
| R5 | Both experiments on the damaged robot; the belief ends on opposite sides | RECORDED PLAYBACK | same | 103.9 – 146.0 |
| R6 | Repair delegated to the engine; independent verification (23/24 vs 20/24) | RECORDED PLAYBACK | same | 146.0 – 177.9 |
| R7 | How representative: replicate PARTIAL; 36 instances 15 vs 14 | RECORDED PLAYBACK | same | 197.4 – 209.9 |
| R8 | Every study: favourable, mixed, negative | RECORDED PLAYBACK | same | 209.9 – 225.8 |
| G1 | The Forge Loop diagram | ILLUSTRATIVE | `03_graphics/architecture_1920x1080.png` (source `docs/assets/architecture.svg`) | – |
| G2 | Creature Forge mark (same geometry and colours as the Studio header) | ILLUSTRATIVE | `03_graphics/creature-forge-mark_512.png` | – |

Stills for thumbnails and title cards are next to each take (`stills/`). An earlier automatic cut of take 3 with
captions is `02_recorded_demo_pages/rough_cut_v2/` (173.5 s; its narration is in `video/narration.srt`).

## 4. Verified statistics suitable for on-screen text
Use these exactly; each has its source and its caveat. Do not round p-values into "significant".

| On-screen text | Caveat to keep nearby | Source |
|---|---|---|
| "Pre-registered: Nemotron's redesigns verified in 6 of 12 investigations; matched random edits in 1 of 12" | small study, mostly push challenges | `experiments/forge_loop/scoreboard/REPORT.md` |
| "Verified on 12 held-out seeds: 12 wins, 0 losses" (live1) | one recorded run | `experiments/forge_loop/demo_capture/live1/` |
| "Same evidence, different question: Nemotron's experiment found the hidden fault; the engine's did not" | one instance, chosen afterwards | `docs/NEMOTRON_CONTRIBUTION.md` |
| "Across 36 robots: Nemotron 15, engine alone 14 — parity" | say "parity", never "better" | same |
| "A fixed non-AI procedure recovered walking in 19 of 48 fresh robots; the AI director in 9" | NO_AI winner | `docs/WALK_RECOVERY.md` |
| "160 robots with unseen damage: diagnosis engine 56, exhaustive search 46 — inconclusive" | NO_AI; p = 0.061 | `docs/E1_RESULTS.md` |
| "Every proposal is tested against a random change of the same size" | – | `docs/ARCHITECTURE.md` |

## 5. What must be disclosed on screen or in narration
1. **Simulation only.** MuJoCo; no hardware.
2. **Recorded vs live.** Label take-3 pages as recorded runs. live1 and live3 are live recordings from 2026-10-16.
3. **The Verified repair (DO-1) involves no AI.** Never attribute it to Nemotron. It was reliable on one robot, not in
   general (R0).
4. **Nemotron's experiment is one selected case**; the broad result is parity.
5. **Learning from experience was not demonstrated.** Do not show memory, "learns from failures" or "gets smarter" claims.
6. **Cuts.** If the investigation wait is cut, caption it ("about 5 minutes cut").
7. **Nemotron proposes; MuJoCo and a fixed rule decide.** The model never scores its own proposal.

## 6. What the audience must understand about Nemotron and Nebius
- Nemotron 3 Super is called **at runtime** through **Nebius Token Factory** from inside the Studio, for diagnosis,
  experiment choice and bounded repair proposals; strict JSON-schema output makes every proposal machine-checkable.
- Each call is cheap and fast in our records (about 3 to 5 s, about $0.002).
- **Nebius AI Cloud** Compute VMs ran the large batch studies (thousands of physics episodes) behind the statistics.

## 7. Recommended narrative arc (about 2:45)
1. **Hook (0:00–0:15):** a drawn robot falls (L1). "AI can explain this. But is the explanation true?"
2. **The idea (0:15–0:30):** G1 diagram: model proposes, physics measures, a fixed rule judges.
3. **Live loop (0:30–1:45):** L2–L7, with the wait cut and captioned. This is the one-minute-plus module footage.
4. **The scientist (1:45–2:20):** R3–R6: same evidence, different experiment, verified repair; then R7 parity.
5. **Honesty (2:20–2:40):** L8 (the verifier says no) and the statistics table, including the NO_AI results.
6. **Close (2:40–2:50):** what it is for: AI suggestions for physical systems that arrive with physical evidence.

## 8. Missing or optional footage (owner's decision)
| Item | Why | Cost and how |
|---|---|---|
| A fresh no-key capture of the current Studio: Home, *Create → Draw*, a challenge, a replay | live1 was recorded at code `e42e64e` (2026-10-16); the Forge Loop code is identical to `main` @ `e58dbdf`, but the release Studio adds a Home entry and later pages | Free, local: start the Studio, then capture with OBS (`VIDEO_PRODUCTION.md` §5). Never film the SCRIPTED MOCK as a model reply |
| Optional new LIVE Forge Loop take on the release build | footage of the exact release with a live call | Needs the owner's approval for about 2 to 3 Token Factory calls (≈ $0.005), local machine only. `cd studio && LIVE_OK=1 BROWSER_PATH="<Edge path>" BASE_URL=http://127.0.0.1:8000 OUT_DIR=<dir> ATTEMPT=1 KIND=push TARGET_FORCE=15 node e2e/forge-demo-capture.mjs` against a Studio started with a key and `CREATURE_FORGE_ENABLE_LIVE=1`. Record every attempt; do not re-roll |
| Voice-over | the narration is the owner's | Read from your final script; about 130 words per minute |

## 9. Replay commands for the recorded pages (no key, no cost)
```sh
npm --prefix studio run build
python scripts/run_studio.py                 # then open ?tab=recovery and ?tab=nemotron
cd studio && BASE_URL=http://127.0.0.1:8000 OUT_DIR=<dir> node e2e/demo-video-capture.mjs   # take-3 style capture
```
`demo-video-capture.mjs` blocks every request except the recorded pages' APIs and refuses software rendering for final
footage (see `VIDEO_PRODUCTION.md` §2).

## 10. The package
Location (outside Git): `%USERPROFILE%\CreatureForge-archive\video_package_2026-10-27\` (152 MB, 67 files plus
`SHA256SUMS`). The files are copies; the originals in the git-ignored `artifacts/` folders are untouched.

| Folder | Contents |
|---|---|
| `01_live_forge_loop/live1_push_verified/` | `take.mp4` (586.8 s, 1920×1080), an earlier 122 s rough cut, 11 stills, `capture_manifest.json` |
| `01_live_forge_loop/live3_walk_not_verified/` | `take.mp4` (208.3 s), 9 stills, `capture_manifest.json` |
| `02_recorded_demo_pages/take3_gpu/` | `take.mp4` (226.3 s, real GPU), 13 stills, chapter manifest |
| `02_recorded_demo_pages/rough_cut_v2/` | 173.5 s cut with and without captions, `narration.srt`, `report.json` |
| `02_recorded_demo_pages/extra_stills/` | page stills from the 2026-10-21 W2 and DO-1 captures |
| `03_graphics/` | architecture diagram (SVG, PNG) and the mark (SVG, PNG) |

Key hashes (SHA-256):
- `live1/take.mp4` `ab2c1488e68ba739745e3e173d52c3572c389cd3ba8edf06062cd594225d2b8f` (hashed at packaging; the 2026-10-16
  capture manifest records chapter times, not the video hash)
- `live3/take.mp4` `83b75cd00fb8298d6c3dd6c5759dae07f2010a693ade4e57bb6a906ca8d288a9` (same note)
- `take3-gpu/take.mp4` `b13f4d9cf9c869ea508b2c90bbfe6c6cd556531580330882d1be4a5e9d58e6ed` (matches `video/media_SHA256SUMS.txt`)
- `rough_cut_v2/rough_cut_clean.mp4` `60f1f5152c575aeb5a7123d34a900d01d859b70cb5ac2ccc4fefe418aa08c542` (matches)

Verify a copy with `sha256sum -c SHA256SUMS` inside the package folder. Back the folder up off this machine.
