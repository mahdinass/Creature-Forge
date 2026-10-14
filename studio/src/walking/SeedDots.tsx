import { useMemo } from 'react'
import type { WalkingSummary } from './walkingTypes'
import './walking.css'

/** One dot per untouched test seed: filled walks, hollow does not. Optionally clickable to replay that seed. */
export function SeedDots({ s, picked, onPick }: { s: WalkingSummary; picked?: number; onPick?: (seed: number) => void }) {
  const rows = useMemo(() => [
    { id: 'start', label: 'Starting controller', n: s.incumbent_walking, dots: s.seeds.map((x) => ({ seed: x.seed, walks: x.incumbent.walking })) },
    { id: 'improved', label: 'Improved controller', n: s.winner_walking, dots: s.seeds.map((x) => ({ seed: x.seed, walks: x.winner.walking })) },
  ], [s])
  return (
    <div className="seed-dots" data-testid="seed-dots">
      {rows.map((r) => (
        <div key={r.id} className="dot-row">
          <div className="dot-head"><b>{r.label}</b><span><b className="big">{r.n}</b> of {s.n} walk</span></div>
          <div className="dots" role="img" aria-label={`${r.label}: ${r.n} of ${s.n} test seeds walk`}>
            {r.dots.map((d) => (onPick ? (
              <button key={d.seed} className={`${d.walks ? 'walks' : 'falls'} ${picked === d.seed ? 'sel' : ''}`} title={`seed ${d.seed}: ${d.walks ? 'walks' : 'does not walk'}`} aria-label={`seed ${d.seed}`} onClick={() => onPick(d.seed)} />
            ) : <i key={d.seed} className={d.walks ? 'walks' : 'falls'} />))}
          </div>
        </div>
      ))}
      <p className="dot-note">Each dot is one test start. The improvement came from a classical optimiser, <b>not from an AI model</b>.</p>
    </div>
  )
}

