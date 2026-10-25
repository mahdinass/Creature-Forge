# G0 exact-design deduplication

Before restarting measurement, the stalled publisher's cause was identified:
866 saved design-index/check entries have only 808 distinct predictor inputs
(804 distinct physical designs after merging 8/16-seed prefix checks). Identical
physical designs can have different pipeline indices. The old driver used a
physical-input hash as the checkpoint id, but submitted duplicate jobs; their
different wall times caused immutable publication to reject the second result.
The old executor then waited for queued jobs, explaining busy workers with no
new published records. Preserve the interrupted archive and its 17 records.

Correct the audit unit, not the evidence: collapse identical designs within the
same episode/model/conditions, require equal counts for equal seed sets and
compatible counts for nested 8/16 checks, retain the largest measured seed set,
retain all design indices, and carry the original-submission verifier label
only across exact same-design identity. Reject conflicts. This avoids inflating
independent evidence and duplicate checkpoint publication. Hypotheses, seeds,
physics, candidate universe and original outcomes remain unchanged; no learner
or prospective evaluation outcome was inspected or selected.

Original inventory/protocol/input hashes remain preserved. The corrected
inventory records both log-entry and unique-intervention counts. Uniformly
measure every corrected unique intervention in a fresh output, without choosing
favorable rows. Identity/deduplication/conflict regression tests are required.
