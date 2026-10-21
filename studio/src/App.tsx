import { useCallback, useEffect, useState } from 'react'
import { getPhase0, getSchema, sandboxSimulate, simulate } from './api'
import { CausalLab } from './causal/CausalLab'
import { ScientistLab } from './scientist/ScientistLab'
import { Do1Recovery } from './do1/Do1Recovery'
import { NemotronCase } from './nemotron/NemotronCase'
import { Demo } from './demo/Demo'
import { ForgePage } from './forge/ForgePage'
import { forgeUrl } from './forge/forgeLogic'
import { Home } from './home/Home'
import { SandboxResult, type SandboxMeta } from './sandbox/SandboxResult'
import { Shell } from './shell/Shell'
import { parseTab, stageOf, type Tab } from './shell/nav'
import type { Change, SandboxBodyDict } from './sketch/freehandTypes'
import { Lab } from './lab/Lab'
import { WalkingLab } from './walking/WalkingLab'
import { parseDeepLink } from './lab/labLogic'
import { Metrics } from './Metrics'
import { ParamPanel, type PushSettings } from './ParamPanel'
import { SketchPage } from './sketch/SketchPage'
import { HeightChart, Transport } from './Timeline'
import { Viewport } from './Viewport'
import { fmtPct } from './playback'
import { usePlayback } from './store'
import type { Params, Phase0, RunPayload, Schema } from './types'

export default function App() {
  const q = new URLSearchParams(window.location.search)
  const [tab, setTab] = useState<Tab>(parseTab(window.location.search))
  const [sandbox, setSandbox] = useState<SandboxMeta | null>(null)
  const [forgeTarget, setForgeTarget] = useState<{ cid: string; n: number | null } | null>(() => {
    const cid = q.get('creature')
    const v = parseInt(q.get('v') ?? '', 10)
    return cid ? { cid, n: Number.isFinite(v) ? v : null } : null
  })
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
        setSandbox(null)
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

  const go = (t: Tab) => {
    setTab(t)
    if (t === 'forge') setForgeTarget(null) // the workspace reopens the last creature it showed
    history.replaceState(null, '', `?tab=${t}`)
    const d = !phase0 ? 5 : t === 'compare' ? phase0.baseline.duration : run ? run.duration : 5
    setDuration(d)
    usePlayback.getState().restart()
    window.scrollTo({ top: 0 })
  }

  const useCreature = (cid: string, n: number) => {
    setForgeTarget({ cid, n })
    setTab('forge')
    history.replaceState(null, '', forgeUrl(cid, n))
    window.scrollTo({ top: 0 })
  }

  const simulateDrawn = async (b: SandboxBodyDict, approximated: Change[] | null): Promise<string | null> => {
    if (!schema) return 'The Studio backend is not ready yet.'
    try {
      const r = await sandboxSimulate(b, push.enabled ? { ...schema.preset.push, force: push.force } : null, seed, schema.preset.duration)
      setRun(r)
      setBody({ ...body!, ...Object.fromEntries(Object.entries(b).filter(([, v]) => typeof v === 'number')) } as Params)
      setSandbox({ explanation: r.explanation, approximated })
      setTab('studio')
      history.replaceState(null, '', '?tab=studio')
      setDuration(r.duration)
      usePlayback.getState().restart()
      return null
    } catch (e) {
      return (e as Error).message
    }
  }

  if (fatal) return <div className="fatal">{fatal}</div>
  if (!schema || !phase0 || !body || !run) return <div className="fatal">Loading MuJoCo experiments…</div>

  const sum = phase0.matched_seed_summary
  const bf = phase0.baseline.body.foot_length
  const cf = phase0.candidate.body.foot_length

  return (
    <div className="app" data-stage={stageOf(tab)}>
      <Shell tab={tab} go={go} />
      <div className="page" key={tab}>

      {tab === 'studio' && (
        <main className="studio">
          <aside>
            {sandbox ? (
              <SandboxResult meta={sandbox} onEdit={() => go('sketch')} onSliders={() => setSandbox(null)} onInvestigate={() => go('demo')} />
            ) : (
              <ParamPanel schema={schema} body={body} onBody={setBody} push={push} onPush={setPush} seed={seed}
                onSeed={setSeed} busy={busy} error={error} onForge={() => void forge(body, schema)} />
            )}
          </aside>
          <section>
            <p className={`run-line ${run.metrics.fell ? 'bad' : 'ok'}`} data-testid="run-line">
              {run.metrics.fell ? `It fell at ${run.events.find((e) => e.kind === 'fall')?.time.toFixed(2)} s.` : 'It stayed on its feet for the whole run.'}
              {run.push ? ` A ${run.push.force} N push hit it at ${run.push.time.toFixed(1)} s.` : ''}
            </p>
            <Viewport closeup run={run} label={sandbox ? 'Your drawn creature' : `Your creature · foot ${run.body.foot_length.toFixed(3)} m`} />
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
            <Viewport closeup run={phase0.baseline} label={`BASELINE · foot ${bf * 100} cm`} />
            <Viewport closeup run={phase0.candidate} label={`CANDIDATE · foot ${cf * 100} cm`} />
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

      {tab === 'overview' && <Home go={go} />}

      {tab === 'locomotion' && <WalkingLab />}

      {tab === 'demo' && <Demo initialRun={q.get('run')} go={go} />}

      {tab === 'causal' && <CausalLab />}
      {tab === 'scientist' && <ScientistLab />}
      {tab === 'nemotron' && <NemotronCase />}
      {tab === 'recovery' && <Do1Recovery />}

      {tab === 'lab' && <Lab initialTrial={link.trial} initialStep={link.step} />}

      {tab === 'forge' && <ForgePage target={forgeTarget} go={go} />}

      {tab === 'sketch' && <SketchPage initialBody={body} onSimulate={simulateDrawn} onUseCreature={useCreature} onUseParams={(p) => {
        const nb = { ...body, ...p }
        setBody(nb)
        setSandbox(null)
        go('studio')
        void forge(nb, schema)
      }} />}
      </div>
    </div>
  )
}
