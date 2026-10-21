# Video production: tools, capture workflow, edit and export (W5, 2026-10-21)

The storyboard and narration are in `STORYBOARD.md`. The cut list (picture plus words, the single source) is
`video/cutlist.json`.

## Tools on this machine (checked 2026-10-21; nothing was installed twice)

| Tool | Version | Source | Use |
|---|---|---|---|
| FFmpeg / ffprobe | 8.1 full build (gyan.dev) | already installed, `C:\Users\mbnas\ffmpeg-8.1-full_build\…\bin`, on `PATH` | screencast → H.264, trims, cards, captions, MKV remux, checks |
| Playwright | `playwright-core` 1.49.1 (`studio/node_modules`) | existing project dependency | deterministic choreography plus CDP screencast |
| Browser | Microsoft Edge (system) | existing | headless, **real GPU** (ANGLE D3D11, Intel Iris Xe) |
| OBS Studio | 32.2.2 | **installed** with `winget install --id OBSProject.OBSStudio --exact --source winget`; the installer hash was verified by winget | optional manual capture; voice-over recording |
| Clipchamp | 4.7.10020.0 | already installed (Microsoft Store) | final edit: voice-over, timing, export |

**Not installed, on purpose.**
- **Playwright's own video recorder.** It wants its bundled `ffmpeg-1010`, but the installed `playwright-core` 1.49.1
  only finds 1011 and 1013. That mismatch is real, but it does not matter: the capture uses a CDP screencast and the
  system FFmpeg 8.1, so no Playwright FFmpeg is needed.
- **A heavy editor** (DaVinci Resolve). Clipchamp covers trimming, voice-over and 1080p export.
- **New MCPs or skills.** The Playwright MCP has no Chrome here. The repository's `playwright-core` scripts are enough
  and are reproducible.

## 1. Start the Studio without running physics

The filmed pages only play back pinned files, so no simulation is needed for filming.
- **Option A: the real Studio.** Run `powershell -ExecutionPolicy Bypass -File scripts\start_studio.ps1`, then open
  `http://127.0.0.1:8000`. Its start-up computes the usual Phase 0 demo rollouts (a nominal biped, unrelated to the
  footage).
- **Option B: no physics at all.** A FastAPI app with only the read-only routers (`create_do1_router`,
  `create_nemotron_router`, the scientist/causal routers with replays disabled) and the built `studio/dist`. Stub
  `/api/schema` and `/api/experiments/phase0` (the app shell needs `baseline`, `candidate` and `matched_seed_summary`).
  Add a MuJoCo tripwire on `mj_step`/`mj_forward`. This is how the 2026-10-21 takes were made, with 0 tripwire hits.

Build the frontend first: `npm --prefix studio run build`.

## 2. Automated capture (raw footage)

```
cd studio
BASE_URL=http://127.0.0.1:8000 OUT_DIR=<dir> node e2e/demo-video-capture.mjs
#   [ZOOM=0.8] [PACE=1] [SHOTS=hook,do1,why,nemo-intro,failure,hypotheses,fork,measure,belief,repair,verify,lab,scope,close]
#   SOFTWARE=1 PACE=0.3 for a quick smoke test with SwiftShader (never for final footage)
```

**What it does:**
- **Browser.** Headless Edge on the **real GPU**. No window opens, so nothing on the desktop is captured and the 200 %
  display scaling of this laptop (2560×1600, 1280×800 logical) cannot crop it.
- **Renderer check.** The take is refused if WebGL reports a software renderer.
- **Framing.** The page is laid out at 2400×1350 CSS px, rendered at 0.8 scale, so every frame is exactly 1920×1080 and
  whole sections fit, uncropped. `ZOOM=1` gives a 1:1 layout with larger text and less per frame.
- **Clean profile.** A fresh browser profile is used. Only page content is recorded: no address bar, tabs, bookmarks or
  desktop.
- **Allow-list.** It blocks every request except `GET /api/do1/*`, `/api/nemotron/*` and the shell's start-up reads.
  Blocked requests are listed in the manifest (0 expected).
- **Shot order** follows the storyboard:
  1. The Verified repair page: the illustrative seed at 1×, then the cards and the "why" panel.
  2. "Nemotron's experiment": the hero flags, then stages 1–9, with the three damaged-robot replays played at 1×.
     It shows the seed where the two experiments differ, then the seed where Nemotron's own experiment fell.
  3. The laboratory strip, the representativeness stage and the study table.
- **Output** in `OUT_DIR`:
  - `take.mp4`: constant 30 fps H.264, built from the screencast timestamps.
  - `frames/`.
  - `stills/*.png`.
  - `manifest.json`: per-chapter `video_start`/`video_end`, the renderer, checks, blocked requests and console errors.

  One 404 per page load is expected: the Studio has no `/favicon.ico`.

**Done on 2026-10-21:**
- `take2-gpu`, in the git-ignored `artifacts/capture/video_2026-10-21/`;
- the smoke takes, in session scratch.

## 3. Rough cut (automatic)

```
python scripts/video_rough_cut.py --take <OUT_DIR> --out <dir>
```
- It cuts the take by chapter, as `video/cutlist.json` specifies, and adds the text-only title and end cards.
- **Outputs:**
  - `rough_cut.mp4`, with captions burnt in;
  - `rough_cut_clean.mp4`, the picture only, for the voice-over;
  - `narration.srt`;
  - `report.json`, with segment times and the checks (< 180 s, 1920×1080, 30 fps).
- To change timing, edit the cut list, not the script.

## 4. Voice-over and final edit (owner, about 30 minutes)
1. **Record the voice-over.** Either use Clipchamp (Record & create → Audio), or OBS: Settings → Output → Recording,
   format MKV, audio only from your microphone, then File → Remux Recordings to MP4/M4A. Read the narration column of
   `STORYBOARD.md` per shot, calmly; about 130 words per minute.
2. **Build the timeline.** In Clipchamp, import `rough_cut_clean.mp4` and the voice-over, plus `narration.srt` if you
   want captions (Captions → upload). Align each recorded paragraph to its shot's start time in `report.json`, and trim
   pauses.
3. **Export:** 1080p, MP4. Check with
   `ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate final.mp4`. It must be under 180 s,
   1920×1080 and 30 fps.
4. **Before uploading:** go through the safety list in `STORYBOARD.md` (no logos, no consoles or keys, caveats present).
   Do not upload or publish without your own decision; YouTube visibility is part of the submission choice.

## 5. Manual OBS capture (only if a hand-held take is preferred)
- **Settings:**
  - Video: Base 1920×1080, Output 1920×1080, 30 FPS.
  - Output: Recording, MKV, encoder "QuickSync H.264" (Intel hardware), with x264 as the fallback.
- **Source.** Add a *Window Capture* of the browser window only, not *Display Capture*. In Edge, open the Studio in an
  InPrivate window; use F11 full screen, zoom 80 % (Ctrl −) to match the automated framing.
- **After recording:** File → Remux Recordings → MP4.
