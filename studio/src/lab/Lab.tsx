import { useCallback, useEffect, useMemo, useState } from 'react'
import { getLabReplay, getLabTrial, getLabTrials } from '../api'
import { usePlayback } from '../store'
import { Notice, OriginBadge, StatusChip } from './Badges'
import {
  filterRows, formatWhen, pct, STEP_TITLE, STEPS, statusInfo, stepState, type Step,
} from './labLogic'
import type { LabRow, LabView } from './labTypes'
import {
  CompareStep, HypothesizeStep, InterveneStep, ObserveStep, VerifyStep, type ReplayControls, type ReplayState,
} from './Steps'

type Filter = 'all' | 'accepted' | 'rejected' | 'invalid'
const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'accepted', label: 'Accepted' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'invalid', label: 'Invalid / failed' },
]

export function Lab({ initialTrial, initialStep }: { initialTrial: string | null; initialStep: Step | null }) {
  const [rows, setRows] = useState<LabRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(initialTrial)
  const [filter, setFilter] = useState<Filter>('all')

  const load = useCallback(() => {
    setError(null)
    setRows(null)
    getLabTrials().then(setRows).catch((e: Error) => setError(e.message))
  }, [])
  useEffect(load, [load])

  const shown = useMemo(() => (rows ? filterRows(rows, filter) : []), [rows, filter])

  return (
    <main className="lab" data-testid="lab">
      <aside className="lab-list" aria-label="Experiment history">
        <h3>Experiments</h3>
        <div className="filters" role="group" aria-label="filter by outcome">
          {FILTERS.map((f) => (
            <button key={f.id} className={filter === f.id ? 'on' : ''} onClick={() => setFilter(f.id)}>{f.label}</button>
          ))}
        </div>
        {error && (
          <Notice tone="bad" testid="list-error">
            Could not load the experiment history: {error}{' '}
            <button className="link" onClick={load}>Try again</button>
          </Notice>
        )}
        {!error && rows === null && <p className="dim">Loading saved experiments…</p>}
        {rows && rows.length === 0 && (
          <Notice testid="list-empty">
            No saved investigations yet. Run <code>scripts/run_investigation.py</code> to create one; bundled demo records
            appear here automatically.
          </Notice>
        )}
        {rows && rows.length > 0 && shown.length === 0 && <p className="dim">No experiments match this filter.</p>}
        <ul>
          {shown.map((r) => <TrialCard key={r.trial_id} row={r} active={r.trial_id === selected} onSelect={() => setSelected(r.trial_id)} />)}
        </ul>
        <small className="ref-note">
          The 16 cm foot in the <b>Compare (Phase 0)</b> tab is a human-authored reference design. It is not an AI result and
          is not one of these experiments.
        </small>
      </aside>

      <section className="lab-detail">
        {selected ? <TrialDetail key={selected} id={selected} initialStep={selected === initialTrial ? initialStep : null} />
          : <EmptyDetail total={rows?.length ?? null} />}
      </section>
    </main>
  )
}

function EmptyDetail({ total }: { total: number | null }) {
  return (
    <div className="lab-empty" data-testid="lab-empty">
      <h2>Pick an experiment</h2>
      <p>
        Each record follows one investigation from the original failure to MuJoCo’s verdict:
        {' '}<b>Observe → Hypothesize → Intervene → Verify → Compare</b>.
      </p>
      <ul className="legend">
        <li><OriginBadge kind="measured" /> numbers MuJoCo produced; solid outline</li>
        <li><OriginBadge kind="model" /> what the language model wrote; dashed outline</li>
        <li><OriginBadge kind="confidence" /> how sure the model said it was</li>
      </ul>
      {total === 0 && <p className="dim">There is nothing to show yet.</p>}
    </div>
  )
}

function TrialCard({ row, active, onSelect }: { row: LabRow; active: boolean; onSelect: () => void }) {
  const info = statusInfo(row.status)
  return (
    <li>
      <button className={`trial-card tone-border-${info.tone} ${active ? 'on' : ''}`} onClick={onSelect}
        data-testid={`trial-${row.trial_id}`} aria-pressed={active}>
        <span className="tc-top">
          <StatusChip status={row.status} />
          <span className="dim">{row.source === 'bundled-demo' ? 'demo record' : 'local'}</span>
        </span>
        <b className="tc-title">{row.label ?? 'Unlabelled investigation'} <span className="dim">{row.variant ? `· ${row.variant} evidence` : ''}</span></b>
        {!row.readable && <span className="dim">{row.error}</span>}
        {row.parameter != null && (
          <span className="tc-line">Proposed <code>{row.parameter}</code> → {row.value}</span>
        )}
        {row.fall_rate && row.fall_rate.baseline != null && (
          <span className="tc-line">Fall rate {pct(row.fall_rate.baseline)} → {pct(row.fall_rate.candidate)}</span>
        )}
        {row.parameter == null && row.readable && <span className="tc-line dim">{statusInfo(row.status).summary}</span>}
        <span className="dim tc-when">{formatWhen(row.created_utc)}</span>
      </button>
    </li>
  )
}

/* ------------------------------------------------------------------ detail */

