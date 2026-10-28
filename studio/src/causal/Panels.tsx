import { Block, Notice, OriginBadge } from '../lab/Badges'
import { Chip } from './Investigation'
import {
  categoryLabel, diagnosisVerdict, fmtCost, fmtNum, fmtPct, memoryUse, memoryVerdictInfo, selfClaim, statusInfo,
} from './causalLogic'
import type { CausalRecord } from './causalTypes'

export function MemoryPanel({ rec, open, onToggle }: { rec: CausalRecord; open: string | null; onToggle: (id: string | null) => void }) {
  const use = memoryUse(rec)
  return (
    <section className="cz-panel" data-testid="cz-memory" id="cz-memory">
      <h2>Retrieved memory</h2>
      {use.length === 0 ? (
        <Notice testid="cz-memory-none">
          No memory items were retrieved for this investigation{rec.memory?.error ? ` (memory error: ${rec.memory.error})` : ''}, so nothing in it came from earlier robots or mechanism cards.
        </Notice>
      ) : (
        <>
          <p className="dim">Items retrieved from earlier robots or mechanism cards are hearsay: the model judged each one and had to test it before relying on it. Links in the timeline open the item here.</p>
          <ul className="cz-mem">
            {use.map((u) => {
              const v = u.verdict ? memoryVerdictInfo(u.verdict) : null
              return (
                <li key={u.item.id} id={`cz-mem-${u.item.id}`} data-testid={`cz-mem-${u.item.id}`}>
                  <button type="button" className="cz-memhead" aria-expanded={open === u.item.id} onClick={() => onToggle(open === u.item.id ? null : u.item.id)}>
                    <b>{u.item.id}</b> <Chip tone="muted">{u.item.kind}</Chip>
                    {v ? <Chip tone={v.tone}>model: {v.label}</Chip> : <Chip tone="muted">no verdict recorded</Chip>}
                    {u.citedInSteps.length > 0 && <small>mentioned in step {u.citedInSteps.join(', ')}</small>}
                  </button>
                  {open === u.item.id && (
                    <div className="cz-memtext">
                      <p><b>Retrieved text.</b> {u.item.text}</p>
                      {u.reason && <Block kind="model" title={`The model's verdict${u.step != null ? ` (step ${u.step})` : ''}`}><p>{u.reason}</p></Block>}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </>
      )}
    </section>
  )
}

export function ClaimsAndVerification({ rec }: { rec: CausalRecord }) {
  const st = statusInfo(rec.verification.status)
  const claim = selfClaim(rec)
  const ps = rec.prediction_summary
  const fin = rec.final
  const r = rec.verification.rollouts ?? {}
  return (
    <section className="cz-panel cz-two" data-testid="cz-verdict">
      <div className="cz-claims" data-testid="cz-claims">
        <h2>What the AI claimed</h2>
        <p className="cz-sub">Self-reported, from the model's own steps. Not independent.</p>
        {fin?.diagnosis_category ? (
          <p>Final diagnosis: <b>{categoryLabel(fin.diagnosis_category)}</b>{fin.confidence != null ? ` (self-reported confidence ${fmtNum(fin.confidence, 2)})` : ''}. It ended by: {fin.ended_by?.replace(/_/g, ' ') ?? 'n/a'}.</p>
        ) : <p>The investigation ended without a final diagnosis{fin?.ended_by ? ` (${fin.ended_by.replace(/_/g, ' ')})` : ''}.</p>}
        {fin?.explanation && <Block kind="model" title="Its explanation"><p>{fin.explanation}</p></Block>}
        {claim.trainWalking.map((t, i) => <p key={i}>Repair with <code>{t.tool}</code>: walking on the training seeds <b>{t.before} → {t.after}</b>{t.of != null ? ` of ${t.of}` : ''}.</p>)}
        {ps && (
          <p data-testid="cz-predacc">Predictions scored before/after each experiment: <b>{ps.n_correct}</b> of <b>{ps.n_scored}</b> correct ({fmtPct(ps.accuracy)}).
            {ps.chance_three_way != null && <> For reference, guessing one of three directions at random gives {fmtPct(ps.chance_three_way)}{ps.majority_observed_baseline != null ? `, and always answering the most common outcome gives ${fmtPct(ps.majority_observed_baseline)}` : ''}.</>}</p>
        )}
      </div>
      <div className="cz-verified" data-testid="cz-verification">
        <h2>Independent verification</h2>
        <p className="cz-sub">Measured by MuJoCo on hidden seeds the AI never saw. The AI could not influence it.</p>
        <p className="cz-bigstatus"><Chip tone={st.tone} testid="cz-status">{st.label}</Chip> <OriginBadge kind="measured" /></p>
        <p>Walking on <b>{fmtPct(rec.verification.walking_frac)}</b> of the validation starts{r.validation != null ? ` (${r.validation} rollouts)` : ''}{r.confirmation ? `, with ${r.confirmation} further confirmation rollouts` : ''}.</p>
        {(rec.verification.reasons ?? []).length > 0 && <ul>{rec.verification.reasons!.map((x, i) => <li key={i}>{x}</li>)}</ul>}
        <small className="dim">{rec.verification.note}</small>
      </div>
    </section>
  )
}

export function EvaluationOnly({ rec }: { rec: CausalRecord }) {
  const ev = rec.evaluation_only
  return (
    <details className="cz-panel cz-eval" data-testid="cz-eval">
      <summary>Evaluation only: the ground truth the AI never saw</summary>
      <Notice tone="warn">{ev.note}</Notice>
      <dl>
        <dt>Injected fault</dt><dd><code>{ev.fault}</code>, severity {ev.severity}</dd>
        <dt>Injected mechanism (taxonomy)</dt><dd>{categoryLabel(ev.injected_category)}</dd>
        <dt>Repair tool built for this fault</dt><dd>{ev.matching_tool ?? 'n/a'}</dd>
        <dt>The AI's final diagnosis</dt><dd>{categoryLabel(ev.diagnosis_category)}</dd>
      </dl>
      <p><b>{diagnosisVerdict(ev)}</b> A correct repair without the right diagnosis is possible, and the reverse.</p>
    </details>
  )
}

export function NoAiComparison({ rec }: { rec: CausalRecord }) {
  if (!rec.no_ai_comparison.length) return null
  return (
    <section className="cz-panel" data-testid="cz-noai">
      <h2>No AI comparison, same robot</h2>
      <p className="dim">Fixed rules or random search with no language model, on the same robot, budget and independent verification.</p>
      <table className="cz-pred">
        <thead><tr><th>Method (no AI)</th><th>Verified outcome</th><th>Walking</th><th>Rollouts used</th></tr></thead>
        <tbody>
          {rec.no_ai_comparison.map((b) => {
            const s = statusInfo(b.status)
            return <tr key={b.policy}><td>{b.policy}</td><td><Chip tone={s.tone}>{s.label}</Chip></td><td>{fmtPct(b.walking_frac)}</td><td>{b.rollouts_used ?? 'n/a'}</td></tr>
          })}
        </tbody>
      </table>
    </section>
  )
}

export function Provenance({ rec }: { rec: CausalRecord }) {
  const l = rec.llm
  return (
    <footer className="cz-prov dim" data-testid="cz-prov">
      <p>
        Record {rec.id} · policy {rec.source.policy}{rec.config.thinking ? ' (model thinking enabled)' : ''} · model {l?.model ?? rec.config.model ?? 'n/a'} ({rec.config.provenance ?? 'n/a'}) ·
        prompt {rec.config.prompt_version ?? 'n/a'} · {l?.calls ?? 0} model calls, {fmtCost(l?.cost_usd)}{l?.latency_s ? `, ${l.latency_s.toFixed(0)} s` : ''}
        {l?.tokens ? `, ${l.tokens.prompt + l.tokens.completion} tokens` : ''}.
      </p>
      <p>Source: {rec.source.file} line {rec.source.line}. This page shows a trimmed copy: system prompt {rec.config.system_prompt ? `(sha256 ${rec.config.system_prompt.sha256.slice(0, 12)}…, ${rec.config.system_prompt.length} characters)` : 'not recorded'}
        and each step's input message are kept only as hashes; the full text is in the source file.</p>
    </footer>
  )
}
