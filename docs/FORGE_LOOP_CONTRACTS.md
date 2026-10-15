# Forge Loop — implementation contracts (v1, 2026-10-14)

Binding interface document for **Draw → Challenge → AI Redesign → Verify → Evolve**. Plan and rationale:
`docs/FORGE_LOOP.md` (summary) and the approved plan. Every module below has one owner; read this whole file before
writing code. If a contract is wrong or missing, stop and report it — do not invent a private variant.

## 0. Non-negotiable rules (all agents)

1. **Frozen work is read-only.** Never edit: anything under `experiments/` except `experiments/forge_loop/`; default
   values, criteria, prompts or protocol builders in `morphology.py`, `controller.py`, `simulate.py`, `failures.py`,
   `forensics.py`, `locomotion.py`, `phasegait*.py`, `optimize.py`, `evaluation.py`, `experiment.py`, `investigator.py`,
   `r1.py`, `r2.py`, `r3.py`, `r3v2.py`, `demo.py`, `phase2a.py`, `sandbox.py` (`BOUNDS`/MJCF are hash-pinned). New
   behaviour goes into **new modules**. Importing and calling these modules is fine.
2. MuJoCo decides. No code path may produce a verdict, metric or replay that was not computed by a rollout. Model
   output is untrusted input: parse, validate, reject with a reason, **never clip** an out-of-range value into range.
3. No model/network calls in tests (fake transports only). No Nebius lifecycle commands. No commits (the orchestrator
   commits). No AI co-author trailers anywhere.
4. Tests and heavy commands run **on the VM**, never locally:
   `python infra/nebius/forge_dev.py test py --tree <your worktree> --slot <your-slot>` (or `exec --heavy "<cmd>"`).
   A single test module: `exec --tree <wt> --slot <s> "python -m unittest tests.test_x -v"` (run `sync` first).
5. Python 3.11+ compatible, stdlib + numpy + mujoco + fastapi/pydantic only (already installed). Paths are always
   rooted in an injected directory (never CWD-relative). JSON written with `encoding="utf-8"`.
6. Write tests first (TDD), keep functions small, match the surrounding style (dataclasses, type hints, short docstrings).

## 1. Ownership

| Module | Owner | Purpose |
|---|---|---|
| `creature_forge/challenges.py` | S1 | stand / push / walk challenge specs, runners, scores, outcome classes |
| `creature_forge/creature_walk.py` | S1 | sandbox-aware walking rollout, body-scaled criteria, controller adaptation (1+8)-ES |
| `creature_forge/forge_pool.py` | S1 | process pool with per-job progress (`imap_unordered`), lazy creation, worker cap |
| `creature_forge/evidence.py` | S2 | compact evidence pack + citation resolution |
| `creature_forge/interventions.py` | S2 | parameter whitelist, edit validation, normalised edit space, body/controller application |
| `creature_forge/forge_ai.py` | S2 | prompt, reply schema, model call, parsing, repair policy |
| `creature_forge/inference_ledger.py` | S2 | persistent, file-locked inference ledger + caps |
| `creature_forge/baselines.py` | S3 | matched-random twins, heuristic proposal |
| `creature_forge/arena.py` | S3 | arms, seeds, screening, validation, records |
| `creature_forge/verdict.py` | S3 | deterministic verdict rule `verdict_v1`, paired statistics |
| `creature_forge/creatures.py` | S4 | creature/version store, lineage, accept/revert |
| `creature_forge/jobs.py` | S4 | background job manager, persisted events, cancel |
| `creature_forge/investigation.py` | S4 (M4) | orchestration of one investigation round and the bounded loop |
| `creature_forge/studio/forge_api.py` | S4 | `APIRouter` for `/api/forge/*` |
| `creature_forge/studio/app.py` | **Opus only** | mounts the router before the `/api/{rest:path}` catch-all |
| `studio/src/forge/*`, `studio/src/api.ts` additions, `studio/e2e/forge-flow.mjs` | S5 | workspace UI |
| `tests/test_frozen_records.py`, `experiments/FROZEN_MANIFEST.json` | H1 | frozen-record guard |
| `infra/**`, `docs/PROJECT_STATE.md`, `docs/memory/*` | Opus | infra, state, decisions |

