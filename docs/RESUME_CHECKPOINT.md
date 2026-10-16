# RESUME CHECKPOINT — Creature Forge (written 2026-10-15 ~19:10 UTC)

Read this first. **Verify each fact against Git / the VM / GitHub before acting** (commands in §9); trust files and commits
over any conversation summary. The objective is to resume in minutes without redoing finished work.

## 1. Repository
- Repo `mahdinass/Creature-Forge` — **PRIVATE** (owner: keep private until the publication audit; ask before any publication).
- Working branch **`feature/forge-loop`**; HEAD at checkpoint = the commit that adds this file (see `git log -1`); previous
  code commit `be9b8d7`. Working tree clean at checkpoint (verify `git status`).
- **Draft PR #16** `feature/forge-loop` → `main`: **NOT merged**. Owner approval is required before merging (merge commit,
  never squash). Owner's merge conditions: CI green ✅, real live end-to-end UI test ✅ (see §3), critical security checks ✅
  (see §6) — all satisfied; **still ask the owner explicitly before merging.**
- **CI**: green on `9a18291` (both `test-context-guards` and `studio-frontend` incl. all browser flows). Re-check on HEAD.
- Superseded WIP branches (content already integrated; keep until the owner agrees to delete):
  `wip/s9-security-hardening-UNVERIFIED` (→ integrated as `269ec90`), `wip/s8-engineering-memory-UNVERIFIED` (→ `d3cda1f`).
- Local `.claude/worktrees/agent-*` directories are leftover agent worktrees; **all their work is integrated**; safe to
  remove with `git worktree remove` after a check.
- Authorship: commits by Mahdi, **no AI co-author trailers** (verified 0 on the branch). Keep it so.

## 2. Completed and verified (do NOT redo)
| milestone | evidence |
|---|---|
| M0 infra: remote dev loop on the Nebius VM, spend ledger, calibration | `infra/nebius/forge_dev.py`, `forge_cloud.py`; `experiments/forge_loop/calibration/REPORT.md` (model choice: Nemotron-3-Super-120B, thinking off, strict per-evidence JSON schema) |
| M1 challenges stand/push/walk on drawn creatures; zoo pilot | `creature_forge/challenges.py`, `creature_walk.py`; `experiments/forge_loop/pilot/` |
| M2 AI investigator, evidence, edit validation, ledger | `evidence.py`, `interventions.py`, `forge_ai.py`, `inference_ledger.py` |
| M3 arena + twins + verdict_v1 (frozen after A/A null pilot) | `arena.py`, `baselines.py` (matched_random_v2), `verdict.py`; `experiments/forge_loop/null_pilot/` |
| M4 orchestration, bounded loop (patience 2, never auto-accepts), accept/revert | `investigation.py`, `creatures.py`, `jobs.py`, `studio/forge_api.py` |
| M5 Studio "My creature" workspace (challenge, investigate, probes, twin, replay, accept, lineage) | `studio/src/forge/*`; browser flow `studio/e2e/forge-flow.mjs` |
| M6 diagnostic probes (incl. walk `retune_controller` probe) | `probes.py`; step-B CONFIRMED/REFUTED + method rule |
| Pre-registered scoreboard v1 (12 live investigations) | `experiments/forge_loop/scoreboard/REPORT.md` — AI 6/12 vs twin 1/12, exact one-sided p = 0.03125, push-dominated, with all owner-required caveats |
| Live walking investigations (B) | 7 records, `experiments/forge_loop/dev_live_records/README.md` "Walking": nothing verified; model never chose co-design |
| Engineering memory (C, implementation) | `creature_forge/memory.py`, `scripts/forge_memory.py`, evidence/prompt hooks, API flag, UI block (no vitest for the UI block yet) |
| Security hardening (all review findings) | `269ec90`, `creature_forge/studio/security.py`, `tests/test_security_review.py` (§6) |
| CI smoke scale for browser flows | `CF_INVESTIGATION_SCALE=smoke` (refused for live, recorded per record) |
| **Live end-to-end UI test** (owner merge condition) | `studio/e2e/forge-live-flow.mjs`; **final run i-140b1435cb84: 15/15 PASS**, verified redesign accepted as v2 in the browser; `experiments/forge_loop/dev_live_records/ui_live/` |
| Submission docs (D, partial) | `docs/submission/DEVPOST.md`, `STORYBOARD.md`, `SETUP_AND_REPRODUCTION.md`, `SUBMISSION_CHECKLIST.md`, `LICENSE_REVIEW.md`; regenerated `THIRD_PARTY_NOTICES.md`; terms doc updated; pydantic declared; local paths scrubbed |
| Tests (VM, combined tree) | 894 Python OK, frontend vitest + strict tsc + build OK, 237 browser checks PASS; frozen-record guard 105/105; secret scan of all 1,625 objects: 0 key hits |

