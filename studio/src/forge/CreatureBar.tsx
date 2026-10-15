import { lineageRows, originLabel } from './forgeLogic'
import type { Creature } from './forgeTypes'

/** Name, version chip and lineage of the creature on the bench. Older versions can be viewed or made current again. */
export function CreatureBar({ creature, viewN, onView, onMakeCurrent, busy, error }: {
  creature: Creature
  viewN: number
  onView: (n: number) => void
  onMakeCurrent: (n: number) => void
  busy: boolean
  error: string | null
}) {
  const rows = lineageRows(creature)
  return (
    <section className="fg-card fg-creature" data-testid="creature-bar" aria-label="creature and versions">
      <div className="fg-creature-head">
        <h2 data-testid="creature-name">{creature.name}</h2>
        <span className="fg-vchip" data-testid="version-chip" title={viewN === creature.current ? 'The current version' : 'Viewing an older version'}>v{viewN}</span>
        {viewN !== creature.current && <span className="fg-note">not the current version (v{creature.current})</span>}
      </div>
      <details className="fg-lineage" open={rows.length > 1} data-testid="lineage">
        <summary>{rows.length === 1 ? 'Version history: just the one you drew' : `Version history: ${rows.length} versions`}</summary>
        <ol>
          {rows.map((r) => (
            <li key={r.n} className={`${r.n === viewN ? 'viewing' : ''} ${r.current ? 'current' : ''}`} style={{ paddingLeft: `${Math.min(r.depth, 4) * 12}px` }} data-testid={`lineage-v${r.n}`}>
              <button className="fg-linkbtn" aria-current={r.n === viewN ? 'true' : undefined} onClick={() => onView(r.n)}>
                <b>v{r.n}</b>
              </button>
              <span className={`fg-origin fg-origin-${r.origin}`}>{originLabel(r.origin)}</span>
              {r.parent !== null && <span className="fg-dim">from v{r.parent}</span>}
              <span className="fg-summary">{r.summary}</span>
              {r.current ? <em className="fg-current-tag">current</em> : (
                <button className="btn btn-ghost fg-small" disabled={busy} data-testid={`make-current-${r.n}`} onClick={() => onMakeCurrent(r.n)}>Make current</button>
              )}
            </li>
          ))}
        </ol>
      </details>
      {error && <div className="error" role="alert">{error}</div>}
    </section>
  )
}
