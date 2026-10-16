# Model and service terms (separate from the project's Apache-2.0 license)

Reviewed 2026-10-14 from the public pages named below. This is a working summary, **not legal advice**; read the originals before the public release. The project's own code is Apache-2.0 (`LICENSE`); nothing below changes that, and nothing in this repository grants rights to the model or the services.

## 1. NVIDIA Nemotron (model) — how we use it
- Model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, called only as a **hosted inference service through Nebius Token Factory**. No weights, quantisations, fine-tunes or other derivative models are included in or distributed with this repository.
- The model card (Hugging Face, `NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`) states: "Use of this model is governed by the **NVIDIA Nemotron Open Model License**" and "This model is ready for commercial use."
- **NVIDIA Nemotron Open Model License** (https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/, "Last Modified: December 15, 2025"), as read: perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable licence to reproduce, create derivative works, publicly display/perform, sublicense and distribute the Work; commercially usable. If the Work (or a derivative) is **redistributed**: give recipients the licence, keep notices, and include a Notice file with "Licensed by NVIDIA Corporation under the NVIDIA Nemotron Model License" where the Work has a NOTICE file. NVIDIA claims no ownership of outputs. No NVIDIA trademark licence beyond reasonable descriptive use. Export/sanctions compliance applies. Termination only on patent/copyright litigation against NVIDIA over the Work. Delaware law, Santa Clara County courts. The text **does not address hosted/API-only use**, has no acceptable-use or guardrail clause in the version read, and refers to an Appendix and possibly other NVIDIA pages that were not available to read.
- The generic *NVIDIA Open Model License* (version of Oct 24, 2025) is a different document (it has a guardrail-bypass termination clause and Trustworthy-AI terms). It is **not** the licence named on the Nemotron 3 Nano model card; if NVIDIA changes the card or the model is switched, re-check which licence applies.
- **Consequence for this project:** because we do not distribute the model, the redistribution conditions (notice file, licence copy) are not triggered by our use as far as the text shows; the hosted-use question is not answered by the text, so confirm with NVIDIA/Nebius if the repository or demo ever bundles weights or a derivative. If weights are ever shipped, add the licence copy and the Notice text above.
- Hackathon rule (from `docs/PROJECT_SPEC.md`): the software must use at least one NVIDIA open-source model; this satisfies it through Token Factory.

### 1a. Which models the project actually called (checked 2026-10-16 by grep of the `"model"` fields under `experiments/`)
| model | where it appears | calls recorded (`"model"` field count) |
|---|---|---|
| `nvidia/nemotron-3-super-120b-a12b` (Super) | Forge Loop default: dev live records, scoreboard records, memory-evaluation records, calibration | 237 |
| `nvidia/Nemotron-3-Ultra-550b-a55b` (Ultra) | `forge_loop/calibration/` only (plus the optional "deep" entry in `model_config.json`); not in the scoreboard or memory evaluation | 19 |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (Nano) | earlier phase: `demo_trials`, `phase1`, `phase2a_r3`, and the calibration comparison | 41 |
| `nvidia/Nemotron-3_5-Lightning` (Lightning) | `forge_loop/calibration/` only (12 requests; the calibration report says it passed but offered no advantage over Super) | 12 |

Lightning was not named in earlier versions of this file. **Its licence was not reviewed** (see section 1e).

### 1b. Forge Loop models: summary (rewritten 2026-10-16)
- Super is the **default** Forge Loop model (`experiments/forge_loop/model_config.json`) and the only model behind the scoreboard and memory-evaluation results. Ultra is an **optional** "deep" profile that was used only in calibration. Nano was the earlier demo/R3 model (section 1). All are used only as hosted inference through Nebius Token Factory; no weights are distributed.
- Verified 2026-10-16 from NVIDIA's own pages: Super is under the NVIDIA Nemotron Open Model License (same as Nano); Ultra is under OpenMDW-1.1 (a different licence). Details in sections 1c and 1d.
- **Benchmarking clause:** Nebius Services Agreement §4.1.10(c) is quoted in section 2. The scoreboard compares a hosted model's proposals with matched random edits (not Nebius against another provider). Whether that falls under the clause is **not decided here**; it is a question in `docs/submission/NEBIUS_CLARIFICATION_REQUEST.md` and is tracked in `docs/submission/LICENSE_REVIEW.md` section 3c.

### 1c. NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`), read 2026-10-16
**Licence: NVIDIA Nemotron Open Model License** (https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/, "Last Modified: December 15, 2025").

