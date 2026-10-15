import { useEffect, useMemo, useState } from 'react'
import { cancelForgeJob, getForgeReplay, getForgeRun } from '../api'
import { Metrics } from '../Metrics'
import { usePlayback } from '../store'
import { HeightChart, Transport } from '../Timeline'
import type { RunPayload } from '../types'
import { Viewport } from '../Viewport'
import {
  controllerNote, countOutcomes, defaultSeed, fmtScore, isTerminal, jobFailureMessage, KIND_INFO, median, outcomeInfo, phaseText, progressFraction,
  replayChoices, runHeadline, seedReason, shortSeed,
} from './forgeLogic'
import type { ChallengeRun, SeedResult } from './forgeTypes'
import { ReplayBoundary } from './ReplayBoundary'
import { useJobPoll } from './useJobPoll'

export function OutcomeBadge({ outcome, testid = 'run-outcome' }: { outcome: string; testid?: string }) {
  const o = outcomeInfo(outcome)
  return <span className={`fg-badge fg-badge-${o.tone}`} data-testid={testid} data-outcome={outcome}>{o.label}</span>
}

function SeedReplay({ run, seed }: { run: ChallengeRun; seed: SeedResult }) {
  const choices = useMemo(() => replayChoices(run, seed), [run, seed])
  const [choiceKey, setChoiceKey] = useState(choices[0].key)
  const [replay, setReplay] = useState<RunPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => setChoiceKey(choices[0].key), [choices])
  const choice = choices.find((c) => c.key === choiceKey) ?? choices[0]
  const canReplay = seed.outcome !== 'ERROR'
  useEffect(() => {
    if (!canReplay) return
    let alive = true
    setReplay(null)
    setError(null)
    getForgeReplay({ runId: run.run_id, seed: seed.seed, direction: choice.direction, force: choice.force })
      .then((r) => {
        if (!alive) return
        setReplay(r)
        usePlayback.getState().setDuration(r.duration)
        usePlayback.getState().restart()
      })
      .catch((e: Error) => alive && setError(e.message))
    return () => { alive = false }
  }, [run.run_id, seed.seed, choice.direction, choice.force, canReplay])

  if (!canReplay) return <div className="fg-note-box" data-testid="replay-none">This seed could not run, so there is nothing to replay. {seed.error}</div>
  return (
    <div className="fg-replay" data-testid="replay">
      {choices.length > 1 && (
        <label className="fg-field fg-inline">
          <span>Replay</span>
          <select value={choice.key} onChange={(e) => setChoiceKey(e.target.value)} data-testid="replay-choice" aria-label="replay variant">
            {choices.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
        </label>
      )}
      {error && <div className="error" role="alert" data-testid="replay-error">Replay failed: {error}</div>}
      {!replay && !error && <div className="fg-skeleton skeleton" data-testid="replay-loading" />}
      {replay && (
        <ReplayBoundary resetKey={`${run.run_id}-${seed.seed}-${choice.key}`}>
          <Viewport closeup run={replay} label={`Seed ${seed.seed} · fresh MuJoCo replay`} />
          <Transport runs={[{ run: replay, label: 'replay', color: '#3cc9d6' }]} />
          <div className="below">
            <HeightChart runs={[{ run: replay, label: 'replay', color: '#3cc9d6' }]} />
            {replay.metrics && <Metrics run={replay} label="Measured in this replay" />}
          </div>
        </ReplayBoundary>
      )}
    </div>
  )
}

