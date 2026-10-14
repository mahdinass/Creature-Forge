import type { Change, Explanation } from '../sketch/freehandTypes'

export interface SandboxMeta { explanation: Explanation; approximated: Change[] | null }

/** Plain-language account of what happened to a drawn creature, from measurements (never a proven cause). */
export function SandboxResult({ meta, onEdit, onSliders, onInvestigate }: { meta: SandboxMeta; onEdit: () => void; onSliders: () => void; onInvestigate: () => void }) {
  const ex = meta.explanation
  const fell = ex.verdict === 'fell'
  return (
    <div className="panel sandbox-result" data-testid="sandbox-result" data-verdict={ex.verdict}>
      <span className="badge-exp">Your drawn creature</span>
      <h2 className={fell ? 'tone-bad' : 'tone-ok'} data-testid="sandbox-headline">{ex.headline}</h2>
      {meta.approximated && (
        <div className="approx-note" data-testid="sandbox-approximated">
          <b>Approximated, as you confirmed.</b> This is not exactly what you drew:
          <ul>{meta.approximated.map((c) => <li key={c.what}>{c.what}: {c.from} → {c.to}</li>)}</ul>
        </div>
      )}
      <ul className="reasons" data-testid="sandbox-reasons">
        {ex.reasons.map((r, i) => <li key={i} data-kind={r.kind}>{r.text}</li>)}
      </ul>
      {ex.design_notes.length > 0 && (
        <div className="design-notes" data-testid="sandbox-design-notes">
          <b>Unusual design choices</b>
          <ul>{ex.design_notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
      <small className="dim">{ex.caveat}</small>
      <div className="actions">
        <button className="btn btn-create" data-testid="edit-drawing" onClick={onEdit}>Edit the drawing</button>
        <button className="btn btn-ghost" onClick={onSliders}>Tune with sliders</button>
      </div>
      <p className="dim link-ai">Curious how an AI would investigate a failure like this? <button className="link" data-testid="to-ai" onClick={onInvestigate}>Open the recorded AI investigation</button>. It was run on a different robot, not on your drawing.</p>
    </div>
  )
}
