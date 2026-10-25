# R0: coordinated repair capability, development pilot

Date: 2026-10-25. Dedicated branch `codex/repair-strategy-r0`, based on
`0828cbd0ea556fb31630e275b444b0197671185e`. This is a development capability
experiment, not a Nemotron, experience-learning or confirmatory result.

## Authority and protected scope

The owner authorized implementation, tests, development-only Nebius execution,
analysis, archiving, research-branch commits/push and a separated Notion update.
Additional infrastructure <= $35; aggregate paid campaign runtime <= 10 hours;
available credit is an independent ceiling. No inference, credit purchase, new
IAM, E-2R/HF2, release changes, PR #20 changes, test/reserve data or merges.
Basic Memory tools are not exposed; tracked records are the fallback.

## Hypothesis and interpretation

Simultaneous optimization of multiple existing repair parameter groups may
recover development robots that competent single-group and sequential searches
cannot recover at equal physical budgets. Better objective alignment is a
separate factor. Capability is a prerequisite for later strategy learning, not
evidence of learning itself. Failure at this finite budget is not physical
impossibility; success in this small selected development cohort is not transfer.

## Inputs and sampling (no R0 outcomes used)

`scripts/r0_experiment.py prepare` checks exact SHA-256 values for the complete
RL-1 dev response matrix (211 instances, 18 bases, 9 dev families, 2,110 cells),
the named `fresh_A1c5.jsonl` dev records and `thresholds_dev.json`. It never calls
`load_bases`, opens walker archives, imports testbench/held-out definitions or
uses a broad artifact glob. The nominal body/vector is taken from design 0 of
each verified A1 record, checked for equality across records of each base.

Failed cohort: zero historically FULL tools at the RL-1 budget; select 12 cases
on distinct bases. Controls: at least one historically FULL tool; select 6 cases
on the remaining distinct bases. At each step choose the eligible case with the
least represented family, tie-breaking by SHA-256 of
`r0-sample-v1:<instance_id>`. No quota substitution if sampling fails. The exact
18 cases are in `cases.json`, pinned by `protocol.json`. Historical outcomes are
used only for sampling, never policy decisions. These outcomes condition the
estimand and make fresh matched restricted controls essential.

One disjoint instance selected by the hash `r0-smoke-v1:<instance_id>` is an
engineering smoke, excluded from the 18-case study. No tuning on smoke recovery
results: only correctness, physics equivalence, failures and throughput may
determine launch. Any scientific change requires a new version before main
outcomes; invalidated records are preserved.

## Six conditions and physical constraints

Actions crossed with objectives `frozen` and `do1`:

1. **single:** all ten existing tool groups, each from nominal design.
2. **sequential:** eight predeclared two-tool programs; optimize the first group,
   then optimize the second from that first-stage result, retaining intermediates.
3. **joint:** simultaneously optimize the union of each corresponding pair from
   nominal design.

The sequential arm tests the existing chained-search capability through a
standardized plant-only portfolio, not a bit-identical replay of the entire
diagnosis/twin/early-stopping engine. There is no twin or privileged diagnosis in
any arm. This qualification must accompany every comparison with the engine.

Pair library (identical in sequential and joint):

| Groups | Physical motivation, not a prediction of success |
|---|---|
| timing + feedback | controller time scale and closed-loop stabilization |
| posture + placement | torso reference and foot support geometry |
| timing + stride | gait frequency, phase, and swing amplitude |
| foot_length + placement | support geometry and placement response |
| torso_mass + feedback | inertia/load and stabilization gains |
| leg_length + timing | limb geometry and gait time scale |
| foot_friction + stride | traction and commanded swing/propulsion |
| torque_limit + timing | actuation capacity and movement time scale |

Groups partition their control/body coordinates. Every coordinate touched in a
sequential program is searched once; global bounds are additionally checked on
every measured candidate and final submission. Guided absolute bounds and the
existing HDB [0.25, 4] body ratio are anchored to the original nominal robot.
No new controller law, fault removal, changed plant, environment edit or relaxed
verifier is allowed. The simulator's coordinate encoding is reused unchanged.
Body changes are simulated redesigns, not evidence of hardware field repair.

DO-1 is the byte-exact existing `scripts/do1_objective.py` from
`experiment/do1-objective`, Git blob `b27a01c62fa82632d596e1c4481051c0b0861aaf`,
SHA-256 `7391890cb9491b73000a1b034e78399d0f6d93b789ca043728b5f2132ed669af`.
It is reused here because the research base lacks that module; it is not
reimplemented or modified. The frozen objective uses `hidden_plant.make_eval_fn`.
DO-1 uses its original evaluator and objective, including lexicographic walking,
survival, paired displacement and gate-margin priorities. All physical calls use
the existing hidden-plant path, no approximate or invented trajectories.

## Budget, candidate selection and seeds

There are 3 optimizer replicates per condition: 18 x 6 x 3 = **324 units**.
Each consumes exactly **3,000 policy rollouts**, including selection:

- Faulty train baseline: 4 rollouts, charged in both objectives.
- Faulty selection baseline: 8 rollouts, charged in both objectives.
- Remaining search allocation: 2,972 rollouts, equally divided across 10 singleton
  programs or 8 sequential/joint programs; sequential splits each program's cap
  between its two stages. Each allocation must meet the unchanged minimum of
  an initial point plus three CMA generations.
- CMA generation-rounding tails are spent on seeded admissible uniform random
  candidates within the same action condition. Sequential tails edit just one
  group from a recorded chain start, never a joint space. No zero-cost evaluations,
  artificial charges or outcome-dependent budget increases are permitted.
