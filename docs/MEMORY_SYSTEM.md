# Creature Forge — persistent AI memory and context protocol

## The problem we are solving

Claude Code, Codex and ChatGPT have separate conversations, so they may forget previous environment setup, architecture decisions and solved problems. Example: a coding agent creates a new virtual environment when `.venv/` already exists. Avoiding that requires **checking the filesystem before acting**, not merely remembering a note.

## Architecture — five distinct layers

| Layer | What it stores | Authority |
|---|---|---|
| Git, filesystem, tests, real tools | Whether a venv exists; code behavior; deployment/config status | Highest for current facts |
| `AGENTS.md` and `CLAUDE.md` | Permanent agent operating rules and when to retrieve memory | Read on agent startup |
| `docs/PROJECT_STATE.md` + `docs/memory/` | Git-versioned project decisions, incidents, fixes and exact evidence | Shared fallback accessible to GitHub-reading agents |
| **Basic Memory** MCP (`creature-forge` project) | Semantic/graph retrieval across Claude Code, Codex and optionally ChatGPT | Supplemental, verify against repo |
| `docs/PROJECT_SPEC.md` | Full planned system vision and acceptance gates | Requirements, not current implementation |

**Design choice:** Start with Basic Memory, a structured Markdown knowledge store with linked notes and semantic search. Don't introduce a separate Graphiti/Neo4j service before a measured retrieval problem requires it. Graph storage alone does not force an agent to retrieve or verify state.

## Cloud / local choice

**Cloud:** Basic Memory Cloud (`https://cloud.basicmemory.com/mcp`) is the practical route to one knowledge base reachable by Claude Code, Codex and ChatGPT without leaving a local process running. This is a separately authenticated service and the cloud MCP endpoint requires a subscription/trial. Installation is a user action. **No cloud project, OAuth connection or synchronization is presumed in this repository.**

**Local:** Basic Memory local is free/open source and can serve Claude Code and local Codex via MCP, but does not automatically sync to ChatGPT. Git-tracked Markdown still provides cross-tool common ground through the GitHub connector.

### Connect Claude Code (Cloud)

1. Sign up for Basic Memory Cloud and create a project called `creature-forge`.
2. From the repository directory, run:
   ```sh
   claude mcp add -s user -t http basic-memory-cloud https://cloud.basicmemory.com/mcp
   ```
3. In Claude Code, run `/mcp` and authenticate the `basic-memory-cloud` server through OAuth.
4. Verify by asking Claude to list Basic Memory projects and search for a note in `creature-forge`.

### Connect Codex

**Codex app:** Settings → Connectors / Custom MCP → enter `https://cloud.basicmemory.com/mcp`, authorize and enable it. Exact UI labels vary.

**Codex CLI:** Basic Memory's current documentation suggests an API key from Basic Memory Cloud Settings → API Keys, then environment variable `BASIC_MEMORY_API_KEY` and the following **user-local** `~/.codex/config.toml` entry:

```toml
[mcp_servers.basic-memory]
url = "https://cloud.basicmemory.com/mcp"
bearer_token_env_var = "BASIC_MEMORY_API_KEY"
```

Don't commit actual keys or place them in `.env.example`. Confirm with `codex mcp list` and an actual note search.

### Connect ChatGPT

Find **Basic Memory Cloud** in ChatGPT's Plugins directory, connect with OAuth and enable it in the conversation. If absent in the directory/account, a supported custom MCP connection may be an alternative depending on account capabilities; don't claim integration exists until a real `list_memory_projects`/search succeeds.

**Important:** This ChatGPT session's GitHub connection already provides access to committed project context independently of Basic Memory, so work can start before cloud linking.

### Free local alternative

Install local Basic Memory using `uv tool install basic-memory` (Python 3.12+; `uv` required), then set up Claude Code and Codex with local Basic Memory MCP according to the official guides. Keep local notes in a designated project path and verify exactly what is indexed. The local edition is not the same thing as a shared remote cloud project.

Docs: https://docs.basicmemory.com/integrations/claude-code/ and https://docs.basicmemory.com/integrations/codex/ and https://docs.basicmemory.com/integrations/chatgpt/

## Mandatory retrieval protocol for agents

- **Session start:** inspect local environment and git status; read the compact state file. Then search memory for the current epic and recent relevant incidents.
- **Before destructive or expensive changes:** inspect actual files and prior decisions; if needed search memory by exact problem ("why did we switch model IDs?", "venv already configured?", "controller failure fixed?").
- **Before changing architecture:** search decisions and notes linked to the affected module, then inspect code/tests and write an ADR if changing assumptions.
- **On test failure:** search previous incidents by error signature; validate a proposed past fix against the current state.
- **At end of milestone:** update project state + decision/incident log and, **when connected**, write a concise Basic Memory note with links back to git commit or file and test output.
- **Compaction/session handoff:** provide a short summary of what's implemented, tested, blocked, next action and relevant references. Keep source-of-truth files updated before handoff.

Search just-in-time, not every fact on every tool invocation. An MCP connection **does not guarantee the model will call it**. Agent instructions, preflight hooks, tests and reviews reduce omissions; none can perfectly prevent them.

## Example memory note format

```md
# Physics environment bootstrap — 2026-10-14
Type: environment
Project: creature-forge
Status: confirmed | tentative | superseded
Last checked: 2026-10-14
Scope: local developer workstation only
Evidence: scripts/context_preflight.py output, commit <sha>
Observation: .venv/ exists, Python <actual version>, mujoco <actual version>
Decision: reuse .venv; do not create a second one
Exception: CI container may intentionally use its own isolated interpreter
Related: [[MuJoCo foundation]], [[Dependency setup]]
```

Every note distinguishes **observation**, **decision**, **scope**, **date**, **verification status**, **counterexamples**, and **evidence**. Do not enter unknown versions as facts. Mark stale notes `superseded` with a reference to the new decision. Never store secrets or medical/personal records in developer memory.

## Verification exercise (must pass before trusting setup)

1. Run `python scripts/context_preflight.py`; note whether it reports any existing venv and tooling.
2. Create a harmless `creature-forge` Basic Memory note about a *verified* setup fact through Claude Code.
3. Start a fresh Codex session; independently search for that same note, identify its evidence and verify it against the repo.
4. If connected, ask ChatGPT to retrieve that note. A successful GitHub-only lookup does **not** prove Basic Memory is connected.
5. Start a fresh Claude Code session and ask how to run the project. Confirm it checks the existing environment rather than making a new one.

If any cross-tool read fails, fix the MCP authentication, project routing or indexing; don't trust undocumented persistence.

## Known limitations

- GitHub commits and Basic Memory notes are **not automatically mirrored** by this setup. The agent protocol specifies dual-write when remote memory is available; this must be observed/tested.
- Notion may remain the human-readable planning space, but it is not authoritative runtime truth.
- The tool guards apply to Claude Code shell tools when project hooks are trusted/enabled; they do not automatically govern Codex shell execution.
- Cost, latency, context pollution and note staleness should be monitored before adding heavier graph machinery.
