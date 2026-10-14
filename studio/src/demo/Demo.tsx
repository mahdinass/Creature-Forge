import { useCallback, useEffect, useState } from 'react'
import { getDemoRun, getDemoRuns, getDemoStatus, startDemoRun } from '../api'
import { Block, Notice } from '../lab/Badges'
import { ReplayStep } from './Replay'
import { Story } from './Story'
import {
  bar, describeEdit, honestHeadline, KIND_INFO, lookupPath, predictionText, rowBadge, statusMessage, STEP_TITLE, STEPS, verdictText,
  type Step,
} from './demoLogic'
import type { DemoRow, DemoRun, DemoStatus, Kind } from './demoTypes'

function KindBanner({ kind, note }: { kind: Kind; note: string }) {
  const k = KIND_INFO[kind]
  return (
    <div className={`kind-banner kind-${kind}`} data-testid="kind-banner" data-kind={kind}>
      <b>{k.label}</b> <span>{note || k.text}</span>
    </div>
  )
}

export function Demo({ initialRun }: { initialRun: string | null }) {
  const [status, setStatus] = useState<DemoStatus | null>(null)
  const [rows, setRows] = useState<DemoRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(initialRun)
  const [busy, setBusy] = useState<string | null>(null)
  const [confirmLive, setConfirmLive] = useState(false)

  const load = useCallback(() => {
    setError(null)
    Promise.all([getDemoStatus(), getDemoRuns()])
      .then(([s, r]) => {
        setStatus(s)
        setRows(r)
        setSelected((cur) => cur ?? r.find((x) => x.kind === 'RECORDED_LIVE' && (x.n_valid_proposals ?? 0) > 0)?.run_id ?? r.find((x) => x.kind === 'RECORDED_LIVE')?.run_id ?? r[0]?.run_id ?? null)
      })
      .catch((e: Error) => setError(e.message))
  }, [])
  useEffect(load, [load])

  const start = async (mode: 'live' | 'mock') => {
    setBusy(mode)
    setError(null)
    try {
      const rec = await startDemoRun(mode, mode === 'live' && confirmLive)
      setSelected(rec.run_id)
      load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <main className="demo" data-testid="demo">
      <div className="banner">
        Observed MuJoCo failure → Nemotron proposal → bounded edit → MuJoCo verification → replay → measured verdict. Every number comes from
        MuJoCo; every sentence the model wrote is marked as the model’s and is never treated as a result. The model call is either{' '}
        <b>live</b> (made during the run), a <b>recording</b> of a real call, or a <b>scripted mock</b> — each is labelled on every screen.
      </div>
      <div className="demo-layout">
        <aside className="lab-list" aria-label="demo runs">
          <h3>Runs</h3>
          {error && <Notice tone="bad" testid="demo-error">{error} <button className="link" onClick={load}>Try again</button></Notice>}
          {!rows && !error && <p className="dim">Loading…</p>}
          <ul>
            {(rows ?? []).map((r) => (
              <li key={`${r.source}-${r.run_id}`}>
                <button className={`trial-card ${r.run_id === selected ? 'on' : ''}`} onClick={() => setSelected(r.run_id)} data-testid={`run-${r.run_id}`} data-source={r.source}
                  aria-pressed={r.run_id === selected}>
                  <span className="tc-top">
                    <span className={`kind-chip kind-${r.kind ?? 'none'}`}>{r.kind ? KIND_INFO[r.kind].label.replace(' — not a model', '') : rowBadge(r)}</span>
                    <span className="dim">{r.source === 'bundled-recording' ? 'bundled' : 'local'}</span>
                  </span>
                  <b className="tc-title">{r.label ?? r.run_id}</b>
                  <span className="tc-line">
                    {r.status !== 'ok' ? `model: ${r.status}` : r.n_valid_proposals ? `${r.n_valid_proposals} valid proposal(s)` : 'no valid proposal'}
                    {r.verdict ? ` · first: ${r.verdict.replace(/_/g, ' ')} (${(r.gain_seeds ?? 0) >= 0 ? '+' : ''}${r.gain_seeds})` : ''}
                  </span>
                  {r.hash_verified === false && <span className="dim">HASH MISMATCH</span>}
                </button>
              </li>
            ))}
          </ul>
          <div className="demo-actions">
            <h4>New run</h4>
            <button onClick={() => void start('mock')} disabled={busy !== null} data-testid="run-mock">
              {busy === 'mock' ? 'Running MuJoCo…' : 'Run scripted mock'}
            </button>
            <small>Scripted text, real physics; labelled SCRIPTED MOCK.</small>
            <button onClick={() => void start('live')} disabled={busy !== null || !status?.live_enabled || !confirmLive} data-testid="run-live">
              {busy === 'live' ? 'Calling Nemotron, then MuJoCo…' : 'Run live with Nemotron'}
            </button>
            <label className="dim">
              <input type="checkbox" checked={confirmLive} onChange={(e) => setConfirmLive(e.target.checked)} disabled={!status?.live_enabled} /> I understand this
              spends Nebius inference budget
            </label>
            {status && !status.live_enabled && (
              <small data-testid="live-disabled">Live mode is off on this server (needs a Nebius key and CREATURE_FORGE_ENABLE_LIVE=1). Recordings show real earlier calls.</small>
            )}
            {status && (
              <small>
                Shared budget: {status.combined_budget.requests_used}/{status.combined_budget.requests_cap} requests ·{' '}
                {status.combined_budget.tokens_used.toLocaleString()}/{status.combined_budget.tokens_cap.toLocaleString()} tokens
              </small>
            )}
            {busy && <small data-testid="busy-note">A run takes 1–4 minutes: the verification simulates 160 MuJoCo rollouts.</small>}
          </div>
        </aside>
        <section className="lab-detail">
          {selected ? <RunDetail key={selected} id={selected} status={status} /> : <p className="dim">Pick or start a run.</p>}
        </section>
      </div>
    </main>
  )
}


function RunDetail({ id, status }: { id: string; status: DemoStatus | null }) {
  const [run, setRun] = useState<DemoRun | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState<Step>('observe')
  const [view, setView] = useState<'story' | 'steps'>('story')

  useEffect(() => {
    let live = true
    getDemoRun(id).then((r) => live && setRun(r)).catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [id])

  if (error) return <Notice tone="bad" testid="run-error">{error}</Notice>
  if (!run) return <p className="dim" data-testid="run-loading">Opening run…</p>
  const msg = statusMessage(run)
  return (
    <article className="detail" data-testid="demo-detail" data-run={run.run_id} data-kind={run.provenance.kind}>
      <header className="detail-head">
        <div>
          <h2>{run.label ?? 'Investigation run'}</h2>
          <p className="dim"><code>{run.run_id}</code> · {run.created_utc.replace('T', ' ')} UTC
            {run.integrity && (run.integrity.verified ? ' · hash verified' : ' · HASH MISMATCH')}</p>
        </div>
      </header>
      <KindBanner kind={run.provenance.kind} note={run.provenance.note} />
      {run.integrity && !run.integrity.verified && <Notice tone="bad">This bundled recording does not match its recorded SHA-256. Treat it as altered.</Notice>}
      <p className={`headline tone-${msg.tone}`} data-testid="demo-headline">{honestHeadline(run)}</p>
      <div className="view-toggle" role="tablist" aria-label="view">
        <button role="tab" aria-selected={view === 'story'} className={view === 'story' ? 'on' : ''} data-testid="view-story" onClick={() => setView('story')}>Guided story</button>
        <button role="tab" aria-selected={view === 'steps'} className={view === 'steps' ? 'on' : ''} data-testid="view-steps" onClick={() => setView('steps')}>Step-by-step details</button>
      </div>
      {view === 'story' ? <Story run={run} /> : (<>
      <nav className="stepper" aria-label="investigation steps">
        {STEPS.map((s, i) => (
          <button key={s} data-step={s} className={step === s ? 'on' : ''} onClick={() => setStep(s)} aria-current={step === s ? 'step' : undefined}>
            <span className="n">{i + 1}</span>{STEP_TITLE[s]}
          </button>
        ))}
      </nav>
      <div className="step" data-testid={`demo-step-${step}`}>
        {step === 'observe' && <ObserveStep run={run} />}
        {step === 'prompt' && <PromptStep run={run} />}
        {step === 'proposal' && <ProposalStep run={run} />}
        {step === 'verify' && <VerifyStep run={run} />}
        {step === 'replay' && <ReplayStep run={run} />}
      </div>
      <footer className="step-nav">
        <button disabled={step === STEPS[0]} onClick={() => setStep(STEPS[STEPS.indexOf(step) - 1])}>← Back</button>
        <button disabled={step === STEPS[STEPS.length - 1]} onClick={() => setStep(STEPS[STEPS.indexOf(step) + 1])}>Next →</button>
        {run.provenance.usage && (
          <small className="dim">{run.provenance.model} · {run.provenance.usage.total_tokens} tokens · reasoning effort {run.provenance.setting.reasoning_effort} · max {run.provenance.setting.max_tokens}</small>
        )}
      </footer>
      </>)}
      <details className="limits"><summary>What this does and does not show</summary>
        <ul>{run.limits.map((l) => <li key={l}>{l}</li>)}</ul>
        {status && <small>Reasoning effort is a request, not a guarantee: the API did not report how much reasoning was used.</small>}
      </details>
    </article>
  )
}

function ObserveStep({ run }: { run: DemoRun }) {
  const f = run.observed.metrics[String(run.observed.failing_seed)]
  const w = run.observed.metrics[String(run.observed.walking_seed)]
  const rowsOf = (m: Record<string, unknown>) => ['label', 'fall_time', 'valid_steps', 'backward_steps', 'touchdowns', 'speed_upright', 'max_abs_pitch'].map((k) => (
    <tr key={k}><td>{k.replace(/_/g, ' ')}</td><td>{typeof m[k] === 'number' ? (m[k] as number).toFixed(2) : String(m[k] ?? '—')}</td></tr>
  ))
  return (
    <div className="step-body">
      <Block kind="measured" title={`The frozen controller on seed ${run.observed.failing_seed} (failing) and ${run.observed.walking_seed} (walking)`} testid="demo-observed">
        <div className="pair-tables">
          <div className="table-scroll"><table><caption>seed {run.observed.failing_seed}</caption><tbody>{rowsOf(f)}</tbody></table></div>
          <div className="table-scroll"><table><caption>seed {run.observed.walking_seed}</caption><tbody>{rowsOf(w)}</tbody></table></div>
        </div>
        <small>Freshly measured at the start of the run (10 s episodes). The controller is the frozen Phase 2A incumbent; the seed only sets a small random initial pose.</small>
      </Block>
    </div>
  )
}

function PromptStep({ run }: { run: DemoRun }) {
  return (
    <div className="step-body">
      <Block kind="measured" title="Exact context sent to the model (measurements only, no conclusions)" testid="demo-context">
        <details open><summary>Show context JSON</summary><pre className="ctx">{JSON.stringify(run.context, null, 1)}</pre></details>
        <small>Prompt SHA-256 <code>{run.prompt.sha256.slice(0, 16)}…</code> · {run.model_reply.temperature} temperature · slots requested {run.model_reply.slots.length}</small>
      </Block>
      <details><summary>System prompt</summary><pre className="ctx">{run.prompt.system}</pre></details>
    </div>
  )
}

function ProposalStep({ run }: { run: DemoRun }) {
  const msg = statusMessage(run)
  return (
    <div className="step-body">
      <Notice tone={msg.tone === 'ok' ? 'muted' : msg.tone} testid="demo-status">{msg.text}</Notice>
      {run.model_reply.slots.map((s, i) => (
        <Block key={i} kind="model" title={`Slot ${i + 1}${s.proposal ? '' : ' — not usable'}`} testid={`demo-slot-${i}`}>
          {s.proposal ? (
            <>
              <p>{s.proposal.claim}</p>
              <ul className="cites">
                {s.proposal.cited_evidence.map((c) => (
                  <li key={c}><code>{c}</code> → <b>{String(lookupPath(run.context, c) ?? 'unresolved')}</b> <small className="dim">(value in the measured context)</small></li>
                ))}
              </ul>
              <p>
                Proposed edit: {s.proposal.edits.map((e, k) => (
                  <code key={k}>{describeEdit(e, run.interventions.find((iv) => iv.slot === i)?.realised[k])}</code>
                ))}
                {' '}· predicted gain ≥ {s.proposal.prediction.min_gain_seeds} seeds · self-reported confidence {(s.proposal.confidence * 100).toFixed(0)}%
              </p>
            </>
          ) : (
            <p>Rejected by schema validation: <code>{s.reason}</code></p>
          )}
        </Block>
      ))}
      <details><summary>Raw reply exactly as received</summary><pre className="ctx" data-testid="demo-raw">{run.model_reply.raw_reply ?? '(no visible content)'}</pre></details>
      {run.model_reply.call && (
        <small className="dim">finish_reason {run.model_reply.call.finish_reason} · latency {run.model_reply.call.latency_s?.toFixed(1)} s · reasoning present: {String(run.model_reply.call.reasoning_present)}</small>
      )}
    </div>
  )
}

function VerifyStep({ run }: { run: DemoRun }) {
  const ver = run.verification
  if (!ver) return <Notice tone="warn" testid="demo-noverify">No valid proposal, so nothing was verified. The record stops here on purpose: a missing result is not replaced.</Notice>
  const rows: { name: string; res: (typeof ver.results)[string]; predicted?: number }[] = [{ name: 'frozen controller', res: ver.results['theta0'] }]
  for (const iv of run.interventions) {
    rows.push({ name: `model proposal ${iv.slot + 1}: ${iv.proposal.edits.map((e) => e.parameter).join(' + ')}`, res: ver.results[`slot${iv.slot}`], predicted: iv.proposal.prediction.min_gain_seeds })
    rows.push({ name: `matched random edit ${iv.slot + 1}: ${iv.matched_random.edits.map((e) => e.parameter).join(' + ')}`, res: ver.results[`slot${iv.slot}_random`] })
  }
  return (
    <div className="step-body">
      <Block kind="measured" title={`Walking on ${ver.seeds.length} fresh seeds (${ver.seeds[0]}–${ver.seeds[ver.seeds.length - 1]})`} testid="demo-verify">
        <div className="table-scroll"><table className="loco-table">
          <thead><tr><td>controller</td><td>walking</td><td>survived</td><td>per seed</td><td>measured verdict</td></tr></thead>
          <tbody>
            {rows.map((r) => {
              const v = verdictText(r.res.verdict)
              return (
                <tr key={r.name}>
                  <td>{r.name}</td><td>{r.res.walking_count}/{r.res.n}</td><td>{r.res.survival_count}/{r.res.n}</td>
                  <td className="bars" title="■ walking, □ not walking, in seed order">{bar(r.res)}</td>
                  <td>{r.res.verdict ? <span className={`chip chip-${v.tone === 'ok' ? 'ok' : v.tone === 'bad' ? 'bad' : 'muted'}`}>{v.text}</span> : '—'}
                    {r.predicted !== undefined && <small className="dim"> {predictionText(r.res.verdict, r.predicted)}</small>}</td>
                </tr>
              )
            })}
          </tbody>
        </table></div>
        <small>{ver.rule}. Same seeds for every row; {ver.rollouts} rollouts. A matched random edit has the same number of edits and the same step sizes on random parameters.</small>
      </Block>
    </div>
  )
}

