# R0 reproduction and launch handoff

Read `REPORT.md`, `protocol.json` and `docs/R0_REPAIRABILITY_PROTOCOL.md` first.
The owner already authorized bounded R0 execution. Current account credit is the
blocking prerequisite. This directory contains a registration and engineering
evidence, with no physical results. Do not label it a completed experiment.

## Source and existing environments

Use the dedicated `codex/repair-strategy-r0` branch. Keep the execution commit
clean and unchanged throughout a campaign, including resume. Do not merge release
work, run test/reserve loaders, or use a wildcard over walker data. No environment
was created here. Windows validation reused:
`C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe`.

Before a VM launch, inspect existing remote Python environments, their executable
paths and installed versions. Reuse the verified existing environment, with
MuJoCo 3.15.0 and matching NumPy; do not invoke an environment-creating sync
command blindly. Use an isolated remote R0 checkout and output directory. Do not
copy credentials or touch other jobs/checkouts. No frontend build is needed.

## Independent launch prerequisites

1. Record current available **Cloud** credit, source and verification epoch; the
   start wrapper accepts evidence at most one hour old. Verify current pricing.
2. Inspect both VM states with the service-account API. Main must stay STOPPED;
   do not take over a running batch instance. Check the existing watchdog.
3. Start only a bounded engineering interval. Verify CPU/RAM, reusable environment,
   existing root SA finisher, active timer, deadline and instance identity.
4. Exercise `prove-selfstop` and verify STOPPED through the control plane. This
   must use the VM's independent root SA, not a personal interactive token.
5. Restart within the original cumulative campaign envelope; set a bounded
   deadline. Run focused development physical regressions and the excluded
   engineering smoke under serial and pooled scheduling. Compare outputs exactly
   apart from recorded wall time. Preserve both outputs regardless of findings.
6. Use measured worker-hours and actual batch utilization to estimate the
   324-unit run. Add 25% margin and already-incurred engineering runtime/cost.
   It must fit available credit, $35 additional infrastructure and ten total
   campaign hours. Otherwise stop, archive the limitation, and preserve sample size.

## Existing cloud lifecycle wrapper (Windows)

The following uses the established operational state and existing SA tooling.
`PY` means the verified existing Python above; it is not a new environment.
`OPS` means `C:\Users\mbnas\.vscode\Creature-Forge\infra\nebius`.

```text
PY -B scripts/r0_nebius.py --ops-root OPS status
PY -B scripts/r0_nebius.py --ops-root OPS start --hours 1 --credit-evidence artifacts/r0_ops/credit.json
PY -B scripts/r0_nebius.py --ops-root OPS prove-selfstop
PY -B scripts/r0_nebius.py --ops-root OPS start --hours 1 --credit-evidence artifacts/r0_ops/credit.json
PY -B scripts/r0_nebius.py --ops-root OPS deadline --hours VERIFIED_FIT_HOURS
PY -B scripts/r0_nebius.py --ops-root OPS stop
```

The credit JSON has numeric `available_usd`, numeric `verified_epoch` and a
nonempty `source`. Supply observed values; do not fabricate an example balance.
The wrapper records campaign start, baseline spend and the independent credit
ceiling under ignored `artifacts/r0_ops/`. It refuses personal-login fallback,
over-cap starts and takeover of active instances. Deadline extension requires
this campaign's end-to-end self-stop proof. Existing ignored operational
state/ledger files change only through normal authorized cloud lifecycle calls.

## VM engineering commands (after prerequisites)

```bash
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export R0_PYTHON=/absolute/path/to/verified/existing/python
STUDY=experiments/causal_engineer/dev/repair_strategy_r0
"$R0_PYTHON" -B scripts/r0_experiment.py run --study "$STUDY" --out artifacts/r0_smoke_serial --smoke --workers 1
"$R0_PYTHON" -B scripts/r0_experiment.py run --study "$STUDY" --out artifacts/r0_smoke_pool --smoke --workers 6
"$R0_PYTHON" -B scripts/r0_integrity.py compare --left artifacts/r0_smoke_serial --right artifacts/r0_smoke_pool
"$R0_PYTHON" -B scripts/r0_experiment.py analyze --study "$STUDY" --out artifacts/r0_smoke_pool --smoke
```

The six smoke units use one excluded instance, replicate zero and 2,000 policy
rollouts each. They are not part of the registered outcome set. Main outcomes
must not be examined to tune scientific choices. Before main execution, preserve
the measured engineering evidence and fit decision without changing the frozen
study. A scientific change needs a distinct pre-outcome registration.

## Main campaign and finalization

After all launch gates pass, obtain the exact epoch installed by the existing
cloud wrapper in `/var/lib/forge/deadline`. Launch the supervisor detached using
the established remote session tooling, from the clean R0 checkout, with
`R0_PYTHON` exported. The deadline must include finalization margin.

```bash
bash scripts/r0_campaign.sh artifacts/r0_run EXACT_INSTALLED_DEADLINE_EPOCH
```

The supervisor runs eight shards, performs analysis and integrity checks only
when complete, archives partial evidence on failure, and invokes the existing
API self-stop. The independent five-minute root timer supplies the hard backstop.
Its local command fakes are tests, not proof of real SA permissions.

For an infrastructure interruption, preserve logs and inspect the cause; resume
missing units with the same commit/protocol/environment/output path and ordinary
driver commands. Completed units must validate and are not rerun. Any algorithm,
physics, schema or invalidating source bug requires preserved invalid records
and a documented new exploratory version, not an automatic selective retry.

After a campaign, confirm both VM states by API, copy the evidence archive and
checksum, verify archive hashes locally, report all six conditions, reconcile
provider charges and update Notion with the outcome. Do not extend beyond the
original campaign limits or launch paid R1 work.
