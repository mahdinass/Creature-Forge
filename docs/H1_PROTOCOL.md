# H1 bounded investigation — frozen Stage A

26 October 2026. Evidence baseline `e8d5fa6730ecf6d2db67021a9d3d0f08cce03310`.
Research branch `codex/h1-bounded-investigation`. This registration precedes all
new H1 counterfactual outcomes. Prior evidence remains unchanged.

## Question and scope

Do the R0 final two-candidate screens reject an already available exact repair
that would achieve `full_recovery_v1` on the original matched development panel?
This measures historical selection opportunity, not a new deployable selector,
the production A1 generator's regret, learning, transfer or Nemotron contribution.

Stage 0 was recovered from the previous VEL-2 worktree, copied without overwriting
the original and reproduced with standard-library-only scripts. All 330 input
hashes match; audit results match after changing only absolute root paths;
reconstruction and supplement are byte-exact. Independent review verified all
28 audit-manifest entries, 640 candidate hashes, 324 incumbent choices and 102
R0 scientific-source hashes. Original and repeated evidence remains in ignored
`artifacts/h1_stage0_20261026`, `h1_recovered_audit`, `h1_recovered_reconstruction`.

## Population and identity freeze

Exactly 324 screens, 18 historical development bases, 18 screens per base,
640 candidate/condition identities. The original 320 known identities remain
fixed. Measure all 320 missing identities (323 unselected screen slots), with no
outcome-based sampling, replacement, new optimization or approximation.
`experiments/causal_engineer/dev/h1/{candidates,pairs,known,protocol}.json` freeze
the actual designs, hidden evaluator-only plant, nominal comparator, original
validation/confirmation seeds and saved variation. IDs include instance, design,
seed panel and variation hashes. All 648 slots reconstruct exactly (623 saved
winners, 25 source-derived numerical tails). One alternative already has a label;
reuse it rather than obtain a new realization. No sealed E-1/reserve inputs.

## Measurement and analysis

Unchanged `hidden_plant.verify` invokes the authoritative MuJoCo full verifier:
24 paired 10-second original/candidate validation seeds; verified improvement
and >=80% validation walking; then, conditionally, 24 disjoint 20-second candidate
confirmation seeds with walking, median upright speed and body-contact checks.
No new training or model calls. Conditional unexecuted confirmation is missing.
Every result, error, warning, raw response array, time and cost is preserved.

Primary descriptive endpoint: count bases with selected non-FULL / alternative
FULL. Also report affected screens, reverse contrasts and bases, base-equal mean
oracle gain, requirement-specific observed and missing counts, rollout totals.
Each base contributes equally; 18 strategies/replicates are technical repeats.
The oracle gain is an upper bound on useful decisions, not attainable policy value.
Whole-base percentile bootstrap: 10,000 draws, seed 2026102611, descriptive95%.
Selection-enriched historical bases limit population interpretation.

## Registered advancement and stopping rules

Stage A advances to B only with all 320 valid new assessments, complete 324-pair
coverage, **at least three independent historical bases with a missed FULL** and
**at least 0.05 base-equal oracle FULL headroom**. This is an engineering/scientific
measurement threshold, not a significance claim. Complete data failing either
headroom threshold yields NO-GO for further H1 selector development under this
design. Missing outcomes, simulator errors, identity or audit failures yield
NOT EVALUABLE. Preserve errors and stop; no favorable selective rerun or imputed
physical failures. Native analysis repeat and independent per-seed audit must
both pass before accepting any gate result.

If justified, B must freeze two new disjoint matched development panels on the
entire 640-candidate cohort before obtaining them, analyze requirement-specific
reliability and ranking reversals, and check legal preverification controls.
Its dedicated protocol must be frozen before B outcomes. Three panels are a
preliminary reliability estimate. Do not train a learner solely to produce numbers.
C requires base-disjoint support, strong physical-only and sham-history controls;
D requires a sufficiently powered, independent prospective equal-budget study.
Insufficient support/power ends those directions as NOT EVALUABLE. No production
integration absent a separate passed registered gate; flag disabled by default
if a learning implementation is ever justified. No H3 launch.

## Operations and conservative forecast

Authorization: $25 additional Cloud, six paid batch hours, $0 Token Factory.
Owner verified current available Cloud balance **$21.04** in this chat. Current
API confirms main cpu-d3 8vCPU/32GiB and batch cpu-d3 64vCPU/256GiB, both STOPPED;
both existing boot disks are 50GiB NETWORK_SSD. No prior research executor found
in the host process inventory; remote absence also follows stopped compute.
Existing Windows independent watchdog is Ready. Existing instance-scoped service
account remains valid; native root API timer/finisher is reused and checked before
physics, along with native timeout and provider API shutdown validation.

Official pricing checked 26 October:
https://docs.nebius.com/compute/resources/pricing . CPU $0.015/vCPU-hour,
RAM $0.0045/GiB-hour; batch compute $2.112/hour; two existing disks accrue about
$0.00972/hour combined. Prices exclude applicable taxes; local quote ledger is
not a provider invoice or account balance. No new VM, disk, service or environment.

Stage A maximum 30,720 equivalents; prior conservative 0.118528 seconds/equivalent
for each of eight six-worker paths gives 0.1265 physics hours (Stage 0 used a
slightly higher conservative forecast 0.158h/$0.335). Reserve one initial paid
hour and ~$3.36 including 0.35-hour shutdown/retrieval allowance and $0.50 slack.
Stage B upper 122,880 equivalents forecasts 0.632h before overhead using the
Stage 0 conservative path scaling; allocate at most two hours subject to actual
Stage A throughput. No initiate-if-does-not-fit exception. Existing supervision,
engineering, retrieval and storage time count cumulatively. Retain $5 of current
credit as reserve; scoped guard uses the lower current-capacity budget and cuts
off at 5.5 elapsed hours from first start, stricter than six cumulative paid hours.
Stop on success/error through the API; guest shutdown is never billing proof.
Reconfirm BOTH VMs STOPPED after every window. Preserve disks and archives.

## Reproduction

`python scripts/h1_counterfactual.py prepare` reconstructs frozen inputs from the
copied raw R0 units and exact Stage 0 candidate reconstruction (no physics).
`python -m unittest discover -s tests -p test_h1.py -v` runs local/VM guards.
Native execution: `bash scripts/h1_native.sh` under existing forge user and
supervised systemd service, after source validation and deadline checks.
`python scripts/h1_counterfactual.py analyze --out <raw> --analysis-output <new.json>`
recomputes the descriptive decision without physics.
`python scripts/h1_audit.py --out <raw>` independently replays response verdicts,
confirmation, identities, accounting and gate without physics (existing VM env).
