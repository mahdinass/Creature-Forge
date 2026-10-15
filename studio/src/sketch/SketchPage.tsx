import { useEffect, useMemo, useRef, useState } from 'react'
import { createCreature, getSandboxSchema, interpretFreehand, sandboxSimulate } from '../api'
import { SketchEditor } from '../SketchEditor'
import { usePlayback } from '../store'
import type { Params, RunPayload } from '../types'
import { Viewport } from '../Viewport'
import { DrawCanvas, ROLE_COLOR } from './DrawCanvas'
import type { Approximation, Change, FreehandResult, Outcome, PenRole, SandboxBodyDict, SandboxSchema, Skeleton } from './freehandTypes'
import { useSketch } from './sketchStore'
import { STARTERS } from './starters'
import { DEFAULT_VIEW, fitView, zoomAt } from './strokes'
import './sketch.css'

const PENS: { id: PenRole; label: string; hint: string }[] = [
  { id: 'auto', label: 'Auto', hint: 'Let Creature Forge decide what each stroke is' },
  { id: 'torso', label: 'Torso', hint: 'A closed shape or a vertical stroke for the body' },
  { id: 'leg', label: 'Leg', hint: 'A stroke from hip down to ankle; a bend marks the knee' },
  { id: 'foot', label: 'Foot', hint: 'A short stroke along the ground under an ankle' },
]
const MATERIAL_FIELDS = [
  { key: 'foot_friction', label: 'Foot grip', unit: '', step: 0.01 },
  { key: 'torque_limit', label: 'Motor strength', unit: 'N·m', step: 0.5 },
  { key: 'leg_density', label: 'Leg material density', unit: 'kg/m³', step: 10 },
]
const OUTCOME: Record<string, { label: string; tone: 'ok' | 'warn' | 'bad' | 'dim'; text: string }> = {
  valid: { label: 'Valid and plausible', tone: 'ok', text: 'This maps exactly to a MuJoCo model.' },
  valid_with_snaps: { label: 'Valid, with gentle snaps', tone: 'ok', text: 'Small corrections were applied to the interpretation, never to your drawing.' },
  questionable: { label: 'Buildable, but questionable', tone: 'warn', text: 'It will be simulated exactly as drawn. Falling over is a legitimate result.' },
  unrepresentable: { label: 'Cannot be built as drawn', tone: 'bad', text: 'The physics model cannot represent this exactly.' },
  needs_input: { label: 'I need your help', tone: 'warn', text: 'The strokes are ambiguous. Pick the right reading below.' },
  unbuildable: { label: 'Nothing to build yet', tone: 'dim', text: 'Keep drawing: a torso and at least one leg.' },
}
const verdictKey = (r: FreehandResult | null, strokes: number): string => (strokes === 0 ? 'unbuildable' : !r ? 'unbuildable' : r.status === 'needs_input' ? 'needs_input' : r.status === 'unbuildable' ? 'unbuildable' : r.outcome)

function MiniCompare({ a, b }: { a: Skeleton; b: Skeleton }) {
  const pts = [a, b].flatMap((s) => [s.torso.base, s.torso.top, ...s.legs.flatMap((l) => [l.hip, l.knee, l.ankle, l.toe, l.heel])])
  const xs = pts.map((p) => p[0])
  const ys = pts.map((p) => p[1])
  const x0 = Math.min(...xs) - 30
  const y0 = Math.min(...ys) - 30
  const w = Math.max(...xs) - x0 + 30
  const h = Math.max(...ys) - y0 + 30
  const draw = (s: Skeleton, c: string, dash?: string) => (
    <g stroke={c} fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={dash}>
      <line x1={s.torso.base[0]} y1={s.torso.base[1]} x2={s.torso.top[0]} y2={s.torso.top[1]} strokeWidth={14} opacity={0.5} />
      {s.legs.map((l, i) => <g key={i}><polyline points={`${l.hip} ${l.knee} ${l.ankle}`} /><line x1={l.heel[0]} y1={l.heel[1]} x2={l.toe[0]} y2={l.toe[1]} /></g>)}
    </g>
  )
  return (
    <svg className="mini-compare" viewBox={`${x0} ${y0} ${w} ${h}`} role="img" aria-label="Before and after the approximation" data-testid="approx-compare">
      {draw(a, '#f2b441', '8 6')}{draw(b, '#3cc9d6')}
    </svg>
  )
}