## 3. Experiment artifacts and logs (all committed unless noted)
- Calibration: `experiments/forge_loop/calibration/` (requests.jsonl, requests_v2.jsonl, REPORT.md).
- Zoo pilot / null pilot: `experiments/forge_loop/pilot/`, `experiments/forge_loop/null_pilot/`.
- Development live records (unedited, protocol-state notes): `experiments/forge_loop/dev_live_records/` (+ `INDEX.json`,
  `ui_live/` screenshots and summaries).
- Scoreboard v1: `experiments/forge_loop/scoreboard/{protocol.json, REPORT.md, results/}` (registered `e12dd0e`).
- Memory evaluation: `experiments/forge_loop/memory_eval/{protocol.json, bank.jsonl}` (registered `670ffa3`-era commit
  "Memory evaluation: pre-register forge-memory-eval-v1"); **results NOT yet committed** — see §4.
- Frozen research records R1/R2/R3/Phase 1/2A/demo: unchanged (`experiments/FROZEN_MANIFEST.json`, `tests/test_frozen_records.py`).
- VM-side (not in Git): `~/dev/integ/artifacts/forge/` (creatures, runs, jobs, investigations), `~/logs/dev/*.log`,
  inference ledger `~/dev/ledger/inference_ledger.jsonl` (local backup `artifacts/vm/ledger_backup/`, may be stale).

## 4. Memory evaluation (forge-memory-eval-v1) — **COMPLETE 2026-10-16** (no evidence of a benefit; see §11 and `memory_eval/REPORT.md`; do not rerun or re-analyse)
- Protocol: 6 new creatures × 2 replicates = 12 pairs; per pair one push challenge run and two LIVE investigations (memory
  on/off) on identical seeds; frozen 34-lesson bank (sha256 in protocol); primary = exact one-sided McNemar; low power stated.
- Running at checkpoint time on the VM slot `integ` (driver `scripts/forge_memory_eval.py --run`, started ~18:36 UTC).
  Progress and final state are recorded in §11 (appended at shutdown).
- **Results live ONLY on the VM** until pulled: `~/dev/integ/experiments/forge_loop/memory_eval/results/runs.jsonl` and the
  records in `~/dev/integ/artifacts/forge/investigations/`. **Never run `forge_dev.py sync --slot integ` before pulling them**
  (sync runs `git clean -fd` and would delete the untracked results file).
- Resume: `python scripts/forge_memory_eval.py --resume` (on the VM, against a live server WITHOUT `CF_MEMORY`) runs only the
  registered pairs not yet in runs.jsonl; a pair interrupted mid-way is recorded as `interrupted` and excluded — never rerun.
- Analysis after completion: `python scripts/forge_memory_eval.py --analyze --records <records dir>` (pre-declared), then
  write `experiments/forge_loop/memory_eval/REPORT.md` honestly (null result is the expected outcome given the power).

## 5. Budgets (keep the caps; ask before raising)
- Infra: conservative ledger `infra/nebius/forge_cloud.py spend` (cap **$10**); ~$4.1 used at checkpoint (+ eval time).
- Inference: Forge ledger cap **$15 / 1,500 requests**; ~90+ requests, ~$0.45 used before the memory eval (+ ~24-36 calls).
- R3 legacy cap (41 requests / 300k tokens) untouched.

