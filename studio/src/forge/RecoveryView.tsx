import { useEffect, useMemo, useState } from 'react'
import { acceptRecovery, cancelForgeJob, ForgeApiError, getRecovery, getRecoveryReplay, listRecoveries, startRecovery } from '../api'
import { usePlayback } from '../store'
import { HeightChart, Transport } from '../Timeline'
import type { RunPayload } from '../types'
import { Viewport } from '../Viewport'
import { ProvChip } from './ArenaCompare'
import {
  buildReasoning, canOfferRecovery, controllerChange, countWalking, editRows, fmtEditValue, fmtRatio, isTerminal, ledgerSegments, modelCostText, newestRecoveryFirst,
  RECOVERY_BUDGETS, RECOVERY_DEFAULT_BUDGET, RECOVERY_STAGE_LABEL, RECOVERY_STAGES, recoveryAcceptState, recoveryBudgetBar, recoveryHeadline, recoveryPhaseText,
  recoveryProvenance, recoveryStageStates, recoverySummaryText, recoveryTone, shortSeed, verdictText, type RoundView,
} from './forgeLogic'
import type { ChallengeRun, Creature, CreatureVersion, ForgeStatus, RecoveryAssessment, RecoveryRecord, RecoverySeedRow, RecoverySummary } from './forgeTypes'
import { ReplayBoundary } from './ReplayBoundary'
import { useJobPoll } from './useJobPoll'

const rowWord = (r: RecoverySeedRow | undefined): string => (!r ? 'n/a' : r.outcome === 'ERROR' ? 'error' : r.outcome === 'PASS' ? 'walks' : r.fell ? 'falls' : r.outcome === 'POOR' ? 'poor' : 'fails')
const rowTone = (r: RecoverySeedRow | undefined): string => (!r ? 'muted' : r.outcome === 'ERROR' ? 'error' : r.outcome === 'PASS' ? 'ok' : r.outcome === 'POOR' ? 'warn' : 'bad')