export function SketchPage({ initialBody, onSimulate, onUseCreature, onUseParams }: {
  initialBody: Params
  onSimulate: (b: SandboxBodyDict, approximated: Change[] | null) => Promise<string | null>
  onUseCreature?: (cid: string, n: number) => void
  onUseParams: (p: Params) => void
}) {
  const { strokes, tool, pen, guided, guides, materials, view, past, future } = useSketch()
  const s = useSketch
  const [mode, setMode] = useState<'draw' | 'refine'>('draw')
  const [res, setRes] = useState<FreehandResult | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [schema, setSchema] = useState<SandboxSchema | null>(null)
  const [preview, setPreview] = useState<RunPayload | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [simError, setSimError] = useState<string | null>(null)
  const [showInterp, setShowInterp] = useState(true)
  const [showRaw, setShowRaw] = useState(true)
  const [template, setTemplate] = useState(false)
  const [consent, setConsent] = useState(false)
  const [highlight, setHighlight] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [creatureName, setCreatureName] = useState('My creature')
  const [useBusy, setUseBusy] = useState(false)
  const [useError, setUseError] = useState<string | null>(null)
  const req = useRef(0)
  const preq = useRef(0)

  useEffect(() => { getSandboxSchema().then(setSchema).catch(() => undefined) }, [])

  // Interpret (debounced). The raw strokes are sent as drawn; the response never rewrites them.
  useEffect(() => {
    const mine = ++req.current
    if (strokes.length === 0) { setRes(null); setApiError(null); return }
    const id = setTimeout(() => {
      interpretFreehand(strokes.map(({ id: sid, role, points }) => ({ id: sid, role, points: points.map((p) => [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10] as [number, number]) })), guided, materials)
        .then((r) => { if (mine === req.current) { setRes(r); setApiError(null); setConsent(false) } })
        .catch((e: Error) => { if (mine === req.current) setApiError(e.message) })
    }, 180)
    return () => clearTimeout(id)
  }, [strokes, guided, materials])

  // 3D preview of the exact compiled body (a 0.5 s run shown paused on its first frame).
  const bodyKey = res?.body ? JSON.stringify(res.body) : ''
  useEffect(() => {
    const mine = ++preq.current
    if (!res?.body) { setPreview(null); setPreviewError(null); return }
    const id = setTimeout(() => {
      sandboxSimulate(res.body!, null, 0, 0.5).then((r) => {
        if (mine !== preq.current) return
        setPreview(r); setPreviewError(null)
        const pb = usePlayback.getState()
        pb.setDuration(r.duration); pb.seek(0)
      }).catch((e: Error) => { if (mine === preq.current) setPreviewError(e.message) })
    }, 350)
    return () => clearTimeout(id)
  }, [bodyKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const vk = verdictKey(res, strokes.length)
  const out = OUTCOME[vk]
  const ap: Approximation | null = res && !res.body ? res.approximation : null
  const canSim = !!res?.body && !busy
  const sim = async (body: SandboxBodyDict, changes: Change[] | null) => {
    setBusy(true); setSimError(null)
    const err = await onSimulate(body, changes)
    if (err) { setSimError(err); setBusy(false) }
  }
  // Save the interpreted creature as version 1 of a new forge creature, then open the forge workspace on it.
  const useThisCreature = async () => {
    const body = res?.body ?? ap?.body
    if (!body || !onUseCreature) return
    setUseBusy(true); setUseError(null)
    try {
      const interp = res ? { status: res.status, outcome: res.outcome, roles: res.roles, notes: res.notes, assumptions: res.assumptions, adjustments: res.adjustments, skeleton: res.skeleton, guided: res.guided } : null
      const c = await createCreature({
        name: creatureName.trim() || 'My creature', body, mode: guided ? 'guided' : 'experimental',
        drawing: {
          strokes: strokes.map(({ id: sid, role, points }) => ({ id: sid, role, points: points.map((p) => [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10]) })),
          interpretation: interp,
          approximation: !res?.body && ap ? { changes: ap.changes, consented: consent } : null,
        },
      })
      onUseCreature(c.id, c.current)
    } catch (e) {
      setUseError((e as Error).message); setUseBusy(false)
    }
  }
  const ranges = schema ? (guided ? schema.scientific_bounds : schema.sandbox_bounds) : null
  const overlay = useMemo(() => ({
    compiled: ap ? ap.after : res?.skeleton ?? null, before: ap ? ap.before : null, showInterpretation: showInterp, showRaw, template, highlight,
  }), [res, ap, showInterp, showRaw, template, highlight])
  const refineBody: Params = useMemo(() => {
    const b = res?.body
    return b ? { ...initialBody, thigh_length: b.thigh_length, shank_length: b.shank_length, foot_length: b.foot_length, torso_mass: b.torso_mass } : initialBody
  }, [res, initialBody])
  const loadStarter = (id: string) => {
    const st = STARTERS.find((x) => x.id === id)!
    s.getState().load(st.strokes, { materials: st.materials, guided: st.terrible ? false : s.getState().guided })
    s.getState().setView(DEFAULT_VIEW)
    setNote(st.terrible ? `“${st.label}” is outside the guided range, so Guided constraints is now off. Press Simulate to see what happens.` : null)
  }
  const steps = [
    { id: 'draw', label: 'Draw', done: strokes.length > 0 },
    { id: 'interpret', label: 'Interpret', done: !!res?.skeleton },
    { id: 'preview', label: 'Preview', done: !!preview },
    { id: 'simulate', label: 'Simulate', done: false },
  ]
  const zoom = (f: number) => s.getState().setView(zoomAt(view, f, [view.x + 500 / view.k, view.y + 350 / view.k]))

  return (
    <main className="sketch-page" data-testid="sketch-page">
      <div className="sk-top">
        <div className="seg" role="tablist" aria-label="drawing mode">
          <button role="tab" aria-selected={mode === 'draw'} data-testid="mode-draw" onClick={() => setMode('draw')}>Draw freehand</button>
          <button role="tab" aria-selected={mode === 'refine'} data-testid="mode-refine" onClick={() => setMode('refine')}>Refine with handles</button>
        </div>
        <ol className="stepper2" aria-label="progress">{steps.map((st, i) => <li key={st.id} className={st.done ? 'done' : ''}><span>{st.done ? '✓' : i + 1}</span>{st.label}</li>)}</ol>
        <button role="switch" aria-checked={guided} className={`guided-switch ${guided ? 'on' : 'off'}`} data-testid="guided-switch" onClick={() => s.getState().setGuided(!guided)}>
          <span className="track"><span className="knob" /></span>
          <span className="gs-text"><b>Guided constraints: {guided ? 'ON' : 'OFF · Experimental'}</b>
            <small>{guided ? 'Gentle snapping and validity hints keep the creature buildable.' : 'Your strokes are used as drawn. Strange, weak or unstable creatures are allowed; physics decides.'}</small></span>
        </button>
      </div>

      {mode === 'refine' ? (
        <div className="refine-wrap" data-testid="refine-mode">
          <p className="dim">Refine mode: drag the joints of a symmetric, straight-legged biped. It runs in the standard Playground with the verified design range.</p>
          <SketchEditor initialBody={refineBody} onUse={onUseParams} />
        </div>
      ) : (
        <div className="sk-grid">
          <section className="sk-stage" aria-label="drawing area">
            <div className="sk-toolbar" role="toolbar" aria-label="drawing tools">
              <div className="pens" role="group" aria-label="pen type">
                {PENS.map((p) => (
                  <button key={p.id} className={tool === 'pen' && pen === p.id ? 'on' : ''} title={p.hint} data-testid={`pen-${p.id}`} aria-pressed={tool === 'pen' && pen === p.id} onClick={() => s.getState().setPen(p.id)}>
                    <i style={{ background: ROLE_COLOR[p.id] }} />{p.label}
                  </button>
                ))}
              </div>
              <button className={tool === 'eraser' ? 'on' : ''} data-testid="tool-eraser" aria-pressed={tool === 'eraser'} title="Erase whole strokes (E)" onClick={() => s.getState().setTool('eraser')}>Erase</button>
              <button className={tool === 'pan' ? 'on' : ''} data-testid="tool-pan" aria-pressed={tool === 'pan'} title="Pan (H, or hold Space)" onClick={() => s.getState().setTool('pan')}>Pan</button>
              <span className="sep" />
              <button data-testid="undo" disabled={!past.length} onClick={() => s.getState().undo()} title="Undo (Ctrl+Z)">Undo</button>
              <button data-testid="redo" disabled={!future.length} onClick={() => s.getState().redo()} title="Redo (Ctrl+Shift+Z)">Redo</button>
              <button data-testid="clear" disabled={!strokes.length} onClick={() => s.getState().clear()}>Clear</button>
              <span className="sep" />
              <button aria-label="Zoom out" data-testid="zoom-out" onClick={() => zoom(1 / 1.25)}>−</button>
              <button aria-label="Fit drawing" data-testid="zoom-fit" onClick={() => s.getState().setView(fitView(strokes.map((x) => x.points)))}>Fit</button>
              <button aria-label="Zoom in" data-testid="zoom-in" onClick={() => zoom(1.25)}>+</button>
            </div>
            <div className="canvas-wrap">
              <DrawCanvas overlay={overlay} />
              {strokes.length === 0 && (
                <div className="canvas-empty" data-testid="canvas-empty">
                  <b>Draw a creature, side view, facing right</b>
                  <span>Sketch a body, then a leg from the hip to the ankle, then a foot. Or start from an example below.</span>
                </div>
              )}
            </div>
            <div className="sk-below">
              <label><input type="checkbox" checked={guides} onChange={(e) => s.getState().setGuides(e.target.checked)} data-testid="toggle-guides" /> Grid and ground guide</label>
              <label><input type="checkbox" checked={template} onChange={(e) => setTemplate(e.target.checked)} /> Starter outline</label>
              <label><input type="checkbox" checked={showRaw} onChange={(e) => setShowRaw(e.target.checked)} data-testid="toggle-raw" /> Raw drawing</label>
              <label><input type="checkbox" checked={showInterp} onChange={(e) => setShowInterp(e.target.checked)} data-testid="toggle-interp" /> Interpreted structure</label>
              <small className="dim">Mouse, touch or pen · P pen · E erase · H pan (or hold Space) · wheel or pinch to zoom · Ctrl+Z undo</small>
            </div>
            <div className="starters" data-testid="starters">
              <span className="dim">Start from</span>
              {STARTERS.map((st) => <button key={st.id} className="chip-btn" title={st.hint} data-testid={`starter-${st.id}`} onClick={() => loadStarter(st.id)}>{st.label}{st.terrible ? ' ·bad' : ''}</button>)}
            </div>
          </section>

          <aside className="sk-inspector" aria-label="what Creature Forge sees">
            <div className={`outcome-badge tone-b-${out.tone}`} data-testid="outcome" data-outcome={vk}>
              <b>{out.label}</b><span>{out.text}</span>
            </div>
            {note && <div className="note-box" data-testid="starter-note">{note}</div>}
            {apiError && <div className="error" role="alert" data-testid="sketch-api-error">{apiError}</div>}

            {res && res.ambiguities.length > 0 && (
              <div className="ask" data-testid="ambiguity">
                {res.ambiguities.map((a, i) => (
                  <div key={i}><b>{a.message}</b>
                    <div className="opts">{a.options.map((o) => (
                      <button key={o.label} className="chip-btn" onMouseEnter={() => setHighlight(a.strokes[0])} onMouseLeave={() => setHighlight(null)}
                        onClick={() => Object.entries(o.assign).forEach(([id, role]) => s.getState().setRole(id, role))}>{o.label}</button>
                    ))}</div>
                  </div>
                ))}
              </div>
            )}

            {res && res.errors.length > 0 && res.status !== 'needs_input' && (
              <div className="why-not" data-testid="why-not" role="alert"><b>Why this cannot be built exactly</b><ul>{res.errors.map((e, i) => <li key={i}>{e}</li>)}</ul></div>
            )}

            {ap && (
              <div className="approx" data-testid="approximation">
                <b>Approximate it? Before and after</b>
                <MiniCompare a={ap.before} b={ap.after} />
                <small><i className="swatch" style={{ background: '#f2b441' }} /> what you drew · <i className="swatch" style={{ background: '#3cc9d6' }} /> what would be simulated</small>
                <ul>{ap.changes.map((c) => <li key={c.what}><b>{c.what}</b>: {c.from} → {c.to}</li>)}</ul>
                <label className="consent"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} data-testid="approx-consent" /> I understand this is a different creature from my drawing.</label>
                <button className="btn btn-create" disabled={!consent || busy} data-testid="approx-simulate" onClick={() => void sim(ap.body, ap.changes)}>Approximate and simulate</button>
              </div>
            )}

            {res && (res.adjustments.length > 0 || res.assumptions.length > 0 || res.notes.length > 0) && (
              <div className="reading" data-testid="reading">
                {res.adjustments.length > 0 && <><b>Snapped (interpretation only)</b><ul data-testid="adjustments">{res.adjustments.map((a, i) => <li key={i}>{a.message}</li>)}</ul></>}
                {res.assumptions.length > 0 && <><b>Assumed</b><ul data-testid="assumptions">{res.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></>}
                {res.notes.length > 0 && <><b>Worth knowing</b><ul data-testid="notes">{res.notes.map((a, i) => <li key={i}>{a}</li>)}</ul></>}
              </div>
            )}

            {strokes.length > 0 && res && (
              <details className="strokes-list" data-testid="strokes-list">
                <summary>What each stroke was read as</summary>
                {strokes.map((st) => (
                  <div key={st.id} className="stroke-row" onMouseEnter={() => setHighlight(st.id)} onMouseLeave={() => setHighlight(null)}>
                    <i style={{ background: ROLE_COLOR[(res.roles[st.id]?.role as PenRole) ?? 'auto'] }} />
                    <span>{st.id}</span>
                    <select aria-label={`role of ${st.id}`} data-testid={`role-${st.id}`} value={st.role} onChange={(e) => s.getState().setRole(st.id, e.target.value as PenRole)}>
                      <option value="auto">auto ({res.roles[st.id]?.role ?? '?'})</option><option value="torso">torso</option><option value="leg">leg</option><option value="foot">foot</option><option value="ignore">ignore</option>
                    </select>
                    <small className="dim">{res.roles[st.id]?.reason}</small>
                  </div>
                ))}
              </details>
            )}

            <div className="materials">
              <b>Materials{!guided && ' (wide experimental range)'}</b>
              {MATERIAL_FIELDS.map((f) => {
                const [lo, hi] = ranges?.[f.key] ?? [0, 1]
                return (
                  <label key={f.key} className="param"><span>{f.label} <b data-testid={`mat-${f.key}`}>{materials[f.key]}</b> {f.unit}</span>
                    <input type="range" min={lo} max={hi} step={f.step} value={Math.min(hi, Math.max(lo, materials[f.key]))} aria-label={f.label}
                      onChange={(e) => s.getState().setMaterial(f.key, Number(e.target.value))} /></label>
                )
              })}
            </div>

            <div className="sk-preview3d" data-testid="sketch-preview">
              {preview && res?.body ? <Viewport run={preview} label="The real MuJoCo model, standing at t = 0" /> : (
                <div className="viewport dimmed"><p className="dim pad">{res?.body === null && strokes.length ? 'No model yet. See the explanation above.' : 'Draw a creature to see its physical model.'}</p></div>
              )}
              {previewError && <div className="error">{previewError}</div>}
            </div>
            {simError && <div className="error" role="alert" data-testid="sim-error">{simError}</div>}
            <button className="btn btn-create btn-lg sim-btn" data-testid="simulate-btn" disabled={!canSim} onClick={() => res?.body && void sim(res.body, null)}>
              {busy ? 'Running MuJoCo…' : 'Simulate my creature'}
            </button>
            {onUseCreature && (
              <div className="use-creature" data-testid="use-creature">
                <label className="param"><span>Creature name</span>
                  <input type="text" maxLength={80} value={creatureName} onChange={(e) => setCreatureName(e.target.value)} data-testid="creature-name-input" aria-label="creature name" /></label>
                <button className="btn btn-simulate btn-lg sim-btn" data-testid="use-creature-btn" disabled={useBusy || !(res?.body || (ap && consent))} onClick={() => void useThisCreature()}>
                  {useBusy ? 'Saving...' : 'Use this creature'}
                </button>
                <small className="dim">Saves it as version 1 and opens the Forge workspace: challenge it, investigate, improve it.</small>
                {useError && <div className="error" role="alert" data-testid="use-creature-error">{useError}</div>}
              </div>
            )}
            {!canSim && strokes.length > 0 && !busy && <small className="dim" data-testid="sim-hint">{ap ? 'Confirm the approximation above to simulate it.' : 'Fix the points above, or turn Guided constraints off to try it anyway.'}</small>}
            {res?.body && <button className="link" data-testid="to-refine" onClick={() => setMode('refine')}>Refine joints with handles instead</button>}
          </aside>
        </div>
      )}
    </main>
  )
}

export type { Outcome }
