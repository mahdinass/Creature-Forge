import { useCallback, useEffect, useRef, useState } from 'react'
import { getCausalRecord, getCausalRecords, getCausalReplay } from '../api'
import { Notice } from '../lab/Badges'
import { usePlayback } from '../store'
import { Transport } from '../Timeline'
import { Viewport } from '../Viewport'
import { Chip, Timeline } from './Investigation'
import { ClaimsAndVerification, EvaluationOnly, MemoryPanel, NoAiComparison, Provenance } from './Panels'
import { categoryLabel, fmtCost, fmtPct, headline, robotSummary, statusInfo } from './causalLogic'
import type { CausalIndex, CausalIndexRow, CausalRecord, CausalReplay, DesignKey } from './causalTypes'
import './causal.css'

type View = 'side' | DesignKey
type Pair = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; initial: CausalReplay; submitted: CausalReplay }

const outcomeChip = (r: CausalReplay) =>
  r.locomotion.walking ? { t: `walks the whole ${r.duration.toFixed(0)} s`, tone: 'ok' }
    : r.locomotion.fell ? { t: `falls at ${r.locomotion.fall_time?.toFixed(1)} s`, tone: 'bad' }
      : { t: r.locomotion.label.replace(/_/g, ' '), tone: 'warn' }

/** The robot first: the faulty design and the design the AI submitted, on the same start, as fresh MuJoCo rollouts. */
function ReplaySection({ id, seeds, note, status }: { id: string; seeds: number[]; note: string; status: string | null }) {
  const [seed, setSeed] = useState(seeds[0] ?? 1)
  const [view, setView] = useState<View>('side')
  const [pair, setPair] = useState<Pair>({ status: 'loading' })
  const cache = useRef(new Map<string, CausalReplay>())
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let live = true
    setPair({ status: 'loading' })
    const get = async (d: DesignKey) => {
      const k = `${id}|${d}|${seed}`
      const hit = cache.current.get(k)
      if (hit) return hit
      const r = await getCausalReplay(id, d, seed)
      cache.current.set(k, r)
      return r
    }
    Promise.all([get('initial'), get('submitted')]).then(([initial, submitted]) => {
      if (!live) return
      setPair({ status: 'ready', initial, submitted })
      const pb = usePlayback.getState()
      pb.setDuration(Math.max(initial.duration, submitted.duration)); pb.setSpeed(0.5); pb.restart()
    }).catch((e: Error) => live && setPair({ status: 'error', message: e.message }))
    return () => { live = false }
  }, [id, seed, attempt])

  const ready = pair.status === 'ready' ? pair : null
  const cells = ready ? ([['initial', 'INITIAL DESIGN (the faulty robot)', ready.initial], ['submitted', 'DESIGN THE AI SUBMITTED', ready.submitted]] as const).filter(([d]) => view === 'side' || view === d) : []
  const color = { initial: '#ff5d6c', submitted: '#4fd18b' } as const
  return (
    <section className="cz-panel cz-replay" data-testid="cz-replay">
      <div className="cz-replay-bar">
        <h2>Watch it</h2>
        <div className="seg" role="group" aria-label="which design">
          {([['side', 'Side by side'], ['initial', 'Initial only'], ['submitted', 'Submitted only']] as const).map(([v, label]) => (
            <button key={v} className={view === v ? 'on' : ''} aria-pressed={view === v} data-testid={`cz-view-${v}`} onClick={() => setView(v)}>{label}</button>
          ))}
        </div>
        <label>Start <select value={seed} onChange={(e) => setSeed(Number(e.target.value))} aria-label="replay seed" data-testid="cz-seed">
          {seeds.map((s) => <option key={s} value={s}>seed {s}</option>)}
        </select></label>
      </div>
      {ready ? (
        <>
          <div className={`cz-duo ${view === 'side' ? '' : 'single'}`} data-testid="cz-duo">
            {cells.map(([d, label, run]) => {
              const c = outcomeChip(run)
              return (
                <div className="cz-cell" key={d}>
                  <Viewport run={run} label={label} closeup />
                  <span className={`cz-result cz-chip-${c.tone}`} data-testid={`cz-result-${d}`}>{c.t}</span>
                </div>
              )
            })}
          </div>
          <Transport runs={cells.map(([d, , run]) => ({ run, label: d, color: color[d] }))} />
        </>
      ) : pair.status === 'error' ? (
        <div className="state error" role="alert" data-testid="cz-replay-error"><b>The replay could not run</b><span>{pair.message}</span>
          <button className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Try again</button></div>
      ) : <div className="cz-duo"><div className="skeleton cz-skel" /><div className="skeleton cz-skel" /><span className="loading-note">Running MuJoCo…</span></div>}
      <p className="dim cz-replay-note">
        {note} One start is shown; the independent verification below{status ? ` (${statusInfo(status).label.toLowerCase()})` : ''} covers many hidden starts, so a single replay can differ from it in either direction.
        {ready?.initial.condition ? ` Conditions on this seed: ${(ready.initial.condition.perturb).toFixed(3)} perturbation, friction ${ready.initial.condition.friction_used.toFixed(2)}.` : ''}
      </p>
    </section>
  )
}

