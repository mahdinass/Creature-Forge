import { useEffect, useState } from 'react'
import { paramDiffs, proposalOutcome, type ParamDiff } from './demoLogic'
import type { DemoRun } from './demoTypes'

const fmt = (x: number) => (Math.abs(x) >= 100 ? x.toFixed(0) : Math.abs(x) >= 10 ? x.toFixed(1) : x.toFixed(3))

/** One parameter on its allowed range: the tick is where it was, the glowing marker is where the edit moved it. */
export function ParamTrack({ d, tone }: { d: ParamDiff; tone: 'model' | 'random' }) {
  const [moved, setMoved] = useState(false)
  useEffect(() => { const id = requestAnimationFrame(() => setMoved(true)); return () => cancelAnimationFrame(id) }, [])
  const shown = moved ? d.uAfter : d.uBefore
  const lo = Math.min(d.uBefore, d.uAfter)
  const hi = Math.max(d.uBefore, d.uAfter)
  return (
    <div className={`ptrack ${d.changed ? 'changed' : ''} ptrack-${tone}`} data-testid={`ptrack-${d.name}`} data-changed={d.changed}>
      <div className="pt-head">
        <b>{d.name}</b> <span className="dim">{d.meaning}</span>
        <span className="pt-val">{d.changed ? <>{fmt(d.before)} → <b>{fmt(d.after)}</b></> : fmt(d.before)}</span>
      </div>
      <div className="pt-rail" role="img" aria-label={`${d.name}: ${d.changed ? `${fmt(d.before)} to ${fmt(d.after)}` : fmt(d.before)} within ${fmt(d.lower)} to ${fmt(d.upper)}`}>
        {d.changed && <span className="pt-span" style={{ left: `${lo * 100}%`, width: `${moved ? (hi - lo) * 100 : 0}%` }} />}
        <span className="pt-before" style={{ left: `${d.uBefore * 100}%` }} />
        {d.changed && <span className="pt-after" style={{ left: `${shown * 100}%` }} />}
      </div>
      <div className="pt-bounds dim"><span>{fmt(d.lower)}</span><span>allowed range</span><span>{fmt(d.upper)}</span></div>
      {d.reflected && <small className="tone-warn">The requested step left the range, so the verifier reflected it at the bound.</small>}
    </div>
  )
}

export function Diffs({ run, slot, who }: { run: DemoRun; slot: number; who: 'model' | 'random' }) {
  const all = paramDiffs(run, slot, who)
  const changed = all.filter((d) => d.changed)
  const rest = all.filter((d) => !d.changed)
  return (
    <div className="diffs">
      {changed.map((d) => <ParamTrack key={d.name} d={d} tone={who} />)}
      {rest.length > 0 && (
        <details>
          <summary>{rest.length} other controller parameters stay fixed</summary>
          <div className="diffs-rest">{rest.map((d) => <ParamTrack key={d.name} d={d} tone={who} />)}</div>
        </details>
      )}
    </div>
  )
}

export function OutcomeBars({ run, slot }: { run: DemoRun; slot: number }) {
  const o = proposalOutcome(run, slot)
  if (!o) return null
  const rows = [
    { key: 'frozen', label: 'Unchanged controller', v: o.frozen, cls: 'bar-frozen' },
    { key: 'model', label: 'With the model’s edit', v: o.model, cls: 'bar-model' },
    { key: 'random', label: 'With a matched random edit', v: o.random, cls: 'bar-random' },
  ]
  return (
    <div className="outcome" data-testid="story-outcome">
      {rows.map((r) => (
        <div key={r.key} className="orow" data-testid={`outcome-${r.key}`}>
          <span className="olabel">{r.label}</span>
          <span className="otrack"><span className={`ofill ${r.cls}`} style={{ width: `${(r.v / o.n) * 100}%` }} /></span>
          <b>{r.v}/{o.n}</b><span className="dim"> walk</span>
        </div>
      ))}
    </div>
  )
}

