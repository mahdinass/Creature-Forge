import { useEffect, useState } from 'react'
import { ForgeApiError, getInvestigation, startInvestigation } from '../api'
import { AcceptPanel } from './AcceptPanel'
import { ArenaCompare, ProvChip } from './ArenaCompare'
import {
  armChip, armList, buildTimeline, isModelFailed, isTerminal, jobFailureMessage, phaseText, progressFraction, VERDICT_TONE, type TimelineStep,
} from './forgeLogic'
import type { ChallengeRun, Creature, CreatureVersion, ForgeStatus, InvestigationRecord } from './forgeTypes'
import { useJobPoll } from './useJobPoll'

function Step({ s, provenance }: { s: TimelineStep; provenance: string }) {
  switch (s.kind) {
    case 'evidence':
      return <li className="fg-tl" data-step="evidence"><b>Evidence sent to the model</b><span>{s.keys.length} sections ({s.bytes.toLocaleString()} characters of JSON): {s.keys.join(', ')}.</span></li>
    case 'model_call':
      return (
        <li className={`fg-tl fg-tl-model ${s.call.error ? 'fail' : ''}`} data-step="model_call">
          <b>Model call</b>
          <dl className="fg-kv">
            <div><dt>model</dt><dd>{s.call.model}</dd></div>
            <div><dt>request id</dt><dd>{s.call.request_id ?? 'none'}</dd></div>
            <div><dt>tokens</dt><dd>{s.tokens ?? 'n/a'}</dd></div>
            <div><dt>latency</dt><dd>{s.call.latency_s != null ? `${s.call.latency_s.toFixed(1)} s` : 'n/a'}</dd></div>
          </dl>
          {s.call.error && <span className="fg-bad">Call error: {s.call.error}</span>}
        </li>
      )
    case 'hypotheses':
      return (
        <li className="fg-tl fg-tl-model" data-step="hypotheses"><b>Hypotheses (written by the model, unverified)</b>
          {s.summary && <span>{s.summary}</span>}
          {s.items.map((h) => (
            <div key={h.id} className="fg-hyp"><b>{h.id}</b> {h.mechanism}
              <div className="fg-cites">{h.cited.map((c) => (
                <code key={c.path} className={c.value === undefined ? 'unresolved' : ''} title={c.value === undefined ? 'This citation does not resolve to a single value in the evidence' : ''}>
                  {c.path} = {c.value === undefined ? 'unresolved' : String(c.value)}</code>))}</div>
            </div>
          ))}
        </li>
      )
    case 'proposals':
      return (
        <li className="fg-tl" data-step="proposals"><b>Proposals checked by the validator</b>
          {s.items.map((p) => (
            <div key={p.id} className={`fg-prop fg-prop-${p.status}`} data-status={p.status}>
              <b>{p.id}</b> <span className="fg-chip">{p.status}</span>{p.hypothesis ? <span className="fg-dim"> for {p.hypothesis}</span> : null}
              {p.expected && <div className="fg-dim">Predicted: {p.expected}</div>}
              {p.reasons.length > 0 && <ul>{p.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
            </div>
          ))}
        </li>
      )
    case 'arena':
      return (
        <li className="fg-tl" data-step="arena"><b>Arena</b>
          <span>{s.arms.length} arms on {s.screenSeeds} screening and {s.validateSeeds} validation seeds, all run in MuJoCo.</span>
          <div className="fg-armlist">{s.arms.map((a) => <span key={a.arm_id}><ProvChip {...a.chip} /> {a.arm_id}{a.unavailable ? ` (unavailable: ${a.unavailable})` : ''}</span>)}</div>
        </li>
      )
    case 'verdicts':
      return (
        <li className="fg-tl" data-step="verdicts"><b>Verdict per arm</b>
          {s.items.map((v) => (
            <div key={v.arm_id} className={`fg-vrow tone-${v.status ? VERDICT_TONE[v.status] : 'muted'}`} data-status={v.status ?? ''}><ProvChip {...v.chip} /> <b>{v.arm_id}</b> {v.text}</div>
          ))}
          <small className="fg-dim">{provenance === 'SCRIPTED_MOCK' ? 'Scripted mock: text written by this repository, not a model.' : ''}</small>
        </li>
      )
    case 'failure':
      return <li className="fg-tl fail" role="alert" data-step="failure" data-testid="model-failure"><b>The model step failed ({s.status})</b><span>{s.message}</span><span>No AI arm exists. Baselines, if shown, are labelled as non-AI.</span></li>
  }
}

function RecordView({ cid, version, record, onAccepted }: { cid: string; version: CreatureVersion; record: InvestigationRecord; onAccepted: (c: Creature) => void }) {
  const arms = armList(record)
  const first = arms.find((a) => record.verdicts?.[a.arm_id]?.status === 'VERIFIED_IMPROVEMENT') ?? arms.find((a) => a.source !== 'original')
  const [armId, setArmId] = useState<string | null>(first?.arm_id ?? null)
  const arm = arms.find((a) => a.arm_id === armId)
  const steps = buildTimeline(record)
  const canCompare = !isModelFailed(record) && !!arm && (record.seeds?.validate?.length ?? 0) > 0
  return (
    <div className="fg-record" data-testid="investigation-record" data-status={record.status}>
      <div className={`fg-prov fg-prov-${record.provenance}`} data-testid="inv-provenance"><b>{record.provenance === 'LIVE' ? 'LIVE' : 'SCRIPTED MOCK'}</b>
        <span>{record.provenance === 'LIVE' ? 'A real model call made for this investigation.' : 'Not a model. Text from a fixture, never counted as a result.'}</span></div>
      <ol className="fg-timeline" data-testid="inv-timeline">{steps.map((s) => <Step key={s.id} s={s} provenance={record.provenance} />)}</ol>
      {arms.length > 1 && (
        <div className="fg-armpick" role="radiogroup" aria-label="arm to compare">
          {arms.filter((a) => a.source !== 'original').map((a) => (
            <button key={a.arm_id} role="radio" aria-checked={a.arm_id === armId} className={a.arm_id === armId ? 'on' : ''} data-testid={`arm-${a.arm_id}`} onClick={() => setArmId(a.arm_id)}>
              <ProvChip {...armChip(a, record.provenance)} /> {a.arm_id}
            </button>
          ))}
        </div>
      )}
      {canCompare && arm && <ArenaCompare record={record} armId={arm.arm_id} />}
      {arm && !isModelFailed(record) && <AcceptPanel cid={cid} version={version} record={record} arm={arm} onAccepted={onAccepted} />}
    </div>
  )
}

/** Starts an investigation of the current run, shows its live events, then its record. Shows an honest "not available yet" on 503. */
export function InvestigationView({ cid, version, run, status, onAccepted }: {
  cid: string
  version: CreatureVersion
  run: ChallengeRun
  status: ForgeStatus | null
  onAccepted: (c: Creature) => void
}) {
  const [phase, setPhase] = useState<'idle' | 'starting' | 'running' | 'unavailable' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [ids, setIds] = useState<{ job: string; inv: string } | null>(null)
  const [record, setRecord] = useState<InvestigationRecord | null>(null)
  const poll = useJobPoll(ids?.job ?? null)

  useEffect(() => { setPhase('idle'); setIds(null); setRecord(null); setMessage(null) }, [run.run_id])

  const start = async (mode: 'live' | 'scripted') => {
    setPhase('starting')
    setMessage(null)
    setRecord(null)
    try {
      const r = await startInvestigation(cid, version.n, { run_id: run.run_id, mode })
      setIds({ job: r.job_id, inv: r.investigation_id })
      setPhase('running')
    } catch (e) {
      setMessage((e as Error).message)
      setPhase(e instanceof ForgeApiError && e.status === 503 ? 'unavailable' : 'error')
    }
  }

  useEffect(() => {
    if (!ids || poll.job?.status !== 'done') return
    let alive = true
    getInvestigation(ids.inv)
      .then((r) => alive && setRecord(r))
      .catch((e: Error) => { if (alive) { setMessage(e.message); setPhase(e instanceof ForgeApiError && e.status === 503 ? 'unavailable' : 'error') } })
    return () => { alive = false }
  }, [ids, poll.job?.status])

  const failed = phase === 'running' && (poll.job?.status === 'failed' || poll.job?.status === 'cancelled')
  const fraction = progressFraction(poll.job)
  return (
    <section className="fg-card fg-inv" data-testid="investigation" aria-label="AI investigation">
      <h3>Investigate with AI</h3>
      <p className="fg-dim">A model reads the measured evidence from this run and proposes bounded edits. MuJoCo then runs the original and every candidate on fresh seeds, and a fixed rule decides.</p>
      {status && !status.live_available && <p className="fg-dim" data-testid="live-hint">Live model calls are switched off on this server.</p>}
      <div className="fg-actions">
        <button className="btn btn-investigate" disabled={phase === 'starting' || phase === 'running'} data-testid="investigate-btn" onClick={() => void start('live')}>
          {phase === 'starting' ? 'Starting...' : 'Investigate with AI'}
        </button>
        <button className="btn btn-ghost" disabled={phase === 'starting' || phase === 'running'} data-testid="investigate-mock-btn" title="Fixture text, not a model" onClick={() => void start('scripted')}>Run scripted mock (not a model)</button>
      </div>
      {phase === 'unavailable' && (
        <div className="fg-note-box" role="status" data-testid="investigation-unavailable">AI investigation is not available yet: {message}</div>
      )}
      {phase === 'error' && <div className="error" role="alert" data-testid="investigation-error">The investigation could not start: {message}</div>}
      {phase === 'running' && !record && !failed && (
        <div className="fg-progress" data-testid="inv-progress">
          <div className="fg-progress-head"><b>Investigating</b><span>{phaseText(poll.job, poll.events)}</span></div>
          <div className="fg-bar"><i style={{ width: `${(fraction ?? 0.04) * 100}%` }} /></div>
          <ul className="fg-events">{poll.events.filter((e) => e.type !== 'progress').slice(-8).map((e) => <li key={e.i}><code>{e.type}</code> {typeof e.data.message === 'string' ? e.data.message : typeof e.data.phase === 'string' ? e.data.phase : ''}</li>)}</ul>
        </div>
      )}
      {failed && <div className="error" role="alert" data-testid="investigation-failed">The investigation failed: {jobFailureMessage(poll.job, poll.events)}</div>}
      {poll.job && isTerminal(poll.job.status) && !record && poll.job.status === 'done' && phase === 'running' && <div className="fg-skeleton skeleton" />}
      {record && <RecordView cid={cid} version={version} record={record} onAccepted={onAccepted} />}
    </section>
  )
}
