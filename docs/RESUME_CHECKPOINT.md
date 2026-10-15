# Resume checkpoint — 2026-10-15 (session paused by the owner)

Say **"continue"** and the orchestrator resumes from here. Everything below was verified at pause time.

## Ground truth at pause
- **Branch** `feature/forge-loop` @ `d60b155` (pushed; local tree clean). **Draft PR #16** → `main`, **NOT merged**.
- **CI on `d60b155`: green** (`test-context-guards`, `studio-frontend` incl. all browser flows).
- **VM `creature-forge-r1-cpu`: STOPPED** via the API (no processes left; no jobs queued/running at stop). Infra spend ledger:
  **$3.86 of $10** (conservative). Inference ledger (on the VM disk, `~/dev/ledger/inference_ledger.jsonl`; local backup
  `artifacts/vm/ledger_backup/inference_ledger_20261015.jsonl`, 142 lines): **86 requests, $0.42 of $15**.
- **Repository: PRIVATE.** No publication action taken.

## Owner decisions in force (2026-10-15)
1. PR #16 approved *in principle*; merge only after final CI green, a **real live end-to-end UI test** passes, and the
   critical security/integration checks are complete — and **ask the owner before merging** (latest instruction).
2. Keep the repo private until the publication audit and licensing/service-term review are complete; ask before any
   publication action.
3. Present the scoreboard (AI 6/12 vs matched twin 1/12, exact one-sided p = 0.03125) as encouraging evidence limited to the
   tested set; disclose small n, six starter families, push-dominated success, selection-budget asymmetry, untested walking.
4. Preserve all protocols, outcomes and historical evidence.
Priorities: A finish/merge (with approval) → B live walking → C engineering memory (evaluate vs no-memory before claiming)
→ D submission assets. Scope discipline: core + submission quality first.

## Done (committed, verified)
- Forge Loop end to end (challenges, creatures/jobs/API, AI investigator, probes incl. walk `retune_controller` probe,
  arena with twin validation, verdict_v1, bounded loop, accept/revert, Studio workspace). 840 Python tests OK on the VM at
  `5a8b9c2`+; frontend 137 vitest + build; 237 browser checks; CI green.
- Smoke scale for CI browser flows (`CF_INVESTIGATION_SCALE=smoke`, refused for live, recorded per record).
- `matched_random_v2` (twin never copies the AI edit; scoreboard v1 had 0 such cases).
- Pre-registered scoreboard v1: `experiments/forge_loop/scoreboard/REPORT.md`.
- **B (live walking) — done for now:** 7 live walk investigations on the tiny-feet creature archived in
  `experiments/forge_loop/dev_live_records/` (README "Walking"). Probes confirm feet; small consistent gains below the 0.5 m
  bar; nothing verified; the model never chose `retune_controller` co-design even after the adaptation probe was confirmed.
- Licence/dependency review: `docs/submission/LICENSE_REVIEW.md` (fonts missing from THIRD_PARTY_NOTICES; terms doc lacks
  Super/Ultra; benchmarking-clause question for the owner; emails in git history; local paths in docs/PROJECT_STATE.md).

## Unfinished work (preserved, NOT verified)
| work | where | state |
|---|---|---|
| **S9 security hardening** (M1 queue/creature/body limits, M2 ledger worst-case settle, M3 TrustedHost + Origin check, L1 no tracebacks to clients, L2 fullmatch ids, L3 idempotent accept, L4 replay quantise + semaphore, L5 reservation release, key redaction, no-redirect opener, https base URL, slot validation, safe tar extraction, nesting guard, `/api/version` without repo_root) | branch **`wip/s9-security-hardening-UNVERIFIED`** @ `20224db` (base `fb3cab5`); local worktree `.claude/worktrees/agent-abfb82fb32069e96b` | agent stopped mid-fix ("settle rows have no `kind`; use `.get`"). It also touched `tests/test_demo.py`, `tests/test_r3.py`, `tests/test_r3v2.py` — **review these carefully: frozen-research tests must not be weakened.** New: `creature_forge/studio/security.py`, `tests/test_security_review.py`. Full suites never ran green. |
| **S8 engineering memory** (`creature_forge/memory.py`, `scripts/forge_memory.py`, evidence/prompt hooks, API flag, UI block) | branch **`wip/s8-engineering-memory-UNVERIFIED`** @ `54aec28` (base `fb3cab5`); worktree `.claude/worktrees/agent-aaba8e5014f9b1404` | agent stopped mid-fix (a prompt string built in a heredoc got literal newlines instead of `\n\n`). Not tested. |
Other `.claude/worktrees/agent-*` directories are already-integrated agents (their content is in `feature/forge-loop`); they can be removed after resume.

## Next steps on "continue" (in order)
1. `python infra/nebius/forge_cloud.py start` (refuses beyond the $10 cap; sets a 6 h deadline). Stop through the API at the
   end of every work block (the deadman powers the guest off but may not stop billing — INCIDENTS 2026-10-15).
2. **S9:** check out `wip/s9-security-hardening-UNVERIFIED` into a worktree (or resume the agent there), finish the
   `.get("kind")` fix, review the three research-test edits (revert anything that weakens frozen checks), run
   `forge_dev.py test py|fe|e2e --tree <wt> --slot s9-sec`; integrate into `feature/forge-loop` only when green.
3. **Live end-to-end UI test** (owner merge condition): `forge_dev.py serve --slot integ --live`, then a real-browser flow
   that clicks "Investigate with AI" (LIVE) on a drawn creature, waits for the verdict, checks labels/twin/replay, and accepts
   only if verified. Record the run (investigation id, screenshots) in `experiments/forge_loop/dev_live_records/`.
4. Confirm CI green on the final head, then **ask the owner** before merging PR #16 (merge commit, no squash).
5. **C:** finish S8 from its WIP branch; build a memory bank from archived LIVE records (`scripts/forge_memory.py --build`);
   pre-register a paired memory vs no-memory evaluation on NEW creatures not in the bank (commit the protocol before any run);
   run; report honestly.
6. **D:** fix licence gaps (add OFL fonts to THIRD_PARTY_NOTICES, terms doc for Super/Ultra, declare pydantic), scrub local
   paths, secret scan of all refs, fresh-clone test on a clean VM slot, Devpost narrative + reproducibility guide, scripted
   demo capture (< 3 min). Disclose: scoreboard caps were enforced by the global ledger only (actual use 24 calls / $0.05).
   **No publication without the owner.**

## How to resume tooling
- Local: `C:\Users\mbnas\.vscode\Creature-Forge`, Python `.venv`, never run tests/builds locally (no free RAM).
- Remote: `infra/nebius/forge_dev.py sync|exec|test|serve|tunnel|pull` (slots in `~/dev/<slot>`; `sync` cleans untracked
  files in the slot — pull outputs first). Studio via `tunnel` at http://127.0.0.1:8765.
- State/decisions: `docs/PROJECT_STATE.md`, `docs/memory/DECISIONS.md`, `docs/memory/INCIDENTS.md`, `docs/FORGE_LOOP.md`,
  `docs/FORGE_LOOP_CONTRACTS.md`; Basic Memory project `creature-forge` (text search).
