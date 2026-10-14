import { useEffect, useMemo, useRef, useState } from 'react'
import { getDemoReplay } from '../api'
import { Metrics } from '../Metrics'
import { usePlayback } from '../store'
import { Transport } from '../Timeline'
import { Viewport } from '../Viewport'
import { apiId, citedEvidence, KIND_INFO, lookupPath, proposalOutcome, statusMessage, verdictText } from './demoLogic'
import type { DemoReplay, DemoRun } from './demoTypes'
import { Diffs, OutcomeBars } from './parts'
import './investigation.css'

type Step = 'failure' | 'evidence' | 'proposal' | 'verification' | 'verdict'
const STEPS: { id: Step; label: string }[] = [
  { id: 'failure', label: 'Failure' }, { id: 'evidence', label: 'Evidence' }, { id: 'proposal', label: 'AI proposal' },
  { id: 'verification', label: 'Verification' }, { id: 'verdict', label: 'Verdict' },
]
const KIND_SHORT: Record<string, string> = { LIVE: 'LIVE', RECORDED_LIVE: 'RECORDED LIVE', SCRIPTED_MOCK: 'SCRIPTED MOCK' }
const num = (x: unknown, nd = 1) => (typeof x === 'number' ? x.toFixed(nd) : '—')

interface Spec { which: string; seed: number; title: string }
type Pair = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; a: DemoReplay; b: DemoReplay; specs: [Spec, Spec] }

function outcomeChip(r: DemoReplay) {
  const m = r.locomotion
  return m.walking ? { text: 'walks the whole 10 s', cls: 'ok' } : m.fell ? { text: `falls at ${m.fall_time?.toFixed(1)} s`, cls: 'bad' } : { text: m.label.replace(/_/g, ' '), cls: 'warn' }
}

