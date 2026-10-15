import { useEffect, useState } from 'react'
import { ForgeApiError, getInvestigation, listInvestigations, startInvestigation } from '../api'
import { AcceptPanel } from './AcceptPanel'
import { ArenaCompare, ProvChip } from './ArenaCompare'
import {
  armChip, budgetLine, buildTimeline, hypotheticalNote, isModelFailed, isTerminal, jobFailureMessage, loopLines, modelResponseOf, newestFirst, phaseText,
  provenanceLabel, STAGE_LABEL, STAGES, stageStates, STATUS_TEXT, summaryChips, VERDICT_TONE, validationTriplet, type ArmView, type TimelineStep,
} from './forgeLogic'
import type { ChallengeRun, Creature, CreatureVersion, ForgeStatus, InvestigationRecord, InvestigationSummary, LoopResult, ModelCall } from './forgeTypes'
import { useJobPoll } from './useJobPoll'

function ModelCard({ call, tokens, live }: { call: ModelCall; tokens: number | null; live?: boolean }) {
  return (
    <div className={`fg-tl fg-tl-model ${call.error ? 'fail' : ''}`} data-step="model_call" data-testid={live ? 'model-response-live' : 'model-call'}>
      <b>Model call</b>
      <dl className="fg-kv">
        <div><dt>model</dt><dd>{call.model}</dd></div>
        <div><dt>request id</dt><dd>{call.request_id ?? 'none'}</dd></div>
        <div><dt>latency</dt><dd>{call.latency_s != null ? `${call.latency_s.toFixed(1)} s` : 'n/a'}</dd></div>
        <div><dt>tokens</dt><dd>{tokens ?? 'n/a'}</dd></div>
        <div><dt>finish</dt><dd>{call.finish_reason ?? 'n/a'}</dd></div>
      </dl>
      {call.error && <span className="fg-bad">Call error: {call.error}</span>}
    </div>
  )
}

function ArmCard({ title, a, testid }: { title: string; a: ArmView | null; testid: string }) {
  if (!a) return null
  const tone = a.verdict ? VERDICT_TONE[a.verdict.status] : 'muted'
  return (
    <div className={`fg-vcard tone-${tone}`} data-testid={testid} data-status={a.verdict?.status ?? ''}>
      <small className="fg-dim">{title}</small>
      <div><ProvChip {...a.chip} /> <b>{a.arm_id}</b></div>
      <span className="fg-dim">{a.edits}</span>
      <p>{a.text}</p>
    </div>
  )
}

