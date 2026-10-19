import { useEffect, useState, type ReactElement } from 'react'
import { getScientistRecord, getScientistRecords, getScientistReplay } from '../api'
import { Notice } from '../lab/Badges'
import { ReplaySection } from '../causal/CausalLab'
import { Chip } from '../causal/Investigation'
import { fmtCost, fmtPct, statusInfo } from '../causal/causalLogic'
import { actorInfo, evidenceLine, hypothesisLabel, scientistHeadline, stepTitle, structureLabel } from './scientistLogic'
import type { BeliefSnapshot, ScientistIndex, ScientistRecord, Step } from './scientistTypes'
import '../causal/causal.css'
import './scientist.css'

function Words({ s }: { s: Step }) {
  if (!s.scientist) return null
  return (
    <div className="sc-words" data-testid="sc-words">
      <p><b>Understanding.</b> {s.scientist.understanding}</p>
      {s.scientist.uncertainty && <p><b>Still unknown.</b> {s.scientist.uncertainty}</p>}
      <p><b>Why this action.</b> {s.scientist.why}</p>
    </div>
  )
}

function Result({ s }: { s: Step }) {
  const r = s.result
  const rows: ReactElement[] = []
  if (r.refused) rows.push(<p key="ref" className="cz-bad">Refused by the instruments: {r.refused}</p>)
  for (const h of r.proposals?.added ?? []) {
    rows.push(<p key={`h-${h.pid}`} className="sc-hyp">Hypothesis <b>{hypothesisLabel(h.pid)}</b>: {h.rank ? `simulated against all data, weight ${h.weight.toFixed(3)}, rank ${h.rank}` : 'simulated against all data and rejected (far worse than the leading explanations)'}</p>)
  }
  if (s.action.action === 'experiment' && r.ok) {
    rows.push(<p key="eig">Expected information gain {r.eig != null ? r.eig.toFixed(2) : 'n/a'} nats (best available {r.best_eig != null ? r.best_eig.toFixed(2) : 'n/a'}).{r.measured ? ` Measured: ${Object.entries(r.measured).map(([k, v]) => `${k.replace(/_/g, ' ')} ${v == null ? 'n/a' : Number(v).toFixed(2)}`).join(', ')}.` : ''}</p>)
  }
  if (r.ran) rows.push(<p key="ran">The engine ran: {r.ran.length ? r.ran.join(', ') : 'nothing (its stopping rule already held)'}</p>)
  if (r.ranking) rows.push(<p key="rank">Tool ranking on the simulator: {r.ranking.map((t) => `${t.tool}${t.cma_walking != null ? ` (${t.cma_walking}/4)` : ''}`).join(', ')}</p>)
  if (r.evidence) {
    rows.push(<p key="ev">Design {r.design}: {evidenceLine(r.evidence)}</p>)
    if (r.evidence.contradiction) rows.push(<p key="con" className="cz-bad">Contradiction: {r.evidence.contradiction}</p>)
  }
  if (r.before && r.after) rows.push(<p key="as">Belief before: {r.before.map(([st, w]) => `${structureLabel(st)} ${w.toFixed(2)}`).join('; ')} → after: {r.after.map(([st, w]) => `${structureLabel(st)} ${w.toFixed(2)}`).join('; ')}</p>)
  if (r.posterior && s.action.action !== 'assimilate') rows.push(<p key="post" className="dim">Belief now: {r.posterior.slice(0, 3).map(([st, w]) => `${structureLabel(st)} ${w.toFixed(2)}`).join('; ')}</p>)
  return <div className="sc-result">{rows}</div>
}

function StepCard({ s }: { s: Step }) {
  const a = actorInfo(s.actor)
  return (
    <li className="cz-step" data-testid={`sc-step-${s.seq}`}>
      <span className="cz-dot" aria-hidden="true" />
      <div className="cz-step-head static">
        <h3>{stepTitle(s)}</h3>
        <Chip tone={a.tone}>{a.label}</Chip>
        <small>{s.plant_cost} robot trials · {s.twin_cost} simulations</small>
      </div>
      <div className="cz-step-body">
        <Words s={s} />
        <Result s={s} />
      </div>
    </li>
  )
}