/** A step-by-step investigation with the two simulations as the centrepiece. Every number is a MuJoCo measurement. */
export function Investigation({ run, go }: { run: DemoRun; go?: (t: 'locomotion' | 'sketch') => void }) {
  const slots = run.interventions.map((i) => i.slot)
  const [step, setStep] = useState<Step>('failure')
  const [slot, setSlot] = useState(slots[0] ?? 0)
  const [arm, setArm] = useState<'model' | 'random'>('model')
  const [seed, setSeed] = useState(run.observed.failing_seed)
  const [pair, setPair] = useState<Pair>({ status: 'loading' })
  const cache = useRef(new Map<string, DemoReplay>())
  const iv = run.interventions.find((i) => i.slot === slot)
  const observe = step === 'failure' || step === 'evidence' || !iv
  const verSeeds = run.verification?.seeds ?? []
  const seeds = [run.observed.failing_seed, run.observed.walking_seed, ...verSeeds]

  const specs: [Spec, Spec] = useMemo(() => observe
    ? [{ which: 'baseline', seed: run.observed.failing_seed, title: `Starting controller · seed ${run.observed.failing_seed}` },
       { which: 'baseline', seed: run.observed.walking_seed, title: `Starting controller · seed ${run.observed.walking_seed}` }]
    : [{ which: 'baseline', seed, title: `Unchanged controller · seed ${seed}` },
       { which: arm === 'model' ? `slot${slot}` : `slot${slot}_random`, seed, title: `${arm === 'model' ? 'With Nemotron’s edit' : 'With a matched random edit'} · seed ${seed}` }],
  [observe, run, seed, arm, slot])

  const key = specs.map((s) => `${s.which}:${s.seed}`).join('|')
  useEffect(() => {
    let live = true
    setPair({ status: 'loading' })
    const get = async (s: Spec) => {
      const k = `${apiId(run)}|${s.which}|${s.seed}`
      const hit = cache.current.get(k)
      if (hit) return hit
      const r = await getDemoReplay(apiId(run), s.which, s.seed)
      cache.current.set(k, r)
      return r
    }
    Promise.all([get(specs[0]), get(specs[1])]).then(([a, b]) => {
      if (!live) return
      setPair({ status: 'ready', a, b, specs })
      const pb = usePlayback.getState()
      pb.setDuration(Math.max(a.duration, b.duration))
      pb.setSpeed(0.5)
      pb.restart()
      // warm the cache with the other replays for the observed failure so stepping through is instant (sequential: one MuJoCo run at a time)
      void (async () => {
        for (const w of run.interventions.flatMap((iv) => [`slot${iv.slot}`, `slot${iv.slot}_random`])) {
          if (!live) return
          const k = `${apiId(run)}|${w}|${run.observed.failing_seed}`
          if (!cache.current.has(k)) await getDemoReplay(apiId(run), w, run.observed.failing_seed).then((r) => cache.current.set(k, r)).catch(() => undefined)
        }
      })()
    }).catch((e: Error) => live && setPair({ status: 'error', message: e.message }))
    return () => { live = false }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  const idx = STEPS.findIndex((s) => s.id === step)
  const blocked = (s: Step) => !iv && (s === 'verification' || s === 'verdict')
  const msg = statusMessage(run)
  const o = iv ? proposalOutcome(run, slot) : null
  const f = run.observed.metrics[String(run.observed.failing_seed)] ?? {}
  const w = run.observed.metrics[String(run.observed.walking_seed)] ?? {}
  const ev = iv ? citedEvidence(run, slot) : []
  const ctx = run.context as Record<string, unknown>
  const kind = run.provenance.kind

  return (
    <div className="inv" data-testid="investigation" data-step={step}>
      <div className="inv-top">
        <div className={`prov prov-${kind}`} data-testid="kind-banner" data-kind={kind}>
          <b>{KIND_SHORT[kind]}</b>
          <span>{kind === 'SCRIPTED_MOCK' ? 'Text written by this repository, not Nemotron. It exercises the pipeline.' : kind === 'LIVE' ? 'A real Nebius call made during this run.' : 'A stored, hash-verified real Nemotron call. Nothing is re-sent; the physics below is re-run.'}</span>
        </div>
        <ol className="rail" aria-label="investigation steps">
          {STEPS.map((s, i) => (
            <li key={s.id}>
              <button className={`${s.id === step ? 'on' : ''} ${i < idx ? 'done' : ''}`} disabled={blocked(s.id)} data-testid={`step-${s.id}`} aria-current={s.id === step ? 'step' : undefined}
                title={blocked(s.id) ? 'No valid proposal, so nothing was simulated' : undefined} onClick={() => setStep(s.id)}>
                <span className="n">{i < idx ? '✓' : i + 1}</span>{s.label}
              </button>
            </li>
          ))}
        </ol>
      </div>

      <div className="inv-main">
        <section className="stage" aria-label="synchronized simulations">
          <div className="stage-bar">
            {!observe && (
              <>
                <div className="seg" role="tablist" aria-label="which edit">
                  <button role="tab" aria-selected={arm === 'model'} data-testid="arm-model" onClick={() => setArm('model')}>Nemotron’s edit</button>
                  <button role="tab" aria-selected={arm === 'random'} data-testid="arm-random" onClick={() => setArm('random')}>Matched random edit</button>
                </div>
                <label className="seed-pick">Test seed
                  <select value={seed} onChange={(e) => setSeed(Number(e.target.value))} aria-label="seed">
                    {seeds.map((s) => <option key={s} value={s}>{s}{s === run.observed.failing_seed ? ' (the failure)' : s === run.observed.walking_seed ? ' (a walker)' : ''}</option>)}
                  </select>
                </label>
              </>
            )}
            {observe && <span className="dim">The same controller on two starting poses.</span>}
          </div>
          {pair.status === 'ready' ? (
            <div className="duo" data-testid="demo-replay">
              {([pair.a, pair.b] as const).map((r, i) => {
                const c = outcomeChip(r)
                return (
                  <div className="duo-cell" key={i}>
                    <Viewport run={r} label={pair.specs[i].title} closeup />
                    <span className={`result-chip ${c.cls}`} data-testid={`result-${i}`}>{c.text}</span>
                  </div>
                )
              })}
            </div>
          ) : pair.status === 'error' ? (
            <div className="state error" role="alert"><b>The simulation could not load</b><span>{pair.message}</span><button className="btn btn-ghost" onClick={() => setPair({ status: 'loading' })}>Try again</button></div>
          ) : (
            <div className="duo"><div className="skeleton duo-skel" /><div className="skeleton duo-skel" /><span className="loading-note">Running MuJoCo…</span></div>
          )}
          {pair.status === 'ready' && <Transport runs={[{ run: pair.a, label: 'left', color: '#ff5d6c' }, { run: pair.b, label: 'right', color: '#4fd18b' }]} />}
        </section>

        <aside className="inspector" data-testid={`inspect-${step}`} aria-live="polite">
          {step === 'failure' && (
            <>
              <h2>Where the robot fails</h2>
              <p>A two-legged robot follows a walking controller for 10 seconds. The only difference between these two runs is a tiny random starting pose.</p>
              <div className="pair-facts">
                <div className="fact bad"><b>Seed {run.observed.failing_seed}</b><span>falls at {num(f.fall_time)} s</span><small>{num(f.backward_steps, 0)} backward steps · {num(f.valid_steps, 0)} valid steps</small></div>
                <div className="fact ok"><b>Seed {run.observed.walking_seed}</b><span>walks</span><small>{num(w.valid_steps, 0)} valid steps · {num(w.speed_upright, 2)} m/s</small></div>
              </div>
              <small className="dim">Measured by MuJoCo at the start of this run.</small>
            </>
          )}
          {step === 'evidence' && (
            <>
              <h2>What the AI was given</h2>
              <p><b>Measurements only.</b> No conclusion and no hint of a fix:</p>
              <ul className="ctx-facts">
                <li><b>{Object.keys((ctx.controller as object) ?? {}).length}</b> controller parameters</li>
                <li><b>{Array.isArray(ctx.failing_seeds) ? ctx.failing_seeds.length : 0}</b> failing run(s) with step counts, pitch and timing</li>
                <li><b>{Array.isArray(ctx.walking_seeds) ? ctx.walking_seeds.length : 0}</b> walking run(s) for contrast</li>
              </ul>
              {iv ? (
                <>
                  <p>The values it chose to cite:</p>
                  <ul className="cites">{ev.map((c) => <li key={c.path}><code>{c.path}</code> = <b>{c.value}</b>{!c.resolved && <span className="tone-bad"> (not in the evidence)</span>}</li>)}</ul>
                </>
              ) : <p className="dim">The reply cited no usable evidence.</p>}
            </>
          )}
          {step === 'proposal' && (
            <>
              <h2>What Nemotron suggested</h2>
              {!iv ? (
                <div className="notice-stop" data-testid="story-noproposal"><b>{msg.text}</b><p>The investigation stops here. Nothing was simulated and nothing was substituted.</p></div>
              ) : (
                <>
                  {slots.length > 1 && (
                    <div className="seg" role="tablist" aria-label="proposal">
                      {slots.map((s) => <button key={s} role="tab" aria-selected={s === slot} data-testid={`slot-${s}`} onClick={() => setSlot(s)}>Proposal {s + 1}</button>)}
                    </div>
                  )}
                  <blockquote className="claim" data-testid="story-claim">
                    <span className="tag">{kind === 'SCRIPTED_MOCK' ? 'Scripted text, not Nemotron' : 'Model-written claim'}</span>
                    “{iv.proposal.claim}”
                    <small>Predicted at least {iv.proposal.prediction.min_gain_seeds} more seeds walk · its own confidence {(iv.proposal.confidence * 100).toFixed(0)}% (uncalibrated)</small>
                  </blockquote>
                  <h3>What it would change</h3>
                  <Diffs key={`${run.run_id}-${slot}`} run={run} slot={slot} who="model" />
                </>
              )}
            </>
          )}
          {step === 'verification' && o && (
            <>
              <h2>What MuJoCo measured</h2>
              <p>Each controller ran on <b>{o.n} fresh seeds</b> the model never saw.</p>
              <OutcomeBars run={run} slot={slot} />
              <div className="seed-strips" data-testid="seed-strips">
                {(['theta0', `slot${slot}`, `slot${slot}_random`] as const).map((k, i) => (
                  <div key={k} className="strip"><span>{['Unchanged', 'Nemotron’s edit', 'Random edit'][i]}</span>
                    <span className="cells">{run.verification!.results[k].walking_by_seed.map((x, j) => <i key={j} className={x ? 'walks' : 'falls'} />)}</span></div>
                ))}
              </div>
              <small className="dim">Each square is one seed: filled walks, hollow does not.</small>
              <details><summary>The matched random edit used for comparison</summary><Diffs run={run} slot={slot} who="random" /></details>
            </>
          )}
          {step === 'verdict' && o && (
            <div data-testid="story-verdict">
              <h2>The verdict</h2>
              <p className={`big-verdict tone-${o.verdict ? verdictText(o.verdict).tone : 'muted'}`}>{o.verdict ? verdictText(o.verdict).text : 'not evaluated'}</p>
              <p>{o.predictionMet ? 'The model’s prediction was met.' : 'The model’s prediction was not met.'}{' '}
                {o.beatRandom ? 'This proposal walked on more seeds than its matched random edit.' : <b>A matched random edit did as well or better ({o.random}/{o.n}), so this does not show the model chose well.</b>}</p>
              <div className="caveats">
                <p><b>Read this carefully.</b> One recorded instance, not a statistical comparison of Nemotron against random edits; that experiment was not completed. The 150 of 150 result on the Home page came from a classical optimiser, not from this model.</p>
              </div>
              <div className="actions">
                {go && <button className="btn btn-simulate" onClick={() => go('locomotion')}>See the tuned walker</button>}
                {go && <button className="btn btn-create" onClick={() => go('sketch')}>Draw your own creature</button>}
              </div>
              <small className="dim">An investigation on your own drawing is not available: this recording was made on the standard walking robot.</small>
            </div>
          )}
          <div className="step-nav2">
            <button className="btn btn-ghost" disabled={idx === 0} onClick={() => setStep(STEPS[idx - 1].id)}>Back</button>
            <button className="btn btn-investigate" disabled={idx === STEPS.length - 1 || blocked(STEPS[idx + 1]?.id)} data-testid="step-next" onClick={() => setStep(STEPS[idx + 1].id)}>Next: {STEPS[Math.min(idx + 1, STEPS.length - 1)].label}</button>
          </div>
          {pair.status === 'ready' && <div className="mini-metrics"><Metrics run={pair.a} label="Left" /><Metrics run={pair.b} label="Right" /></div>}
          <small className="dim kind-note">{KIND_INFO[kind].text}{lookupPath(ctx, 'episode') ? '' : ''}</small>
        </aside>
      </div>
    </div>
  )
}
