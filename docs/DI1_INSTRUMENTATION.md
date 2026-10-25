# DI-1 instrumentation v1

Observation-only, per-instance reversible hooks around original Episode and
HDBWorkbench methods; original implementation is called exactly once. No new
physics or hypothesis calls. The delegated pool preserves candidate/job order
and results. `fault_bench.apply_changes` is temporarily wrapped in the single
investigation process to retain attempted edits, legal vectors and rejection
reasons. CMA population jobs retain every evaluated intermediate candidate.

Exclusive-created JSONL journal: logical sequence, nested operation scopes,
previous-record hash and SHA256; flush+fsync before the next delegated operation.
Every simulation batch's exact designs/seeds/duration/conditions is persisted
before jobs begin; every result follows its matching batch. Calls retain twin
deviations, ensemble inputs, predictions and uncertainty, particle caches,
complete ranked diagnostic candidate sets, selection and available observations,
posterior/weights and budget remaining. Hidden plant objects are redacted from
all trace dictionaries and are held only in trusted evaluation records.

Existing assimilation forecasts that occur after an observation remain labelled
by actual temporal sequence: they are not claimed to be prospective forecasts.
The first decision panel is explicitly frozen after ranking, before its plant
probe. The initial observation cannot have an inferred retrospective forecast.
Unavailable/refused predictions remain unavailable. No synthetic verdicts.

Acceptance: hash-chain/provenance/redaction/immutability/limits guards, and exact
scientific equality of complete uninstrumented versus instrumented baseline on
each eligible pilot base, including diagnosis, search outputs, selected vector,
budget ledger, validation and confirmation. Exclude only wall-clock fields from
equality. Alternative paths run only after the baseline equality passes.

The local control process is single-threaded; process workers run unchanged
module-level simulator functions. Each parallel base has its own journal and
separate process. Hooks are restored even on failure. No release API changes.

Before physics: the Windows working-copy manifest retains CRLF hashes for four inherited files. pilot_git_blob_hashes.json additionally freezes committed LF bytes for Linux verification. This transport-only amendment changes no source, seeds, policy or analysis.