Verified from the official pages:
- Model card (Hugging Face `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16`, read 2026-10-16): "Use of this model is governed by the NVIDIA Nemotron Open Model License." and "This model is ready for commercial use." The card says the NIM container is governed instead by the NVIDIA Software License Agreement and Product-Specific Terms for AI Products. We do not use a NIM container.
- Licence page, as read through a page-summarising fetch (the page directs readers to a "Download PDF" for the full text; section numbers are those the page shows):
  - §2 Grant: perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable licence to reproduce, modify, display, perform, sublicense and distribute the Work. The grant terminates if you start patent or copyright litigation alleging infringement by the Work or its outputs.
  - §3 Redistribution: give recipients a copy of the licence, retain notices, and, if the Work includes a NOTICE file, include the statement referencing the "NVIDIA Nemotron Model License". Applies only to redistributing the Work or derivatives.
  - Outputs: the page states NVIDIA claims no ownership of outputs generated from the Works ("Works are commercially usable").
  - §4 Trademarks: no right to NVIDIA trade names, trademarks or product names, "except for reasonable, customary descriptive use" (paraphrase of the page text).
  - §5 "AS IS" disclaimer; §6 limitation of liability; §7 if you offer warranty or indemnity to others you must indemnify NVIDIA for related claims; §8 NVIDIA may use feedback; §9 Delaware law, Santa Clara County courts; §10 export, import and sanctions compliance (EAR, OFAC).
- Model card, ethical considerations: "NVIDIA believes Trustworthy AI is a shared responsibility" and "We advise against circumvention of any provided safety guardrails contained in the Model". This is advice on the model card, not a licence clause that the licence page showed.

Applies to THIS project:
- Hosted inference through Token Factory via API: the licence text read does not address hosted or API-only use. We never download, fine-tune or redistribute weights, so the §3 redistribution conditions are not triggered on the text read.
- Publishing model outputs (raw replies in `experiments/` records): no output restriction was found; NVIDIA claims no ownership of outputs.
- Attribution: no attribution requirement for API-only use found; naming the model factually is descriptive use. No NVIDIA logos or endorsement wording.
- Use restrictions / acceptable-use clause: none shown on the licence page. The Trustworthy-AI guardrail text is advisory on the model card.
- Evaluation/benchmark publication: no clause found.
- Termination / patent: only the patent/copyright litigation trigger in §2.

NOT verified: the full licence text (only the page rendering was read, via summarisation, not the PDF); whether an appendix or other NVIDIA pages add terms; whether Nebius's hosted copy of the model is offered under additional Nebius terms (the Nebius Quick Guide says third-party models follow their own terms, section 2).

