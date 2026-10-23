# Experience learning P0.5: research materials (V2, `feature/experience-learning`)

**Status:** archival design material and an A0 cost model. **This is not an experimental harness, and nothing here has been
executed against Creature Forge physics.**

The current rules are in `docs/plans/EXPERIENCE_P05_PROTOCOL.md`. The handoff is `docs/EXPERIENCE_P05_HANDOFF.md`.

- **`design_archive/`:** archived copies (verify with `sha256sum -c SHA256SUMS`) of the P0.5 design documents, calculation
  scripts, outputs, unit tests and synthetic section-E results, as delivered by the 2026-10-22/23 Claude Code session.
  32 files are byte-identical to the source; 1 is sanitised for publication (`PROVENANCE.tsv` gives source and published
  sha256). The
  directory is marked `-text` in `.gitattributes`, so git does no EOL conversion.
  - Precedence: revision 1 → 2 → 2.1 → amendment 2.2 → erratum 2.2a.
  - The section-E results for G = 46 are absent: NOT COMPUTED.
  - `test_p05_amend22.py` line 11: a local absolute default path was replaced by a repository-relative default (B12,
    resolved). The unredacted copy is not published.
- **`a0_review/`:** the exact binomial operating characteristics of the P05-SV1 admission rule (protocol §5).
- **`a0_cost_model/`:** a fresh cost and precision model for the owner settings (B = 300, 8 train seeds, 3 instances per
  base, 28 confirmatory bases). It is read-only arithmetic using the archived formulas, and every number is [ASSUMP].
