# Feedback on Nebius and NVIDIA technologies (from actual use, 2026-10-13 -> 2026-10-15)

Required by the hackathon submission. Everything below was observed during this project and is backed by a record in the repository (named in each section); where we could not verify something we say so or leave it out. These are engineering observations from one account, not benchmarks of the platform or the models.

## What we use

Creature Forge's Forge Loop calls **`nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory** with thinking disabled (`chat_template_kwargs.enable_thinking=false`) and strict `json_schema` guided decoding, `max_tokens` 8,000, temperature 0.6. The model reads measured physics evidence about a failing creature, optionally requests diagnostic probes, and proposes bounded edits; MuJoCo and a fixed rule decide whether an edit is a verified improvement. The calibration that led to this default is in `experiments/forge_loop/calibration/REPORT.md`. The earlier phases of the project used `NVIDIA-Nemotron-3-Nano-30B-A3B`; observations about that phase are marked "earlier phase".

## Nebius Token Factory (inference)

**Worked well**
- The OpenAI-compatible chat API accepted a strict `json_schema` response format on all four models we calibrated (12/12 requests in the first round returned HTTP 200, `finish_reason=stop` and non-empty content). That made structured output practical to build on.
- The schema constraint is genuinely useful for identifiers. Our first contract left hypothesis ids and evidence citations to the prompt and 0/12 replies were machine-valid; after we enumerated the hypothesis ids, the editable parameter names and every citable evidence path in the JSON schema, 9/12 and then 6/6 of the chosen configurations were valid. Our lesson was to constrain identifiers by construction, not by instruction (calibration v1 and v2; `docs/memory/INCIDENTS.md`).
- Latency and cost for the production configuration are low: 4.0-4.8 s per call, about 770-930 completion tokens, about $0.002 per call in our ledger (cost is our own computation from recorded usage). The 12-investigation scoreboard used 24 model calls, 146,901 tokens and $0.050.
- Responses carry request ids and `usage`, which we store in every investigation record, so each result can be traced to a specific call.

**Friction / requests**
1. **Which reasoning controls work on which model.** We found the working combination by experiment. For Super, `enable_thinking=false` through `chat_template_kwargs` gave short, valid replies (4/4). For Ultra, `reasoning_effort=low` was valid 4/4 but took 28-61 s and 7.8k-14.5k completion tokens, close to our 16k cap. A per-model table of which of `reasoning_effort` and `chat_template_kwargs.enable_thinking` is honoured, and what each does to latency and token use, would have saved calibration requests.
2. **Reasoning budget and empty content (earlier phase and calibration).** With Nano, hidden reasoning consumed the completion budget on a short JSON task and the API returned HTTP 200 with `finish_reason=length` and **`content: null`**. In calibration, Nano with `reasoning_effort=low` hit the 16,000-token cap after 96 s with empty content. An earlier-phase test with `reasoning_effort="none"` on Nano also returned null content (`docs/memory/INCIDENTS.md`). Returning partial visible content, a dedicated reasoning budget, or an explicit error status would avoid silent empty answers. In that phase `usage` also did not report a `reasoning_tokens` figure, so the hidden spend could not be seen per call (`docs/PROJECT_STATE.md`, R3 notes). (In calibration, Nano with `enable_thinking=false` was valid under the production edit rule; we did not choose it.)
3. **Bounds are not enforced by guided decoding.** Strict `json_schema` enforced the format and the enums, but two of the twelve second-round calibration requests (Super with `reasoning_effort=low`, Ultra with thinking off) still proposed edits outside the numeric bounds stated in the prompt, for example `foot_length` x2.0 where the limit was 1.5. This is not a platform defect: our server-side validator re-checks every edit and rejects it. We mention it because numeric range constraints in the guided-decoding schema, if supported, would reduce rejected replies.

## Nebius AI Cloud (compute)

**Worked well**
- The Studio, MuJoCo batches, the scoreboard (8,870 rollouts in 21.5 minutes) and the live browser flow all ran on one Nebius VM; code was synced over SSH and the Studio was reached through an SSH tunnel. The VM could be stopped and started through the API.

**Friction / requests**
1. **A guest-initiated power-off did not stop the billing state.** Our 6-hour in-guest deadman (`poweroff` inside the VM) fired, SSH stopped answering, yet the instance still reported `RUNNING` 3.75 hours later; an API `stop` brought it to `STOPPED` immediately (`docs/memory/INCIDENTS.md`, 2026-10-15). We could not verify whether that period was billed, so we assumed it was. Having an instance whose guest powered itself off transition to a stopped state, or documenting how it is billed, would help.
2. **Regional CPU quota.** On this tenant `eu-north1` and `us-central1` showed a 0 vCPU quota (`nebius quotas quota-allowance list`), so the VM was created in `eu-west1` (`docs/NEBIUS_CLOUD_R1.md`). A clearer first-run message about where quota exists would have saved a step.
3. **Stopped VMs still bill for disk.** The 50 GiB boot disk costs about $0.12/day while the VM is stopped (docs.nebius.com pricing as recorded in `docs/NEBIUS_CLOUD_R1.md`). This is documented and reasonable; we mention it because our spend ledger has to account for it explicitly.

## NVIDIA Nemotron

