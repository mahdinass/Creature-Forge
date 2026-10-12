# Free AI Memory Setup — Creature Forge (Windows)

**Cost: $0 for Basic Memory local.** No cloud account, subscription or paid memory API is required. This keeps memory on your own computer and lets Claude Code + Codex CLI access the same project. It does **not** automatically connect the web ChatGPT assistant.

Follow these steps on the Windows computer where you develop Creature Forge. Commands below are for PowerShell.

## 1. Requirements

Basic Memory requires **Python 3.12+** and can be installed through **uv**. Install uv from https://docs.astral.sh/uv/getting-started/installation/ if needed.

```powershell
python --version
uv --version
uv tool install basic-memory
basic-memory --version
```

If `python` is not on PATH, try `py -3 --version`. Follow the uv installer's PATH guidance, then restart the terminal before retrying.

**Note:** `uv tool install` installs an independent developer tool; it does **not** create another Creature Forge project's `.venv` directory. Do not create a project venv merely to install Basic Memory.

## 2. Create a local knowledge base for Creature Forge

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\basic-memory\creature-forge"
bm project add creature-forge "$HOME\basic-memory\creature-forge"
bm project default creature-forge
bm project list
```

This stores local memory notes outside the repository. We keep summary decisions, incident logs, verified project state and setup instructions in Git too, so GitHub-reading assistants can see them. Do not move the working memory folder into a temporary directory or commit its database/index.

## 3. Connect Claude Code

```powershell
claude mcp add -s user basic-memory basic-memory mcp
```

Restart Claude Code if needed. Within Claude Code, type `/mcp` and confirm `basic-memory` is connected. Ask: "List Basic Memory projects and show creature-forge."

## 4. Connect Codex CLI

```powershell
codex mcp add basic-memory -- basic-memory mcp
codex mcp list
```

In Codex, verify the server responds and finds the **same** `creature-forge` project.

Alternatively configure `~/.codex/config.toml` on your own workstation:

```toml
[mcp_servers.basic-memory]
command = "basic-memory"
args = ["mcp"]
```

Don't register both forms simultaneously. The Windows `basic-memory` executable must be on PATH for the agent process.

### Codex desktop app (rather than CLI)

Some app clients cannot spawn local command-based MCP servers. In that case:

```powershell
basic-memory mcp --transport streamable-http --port 8000
```

While that terminal remains running, connect the app to **http://localhost:8000/mcp** in its MCP settings, *if the app supports local HTTP MCP*. The app and CLI have different integration capabilities. Bind to localhost only; do not publicly expose your memory endpoint.

## 5. Verify that this actually solves the forgetfulness problem

- Run `python scripts/context_preflight.py` in the Creature Forge checkout. Observe an actual interpreter path and any existing venvs.
- Ask Claude to save a **verified** fact (e.g., the actual active interpreter path and command used), with scope/date/evidence, in Basic Memory project `creature-forge`.
- Start a **fresh Codex session**, retrieve the note, and ask Codex to check the actual interpreter/venv before proposing installation.
- Restart Claude Code, repeat the retrieval. Check that it reads the existing environment and doesn't create a duplicate.
- Test `python -m unittest discover -s tests -v` after cloning to validate the Git-tracked safeguards; local hook execution is not proven until run on your machine.

An MCP connection **cannot force perfect memory retrieval**. `AGENTS.md`, `CLAUDE.md`, session preflight and Git-tracked records are designed to reduce missed context.

## 6. ChatGPT without a cloud subscription

ChatGPT in the web app cannot directly spawn your private Windows MCP process. **No paid service is needed for the core Claude Code + Codex workflow.** For ChatGPT, use GitHub as the shared bridge: update `docs/PROJECT_STATE.md` and `docs/memory/`, commit/push, and ask ChatGPT to inspect those files via your connected GitHub. This is *Git-backed shared context*, not the same thing as native Basic Memory search.

Paid Basic Memory Cloud is **optional** if you later prefer seamless hosted remote MCP and access from multiple devices.

## 7. Official documentation

- Free local installation: https://docs.basicmemory.com/start-here/quickstart-local
- Claude Code local MCP: https://docs.basicmemory.com/integrations/claude-code/
- Codex local MCP: https://docs.basicmemory.com/integrations/codex/
- Local project commands: https://docs.basicmemory.com/local/cli-basics
- Project memory policy: [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md)
