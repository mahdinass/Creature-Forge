import { useCallback, useEffect, useMemo, useState } from 'react'
import { getOverview, getWalkingReplay, getWalkingSummary } from '../api'
import { Overview } from '../overview/Overview'
import type { OverviewData } from '../overview/overviewTypes'
import { usePlayback } from '../store'
import type { Tab } from '../shell/nav'
import { Viewport } from '../Viewport'
import type { WalkingReplay, WalkingSummary } from '../walking/walkingTypes'
import './home.css'

type Which = 'r2_winner' | 'incumbent'
const reduceMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

/** The hero is a real MuJoCo replay of the committed walking controllers on one of the R2 evaluation seeds. */
function HeroStage({ summary }: { summary: WalkingSummary }) {
  const seed = summary.featured[0]
  const [which, setWhich] = useState<Which>('r2_winner')
  const [runs, setRuns] = useState<Partial<Record<Which, WalkingReplay>>>({})
  const [error, setError] = useState<string | null>(null)
  const [paused, setPaused] = useState(reduceMotion())
  const run = runs[which]

  const load = useCallback((w: Which) => {
    setError(null)
    getWalkingReplay(w, seed).then((r) => setRuns((p) => ({ ...p, [w]: r }))).catch((e: Error) => setError(e.message))
  }, [seed])
  useEffect(() => { load('r2_winner'); load('incumbent') }, [load])

  useEffect(() => {
    if (!run) return
    const pb = usePlayback.getState()
    pb.setDuration(run.duration)
    pb.setLoop(true)
    pb.setSpeed(1)
    if (reduceMotion()) pb.seek(Math.min(3, run.duration)); else pb.restart()
    return () => { usePlayback.getState().setLoop(false); usePlayback.getState().setSpeed(0.5) }
  }, [run])

  const m = run?.locomotion
  const caption = !run || !m ? '' : m.walking
    ? `${run.controller_label}: walks the full ${run.duration.toFixed(0)} s`
    : m.fell ? `${run.controller_label}: falls at ${m.fall_time?.toFixed(1)} s` : `${run.controller_label}: ${m.label.replace(/_/g, ' ')}`

  return (
    <div className="hero-stage" data-testid="hero-stage">
      {run ? <Viewport run={run} label="" bare className="hero-vp" /> : error ? (
        <div className="state error" role="alert"><b>The hero replay could not load</b><span>{error}</span><button className="btn btn-ghost" onClick={() => { load('r2_winner'); load('incumbent') }}>Try again</button></div>
      ) : <div className="skeleton hero-skeleton" aria-label="Running MuJoCo" />}
      <div className="hero-caption" data-testid="hero-caption" aria-live="polite">
        <div className="seg" role="tablist" aria-label="controller">
          <button role="tab" aria-selected={which === 'incumbent'} data-testid="hero-start" onClick={() => setWhich('incumbent')}>Starting controller</button>
          <button role="tab" aria-selected={which === 'r2_winner'} data-testid="hero-improved" onClick={() => setWhich('r2_winner')}>Improved controller</button>
        </div>
        <span className="cap-text">{caption || 'Running MuJoCo…'}</span>
        {paused && <button className="btn btn-ghost" onClick={() => { setPaused(false); usePlayback.getState().restart() }}>Play</button>}
        <small>Real MuJoCo replay · seed {seed} of the 150 untouched test seeds</small>
      </div>
    </div>
  )
}

function SeedDots({ s }: { s: WalkingSummary }) {
  const rows = useMemo(() => [
    { id: 'start', label: 'Starting controller', n: s.incumbent_walking, dots: s.seeds.map((x) => x.incumbent.walking) },
    { id: 'improved', label: 'Improved controller', n: s.winner_walking, dots: s.seeds.map((x) => x.winner.walking) },
  ], [s])
  return (
    <div className="seed-dots" data-testid="seed-dots">
      {rows.map((r) => (
        <div key={r.id} className="dot-row">
          <div className="dot-head"><b>{r.label}</b><span><b className="big">{r.n}</b> of {s.n} walk</span></div>
          <div className="dots" role="img" aria-label={`${r.label}: ${r.n} of ${s.n} test seeds walk`}>
            {r.dots.map((w, i) => <i key={i} className={w ? 'walks' : 'falls'} />)}
          </div>
        </div>
      ))}
      <p className="dot-note">Each dot is one test start. The improvement came from a classical optimiser, <b>not from an AI model</b>.</p>
    </div>
  )
}