## 6. Security review status
Fixed and tested (`269ec90`): M1 job/creature/body limits (429/413), M2+L5 worst-case ledger settle / reservation release,
M3 Host allow-list + same-origin writes (`RequestGuard`; tests set `CF_ALLOW_TESTSERVER=1`), L1 no tracebacks to clients,
L2 fullmatch ids, L3 idempotent accept, L4 replay quantisation + concurrency cap; key redaction, no-redirect opener,
https-only base URL, slot/pull validation, safe tar extraction, nesting guard, `/api/version` without repo_root.
**Open (low, not blocking):** list endpoints read every record (no pagination), unbounded growth of jobs/runs/ledger files,
legacy `/api/demo/run` uses its own (R3) budget, scoreboard caps were enforced by the global ledger only (disclosed).

## 7. Next actions in priority order
1. ~~Memory evaluation~~ DONE 2026-10-16 (12/12 pairs, analysed once, `REPORT.md` committed). Verify states (§9) on resume.
2. Ask the owner for approval to merge PR #16 (all owner conditions are met; re-check CI on HEAD first).
3. Submission (D): record demo footage with a scripted Playwright capture of the live flow (raw clips; the owner does the
   voice-over/edit), update `SCREEN_CAPTURE_PLAN.md` and `NEBIUS_NVIDIA_FEEDBACK.md` to Super-120B, fresh-clone test on a
   clean VM slot, publication audit (git-history emails, `webgl-constants` licence UNKNOWN, model licence texts, Nebius
   benchmarking-clause question) — **no publication without the owner**.
4. Optional, only if time remains: vitest for the memory UI block; pagination for list endpoints.

## 8. Do NOT repeat
- Do not rerun calibration, zoo/null pilots, the scoreboard, the walking investigations or the live UI test.
- Do not re-register or edit any `protocol.json`, `bank.jsonl`, frozen record, or archived live record.
- Do not reinstall environments: VM slots `~/dev/<slot>` have venvs + node_modules; local `.venv` exists.
- Do not redo the codebase audit, security review or licence review; their outputs are committed.
- Do not rebuild working components (challenges, arena, verdict, probes, memory, Studio workspace).

## 9. Commands to resume
```powershell
cd C:\Users\<user>\.vscode\Creature-Forge
git fetch; git status -sb; git log -3 --oneline            # expect feature/forge-loop, clean
gh pr view 16 --json state,isDraft; gh pr checks 16         # Draft, open, CI
.venv\Scripts\python infra\nebius\forge_cloud.py status     # VM state; `spend` for the infra ledger
.venv\Scripts\python infra\nebius\forge_cloud.py start      # only when needed (cap-guarded, 6 h deadline)
.venv\Scripts\python infra\nebius\forge_dev.py exec --slot integ "wc -l experiments/forge_loop/memory_eval/results/runs.jsonl"
.venv\Scripts\python infra\nebius\forge_dev.py pull --slot integ experiments/forge_loop/memory_eval/results
.venv\Scripts\python infra\nebius\forge_dev.py pull --slot integ artifacts/forge/investigations
.venv\Scripts\python infra\nebius\forge_dev.py serve --slot integ --live   # live server (never set CF_MEMORY for the eval)
.venv\Scripts\python infra\nebius\forge_cloud.py stop       # ALWAYS stop via the API at the end of a block
```
Never run tests/builds/MuJoCo locally (no free RAM); use `forge_dev.py test py|fe|e2e --slot verify`.

## 10. Where state lives
`docs/PROJECT_STATE.md` (dated sections), `docs/memory/DECISIONS.md`, `docs/memory/INCIDENTS.md`, `docs/FORGE_LOOP.md`,
`docs/FORGE_LOOP_CONTRACTS.md`, this file, Basic Memory project `creature-forge` (text search "checkpoint").

## 11. Shutdown record
(appended at shutdown — see below)

### Interim (pushed 2026-10-15T19:03:26Z)
- Memory evaluation RUNNING on the VM: **4 of 12 pairs recorded** (~8 min per pair). The driver runs through the
  orchestrator's SSH session: if that session ended before completion, the pair in flight was interrupted. On resume:
  pull results first, then `python scripts/forge_memory_eval.py --resume` (records that pair as excluded; never reruns).
- VM RUNNING (deadline ~302 min left at this write);
  the orchestrator stops it through the API after the evaluation. If the session died first, the deadman powers the guest
  off at the deadline and the Windows watchdog stops it via the API when the PC is on — run `forge_cloud.py status` and
  `stop` on resume (INCIDENTS 2026-10-15: a powered-off guest may still show RUNNING).

