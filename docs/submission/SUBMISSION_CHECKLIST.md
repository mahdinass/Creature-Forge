# Final submission checklist (V1)

- **Deadlines:** the official deadline is **Fri 2026-10-30, 10:00 PDT = 17:00 UTC = 18:00 Europe/Oslo** (Oslo is on CET
  from 25 Oct); the internal target is **Tue 2026-10-27**,
  with 28–29 October as buffer.
- **Status as of the V1 release candidate.** The release record is `docs/RELEASE_V1.md`. Status values: done = verified in
  the repository; OWNER = needs the owner.
- **The repository is private.** Nothing has been uploaded, published or submitted.

## Hackathon deliverables (docs/PROJECT_SPEC.md §1.2)
| Item | Status | Notes |
|---|---|---|
| Functional application matching what is filmed | done | Branch `release/v1`, tag `v1.0.0-rc1`. The filmed pages are *Verified repair* (`?tab=recovery`) and *Nemotron's experiment* (`?tab=nemotron`). Both are recorded playback, so they need no key. CI runs both flows on a clean Ubuntu checkout |
| Uses an NVIDIA open model at runtime | done | Nemotron 3 Super via Token Factory: the recorded HaS scientist calls (request ids in `experiments/w2/`) and live Forge Loop calls when a key is set |
| Runs on Nebius Token Factory / AI Cloud | done | Inference on Token Factory; all heavy simulation on Nebius CPU VMs (`infra/nebius/`) |
| Open-source licence visible | done | Apache-2.0 `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md` |
| README: install, prerequisites, env vars, run, demo, reproduction | done | `README.md` (judge quick start), `docs/submission/SETUP_AND_REPRODUCTION.md`. Commands verified in a fresh-venv clean clone; see the release record |
| Where NVIDIA / Nebius are used | done | README table; `DEVPOST.md` |
| Video < 3 min, ≥ 1 min of the application operating | **OWNER** | Picture done: rough cut v2 is 173.5 s at 1920×1080 (`video/rough_cut_v2_report.json`). The narration is corrected for W3 (`STORYBOARD.md` = `video/cutlist.json` = `video/narration.srt`). **To do: record the voice-over, export, check < 180 s** (`VIDEO_PRODUCTION.md` §4) |
| Text description, track, feedback | draft ready / **OWNER** | `DEVPOST.md` (V1, matches the app and video); `FEEDBACK.md` (review and paste) |
| Public repository or judge access | **OWNER** | Private. Before any visibility change, run the pre-publication checks below |
| Available through 2026-12-15 | **OWNER** | Depends on the visibility decision; no always-on VM is planned (the demo runs locally) |
| Submit before the deadline | **OWNER** | |

## Owner decisions (none are taken without the owner)
1. **Visibility:** make the repository public, or give judges access another way.
2. **YouTube:** upload the final video, with the visibility of your choice (unlisted or public), and paste the URL into
   Devpost.
3. **Devpost:** review `DEVPOST.md`, paste it and submit.
4. **Integration PR into `main`:** review and merge (PR link in the release record). A merge commit keeps every frozen
   commit; a squash would not keep them on `main` but leaves the release tag intact.
5. **PR #18 (`fix/ci-license-and-workflow`):** not part of V1. It overlaps the V1 workflow change. Close it, or rebase it
   after V1.
6. **AI co-author disclosures:** kept, as the owner instructed. The earlier "zero AI trailers" item is withdrawn: the
   `Co-Authored-By` lines are a deliberate disclosure.
7. **Git-history e-mail exposure:** the author e-mail is in history. Accept it, or decide before publication; any rewrite
   would break the frozen hashes.
8. **Benchmarking clause and §18.7 clarification:** open (`MODEL_AND_SERVICE_TERMS.md` §1b, `LICENSE_REVIEW.md` §3c,
   `NEBIUS_CLARIFICATION_REQUEST.md`, not sent).
9. **Off-machine backup:** copy `%USERPROFILE%\CreatureForge-archive\2026-10-21\`, which holds the raw archives and the
   video, to a private disk or drive. Then run `sha256sum -c ARCHIVES.sha256` on the copy
   (`docs/NONGIT_ASSETS_2026-10-21.md`). Afterwards, also copy `artifacts/capture/video_2026-10-21/rough_cut_v2/` and your
   final export.

## Pre-publication checks (before any visibility change)
- [x] **Reachable-history secret scan** (2026-10-24, rc2). Scope: every blob reachable from all 100 local and remote refs and
      tags (2,476 blobs, 397 MB), checked for the actual key value (from `.env`, in memory, never printed) and 6
      credential patterns (key assignment, bearer, private-key block, JWT, `sk-`, AWS). **0 hits.** Re-run after any new
      commit before going public.
- [x] **No secrets in tracked files:** `.env` is untracked and ignored, and `.env.example` has no value.
- [x] **No local Windows paths** in tracked docs (re-checked for V1).
- [x] **Third-party notices are current.** The dependency files are unchanged since they were generated. `--check` reports
      "stale" on this Windows venv only because its versions are older (numpy 2.4.6 vs the recorded 2.5.4). The committed
      file matches the recorded environment and keeps the verified `webgl-constants` licence note.
- [ ] **Nebius resource ids** (project and instance ids in `infra/nebius/` and some docs): decide whether to redact them
      before going public. They are not credentials.
- [ ] **CI green on the final head:** check the release record before publishing.

## rc2 status (2026-10-24; PR #20, `release/v1-rc2-prep`)
| Item | Status | Evidence |
|---|---|---|
| E-1 result, with defensible wording | done, **OWNER review** | README and Devpost paragraphs. Primary inconclusive; ablation supportive, not study-wide significant; failure analysis exploratory; no experience-learning claim |
| CI on the rc2 head | re-run after the frozen-manifest fix | The only failure on the first rc2 run was the frozen-record guard: the E-1 records were not in `FROZEN_MANIFEST.json`. Fixed (42 additions, nothing changed) |
| Live NVIDIA model at runtime | done, re-verified 2026-10-24 | Super and Nano connectivity (HTTP 200); live end-to-end Studio investigation (`docs/submission/evidence/live_acceptance_2026-10-24.json`) |
| Nebius integration | done, re-verified 2026-10-24 | Token Factory calls above; AI Cloud VMs with a service-account API stop (STOPPED verified) |
| Feedback text | updated | `FEEDBACK.md`, section "Update, 2026-10-16 → 2026-10-24" |
| Unsupported-claim scan | done | Judge-facing text (README, Devpost, cut list, narration, storyboard, Studio UI) mentions experience learning only as "not demonstrated" and uses "significant" only in recorded verifier reasons |
| Video voice-over and export, YouTube, Devpost submit, visibility, PR #19 / #20 merges, `v1.0.0-rc2` tag | **OWNER** | See "Owner decisions" above |
