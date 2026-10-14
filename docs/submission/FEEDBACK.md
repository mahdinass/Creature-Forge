# Feedback on Nebius and NVIDIA technologies (from actual use, 2026-10-13 → 2026-10-14)

Required by the hackathon submission. Everything below was observed during this project; where we could not verify something we say so.

## Nebius Token Factory (inference)
**Worked well**
- OpenAI-compatible chat API worked on the first call; `usage` and request ids make auditing easy; total latency of 0.4–1.2 s for short prompts and 16–80 s for long reasoning replies.
- `llms.txt` and `.md` doc pages are a good idea for tooling.

**Friction / requests**
1. **Reasoning models and token budgets.** For `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, hidden reasoning consumed 3.4k–6.7k completion tokens for a short JSON task. When `max_tokens` was exhausted the API returned HTTP 200, `finish_reason=length` and **`content: null`** with no partial answer. A dedicated `reasoning_budget`, or returning partial visible content, or an explicit error code would avoid silent empty answers.
2. **`reasoning_effort`.** The docs list `none|minimal|low|medium|high|xhigh|max` but not per-model behaviour. For this model `none` was accepted yet reasoning was still present and content was null; `low`/`medium` gave similar token counts. Please document which values each model honours and what they do.
3. **`usage.completion_tokens_details.reasoning_tokens`** exists in the spec but was not returned for this model, so we could not verify the effect of the effort setting.
4. **Prices.** We could not find the per-token price of this model in the public docs, so cost estimates are bracketed assumptions. A price column on each model's page would help budget caps.
5. **Structured output** is documented as model-dependent; a machine-readable capability flag per model would help (we did not use it).

## Nebius AI Cloud (compute)
**Worked well**
- VM creation with the CLI is simple; a `cpu-d3` 8 vCPU / 32 GiB machine (≈ $0.264/h compute + disk) booted in about a minute; stop/start preserved the disk and the public IP. cloud-init user data made the SSH-key-only setup reproducible.
- Quota errors name the quota and region exactly.

**Friction / requests**
1. **No native Windows CLI.** We installed Ubuntu in WSL just to run `nebius`; a Windows build (or documented PowerShell route) would help many hackathon users.
2. **New-account non-GPU vCPU quota was 0 in `eu-north1` and `us-central1`** (the regions the docs lead with) but 200 elsewhere; discovering this took a failed create. Showing quotas in the create docs/quickstart would save time.
3. **Credit balance** could not be read from the CLI; the pricing page did not list the public-IPv4 price.
4. Stopped VMs still bill for disks (documented); an explicit "estimated cost while stopped" in `instance get` would help.

## NVIDIA Nemotron
**Worked well**
- When Nemotron 3 Nano produced content it followed a strict JSON schema, cited values that resolved correctly in the evidence, and proposed bounded, falsifiable edits.
- The model card states commercial use is allowed.

**Friction / requests**
1. Hidden reasoning cannot be turned off in the hosted setting we used (no documented `enable_thinking` / `chat_template_kwargs` equivalent); for short structured tasks a non-reasoning mode would be more economical and more reliable.
2. The Nemotron Open Model License does not say how hosted/API-only use is treated; a short FAQ would remove doubt for projects that never redistribute weights.
3. Guidance on reasoning-token budgets per task type would help users size `max_tokens`.

## Honest note
These observations come from one account and one model over two days; some may reflect our prompts (for example the 2.7k-token evidence prompt) rather than the platform.
