import { useEffect, useState } from 'react'
import { getForgeArmReplay } from '../api'
import { usePlayback } from '../store'
import { HeightChart, Transport } from '../Timeline'
import type { RunPayload } from '../types'
import { Viewport } from '../Viewport'
import { armChip, armList, armScores, median, validationTriplet, VERDICT_TONE, verdictText } from './forgeLogic'
import type { InvestigationRecord } from './forgeTypes'
import { ReplayBoundary } from './ReplayBoundary'

export function ProvChip({ label, tone }: { label: string; tone: string }) {
  return <span className={`fg-chip fg-chip-${tone}`} data-testid="prov-chip">{label}</span>
}

/** Original and the selected arm (optionally its matched twin) on the same held-out seed, driven by the one shared playback clock. */
export function ArenaCompare({ record, armId }: { record: InvestigationRecord; armId: string }) {
  const seeds = record.seeds?.validate ?? []
  const arms = armList(record)
  const arm = arms.find((a) => a.arm_id === armId)
  const twin = arm?.source !== 'random_baseline' && arm?.arm_id === record.selection?.ai ? validationTriplet(record).twin : null
  const [seed, setSeed] = useState<number | null>(seeds[0] ?? null)
  const [withTwin, setWithTwin] = useState(false)
  const [runs, setRuns] = useState<{ id: string; label: string; run: RunPayload }[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const verdict = record.verdicts?.[armId]
  const twinId = withTwin && twin ? twin.arm_id : null
  const label = (id: string) => (id === 'original' ? 'ORIGINAL' : armChip(arms.find((a) => a.arm_id === id) ?? { source: 'heuristic' }, record.provenance).label)

  useEffect(() => {
    if (seed === null) return
    let alive = true
    setRuns(null)
    setError(null)
    const ids = ['original', armId, ...(twinId ? [twinId] : [])]
    Promise.all(ids.map((id) => getForgeArmReplay(record.id, id, seed)))
      .then((rs) => {
        if (!alive) return
        setRuns(rs.map((run, i) => ({ id: ids[i], label: label(ids[i]), run })))
        const pb = usePlayback.getState()
        pb.setDuration(Math.max(...rs.map((r) => r.duration)))
        pb.restart()
      })
      .catch((e: Error) => alive && setError(e.message))
    return () => { alive = false }
  }, [record.id, armId, seed, twinId]) // eslint-disable-line react-hooks/exhaustive-deps

  const rows = arms
    .map((a) => ({ a, scores: armScores(record, a.arm_id) }))
    .filter((r) => r.scores.length > 0)
    .map((r) => ({ ...r, med: median(r.scores.map((s) => s.score)) }))
  const top = Math.max(1e-9, ...rows.map((r) => r.med ?? 0))
  const colors = ['#e5484d', '#4fd18b', '#f2b441']

  return (
    <section className="fg-card fg-arena" data-testid="arena-compare">
      <h3>The original and {arm ? `${armChip(arm, record.provenance).label.toLowerCase()} ${arm.arm_id}` : armId}, same held-out seed</h3>
      <div className="fg-actions">
        {seeds.length > 0 && (
          <label className="fg-field fg-inline">
            <span>Held-out seed</span>
            <select value={seed ?? ''} onChange={(e) => setSeed(Number(e.target.value))} aria-label="held-out seed" data-testid="arena-seed">
              {seeds.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        )}
        {twin && (
          <label className="fg-check"><input type="checkbox" checked={withTwin} onChange={(e) => setWithTwin(e.target.checked)} data-testid="arena-twin-toggle" /> Also show the matched random twin ({twin.arm_id})</label>
        )}
      </div>
      {error && <div className="error" role="alert" data-testid="arena-replay-error">Replay failed: {error}</div>}
      {!runs && !error && seed !== null && <div className="fg-skeleton skeleton" data-testid="arena-loading" />}
      {runs && (
        <ReplayBoundary resetKey={`${record.id}-${armId}-${seed}-${twinId}`}>
          <div className={`fg-pair fg-pair-${runs.length}`} data-testid="arena-viewports">
            {runs.map((r) => <Viewport key={r.id} closeup run={r.run} label={r.label} />)}
          </div>
          <Transport runs={runs.map((r, i) => ({ run: r.run, label: r.label.toLowerCase(), color: colors[i] }))} />
          <HeightChart runs={runs.map((r, i) => ({ run: r.run, label: r.label.toLowerCase(), color: colors[i] }))} />
        </ReplayBoundary>
      )}
      {rows.length > 0 && (
        <div className="fg-scorebars" data-testid="score-bars">
          <b>Median score on the held-out seeds</b>
          {rows.map(({ a, med, scores }) => (
            <div key={a.arm_id} className="fg-scorerow">
              <span><ProvChip {...armChip(a, record.provenance)} /> {a.arm_id}</span>
              <i className="fg-track"><i style={{ width: `${((med ?? 0) / top) * 100}%` }} /></i>
              <b>{med === null ? 'n/a' : med.toFixed(2)}</b><small className="fg-dim">{scores.length} seeds</small>
            </div>
          ))}
        </div>
      )}
      <p className={`fg-verdict-text tone-${VERDICT_TONE[verdict?.status ?? 'NOT_VERIFIED']}`} data-testid="arena-verdict" data-status={verdict?.status ?? 'none'}>
        {verdictText(verdict)}
      </p>
    </section>
  )
}
