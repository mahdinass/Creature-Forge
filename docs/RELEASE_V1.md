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

## 9. `v1.0.0-rc2` (proposed; branch `release/v1-rc2-prep`, through a PR into `release/v1`)

**What it adds.** One registered result, E-1, plus the operational fixes that made running it safe. The V1 demo, its
records and its claims are unchanged.

**Contents:**
- **Merge of `research/e1-engine-heldout` (`26626b6`):**
  - the E-1 protocol (registered at `494ed9b` before the sealed side was opened), results and correction note:
    `docs/E1_PROTOCOL.md`, `docs/E1_RESULTS.md`;
  - the evidence: `experiments/e1/` (gates, build, final archive sha256 `8ebaceb4…`, `RESERVE.md`);
  - the code: `creature_forge/hdb_testbench.py`, `scripts/e1_*.py`, `tests/test_e1.py`;
  - the Nebius operations fixes: auth-horizon guard, service-account stop path with STOPPED verification, VM-side API
    self-stop.
- **README and Devpost:** one E-1 paragraph each.
  - The primary result is inconclusive (56 vs 46, one-sided p = 0.061).
  - The diagnosis ablation is supportive but not study-wide significant (56 vs 42, p = 0.017; registered Holm(2)-adjusted
    0.034; Holm over all three tests 0.050).
  - The failure analysis is exploratory.
  - E-1 does not demonstrate learning from experience.
- **Optional narration line** for the owner's voice-over: `docs/submission/E1_NARRATION_OPTION.md`. The cut list is
  unchanged.

**Not changed:**
- the DO-1 and W2 records and replays;
- the Studio pages;
- the physics, verifier and optimiser code paths used by the demo;
- the `v1.0.0-rc1` tag.

## 10. Submission candidate (branch `release/v1-submission`, PR into `main`; 2026-10-27)

**Base and integration decision.** Built on `release/v1-rc2-prep` @ `60b6ac9`, so it contains V1 (PR #19) and rc2
(PR #20). PR #20 was reviewed and kept whole: its E-1 code is a separate module and scripts, the frozen manifest only gains
42 entries (0 removed or changed), and its infra changes harden the VM stop path. H1 (PR #22), H3 (PR #23), E-2R and the
other research branches are **not** included; their decisions are summarised in `docs/RESEARCH_STATUS.md`.

**What changed (documentation, assets and records only; no code path of the app changed):**
- judge-facing `README.md`; new `docs/ARCHITECTURE.md`, `docs/RESEARCH_STATUS.md`, `docs/README.md`, `docs/assets/`;
- `docs/submission/`: rewritten `DEVPOST.md` and `SUBMISSION_CHECKLIST.md` (compliance with the official rules),
  `FEEDBACK.md` summary, new `JUDGE_TESTING.md` and `VIDEO_HANDOFF.md`;
- byte-identical imports from `feature/demo-capture` @ `29e8e50`: `experiments/forge_loop/demo_capture/` and
  `studio/e2e/forge-demo-capture.mjs` (not run by CI);
- `.env.example` documents `CREATURE_FORGE_ENABLE_LIVE` (empty, off).

**Frozen-manifest status.** `tests/test_frozen_records.py` passes on this branch: rc2 already registered the 42 E-1
records. The "42 inherited E1 omissions" reported by later research branches (H1, H3) belong to those branches, which
fork from `research/e1-engine-heldout` before rc2's manifest commit; they are not a release defect, and nothing in the
manifest was edited here.

**Validation on Windows 11, Python 3.11.9, NumPy 2.4.6, MuJoCo 3.15.0, Node 24 (2026-10-27/28):**
| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | 1,643 tests, OK, 6 skipped, 1,846 s |
| `npm --prefix studio test` | 199 passed (14 files) |
| `npm --prefix studio run build` | built (chunk-size warning only) |
| `python scripts/smoke_test.py` | 6/6 PASS |
| Studio start (no key) | ready in about 15 s; `/`, `/api/do1/index`, `/api/nemotron/case`, `/api/forge/status` HTTP 200; `live_available: false` |
| `python scripts/lab_browser_check.py` (Edge) | 301 PASS, 2 FAIL. Both failures are waits for long MuJoCo jobs (`forge-flow` scripted investigation, 15 min; `forge-recovery-flow`, 10 min) while an unrelated process held about 10 CPU-hours and free RAM was about 1 GB. The demo-video flows (`do1-flow`, `nemotron-flow`) passed. No app code differs from rc2, whose CI run passed; CI on Ubuntu is the reference |
| Test fix | `tests/test_creature_gen.py::test_stilts_matches_record` had never run (its record was absent on every branch with the test). With the imported record it errored: the record stores leg geometry per leg. The test now checks both legs; values match exactly |
| Secret scan | the real key value and 6 credential patterns over every blob added since `60b6ac9` (31 blobs) and the commit messages: 0 hits |

**Nebius.** No paid service was used. Both VMs were STOPPED via the control plane at 2026-10-27 22:13 UTC.
