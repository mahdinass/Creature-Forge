# Draft: request for written clarification (for the owner to review and send; NOT sent)

Prepared 2026-10-16. Clause wording below is quoted as recorded in `docs/MODEL_AND_SERVICE_TERMS.md` section 2 (from https://docs.nebius.com/legal/agreement, read 2026-10-16; the page shows publication date September 15, 2026 and effective date September 28, 2026). Check it against the live page before sending.

---

**To:** [Nebius support / hackathon organiser contact: fill in the channel shown in the Nebius console or the hackathon page]
**Subject:** Two questions on the Nebius Services Agreement before our hackathon submission (Creature Forge)

Hello,

I am submitting "Creature Forge" to the Nebius x NVIDIA Global AI Hackathon 2026 (submission deadline Friday 30 October 2026, 18:00 Europe/Oslo). The project runs a hosted NVIDIA Nemotron model through Nebius Token Factory and runs its physics simulations on a Nebius AI Cloud VM. The hackathon rules ask us to explain publicly where these are used. I would like written confirmation on two points of the Nebius Services Agreement so that we comply with it.

**Question 1: Clause 18.7 (publicity and use of the Nebius name).** The clause says that references to Nebius, and "the fact and/or details of cooperation relating to this Agreement", may be communicated "to third parties or the public with the prior written consent of Nebius". May our public hackathon submission (repository README, Devpost text, and a video under 3 minutes) state **factually** that the project runs on Nebius AI Cloud and Nebius Token Factory? We would use the names in plain text only: no Nebius logos, and no wording that suggests endorsement, sponsorship or partnership beyond participating in the hackathon.

**Question 2: Clause 4.1.10(c) ("competitive analysis or benchmarking").** The clause restricts use of the Services to "engage in competitive analysis or benchmarking". We want to publish the results of our own pre-registered evaluation. It compares the hosted Nemotron model's redesign proposals with matched random edits and, in a second study, with a no-memory baseline, each verified in the MuJoCo physics simulator. In the first study the AI-selected redesign was verified in 6 of 12 cases against 1 of 12 for its matched-random twin. The second study found no evidence of a benefit from the memory feature. Does publishing this evaluation fall under clause 4.1.10(c)?

To be precise about what it is: it compares a model's outputs against random baselines, on our own robot-design task. It does not compare Nebius with any other provider, and it reports no latency, throughput or price comparison between providers. If any part of this would be restricted, please tell me which part so that I can remove it.

Our repository is private until publication. I am happy to share the relevant text of the draft submission for review. A written reply, even a short one, before the deadline would help us keep the public materials accurate.

Thank you for your time,

[Name], project owner, Creature Forge
[Preferred reply channel: add when sending]

---

## Before sending (owner checklist; not part of the message)

- [ ] Open the live Nebius agreement and confirm the exact wording and clause numbers of 18.7 and 4.1.10(c) (the quotes above come from a summarised page read; the lead-in sentence of 4.1.10 was not captured).
- [ ] Choose the recipient: the Nebius support channel and/or the hackathon organisers (Devpost organiser channel). Do not include API keys, account ids or the VM address.
- [ ] Add your name and preferred reply channel; keep your personal email address out of repository copies of this file.
- [ ] Confirm the numbers (6/12 vs 1/12; memory evaluation null result) against `experiments/forge_loop/scoreboard/REPORT.md` and `experiments/forge_loop/memory_eval/REPORT.md`.
- [ ] Decide whether to also ask the question about the NVIDIA model licences; the model cards were verified 2026-10-16 and the text read does not restrict hosted use (see `docs/MODEL_AND_SERVICE_TERMS.md` sections 1c and 1d), so it is left out to keep this short.
- [ ] After sending, record: date sent ____ , channel ____ , reply received ____ , outcome ____ . If no written answer arrives by the deadline, keep public text to factual naming only: no logos, no endorsement wording, no cross-provider comparison, and decide separately whether to publish the evaluation figures.
- [ ] Update `docs/submission/SUBMISSION_CHECKLIST.md` and `docs/submission/LICENSE_REVIEW.md` (section 5b) with the outcome.
