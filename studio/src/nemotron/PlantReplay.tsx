import { useEffect, useState } from 'react'
import { getNemotronReplay } from '../api'
import { ReplayBoundary } from '../forge/ReplayBoundary'
import { usePlayback } from '../store'
import { HeightChart, Transport } from '../Timeline'
import { Viewport } from '../Viewport'
import type { ReplayName, W2Payload } from './nemotronTypes'

export interface ReplayLane { name: ReplayName; label: string; color: string; outcome: (seed: number) => { text: string; ok: boolean } }

/** Damaged-plant replays from the fidelity-gated W2 export, synchronised on the shared playback clock. Only one PlantReplay
 *  is mounted at a time on the page (the clock is global). Nothing is simulated: the files are played back. */
export function PlantReplay({ lanes, seeds, seed, onSeed, note, testid }: {
  lanes: ReplayLane[]; seeds: number[]; seed: number; onSeed: (s: number) => void; note: string; testid: string
}) {
  const [runs, setRuns] = useState<W2Payload[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    setRuns(null); setError(null)
    Promise.all(lanes.map((l) => getNemotronReplay(l.name, seed))).then((rs) => {
      if (!alive) return
      setRuns(rs)
      const pb = usePlayback.getState()
      pb.setDuration(Math.max(...rs.map((r) => r.duration)))
      pb.restart()
    }).catch((e: Error) => alive && setError(e.message))
    return () => { alive = false }
  }, [lanes.map((l) => l.name).join(','), seed])   // eslint-disable-line react-hooks/exhaustive-deps

  const chart = runs?.map((run, i) => ({ run, label: lanes[i].label.toLowerCase(), color: lanes[i].color })) ?? []
  return (
    <div className="nm-replay" data-testid={testid}>
      <div className="nm-replay-bar">
        <span className="nm-recon">Reconstructed MuJoCo replay · damaged robot</span>
        <div className="nm-seeds" role="group" aria-label="start condition">
          {seeds.map((s) => (
            <button key={s} type="button" aria-pressed={s === seed} className={s === seed ? 'on' : ''} onClick={() => onSeed(s)}
              data-testid={`${testid}-seed-${s}`} title={lanes.map((l) => `${l.label}: ${l.outcome(s).text}`).join(' · ')}>
              {lanes.map((l) => <i key={l.name} className={l.outcome(s).ok ? 'ok' : 'bad'} style={{ ['--c' as string]: l.color }} />)}
            </button>
          ))}
        </div>
      </div>
      {error && <div className="error" role="alert" data-testid={`${testid}-error`}>Replay failed: {error}</div>}
      {!runs && !error && <div className="skeleton nm-replay-skel" />}
      {runs && (
        <ReplayBoundary resetKey={`${lanes.map((l) => l.name).join(',')}-${seed}`}>
          <div className={`nm-views nm-views-${runs.length}`}>
            {runs.map((run, i) => {
              const o = lanes[i].outcome(seed)
              return (
                <figure key={lanes[i].name} className="nm-view" style={{ ['--c' as string]: lanes[i].color }} data-testid={`${testid}-view-${lanes[i].name}`}>
                  <Viewport closeup run={run} label={`${lanes[i].label} · seed ${seed}`} />
                  <figcaption className={o.ok ? 'ok' : 'bad'}><b>{o.text}</b></figcaption>
                </figure>
              )
            })}
          </div>
          <Transport runs={chart} />
          <HeightChart runs={chart} />
        </ReplayBoundary>
      )}
      <p className="nm-small" data-testid={`${testid}-note`}>{note}</p>
    </div>
  )
}
