import { useCallback, useEffect, useState } from 'react'
import { getPhase0, getSchema, simulate } from './api'
import { Lab } from './lab/Lab'
import { Locomotion } from './locomotion/Locomotion'
import { parseDeepLink } from './lab/labLogic'
import { Metrics } from './Metrics'
import { ParamPanel, type PushSettings } from './ParamPanel'
import { SketchEditor } from './SketchEditor'
import { HeightChart, Transport } from './Timeline'
import { Viewport } from './Viewport'
import { fmtPct } from './playback'
import { usePlayback } from './store'
import type { Params, Phase0, RunPayload, Schema } from './types'

type Tab = 'studio' | 'compare' | 'lab' | 'locomotion' | 'sketch'

export default function App() {
  const q = new URLSearchParams(window.location.search)
  const [tab, setTab] = useState<Tab>((['studio', 'compare', 'lab', 'locomotion', 'sketch'] as Tab[]).find((t) => t === q.get('tab')) ?? 'studio')
  const link = parseDeepLink(window.location.search)
  const [schema, setSchema] = useState<Schema | null>(null)
  const [phase0, setPhase0] = useState<Phase0 | null>(null)
  const [body, setBody] = useState<Params | null>(null)
  const [push, setPush] = useState<PushSettings>({ enabled: true, force: 25 })
  const [seed, setSeed] = useState(0)
  const [run, setRun] = useState<RunPayload | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fatal, setFatal] = useState<string | null>(null)
  const setDuration = usePlayback((s) => s.setDuration)

  const forge = useCallback(
    async (b: Params, s: Schema) => {
      setBusy(true)
      setError(null)
      try {
        const r = await simulate(b, seed, s.preset.duration,
          push.enabled ? { ...s.preset.push, force: push.force } : null)
        setRun(r)
        setDuration(r.duration)
        usePlayback.getState().restart()
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setBusy(false)
      }
    },
    [seed, push, setDuration],
  )

  // initial load: schema, Phase 0 experiment; start the studio on the Phase 0 baseline (8 cm foot)
  useEffect(() => {
    Promise.all([getSchema(), getPhase0()])
      .then(([s, p]) => {
        setSchema(s)
        setPhase0(p)
        setBody(p.baseline.body)
        setRun(p.baseline)
        setDuration(p.baseline.duration)
        const pb = usePlayback.getState()
        const t0 = parseFloat(q.get('t') ?? '')
        if (Number.isFinite(t0)) pb.seek(t0) // deep link: ?tab=compare&t=2.0 opens paused at that sim time
        else pb.restart()
      })
      .catch((e: Error) => setFatal(`Cannot reach the Studio backend: ${e.message}`))
  }, [setDuration])

  useEffect(() => {
    let last = performance.now()
    let raf = 0
    const loop = (now: number) => {
      usePlayback.getState().tick(Math.min(0.1, (now - last) / 1000))
      last = now
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  if (fatal) return <div className="fatal">{fatal}</div>
  if (!schema || !phase0 || !body || !run) return <div className="fatal">Loading MuJoCo experiments…</div>

  const sum = phase0.matched_seed_summary
  const bf = phase0.baseline.body.foot_length
  const cf = phase0.candidate.body.foot_length

  return (
    <div className="app">
      <header>
        <h1>🦿 Creature Forge <span>Studio</span></h1>
        <nav>
          {(['studio', 'compare', 'lab', 'locomotion', 'sketch'] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? 'on' : ''}
              onClick={() => {
                setTab(t)
                const d = (t === 'compare' ? phase0.baseline : run).duration
                setDuration(d)
                usePlayback.getState().restart()
              }}>
              {{ studio: 'Studio', compare: 'Compare (Phase 0)', lab: 'Investigations', locomotion: 'Locomotion', sketch: 'Sketch' }[t]}
            </button>
          ))}
        </nav>
        <small>Poses are MuJoCo output recorded server-side; the browser only replays them.</small>
      </header>

      {tab === 'studio' && (
        <main className="studio">
          <aside>
            <ParamPanel schema={schema} body={body} onBody={setBody} push={push} onPush={setPush} seed={seed}
              onSeed={setSeed} busy={busy} error={error} onForge={() => void forge(body, schema)} />
          </aside>
          <section>
            <Viewport run={run} label={`Your creature · foot ${run.body.foot_length.toFixed(3)} m`} />
            <Transport runs={[{ run, label: 'run', color: '#4cc2ff' }]} />
            <div className="below">
              <HeightChart runs={[{ run, label: 'run', color: '#4cc2ff' }]} />
              <Metrics run={run} label="Measured results" />
            </div>
          </section>
        </main>
      )}

      {tab === 'compare' && (
        <main className="compare">
          <div className="banner">
            Same controller, seed {phase0.baseline.seed}, and {phase0.baseline.push?.force} N push
            ({phase0.baseline.push?.duration} s at t = {phase0.baseline.push?.time} s).
            Only the foot length differs: <b>{bf * 100} cm</b> vs <b>{cf * 100} cm</b>.
          </div>
          <div className="pair">
            <Viewport run={phase0.baseline} label={`BASELINE · foot ${bf * 100} cm`} />
            <Viewport run={phase0.candidate} label={`CANDIDATE · foot ${cf * 100} cm`} />
          </div>
          <Transport runs={[{ run: phase0.baseline, label: 'baseline', color: '#e5484d' },
            { run: phase0.candidate, label: 'candidate', color: '#3fb97f' }]} />
          <div className="below">
            <HeightChart runs={[{ run: phase0.baseline, label: 'baseline', color: '#e5484d' },
              { run: phase0.candidate, label: 'candidate', color: '#3fb97f' }]} />
            <div className="summary">
              <h4>Matched seeds {sum.seeds.join(', ')}</h4>
              <table>
                <thead><tr><td></td><td>fall rate</td><td>mean min height</td><td>mean max pitch</td></tr></thead>
                <tbody>
                  <tr><td>{bf * 100} cm</td><td>{fmtPct(sum.baseline.fall_rate)}</td>
                    <td>{sum.baseline.mean_min_torso_height.toFixed(2)} m</td>
                    <td>{(sum.baseline.mean_max_abs_pitch * 57.2958).toFixed(0)}°</td></tr>
                  <tr><td>{cf * 100} cm</td><td>{fmtPct(sum.candidate.fall_rate)}</td>
                    <td>{sum.candidate.mean_min_torso_height.toFixed(2)} m</td>
                    <td>{(sum.candidate.mean_max_abs_pitch * 57.2958).toFixed(0)}°</td></tr>
                </tbody>
              </table>
              <small>Measured over {sum.seeds.length} seeded MuJoCo rollouts at this disturbance only; not a general robustness claim.</small>
            </div>
          </div>
          <div className="pair">
            <Metrics run={phase0.baseline} label="Baseline" />
            <Metrics run={phase0.candidate} label="Candidate" />
          </div>
        </main>
      )}

      {tab === 'locomotion' && <Locomotion />}

      {tab === 'lab' && <Lab initialTrial={link.trial} initialStep={link.step} />}

      {tab === 'sketch' && (
        <main>
          <SketchEditor onUse={(p) => {
            setBody({ ...body, ...p })
            setTab('studio')
          }} />
        </main>
      )}
    </div>
  )
}