- Select the best two distinct returned CMA/tail candidates by the objective's
  train score. Evaluate each on 8 disjoint selection seeds (16 rollouts total),
  then submit the highest selection score, with deterministic earliest tie-break.
  There is no early stopping or verifier-driven candidate choice. If only one
  distinct candidate exists, measure it twice and charge both measurements.

An exact equal rollout count addresses additional-search confounding. Search
dimensionality, portfolio size, initialization overhead and candidate count still
differ intentionally and are reported. These differences limit claims about a
pure mathematical action-space effect separated from search allocation.

Seeds are the first 32 SHA-256 bits of
`r0-dev-v1:<instance_id>:<role>:<index>`, with roles train=4, select=8,
validate=24, confirm=24. Collisions across roles and with historical seed roles
fail preparation. Physical seed sets are matched across arms and optimizer
replicates. Replicates change optimizer randomness only and are technical
replicates, never additional independent robots.

The policy receives only opaque robot id, nominal design and train/select seeds.
A trusted evaluator closes over the private plant and returns measured scores.
It does not expose family, severity, historical outcomes, hidden parameters,
validation/confirmation seeds or outcomes. Verification occurs only after solve
returns a submitted design. All per-seed verification rows are retained.

## Independent endpoint and frozen analysis

Use unchanged `hidden_plant.verify` -> `recovery.assess` / `full_recovery_v1`.
Validation costs 48 10-second rollouts; successful validation additionally invokes
24 20-second confirmations (48 equivalents). These are outside the policy cap
but included in compute/cost totals, identical rules for every condition.

Report all six FULL/PARTIAL/NOT/ERROR counts, failed/control cohorts, validation
walking fractions, policy/verification rollouts, times, errors and per-case
replicate counts. Primary descriptive contrast: joint/do1 minus sequential/do1
on the 12 historically failed bases. Also report joint versus single under each
objective and objective effects within each action condition.

Average the three replicate outcomes within each base. Descriptive 95% intervals
resample the 12 bases with replacement (10,000 replicates, seed 2026102507).
Exploratory two-sided sign-flip probabilities enumerate base-level contrasts.
There are no confirmatory claims and no uncorrected subgroup declarations.
All predeclared comparisons appear regardless of outcome. An incomplete set has
no full-study analysis; missing/invalid units are enumerated, never silently
excluded or counted as completed comparisons.

**Development advancement gate (all clauses required):**

- A repeatable rescue is a failed-cohort base where joint/do1 verifies on >=2/3
  optimizer replicates, and both single/do1 and sequential/do1 verify on <=1/3.
- >=3 rescued bases, spanning >=2 development families.
- Across the 12 failed bases, the sum of joint/do1 FULL counts minus the per-base
  maximum of the two restricted/do1 FULL counts is >=3.
- No material control regression: joint/do1 <=1/3 when either restricted/do1 >=2/3.
- All 324 records complete and valid; no verification ERROR.

The per-base best restricted comparator is a deliberately conservative
hindsight reference for advancement, not a deployable baseline policy. Passing
permits R1 design only, not a paid R1 campaign or test unsealing. If the same joint
procedure works generally, report a generic optimizer improvement rather than
assuming a conditional strategy-learning problem exists.

## Engineering gates, recovery and provenance

Before any paid launch: current credit and pricing verified, both VM states read
from the API, sufficient resources, reusable environment checked, working
instance-scoped SA authentication, VM-side deadline API stop and laptop watchdog
checked. Before the full study, exercise VM-side SA stop end to end and verify
STOPPED through the control plane. A guest poweroff is not a stop.

Freeze source, case and protocol hashes before main outcomes. Code hashes use LF
normalization only for source portability; evidence hashes use exact bytes.
Each atomic unit includes commit, protocol/source hashes, environment fingerprint,
conditions, seeds, optimizer settings, budgets, selected design, full verification
and timings. Successful checkpoint reuse requires full identity, schema,
constraint, seed and ledger validation. No unfavorable successful unit is rerun.
Missing checkpoints may resume with identical frozen inputs; process/infrastructure
failures retain their logs. Algorithm/physics/schema errors stop the campaign.
Any invalidating bug requires preserved invalid evidence, a documented versioned
amendment, and a clearly new exploratory run; no automatic selective retry.

Engineering smoke uses the excluded instance, all six conditions, replicate 0,
2,000 policy rollouts. Serial and pooled scientific outputs must match exactly
(wall-clock fields excluded). Single-thread BLAS/OMP prevents hidden nested
parallelism. No alternative physics implementation is introduced.

The batch VM has 64 vCPU / 256 GiB. A proposed 8 deterministic shards x 6
existing-size workers = 48 independent serial unit processes uses the authorized
batch capacity without nested MuJoCo pools. This is batch scheduling, not agents
or a changed optimizer. Main-VM six-worker guidance is preserved per shard; the
8-vCPU main VM stays stopped. Worker count/shards may change for scheduling only,
subject to exact output equivalence and fixed unit identities.

Use measured smoke worker-hours, actual batch utilization and current price for
launch estimates. Do not launch if projected total plus 25% margin and already
incurred runtime/spend cannot fit available credit, $35 and 10 paid hours. No
silent sample reduction. Normal completion runs frozen analysis and archives
checksums, then invokes API self-stop. Fatal failure or timeout also finalizes
available evidence and requests API stop; VM-side systemd timer is independent
of laptop and user login. Verify STOPPED after every stop. No blind extension.

## Known inherited limitation

At the starting research commit, the global frozen manifest omits 42 E-1 paths;
its stored-blob checks pass and E-1's separate archive checks were verified. The
owner reports the rc2 checkout fixes this. R0 does not regenerate that manifest
or modify release files. New R0 evidence has its own SHA-256 manifest.