// ---- how the director reasoned -------------------------------------------------------------------------------------
function RoundCard({ r, isAi, mock }: { r: RoundView; isAi: boolean; mock: boolean }) {
  return (
    <li className="fg-tl fg-rec-round" data-testid="rec-round" data-round={r.round}>
      <b>Round {r.round}</b>
      {r.directorIssues.length > 0 && (
        <div className="fg-note-box" role="status" data-testid="rec-director-issues">
          {r.directorIssues.map((x, i) => <div key={i}>The director&rsquo;s {x}. Nothing was substituted for it.</div>)}
        </div>
      )}
      {isAi && !mock && r.hypotheses.length === 0 && r.directorIssues.length === 0 && <span className="fg-dim">No hypotheses were recorded for this round.</span>}
      {r.hypotheses.map((h) => (
        <div key={h.id} className={`fg-hyp fg-rec-hyp ${h.refuted ? 'refuted' : ''}`} data-testid="rec-hypothesis" data-refuted={h.refuted}>
          <b>{h.id}</b> <span className="fg-chip fg-chip-model">HYPOTHESIS</span>
          {h.refuted && <span className="fg-chip fg-chip-bad" data-testid="rec-refuted-chip">REFUTED{h.refutedRound ? ` in round ${h.refutedRound}` : ''}</span>}
          <div>{h.mechanism}</div>
          {h.cites.length > 0 && (
            <div className="fg-cites">{h.cites.map((c) => (
              <code key={c.path} title={c.value === null ? 'The value is not stored in this record' : 'Value in the evidence sent to the model'}>
                {c.path}{c.value === null ? '' : ` = ${c.value}`}</code>))}</div>
          )}
          {h.competing.length > 0 && <small className="fg-dim">Competing explanation: {h.competing.join('; ')}</small>}
        </div>
      ))}
      {r.probes.length > 0 && (
        <div className="fg-rec-block">
          <b className="fg-rec-sub">{isAi ? 'Probes requested, expectation against measurement' : 'Probes chosen by the rule'}</b>
          {r.probes.map((p) => (
            <div key={p.id} className={`fg-probe fg-rec-probe fg-rec-chip-${p.chip.tone}`} data-testid="rec-probe" data-probe={p.id} data-match={p.chip.label}>
              <div><b>{p.id}</b> {isAi && <span className={`fg-chip fg-chip-${p.chip.tone === 'ok' ? 'good' : p.chip.tone === 'bad' ? 'bad' : 'original'}`}>{p.chip.label}</span>}</div>
              {isAi && <span>The director expected: {p.expect ? (p.expect === 'improves' ? 'the best candidate beats the unchanged creature' : 'no change') : 'n/a'}{p.hypothesis ? ` (to test ${p.hypothesis})` : ''}.</span>}
              <span>Measured by MuJoCo: {p.measured}{p.rollouts !== null ? ` (${p.rollouts} rollouts)` : ''}.</span>
            </div>
          ))}
        </div>
      )}
      {r.rejectedProbes.length > 0 && <small className="fg-bad" data-testid="rec-rejected-probes">Rejected probes: {r.rejectedProbes.join('; ')}</small>}
      {r.refuted.length > 0 && <span data-testid="rec-refuted-list"><b>Refuted after the measurements:</b> {r.refuted.join(', ')}</span>}
      {r.diagnosis && <p className="fg-rec-diag" data-testid="rec-diagnosis"><b>{mock ? 'Scripted text' : 'Diagnosis'}:</b> {r.diagnosis}</p>}
      {r.plans.length > 0 && (
        <div className="fg-rec-block">
          <b className="fg-rec-sub">{isAi ? 'Plans (what to optimise)' : 'Plan chosen by the rule'}</b>
          {r.plans.map((p) => (
            <div key={p.id} className="fg-prop fg-rec-plan" data-testid="rec-plan" data-plan={p.id} data-status={p.status}>
              <div><b>{p.id}</b> <span className="fg-dim">starts from {p.init}; {Math.round(p.share * 100)}% of the remaining budget ({p.budget} rollouts)</span></div>
              <div className="fg-chips" aria-label="subsystems optimised">
                {p.subsystems.map((s) => <span key={`${s.kind}-${s.name}`} className={`fg-chip fg-rec-sub-${s.kind}`} data-kind={s.kind}>{s.kind === 'control' ? 'control' : 'body'}: {s.name}</span>)}
                {p.subsystems.length === 0 && <span className="fg-dim">no subsystem</span>}
              </div>
              {p.hypothesis && <span className="fg-dim">For {p.hypothesis}. </span>}
              {p.prediction && <span>Prediction: {p.prediction}</span>}
              <span>Measured by MuJoCo: {p.measured}{p.rollouts !== null ? ` (${p.rollouts} rollouts used${p.refunded ? `, ${p.refunded} refunded` : ''})` : ''}.</span>
            </div>
          ))}
        </div>
      )}
      {r.rejectedPlans.length > 0 && <small className="fg-bad" data-testid="rec-rejected-plans">Rejected plans (cost nothing, their share is forfeited): {r.rejectedPlans.join('; ')}</small>}
    </li>
  )
}

function Reasoning({ rec }: { rec: RecoveryRecord }) {
  const view = useMemo(() => buildReasoning(rec), [rec])
  return (
    <section className="fg-card" data-testid="rec-reasoning" aria-labelledby="rec-reasoning-h">
      <h3 id="rec-reasoning-h">{view.title}</h3>
      {view.isAi && !view.mock && <p className="fg-dim">Hypotheses are the model&rsquo;s words, unverified. The code compares each expectation with what MuJoCo measured; a probe that matches is not proof of the mechanism.</p>}
      {view.mock && <p className="fg-dim">Fixture text produced by the fixed rule. No model was called, so nothing here is a model&rsquo;s reasoning.</p>}
      {!view.isAi && <p className="fg-dim">A fixed engineering rule picked these probes and plans. It forms no hypotheses and states no expectations.</p>}
      {view.rounds.length === 0 ? <p className="fg-dim" data-testid="rec-no-rounds">No rounds were recorded.</p> : (
        <ol className="fg-timeline">{view.rounds.map((r) => <RoundCard key={r.round} r={r} isAi={view.isAi} mock={view.mock} />)}</ol>
      )}
    </section>
  )
}

