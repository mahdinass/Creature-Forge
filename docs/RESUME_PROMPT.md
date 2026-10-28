# Resume prompt (copy into a fresh Claude Code session, Opus 5.5, high effort, started in the repository root)

> **SUPERSEDED (2026-10-18).** Historical checkpoint of the Forge Loop session (2026-10-15). For the current state read
> `docs/RESEARCH_HANDOFF_2026-10-18.md`.

```
Continue the Creature Forge project from its saved checkpoint. Do not start over.

1. Read docs/RESUME_CHECKPOINT.md completely (especially §8 "Do NOT repeat" and §11 "Shutdown record"), then AGENTS.md and
   CLAUDE.md. Treat Git, the VM and GitHub as the source of truth, not earlier conversation summaries.
2. Verify the actual state before acting: `git fetch; git status -sb; git log -5 --oneline`, `gh pr view 16 --json state,isDraft`,
   `gh pr checks 16`, `.venv\Scripts\python infra\nebius\forge_cloud.py status` and `spend`. Report any difference from the
   checkpoint.
3. Continue directly with the FIRST unfinished item of §7 "Next actions" (normally: finish or analyse the memory evaluation
   forge-memory-eval-v1 using --resume / --analyze exactly as described in §4; never rerun a recorded pair or edit a
   registered protocol or bank).
4. Rules: all tests/builds/MuJoCo/live calls run on the Nebius VM via infra/nebius/forge_dev.py; stop the VM through the API at
   the end of every work block; respect the budgets ($10 infra, $15 / 1,500 requests inference); no AI co-author trailers;
   do NOT merge PR #16 or change repository visibility without my explicit approval; keep R1/R2/R3 and all registered or
   archived records unchanged; report results honestly (null results included).
5. Use Sonnet/Haiku subagents only for independent implementation tasks with explicit file ownership; integrate and verify
   their work yourself.
```
