# Milestone plan to the NVIDIA × Nebius hackathon (written 2026-10-14)

Official deadline: **Fri 2026-10-30, 18:00 Europe/Oslo**. Internal hard deadline: **Thu 2026-10-29**. Dates are Oslo time. "You" = Mahdi (decisions/approvals); "I" = Claude Code. Priorities: (1) an honest, working AI-driven investigation demo, (2) Studio polish, (3) reproducible public release, (4) final video. R2 is finished and must not consume more calendar.

## Submission obligations that shape the plan (from `docs/PROJECT_SPEC.md` §1.2)
- Software must **use an NVIDIA open-source model (Nemotron) in an actual product run** and **run on Nebius Token Factory or AI Cloud**. Today: Nebius AI Cloud VM used for R1/R2 (done); Nemotron used in 3 Phase 1 calls only → R3 + demo mode are required, not optional.
- Public repository with a visible open-source licence (choose after dependency/IP audit), README (install, env vars, run, demo scenario, evaluation reproduction), no credentials in history or footage.
- Demo video < 3 min on YouTube, ≥ 1 min of the key modules actually running, no unlicensed content.
- Judging access: static-replay Studio (no hosted compute) + local reproduction; keep available through Dec 15 (so no always-on VM; see cost note).
- All text in English.

## Calendar
| date | milestone | owner | exit criterion |
|---|---|---|---|
| **Wed 14 Oct** (today) | R1 merged; R2 executed (null→positive result documented); R3 design + offline machinery + this plan | done | PR for R2 open (not merged); R3 tests green; no live model calls |
| **Thu 15 Oct** | Decisions: approve R3 protocol/cap (≈ 121k tokens, < $1); review R2 PR. I: register R3 protocol (seeds, caps, endpoints), implement R3 physics-evaluation stage (reuses R2 jobs/ledger) + tests with scripted model | You + I | R3 protocol committed before the first request; stage tests pass; VM ready (start only when needed) |
| **Fri 16 Oct** | **Live R3 batch**: evidence run → 30 requests (arms M, N) → matched-random + heuristic → screening → validation → report with all outcomes including null/invalid | I | `experiments/phase2a_r3/REPORT.md`; ledger + request log verified; VM stopped |
| Sat 17 – Sun 18 Oct | Buffer / weekend: R2 PR merge decision; optional Windows replication of the R2 final on a machine with ≥ 4 GB free; demo-mode loop (evidence → Nemotron → MuJoCo → replay) behind a "live vs replay" label | I | demo mode works end to end offline with the scripted model, and live behind an explicit flag |
| **Mon 19 Oct** | Studio: "Results" view for R2/R3 — θ0 vs winner side by side on a failing seed (existing synchronized replay), paired table, ledger/budget panel, honest limits text | I | view loads from bundled records, no backend compute needed |
| Tue 20 Oct | Studio: Investigation Lab shows R3 proposals with provenance (observed / model / measured), invalid replies, matched-random comparison | I | Lab browser check extended, passes at 320 px width |
| Wed 21 Oct | Locomotion tab updated with R2 winner, basin map, replay; frontend tests + build + browser flows green; CI green on a draft PR | I | all checks green locally and in CI |
| Thu 22 Oct | Public-release prep: dependency/licence audit, LICENSE choice (**your decision**), README rewrite, `docs/submission-checklist.md`, secret scan of full history, remove artifacts/backup branches from the public view if needed | I + You | fresh-clone install + `smoke_test.py` + `verify_demo_trials.py` + R2 reproducibility check pass on a clean Linux VM |
| Fri 23 Oct | **Feature freeze 18:00.** Demo script and storyboard (< 3 min: problem → failure autopsy → Nemotron proposal → MuJoCo verdict → before/after replay → R2/R3 honest results); screen capture list | I + You | storyboard approved |
| Sat 24 – Sun 25 Oct | Record and edit video; capture clean screen footage of live and replay modes (labelled); thumbnail; YouTube upload (unlisted) | You (+ I for scripts/captions) | video < 3 min, ≥ 1 min of modules running |
| Mon 26 Oct | Bug-fix only. Submission text (English), architecture diagram, limitations, track fit (Physical AI), team/ownership statements | I + You | draft of every required field |
| Tue 27 Oct | Fresh-checkout reproduction of every official artifact on a new VM (Nebius CPU, stopped afterwards); fix last issues; make repository public (**your action**) | I + You | checklist complete |
| Wed 28 Oct | Submission dry run on the platform; verify links (repo, video, demo), licence visible, no secrets | You | every field filled, nothing unverified |
| **Thu 29 Oct** | **Internal deadline: submit.** Delete the VM and disk after final retrieval; cost summary | You + I | submission receipt |
| Fri 30 Oct | Buffer only (official deadline 18:00 Oslo). No new features. | — | — |

## Decisions I need from you (by date)
- **Thu 15 Oct:** approve (or change) the R3 request cap and budget; confirm Nemotron model id stays `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.
- **Thu 22 Oct:** licence choice; whether the repository goes public on the 27th.
- **Fri 23 Oct:** feature freeze content; who records the voice-over.

## Cost note
Nebius VM $0.269/h while running + ~$0.12/day disk (stopped). R1+R2 used well under $1 of compute. Planned: R3 physics < $0.15, Nemotron < $1 (price unverified), a clean-checkout rehearsal ~$0.3. Judging access through Dec 15 should be static replays plus local reproduction, not a running VM (a running VM would cost ≈ $6.5/day).

## Risks
- R3 may show no benefit of the model over matched random edits (plausible). Mitigation: the demo is framed as a verifiable propose→simulate→verify loop with honest comparison; R2's optimiser result is the quantitative headline.
- Nemotron replies may be malformed (reasoning consumes tokens; `content: null` occurred before). Mitigation: strict parsing, all failures reported, budget fixed.
- Windows replication of the R2 final is blocked by RAM; documented limitation.
- Studio replay payload size (≈ 0.9 MB per run JSON) may slow static hosting; bundle only chosen seeds.
