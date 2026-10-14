# Final submission checklist

Official deadline **Fri 2026-10-30, 18:00 Europe/Oslo**; internal deadline **Thu 2026-10-29**. Status as of 2026-10-14 (✅ done · ⬜ open · 🧑 needs the owner).

## Hackathon deliverables (docs/PROJECT_SPEC.md §1.2)
| item | status | notes |
|---|---|---|
| Functional application matching what is filmed | ✅ | Studio on `main`; CI green; real-browser flows for Overview, AI Investigation, Locomotion, Lab |
| Uses an NVIDIA open model at runtime | ✅ | Nemotron 3 Nano via Token Factory in `creature_forge/demo.py`; two real recorded calls (13 requests, 70,764 tokens total in the shared budget) |
| Runs on Nebius Token Factory / AI Cloud | ✅ | runtime inference + CPU VM experiments (R1/R2); logs and ledgers in `experiments/` |
| Public source repository | 🧑 | make public after the pre-publication checks below |
| Open-source licence visible | ✅ | Apache-2.0 `LICENSE`, `NOTICE` (Copyright 2026 Mahdi Nasser), `THIRD_PARTY_NOTICES.md` |
| README: install, prerequisites, env vars, run, demo scenario, evaluation reproduction | ✅ | `README.md`, `docs/submission/SETUP_AND_REPRODUCTION.md` |
| Where NVIDIA / Nebius are used | ✅ | README table; `docs/submission/DEVPOST.md` |
| YouTube video < 3 min, ≥ 1 min of modules operating | ⬜ 🧑 | storyboard and capture plan ready (`STORYBOARD.md`, `SCREEN_CAPTURE_PLAN.md`) |
| Text description, track, feedback on Nebius/NVIDIA technologies | ✅ draft | `DEVPOST.md`, `FEEDBACK.md` (review and paste) |
| Judging access | ⬜ | local reproduction + recordings need no key; decide hosting (see below) |
| English material | ✅ | |
| Available through 2026-12-15 | ⬜ 🧑 | repository must stay public and runnable; no always-on VM is planned (≈ $6.5/day) |
| Submit before the deadline | 🧑 | |

## Pre-publication checks (before making the repository public)
- [ ] Full reachable-history secret scan on the final refs (`scripts` snippet in `docs/MODEL_AND_SERVICE_TERMS.md` §3; last run 2026-10-14: 0 matches in all objects).
- [ ] Zero AI co-author trailers on any ref (last check: 0; the local backup branch and `refs/original` were removed 2026-10-14).
- [ ] `.env` untracked and ignored; `.env.example` has no value; no key in logs under `experiments/*/logs`, `results*/` (scan covers them).
- [ ] `THIRD_PARTY_NOTICES.md` regenerated after any dependency change; no UNKNOWN licences.
- [ ] `git ls-files` shows no third-party binary assets; videos/screenshots in the repo (if any) are original.
- [ ] README renders correctly on GitHub; badges/links work; no private paths.
- [ ] CI green on `main`.
- [ ] Written clarification on public references to Nebius/NVIDIA requested (`NEBIUS_CLARIFICATION_REQUEST.md`) and the answer (or its absence) recorded.
- [ ] Decide whether the immutable preregistered records stay in the public repository (recommended: yes, they are the evidence).

## Unresolved questions (record, do not guess)
1. Does hackathon participation constitute Nebius's consent under Services Agreement §18.7 for factual public references? (request drafted, not yet sent)
2. NVIDIA Nemotron Open Model License: no text on hosted/API-only use; appendix and any other NVIDIA pages not read. No weights are distributed.
3. Nebius AUP, Service-Specific Terms and DPA were not read in full.
4. Hosted judging access: the replays need a Python backend; options: (a) judges run locally from the README; (b) a small hosted instance (cost, abuse and key-safety limits needed); (c) video + recorded runs only. Decision needed from the owner.
5. Tavily bonus: not pursued (not relevant to the core experience).

## Plan to the internal deadline (supersedes `docs/MILESTONE_PLAN.md`; R3 v3 cancelled by the owner)
| date | work |
|---|---|
| Wed 14 Oct | PRs #9–#12 merged, CI green on `main`; Overview tab, README, submission package drafted (this branch) |
| Thu 15 – Fri 16 Oct | Review the drafts; send the Nebius/organizer clarification; decide judging access |
| Sat 17 – Sun 18 Oct | Polish Studio copy and mobile layout; record screen footage per the capture plan |
| Mon 19 – Tue 20 Oct | Voice-over and edit; first cut under 3:00 |
| Wed 21 Oct | Repository audit (scans, notices, README on a clean clone); fresh-clone install + tests on a clean Linux VM (start, test, stop) |
| Thu 22 Oct | Final cut; upload to YouTube (unlisted); Devpost draft complete |
| Fri 23 – Mon 26 Oct | Buffer; answers from Nebius/organizers; fixes only |
| Tue 27 Oct | Make the repository public (owner); verify links from a logged-out browser |
| Wed 28 Oct | Submission dry run on Devpost; all fields filled |
| **Thu 29 Oct** | **Submit.** Then delete the VM and disk after confirming results are archived (owner decision) |
| Fri 30 Oct | Buffer only (deadline 18:00 Oslo) |

## Cost status
Nebius VM stopped (disk ≈ $0.12/day). Inference used: 13 requests / 70,764 tokens (≈ $0.35 at an assumed $5 per million tokens; price unverified). No GPU was provisioned.
