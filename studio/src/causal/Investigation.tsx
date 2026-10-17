import { useState, type ReactNode } from 'react'
import { Block, OriginBadge } from '../lab/Badges'
import {
  categoryLabel, directionWord, fmtDelta, fmtNum, hypothesisTone, ledgerAt, linkifyIds, predictionRows, repairLine, scoreTally, scoreTone,
  statusCounts, stepErrors, stepExperiments, stepTitle, walkingChange, type HypothesisState,
} from './causalLogic'
import type { CausalRecord, Experiment, NewHypothesis, Step } from './causalTypes'

/** Model text with every mention of a retrieved memory item turned into a link that opens the item. */
export function ModelText({ text, memoryIds, onItem }: { text: string; memoryIds: string[]; onItem: (id: string) => void }) {
  return (
    <>
      {linkifyIds(text, memoryIds).map((seg, i) => seg.item
        ? <button key={i} type="button" className="cz-memlink" onClick={() => onItem(seg.item!)} title="Show this retrieved memory item">{seg.text}</button>
        : <span key={i}>{seg.text}</span>)}
    </>
  )
}

export const Chip = ({ tone, children, title, testid }: { tone: string; children: ReactNode; title?: string; testid?: string }) =>
  <span className={`cz-chip cz-chip-${tone}`} title={title} data-testid={testid}>{children}</span>

function StatusPath({ state }: { state: HypothesisState }) {
  return (
    <span className="cz-path" aria-label={`status path ${state.path.join(' then ')}`}>
      {state.path.map((p, i) => <span key={i}>{i > 0 && <i aria-hidden="true">→</i>}<Chip tone={hypothesisTone(p)}>{p}</Chip></span>)}
    </span>
  )
}

function HypothesisCard({ h, state, memoryIds, onItem }: { h: NewHypothesis; state: HypothesisState | undefined; memoryIds: string[]; onItem: (id: string) => void }) {
  return (
    <article className="cz-hyp" data-testid={`cz-hyp-${h.id}`}>
      <header>
        <b>{h.id}</b>
        <Chip tone="cat">{categoryLabel(h.category)}</Chip>
        {state ? <StatusPath state={state} /> : <Chip tone="muted">not yet created at this step</Chip>}
        <small>confidence when created {fmtNum(h.confidence, 2)} (self-reported)</small>
      </header>
      <p><b>Mechanism.</b> <ModelText text={h.mechanism} memoryIds={memoryIds} onItem={onItem} /></p>
      <p><b>Causal chain.</b> <ModelText text={h.causal_chain} memoryIds={memoryIds} onItem={onItem} /></p>
      {h.evidence.length > 0 && <p className="cz-ev"><b>Cited evidence.</b> {h.evidence.join(', ')}</p>}
    </article>
  )
}