### 1d. NVIDIA Nemotron 3 Ultra (`nvidia/Nemotron-3-Ultra-550b-a55b`), read 2026-10-16
**Licence: OpenMDW License Agreement, version 1.1 (OpenMDW-1.1)** (https://raw.githubusercontent.com/OpenMDW/OpenMDW/refs/heads/main/1.1/LICENSE.OpenMDW-1.1; index https://openmdw.ai/license/, page dated 2026-05-27).

Verified from official pages:
- Model card (Hugging Face `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16`, read 2026-10-16): licence tag "openmdw-1.1"; "Use of this model is governed by the" OpenMDW License Agreement, version 1.1, listed under "Governing Download Terms"; "This model is ready for commercial and non-commercial use." Same Trustworthy-AI advisory text as Super ("We advise against circumvention of any provided safety guardrails"). The last ~4,000 characters of the card page were not read.
- The licence text has **no section numbers or headings** (one block of paragraphs), so no section citations can be given. Key phrases as read:
  - Grant: use, modify and share the Model Materials without charge, subject to the agreement (copyright, patent, database and trade-secret rights).
  - Redistribution only: "you shall retain in your distribution (1) a copy of this agreement" plus copyright and origin notices.
  - Outputs: "This agreement does not impose any restrictions or obligations with respect to any use" (of outputs; the full sentence continues past the quoted words).
  - Termination: if you sue anyone claiming the materials infringe a patent or copyright, "then all rights and grants made to you hereunder are terminated" (exception for responding to a suit already brought against you).
  - "AS IS" disclaimer and limitation of liability; you are responsible for clearing third-party rights.
- Not found in the text read: acceptable-use restrictions, trademark clause, attribution requirement for API use, any evaluation or benchmark-publication clause.

Applies to THIS project: Ultra was called only in the calibration (19 recorded calls); results published in the scoreboard and memory evaluation did not use it. Hosted use through Token Factory involves no redistribution, so the notice and copy-of-licence condition is not triggered; outputs are expressly unrestricted.

NOT verified: the full verbatim licence text (read through summarisation, which declined to reproduce it); an NVIDIA-hosted card page (build.nvidia.com returned no licence text; the Hugging Face card is the source). A search result noted that a third-party mirror (a Dell-hosted copy of the Hugging Face page) labels the licence "NVIDIA Open Model License"; the official Hugging Face card and NGC listing say OpenMDW-1.1, and this review follows the official card. Re-check the card before publication.

### 1e. Lightning
`nvidia/Nemotron-3_5-Lightning` was called 12 times, only during calibration. Its model card and licence were **not read**. Public text should not assert a licence for it; mention it only as "also tried in calibration" or omit it.

## 2. Nebius (services)
- Sources: Services Agreement https://docs.nebius.com/legal/agreement, Token Factory Legal Quick Guide https://docs.tokenfactory.nebius.com/legal/legal-quick-guide.md (both read 2026-10-14; the AUP, Service-Specific Terms and DPA were not read).
- **Third-party models (§13):** third-party services/models are governed by their own terms; the customer must comply with them; Nebius's indemnity, warranty and support do not apply to them. The Quick Guide does not discuss model licences.
- **Our content:** the Quick Guide says customers own their inputs/outputs and that Nebius does not use customer content to train models; without Zero Data Retention, inputs/outputs may be stored (Finland) for speculative decoding. Prompts here contain only simulation data (no personal data, no credentials).
- **Use restrictions to keep in mind:** comply with the AUP; no use for consumer/personal/household purposes (§4.1.10(a)); stay within API rate limits (§4.1.9(b)); no "competitive analysis or benchmarking" (§4.1.10(c)); outputs are provided "as is" (§15.3). Trial credits: the customer bears the risk and costs of use during the trial period (§6.2).
- **Re-read 2026-10-16** (https://docs.nebius.com/legal/agreement, page shows publication date September 15, 2026 and effective date September 28, 2026; read through a page-summarising fetch, so confirm wording against the page). Clause 4.1.10 fragments as read: (a) "for any consumer, personal, family, or household purposes"; (b) "for any other non-professional, non-commercial, non-research purposes"; (c) "to develop or improve a product or service that competes with the Services" and "engage in competitive analysis or benchmarking". The exact lead-in sentence and the way (c) joins its two limbs were not captured and must be checked by the owner. Clause 18.7 fragments: "Any references to Nebius shall only be published ..."; "the fact and/or details of cooperation relating to this Agreement shall only be communicated"; "to third parties or the public with the prior written consent of Nebius"; "except where applicable law obligates to provide the relevant information." The summariser placed 18.7 under a Confidentiality heading.
- **Publicity (§18.7, §20.5):** public references to the cooperation need Nebius's prior written consent, and Nebius may use the customer's name/marks. **Action before public release:** confirm that the hackathon's rules/sponsor terms cover naming Nebius in the public repository and video, and whether publishing our own evaluation (hosted model vs matched random edits and a no-memory baseline) is "benchmarking" under §4.1.10(c). Both questions are in `docs/submission/NEBIUS_CLARIFICATION_REQUEST.md` (drafted, not sent). (R1/R2 timing figures describe our own simulator on a rented VM and make no comparison between providers.)

## 3. Other checks done (2026-10-14)
- No credentials or secret patterns in any reachable git object (all refs, 395 blobs: 0 matches of the real Nebius key's bytes, 0 of generic private-key/token patterns); `.env` is git-ignored and untracked; only `.env.example` is tracked.
- No tracked third-party binary assets (images, fonts, models, video); the robot model is generated by code; no external CDN/font URLs in the frontend.
- The local-only backup branch `backup/pre-trailer-rewrite` and the filter-branch backup ref `refs/original/...` (two old commits with AI co-author trailers; never pushed) were inspected on 2026-10-14: every commit's tree already exists in `main`'s history (no unique work), and both refs were deleted locally. No ref in the repository now reaches a commit with a co-author trailer. No remote branch was deleted and no registered history was rewritten.
- Copyright holder in `NOTICE`: Mahdi Nasser (confirmed by the owner 2026-10-14).

## 4. Open items before the public release
1. Owner read of the full NVIDIA Nemotron Open Model License PDF (Super) and the OpenMDW-1.1 text (Ultra) (sections 1c, 1d), and of the Nebius AUP and Service-Specific Terms. Super/Ultra model-card licences were verified 2026-10-16; Lightning was not reviewed.
2. Confirm sponsor/hackathon permission for public mention of Nebius (§18.7).
3. (done 2026-10-14) Local backup refs removed; re-run the trailer check before publishing.
4. Re-run `scripts/generate_third_party_notices.py` after any dependency change.
5. Written clarification from Nebius / the organizers on §18.7 (draft: `docs/submission/NEBIUS_CLARIFICATION_REQUEST.md`, not yet sent); until then public text stays factual, with no logos and no endorsement wording.
