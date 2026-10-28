# Architecture

This page describes the components that exist in the code and how they interact. Planned or proposed components are
not shown. File names are relative to the repository root.

## 1. System overview
```mermaid
flowchart TB
    subgraph Browser["Browser: Studio frontend (studio/, React + three.js)"]
        UI[Create / Simulate / Investigate pages]
        VIEW[3-D replay viewport, timeline, charts]
    end
    subgraph Server["Local server: FastAPI (creature_forge/studio/)"]
        API[app.py and routers:<br/>forge_api, do1_api, nemotron_api, causal_api]
        JOBS[Job queue and process pool<br/>jobs.py]
        STORE[(Creature store, investigation records,<br/>inference ledger)]
        PINS[(Recorded, hash-pinned records<br/>experiments/)]
    end
    subgraph Physics["Physics and judgement (deterministic)"]
        MJ[MuJoCo 3.15 rollouts<br/>simulate.py, walking.py, challenges.py]
        PROBES[Diagnostic probes<br/>probes.py]
        ARENA[Arena: AI, matched random,<br/>heuristic arms; arena.py]
        VERD[verdict_v1 / full_recovery_v1<br/>verdict.py, recovery.py]
    end
    subgraph AI["Model inference (only with a key and live mode)"]
        CLIENT[NebiusClient + caps<br/>nebius.py, inference_ledger.py]
        TF[[Nebius Token Factory<br/>NVIDIA Nemotron 3 Super]]
    end
    UI <--> API
    VIEW <--> API
    API --> JOBS --> MJ
    API --> PINS
    JOBS --> FAI[Forge Loop investigator<br/>forge_ai.py, interventions.py]
    FAI --> CLIENT --> TF
    FAI --> PROBES --> MJ
    FAI --> ARENA --> MJ
    ARENA --> VERD
    FAI --> STORE
    CLIENT --> STORE
```

Two kinds of page share this server:
- **Interactive pages** (Draw, Playground, Compare, My creature) run MuJoCo on the local machine through the job queue.
  Three interactive paths can call a language model, and only when `NEBIUS_API_KEY` and `CREATURE_FORGE_ENABLE_LIVE=1`
  are set: *My creature → Investigate with AI* (the Forge Loop investigation, the main one), *My creature → Recover
  walking* (AI director) and *AI investigation → Run live* (the original Nano path, `creature_forge/demo.py`). Without a
  key each runs a labelled SCRIPTED MOCK proposer.
