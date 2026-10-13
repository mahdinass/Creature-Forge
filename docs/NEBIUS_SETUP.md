# Nebius × NVIDIA — credits and integration onboarding

Source information supplied by the project owner on October 13, 2026, with corroborating hackathon material. **These are offers and links, not a confirmation that credits have been redeemed.**

## Builder resources

- Nebius for AI Builders: https://dev.nebius.com/
- Nebius Builders Program: https://dev.nebius.com/builders
- Nebius community Discord: https://discord.gg/eXYTGhgnhK
- Hackathon rules: https://nebiusglobalaihackathon.devpost.com/rules
- Hackathon FAQ: https://nebiusglobalaihackathon.devpost.com/details/faqs

## Token Factory credit paths

1. **$25 promotional Token Factory credit:** https://nebius.com/promo-code?utm_promo_event_code=2026-devpost-global-ai-hack&utm_promo_code_type=Token_Factory&utm_promo_activation_code=NEBIUS-DEVPOST-GLOBAL26
   - Activation code: `NEBIUS-DEVPOST-GLOBAL26`.
   - Complete the official form and check successful activation in your own Nebius account.
2. **Another advertised $25 Token Factory credit:** enroll at https://dev.nebius.com/builders. The program also advertises Tavily / Nebius Academy resources, office hours and community access.

The two promotional routes advertise up to $50 in Token Factory credits **subject to eligibility, program terms, and successful provisioning**. Credits are **not** the same as Nebius AI Cloud GPU-compute credits. Do not infer that any account has received them. Check expiration, payment/billing requirements and quotas in the actual account.

## Project integration requirements

- Use an eligible NVIDIA open-source model for a meaningful **runtime** task in Creature Forge (e.g. Nemotron interpreting physics telemetry and proposing constrained experiments).
- Invoke it via Nebius Token Factory inference or use Nebius AI Cloud compute in a compliant manner, as specified in the official rules.
- Verify actual endpoint, model catalog, tool calling / structured output support and API key in a smoke test. Do not hardcode a model ID from an older blog post.
- Keep `NEBIUS_API_KEY` in user environment or a local gitignored `.env`, not in source, notes, screenshots or memory.
- Account-credit activation and API access are two separate checks. Stop and ask for user action if billing/onboarding or OAuth requires private information.
- Save only redacted model IDs, endpoint class, request IDs, timing, token counts and cost estimates in logs.
- Set per-session and per-day limits before enabling multi-run agents; the main project spec has suggested budget caps.

## Status

- [ ] $25 promo form successfully redeemed (user verifies)
- [ ] Builders Program enrolled and second credit confirmed (user verifies)
- [ ] Nebius account / country-of-billing supported and approved
- [ ] Nebius API key created and stored locally
- [ ] Active eligible Nemotron model listed
- [ ] Real runtime inference smoke test succeeds
- [ ] Token / compute limits and spending guard configured

Do not check boxes based on a promise or an AI-generated response; verify external state directly.

## Client token-budget semantics
`NebiusClient` blocks a request before any network call if `tokens_used + estimate_prompt_tokens(messages) + max_tokens` exceeds `max_total_tokens`. Completion size is hard-capped by `max_tokens`; the prompt estimate is a heuristic (~3 UTF-8 bytes per token + 64), not a server-verified count or guaranteed bound. Actual API-reported usage is added afterwards and blocks later calls. Request count and timeout are hard limits; there are no retries.