function Step({ s, provenance }: { s: TimelineStep; provenance: string }) {
  const mock = provenance === 'SCRIPTED_MOCK'
  switch (s.kind) {
    case 'evidence':
      return <li className="fg-tl" data-step="evidence"><b>Evidence sent to the model</b><span>{s.keys.length} sections ({s.bytes.toLocaleString()} characters of JSON): {s.keys.join(', ')}.</span></li>
    case 'model_call':
      return <li><ModelCard call={s.call} tokens={s.tokens} /></li>
    case 'probes':
      return (
        <li className="fg-tl fg-tl-model" data-step="probes"><b>Diagnostic probes (counterfactual runs, not proposals)</b>
          <span className="fg-dim">The model asked for these experiments before proposing anything. MuJoCo ran each on the same {s.seeds} probe seeds as the unchanged creature{s.rollouts !== null ? ` (${s.rollouts} rollouts)` : ''}. The check of expected against observed is made by the code, not the model.</span>
          {s.skipped && <span className="fg-note-box" data-testid="probes-skipped">Probes were skipped: {s.skipped}</span>}
          {s.rows.map((r) => (
            <div key={r.probe_id} className={`fg-probe fg-probe-${r.verdict.replace(' ', '_')}`} data-testid="probe-row" data-probe={r.probe_id} data-verdict={r.verdict}>
              <div><b>{r.probe_id}</b> <span className="fg-chip">{r.verdict}</span></div>
              <span>Changed: {r.transformation}</span>
              <span>Expected: {r.expect ?? 'n/a'}{r.hypothesis ? ` (to test ${r.hypothesis})` : ''}. Observed: {r.observed ?? 'n/a'}.</span>
              <span className="fg-dim">{r.detail}</span>
            </div>
          ))}
        </li>
      )
    case 'hypotheses':
      return (
        <li className="fg-tl fg-tl-model" data-step="hypotheses"><b>{mock ? 'Hypotheses (scripted text, not a model)' : 'Hypotheses (written by the model, unverified)'}</b>
          {s.summary && <span>{s.summary}</span>}
          {s.items.map((h) => (
            <div key={h.id} className="fg-hyp"><b>{h.id}</b> {h.mechanism}
              <div className="fg-cites">{h.cited.map((c) => (
                <code key={c.path} className={c.value === undefined ? 'unresolved' : ''} title={c.value === undefined ? 'This citation does not resolve to a single value in the evidence' : 'Value in the evidence sent to the model'}>
                  {c.path} = {c.value === undefined ? 'unresolved' : String(c.value)}</code>))}</div>
              {h.competing && h.competing.length > 0 && <small className="fg-dim">Competing explanation: {h.competing.join('; ')}</small>}
            </div>
          ))}
        </li>
      )
    case 'proposals':
      return (
        <li className="fg-tl" data-step="proposals"><b>Proposals checked by the validator</b>
          {s.items.map((p) => (
            <div key={p.id} className={`fg-prop fg-prop-${p.status}`} data-status={p.status}>
              <b>{p.id}</b> <span className="fg-chip">{p.status}</span> {p.edits}{p.hypothesis ? <span className="fg-dim"> (for {p.hypothesis})</span> : null}
              {p.expected && <div className="fg-dim">Predicted: {p.expected}</div>}
              {p.reasons.length > 0 && <ul>{p.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
            </div>
          ))}
        </li>
      )
    case 'arena':
      return (
        <li className="fg-tl" data-step="arena"><b>Arms</b>
          <span>{s.arms.length} arms run in MuJoCo: {s.screenSeeds} screening seeds, then {s.validateSeeds} held-out validation seeds for the selected ones.</span>
          <div className="table-scroll"><table data-testid="arms-table">
            <thead><tr><td>arm</td><td>source</td><td>change</td><td>rollouts</td></tr></thead>
            <tbody>{s.arms.map((a) => (
              <tr key={a.arm_id} data-arm={a.arm_id}><td className="fg-left">{a.arm_id}</td><td><ProvChip {...a.chip} /></td>
                <td className="fg-left">{a.unavailable ? `not run: ${a.unavailable}` : a.error ? `error: ${a.error}` : a.edits}</td><td>{a.rollouts ?? 'n/a'}</td></tr>
            ))}</tbody></table></div>
        </li>
      )
    case 'screening':
      return (
        <li className="fg-tl" data-step="screening"><b>Screening ranking</b>
          <span className="fg-dim">Screening only selects which arms get validated; it decides nothing.</span>
          {[['AI arms', s.ai], ['Baseline arms', s.baseline]].map(([title, rows]) => (
            <div key={title as string} className="table-scroll"><table><caption className="fg-left">{title as string}</caption>
              <tbody>{(rows as typeof s.ai).map((r) => (
                <tr key={r.arm_id}><td className="fg-left">{r.arm_id}</td><td>median {r.median === null ? 'n/a' : r.median.toFixed(2)}</td>
                  <td>{r.arm_id === s.selected.ai || r.arm_id === s.selected.baseline ? 'selected for validation' : ''}{r.arm_id === s.selected.twin ? ' (matched twin)' : ''}</td></tr>
              ))}</tbody></table></div>
          ))}
          {s.excluded.length > 0 && <small className="fg-bad">Excluded: {s.excluded.join('; ')}</small>}
        </li>
      )
    case 'validation':
      return (
        <li className="fg-tl" data-step="validation"><b>Validation on {s.seeds} held-out seeds</b>
          <span className="fg-dim">{mock ? 'The scripted mock’s change' : 'Nemotron’s change'} against a random change of the same size, on the same held-out seeds. The verdict is MuJoCo’s fixed rule; the model’s confidence is not read.</span>
          <div className="fg-vgrid" data-testid="validation-grid">
            <ArmCard title={mock ? 'Scripted mock change' : 'AI change'} a={s.ai} testid="verdict-ai" />
            <ArmCard title="Matched random twin" a={s.twin} testid="verdict-twin" />
            <ArmCard title="Best baseline" a={s.baseline} testid="verdict-baseline" />
          </div>
          {!s.twin && s.ai && <small className="fg-dim" data-testid="no-twin">No matched random twin was validated in this record, so there is nothing to put next to it.</small>}
          {s.others.map((o) => <ArmCard key={o.arm_id} title="Other arm" a={o} testid={`verdict-${o.arm_id}`} />)}
        </li>
      )
    case 'failure':
      return <li className="fg-tl fail" role="alert" data-step="failure" data-testid="model-failure"><b>{s.status === 'done' ? 'Problem' : (STATUS_TEXT[s.status] ?? s.status)}</b><span>{s.message}</span>{s.status === 'model_failed' && <span>No AI arm exists. Baselines, if shown, are labelled as non-AI.</span>}</li>
  }
}

function RecordView({ cid, version, record, onAccepted }: { cid: string; version: CreatureVersion; record: InvestigationRecord; onAccepted: (c: Creature) => void }) {
  const trip = validationTriplet(record)
  const arms = (record.arms ?? []).filter((a) => a.source !== 'original' && !a.unavailable)
  const verifiedArm = arms.find((a) => record.verdicts?.[a.arm_id]?.status === 'VERIFIED_IMPROVEMENT')
  const first = verifiedArm ?? trip.ai ?? arms.find((a) => !!record.verdicts?.[a.arm_id]) ?? null
  const [armId, setArmId] = useState<string | null>(first?.arm_id ?? null)
  useEffect(() => { setArmId(first?.arm_id ?? null) }, [record.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const validated = arms.filter((a) => !!record.verdicts?.[a.arm_id])
  const arm = validated.find((a) => a.arm_id === armId) ?? null
  const steps = buildTimeline(record)
  const canCompare = !isModelFailed(record) && !!arm && (record.seeds?.validate?.length ?? 0) > 0
  const hyp = hypotheticalNote(record)
  return (
    <div className="fg-record" data-testid="investigation-record" data-status={record.status} data-provenance={record.provenance}>
      <div className={`fg-prov fg-prov-${record.provenance}`} data-testid="inv-provenance"><b>{provenanceLabel(record.provenance)}</b>
        <span>{record.provenance === 'LIVE' ? 'A real model call made for this investigation.' : 'Not a model. Text from a fixture, never counted as a result.'}</span>
        <span className="fg-dim">{STATUS_TEXT[record.status] ?? record.status}{record.creature.round && record.creature.round > 1 ? `, round ${record.creature.round}` : ''}</span></div>
      {hyp && <div className="fg-note-box" data-testid="hypothetical-note">{hyp}</div>}
      <ol className="fg-timeline" data-testid="inv-timeline">{steps.map((s) => <Step key={s.id} s={s} provenance={record.provenance} />)}</ol>
      <p className="fg-dim" data-testid="budget-line">Budget used: {budgetLine(record.budget)}.</p>
      {validated.length > 0 && (
        <div className="fg-armpick" role="radiogroup" aria-label="arm to compare and decide on">
          {validated.map((a) => (
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

/** The creature's investigations, newest first. */
export function InvestigationList({ cid, nonce, openId, onOpen }: { cid: string; nonce: number; openId: string | null; onOpen: (id: string) => void }) {
  const [list, setList] = useState<InvestigationSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    listInvestigations(cid).then((l) => alive && setList(newestFirst(l))).catch((e: Error) => alive && setError(e.message))
    return () => { alive = false }
  }, [cid, nonce])
  return (
    <section className="fg-card" data-testid="investigation-list" aria-label="investigations of this creature">
      <h3>Investigations</h3>
      {error && <div className="error" role="alert">{error}</div>}
      {list && list.length === 0 && <p className="fg-dim" data-testid="investigation-list-empty">None yet. Run a challenge, then investigate it.</p>}
      <ul className="fg-ilist">
        {(list ?? []).map((s) => (
          <li key={s.id}>
            <button className={`fg-linkbtn ${s.id === openId ? 'on' : ''}`} data-testid="investigation-item" data-id={s.id} onClick={() => onOpen(s.id)}>
              <b>{s.id}</b> <span className="fg-dim">v{s.creature.n}{s.creature.round && s.creature.round > 1 ? ` round ${s.creature.round}` : ''} · {new Date(s.created).toLocaleString()}</span>
            </button>
            <span className="fg-chips">{summaryChips(s).map((c) => <ProvChip key={c.label} {...c} />)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Starts an investigation of the current run (single or a bounded loop), shows its live progress, then the record. */
export function InvestigationView({ cid, version, versions, run, status, openId, onOpenId, onChanged, onAccepted }: {
  cid: string
  version: CreatureVersion
  versions: CreatureVersion[]
  run: ChallengeRun | null
  status: ForgeStatus | null
  openId: string | null
  onOpenId: (id: string | null) => void
  onChanged: () => void
  onAccepted: (c: Creature) => void
}) {
  const [phase, setPhase] = useState<'idle' | 'starting' | 'running' | 'unavailable' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [loop, setLoop] = useState(false)
  const [probes, setProbes] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [record, setRecord] = useState<InvestigationRecord | null>(null)
  const [recordError, setRecordError] = useState<string | null>(null)
  const poll = useJobPoll(jobId)

  useEffect(() => { setPhase('idle'); setJobId(null); setMessage(null) }, [run?.run_id])

  const start = async (mode: 'live' | 'scripted') => {
    if (!run) return
    setPhase('starting'); setMessage(null); setRecord(null); onOpenId(null)
    try {
      const r = await startInvestigation(cid, version.n, { run_id: run.run_id, mode, loop, probes })
      setJobId(r.job_id)
      setPhase('running')
    } catch (e) {
      setMessage((e as Error).message)
      setPhase(e instanceof ForgeApiError && e.status === 503 ? 'unavailable' : 'error')
    }
  }

  const loopResult = (poll.job?.result_ref as { loop?: LoopResult } | null)?.loop ?? null
  const finishedId = (poll.job?.result_ref as { investigation_id?: string } | null)?.investigation_id ?? null
  useEffect(() => {
    if (poll.job?.status !== 'done') return
    onChanged()
    if (!loopResult && finishedId) onOpenId(finishedId)
    else if (loopResult) onOpenId(loopResult.best?.investigation_id ?? loopResult.rounds[loopResult.rounds.length - 1]?.investigation_id ?? null)
  }, [poll.job?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setRecord(null); setRecordError(null)
    if (!openId) return
    let alive = true
    getInvestigation(openId).then((r) => alive && setRecord(r)).catch((e: Error) => alive && setRecordError(e.message))
    return () => { alive = false }
  }, [openId])

  const failed = phase === 'running' && (poll.job?.status === 'failed' || poll.job?.status === 'cancelled')
  const running = phase === 'running' && !!poll.job && !isTerminal(poll.job.status) || phase === 'running' && !poll.job
  const busy = phase === 'starting' || running
  const live = status?.live_available === true
  const stages = stageStates(poll.events)
  const modelCall = modelResponseOf(poll.events)
  return (
    <section className="fg-card fg-inv" data-testid="investigation" aria-label="AI investigation">
      <h3>Investigate with AI</h3>
      {run ? (
        <p className="fg-dim">A model reads the measured evidence from this run and proposes bounded edits. MuJoCo then runs the original, each proposal and a matched random change on held-out seeds, and a fixed rule decides. Nothing is accepted for you.</p>
      ) : (
        <p className="fg-dim" data-testid="investigate-needs-run">Run a challenge first: the investigation starts from its measured result.</p>
      )}
      {run && (
        <>
          <label className="fg-check" data-testid="loop-option"><input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} disabled={busy} data-testid="loop-checkbox" />
            Keep investigating (up to 3 rounds, stops after 2 rounds without a verified change, never accepts for you)</label>
          <label className="fg-check" data-testid="probes-option"><input type="checkbox" checked={probes} onChange={(e) => setProbes(e.target.checked)} disabled={busy} data-testid="probes-checkbox" />
            Run diagnostic probes first (the model picks up to 3 what-if experiments, MuJoCo runs them, then it proposes; costs one more model call)</label>
          <div className="fg-actions">
            <button className="btn btn-investigate" disabled={busy || !live} data-testid="investigate-btn" onClick={() => void start('live')}>
              {phase === 'starting' ? 'Starting...' : 'Investigate with AI'}
            </button>
            <button className="btn btn-ghost" disabled={busy} data-testid="investigate-mock-btn" title="Fixture text, not a model" onClick={() => void start('scripted')}>Run scripted mock (not a model)</button>
          </div>
          {!live && (
            <p className="fg-dim" data-testid="live-hint">Live model calls are off on this server, so "Investigate with AI" is disabled. They need CREATURE_FORGE_ENABLE_LIVE=1, an API key and ledger headroom. The scripted mock still runs the whole pipeline, labelled as not a model.</p>
          )}
          {live && status?.model && <p className="fg-dim">Model: {status.model.model}{status.ledger?.usd !== undefined ? ` · ledger $${status.ledger.usd.toFixed(2)} used` : ''}</p>}
        </>
      )}
      {phase === 'unavailable' && <div className="fg-note-box" role="status" data-testid="investigation-unavailable">AI investigation is not available yet: {message}</div>}
      {phase === 'error' && <div className="error" role="alert" data-testid="investigation-error">The investigation could not start: {message}</div>}
      {phase === 'running' && (
        <div className="fg-progress" data-testid="inv-progress" data-job-status={poll.job?.status ?? 'starting'}>
          <div className="fg-progress-head"><b>{loop ? 'Investigating (loop)' : 'Investigating'}</b><span>{phaseText(poll.job, poll.events)}</span></div>
          <ol className="fg-stages" data-testid="inv-stages">{STAGES.map((s) => <li key={s} className={`fg-stage fg-stage-${stages[s]}`} data-stage={s} data-state={stages[s]}>{STAGE_LABEL[s]}</li>)}</ol>
          {modelCall && <ModelCard call={modelCall} tokens={modelCall.usage?.total_tokens ?? null} live />}
          {poll.error && <small className="fg-bad">Cannot reach the server for progress: {poll.error}</small>}
        </div>
      )}
      {failed && <div className="error" role="alert" data-testid="investigation-failed">The investigation failed: {jobFailureMessage(poll.job, poll.events)}</div>}
      {loopResult && (
        <div className="fg-looprs" data-testid="loop-result">
          <b>Loop finished</b>
          <ul>{loopLines(loopResult).map((l, i) => <li key={i}>{l}</li>)}</ul>
          <div className="fg-actions">{loopResult.rounds.map((r) => (
            <button key={r.investigation_id} className="btn btn-ghost fg-small" data-testid={`loop-round-${r.round}`} onClick={() => onOpenId(r.investigation_id)}>Open round {r.round}</button>
          ))}</div>
        </div>
      )}
      {recordError && <div className="error" role="alert" data-testid="record-error">Could not load the investigation: {recordError}</div>}
      {openId && !record && !recordError && <div className="fg-skeleton skeleton" />}
      {record && <RecordView cid={cid} version={versions.find((v) => v.n === record.creature.n) ?? version} record={record} onAccepted={onAccepted} />}
    </section>
  )
}