function TrialDetail({ id, initialStep }: { id: string; initialStep: Step | null }) {
  const [view, setView] = useState<LabView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState<Step>(initialStep ?? 'observe')
  const [seed, setSeed] = useState(0)
  const [replay, setReplay] = useState<ReplayState>({ status: 'idle' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let live = true
    setView(null)
    setError(null)
    getLabTrial(id)
      .then((v) => {
        if (!live) return
        setView(v)
        setSeed(v.replay.seeds[0] ?? 0)
      })
      .catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [id, attempt])

  const runReplay = useCallback(() => {
    setReplay({ status: 'loading', seed })
    getLabReplay(id, seed)
      .then((data) => {
        setReplay({ status: 'ready', data })
        usePlayback.getState().setDuration(data.baseline.duration)
        usePlayback.getState().seek(0)
      })
      .catch((e: Error) => setReplay({ status: 'error', message: e.message, seed }))
  }, [id, seed])

  // a different seed invalidates the loaded replay instead of silently showing the wrong one
  const onSeed = (s: number) => {
    setSeed(s)
    if (replay.status !== 'loading') setReplay({ status: 'idle' })
  }

  if (error)
    return (
      <Notice tone="bad" testid="detail-error">
        {error.includes('no such') ? 'This record no longer exists.' : `Could not open this record: ${error}`}{' '}
        <button className="link" onClick={() => setAttempt((a) => a + 1)}>Try again</button>
      </Notice>
    )
  if (!view) return <p className="dim" data-testid="detail-loading">Opening record…</p>

  const info = statusInfo(view.outcome.status)
  const ctl: ReplayControls = { state: replay, seeds: view.replay.seeds, seed, onSeed, onLoad: runReplay }
  const st = stepState(view, step)

  return (
    <article className="detail" data-testid="detail" data-trial={view.trial_id}>
      <header className="detail-head">
        <div>
          <h2>{view.label ?? 'Unlabelled investigation'} <span className="dim">· {view.variant} evidence</span></h2>
          <p className="dim">
            <code>{view.trial_id}</code> · {formatWhen(view.created_utc)} · {view.source === 'bundled-demo' ? 'bundled demo record' : 'local record'}
            {view.integrity && (view.integrity.verified ? ' · hash verified' : ' · HASH MISMATCH')}
          </p>
        </div>
        <StatusChip status={view.outcome.status} />
      </header>

      <p className={`headline tone-${info.tone}`} data-testid="headline">{info.summary}</p>
      {view.integrity && !view.integrity.verified && (
        <Notice tone="bad">This bundled record does not match its recorded SHA-256. Treat it as altered.</Notice>
      )}
      {view.degraded && <Notice tone="warn" testid="degraded">{view.degraded}. Showing what could be read.</Notice>}
      {view.missing.length > 0 && !view.degraded && (
        <Notice testid="missing"><b>Not in this record:</b> {view.missing.join(' · ')}</Notice>
      )}

      <nav className="stepper" aria-label="investigation steps">
        {STEPS.map((s, i) => {
          const ready = stepState(view, s).ready
          return (
            <button key={s} data-step={s} className={`${step === s ? 'on' : ''} ${ready ? '' : 'off'}`}
              onClick={() => setStep(s)} aria-current={step === s ? 'step' : undefined}>
              <span className="n">{i + 1}</span>{STEP_TITLE[s]}
            </button>
          )
        })}
      </nav>

      <div className="step" data-testid={`step-${step}`}>
        {step === 'observe' && st.ready && <ObserveStep view={view} ctl={ctl} />}
        {step === 'hypothesize' && st.ready && <HypothesizeStep view={view} />}
        {step === 'intervene' && st.ready && <InterveneStep view={view} />}
        {step === 'verify' && st.ready && <VerifyStep view={view} />}
        {step === 'compare' && st.ready && <CompareStep view={view} ctl={ctl} />}
        {!st.ready && <Unavailable view={view} step={step} reason={st.reason ?? ''} />}
      </div>

      <footer className="step-nav">
        <button disabled={step === STEPS[0]} onClick={() => setStep(STEPS[STEPS.indexOf(step) - 1])}>← Back</button>
        <button disabled={step === STEPS[STEPS.length - 1]} onClick={() => setStep(STEPS[STEPS.indexOf(step) + 1])}>Next →</button>
        {view.model_call?.usage && (
          <small className="dim">
            {view.model_call.model} · {view.model_call.usage.total_tokens} tokens · {view.model_call.latency_s?.toFixed(1)} s ·
            {' '}{view.mode === 'live' ? 'live Nebius call' : view.mode}
          </small>
        )}
      </footer>
    </article>
  )
}

function Unavailable({ view, step, reason }: { view: LabView; step: Step; reason: string }) {
  const raw = step === 'hypothesize' ? view.raw_model_reply : null
  return (
    <div className="step-body" data-testid="step-unavailable">
      <Notice tone="warn">
        <b>{STEP_TITLE[step]} is not available.</b> {reason}
        {view.outcome.reason && <> Recorded reason: <code>{view.outcome.reason}</code></>}
      </Notice>
      {raw && (
        <section className="block block-model" data-testid="raw-reply">
          <header><h4>What the model actually replied</h4><OriginBadge kind="model" /></header>
          <pre>{raw.text}</pre>
          <small>{raw.note}{raw.truncated ? ' Shown truncated.' : ''} It was never tested in MuJoCo, so it says nothing about whether the idea works.</small>
        </section>
      )}
    </div>
  )
}