Each owner writes `tests/test_<module>.py` for their modules.

## 2. Shared vocabulary

- **Body**: a `sandbox.SandboxBody`. Creatures always store per-leg fields explicitly (`*_r` never `None`).
  Legs: `left` = rear leg in the drawing frame, `right` = front leg (as `freehand.py` produces them). Edit targets use
  `both | rear | front`.
- **Mode**: `guided` (bounds = `morphology.BOUNDS`, legs must stay symmetric) or `experimental` (`sandbox.SANDBOX_BOUNDS`).
- **Controllers** of a version: `stand` = `controller.GaitParams` dict (default `GaitParams()`); `walk` =
  15-vector in `r3.PARAM_NAMES` order or `null` until adapted, plus provenance (§4.3).
- **Outcome class** per seed and aggregate: `FAIL` (fell / cannot do it) · `POOR` (did it with small margin or not
  genuinely) · `PASS`. A run that could not execute is `ERROR` (with message) — never folded into FAIL.
- **Score**: per-seed continuous capability score, higher is better (§3).

## 3. Challenges (S1) — `creature_forge/challenges.py`

```python
@dataclass(frozen=True)
class ChallengeSpec:
    kind: Literal["stand", "push", "walk"]
    seeds: tuple[int, ...]            # explicit; see §7 for namespaces
    duration: float                   # stand 8.0, push 5.0, walk 10.0 (defaults via default_spec(kind, seeds))
    perturb: float = 0.02             # initial perturbation std (stand/push); walk default locomotion.PERTURB (0.03)
    target_force: float = 10.0        # push: N that defines PASS; pilot: backward is the weak direction (default robot 10 N)
    push_time: float = 1.0            # push: nominal onset, jittered per seed by ±0.1 s (seeded)
    push_duration: float = 0.15
    max_force: float = 80.0           # push: search ceiling (score censored at max_force)
    start: Literal["drawn", "neutral"] = "drawn"   # walk default "neutral"
    settle_s: float = 0.3             # failure rules ignore t < settle_s (leaning drawings)
    def to_dict(self) -> dict: ...
    @staticmethod
    def from_dict(d: dict) -> "ChallengeSpec": ...   # validates ranges, raises ValueError with a reason

def default_spec(kind: str, seeds: Sequence[int]) -> ChallengeSpec: ...

@dataclass
class SeedResult:
    seed: int
    outcome: Literal["PASS", "POOR", "FAIL", "ERROR"]
    score: float                      # stand: survival time s; push: min(fwd, bwd) critical force N; walk: valid-gait distance m
    metrics: dict                     # JSON-safe; see below
    events: list[dict]                # FailureEvent dicts (time, kind, evidence)
    rollouts: int                     # physics episodes used for this seed
    error: str | None = None

@dataclass
class ChallengeResult:
    spec: dict; body: dict; controller: dict     # controller = provenance record (§4.3)
    per_seed: list[SeedResult]
    outcome: str                                  # aggregate: PASS if >= 80 % seeds PASS, FAIL if >= 50 % FAIL, else POOR (ERROR if any ERROR)
    summary: dict                                 # counts per outcome, score median/mean/min/max, Wilson CI of PASS rate
    forensics: dict                               # compact physics summary of the worst seed (§5 citations point here)
    rollouts: int; wall_s: float

def run_seed(body: SandboxBody, controllers: dict, spec: ChallengeSpec, seed: int) -> SeedResult   # pure, picklable args
def run_challenge(body, controllers, spec, pool=None, progress=None) -> ChallengeResult            # progress(done, total)
def replay_payload(body, controllers, spec, seed: int, *, force: float | None = None,
                   direction: int = +1, max_hz: int = 50) -> dict    # RunPayload for the viewer, decimated to <= 50 Hz
```

Physics rules:
- **Stand/push controller** = `GaitParams(**controllers["stand"])` (default `GaitParams()`). The drawn pose is only the
  starting configuration (`simulate.run_rollout` already applies `body.pose`). Never target the drawn pose.
