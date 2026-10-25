# Post-run hash-index path portability

The original Linux analysis completed successfully and repeated byte-exactly
in its original VM environment. A Windows re-analysis then correctly refused
immutable publication because the source's string replacement matched two
backslashes rather than Windows' single separator in hash-index keys. No raw
record or original analysis was replaced.

Post-run engineering correction: `path.relative_to(root).as_posix()` normalizes
the manifest key spelling. No physical measurement, predictor, feature, target,
pairing, numerical statistic, bootstrap, seed, gate or record content changes.
The original source commit `f70549d` and its protocol hashes remain preserved;
the measurement archive retains the unmodified Linux analysis. The current
analysis utility includes only this formatting fix, with a Windows/POSIX path
regression test. The local exact replay remains a **failed byte-exact check**:
Python 3.11 and the registered Python 3.12 also differ in float summation.
Captured local output identifies last-bit floating differences; identities,
hashes, counts and choices match. A separate verification receipt records the
maximum difference. The original analysis is not replaced or relabeled exact.

[Python 3.12 changed the built-in float summation algorithm](https://docs.python.org/3.12/library/functions.html#sum).
Use the registered Python 3.12 VM environment for byte-identical re-analysis;
this already passed before retrieval. No numerical calculation or scientific
threshold was changed to force local equality or a positive gate. The formatting
fix only makes the hash-index keys portable.