// ---- budget ledger ---------------------------------------------------------------------------------------------
function Ledger({ rec }: { rec: RecoveryRecord }) {
  const l = ledgerSegments(rec.pipeline)
  const ass = rec.assessment?.rollouts
  return (
    <section className="fg-card" data-testid="rec-ledger" aria-labelledby="rec-ledger-h">
      <h3 id="rec-ledger-h">Where the rollouts went</h3>
      {!rec.pipeline ? <p className="fg-dim">No search ledger was recorded.</p> : (
        <>
          <div className="fg-ledger" role="img" aria-label={`${l.used} of ${l.total} rollouts used: ${l.segments.map((s) => `${s.label} ${s.n}`).join(', ')}`}>
            {l.segments.filter((s) => s.n > 0).map((s) => <i key={s.key} className={`fg-seg fg-seg-${s.key}`} style={{ width: `${(s.n / Math.max(1, l.total)) * 100}%` }} title={`${s.label}: ${s.n}`} />)}
          </div>
          <ul className="fg-legend" data-testid="rec-ledger-legend">
            {l.segments.map((s) => <li key={s.key} data-seg={s.key}><i className={`fg-swatch fg-seg-${s.key}`} /> {s.label}: <b>{s.n}</b></li>)}
          </ul>
          <p className="fg-dim" data-testid="rec-ledger-note">
            {l.used} of {l.total} rollouts used{l.refunded > 0 ? `; ${l.refunded} reserved by probes and plans were refunded unspent` : ''}. Every arm in a comparison gets the same total budget.
            {ass ? ` Validation (${ass.validation ?? 0}) and confirmation (${ass.confirmation ?? 0}) rollouts run afterwards on held-out seeds and are not part of the search budget.` : ''}
          </p>
        </>
      )}
    </section>
  )
}

// ---- candidate -------------------------------------------------------------------------------------------------
function Candidate({ rec, version }: { rec: RecoveryRecord; version: CreatureVersion | null }) {
  const cand = rec.candidate
  if (!cand) return <section className="fg-card" data-testid="rec-candidate"><h3>The candidate</h3><p className="fg-dim">No candidate was produced.</p></section>
  const rows = editRows(cand.edits, version?.body as unknown as Record<string, unknown> | undefined, cand.body)
  const wv = version?.controllers.walk?.vector
  const cc = controllerChange(wv, cand.vector)
  return (
    <section className="fg-card" data-testid="rec-candidate" aria-labelledby="rec-candidate-h">
      <h3 id="rec-candidate-h">The candidate (picked by screening, judged only on held-out seeds)</h3>
      <b className="fg-rec-sub">Body</b>
      {rows.length === 0 ? <p className="fg-dim" data-testid="rec-no-body-edits">The body is unchanged. Only the walking controller differs.</p> : (
        <div className="table-scroll"><table data-testid="rec-edits"><thead><tr><td>body parameter</td><td>before</td><td>after</td><td>ratio</td></tr></thead>
          <tbody>{rows.map((e) => <tr key={e.param} data-param={e.param}><td className="fg-left">{e.label}</td><td>{fmtEditValue(e.before)}</td><td>{fmtEditValue(e.after)}</td><td>{fmtRatio(e.ratio)}</td></tr>)}</tbody></table></div>
      )}
      <b className="fg-rec-sub">Walking controller</b>
      <p className="fg-dim" data-testid="rec-ctrl-summary">
        {cc.hasBefore ? `${cc.changed} of ${cc.rows.length} walking parameters differ from this version's controller.` : 'This version has no walking controller of its own; the search started from the frozen R2 walking controller, so there is no per-parameter before value.'}
        {' '}Candidate source: {rec.candidate?.source}.
      </p>
      <div className="fg-gains" data-testid="rec-fp">
        {cc.rows.filter((r) => r.fp).map((r) => (
          <span key={r.name} className={`fg-chip ${Math.abs(r.after) > 1e-12 ? 'fg-chip-fp' : 'fg-chip-original'}`} data-testid={`rec-${r.name}`} data-active={Math.abs(r.after) > 1e-12}>
            {r.name} = {Number(r.after.toPrecision(4))}{Math.abs(r.after) > 1e-12 ? ' (foot placement active)' : ' (off)'}</span>
        ))}
      </div>
      <details className="fg-details"><summary>All {cc.rows.length} walking parameters</summary>
        <div className="table-scroll"><table><thead><tr><td>parameter</td><td>before</td><td>after</td></tr></thead>
          <tbody>{cc.rows.map((r) => <tr key={r.name} className={r.fp && Math.abs(r.after) > 1e-12 ? 'changed' : ''}><td className="fg-left">{r.name}</td><td>{r.before === null ? 'n/a' : Number(r.before.toPrecision(4))}</td><td>{Number(r.after.toPrecision(4))}</td></tr>)}</tbody></table></div>
      </details>
    </section>
  )
}

