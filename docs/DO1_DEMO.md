# Verified repair page (DO-1 L4 recovery), Studio tab `?tab=recovery`

The page puts three designs side by side on the same robot (L4, `hdb-v1-gen-0137:low_ground_friction:0`), the same
hidden plant and the same validation seed. All three are driven by one shared playback clock.

| Design | Validation walking | Status | 20 s confirmation |
|---|---|---|---|
| Faulty robot | 5/24 | — | — |
| Frozen optimizer repair | 19/24 | PARTIAL_IMPROVEMENT | not run |
| DO-1 optimizer repair | 21/24 | FULL_RECOVERY | 22/24 walking |

DO-1 is a deterministic change to the plant optimizer's objective. Both arms are A1e6 with recorded provenance NO_AI, so
**no Nemotron call** was made in either. The result is **one exploratory technical replicate on one robot, not a
recovery rate**. The page states both.

## Data path (no simulation anywhere)
1. **The export.** `scripts/do1_demo_export.py` ran on the main VM, the recorded Linux environment, at commit `2d2fbfb`.
   All 96 rows reproduced exactly on the verifier's own path and on the frame path; the max FK error was 0.0 m. The
   output is `experiments/do1/demo/`: `index.json`, 96 viewer payloads with pre-step frames, and `SHA256SUMS`. It is
   frozen in `experiments/FROZEN_MANIFEST.json`.
2. **The API.** `creature_forge/studio/do1_api.py` (`/api/do1/index`, `/api/do1/payload/{design}/{10|20}/{seed}`):
   - It refuses to serve unless the export's `SHA256SUMS` equals the pinned hash (`73078ae5…`), and every served file
     must match it.
   - It adds the verifier's recorded outcome (status, reasons, verdict, confirmation checks) from the audited record
     `experiments/do1/l4_r0/do1_l4_r0.jsonl` (pinned `00a8db20…`), plus the criterion `recovery.PASS_FRAC`.
   - Design, duration and seed are validated, and the file name comes from the export's index, never from the request.
   - A tampered file returns 503.
3. **The page.** `studio/src/do1/` (`Do1Recovery.tsx`, `do1Logic.ts`, `do1Types.ts`, `do1.css`):
   - Every number is computed from the per-seed rows or from the recorded verification. `aggregateOf` cross-checks the
     rows against the exported aggregates and fails loudly on any disagreement. No result is hardcoded.
   - Payloads load per seed: three files for a validation seed, one for a confirmation seed.
   - The viewer is the existing `Viewport`, `Transport` and `HeightChart`.

## What the page shows
- **Cards.** Walking k/24 with a 24-seed dot strip (each dot selects its seed), median distance, the median paired
  gain vs the faulty robot with better/worse/tied counts and the verdict, and the 20 s confirmation.
- **Seed selector.** All 24 validation seeds, each with its three outcomes. The pre-declared default seed 66645963 is
  labelled "Illustrative seed · pre-declared rule": the first seed where the frozen repair does not walk and DO-1 does.
  The aggregates stay visible whatever seed is chosen.
- **Replays.**
  - Validation mode: three synchronised viewports with the same camera, scale and clock. Play/pause/restart, speed,
    a scrub bar and a clickable torso-height chart.
  - Confirmation mode: DO-1's 20 s runs on the 24 confirmation seeds.
- **Why the frozen repair's longer walk is not FULL.** Its median distance is 0.38 m greater, but `full_recovery_v1`
  requires ≥ 80 % walking (20/24) and it has 19/24, so its 20 s confirmation never ran. The verifier's recorded reason
  is quoted verbatim.

## Verification (2026-10-21)
- Python: `tests/test_do1_api.py` (7 tests). With the app-level suites, 95 tests pass under a physics tripwire (0 hits).
- Frontend:
  - `npm run build` is OK.
  - vitest 189/190; the one failure is pre-existing and also fails on unmodified `main` (a locale-dependent number
    format in `forgeLogic.test.ts`). `src/do1/do1Logic.test.ts` (6) runs against the committed export and record.
- Browser: `BASE_URL=… [SHOT_DIR=…] node studio/e2e/do1-flow.mjs` gives 48/48 PASS.
  - Every card number is compared with `/api/do1/index`.
  - Also checked: seed switching loads exactly 3 payloads, dot picking, the shared clock and scrubbing, confirmation
    mode, invalid paths refused, and that the page issues only `GET /api/do1/*`.
  - A regression pass renders every other tab with simulation-backed requests aborted.
- Real-GPU check (Edge, Intel Iris Xe): 1× playback runs in real time.

## Floor grid visual issue: fixed (`3fe9add`)
- **Symptom:** the shared `Viewport`'s floor grid was missing in some viewports.
  - Real GPU (Intel Iris Xe): 12/162 frames of a size × seed × time sweep, depending on camera position.
  - SwiftShader: every frame.
- **Cause:** the floor (400 m) and the infinite grid (10,400 m) are each two huge triangles. Clipped at the 0.1 m near
  plane, their depth errors exceed the grid's 1 mm offset, so the floor won the depth test.
- **Fix:** the floor is a backdrop, drawn first (`renderOrder={-1}`) with no depth write.
- **After the fix:** 0/162 frames missing on GPU and on SwiftShader. The investigation details are in `docs/PROJECT_STATE.md`.

## Run locally
`powershell -ExecutionPolicy Bypass -File scripts\start_studio.ps1`, then open `http://127.0.0.1:8000/?tab=recovery`.
The Studio start-up computes its usual Phase 0 demo; the DO-1 page itself only reads files.