function RecordList({ rows, picked, onPick }: { rows: CausalIndexRow[]; picked: string | null; onPick: (id: string) => void }) {
  return (
    <ul className="cz-list" data-testid="cz-list" aria-label="Recorded investigations">
      {rows.map((r, i) => {
        const s = statusInfo(r.status)
        return (
          <li key={r.id}>
            <button type="button" className={`cz-card ${picked === r.id ? 'on' : ''}`} aria-pressed={picked === r.id} data-testid={`cz-card-${i}`} onClick={() => onPick(r.id)}>
              <span className="cz-card-top"><Chip tone={s.tone}>{s.label}</Chip><small>{fmtPct(r.walking_frac)} of hidden starts walk</small></span>
              <span className="cz-card-robot">{robotSummary(r.robot)}</span>
              <span className="cz-card-meta">{r.n_steps} steps · {r.n_experiments} experiments · {r.llm_calls ?? 0} model calls · {fmtCost(r.cost_usd)}</span>
              <span className="cz-card-meta">AI's final diagnosis: {categoryLabel(r.final_category)}{r.has_memory ? ' · used retrieved memory' : ''}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function RecordView({ id, index }: { id: string; index: CausalIndex }) {
  const [rec, setRec] = useState<CausalRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openItem, setOpenItem] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setRec(null); setError(null); setOpenItem(null)
    getCausalRecord(id).then((r) => live && setRec(r)).catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [id])
  const showItem = useCallback((item: string) => {
    setOpenItem(item)
    requestAnimationFrame(() => document.getElementById(`cz-mem-${item}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }, [])

  if (error) return <div className="state error" role="alert" data-testid="cz-record-error"><b>This record could not be loaded</b><span>{error}</span></div>
  if (!rec) return <div className="skeleton" style={{ height: 360 }} aria-label="Loading record" />
  const st = statusInfo(rec.verification.status)
  const memoryIds = rec.memory.items.map((m) => m.id)
  return (
    <div className="cz-record" data-testid="cz-record">
      <p className={`cz-headline cz-head-${st.tone}`} data-testid="cz-headline">{headline(rec)}</p>
      {rec.error && <Notice tone="bad">This episode reported an error: {rec.error}</Notice>}
      <ReplaySection id={rec.id} seeds={index.replay.seeds} note={index.replay.note} status={rec.verification.status} />
      <section className="cz-panel">
        <h2>The investigation, step by step</h2>
        <p className="dim">Text with a dashed border was written by the language model and is not checked by the simulator. Numbers on experiment cards were measured by MuJoCo. Click a step to see the hypotheses as they stood after it.</p>
        <Timeline rec={rec} memoryIds={memoryIds} onItem={showItem} />
      </section>
      <MemoryPanel rec={rec} open={openItem} onToggle={setOpenItem} />
      <ClaimsAndVerification rec={rec} />
      <NoAiComparison rec={rec} />
      <EvaluationOnly rec={rec} />
      <Provenance rec={rec} />
    </div>
  )
}

/** Causal engineer: recorded investigations of why a simulated biped falls. Read-only; every word of data comes from a stored record. */
export function CausalLab() {
  const [index, setIndex] = useState<CausalIndex | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  useEffect(() => {
    getCausalRecords().then((i) => { setIndex(i); setPicked(i.records[0]?.id ?? null) }).catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <main><div className="state error" role="alert" data-testid="cz-error"><b>The recorded investigations could not be loaded</b><span>{error}</span></div></main>
  if (!index) return <main><div className="skeleton" style={{ height: 420 }} aria-label="Loading" /></main>
  if (!index.records.length) return <main className="causal"><Notice testid="cz-empty">No recorded investigations are installed. Export some with scripts/ce_export_records.py.</Notice></main>
  return (
    <main className="causal" data-testid="causal-lab">
      <section className="cz-hero">
        <h1>Why does it fall?</h1>
        <p>A language model plays scientist. It watches a simulated two-legged robot fall, writes down competing explanations, predicts the outcome of experiments before they run, revises its beliefs when the physics disagrees, directs repairs, and is then judged by an independent check it cannot see.</p>
        <p className="dim">These are recorded runs, including the ones that failed. Nothing here calls a model; replays are fresh simulations.</p>
      </section>
      <RecordList rows={index.records} picked={picked} onPick={setPicked} />
      {picked && <RecordView key={picked} id={picked} index={index} />}
    </main>
  )
}
