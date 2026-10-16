# Licence and dependency review (publication readiness)

Status: working review, not legal advice. Prepared 2026-10-15 on branch `feature/forge-loop` (working tree had uncommitted changes, see 4.6). The repository stays private. Nothing was built, tested, installed or fetched from the network for this review; licence statements come from `studio/package-lock.json`, from `node_modules/*/package.json` and `LICENSE` files already on disk, and from the repository's own notices. Anything not checked against one of those sources is marked **unverified**.

Files read: `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, `pyproject.toml`, `studio/package.json`, `studio/package-lock.json`, `docs/MODEL_AND_SERVICE_TERMS.md`, `docs/submission/*` (checklist, Devpost text and others by name), `README.md`, `experiments/forge_loop/model_config.json`, `.gitignore`, `.gitattributes`, `tests/test_license.py`, and the import statements of `creature_forge/*.py` and `creature_forge/studio/*.py`.

## 1. Direct dependencies

### 1a. Python (`pyproject.toml`)

| name | declared range | licence | in THIRD_PARTY_NOTICES.md | notes |
|---|---|---|---|---|
| mujoco | `==3.15.0` (runtime) | Apache-2.0 | yes (3.15.0) | physics engine; `NOTICE` names it |
| numpy | `>=2.4.6,<2.6` (runtime) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | yes (2.4.6) | licence string as in the notice |
| python-dotenv | `>=1.0` (runtime) | BSD-3-Clause | yes (1.2.4) | imported by `creature_forge/config.py` |
| fastapi | `>=0.110` (extra `studio`) | MIT | yes (0.143.0) | Studio backend |
| uvicorn | `>=0.29` (extra `studio`) | BSD-3-Clause | yes (0.54.0) | server; imported by `scripts/` |
| httpx | `>=0.27` (extra `studio`) | BSD-3-Clause | yes (0.28.1) | used by tests (`TestClient`) |
| setuptools | `>=77` (build-system) | not checked (unverified; build tool, not shipped) | no | build-time only; no lock file for it |

Direct import not declared in `pyproject.toml`: **pydantic** (`creature_forge/studio/app.py`, `creature_forge/studio/forge_api.py`). It arrives only through fastapi. It is in the notice as pydantic 2.14.1, MIT, so this is a declaration gap, not a licence gap. Note that `pydantic` is not listed in `THIRD_PARTY_NOTICES.md` as a *direct* dependency anywhere; it appears only in the runtime-closure table.

### 1b. npm (`studio/package.json`; licences from `studio/package-lock.json` `license` fields, cross-checked with `node_modules/*/package.json` where installed)

| name | declared range | locked version | licence | in THIRD_PARTY_NOTICES.md | notes |
|---|---|---|---|---|---|
| @fontsource-variable/bricolage-grotesque | `^5.3.0` (dependencies) | 5.3.0 | OFL-1.1 | **no** | font bundled into `studio/dist` by the build; see section 2 |
| @fontsource-variable/instrument-sans | `^5.3.0` (dependencies) | 5.3.0 | OFL-1.1 | **no** | same; see section 2 |
| @react-three/drei | `^10.7.9` | 10.7.9 | MIT | yes | |
| @react-three/fiber | `^9.8.1` | 9.8.1 | MIT | yes | |
| react | `^19.3.0` | 19.3.0 | MIT | yes | |
| react-dom | `^19.3.0` | 19.3.0 | MIT | yes | |
| three | `^0.186.1` | 0.186.1 | MIT | yes | the notice also lists three 0.170.0 (transitive) |
| zustand | `^5.0.15` | 5.0.15 | MIT | yes | the notice also lists zustand 4.5.7 (transitive) |
| @types/react | `^19.3.0` (dev) | 19.3.0 | MIT | yes | |
| @types/react-dom | `^19.3.0` (dev) | 19.3.0 | MIT | yes | |
| @types/three | `^0.186.0` (dev) | 0.186.0 | MIT | yes | |
| @vitejs/plugin-react | `^6.1.2` (dev) | 6.1.2 | MIT | yes | |
| playwright-core | `^1.49.1` (dev) | 1.49.1 | Apache-2.0 | yes | used by `studio/e2e` |
| typescript | `^7.0.2` (dev) | 7.0.2 | Apache-2.0 | yes | |
| vite | `^8.3.4` (dev) | 8.3.4 | MIT | yes | |
| vitest | `^5.0.4` (dev) | 5.0.4 | MIT | yes | |

Lock file: `lockfileVersion` 3, 152 package entries (68 non-dev, 84 dev). One entry has no `license` field in the lock: **webgl-constants 1.1.1** (a transitive dependency of drei/three tooling). The notice records it as MIT "per LICENSE file"; the installed `node_modules/webgl-constants/LICENSE` reads "MIT License, Copyright (c) 2019 Tim van Scherpenzeel". **Resolved 2026-10-15:** the copy installed on the VM by `npm ci` (registry tarball pinned by the lock's `integrity` hash, so byte-identical to what any fresh install receives) has the same MIT `LICENSE` file, and its `README.md` states "released under the MIT license"; only `package.json` lacks a `license` field. MIT is correct.

Every other lock entry's notice row matches the lock's name and version (checked by script against the notice table, 0 mismatches apart from the two fonts).

## 2. Gaps

### 2a. Notice gaps

1. **Two OFL-1.1 fonts are not in `THIRD_PARTY_NOTICES.md`.** `@fontsource-variable/bricolage-grotesque` 5.3.0 and `@fontsource-variable/instrument-sans` 5.3.0 are production dependencies, imported in `studio/src/main.tsx` (lines 4-5). They were added in commit `dd8d6ea` (2026-10-14 17:52), after the notice was last regenerated in `63ce1f3` (13:07). The notice is generated by `scripts/generate_third_party_notices.py` (not run here). Both packages' `LICENSE` files (read locally) carry "Copyright 2022 The Bricolage Grotesque Project Authors" and "Copyright 2022 The Instrument Sans Project Authors" with OFL text. The OFL conditions apply when the font files are redistributed (for example, inside a built `studio/dist`); the repository itself does not contain the font files (they are generated into `studio/node_modules`). Whether either font has a "Reserved Font Name" declared was **not verified**: the copyright lines I read do not show one.
2. **`pydantic` is used directly but not declared** (section 1a). Not a licence gap.
3. The notice's own test (`tests/test_license.py`) checks only that no row says UNKNOWN and that four named packages are present. It does not detect the fonts above, so the gap was not caught by CI.

### 2b. Python imports added since the notices were generated (Forge Loop)

The Forge Loop modules were read for third-party imports (`grep` over the import lines; not executed).

- `challenges.py`, `arena.py`, `baselines.py`: `numpy` (declared).
- `creature_walk.py`: `mujoco`, `numpy` (declared). `evidence.py`: `mujoco` (lazy import, declared).
- `forge_ai.py`, `inference_ledger.py`, `interventions.py`, `forge_pool.py`, `probes.py`, `verdict.py`, `investigation.py`, `creatures.py`, `jobs.py`: standard library only, plus intra-package imports. `nebius.py` (the HTTP client) imports standard library only; no `openai` or `requests` package.
- `studio/forge_api.py`: `fastapi`, `pydantic` (fastapi declared; pydantic not declared, see 1a).
- `inference_ledger.py` uses `msvcrt` / `fcntl` (standard library, platform-specific).

Result: **the Forge Loop added no third-party Python package that is missing from `pyproject.toml` or from the notice.** The only undeclared direct import is `pydantic`, which is already in the notice.

Other third-party imports seen outside the package (not in the Forge Loop): `dotenv` (`config.py`, declared), `fastapi` / `uvicorn` / `httpx` in tests and scripts (declared in the `studio` extra; the notice covers them). No `playwright` Python import was found; the browser checks use `playwright-core` from npm.

### 2c. Frontend build inputs

`studio/dist` exists on the local disk (git-ignored). It contains the bundled fonts. It is not tracked and is not part of the repository, so no font file is currently redistributed by git. It would be if a build were published (for example, to a hosting service or as a release asset). **Unverified:** whether `studio/dist` was ever published anywhere.

## 3. Model and service terms

### 3a. What `docs/MODEL_AND_SERVICE_TERMS.md` covers (reviewed 2026-10-14)

- Section 1 covers only **`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`**. It summarises the NVIDIA Nemotron Open Model License as read (hosted/API-only use is not addressed by the text it read; the appendix and other NVIDIA pages were not read). It states that no weights are distributed.
- Section 2 covers Nebius: §13 (third-party models are governed by their own terms), §4.1.9(b) rate limits, §4.1.10(a) consumer use, §4.1.10(c) "competitive analysis or benchmarking", §6.2 trial risk, §15.3 "as is", §18.7 publicity. The AUP, Service-Specific Terms and DPA were not read.
- Open items in section 4 of that doc: owner reading of the Nemotron appendix and the Nebius AUP and Service-Specific Terms; sponsor or organiser permission for public mention of Nebius; a written clarification (draft `docs/submission/NEBIUS_CLARIFICATION_REQUEST.md`, not sent as of 2026-10-14).

I did not re-read the external pages (no network use in this review).

### 3b. Models the Forge Loop now uses

| model | where | terms doc covers it? |
|---|---|---|
| `nvidia/nemotron-3-super-120b-a12b` | default in `experiments/forge_loop/model_config.json` (`"default"`); behind all scoreboard, memory-evaluation and dev live records (237 recorded calls) | **Yes (updated 2026-10-16):** `MODEL_AND_SERVICE_TERMS.md` section 1c. Licence per the official Hugging Face model card: NVIDIA Nemotron Open Model License (same as Nano) |
| `nvidia/Nemotron-3-Ultra-550b-a55b` | `"deep"` option in `model_config.json`; called only in `experiments/forge_loop/calibration/` (19 calls), not in the scoreboard or memory evaluation | **Yes:** section 1d. Licence per the official model card: OpenMDW-1.1 (a different licence; no section numbers; outputs unrestricted) |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | earlier demo and R3 tooling (41 recorded calls) | Yes (section 1) |
| `nvidia/Nemotron-3_5-Lightning` | calibration only (12 calls); not named in earlier versions of this review | **No.** Licence not reviewed (section 1e) |

**Flag (updated 2026-10-16):** the Super and Ultra model cards were read on 2026-10-16 (see `MODEL_AND_SERVICE_TERMS.md` 1c, 1d): Super is under the NVIDIA Nemotron Open Model License, Ultra under OpenMDW-1.1. The two licences differ, so public text must not say "all Nemotron models use the same licence". `THIRD_PARTY_NOTICES.md` (section "External services and models"), the README model table and `docs/submission/DEVPOST.md` were still **not updated** by this change (README and notices name only Nano; DEVPOST names Super without a licence). Verification limits: the licence pages were read through a summarising fetch, not as a PDF or raw text for the Nemotron licence; the OpenMDW text was likewise summarised; Lightning was not reviewed. Neither licence, as read, restricts publishing outputs or evaluation results, and neither is triggered by API-only use (no redistribution).

### 3c. OPEN QUESTION for the owner (not a conclusion)

The pre-registered Forge Loop scoreboard (`experiments/forge_loop/scoreboard/`, headline in `README.md`: AI arm 6/12 verified vs its matched-random twin 1/12) runs a Nebius-hosted Nemotron model and compares its proposals against matched random edits, and the README and `FORGE_LOOP.md` report the comparison publicly. Nebius §4.1.10(c), as summarised in the terms doc, excludes "competitive analysis or benchmarking" of the service.

Question for the owner: **does comparing a hosted model's proposals with random edits, published as a result, fall under §4.1.10(c)?** The comparison is between the model's outputs and a random baseline, not between Nebius and another provider, and the terms doc's own note says the timing figures make no provider comparison. This review does not decide the point. The owner should read the original §4.1.10(c) and, if unclear, include it in the clarification request.

## 4. Repository content risks before going public

### 4a. Committed raw model responses

- Tracked `.jsonl` files: 20 in total. Largest groups: `experiments/forge_loop/calibration/requests.jsonl` (390 KB) and `requests_v2.jsonl` (565 KB); `experiments/forge_loop/dev_live_records/i-*.json` (14 files, about 60-103 KB each); `experiments/forge_loop/scoreboard/results/records/i-*.json` (12 files, about 92-141 KB each) plus `runs.jsonl` and `summary.json`; `experiments/phase2a_r3/results/requests.jsonl`, `results_v2/demo_requests.jsonl` and `calibration.jsonl`.
- Each Forge Loop record includes the model's `reply` text, `model_calls` and the evidence sent to it (checked: field names in `i-f9873480e42a.json`).
- The terms doc records the reading that NVIDIA claims no ownership of outputs and that Nebius says customers own their inputs and outputs (Token Factory Quick Guide). On that reading, publishing outputs is not restricted by the text read. **Unverified** against the AUP, which was not read.
- Content: simulation evidence and creature parameters, no personal data found in these files (grep of section 4b). The prompts do not contain credentials (see section 4c).

### 4b. Personal data and local paths in tracked files (`git grep`, counts)

| pattern | result |
|---|---|
| `C:\Users` / `C:/Users` | 1 line in `docs/PROJECT_STATE.md` (line 14: `C:/Users/<user>/basic-memory/...`); 2 more lines in the same file use `C:\\Users\\<user>\\...` (lines 48, 50), which the fixed-string search did not match because of the doubled backslashes. **Fixed 2026-10-15** (paths scrubbed; 0 hits) |
| Windows username | `docs/PROJECT_STATE.md`: 3 lines (14, 48, 50). **Fixed 2026-10-15**; this table no longer quotes it |
| `@gmail` in tracked files | 0 |
| email-shaped strings in tracked files | 0 |
| `forge@` | 0 |
| `66.201.` | 0 |
| other public-looking IPv4 literals | none found (loopback and `0.0.0.0` excluded) |
| Linux VM paths | `experiments/phase2a_r1/logs/pip-freeze.txt:7`, `experiments/phase2a_r2/logs/pip-freeze.txt` (file path `/home/forge/repo.bundle`); `infra/nebius/cloud-init.yaml.tmpl:40` (`/home/forge`). Not personal, but machine-specific |
| owner name "Mahdi" | intentional in `NOTICE` (1) and in several docs (about 7 lines in total) |
| key-shaped strings | matches only for variable names (`NEBIUS_API_KEY=`, `api_key=`) in `creature_forge/investigation.py`, `tests/test_config.py`, `docs/submission/SETUP_AND_REPRODUCTION.md`, `docs/memory/DECISIONS.md` (the word "Bearer auth"). Values were not printed. The 10-14 scan (see `MODEL_AND_SERVICE_TERMS.md` section 3) found no real key bytes; **not re-run** here |

### 4c. Git history metadata (not in tracked files)

- `git log --all` shows **198 commit author/committer entries with `@gmail.com` addresses** (238 on 2026-10-15 as commits accumulate; same single address; 0 AI co-author trailers on any ref) and 66 with `@users.noreply.github.com`, plus 14 with `@github.com`. There are 2 distinct author/committer addresses in total (local parts not printed here). Making the repository public exposes these addresses in history. The checklist does not mention this. **Owner decision:** accept, or rewrite history (which the 10-14 notes say was already done once for co-author trailers; no further rewrite was requested).

### 4d. `.env` and ignored local state

- `.env` exists on disk (308 bytes), is **untracked** (`git ls-files` lists only `.env.example`) and is git-ignored (`.gitignore` line 2). Contents not read.
- Also present and ignored: `infra/nebius/state.json`, `infra/nebius/spend_ledger.jsonl`, `infra/nebius/watchdog.log`, `artifacts/`, `studio/dist/`, `.venv/`, `.claude/worktrees/`. Their contents were not reviewed; `state.json` is described in `.gitignore` as machine-specific.
- `.claude/settings.json` and two skills under `.claude/skills/` are **tracked**. Their content was not reviewed for personal paths.

### 4e. Working tree is not clean

`git status` at review time: `M creature_forge/investigation.py`, `M creature_forge/probes.py`, `?? tests/test_retune_probe.py`. The start-of-session snapshot was clean. Any public release should be cut from a committed, reviewed state.

## 5. Checklist

### 5a. Already in place (as read in this review)

- [x] `LICENSE` (Apache-2.0 full text), `NOTICE` (Copyright 2026 Mahdi Nasser), `THIRD_PARTY_NOTICES.md` present.
- [x] `pyproject.toml` declares `license = "Apache-2.0"` and `license-files`; `tests/test_license.py` checks these.
- [x] Notice rows match all npm lock entries (script check) except the two fonts (section 2a). Python rows were checked by reading the table against `pyproject.toml` closure names only, not against an install.
- [x] `.env` untracked and ignored; `.env.example` tracked.
- [x] Model weights are not in the repository (no tracked model binaries found by the section 4 checks; the 10-14 audit said the same for images, fonts and video).
- [x] Forge Loop added no new Python package (section 2b).

### 5b. Owner decisions or actions before publication

- [x] Add `@fontsource-variable/bricolage-grotesque` and `@fontsource-variable/instrument-sans` (OFL-1.1) to `THIRD_PARTY_NOTICES.md` (done 2026-10-15; both rows present). Still open: check the OFL Reserved Font Name clause; optionally extend `tests/test_license.py`.
- [x] `pydantic>=2` declared in the `studio` extra of `pyproject.toml` (2026-10-15).
- [x] Licence statement for `webgl-constants`: MIT, confirmed from the integrity-pinned registry tarball (section 1, 2026-10-15).
- [ ] Decide which Nemotron models to name publicly. Super is the Forge Loop default and the only model behind the published results; Ultra and Lightning appear only in calibration. Licences verified from the model cards 2026-10-16 (Super: NVIDIA Nemotron Open Model License; Ultra: OpenMDW-1.1; section 3b). Still to do: apply the wording changes to README, `THIRD_PARTY_NOTICES.md` and `DEVPOST.md`.
- [ ] Owner read of the original Nebius Services Agreement §4.1.10(c) against the scoreboard comparison (section 3c).
- [ ] Owner read of the full NVIDIA Nemotron Open Model License PDF and the OpenMDW-1.1 text (read only through summaries on 2026-10-16), and of the Nebius AUP and Service-Specific Terms (still open from `MODEL_AND_SERVICE_TERMS.md` section 4).
- [ ] Send the Nebius / organiser clarification on §18.7 public references, or accept the risk with the public text kept factual (no logos, no endorsement wording).
- [ ] Decide whether the 20 raw-record `.jsonl`/`.json` files stay public (recommended by the checklist as the evidence; the terms reading above does not restrict output publication, but the AUP is unread).
- [x] Redact `docs/PROJECT_STATE.md` lines 14, 48, 50 (Windows username and local paths): done 2026-10-15; `git grep` for the username returns 0 tracked hits.
- [ ] Decide on the commit author email addresses in history (section 4c).
- [ ] Commit or discard the three working-tree changes (section 4e) and re-run the secret scan and CI on the final committed refs.
- [ ] Confirm that `studio/dist` will not be published, or include the OFL notices with any published build.

### 5c. Not verified in this review

- Any statement about licence terms beyond the text already in the repository (no network, no external pages read).
- Licences of `setuptools` and of the Python packages' own transitive dependencies beyond the notice table.
- (Changed 2026-10-16) The Super and Ultra model cards were read and name different licences (see section 3b). Still unverified: the full verbatim licence texts, and the licence of `nvidia/Nemotron-3_5-Lightning` (calibration only).
- Whether any font has a Reserved Font Name.
- Contents of `.env`, `infra/nebius/state.json`, `infra/nebius/spend_ledger.jsonl`, `infra/nebius/watchdog.log`, `.claude/settings.json`, `.claude/skills/*`; contents of the `experiments/**` raw files beyond their field names and sizes.
- Whether the 10-14 secret scan still holds on the current refs (it was not re-run).