- **Recorded pages** (Nemotron's experiment, Verified repair, AI scientist, Causal engineer, AI investigation, history)
  serve committed records. The Verified repair and Nemotron routers check SHA-256 sums before serving anything. No
  simulation or model call happens on these pages.

## 2. The Forge Loop investigation (live module)
```mermaid
sequenceDiagram
    participant U as User
    participant S as Studio API
    participant M as MuJoCo
    participant N as Nemotron 3 Super (Token Factory)
    participant V as Validator + verdict_v1
    U->>S: run challenge (stand / push / walk)
    S->>M: seeded rollouts (challenge seeds)
    M-->>S: per-seed outcomes, scores, telemetry
    U->>S: Investigate with AI
    S->>N: evidence pack + schema (request 1)
    N-->>S: hypotheses, probe requests with expectations
    S->>V: validate probe requests
    S->>M: run probes (probe seeds)
    M-->>S: measured probe results
    S->>N: evidence + probe results (request 2)
    N-->>S: up to 3 bounded edit proposals
    S->>V: schema, whitelist, bounds (reject, never clip)
    S->>M: screen AI arms, random twins, heuristic (screen seeds)
    S->>M: validate best AI arm and its matched twin (held-out seeds)
    M-->>V: paired scores
    V-->>S: VERIFIED_IMPROVEMENT / NOT_VERIFIED / INCONCLUSIVE / WORSE
    S-->>U: record with request ids, tokens, cost, verdicts, replays
    U->>S: accept (allowed only if VERIFIED)
```
- The diagram shows an investigation with probes on (two model requests). With probes off, one request returns the
  hypotheses and proposals directly.
- **Seeds** come from hashed blocks with disjoint roles (challenge, train, screen, validate, probe).
- **Matched random twin:** for the AI arm that is validated, a random edit of the same size on the same parameters is
  validated on the same seeds. A VERIFIED AI arm beside a VERIFIED twin is shown as such.
- **Caps:** at most 4 model calls and 80,000 tokens per investigation, plus global request and dollar caps. A call whose
  worst-case cost would exceed a cap is refused before it is sent.
- Contracts and thresholds: [`FORGE_LOOP.md`](FORGE_LOOP.md), [`FORGE_LOOP_CONTRACTS.md`](FORGE_LOOP_CONTRACTS.md).

## 3. The HaS scientist on the Hidden-Damage Bench (batch studies; recorded in the Studio)
```mermaid
flowchart LR
    PLANT[Hidden plant:<br/>robot with an unknown fault] -->|plant rollouts, charged| NB[Lab notebook:<br/>measurements, posterior,<br/>candidate experiments + EIG,<br/>engine recommendation]
    NB --> NEM{Nemotron 3 Super<br/>one tool call per turn}
    NEM -->|experiment / propose hypothesis| BE[Bayesian belief engine<br/>MuJoCo twin simulations]
    NEM -->|delegate| ENG[Deterministic engine A1c5]
    NEM -->|repair| CMA[CMA-ES repair<br/>twin or plant]
    BE --> NB
    ENG --> NB
    CMA --> NB
    NEM -->|submit| FR[full_recovery_v1 on validation<br/>and confirmation seeds the agent never saw]
```
- Code: `creature_forge/has_agent.py`, `belief_engine.py`, `hdb_bench.py`, `walk_opt.py`; runner
  `scripts/hdb_agent_run.py`, run on Nebius VMs. The Studio only plays back its records.
- An invalid model reply falls back to the engine's recommendation, and the fallback is recorded. An agent that always
  delegates reproduces the engine-only arm exactly, which is how Nemotron's own decisions are attributed.
- **`full_recovery_v1`** (`creature_forge/recovery.py`): the candidate must beat the original under `verdict_v1` on 24
  validation seeds, walk on at least 80 % of them, and then walk the full 20 s on at least 80 % of disjoint confirmation
  seeds. Errors are never counted as successes.

## 4. Verified repair (DO-1, NO_AI)
The *Verified repair* page compares two CMA-ES optimiser repairs of one robot on a slippery floor: the frozen objective
and the DO-1 objective (a deterministic change to what the optimiser rewards). Both are judged by `full_recovery_v1`. The
page plays back exports that were reproduced row by row from the experimental records on Linux before export
(`scripts/do1_demo_export.py`, `experiments/do1/demo/`). No language model is involved.

## 5. Inference safety and provenance
| Mechanism | Where |
|---|---|
| Request, token, per-investigation and dollar caps; no blind retries; key never logged or put in `repr` | `creature_forge/nebius.py` |
| Persistent inference ledger: request id, model, tokens, cost, purpose | `creature_forge/inference_ledger.py` |
| Strict JSON schema with enumerated hypothesis ids, editable parameters and citable evidence paths | `creature_forge/forge_ai.py` |
| Reject-never-clip edit validation | `creature_forge/interventions.py` |
| Every record carries the code commit and a dirty flag | investigation records |
| Frozen experiment records pinned by git blob id | `experiments/FROZEN_MANIFEST.json`, `tests/test_frozen_records.py` |
| Recorded demo files pinned by SHA-256 before serving | `creature_forge/studio/do1_api.py`, `nemotron_api.py` |

## 6. Where things run
| Work | Where |
|---|---|
| Studio, interactive MuJoCo, recorded pages | The user's machine (any OS) |
| Live model calls | Nebius Token Factory, called from the user's machine |
| Batch studies (scoreboard, HaS, DS-1, W3/W4, E-1, R0, H1, H3 and others) | Nebius AI Cloud Compute VMs (8 and 64 vCPU, Linux), controlled by `infra/nebius/forge_cloud.py` and `forge_dev.py` |
| Demo exports | Main Nebius VM, fail-closed against the recorded rows |

Nothing in the system trains or fine-tunes a model. "Memory" components in the research code (`has_memory.py`,
`repair_memory.py` on research branches) are deterministic retrieval or small statistical models, and none of them has
shown a benefit (see [`RESEARCH_STATUS.md`](RESEARCH_STATUS.md)).
