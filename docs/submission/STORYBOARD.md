# Demo video storyboard (English, target 2:50, hard limit < 3:00)

Hackathon rules (see `docs/PROJECT_SPEC.md` §1.2): YouTube, under three minutes, no unlicensed third-party content, simulation-only entries need **at least one minute of the key modules actually operating**. Here about 1:50 of the runtime is the running Studio (shots 2-8). The video centres on the live loop; everything shown is real. Live Nemotron replies carry the LIVE label, archived ones RECORDED, fixtures SCRIPTED MOCK; nothing scripted is presented as a model. Footage comes from the recorded live takes of 2026-10-16 (`studio/e2e/forge-demo-capture.mjs` on the Nebius VM; takes, provenance and shot timings in `experiments/forge_loop/demo_capture/README.md`); the Nemotron wait may be cut, with a visible "(wait cut)" caption. Capture details: `SCREEN_CAPTURE_PLAN.md`.

Voice-over: plain English, calm pace (about 130 words per minute). On-screen text in brackets.

| # | Time | Screen | Voice-over |
|---|---|---|---|
| 1 | 0:00-0:12 | A drawn biped tips over in a push test. | "Robots fall. The hard part is knowing why, and proving that a fix really works. A user draws a robot; Nemotron investigates its failures; MuJoCo verifies the fix." |
| 2 | 0:12-0:27 | Studio: draw a creature, click *Use this creature*. | "This is Creature Forge. I draw a robot, and it becomes version one." |
| 3 | 0:27-0:42 | Target 15 N typed; push challenge runs; outcome POOR on 0 of 8 seeds at the target, per-seed scores, replay of the fall at 15 N (take `live1`). | "I want it to withstand a 15 newton shove. MuJoCo tests it: it only holds about 12 and a half, and falls backward. The failure is measured, not described." |
| 4 | 0:42-1:07 | *Investigate with AI* (LIVE banner, probes on); progress; cut the wait. | "Now a real call to NVIDIA Nemotron on Nebius Token Factory. It reads the measured evidence and requests diagnostic probes: counterfactual simulations run by code." |
| 5 | 1:07-1:30 | Probe cards: foot x1.5 CONFIRMED, friction x2 REFUTED (use the real values of the run shown). | "Each probe is judged by physics, not by the model. Longer feet: confirmed. More friction: refuted. The model has to propose with those results in front of it." |
| 6 | 1:30-1:55 | Proposal with cited evidence, then the arena table: AI arm VERIFIED beside its matched-random twin (INCONCLUSIVE in the archived run). | "It proposes a longer foot. MuJoCo tests it on held-out seeds, next to a random edit of the same size. A fixed rule decides: verified. The twin is not." |
| 7 | 1:55-2:10 | Click *Accept*; creature shows v2 attributed to Nemotron; v2 challenged. | "Only a verified redesign can be accepted. It becomes version two, and we challenge it again." |
| 8 | 2:10-2:25 | Honest negative (take `live2-walk`): walking; the probes contradict the model's own hypotheses (longer feet walk 4.8 m less); its controller tweak gains 0.12 m, NOT_VERIFIED; Accept stays disabled. | "It does not always work. On walking, physics contradicted the model's own hypotheses, and its small controller change gained about 12 centimetres, far below our half-metre bar. Not verified, so it cannot be accepted. We show that too." |
| 9 | 2:25-2:50 | Slide: scoreboard with caveats (below), then end card. | "Pre-registered across twelve investigations: the Nemotron-selected redesign verified six times, its matched random twin once. Encouraging, but small, six starter shapes, mostly the push challenge, and the AI picked from up to three proposals. Built for the Nebius and NVIDIA hackathon." |

**Scoreboard slide text (all lines required, none omitted):** "Pre-registered, 12 investigations: Nemotron-selected redesign verified 6/12; matched-random twin 1/12 (exact one-sided p = 0.03125). Encouraging evidence for the tested creatures and challenges only. Small sample (12). Six starter families, each repeated. 5 of 6 successes on the push challenge. AI chose the best of up to 3 proposals; the twin is one edit (post-hoc best-of-k check: 5 vs 0). Walking: nothing verified."

If the honest-negative clip should show an INCONCLUSIVE verdict instead of walking, use the development record `i-c2c4c48729d3` (INCONCLUSIVE) or a scoreboard cell such as bird-knees/push rep 2 (AI INCONCLUSIVE); keep the verdict label visible.

## Rules for the edit
- Keep the LIVE / RECORDED / SCRIPTED MOCK banner visible whenever a model reply is on screen. A cut wait must be captioned.
- Do not show terminals with environment variables, `.env`, tokens, request headers, or the Nebius console with account identifiers or balances.
- Use only footage captured from the app; no stock clips, no third-party music unless the track's licence is documented (preferred: no music).
- Do not display NVIDIA or Nebius logos or marks (not licensed for use here); name them in text only.
- Do not say "partner", "sponsored by" or "endorsed by"; say "built for the Nebius x NVIDIA Global AI Hackathon".
- Never say the model "proves", "beats random", or is "significantly better"; never present the scoreboard without its caveats; never say Nemotron produced the classical 150/150 controller.
- The memory evaluation is complete with a null result (no evidence of a benefit, p = 0.77). If mentioned at all, say exactly that; never imply memory helped.
