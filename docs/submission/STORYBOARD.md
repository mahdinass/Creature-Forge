# Demo video storyboard (English, target 2:40, hard limit < 3:00)

Hackathon rules (see `docs/PROJECT_SPEC.md` §1.2): YouTube, under three minutes, no unlicensed third-party content, simulation-only entries need **at least one minute of the key modules actually operating**. Here ≈ 1:55 of the runtime is live software (shots 3–7). Everything shown is real: recorded Nemotron runs are labelled RECORDED LIVE; nothing scripted is presented as a model.

Voice-over (plain English, calm pace ≈ 130 words per minute). On-screen text in brackets. Capture commands and the state to prepare are in `SCREEN_CAPTURE_PLAN.md`.

| # | Time | Screen | Voice-over |
|---|---|---|---|
| 1 | 0:00–0:12 | Studio: a biped is pushed and falls (Compare tab, 8 cm foot). | "Robots fall. The hard part isn't the fall — it's knowing why, and proving that a fix really works. This is Creature Forge." |
| 2 | 0:12–0:25 | Overview tab: five-step pipeline. | "A failure is measured in MuJoCo. We capture the evidence. NVIDIA Nemotron, running on Nebius Token Factory, proposes bounded fixes. MuJoCo tests every one — next to a random edit of the same size — and decides." |
| 3 | 0:25–0:50 | AI Investigation → recorded live run 2 → **Observed failure**: failing seed 9101 measured; then **What the model saw**: the exact evidence JSON. | "Here the starting controller falls at start-up on this seed. This exact, measured context is all the model sees — no conclusions, only numbers." |
| 4 | 0:50–1:15 | **Model proposal**: banner RECORDED LIVE, raw reply, two proposals with the evidence values they cite, requested vs realised edit, predicted gain. | "Nemotron returns two proposals, each citing measured values and making a falsifiable prediction. This is a stored copy of a real call; the banner says so. Anything invalid is rejected — like the first recorded run, where the model cited the wrong paths and nothing was simulated." |
| 5 | 1:15–1:45 | **Verification**: table 19/32 → 28/32 and 25/32; matched random edits 25/32 and 30/32; per-seed bars. | "MuJoCo tests each proposal on thirty-two fresh seeds. Both edits help: twenty-eight and twenty-five walking seeds, against nineteen. But look at the random edits: twenty-five, and thirty. Random edits of this size help too, so one run can't show the model is better — and we say so." |
| 6 | 1:45–2:10 | **Replay and verdict**: synchronized replay seed 9101: frozen controller falls at 3 s, edited walks; height chart. Verdict text. | "Replay the same failure side by side. The original falls after three seconds; the edited controller keeps walking. These are fresh deterministic simulations, not recordings of video." |
| 7 | 2:10–2:30 | Overview: classical card (150/150 vs 91/150, "no language model"); Nemotron card with "not completed" notice. | "Separately, a classical local optimiser found a controller that walks on 150 of 150 untouched seeds versus 91, statistically confirmed — with no language model involved. Our systematic Nemotron-versus-random study wasn't completed: generation calibration failed, and the report says so." |
| 8 | 2:30–2:40 | Repo / README with license and the Nebius VM controller; end card. | "Everything is preregistered, reproducible and Apache-2.0. Simulation on Nebius AI Cloud, inference on Nebius Token Factory, with NVIDIA Nemotron. Creature Forge: machines that learn from falling." |

## Rules for the edit
- Keep the RECORDED LIVE / SCRIPTED MOCK / LIVE banners visible whenever a model reply is on screen.
- Do not show terminals with environment variables, `.env`, tokens, request headers, or the Nebius console with account identifiers or balances.
- Use only footage captured from the app; no stock clips, no third-party music unless the track's licence is documented (preferred: no music, or a track licensed for this use).
- Do not display NVIDIA or Nebius logos or marks (not licensed for use here); name them in text only.
- Do not say "partner", "sponsored by" or "endorsed by"; say "built for the Nebius × NVIDIA Global AI Hackathon".
- Never say the model "discovered" the 150/150 controller; never say it "beat" random edits.
- Optional live segment (only if budget and time allow, within the shared cap): a single *Run live* click, cut to the finished result; the banner must read LIVE.