function NemotronPreview({ o, go }: { o: OverviewData; go: (t: Tab) => void }) {
  const run = o.nemotron.recorded_runs.find((r) => r.kind === 'RECORDED_LIVE' && r.proposals.length > 0)
  const p = run?.proposals[0]
  const n = run?.n ?? 32
  const bars = run && p ? [
    { k: 'Unchanged controller', v: run.frozen_walking ?? 0, c: 'bar-frozen' },
    { k: 'With Nemotron’s edit', v: p.model_walking, c: 'bar-model' },
    { k: 'With a matched random edit', v: p.random_walking, c: 'bar-random' },
  ] : []
  return (
    <div className="nem-preview" data-testid="nemotron-preview">
      <ol className="flow" aria-label="how an investigation runs">
        {['A robot fails', 'The AI reads the measurements', 'It proposes a bounded change', 'MuJoCo tests the change', 'You see the verdict'].map((t, i) => <li key={t}><span>{i + 1}</span>{t}</li>)}
      </ol>
      {run && p && (
        <div className="nem-card">
          <div><span className="tag tag-model">Recorded real Nemotron call</span><h3>It proposed changing {p.edits.join(' and ')}</h3></div>
          <div className="outcome">
            {bars.map((b) => (
              <div className="orow" key={b.k}><span className="olabel">{b.k}</span><span className="otrack"><span className={`ofill ${b.c}`} style={{ width: `${(b.v / n) * 100}%` }} /></span><b>{b.v}/{n}</b></div>
            ))}
          </div>
          <p className="honest">A matched random edit did nearly as well. This shows the loop works, <b>not that the model beats random edits</b>; that comparison was not completed.</p>
          <button className="btn btn-investigate" data-testid="cta-ai-card" onClick={() => go('demo')}>Open the investigation</button>
        </div>
      )}
    </div>
  )
}

export function Home({ go }: { go: (t: Tab) => void }) {
  const [summary, setSummary] = useState<WalkingSummary | null>(null)
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    getWalkingSummary().then(setSummary).catch((e: Error) => setError(e.message))
    getOverview().then(setOverview).catch(() => undefined)
  }, [])
  return (
    <div className="home" data-testid="overview">
      <section className="hero" data-testid="hero">
        {summary ? <HeroStage summary={summary} /> : (
          <div className="hero-stage">{error
            ? <div className="state error" role="alert"><b>Walking records not found</b><span>{error}</span></div>
            : <div className="skeleton hero-skeleton" aria-label="Loading" />}</div>
        )}
        <div className="hero-copy">
          <h1>
            <span className="h1-line" style={{ ['--c' as string]: 'var(--create)' }}>Create.</span>
            <span className="h1-line" style={{ ['--c' as string]: 'var(--simulate)' }}>Simulate.</span>
            <span className="h1-line" style={{ ['--c' as string]: 'var(--investigate)' }}>Investigate.</span>
          </h1>
          <p>Draw a two-legged creature, drop it into a real physics engine, and see how an AI model investigates why robots fall.</p>
          <div className="hero-actions">
            <button className="btn btn-create btn-lg" data-testid="cta-draw" onClick={() => go('sketch')}>Draw a creature</button>
            <button className="btn btn-investigate btn-lg" data-testid="cta-ai" onClick={() => go('demo')}>Watch an AI investigation</button>
          </div>
        </div>
      </section>

      <section className="stages" aria-label="the three steps">
        <button className="stage s-create" onClick={() => go('sketch')}>
          <svg viewBox="0 0 120 70" aria-hidden="true"><path d="M20 55 C 30 20, 50 60, 60 30 S 90 50, 100 15" stroke="var(--create)" strokeWidth="3" fill="none" strokeLinecap="round" strokeDasharray="4 6" /></svg>
          <b>Create</b><span>Sketch a biped with the pen. Turn off the guides to try a terrible one.</span>
        </button>
        <button className="stage s-simulate" onClick={() => go('studio')}>
          <svg viewBox="0 0 120 70" aria-hidden="true"><path d="M20 60 L50 12 L70 40 L100 62" stroke="var(--simulate)" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <b>Simulate</b><span>Push it in real physics and read, in plain words, why it fell.</span>
        </button>
        <button className="stage s-investigate" onClick={() => go('demo')}>
          <svg viewBox="0 0 120 70" aria-hidden="true"><g fill="var(--investigate)"><rect x="22" y="30" width="14" height="30" rx="3" opacity=".4" /><rect x="52" y="16" width="14" height="44" rx="3" /><rect x="82" y="22" width="14" height="38" rx="3" opacity=".7" /></g></svg>
          <b>Investigate</b><span>Follow an AI proposal from a failing robot to the simulator’s verdict.</span>
        </button>
      </section>

      {summary && (
        <section className="band" data-testid="r2-band">
          <div className="band-head">
            <h2>A robot taught to walk</h2>
            <p>The starting controller walked on {summary.incumbent_walking} of {summary.n} fresh starts. After local tuning it walks on {summary.winner_walking}.</p>
            <button className="btn btn-simulate" data-testid="cta-walking" onClick={() => go('locomotion')}>See it in the Walking lab</button>
          </div>
          <SeedDots s={summary} />
        </section>
      )}

      {overview && (
        <section className="band band-model" data-testid="ai-band">
          <div className="band-head">
            <h2>How an AI investigation works</h2>
            <p>A recorded, real model call: what it changed, and what the simulator measured.</p>
          </div>
          <NemotronPreview o={overview} go={go} />
        </section>
      )}

      <details className="research" data-testid="research-details">
        <summary>Research notes and caveats</summary>
        <Overview go={(t) => go(t)} embedded />
      </details>
    </div>
  )
}