function PredictionTable({ e }: { e: Experiment }) {
  const rows = predictionRows(e)
  if (!rows.length) return <p className="dim">No predictions were registered for this experiment.</p>
  return (
    <table className="cz-pred" data-testid={`cz-pred-${e.id}`}>
      <caption>Predictions registered before the experiment ran, then scored against the measurement</caption>
      <thead><tr><th>Hypothesis</th><th>Quantity</th><th>Predicted</th><th>Measured</th><th>Before → after</th><th>Score</th></tr></thead>
      <tbody>
        {rows.map(({ pred, score }, i) => (
          <tr key={i}>
            <td>{pred.hypothesis}</td>
            <td><code>{pred.quantity}</code></td>
            <td>{directionWord(pred.direction)}</td>
            <td>{score ? directionWord(score.observed) : 'n/a'}</td>
            <td>{score && score.base != null ? `${fmtNum(score.base)} → ${fmtNum(score.new)} (${fmtDelta(score.delta)})` : 'n/a'}</td>
            <td><Chip tone={scoreTone(score?.status)}>{score ? (score.status === 'unscored' ? 'not scored' : score.status) : 'not scored'}</Chip></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function ExperimentCard({ e, memoryIds, onItem }: { e: Experiment; memoryIds: string[]; onItem: (id: string) => void }) {
  const w = walkingChange(e)
  const t = scoreTally(e.scoring)
  if (e.kind === 'repair') {
    return (
      <article className="cz-exp cz-repair" data-testid={`cz-exp-${e.id}`}>
        <header><b>{e.id}</b><Chip tone="repair">repair</Chip><OriginBadge kind="measured" hint="Rollouts counted and run by the benchmark workbench" /></header>
        <p>{repairLine(e)}.</p>
        {w && <p className="cz-walk">Training seeds walking after the repair: <b>{w.before} → {w.after}</b>{w.of != null ? ` of ${w.of}` : ''}. <small>These are seeds the AI could see; the independent check below uses hidden ones.</small></p>}
        {e.predicted_n_walking != null && <p>The AI predicted {e.predicted_n_walking} training seeds would walk{e.prediction_error != null ? `; it was off by ${e.prediction_error}` : ''}.</p>}
        {e.train_fitness != null && <p className="dim">Training fitness {fmtNum(e.train_fitness)}{e.is_current_best ? ' (best design so far)' : ''}.</p>}
      </article>
    )
  }
  return (
    <article className="cz-exp" data-testid={`cz-exp-${e.id}`}>
      <header><b>{e.id}</b><Chip tone="cf">experiment</Chip><span className="cz-change">change: <code>{e.change ?? 'none recorded'}</code></span><small>{e.cost} rollouts</small></header>
      {e.purpose && <Block kind="model" title="Purpose, as the model wrote it"><p><ModelText text={e.purpose} memoryIds={memoryIds} onItem={onItem} /></p></Block>}
      <PredictionTable e={e} />
      <p className="cz-tally">
        {t.total ? <>Scored: <b>{t.correct}</b> correct, <b>{t.incorrect}</b> incorrect{t.unscored ? `, ${t.unscored} not scored` : ''}. </> : null}
        {w && <>Walking on the observation seeds: <b>{w.before} → {w.after}</b>{w.of != null ? ` of ${w.of}` : ''}.</>}
      </p>
    </article>
  )
}

function TransitionRow({ t }: { t: NonNullable<Step['hypothesis_transitions']>[number] }) {
  if (t.from === null) return null
  const changed = t.from !== t.to
  return (
    <li className="cz-trans" data-testid={`cz-trans-${t.id}`}>
      <b>{t.id}</b> {changed ? <><Chip tone={hypothesisTone(t.from)}>{t.from}</Chip><i aria-hidden="true">→</i><Chip tone={hypothesisTone(t.to)}>{t.to}</Chip></> : <>stays <Chip tone={hypothesisTone(t.to)}>{t.to}</Chip></>}
      {t.experiments.length > 0 && <small> citing {t.experiments.join(', ')}</small>}
      {t.cited_predictions && t.cited_predictions.n_scored > 0 && <small> · its own predictions there: {t.cited_predictions.n_correct} of {t.cited_predictions.n_scored} correct</small>}
      <q>{t.reason}</q>
    </li>
  )
}

function StepView({ rec, step, selected, onSelect, ledger, memoryIds, onItem }: {
  rec: CausalRecord; step: Step; selected: boolean; onSelect: () => void; ledger: HypothesisState[]; memoryIds: string[]; onItem: (id: string) => void
}) {
  const p = step.parsed
  const exps = stepExperiments(rec, step)
  const trans = (step.hypothesis_transitions ?? []).filter((t) => t.from !== null)
  const errs = stepErrors(step)
  const conclude = p?.conclude?.[0]
  const mem = p?.memory_assessments ?? step.memory_assessments ?? []
  return (
    <section className={`cz-step ${selected ? 'sel' : ''}`} data-testid={`cz-step-${step.step}`} aria-current={selected ? 'step' : undefined}>
      <button type="button" className="cz-step-head" onClick={onSelect} aria-pressed={selected}>
        <span className="cz-dot" aria-hidden="true" />
        <h3>{stepTitle(step)}</h3>
        {step.remaining_after != null && <small>{step.remaining_after} rollouts left</small>}
        {step.repaired && <Chip tone="warn" title="The first reply broke the response format and was asked for again once">format retry</Chip>}
      </button>
      <div className="cz-step-body">
        {p?.result_reading && (
          <Block kind="model" title="What the model read from the results" hint="Text written by the language model. Not checked by MuJoCo.">
            <p className="cz-reading" data-testid={`cz-reading-${step.step}`}><ModelText text={p.result_reading} memoryIds={memoryIds} onItem={onItem} /></p>
          </Block>
        )}
        {trans.length > 0 && (
          <div className="cz-block">
            <h4>Hypothesis status changes <OriginBadge kind="model" hint="The model chose the status and wrote the reason" /></h4>
            <ul className="cz-translist">{trans.map((t, i) => <TransitionRow key={i} t={t} />)}</ul>
          </div>
        )}
        {(p?.new_hypotheses ?? []).length > 0 && (
          <div className="cz-block">
            <h4>New hypotheses <OriginBadge kind="model" /></h4>
            {p!.new_hypotheses!.map((h) => <HypothesisCard key={h.id} h={h} state={ledger.find((s) => s.id === h.id)} memoryIds={memoryIds} onItem={onItem} />)}
          </div>
        )}
        {mem.length > 0 && (
          <div className="cz-block">
            <h4>Retrieved memory, as the model judged it <OriginBadge kind="model" /></h4>
            <ul className="cz-translist">
              {mem.map((m) => <li key={m.item}><button type="button" className="cz-memlink" onClick={() => onItem(m.item)}>{m.item}</button> <Chip tone="muted">{m.verdict.replace(/_/g, ' ')}</Chip><q>{m.reason}</q></li>)}
            </ul>
          </div>
        )}
        {exps.map((e) => <ExperimentCard key={e.id} e={e} memoryIds={memoryIds} onItem={onItem} />)}
        {conclude && (
          <Block kind="model" title={`Conclusion: ${categoryLabel(conclude.diagnosis_category)}`} hint="The model's own diagnosis and confidence. The independent check below is separate.">
            <p><ModelText text={conclude.explanation} memoryIds={memoryIds} onItem={onItem} /></p>
            <small className="dim">Self-reported confidence {fmtNum(conclude.confidence, 2)}. It chose to submit: {conclude.submit}.</small>
          </Block>
        )}
        {errs.length > 0 && (
          <div className="cz-block cz-bad" role="status">
            <h4>This reply could not be used</h4>
            <ul>{errs.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </div>
        )}
      </div>
    </section>
  )
}

export function Ledger({ rec, step, onStep }: { rec: CausalRecord; step: number; onStep: (k: number) => void }) {
  const states = ledgerAt(rec.hypotheses ?? {}, step)
  const counts = statusCounts(states)
  const last = rec.steps.length
  return (
    <aside className="cz-ledger" data-testid="cz-ledger" aria-label="Hypothesis ledger">
      <h3>Hypotheses after step {step}</h3>
      <div className="cz-ledger-nav">
        <button type="button" className="btn btn-ghost" disabled={step <= 1} onClick={() => onStep(step - 1)} aria-label="previous step">‹</button>
        <input type="range" min={1} max={Math.max(1, last)} value={step} onChange={(e) => onStep(Number(e.target.value))} aria-label="ledger step" />
        <button type="button" className="btn btn-ghost" disabled={step >= last} onClick={() => onStep(step + 1)} aria-label="next step">›</button>
      </div>
      <p className="cz-counts" data-testid="cz-counts">
        {Object.entries(counts).map(([k, n]) => <Chip key={k} tone={hypothesisTone(k)}>{n} {k}</Chip>)}
      </p>
      <ul>
        {states.map((s) => (
          <li key={s.id} data-testid={`cz-ledger-${s.id}`} data-status={s.status}>
            <details>
              <summary><b>{s.id}</b> <Chip tone={hypothesisTone(s.status)}>{s.status}</Chip> <span>{categoryLabel(s.category)}</span></summary>
              <p>{s.mechanism}</p>
              {s.changedAt > s.created && <p className="dim">Last changed at step {s.changedAt}{s.experiments.length ? `, citing ${s.experiments.join(', ')}` : ''}: <q>{s.reason}</q></p>}
              <StatusPath state={s} />
            </details>
          </li>
        ))}
      </ul>
      <p className="dim cz-note">Statuses are the model's own verdicts. A repair that works does not by itself prove a cause.</p>
    </aside>
  )
}

export function Timeline({ rec, memoryIds, onItem }: { rec: CausalRecord; memoryIds: string[]; onItem: (id: string) => void }) {
  const [sel, setSel] = useState(Math.max(1, rec.steps.length))
  const ledger = ledgerAt(rec.hypotheses ?? {}, sel)
  const obs = rec.initial_observation
  return (
    <div className="cz-timeline-wrap">
      <div className="cz-timeline" data-testid="cz-timeline">
        <section className="cz-step cz-step0">
          <div className="cz-step-head static"><span className="cz-dot" aria-hidden="true" /><h3>Start: observe the failure</h3></div>
          <div className="cz-step-body">
            <p>The AI watched the faulty robot on {obs ? (obs.n_walking ?? 0) + (obs.n_fell ?? 0) : rec.config.n_obs ?? 'its'} observation seeds
              {obs ? <>: <b>{obs.n_walking ?? 0}</b> walked, <b>{obs.n_fell ?? 0}</b> fell. </> : '. '}
              It was given the robot's body and controller numbers and a rollout budget of {rec.budget.total ?? rec.config.budget} (this record used {rec.budget.used ?? 'n/a'}); it was never told what is wrong.</p>
          </div>
        </section>
        {rec.steps.map((s) => (
          <StepView key={s.step} rec={rec} step={s} selected={s.step === sel} onSelect={() => setSel(s.step)} ledger={ledger} memoryIds={memoryIds} onItem={onItem} />
        ))}
      </div>
      <Ledger rec={rec} step={sel} onStep={setSel} />
    </div>
  )
}
