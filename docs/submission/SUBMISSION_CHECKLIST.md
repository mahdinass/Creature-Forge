# Submission compliance checklist (final candidate, 2026-10-27)

- **Source of truth:** the official rules at `https://nebiusglobalaihackathon.devpost.com/rules` and the challenge page,
  both read on 2026-10-27. Quotes below are from the rules.
- **Deadline:** Friday 2026-10-30, **10:00 PDT = 17:00 UTC = 18:00 Oslo** (CET). Drafts can be saved on Devpost before then;
  the submission cannot be changed after the deadline.
- **Status values:** DONE = verified in the repository or by a check named here; OWNER = only the owner can do it;
  OPEN = still to do. Responsible person: **Owner** (Mahdi) or **Release prep** (this branch; already done).

## 1. Project requirements
| Requirement (rules) | Status | Evidence | Remaining | Who |
|---|---|---|---|---|
| "A working software application" | DONE | Studio installs and runs from the README; local run on 2026-10-27 served the app and both demo APIs (HTTP 200); 199 frontend tests and the Python suite; CI on Ubuntu | Re-check CI green on the PR head | Owner reviews |
| "Runs on Nebius Token Factory or Nebius AI Cloud": "makes a runtime call to the Token Factory inference API, or is deployed/run using Nebius AI Cloud compute (Serverless Jobs, Serverless Endpoints, or DevPods)" | DONE via **Token Factory runtime calls** | `creature_forge/nebius.py`; live Studio investigation records with request ids (`experiments/forge_loop/demo_capture/live1/`, `docs/submission/evidence/live_acceptance_2026-10-24.json`) | Do **not** claim the AI Cloud clause: our VMs were Compute instances, not Serverless Jobs, Endpoints or DevPods. The Devpost text already says so | – |
| "Uses at least one NVIDIA open source model" | DONE | `nvidia/nemotron-3-super-120b-a12b` (`experiments/forge_loop/model_config.json`); Ultra and Nano in calibration and prototype | – | – |
| Track fit: Physical AI, "embodied and edge agents… robotics… powered by Nemotron"; Stage One requires a "genuine attempt at the track's stated goal" | DONE (simulation-only robotics) | README, DEVPOST.md | Owner confirms the track choice on the form | Owner |
| "Functionality: … must function as depicted in the video and/or expressed in the text description" | DONE for the text; **OWNER** for the video | Video must show only footage of the real app, labelled live or recorded (`VIDEO_HANDOFF.md` §5) | Check the final cut against §5 | Owner |
| "New & Existing": new projects, or explain significant updates | DONE | First commit 2026-10-13, inside the submission period (from 2026-08-26) | State "new project" on the form | Owner |
| "Third Party Integrations: authorized to use them" | DONE | `THIRD_PARTY_NOTICES.md`, `docs/MODEL_AND_SERVICE_TERMS.md`, `LICENSE_REVIEW.md` | The optional clarification draft (`NEBIUS_CLARIFICATION_REQUEST.md`) was never sent; it is not required | Owner (optional) |