### Shutdown record — 2026-10-15 19:07 UTC (owner disconnecting)
**Memory evaluation forge-memory-eval-v1: STOPPED at a clean pair boundary, 5 of 12 pairs complete.**
- Completed (both investigations `done`, results committed in `experiments/forge_loop/memory_eval/results/`): replicate 1 of
  `short-legs`, `long-legs`, `big-torso`, `small-feet`, `heavy-legs`. Raw `runs.jsonl` + 10 unedited records (`records/`,
  SHA-256 in `records/MANIFEST.json`).
- Remaining (7 pairs, NOT started): replicate 1 of `soft-motors`; replicate 2 of all six creatures.
- `mem-soft-motors-1` (`c-2fd9f160`) was created by the driver just before the stop and has **zero investigations**, so no
  investigation was interrupted and nothing is excluded. `--resume` (updated in this commit) creates a fresh creature for
  that pair; it excludes a pair only if its creature already has an investigation, and it never reruns a recorded pair.
- **No interim analysis was run** (the pre-declared test is defined on all 12 pairs; looking early would invite optional
  stopping). Run `--analyze` only after `--resume` has completed the remaining pairs.
- Code for the remaining pairs must stay the same as for the completed ones: **do not change** `creature_forge/` investigation,
  evidence, memory, probes, arena or verdict code before resuming (each record stores `code.commit`; compare it).
- Resume: start the VM → `forge_dev.py serve --slot integ --live` (never `CF_MEMORY`) →
  `forge_dev.py exec --slot integ --timeout 9000 "python scripts/forge_memory_eval.py --resume"` (or run it inside `tmux` on
  the VM so it does not depend on the local SSH session) → pull `runs.jsonl` and records → `--analyze` → write `REPORT.md`.
  A `forge_dev.py sync --slot integ` is now safe: `runs.jsonl` is committed, so the slot keeps it.
- Inference ledger at stop: **111 requests, $0.4764** of $15 (backup `artifacts/vm/ledger_backup/inference_ledger_20261015b.jsonl`).
- VM: stopped through the Nebius API right after this commit (see `forge_cloud.py status`; infra ledger `spend`).
- Nothing merged; repository private; PR #16 still Draft.

### Completion record — 2026-10-16 (memory evaluation finished)
- Resumed 2026-10-15 21:49 UTC in remote `tmux` session `memeval` on slot `integ` (synced to `6dc214f`, snapshot `6314247`;
  `creature_forge/`, protocol and bank identical to run 1's `50f24a7`), live server without `CF_MEMORY`. Ran the 7 remaining
  pairs; finished 22:29 UTC, driver exit 0. 12/12 pairs, 24/24 investigations `done`, 0 exclusions, no reruns.
- `runs.jsonl` append-only (first 5 lines byte-identical); 24 records archived with SHA-256 manifest; `--analyze` run ONCE
  after completion: memory 6/12 vs no memory 7/12, discordant 3 vs 4, p = 0.773 -> **no evidence of a benefit**; memory cited
  0/12 (delivered and citable; checked); twins 0/24 verified. `experiments/forge_loop/memory_eval/REPORT.md`.
- Inference ledger after the run: 140 requests, $0.5412 (backup `artifacts/vm/ledger_backup/inference_ledger_20261016.jsonl`).
- Do NOT repeat: the memory evaluation (any part), its analysis, or the delivery/citability audit.
- **Fresh-clone test PASSED (2026-10-15 22:40-22:47 UTC):** `git clone` of `feature/forge-loop` @ `ce48810` from GitHub ->
  new VM slot `fresh` (new venv, `pip install -e .[studio]`, `npm ci`) -> py 894 OK (1 skipped), vitest 137/137 + build,
  browser 237 checks PASS, smoke + demo-trial verification PASS; slot tree clean afterwards. Do not repeat unless code changes.
- Also done this block: `webgl-constants` confirmed MIT; capture plan and feedback docs rewritten (`4a43440`).
- VM STOPPED through the API after the test; infra $4.44 of $10.
- **Remaining D items:** scripted demo capture (owner records voice-over), publication audit owner decisions (history
  emails, Nebius §4.1.10(c)/§18.7, Super/Ultra licence texts), final secret scan on the final refs. PR #16 merge awaits the
  owner's explicit yes (merge commit, no squash).
