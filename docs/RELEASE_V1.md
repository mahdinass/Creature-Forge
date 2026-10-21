# Creature Forge V1: release candidate record

- **Release:** `v1.0.0-rc1`, an annotated tag on branch `release/v1` in the private repository. The exact commit:
  `git rev-parse v1.0.0-rc1^{commit}`. It is also recorded in the tag message, the integration PR and
  `docs/PROJECT_STATE.md` on later development branches.
- **Purpose:** the submission-ready deliverable for the Nebius × NVIDIA Global AI Hackathon 2026, Physical AI track. It
  contains no new physics experiments, no paid model calls and no new features.

## 1. Contents
| Deliverable | Where |
|---|---|
| Studio (FastAPI + React/three.js) | `creature_forge/studio/`, `studio/`; launch with `scripts/run_studio.py` (any OS) or `scripts/start_studio.ps1` (Windows) |
| Verified repair (DO-1, **NO_AI**) | `?tab=recovery`; replays in `experiments/do1/demo/` (SHA256SUMS pinned in `creature_forge/studio/do1_api.py`); `docs/DO1_DEMO.md` |
| Nemotron's experiment (recorded LIVE) | `?tab=nemotron`; `experiments/w2/` (pinned in `nemotron_api.py`); `docs/NEMOTRON_CONTRIBUTION.md` |
| W3/W4 replication (reviewed) | `docs/DO1_REPLICATION_PROTOCOL.md` (pre-registered at `3b8a8b1`), `docs/DO1_REPLICATION_REPORT.md`, raw evidence `experiments/do1/w3w4_2026-10-21/` |
| README, setup, licences | `README.md`, `docs/submission/SETUP_AND_REPRODUCTION.md`, `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, `docs/MODEL_AND_SERVICE_TERMS.md` |
| Devpost text | `docs/submission/DEVPOST.md` |
| Video assets | `docs/submission/STORYBOARD.md`, `video/cutlist.json`, `video/narration.srt`, `VIDEO_PRODUCTION.md`; rough cut v2 is git-ignored (hashes in `video/media_SHA256SUMS.txt`) |
| Submission actions | `docs/submission/SUBMISSION_CHECKLIST.md` |

## 2. Provenance (nothing rewritten)
- **The release line is linear up to the W2 checkpoint, then one merge:**
  - `main e58dbdf` ⊂ `ea9e729` ⊂ TA-1 `86d0a2b` ⊂ DO-1 harness **`e9d2379`** (tag `checkpoint/do1-l4-r0-harness-e9d2379`)
    ⊂ W2 checkpoint **`5e02df5`** (tag `checkpoint/w2-demo-2026-10-21`) ⊂ `feature/do1-demo` `28766c6`;
  - plus the merge of `experiment/do1-replication-w3w4` @ `920a7b0`, which contains the pre-registration `3b8a8b1` and
    the results `c0c8936`;
  - plus the V1 release commit.
- **`experiments/FROZEN_MANIFEST.json`:** 585 entries (git blob ids). They are the union of both lines, with no
  conflicting id, and each one equals the tree. `tests/test_frozen_records.py` enforces them.
- **Disclosure:** commits written with an AI coding assistant carry `Co-Authored-By` disclosures, which are kept.

## 3. Changes in the V1 release commit (no physics, verifier, optimizer or record change)
- **Studio:**
  - Home has a "Shown in the demo video" entry to both demo pages;
  - the Verified repair page cites the replication report. There are no new numbers on the page; every number is
    still derived from the records.
- **CI:** `scripts/lab_browser_check.py` now also runs `do1-flow.mjs` and `nemotron-flow.mjs`, so both demo pages are
  tested on a clean Ubuntu checkout.
- **Video:**
  - narration shot 2 cites the W3 replication; shot 9 says "Nemotron's one pre-registered win";
  - the captions are regenerated (rough cut v2, same picture, 173.5 s).
- **Docs:**
  - README, setup and reproduction, Devpost and the checklist are rewritten for V1;
  - `NEMOTRON_CONTRIBUTION.md` is updated with W3/W4 for accuracy;
  - this record and `PROJECT_STATE.md` are new.

## 4. Validation
The results are recorded in `docs/PROJECT_STATE.md` (V1 section) and in the readiness report:
- **Python:** `python -m unittest discover -s tests`.
- **Frontend:** `npm --prefix studio test` and `npm --prefix studio run build`.
- **Browser:** `python scripts/lab_browser_check.py`, 11 real-browser flows.
- **Clean clone:** a fresh clone from GitHub with a **fresh** virtual environment and `npm ci`, then the judge quick start
  and the evidence checks.
- **CI:** GitHub Actions on `release/v1` (Ubuntu, Python 3.12, Node 22, clean checkout, full history).

## 5. Dependencies
- **Python** (`pyproject.toml`): `mujoco==3.15.0`, `numpy>=2.4.6,<2.6`, `python-dotenv`; the `[studio]` extra adds `fastapi`, `uvicorn`,
  `httpx` and `pydantic`.
- **Frontend:** `studio/package-lock.json`, installed with `npm ci` (React, three.js, React Three Fiber, Vite, vitest,
  playwright-core).
- **Recorded experiment environment:** Linux, Python 3.12.3, numpy 2.5.4, MuJoCo 3.15.0.
- **Browser checks:** a system Chrome or Edge (`BROWSER_PATH` overrides).

## 6. Reproduction
See README *Quick start for judges* and `docs/submission/SETUP_AND_REPRODUCTION.md` §1–§6. The core commands:
```sh
pip install -e ".[studio]" && npm --prefix studio ci && npm --prefix studio run build && python scripts/run_studio.py
python scripts/do1_replication_analysis.py --w3 experiments/do1/w3w4_2026-10-21/do1_l4_rep.jsonl \
  --w4 experiments/do1/w3w4_2026-10-21/do1_x.jsonl
```

## 7. Known limitations
- **Scientific:**
  - DO-1 replication is on one robot, on studied validation seeds, with thin margins. W4 is two examples, one of which is
    not recovered.
  - The Nemotron case is a single instance chosen afterwards, and the broad comparison is parity (15 vs 14 of 36). See
    the README and the reports.
- **Pages and replays:**
  - The Verified repair page plays the exploratory r0 replicate; the replication is cited, not replayed.
  - Pages that simulate locally (Playground, Compare, My creature) run MuJoCo on the viewer's machine. Windows reproduces
    labels and verdicts but not every row bit-for-bit.
  - The demo pages are playback, so they are unaffected.
- **Tests and git-ignored data:** 24 DO-1 tests skip without the git-ignored DS-1 stored records (CI and clean clones).
  Large raw archives and all video files are outside Git (`docs/NONGIT_ASSETS_2026-10-21.md`).
- **CI on frozen refs:** CI fails on the frozen refs before the CI fixes (`e9d2379`, `86d0a2b`, both checkpoint tags). This
  is by design; frozen commits are not changed.

## 8. Freeze policy (how V1 stays unmodified)
- **Immutable references:** `v1.0.0-rc1` is an annotated tag. Never move or delete it. A fix becomes `v1.0.0-rc2` from
  `release/v1`.
- **`release/v1` changes only for a release blocker,** and only by a reviewed PR. New work goes on new branches; the next
  research is `feature/experience-learning`.
- **Remote and local guards:** GitHub rulesets and a local pre-push hook guard the branch and the tag. The status of each
  is recorded in `docs/PROJECT_STATE.md`.
- **Experiment preflights refuse modified code.** The experiment runners refuse to run when the protected paths
  (`creature_forge/`, `experiments/`) differ from their frozen implementation commits.