## 2. Submission requirements
| Requirement (rules) | Status | Evidence | Remaining | Who |
|---|---|---|---|---|
| Demo URL / test build | Not required for Physical AI ("not required for Physical AI submissions") | Local quick start is the test build | – | – |
| "Text description that should explain the features and functionality" | DONE (draft) | `docs/submission/DEVPOST.md` | Review and paste | Owner |
| "URL to your public code repository" on GitHub | **OPEN** | Repository `mahdinass/Creature-Forge` is **PRIVATE** (checked 2026-10-27 with `gh repo view`) | Make it public after the pre-publication checks in §4 | Owner |
| "The repository must contain all necessary source code, assets, and instructions" | DONE | Source, frontend, recorded demo records (hash-pinned) and instructions are in Git. Large raw archives and videos are outside Git and are not needed to run the app | – | – |
| "Public and open source… license file… visible at the top of the repository page (About section)" | DONE for the file; detection to re-check after going public | `LICENSE` (Apache-2.0); GitHub's API already reports `apache-2.0` | Look at the About box once public | Owner |
| "README with setup instructions and clear guidance for running" | DONE on this branch | `README.md`, `docs/submission/JUDGE_TESTING.md` | **The default branch `main` still shows the old README** until the release PR is merged | Owner (merge) |
| "Highlight how you've used NVIDIA Nemotron… where Token Factory accelerated your workflow and any other Nebius Tools" | DONE | README *NVIDIA and Nebius*, DEVPOST *How we used NVIDIA and Nebius* | – | – |
| Video "less than three (3) minutes" | **OWNER** | Assets: `VIDEO_HANDOFF.md`; earlier cut was 173.5 s | Check the final export with `ffprobe` (< 180 s) | Owner |
| Video "uploaded to and made publicly visible on YouTube" | **OWNER** | – | Upload as **Public** (the rules say publicly visible) and paste the link | Owner |
| Video "must not include third party trademarks, or copyrighted music" | **OWNER** | Captures contain no NVIDIA or Nebius logos | Use rights-cleared music only; names as plain text | Owner |
| Physical AI: "at least one minute of footage… the key application modules in action" | Assets DONE; cut **OWNER** | `live1` holds about 4 min of real Forge Loop footage, plus 3.8 min of recorded demo pages (`VIDEO_HANDOFF.md` §2–§3) | Keep at least 60 s of real module footage in the cut | Owner |
| "Identify which track" | **OWNER** | Physical AI | Select on the form | Owner |
| "Provide feedback on Nebius Token Factory, AI Cloud and any NVIDIA tools" | DONE (draft) | `docs/submission/FEEDBACK.md`, paste-ready summary at the top | Paste into the form | Owner |
| English | DONE | All submission text is in English | – | – |
| Team representation | **OWNER** | Solo entrant as far as the repository shows (every commit is by the owner's local or GitHub identity; AI-assistant commits carry a `Co-Authored-By` line) | If teammates exist, invite them on Devpost and appoint the Representative | Owner |
| "Testing: Access must be provided… free of charge and without any restriction… until the Judging Period ends" (15 Dec 2026) | DONE once public | Public repository + local run; no login needed | Keep the repository public and unchanged in substance until 2026-12-15 | Owner |
| Final Devpost submission | **OWNER** | – | Submit before 10:00 PDT on 30 Oct; save a draft early | Owner |

## 3. Release integration (needs the owner's approval)
| Item | Status | Notes |
|---|---|---|
| Release PR `release/v1-submission` → `main` | OPEN, awaiting review | Contains `release/v1` (PR #19), `release/v1-rc2-prep` (PR #20) and this submission work. Merging it makes the judge-facing README the default page. Use a **merge commit** (keeps every frozen commit) |
| PRs #19 and #20 | Superseded once the release PR is merged | Close them, or merge them first in order (#19 then #20); either way the content is identical |
| Tag `v1.0.0-rc2` (or `v1.0.0`) | OPEN | Proposed on the merged commit after CI is green. Never move `v1.0.0-rc1` |
| PRs #22 (H1), #23 (H3), E-2R | **Not part of the release** | Research records; summarised in `docs/RESEARCH_STATUS.md` |
| PR #17 (demo capture), PR #18 (CI license fix) | Not merged | The demo-capture records and the capture script were imported byte-identically into this branch; #18 overlaps the V1 workflow change |

## 4. Pre-publication checks (before making the repository public)
- [x] **Reachable-history secret scan** on 2026-10-24 (rc2): every blob reachable from all refs, the real key value and 6
      credential patterns: 0 hits. **Re-run on 2026-10-27** for the new commits of this branch: see `docs/RELEASE_V1.md` §10.
- [x] `.env` is untracked and ignored; `.env.example` has no values.
- [x] No local Windows paths in the new tracked documents (checked 2026-10-27).
- [ ] **Owner decision: making the repository public publishes every branch**, including research branches and draft PRs.
      That is intended for transparency; it is irreversible in practice (forks, caches).
- [ ] **Owner decision: author e-mail in Git history.** It cannot be removed without rewriting history, which would break
      the frozen hashes. Accept it, or decide before going public.
- [ ] **Owner decision: Nebius resource ids** (project, instance and service-account ids in `infra/nebius/` and some
      docs). They are not credentials; redact only if you prefer.
- [ ] **Service-account keys** live outside the repository (WSL home and the VMs); they expire 2026-11-07. Nothing to
      publish; consider revoking them after the hackathon.

## 5. Final human-only actions, in order
1. Review and merge the release PR into `main` (merge commit). Confirm CI is green on `main`.
2. Decide the §4 items, then make the repository public. Confirm the About box shows Apache-2.0.
3. Produce the video from `VIDEO_HANDOFF.md`; export < 180 s; upload to YouTube as Public.
4. Paste `DEVPOST.md` and the `FEEDBACK.md` summary into Devpost; select **Physical AI**; add the repository and video URLs.
5. Add teammates, if any. Save a draft, then submit before **18:00 Oslo on Friday 30 October**.
6. Keep the repository public and the Nebius VMs stopped. Back up `%USERPROFILE%\CreatureForge-archive\`.