function BeliefChart({ history }: { history: BeliefSnapshot[] }) {
  return (
    <section className="cz-panel" data-testid="sc-belief">
      <h2>How the belief changed</h2>
      <p className="dim">Posterior weight of each explanation after each step, computed by the belief engine from simulations of the hypotheses against the measurements.</p>
      <ol className="sc-belief">
        {history.map((h, i) => (
          <li key={i}>
            <span className="sc-belief-label">{h.label.replace(/^after_/, 'after ').replace(/_/g, ' ')}</span>
            <span className="sc-bars">
              {h.structures.slice(0, 4).map((x, j) => (
                <span key={j} className={`sc-bar sc-bar-${j}`} style={{ width: `${Math.max(2, x.w * 100)}%` }} title={`${structureLabel(x.structure)} ${x.w.toFixed(3)}`}>
                  {x.w >= 0.15 ? `${structureLabel(x.structure)} ${x.w.toFixed(2)}` : ''}
                </span>
              ))}
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}

function RecordView({ id, index }: { id: string; index: ScientistIndex }) {
  const [rec, setRec] = useState<ScientistRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setRec(null); setError(null)
    getScientistRecord(id).then((r) => live && setRec(r)).catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [id])
  if (error) return <div className="state error" role="alert"><b>This record could not be loaded</b><span>{error}</span></div>
  if (!rec) return <div className="skeleton" style={{ height: 360 }} aria-label="Loading record" />
  const st = statusInfo(rec.verification.status)
  const ev = rec.evaluation_only
  return (
    <div className="cz-record" data-testid="sc-record">
      <p className={`cz-headline cz-head-${st.tone}`} data-testid="sc-headline">{scientistHeadline(rec)}</p>
      <ReplaySection id={rec.id} seeds={index.replay.seeds} note={index.replay.note} status={rec.verification.status} getReplay={getScientistReplay} />
      <section className="cz-panel">
        <h2>The investigation, decision by decision</h2>
        <p className="dim">Dashed text is Nemotron's own reasoning, recorded before each action. Everything else is an instrument result: measurements on the robot, simulations, information-gain estimates, optimiser output.</p>
        <ol className="cz-timeline sc-timeline">{rec.steps.map((s) => <StepCard key={s.seq} s={s} />)}</ol>
      </section>
      <BeliefChart history={rec.belief_history} />
      {rec.memory_views.length > 0 && (
        <section className="cz-panel"><h2>Memory</h2>
          <p className="dim">Dossiers shown on the last turn (ranked by applicability checks on this robot's data): {rec.memory_views[0].shown.map(([d, sc]) => `${d} (${sc.toFixed(2)})`).join(', ')}. Applied: {(rec.memory_uses ?? []).map((u) => u.dossier).join(', ') || 'none'}.</p>
        </section>
      )}
      <section className="cz-two">
        <div className="cz-verified"><h2>Independent verification</h2>
          <p className="cz-bigstatus"><Chip tone={st.tone}>{st.label}</Chip> {fmtPct(rec.verification.walking_frac)} of hidden starts walk</p>
          <p className="dim">The scientist never sees these trials. {rec.verification.reasons.join('; ')}</p>
        </div>
        <div><h2>What it cost</h2>
          <p>{rec.costs.plant_used} of {rec.costs.plant_total} robot trials · {rec.costs.twin_used} of {rec.costs.twin_total} simulations · {rec.costs.llm_calls} model calls · {fmtCost(rec.costs.cost_usd)}</p>
        </div>
      </section>
      <details className="cz-eval" data-testid="sc-eval"><summary>Evaluation only (hidden from the scientist)</summary>
        <p className="dim">{ev.note}</p>
        <dl><dt>Injected deviation</dt><dd>{structureLabel(ev.injected_structure)} ({ev.family.replace(/_/g, ' ')}, {ev.severity_multiple}× its failure threshold)</dd>
          <dt>Final belief</dt><dd>{structureLabel(ev.final_belief)} ({ev.final_belief_mass.toFixed(2)}); weight on the truth {ev.mass_on_injected.toFixed(2)}</dd></dl>
      </details>
      <p className="cz-prov dim">Arm {rec.arm} · {rec.provenance} · model {rec.model.name ?? 'none'} · source {rec.source.file}:{rec.source.line}</p>
    </div>
  )
}

/** The autonomous scientist: Nemotron directs an investigation and uses deterministic instruments. Read-only recorded runs. */
export function ScientistLab() {
  const [index, setIndex] = useState<ScientistIndex | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  useEffect(() => {
    getScientistRecords().then((i) => { setIndex(i); setPicked(i.records[0]?.id ?? null) }).catch((e: Error) => setError(e.message))
  }, [])
  if (error) return <main><div className="state error" role="alert"><b>The recorded investigations could not be loaded</b><span>{error}</span></div></main>
  if (!index) return <main><div className="skeleton" style={{ height: 420 }} aria-label="Loading" /></main>
  if (!index.records.length) return <main className="causal"><Notice testid="sc-empty">No recorded investigations are installed. Export some with scripts/has_export_records.py.</Notice></main>
  return (
    <main className="causal" data-testid="scientist-lab">
      <section className="cz-hero">
        <h1>The AI scientist</h1>
        <p>Nemotron investigates a robot whose hidden damage nobody knows. It decides what it does not yet understand, writes executable explanations, orders experiments, notices when the physics contradicts it, engineers a repair with an optimiser, and decides when the evidence is strong enough. The simulator, a Bayesian belief engine and the optimiser are its instruments; an independent verification it never sees judges the result.</p>
        <p className="dim">Recorded development runs, including failures. Nothing here calls a model; replays are fresh simulations.</p>
      </section>
      <ul className="cz-list" aria-label="Recorded investigations">
        {index.records.map((r, i) => {
          const s = statusInfo(r.status)
          return (
            <li key={r.id}>
              <button type="button" className={`cz-card ${picked === r.id ? 'on' : ''}`} aria-pressed={picked === r.id} data-testid={`sc-card-${i}`} onClick={() => setPicked(r.id)}>
                <span className="cz-card-top"><Chip tone={s.tone}>{s.label}</Chip><small>{fmtPct(r.walking_frac)} of hidden starts walk</small></span>
                <span className="cz-card-meta">arm {r.arm} · {r.n_steps} decisions · {r.n_experiments} experiments · {r.llm_calls ?? 0} model calls · {fmtCost(r.cost_usd)}</span>
              </button>
            </li>
          )
        })}
      </ul>
      {picked && <RecordView key={picked} id={picked} index={index} />}
    </main>
  )
}