- **Settle window**: failure detection for stand/push ignores `t < settle_s`; disclose in `metrics["settle_s"]`.
  Report `metrics["z_ref"]` (start torso height) because crouched starts make the height rule more lenient.
- **Stand** metrics: `survival_s`, `fell`, `fall_time`, `max_abs_pitch_after_settle`, `min_height_ratio`,
  `saturation_frac`, `slip_frac`. POOR if survived but `max_abs_pitch_after_settle > 0.5` or `min_height_ratio < 0.7`.
- **Push**: per seed, for each direction (+1 forward, −1 backward): rollout at 0 N (if it falls → score 0,
  "falls without a push"), at `max_force` (survives → score = max_force, censored), else bisection (5 steps) between
  last-survived and first-fallen force; critical force = last survived. Seed RNG also jitters push onset.
  `score = min(fwd, bwd)`. Metrics: `critical_force_fwd`, `critical_force_bwd`, `weak_direction`, `censored`,
  `bisection_trace` (list of (force, survived)). Forensics: `forensics.build_forensics` at the first failing force of the
  weak direction (mirror sign conventions for backward pushes: forensics' "+x = push direction"; set `mirrored: true`).
  Outcome: PASS if score ≥ target_force, POOR if ≥ 0.6·target, else FAIL. Default target 10 N (zoo pilot).
- **Walk**: `creature_walk.rollout(...)` + `locomotion.compute_metrics(tr, crit=creature_criteria(body))` +
  `locomotion.classify`. Score = forward displacement while upright and gait-valid (0 if fallen before 1 s). PASS if
  label `walking`; POOR if upright at the end but not walking; FAIL if fell.
- Each `run_seed` must be deterministic for (body, controllers, spec, seed) on one platform.

### creature_walk.py (S1)

```python
def creature_criteria(body: SandboxBody) -> locomotion.WalkingCriteria
    # step/advance gates scaled by mean leg length / 0.60 m; returns exactly DEFAULT_CRITERIA for the default body
def rollout(controller, body: SandboxBody, seed: int, duration: float, *, start="neutral", perturb=locomotion.PERTURB,
            record_poses=False) -> dict      # same trace format as locomotion.rollout; applies pose when start=="drawn"
def adapt_controller(body, init_vector, *, budget: int, train_seeds: Sequence[int], noise_seed: int,
                     pool=None, progress=None) -> dict
    # (1+8)-ES in r2's normalised space (reuse r2.to_u/from_u/reflect); score tuple like r2.score_of
    # returns {"vector", "init_vector", "budget", "rollouts_used", "train_seeds", "noise_seed", "history": [...], "best_score"}
R2_WINNER: tuple[float, ...]   # loaded from experiments/phase2a_r2/results/selection.json (read-only)
```

### forge_pool.py (S1)

```python
class ForgePool:  # lazy: no processes until first map; spawn context; max_workers from env CF_WORKERS (default 6, clamp 1..7)
    def imap(self, fn, jobs: list) -> Iterator[tuple[int, Any]]   # yields (index, result) as completed; exceptions -> ("error", msg)
    def close(self) -> None
def get_pool() -> ForgePool   # process-wide singleton; never created at import time
```
Job functions must be module-level and take one picklable dict.

## 4. Creatures (S4) — `creature_forge/creatures.py`

### 4.1 Storage
Root `<data_root>/creatures/<cid>.json` (one file per creature, atomic write via temp + `os.replace`).
`data_root` defaults to `<repo>/artifacts/forge` and is injected via `create_app(forge_dir=...)`.

### 4.2 Records
```jsonc
// Creature
{"id": "c-1a2b3c4d", "name": "Stubby", "created": "2026-10-15T10:00:00Z", "current": 2,
 "versions": [ /* CreatureVersion, n = 1.. */ ]}
// CreatureVersion
{"n": 2, "parent": 1, "created": "...", "content_hash": "sha256 of canonical {body, controllers}",
 "mode": "experimental", "body": { /* SandboxBody fields, *_r explicit, pose list of 7 */ },
 "controllers": {"stand": {/* GaitParams */}, "walk": null | {"vector": [15], "provenance": {...}}},
 "origin": "user" | "ai_accepted",
 "drawing": {"strokes": [...], "interpretation": {...}, "approximation": null | {"changes": [...], "consented": true}},  // n=1 only; children reference parent
 "change": null | {"edits": [...], "category": "morphology|control|combined", "rationale": "model hypothesis text",
                   "source": "nemotron" | "random_baseline" | "heuristic", "model": "nvidia/...",
                   "investigation_id": "i-...", "arm_id": "...", "verdict": {...}}}
```
### 4.3 Controller provenance (also embedded in every challenge/arena result)
`{"stand": {"kind": "stand-pd", "params": {...}, "edited": bool}, "walk": {"kind": "r2-transfer" | "adapted" | "none",
"vector": [...] | null, "adaptation": null | {budget, rollouts_used, train_seeds, noise_seed, parent_vector}}}`

### 4.4 API (Python)
```python
class CreatureStore:
    def __init__(self, root: Path)
    def create(self, *, name, body: dict, mode, drawing: dict) -> dict          # validates body against mode; n=1, origin user
    def list(self) -> list[dict]        # summaries: id, name, current, n_versions, created
    def get(self, cid) -> dict          # KeyError if missing
    def version(self, cid, n) -> dict
    def accept(self, cid, *, parent_n, body, controllers, change: dict) -> dict   # new version n = max+1, current = n
    def set_current(self, cid, n) -> dict                                          # revert/forward; never deletes
```
`accept` must refuse (ValueError) unless `change["verdict"]["status"] == "VERIFIED_IMPROVEMENT"`.

## 5. AI investigator (S2)

### 5.1 Evidence pack — `evidence.py`
`build_evidence(version: dict, challenge_result: dict, history: list[dict] | None) -> dict` returns a JSON object of
≤ ~6 KB (≈ 2.5k tokens) with stable keys, e.g.:
```
creature.{mode, body.{...}, derived.{leg_length_rear, leg_length_front, foot_to_leg, mass_total, weight_n, torque_to_weight}}
challenge.{kind, target_force?, seeds_n, duration}
controller.{stand.{...}, walk.{kind, ...}}
outcome.{aggregate, counts, score.{median, min, max}}
seeds[i].{seed, outcome, score, key metrics}            (≤ 6 seeds: worst, median, best)
forensics.{...}                                         (compact; from ChallengeResult.forensics)
history[k].{round, proposal summary, verdict, effect}   (prior rounds/versions, ≤ 5 entries)
bounds.{param: [lo, hi], current}                       (editable params only)
```
`resolve(evidence, path) -> scalar` — dotted/indexed path (`seeds[0].score`); citations must resolve to a
**scalar** (not list/dict), else the citation is invalid.

### 5.2 Edits — `interventions.py`
Whitelist (param id → kind):
- morphology: `torso_mass`, `thigh_length`, `shank_length`, `foot_length` (+ `target`), `leg_density`, `foot_friction`
- actuation: `torque_limit`
- control (stand/push challenges): `stand.kp`, `stand.kd`, `stand.balance_gain`, `stand.stand_hip`, `stand.stand_knee`
- control (walk): `walk.<name>` for each name in `r3.PARAM_NAMES`
```python
@dataclass(frozen=True)
class Edit: param: str; op: Literal["scale", "set"]; value: float; target: Literal["both", "rear", "front"] = "both"
def validate_edits(version: dict, challenge_kind: str, edits: list[dict]) -> tuple[list[Edit], list[str]]   # (ok, reasons)
def apply_edits(version: dict, edits: list[Edit]) -> tuple[dict, dict]   # (body, controllers) new dicts; does not mutate
def magnitude(version, edit) -> float      # morph/actuation: |ln(new/old)|; control: |Δu| (linear over its bounds)
def category(edits) -> str                 # morphology | control | combined (actuation counts as morphology)
```
Rules: ≤ 4 edits; no duplicate (param, target); morphology/actuation new/old ratio ∈ [0.5, 1.5]; control |Δu| ≤ 0.25;
result within the mode's bounds; guided mode forbids `rear`/`front` targets; no-op edits rejected; walk edits only for
walk challenges, stand edits only for stand/push. Every rejection reason names the param and the violated rule.

### 5.3 Model reply schema — `forge_ai.py`
```jsonc
{"diagnosis": {"summary": "string <= 400 chars",
   "hypotheses": [{"id": "H1", "mechanism": "string", "evidence": ["seeds[0].metrics.critical_force_bwd", ...],
                   "competing": ["string"]}]},                       // 1..3 hypotheses, 1..6 citations each
 "proposals": [{"id": "P1", "hypothesis": "H1", "category": "morphology|control|combined",
   "edits": [{"param": "foot_length", "op": "scale", "value": 1.3, "target": "both"}],
   "retune_controller": false,                                       // walk only; triggers equal retune for all arms
   "prediction": {"metric": "score", "direction": "increase", "expected_change": "string"},
   "tradeoffs": "string", "confidence": 0.0-1.0, "verification": "string"}]}   // 1..3 proposals
```
Validation outcome per proposal: `accepted` | `rejected` + reasons (schema, unknown hypothesis id, unresolved citation,
edit rule, category mismatch). The model's `category` must equal `category(edits)` or the proposal is rejected.
```python
@dataclass
class ModelConfig: model: str; max_tokens: int = 16000; temperature: float = 0.6; reasoning_effort: str | None = "low"
                   extra_body: dict | None = None; json_schema: bool = True; timeout_s: float = 180.0
def build_messages(evidence: dict, *, allowed: dict, max_proposals: int = 3) -> list[dict]
def call_model(client, cfg: ModelConfig, messages, ledger) -> ModelCall        # one request; records everything
def parse_reply(text: str) -> dict                                               # tolerant of <think> prefix, rejects lists
def validate_reply(reply: dict, evidence: dict, version: dict, kind: str) -> dict  # {"proposals": [{id, status, reasons, edits}], "hypotheses": [...]}
def investigate_once(client, cfg, version, challenge_result, history, ledger) -> dict   # ≤ 2 calls (1 + 1 repair if schema-invalid)
```
`ModelCall` record: `model, settings, prompt_sha256, messages, raw_response (full JSON), content, reasoning_present,
request_id, latency_s, usage, cost_usd, finish_reason, http_status, error`. Never contains the API key.
Repair call: only when the first reply is unparseable/schema-invalid; one attempt; the repair prompt contains the
validator's error list; counted in budgets.

### 5.4 Ledger — `inference_ledger.py`
Path from env `CF_INFERENCE_LEDGER` (VM: `~/dev/ledger/inference_ledger.jsonl`), else `<data_root>/inference_ledger.jsonl`.
Append-only JSON lines `{ts, request_id, model, prompt_tokens, completion_tokens, cost_usd, purpose, investigation_id}`;
file lock around read-check-append. Caps: **1,500 requests, $15.00** total; per investigation 4 requests / 80k tokens.
`reserve(est_prompt_tokens, max_tokens, model)` raises `BudgetExceeded` before any network call if the worst-case cost
would exceed a cap. Prices from `GET /v1/models` (per-token strings) cached in the ledger dir; unknown price → refuse.

## 6. Arena and verdict (S3)

### 6.1 Arms
`arm_id` strings: `original`, `ai:P1`, `random:P1` (twin of P1), `heuristic`. Every arm record:
`{arm_id, source: original|nemotron|random_baseline|heuristic, proposal_id?, edits, category, body, controllers,
controller_provenance, retune: null|{budget, noise_seed, rollouts_used}}`.
- **Matched-random twin** (`baselines.matched_random(version, kind, ai_edits, rng)`): same number of edits; for each AI
  edit draw a random whitelisted param of the same kind (morphology/actuation/control) with target `both`, the same
  `magnitude` and a random sign, op `scale` (morph) / `set` (control); if the result leaves bounds, flip the sign; if
  still invalid, redraw (max 20), else record `unavailable`. RNG seeded from `(investigation_id, proposal_id)`.
- **Heuristic** (`baselines.heuristic(version, kind, challenge_result)`): deterministic, documented rule table
  (e.g. push/stand falls → `foot_length ×1.3 both`; torque saturation → `torque_limit ×1.3`; slip → `foot_friction ×1.3`;
  walk falls → `walk.balance_gain`/`walk.pitch_kp` +0.1 u). Labelled non-AI everywhere.
- **Retune fairness**: if any AI walk proposal sets `retune_controller`, every arm (incl. original) gets the same
  `adapt_controller` budget and `noise_seed`.

### 6.2 Protocol
```python
@dataclass(frozen=True)
class ArenaConfig: screen_seeds: tuple; validate_seeds: tuple; train_seeds: tuple; retune_budget: int = 0
                   n_validate_arms: int = 2     # best AI arm + best baseline arm (plus original always)
def run_arena(version, spec_kind, arms: list[dict], cfg: ArenaConfig, pool, progress) -> dict
```
Screening: all arms × `screen_seeds` (`challenges.run_seed`). Selection rule (recorded): best AI arm = highest median
screening score among AI arms (ties: mean, then arm order); best baseline likewise among random+heuristic.
Validation: original + selected arms × `validate_seeds`. Results stored per arm per seed (score, outcome, metrics).

### 6.3 Verdict — `verdict.py` (`verdict_v1`, thresholds frozen after the M3 pilot)
```python
MIN_EFFECT = {"push": {"abs": 3.0, "rel": 0.10}, "stand": {"abs": 1.0}, "walk": {"abs": 0.5}}   # draft
def paired_sign_test(diffs) -> float                       # one-sided exact binomial on non-zero diffs
def verdict(kind, original_scores, candidate_scores, guard: dict | None) -> dict
# -> {"status": VERIFIED_IMPROVEMENT|NOT_VERIFIED|WORSE|INCONCLUSIVE, "rule": "verdict_v1", "n": .., "wins": .., "losses": ..,
#     "ties": .., "median_diff": .., "p_one_sided": .., "min_effect": .., "pass_rate": {orig, cand, wilson CIs}, "reasons": [..]}
```
VERIFIED_IMPROVEMENT iff p < 0.05 and median paired diff ≥ min effect (push: both abs and rel) and guard passes.
WORSE iff the mirrored test is significant in the other direction. INCONCLUSIVE iff fewer than 6 non-tied pairs.
Otherwise NOT_VERIFIED. The same function judges baseline arms. Model confidence is never an input.

## 7. Seeds
`seed_block(creature_id, n, round, role, k) -> tuple[int, ...]`: `base = 100_000 + int(sha256(f"{cid}:{n}:{round}:{role}")[:8], 16) % 800_000`,
seeds `base .. base+k-1`. Roles: `challenge` (user runs + evidence), `train`, `screen`, `validate`, `probe`.
Within an investigation all role blocks must be pairwise disjoint and disjoint from `r2.consumed_seed_sets()`,
`r3` and demo seed sets (< 100 000 by construction) — assert, and bump `round` salt on collision.
Default sizes (pilot may change): challenge 8, train 3, screen 12, validate 24.

## 8. Jobs and investigations (S4)

`jobs.py`: `JobManager(root, pool_factory)`; one orchestration worker thread (jobs run one at a time, FIFO);
`submit(kind, fn, **kw) -> job_id`; job file `<data_root>/jobs/<job_id>.json` + `<job_id>.events.jsonl`.
Job: `{id, kind: challenge|investigation|loop, status: queued|running|done|failed|cancelled, created, started, finished,
progress: {phase, done, total}, result_ref, error}`. Event: `{i, t, type, data}` with types
`phase | progress | model_request | model_response | validation | arm_result | verdict | error | note`.
Cancel sets a flag checked between rollouts batches. On server restart, `running` jobs are marked `failed`
("server restarted") — never silently resumed or faked.

`investigation.py` (M2–M4): `run_investigation(store, version_ref, challenge_run, cfg, client, ledger, pool, emit)`:
evidence → model (`investigate_once`) → validation → arms (AI accepted + twins + heuristic + original) → arena →
verdicts → record `<data_root>/investigations/<inv_id>.json`. If the model is unavailable or fails, the record is
saved with `status: model_failed` and the error, and **no AI arm exists** (baselines may still be shown, labelled).
Bounded loop (M4): `max_rounds 3, max_proposals 9, max_rollouts 3000, max_calls 4, wall 600 s, stop on no improvement`.
Investigation record keys: `id, created, mode (live|scripted), provenance (LIVE|SCRIPTED_MOCK), creature {cid, n,
content_hash}, challenge_run_id, spec, evidence, model_calls [ModelCall], reply, validation, arms, seeds {train, screen,
validate}, screening, selection, validation_results, verdicts {arm_id: verdict}, budget {rollouts, wall_s, calls,
tokens, usd}, code {commit, dirty}, status, error`.
**SCRIPTED_MOCK** replies come only from an explicit fixture transport, are labelled in the record and UI, and can
never be promoted to LIVE or counted in scoreboards.

## 9. HTTP API (S4) — prefix `/api/forge`

| Method | Path | Body → Response |
|---|---|---|
| GET | `/status` | → `{live_available, model, ledger: {requests, usd, caps}, workers, version}` |
| GET | `/creatures` | → `[summary]` (`200 []` when empty) |
| POST | `/creatures` | `{name, body, mode, drawing}` → creature |
| GET | `/creatures/{cid}` | → creature (404 JSON if missing) |
| POST | `/creatures/{cid}/current` | `{n}` → creature |
| POST | `/creatures/{cid}/versions/{n}/challenges` | `{kind, seeds?: int count, overrides?: {...}}` → `{job_id, run_id}` |
| GET | `/runs/{run_id}` | → ChallengeResult JSON |
| POST | `/creatures/{cid}/versions/{n}/investigations` | `{run_id, mode: "live"|"scripted"}` → `{job_id, investigation_id}` |
| GET | `/investigations/{iid}` | → investigation record |
| GET | `/investigations?cid=` | → `[summary]` |
| GET | `/jobs/{job_id}?since=i` | → `{job, events: [...]}` |
| POST | `/jobs/{job_id}/cancel` | → job |
| GET | `/replay?run_id=|investigation_id=&arm=&seed=&direction=&force=` | → RunPayload (≤ 50 Hz) |
| POST | `/creatures/{cid}/accept` | `{investigation_id, arm_id}` → new version (409 + reason unless VERIFIED) |

Errors: `{"detail": "human-readable reason"}` with 400/404/409/422/503. `live` mode requires
`CREATURE_FORGE_ENABLE_LIVE=1`, an API key and ledger headroom, else 503 with the reason.

## 10. Frontend (S5)
Tab `forge` (journey stage Investigate/Create bridge) with deep link `?tab=forge&creature=<cid>&v=<n>`. Components in
`studio/src/forge/`: `ForgePage` (shell), `CreatureBar` (name, version chip, lineage, revert), `ChallengePicker`,
`RunView` (outcome badge FAIL/POOR/PASS/ERROR, per-seed strip, replay via existing `Viewport`/`Transport`),
`InvestigationView` (live event timeline: evidence sent → model call (model, request id, tokens, latency) →
hypotheses → proposals with accepted/rejected reasons → arena progress → verdicts), `ArenaCompare` (synchronized
original vs selected arm via shared `usePlayback`; provenance chips ORIGINAL / NEMOTRON / RANDOM BASELINE / HEURISTIC /
SCRIPTED MOCK), `AcceptPanel` (param diff via `ParamTrack`, silhouettes via `MiniCompare`; accept enabled only for
VERIFIED arms). Draw page gains "Use this creature" → `POST /api/forge/creatures` → navigate to forge tab.
Polling `GET /jobs/{id}?since=` every 1 s while running. Pure logic in `forgeLogic.ts` with vitest tests.
Never render a verdict, number or replay that did not come from the API.