// ---- verification ----------------------------------------------------------------------------------------------
function Checks({ a }: { a: RecoveryAssessment }) {
  const c = a.confirmation
  if (!c.run || !c.checks) return <p className="fg-dim" data-testid="rec-confirm-skipped">Confirmation was not run{c.reason ? ` (${c.reason})` : ''}. It only runs for a candidate that passed the validation.</p>
  const k = c.checks
  const mark = (ok: boolean) => <span className={`fg-chip ${ok ? 'fg-chip-good' : 'fg-chip-bad'}`}>{ok ? 'PASSED' : 'FAILED'}</span>
  return (
    <ul className="fg-checks" data-testid="rec-confirm">
      <li data-check="walking_frac">{mark(k.walking_frac.passed)} walking on {Math.round(k.walking_frac.value * 100)}% of the {c.per_seed?.length ?? 0} confirmation seeds at {c.duration ?? 20} s (needs at least {Math.round(k.walking_frac.need * 100)}%)</li>
      <li data-check="median_speed">{mark(k.median_speed_upright.passed)} median upright speed {k.median_speed_upright.value.toFixed(3)} m/s (minimum {k.median_speed_upright.need.toFixed(3)} m/s)</li>
      <li data-check="body_contact">{mark(k.body_contact.passed)} body contact {k.body_contact.passed ? `stays under ${k.body_contact.max_frac} on every seed` : `above ${k.body_contact.max_frac} on seeds ${k.body_contact.seeds_over.join(', ')}`}</li>
    </ul>
  )
}

function SideBySide({ rec, seeds, rows }: { rec: RecoveryRecord; seeds: number[]; rows: { o: Map<number, RecoverySeedRow>; c: Map<number, RecoverySeedRow> } }) {
  const first = useMemo(() => seeds.find((s) => rows.o.get(s)?.outcome !== 'PASS' && rows.c.get(s)?.outcome === 'PASS') ?? seeds[0] ?? null, [seeds, rows])
  const [seed, setSeed] = useState<number | null>(first)
  const [runs, setRuns] = useState<{ id: string; label: string; run: RunPayload }[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => setSeed(first), [first, rec.id])
  useEffect(() => {
    if (seed === null) return
    let alive = true
    setRuns(null); setError(null)
    Promise.all([getRecoveryReplay(rec.id, 'original', seed), getRecoveryReplay(rec.id, 'candidate', seed)])
      .then(([o, c]) => {
        if (!alive) return
        setRuns([{ id: 'original', label: `ORIGINAL · ${rowWord(rows.o.get(seed))}`, run: o }, { id: 'candidate', label: `CANDIDATE · ${rowWord(rows.c.get(seed))}`, run: c }])
        const pb = usePlayback.getState()
        pb.setDuration(Math.max(o.duration, c.duration))
        pb.restart()
      })
      .catch((e: Error) => alive && setError(e.message))
    return () => { alive = false }
  }, [rec.id, seed]) // eslint-disable-line react-hooks/exhaustive-deps
  if (seed === null) return null
  const colors = ['#e5484d', '#4fd18b']
  return (
    <div className="fg-rec-compare" data-testid="rec-compare">
      <label className="fg-field fg-inline">
        <span>Validation seed</span>
        <select value={seed} onChange={(e) => setSeed(Number(e.target.value))} aria-label="validation seed to replay" data-testid="rec-seed">
          {seeds.map((s) => <option key={s} value={s}>{shortSeed(s)}: original {rowWord(rows.o.get(s))}, candidate {rowWord(rows.c.get(s))}</option>)}
        </select>
      </label>
      {error && <div className="error" role="alert" data-testid="rec-replay-error">Replay failed: {error}</div>}
      {!runs && !error && <div className="fg-skeleton skeleton" data-testid="rec-replay-loading" />}
      {runs && (
        <ReplayBoundary resetKey={`${rec.id}-${seed}`}>
          <div className="fg-pair fg-pair-2" data-testid="rec-viewports">{runs.map((r) => <Viewport key={r.id} closeup run={r.run} label={r.label} />)}</div>
          <Transport runs={runs.map((r, i) => ({ run: r.run, label: r.id, color: colors[i] }))} />
          <HeightChart runs={runs.map((r, i) => ({ run: r.run, label: r.id, color: colors[i] }))} />
          <p className="fg-dim">A fresh MuJoCo replay of one seed under the same conditions as the validation. One animation is not evidence; the per-seed strip above is.</p>
        </ReplayBoundary>
      )}
    </div>
  )
}

