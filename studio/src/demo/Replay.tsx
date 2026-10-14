import { useEffect, useRef, useState } from 'react'
import { getDemoReplay } from '../api'
import { Notice } from '../lab/Badges'
import { Metrics } from '../Metrics'
import { usePlayback } from '../store'
import { HeightChart, Transport } from '../Timeline'
import { Viewport } from '../Viewport'
import { apiId, honestHeadline, replayOptions, verdictText } from './demoLogic'
import type { DemoReplay, DemoRun } from './demoTypes'

type ReplayState = { status: 'idle' } | { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; a: DemoReplay; b: DemoReplay; which: string; seed: number }

export function ReplayStep({ run, autoLoad = false, initialWhich }: { run: DemoRun; autoLoad?: boolean; initialWhich?: string }) {
  const opts = replayOptions(run)
  const [which, setWhich] = useState(initialWhich && opts.some((o) => o.id === initialWhich) ? initialWhich : opts[Math.min(1, opts.length - 1)].id)
  const [seed, setSeed] = useState(run.observed.failing_seed)
  const [state, setState] = useState<ReplayState>({ status: 'idle' })
  const reqId = useRef(0)
  const seeds = [run.observed.failing_seed, run.observed.walking_seed, ...(run.verification?.seeds ?? [])]

  const change = (apply: () => void) => { reqId.current += 1; apply(); setState({ status: 'idle' }) }
  const load = async () => {
    const mine = ++reqId.current
    setState({ status: 'loading' })
    try {
      const [a, b] = await Promise.all([getDemoReplay(apiId(run), 'baseline', seed), getDemoReplay(apiId(run), which, seed)])
      if (mine !== reqId.current) return
      setState({ status: 'ready', a, b, which, seed })
      usePlayback.getState().setDuration(Math.max(a.duration, b.duration))
      usePlayback.getState().restart()
    } catch (e) {
      if (mine === reqId.current) setState({ status: 'error', message: (e as Error).message })
    }
  }
  useEffect(() => { if (autoLoad && opts.length > 1) void load() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const ver = run.verification
  const sel = ver && which !== 'baseline' ? ver.results[which] : null
  return (
    <div className="step-body">
      <div className="replay-bar">
        <label>Compare the frozen controller with{' '}
          <select value={which} onChange={(e) => change(() => setWhich(e.target.value))} aria-label="edited controller">
            {opts.filter((o) => o.id !== 'baseline').map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </label>
        <label>Seed{' '}
          <select value={seed} onChange={(e) => change(() => setSeed(Number(e.target.value)))} aria-label="seed">
            {seeds.map((s) => <option key={s} value={s}>{s}{s === run.observed.failing_seed ? ' (observed failure)' : s === run.observed.walking_seed ? ' (observed walker)' : ''}</option>)}
          </select>
        </label>
        <button data-testid="demo-load-replay" onClick={() => void load()} disabled={state.status === 'loading' || opts.length < 2}>
          {state.status === 'loading' ? 'Running MuJoCo…' : 'Load synchronized replay'}
        </button>
        <small>Fresh deterministic MuJoCo rollouts of the stored controller vectors; no model call.</small>
      </div>
      {opts.length < 2 && <Notice testid="demo-noreplay">There is no proposed controller to replay because the model produced no valid proposal.</Notice>}
      {state.status === 'error' && <Notice tone="bad">{state.message}</Notice>}
      {state.status === 'ready' && (
        <>
          <div className="pair" data-testid="demo-replay">
            <Viewport run={state.a} label={`FROZEN CONTROLLER · seed ${state.seed}`} />
            <Viewport run={state.b} label={`${opts.find((o) => o.id === state.which)?.label.toUpperCase()} · seed ${state.seed}`} />
          </div>
          <Transport runs={[{ run: state.a, label: 'frozen', color: '#e5484d' }, { run: state.b, label: 'edited', color: '#3fb97f' }]} />
          <div className="below">
            <HeightChart runs={[{ run: state.a, label: 'frozen', color: '#e5484d' }, { run: state.b, label: 'edited', color: '#3fb97f' }]} />
            <div className="pair"><Metrics run={state.a} label="Frozen" /><Metrics run={state.b} label="Edited" /></div>
          </div>
        </>
      )}
      <section className="verdict" data-testid="demo-verdict">
        <h4>Measured verdict</h4>
        <p>{honestHeadline(run)}</p>
        {sel?.verdict && <p>Selected controller: <span className={`chip chip-${verdictText(sel.verdict).tone === 'ok' ? 'ok' : verdictText(sel.verdict).tone === 'bad' ? 'bad' : 'muted'}`}>{verdictText(sel.verdict).text}</span></p>}
        <small>Replay shows one seed; the verdict above is over all {ver?.seeds.length ?? 0} verification seeds. Nothing here is a statistical claim about the model.</small>
      </section>
    </div>
  )
}
