import { useEffect, useState } from 'react'
import { getForgeArmReplay } from '../api'
import { usePlayback } from '../store'
import { HeightChart, Transport } from '../Timeline'
import type { RunPayload } from '../types'
import { Viewport } from '../Viewport'
import { armChip, armList, armScores, median, VERDICT_TONE, verdictText } from './forgeLogic'
import type { InvestigationRecord } from './forgeTypes'
import { ReplayBoundary } from './ReplayBoundary'

export function ProvChip({ label, tone }: { label: string; tone: string }) {
  return <span className={`fg-chip fg-chip-${tone}`} data-testid="prov-chip">{label}</span>
}

/** Original and the selected arm on the same seed, driven by the one shared playback clock. Verdict text is the record's. */
export function ArenaCompare({ record, armId }: { record: InvestigationRecord; armId: string }) {
  const seeds = record.seeds?.validate ?? []
  const [seed, setSeed] = useState<number | null>(seeds[0] ?? null)
  const [pair, setPair] = useState<[RunPayload, RunPayload] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const arms = armList(record)
  const arm = arms.find((a) => a.arm_id === armId)
  const verdict = record.verdicts?.[armId]

  useEffect(() => {
    if (seed === null) return
    let alive = true
    setPair(null)
    setError(null)
    Promise.all([getForgeArmReplay(record.id, 'original', seed), getForgeArmReplay(record.id, armId, seed)])
      .then((p) => {
        if (!alive) return
        setPair(p)
        const pb = usePlayback.getState()
        pb.setDuration(Math.max(p[0].duration, p[1].duration))
        pb.restart()
      })
      .catch((e: Error) => alive && setError(e.message))
    return () => { alive = false }
  }, [record.id, armId, seed])

  const rows = arms
    .map((a) => ({ a, scores: armScores(record, a.arm_id) }))
    .filter((r) => r.scores.length > 0)
    .map((r) => ({ ...r, med: median(r.scores.map((s) => s.score)) }))
  const top = Math.max(1e-9, ...rows.map((r) => r.med ?? 0))

  return (
    <section className="fg-card fg-arena" data-testid="arena-compare">
      <h3>Original against {arm ? armChip(arm, record.provenance).label.toLowerCase() : armId}, same seed</h3>
      {seeds.length > 0 && (
        <label className="fg-field fg-inline">
          <span>Validation seed</span>
          <select value={seed ?? ''} onChange={(e) => setSeed(Number(e.target.value))} aria-label="validation seed">
            {seeds.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      )}
      {error && <div className="error" role="alert" data-testid="arena-replay-error">Replay failed: {error}</div>}
      {pair && (
        <ReplayBoundary resetKey={`${record.id}-${armId}-${seed}`}>
          <div className="fg-pair">
            <Viewport closeup run={pair[0]} label="ORIGINAL" />
            <Viewport closeup run={pair[1]} label={arm ? armChip(arm, record.provenance).label : armId} />
          </div>
          <Transport runs={[{ run: pair[0], label: 'original', color: '#e5484d' }, { run: pair[1], label: 'arm', color: '#4fd18b' }]} />
          <HeightChart runs={[{ run: pair[0], label: 'original', color: '#e5484d' }, { run: pair[1], label: 'arm', color: '#4fd18b' }]} />
        </ReplayBoundary>
      )}
      {rows.length > 0 && (
        <div className="fg-scorebars" data-testid="score-bars">
          <b>Median score on the validation seeds</b>
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