function Verification({ rec }: { rec: RecoveryRecord }) {
  const a = rec.assessment
  const maps = useMemo(() => ({ o: new Map((a?.validation.original ?? []).map((r) => [r.seed, r])), c: new Map((a?.validation.candidate ?? []).map((r) => [r.seed, r])) }), [a])
  if (!a) return <section className="fg-card" data-testid="rec-verification"><h3>Verification</h3><p className="fg-dim">No verification was run for this recovery.</p></section>
  const seeds = a.validation.candidate.map((r) => r.seed)
  const o = countWalking(a.validation.original)
  const c = countWalking(a.validation.candidate)
  return (
    <section className="fg-card" data-testid="rec-verification" aria-labelledby="rec-verify-h">
      <h3 id="rec-verify-h">Verification on held-out seeds</h3>
      <p className="fg-dim">The same {seeds.length} seeds and variation (stronger pushes, push-time jitter, friction) for the original and the candidate. The selection never saw them.</p>
      <div className="fg-facts" data-testid="rec-validation-counts">
        <div><span>{o.walking}/{o.n}</span>original walking</div>
        <div><span>{c.walking}/{c.n}</span>candidate walking</div>
      </div>
      <div className="fg-vstrip" role="list" aria-label="per-seed validation results" data-testid="rec-strip">
        {seeds.map((s) => (
          <div key={s} role="listitem" className="fg-vseed" data-seed={s} data-original={rowWord(maps.o.get(s))} data-candidate={rowWord(maps.c.get(s))}
            title={`seed ${s}: original ${rowWord(maps.o.get(s))}, candidate ${rowWord(maps.c.get(s))}`}>
            <small>{shortSeed(s)}</small>
            <span className={`fg-vcell tone-${rowTone(maps.o.get(s))}`}>O {rowWord(maps.o.get(s))}</span>
            <span className={`fg-vcell tone-${rowTone(maps.c.get(s))}`}>C {rowWord(maps.c.get(s))}</span>
          </div>
        ))}
      </div>
      <p className={`fg-verdict-text tone-${a.validation.verdict.status === 'VERIFIED_IMPROVEMENT' ? 'ok' : a.validation.verdict.status === 'WORSE' ? 'bad' : 'muted'}`} data-testid="rec-verdict" data-status={a.validation.verdict.status}>
        verdict_v1: {verdictText(a.validation.verdict)}
      </p>
      <Checks a={a} />
      {a.reasons.length > 0 && <ul className="fg-reasons" data-testid="rec-reasons">{a.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
      {(a.errors ?? []).length > 0 && <div className="error" role="alert" data-testid="rec-errors">Errored rollouts: {(a.errors ?? []).map((e) => `${e.arm} seed ${e.seed}: ${e.error}`).join('; ')}</div>}
      <SideBySide rec={rec} seeds={seeds} rows={maps} />
    </section>
  )
}

// ---- accept ----------------------------------------------------------------------------------------------------
function AcceptRecovery({ cid, rec, versions, onAccepted, onRunWalk }: {
  cid: string; rec: RecoveryRecord; versions: CreatureVersion[]; onAccepted: (c: Creature) => void; onRunWalk: (n: number) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const st = recoveryAcceptState(rec)
  const done = versions.find((v) => v.change?.recovery_id === rec.id)
  const next = Math.max(0, ...versions.map((v) => v.n)) + 1
  useEffect(() => setError(null), [rec.id])
  const accept = async () => {
    setBusy(true); setError(null)
    try { onAccepted(await acceptRecovery(cid, rec.id)) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <section className="fg-card fg-accept" data-testid="rec-accept" data-can-accept={st.allowed && !done} aria-labelledby="rec-accept-h">
      <h3 id="rec-accept-h">Accept</h3>
      {done ? (
        <div className="fg-note-box fg-accepted" role="status" data-testid="rec-accepted">
          <b>Accepted as v{done.n}.</b> The lineage records the change and that it was a full recovery.
          <button className="btn btn-simulate fg-small" data-testid="rec-run-walk" onClick={() => onRunWalk(done.n)}>Run walk challenge on v{done.n}</button>
        </div>
      ) : (
        <>
          {st.reason && <p className="fg-note-box" data-testid="rec-accept-blocked">{st.reason}</p>}
          {st.allowed && <p className="fg-dim">Only a full recovery (walking validated on held-out seeds and confirmed at 20 s) can become a new version. Nothing is accepted for you.</p>}
          {error && <div className="error" role="alert" data-testid="rec-accept-error">{error}</div>}
          <div className="fg-actions">
            <button className="btn btn-investigate" disabled={!st.allowed || busy} data-testid="rec-accept-btn" onClick={() => void accept()}>
              {busy ? 'Accepting...' : `Accept as version ${next}`}
            </button>
          </div>
        </>
      )}
    </section>
  )
}

// ---- the whole record --------------------------------------------------------------------------------------------
export function RecoveryView({ cid, rec, versions, onAccepted, onRunWalk }: {
  cid: string; rec: RecoveryRecord; versions: CreatureVersion[]; onAccepted: (c: Creature) => void; onRunWalk: (n: number) => void
}) {
  const prov = recoveryProvenance(rec.provenance)
  const head = recoveryHeadline(rec)
  const parent = versions.find((v) => v.n === rec.creature.n) ?? null
  const calls = rec.director_record?.calls ?? []
  return (
    <div className="fg-record fg-rec" data-testid="recovery-view" data-status={rec.status} data-provenance={rec.provenance}>
      <section className={`fg-card fg-rec-head fg-verdict-${head.tone}`} data-testid="rec-header" aria-label="recovery result">
        <div className={`fg-prov fg-prov-${rec.provenance}`} data-testid="rec-provenance">
          <ProvChip label={prov.label} tone={prov.tone} />
          <b data-testid="rec-model">{rec.model ?? 'no model'}</b>
          <span className="fg-dim">{prov.text}</span>
          <span className="fg-dim" data-testid="rec-cost">{modelCostText(rec.director_record)}</span>
        </div>
        <p className="fg-headline" role="status" data-testid="rec-status" data-status={rec.status}>{head.text}</p>
        <span className="fg-dim">Recovery of v{rec.creature.n} · {rec.budget.used ?? 'n/a'} of {rec.budget.total} search rollouts used{rec.scale === 'smoke' ? ' · smoke scale (test server)' : ''}</span>
        {calls.length > 0 && (
          <details className="fg-details" data-testid="rec-requests"><summary>Request ids and cost ({calls.length} calls)</summary>
            <div className="table-scroll"><table><thead><tr><td>#</td><td>request id</td><td>latency</td><td>tokens</td><td>cost</td><td>finish</td></tr></thead>
              <tbody>{calls.map((c, i) => <tr key={i}><td>{i}</td><td className="fg-left">{c.request_id ?? 'none'}{c.error ? ` (error: ${c.error})` : ''}</td><td>{c.latency_s != null ? `${c.latency_s.toFixed(1)} s` : 'n/a'}</td>
                <td>{c.usage?.total_tokens ?? 'n/a'}</td><td>{c.cost_usd != null ? `$${c.cost_usd.toFixed(4)}` : 'n/a'}</td><td>{c.finish_reason ?? 'n/a'}</td></tr>)}</tbody></table></div>
          </details>
        )}
        {rec.director === 'fix' && <span className="fg-dim">No model was called for this recovery.</span>}
      </section>
      {rec.error && <div className="error" role="alert" data-testid="rec-error">{rec.error}</div>}
      <Reasoning rec={rec} />
      <Ledger rec={rec} />
      <Candidate rec={rec} version={parent} />
      <Verification rec={rec} />
      <AcceptRecovery cid={cid} rec={rec} versions={versions} onAccepted={onAccepted} onRunWalk={onRunWalk} />
    </div>
  )
}

// ---- history ---------------------------------------------------------------------------------------------------
export function RecoveryList({ cid, nonce, openId, onOpen }: { cid: string; nonce: number; openId: string | null; onOpen: (id: string) => void }) {
  const [list, setList] = useState<RecoverySummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    listRecoveries(cid).then((l) => alive && setList(newestRecoveryFirst(l))).catch((e: Error) => alive && setError(e.message))
    return () => { alive = false }
  }, [cid, nonce])
  return (
    <section className="fg-card" data-testid="recovery-list" aria-label="walking recoveries of this creature">
      <h3>Walking recoveries</h3>
      {error && <div className="error" role="alert">{error}</div>}
      {list && list.length === 0 && <p className="fg-dim" data-testid="recovery-list-empty">None yet. A walk challenge that fails offers "Recover walking".</p>}
      <ul className="fg-ilist">
        {(list ?? []).map((s) => {
          const p = recoveryProvenance(s.provenance)
          return (
            <li key={s.id}>
              <button className={`fg-linkbtn ${s.id === openId ? 'on' : ''}`} data-testid="recovery-item" data-id={s.id} data-status={s.status} onClick={() => onOpen(s.id)}>
                <b>{s.id}</b> <span className="fg-dim">v{s.creature.n} · {new Date(s.created).toLocaleString()}</span>
              </button>
              <span className="fg-chips"><ProvChip label={p.label} tone={p.tone} /><span className={`fg-chip fg-rec-st-${recoveryTone(s.status)}`}>{recoverySummaryText(s)}</span></span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// ---- start + progress + record --------------------------------------------------------------------------------------
export function RecoveryPanel({ cid, version, versions, run, status, openId, onOpenId, onChanged, onAccepted, onRunWalk }: {
  cid: string
  version: CreatureVersion
  versions: CreatureVersion[]
  run: ChallengeRun | null
  status: ForgeStatus | null
  openId: string | null
  onOpenId: (id: string | null) => void
  onChanged: () => void
  onAccepted: (c: Creature) => void
  onRunWalk: (n: number) => void
}) {
  const live = status?.live_available === true
  const [director, setDirector] = useState<'ai' | 'fix'>('ai')
  const [budget, setBudget] = useState<number>(RECOVERY_DEFAULT_BUDGET)
  const [phase, setPhase] = useState<'idle' | 'starting' | 'running' | 'unavailable' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [rid, setRid] = useState<string | null>(null)
  const [record, setRecord] = useState<RecoveryRecord | null>(null)
  const [recordError, setRecordError] = useState<string | null>(null)
  const poll = useJobPoll(jobId)
  const offer = canOfferRecovery(run, version.n)

  useEffect(() => { setPhase('idle'); setJobId(null); setMessage(null) }, [run?.run_id, version.n])

  const start = async () => {
    setPhase('starting'); setMessage(null); setRecord(null); onOpenId(null)
    try {
      const r = await startRecovery(cid, version.n, director === 'fix' ? { director: 'fix', budget } : { director: 'ai', mode: live ? 'live' : 'scripted', budget })
      setJobId(r.job_id); setRid(r.recovery_id); setPhase('running')
    } catch (e) {
      setMessage((e as Error).message)
      setPhase(e instanceof ForgeApiError && e.status === 503 ? 'unavailable' : 'error')
    }
  }

  const st = poll.job?.status
  useEffect(() => {
    if (!st || !isTerminal(st)) return
    onChanged()
    if (rid) onOpenId(rid)
  }, [st]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setRecord(null); setRecordError(null)
    if (!openId) return
    let alive = true
    getRecovery(openId).then((r) => alive && setRecord(r)).catch((e: Error) => alive && setRecordError(e.message))
    return () => { alive = false }
  }, [openId])

  const running = phase === 'running' && (!poll.job || !isTerminal(poll.job.status))
  const busy = phase === 'starting' || running
  const stages = recoveryStageStates(poll.job, poll.events)
  const bar = recoveryBudgetBar(poll.job, budget)
  const failedJob = phase === 'running' && (poll.job?.status === 'failed' || poll.job?.status === 'cancelled')
  if (!offer && !openId && phase === 'idle') return null
  return (
    <section className="fg-card fg-rec-panel" data-testid="recovery" aria-label="Recover walking">
      <h3>Recover walking</h3>
      {offer && (
        <>
          <p className="fg-dim">This walk challenge was not passed. A search tunes the walking controller and, if the director asks for it, the body, then a held-out validation and a harder 20 s confirmation decide whether the creature really walks. A small improvement is reported as an improvement, never as a recovery.</p>
          <fieldset className="fg-rec-form" disabled={busy}>
            <legend className="sr-only">Director and budget</legend>
            <label className="fg-check"><input type="radio" name="rec-director" checked={director === 'ai'} onChange={() => setDirector('ai')} data-testid="rec-dir-ai" />
              <span>AI director {live ? <b className="fg-live-tag">LIVE</b> : <b className="fg-mock-tag">SCRIPTED MOCK (not a model)</b>}
                <small className="fg-dim"> {live ? 'A model chooses the probes and plans.' : 'Live model calls are off on this server, so the fixed rule’s decisions are shown in the AI layout, labelled as not a model.'}</small></span></label>
            <label className="fg-check"><input type="radio" name="rec-director" checked={director === 'fix'} onChange={() => setDirector('fix')} data-testid="rec-dir-fix" />
              <span>Fixed engineering rule (no AI) <small className="fg-dim">The same search with a rule instead of a director.</small></span></label>
            <label className="fg-field fg-inline"><span>Budget (rollouts)</span>
              <select value={budget} onChange={(e) => setBudget(Number(e.target.value))} aria-label="search budget in rollouts" data-testid="rec-budget">
                {RECOVERY_BUDGETS.map((b) => <option key={b} value={b}>{b}{b === RECOVERY_DEFAULT_BUDGET ? ' (default)' : ''}</option>)}
              </select>
              <small>Every arm in a comparison gets the same total budget.</small></label>
          </fieldset>
          <div className="fg-actions">
            <button className="btn btn-investigate" disabled={busy} data-testid="recover-btn" onClick={() => void start()}>{phase === 'starting' ? 'Starting...' : 'Recover walking'}</button>
            {running && poll.job && <button className="btn btn-ghost" data-testid="rec-cancel" onClick={() => void cancelForgeJob(poll.job!.id).catch(() => undefined)}>Cancel</button>}
          </div>
        </>
      )}
      {phase === 'unavailable' && <div className="fg-note-box" role="status" data-testid="recovery-unavailable">Walking recovery is not available: {message}</div>}
      {phase === 'error' && <div className="error" role="alert" data-testid="recovery-error">The recovery could not start: {message}</div>}
      {phase === 'running' && (
        <div className="fg-progress" data-testid="rec-progress" data-job-status={poll.job?.status ?? 'starting'}>
          <div className="fg-progress-head"><b>Recovering walking</b><span>{recoveryPhaseText(poll.job, poll.events)}</span></div>
          <ol className="fg-stages" data-testid="rec-stages">{RECOVERY_STAGES.map((s) => <li key={s} className={`fg-stage fg-stage-${stages[s]}`} data-stage={s} data-state={stages[s]}>{RECOVERY_STAGE_LABEL[s]}</li>)}</ol>
          {bar && (
            <div data-testid="rec-budget-bar" data-fraction={bar.fraction.toFixed(2)}>
              <div className="fg-bar" role="progressbar" aria-label={bar.label} aria-valuemin={0} aria-valuemax={bar.total} aria-valuenow={bar.done}><i style={{ width: `${bar.fraction * 100}%` }} /></div>
              <small className="fg-dim">{bar.label}: {bar.done} of {bar.total}</small>
            </div>
          )}
          {poll.error && <small className="fg-bad">Cannot reach the server for progress: {poll.error}</small>}
        </div>
      )}
      {failedJob && <div className="error" role="alert" data-testid="recovery-failed">The recovery {poll.job?.status === 'cancelled' ? 'was cancelled' : 'failed'}{poll.job?.error ? `: ${poll.job.error}` : ''}</div>}
      {recordError && !failedJob && <div className="error" role="alert" data-testid="recovery-record-error">Could not load the recovery: {recordError}</div>}
      {openId && !record && !recordError && <div className="fg-skeleton skeleton" />}
      {record && <RecoveryView cid={cid} rec={record} versions={versions} onAccepted={onAccepted} onRunWalk={onRunWalk} />}
    </section>
  )
}
