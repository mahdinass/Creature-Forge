import { useEffect, useRef, useState } from 'react'
import { getWalkingReplay, getWalkingSummary } from '../api'
import { Locomotion } from '../locomotion/Locomotion'
import { usePlayback } from '../store'
import { Transport } from '../Timeline'
import { Viewport } from '../Viewport'
import { SeedDots } from './SeedDots'
import type { WalkingReplay, WalkingSummary } from './walkingTypes'
import './walking.css'

type Which = 'incumbent' | 'r2_winner'
type Pair = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; a: WalkingReplay; b: WalkingReplay }

const chip = (r: WalkingReplay) => (r.locomotion.walking ? { t: 'walks the whole 10 s', c: 'ok' } : r.locomotion.fell ? { t: `falls at ${r.locomotion.fall_time?.toFixed(1)} s`, c: 'bad' } : { t: r.locomotion.label.replace(/_/g, ' '), c: 'warn' })
const committedText = (r: WalkingReplay) => (r.committed ? (r.committed.walking ? 'walked' : r.committed.fall_time ? `fell at ${r.committed.fall_time.toFixed(1)} s` : r.committed.label.replace(/_/g, ' ')) : 'not in the committed record')

/** Robot first: the starting walking controller and the tuned one on the same start, then the numbers. */
export function WalkingLab() {
  const [summary, setSummary] = useState<WalkingSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [seed, setSeed] = useState<number | null>(null)
  const [pair, setPair] = useState<Pair>({ status: 'loading' })
  const cache = useRef(new Map<string, WalkingReplay>())

  useEffect(() => { getWalkingSummary().then((s) => { setSummary(s); setSeed(s.featured[0]) }).catch((e: Error) => setError(e.message)) }, [])
  useEffect(() => {
    if (seed === null) return
    let live = true
    setPair({ status: 'loading' })
    const get = async (w: Which) => {
      const k = `${w}|${seed}`
      const hit = cache.current.get(k)
      if (hit) return hit
      const r = await getWalkingReplay(w, seed)
      cache.current.set(k, r)
      return r
    }
    Promise.all([get('incumbent'), get('r2_winner')]).then(([a, b]) => {
      if (!live) return
      setPair({ status: 'ready', a, b })
      const pb = usePlayback.getState()
      pb.setDuration(Math.max(a.duration, b.duration)); pb.setSpeed(0.5); pb.restart()
    }).catch((e: Error) => live && setPair({ status: 'error', message: e.message }))
    return () => { live = false }
  }, [seed])

  if (error) return <main><div className="state error" role="alert" data-testid="walking-error"><b>The walking records could not be loaded</b><span>{error}</span></div></main>
  if (!summary || seed === null) return <main><div className="skeleton" style={{ height: 420 }} aria-label="Loading" /></main>
  const idx = summary.featured.indexOf(seed)

  return (
    <main className="walking" data-testid="walking-lab">
      <section className="wl-hero">
        <div className="wl-copy">
          <h1>Teach it to walk</h1>
          <p>The same robot, the same start. On the left, the walking controller we began with. On the right, the one found by tuning its parameters with a classical optimiser.</p>
          <div className="wl-big" data-testid="wl-numbers">
            <div><b>{summary.incumbent_walking}</b><span>of {summary.n} starts walk</span><small>starting controller</small></div>
            <div className="arrow" aria-hidden="true">→</div>
            <div className="up"><b>{summary.winner_walking}</b><span>of {summary.n} starts walk</span><small>improved controller</small></div>
          </div>
          <p className="dim attrib" data-testid="wl-attribution">{summary.attribution}</p>
        </div>
        <div className="wl-stage">
          <div className="wl-bar">
            <span className="dim">Start {seed}{idx >= 0 ? ' (the starting controller falls here)' : ''}</span>
            {summary.featured.length > 1 && (
              <div className="seg" role="group" aria-label="examples where the starting controller falls">
                {summary.featured.slice(0, 4).map((f, i) => <button key={f} aria-pressed={f === seed} className={f === seed ? 'on' : ''} data-testid={`wl-example-${i}`} onClick={() => setSeed(f)}>Example {i + 1}</button>)}
              </div>
            )}
          </div>
          {pair.status === 'ready' ? (
            <div className="duo" data-testid="wl-replay">
              {([pair.a, pair.b] as const).map((r, i) => {
                const c = chip(r)
                return (
                  <div className="duo-cell" key={i}>
                    <Viewport run={r} label={r.controller_label} closeup />
                    <span className={`result-chip ${c.c}`} data-testid={`wl-result-${i}`}>{c.t}</span>
                  </div>
                )
              })}
            </div>
          ) : pair.status === 'error' ? (
            <div className="state error" role="alert"><b>The replay could not run</b><span>{pair.message}</span><button className="btn btn-ghost" onClick={() => setSeed(seed)}>Try again</button></div>
          ) : <div className="duo"><div className="skeleton duo-skel" /><div className="skeleton duo-skel" /><span className="loading-note">Running MuJoCo…</span></div>}
          {pair.status === 'ready' && <Transport runs={[{ run: pair.a, label: 'start', color: '#ff5d6c' }, { run: pair.b, label: 'improved', color: '#4fd18b' }]} />}
          {pair.status === 'ready' && (
            <p className="dim wl-prov" data-testid="wl-provenance">
              Committed record (measured on the evidence machine): starting controller {committedText(pair.a)}, improved controller {committedText(pair.b)}. This replay is a fresh MuJoCo run on this computer.
            </p>
          )}
        </div>
      </section>

      <section className="wl-dots">
        <h2>Every test start</h2>
        <p className="dim">Click any dot to watch that start. {summary.paired.winner_only} starts that the old controller failed are walked by the new one; {summary.paired.incumbent_only} go the other way.</p>
        <SeedDots s={summary} picked={seed} onPick={setSeed} />
      </section>

      <details className="advanced" data-testid="walking-advanced">
        <summary>Advanced results: how the controller was found, and the earlier search history</summary>
        <div className="wl-how">
          <h3>How it improved</h3>
          <ul>
            <li>A classical local search (random-subset perturbations, an initiation grid and a (1+8) evolution strategy) adjusted 15 controller parameters around the working controller.</li>
            <li>The test starts were untouched while it was tuned. Both controllers were then run on the same {summary.n} starts, with identical physics.</li>
            <li>The result is for this one robot body and this distribution of starts. Outcomes were measured on Linux; replays here run on your machine.</li>
          </ul>
        </div>
        <Locomotion />
      </details>
    </main>
  )
}