function RunResult({ run }: { run: ChallengeRun }) {
  const kind = run.spec.kind
  const [seedId, setSeedId] = useState<number | null>(() => defaultSeed(run))
  useEffect(() => setSeedId(defaultSeed(run)), [run])
  const sel = run.per_seed.find((s) => s.seed === seedId) ?? null
  const counts = countOutcomes(run.per_seed)
  const scores = run.per_seed.filter((s) => s.outcome !== 'ERROR').map((s) => s.score)
  const info = outcomeInfo(run.outcome)
  const note = controllerNote(run)
  return (
    <div className="fg-result" data-testid="run-result" data-kind={kind}>
      <div className={`fg-verdict fg-verdict-${info.tone}`}>
        <OutcomeBadge outcome={run.outcome} />
        <div>
          <p className="fg-headline" data-testid="run-headline">{runHeadline(run)}</p>
          <p className="fg-dim">{info.text} {KIND_INFO[kind].scoreMeaning}</p>
        </div>
      </div>
      {run.outcome === 'ERROR' && (
        <div className="error" role="alert" data-testid="run-error-seeds">
          {run.per_seed.filter((s) => s.outcome === 'ERROR').slice(0, 3).map((s) => <div key={s.seed}>Seed {s.seed}: {s.error ?? 'no message'}</div>)}
        </div>
      )}
      <div className="fg-facts">
        <div><span>{counts.PASS}</span>pass</div>
        <div><span>{counts.POOR}</span>poor</div>
        <div><span>{counts.FAIL}</span>fail</div>
        {counts.ERROR > 0 && <div><span>{counts.ERROR}</span>error</div>}
        <div><span>{fmtScore(kind, median(scores))}</span>median score</div>
        {run.rollouts !== undefined && <div><span>{run.rollouts}</span>rollouts</div>}
        {run.wall_s !== undefined && <div><span>{run.wall_s.toFixed(1)} s</span>wall time</div>}
      </div>
      {note && <p className="fg-dim" data-testid="controller-note">{note}</p>}

      <h3>Seeds <small className="fg-dim">click one to replay it</small></h3>
      <div className="fg-strip" role="listbox" aria-label="seeds" data-testid="seed-strip">
        {run.per_seed.map((s) => (
          <button key={s.seed} role="option" aria-selected={s.seed === seedId} className={`fg-seed fg-seed-${outcomeInfo(s.outcome).tone} ${s.seed === seedId ? 'on' : ''}`}
            data-testid="seed-btn" data-outcome={s.outcome} title={`seed ${s.seed}: ${s.outcome}, ${fmtScore(kind, s.score)}`} onClick={() => setSeedId(s.seed)}>
            <b>{s.outcome}</b><span>{shortSeed(s.seed)}</span><small>{s.outcome === 'ERROR' ? 'no score' : fmtScore(kind, s.score)}</small>
          </button>
        ))}
      </div>
      {sel && <p className="fg-seedline" data-testid="seed-reason"><b>Seed {sel.seed}:</b> {seedReason(kind, sel)}</p>}
      {sel && <SeedReplay run={run} seed={sel} />}

      <details className="fg-details">
        <summary>Every seed in detail</summary>
        <div className="table-scroll">
          <table>
            <thead><tr><td>seed</td><td>outcome</td><td>score</td><td>what happened</td><td>rollouts</td></tr></thead>
            <tbody>
              {run.per_seed.map((s) => (
                <tr key={s.seed}><td>{s.seed}</td><td>{s.outcome}</td><td>{s.outcome === 'ERROR' ? 'n/a' : fmtScore(kind, s.score)}</td><td className="fg-left">{seedReason(kind, s)}</td><td>{s.rollouts}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

/** Live progress of a challenge job, then its stored result. A job that failed is shown as an ERROR with the real message. */
export function RunView({ jobId, runId, onRun }: { jobId: string | null; runId: string | null; onRun: (r: ChallengeRun | null) => void }) {
  const poll = useJobPoll(jobId)
  const [run, setRun] = useState<ChallengeRun | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const status = poll.job?.status
  const ready = jobId ? status === 'done' : !!runId
  useEffect(() => {
    setRun(null)
    setLoadError(null)
    onRun(null)
    if (!ready || !runId) return
    let alive = true
    getForgeRun(runId)
      .then((r) => { if (alive) { setRun(r); onRun(r) } })
      .catch((e: Error) => alive && setLoadError(e.message))
    return () => { alive = false }
  }, [ready, runId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!jobId && !runId) {
    return <div className="fg-empty" data-testid="run-empty"><b>No run yet</b><span>Pick a challenge and press run. The result and a real replay appear here.</span></div>
  }
  const fraction = progressFraction(poll.job)
  const active = jobId && !isTerminal(status)
  return (
    <section className="fg-card fg-run" data-testid="run-view" aria-live="polite">
      {active && (
        <div className="fg-progress" data-testid="run-progress">
          <div className="fg-progress-head"><b>Running in MuJoCo</b><span data-testid="run-phase">{phaseText(poll.job, poll.events)}</span></div>
          <div className="fg-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={fraction === null ? undefined : Math.round(fraction * 100)}>
            <i style={{ width: `${(fraction ?? 0.04) * 100}%` }} className={fraction === null ? 'indeterminate' : ''} />
          </div>
          {poll.error && <small className="fg-bad" data-testid="poll-error">Cannot reach the server for progress: {poll.error}</small>}
          {jobId && <button className="btn btn-ghost fg-small" onClick={() => void cancelForgeJob(jobId).catch(() => undefined)}>Cancel run</button>}
        </div>
      )}
      {jobId && (status === 'failed' || status === 'cancelled') && (
        <div className="fg-failed" role="alert" data-testid="run-failed" data-job-status={status}>
          <div className="fg-verdict fg-verdict-error"><OutcomeBadge outcome="ERROR" testid="run-outcome" /><div>
            <p className="fg-headline">{status === 'cancelled' ? 'The run was cancelled.' : 'The run could not be carried out.'}</p>
            <p className="fg-dim">This is a failed run, not a result about your creature.</p></div></div>
          <pre data-testid="run-failed-message">{jobFailureMessage(poll.job, poll.events)}</pre>
        </div>
      )}
      {loadError && <div className="error" role="alert" data-testid="run-load-error">Could not load the result: {loadError}</div>}
      {ready && !run && !loadError && <div className="fg-skeleton skeleton" />}
      {run && <RunResult run={run} />}
    </section>
  )
}