**Worked well**
- With the strict schema, Nemotron 3 Super (thinking off) returned valid, grounded proposals: every citation resolved to a real value in the evidence, edits stayed inside the allowed parameters (4/4 in the chosen configuration), and the diagnoses were physically sensible (foot length, ankle balance gain, standing posture, leg proportions). In calibration, Ultra with `reasoning_effort=low` produced the most diverse hypotheses (an informal reading).
- In the end-to-end run `i-140b1435cb84` (live browser flow, 15/15 checks), Nemotron proposed `foot_length` x1.35 after seeing the probe results, and MuJoCo verified it on 12 held-out seeds (+6.25 N median critical push force) while the matched random edit was inconclusive. That is one worked case, not a statistic.
- Pre-registered scoreboard, exactly as `experiments/forge_loop/scoreboard/REPORT.md` frames it: across 12 investigations of drawn creatures, the Nemotron-selected redesign verified in 6/12 and its matched random twin in 1/12 (exact one-sided McNemar on the discordant pairs 5 vs 0, p = 0.031). The sample is small (six starter creatures, two replicates, one model, one physics model), 5 of the 6 AI successes were on the push challenge, the AI picked the best of up to three proposals, and no walking redesign was verified. We read it as encouraging for the tested creatures and challenges, and make no claim of general superiority.

**Friction / requests**
1. **Plausible but inconsistent diagnoses.** Across repeated development runs on one creature the model's hypotheses were physically plausible but varied between runs (torque, friction, heel geometry), and on the walking challenge it repeatedly identified the support base (the probes confirmed it) but chose edits too small to pass our 0.5 m bar (`experiments/forge_loop/dev_live_records/README.md`). We handle both with probes and an independent verifier; model-side guidance on keeping a diagnosis consistent across samples would help.
2. **Earlier phase (Nano):** the first live investigation, with Nano, blamed torso inertia, which MuJoCo falsified (`docs/memory/INCIDENTS.md`); we kept it as a recorded failed trial, which is the intended behaviour of the verifier. We moved the default to Super after the calibration above.

## Update, 2026-10-16 → 2026-10-24 (later phases; same account)

**Nebius AI Cloud: what worked well**
- **Service accounts with resource-scoped access permits.**
  - A group whose only rights are `editor` permits on two specific instances let an unattended watchdog and the VM itself
    stop instances through the API.
  - A project-wide listing is refused, so the scope is visibly minimal.
  - `iam auth-public-key generate --expires-at` gives keys that expire on their own.
  - In a live test, the VM requested its own API stop and the control plane reported STOPPED 47 s later
    (`infra/nebius/forge_cloud.py`, `infra/nebius/remote/forge-selfstop`).
- **Large batch work.** A registered study ran on a 64-vCPU VM: 480 physics episodes in about 3.4 h. Each run finished
  with an API self-stop (`docs/E1_RESULTS.md`).

**Nebius AI Cloud: friction and requests**
1. **The CLI federation login is a fixed ~12 h token with no refresh.**
   - Twice, a long run outlived it. The unattended stop then failed until the owner logged in again, about 5–7 h later.
     The overrun cost was about $11 on 2026-10-19 and about $1.5 on 2026-10-24 (`docs/memory/INCIDENTS.md`,
     `docs/PROJECT_STATE.md`).
   - We now keep every deadline inside the token lifetime and use a service account for stops.
   - **Request:** a refreshable CLI session, or an expiry warning in `nebius` output.
2. **A guest power-off is restarted by the platform.** The instance's desired state is "running", so an in-guest `poweroff`
   is not a billing stop (re-observed twice on 2026-10-20). Only an API stop holds.
   - **Request:** an instance-level maximum runtime or TTL, or a "stay stopped on guest shutdown" option.
3. **`nebius profile create` silently activates the new profile.** Creating a service-account profile switched our
   default away from the owner's federation profile. We had to run `profile activate` again.
4. **vCPU is not cores.** The 64-vCPU preset behaved like about 32 physical cores for our numpy/MuJoCo workers. On the
   8-vCPU VM, an SMT benchmark showed no throughput gain beyond 4 processes.
   - **Request:** state the vCPU → core mapping beside the presets.

**Nebius Token Factory and Nemotron (2026-10-24)**
- **Live checks.** One request each to `nvidia/nemotron-3-super-120b-a12b` (0.7 s) and
  `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (1.3 s), both HTTP 200.
- **Live end-to-end Studio investigation.** The Forge Loop ran over real HTTP on a Nebius VM (two rounds, 2 model calls,
  about $0.004; `docs/submission/evidence/live_acceptance_2026-10-24.json`).
  - **Round 1:** Nemotron's "rear foot length × 1.25" was verified by MuJoCo on 12 held-out seeds (12 wins, 0 losses).
    A size-matched random edit also verified in that round.
  - **Round 2:** its proposal was inconclusive.
- **Nemotron's runtime decisions do not yet beat our deterministic engine on outcomes** (15 vs 14 across 36 paired
  instances; `docs/NEMOTRON_CONTRIBUTION.md`). We report this as found.

## Honest note
These observations come from one account, a small number of calibration requests (30 requests, $0.31 in total, including n = 1 per model-setting pair outside the chosen ones) and two days of development. Some may reflect our prompts or contract (the first calibration round failed because of our schema, not the models) rather than the platform. "Valid" in the calibration means machine-checkable and grounded in real evidence paths, not physically correct.
