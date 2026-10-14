import { useEffect, useMemo, useRef, useState } from 'react'
import { getSketchSupport, normalizeSketch, simulate } from './api'
import { usePlayback } from './store'
import {
  errorNodes, GROUND_Z, handleFromMass, massFromHandle, nodesEqual, PRESETS, sketchFromLengths, snapDrag, TORSO_HEIGHT, type Nodes,
} from './sketchLogic'
import { Viewport } from './Viewport'
import type { NormalizeResult, Params, RunPayload, Sketch, SketchAdjustment, SketchSupport } from './types'

// Uniform scale so lengths look right: metres -> pixels. Side view, x forward, z up.
const S = 300
const VW = 400
const VH = 560
const X0 = -0.45
const Z0 = -0.17
const sx = (x: number) => (x - X0) * S
const sz = (z: number) => VH - (z - Z0) * S
const ux = (px: number) => px / S + X0
const uz = (py: number) => (VH - py) / S + Z0

const EXTRA_SLIDERS: { key: string; label: string; unit: string; step: number }[] = [
  { key: 'foot_friction', label: 'Foot grip (friction μ)', unit: '', step: 0.05 },
  { key: 'torque_limit', label: 'Motor strength (torque limit)', unit: 'N·m', step: 1 },
  { key: 'leg_density', label: 'Leg material density', unit: 'kg/m³', step: 50 },
]
const dist = (a: [number, number], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1])

/** Direct-manipulation editor for the supported planar biped. Drag any joint freely; the server projects the drawing onto
 *  what MuJoCo can build, reports every adjustment, and refuses (with reasons) anything it cannot represent. */
export function SketchEditor({ initialBody, onUse }: { initialBody: Params; onUse: (params: Params) => void }) {
  const startSketch = (b: Params): Sketch => sketchFromLengths(b.thigh_length, b.shank_length, b.foot_length)
  const [nodes, setNodes] = useState<Nodes>(() => startSketch(initialBody).nodes as Nodes)
  const [extras, setExtras] = useState<Params>(() => ({
    torso_mass: initialBody.torso_mass, foot_friction: initialBody.foot_friction, torque_limit: initialBody.torque_limit, leg_density: initialBody.leg_density,
  }))
  const [result, setResult] = useState<NormalizeResult | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [support, setSupport] = useState<SketchSupport | null>(null)
  const [drag, setDrag] = useState<string | null>(null)
  const [snaps, setSnaps] = useState<string[]>([])
  const [notice, setNotice] = useState<SketchAdjustment[]>([]) // what the last release snapped; the committed sketch no longer differs
  const [preview, setPreview] = useState<RunPayload | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const svg = useRef<SVGSVGElement>(null)
  const req = useRef(0)
  const previewReq = useRef(0)
  const resultFor = useRef<Nodes | null>(null) // the drawing the current `result` was computed for
  const pendingCommit = useRef(false) // released before the server answered: commit when it does
  const segments = useMemo(() => startSketch(initialBody).segments, [initialBody]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { getSketchSupport().then(setSupport).catch((e: Error) => setApiError(e.message)) }, [])

  // Normalise the drawing on the server (debounced; stale answers are discarded).
  useEffect(() => {
    const mine = ++req.current
    const id = setTimeout(() => {
      normalizeSketch({ nodes, segments }, extras)
        .then((r) => {
          if (mine !== req.current) return
          resultFor.current = nodes
          setResult(r)
          setApiError(null)
          if (pendingCommit.current && r.ok) {
            pendingCommit.current = false
            setNotice(r.adjustments)
            setNodes(r.sketch.nodes as Nodes)
          }
        })
        .catch((e: Error) => { if (mine === req.current) setApiError(e.message) })
    }, 100)
    return () => clearTimeout(id)
  }, [nodes, extras, segments])

  // Physical preview: the compiled MuJoCo model standing at t = 0 (a 0.5 s run, shown paused on its first frame).
  const okParams = result?.ok ? result.params : null
  const paramsKey = okParams ? JSON.stringify(okParams) : ''
  useEffect(() => {
    if (!okParams) return
    const mine = ++previewReq.current
    const id = setTimeout(() => {
      simulate(okParams, 0, 0.5, null)
        .then((r) => {
          if (mine !== previewReq.current) return
          setPreview(r); setPreviewError(null)
          const pb = usePlayback.getState()
          pb.setDuration(r.duration); pb.seek(0)
        })
        .catch((e: Error) => { if (mine === previewReq.current) setPreviewError(e.message) })
    }, 350)
    return () => clearTimeout(id)
  }, [paramsKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const toUser = (e: { clientX: number; clientY: number }): [number, number] => {
    const r = svg.current!.getBoundingClientRect()
    return [ux(((e.clientX - r.left) / r.width) * VW), uz(((e.clientY - r.top) / r.height) * VH)]
  }
  const move = (e: React.PointerEvent) => {
    if (!drag || !svg.current) return
    const [x, z] = toUser(e)
    if (drag === 'mass') {
      setExtras((p) => ({ ...p, torso_mass: massFromHandle(z, nodes.hip[1]) }))
      return
    }
    const s = snapDrag(drag, [x, z], nodes)
    setSnaps(s.snaps)
    setNodes({ ...nodes, [drag]: s.point })
  }
  const release = () => {
    if (drag && drag !== 'mass') {
      if (result?.ok && resultFor.current === nodes) {
        setNotice(result.adjustments)
        setNodes(result.sketch.nodes as Nodes) // commit what the physics will actually get
      } else {
        pendingCommit.current = true // the answer for this drawing has not arrived yet; never commit a stale one
      }
    }
    setDrag(null)
    setSnaps([])
  }
  const loadPreset = (l: [number, number, number]) => { pendingCommit.current = false; setNotice([]); setNodes(sketchFromLengths(...l).nodes as Nodes) }

  const solid: Nodes = drag || !result?.ok ? nodes : (result.sketch.nodes as Nodes)
  const ghost = result?.ok && !nodesEqual(nodes, result.sketch.nodes as Nodes, 1e-3) ? nodes : null
  const errors = result && !result.ok ? result.errors : []
  const bad = new Set(errorNodes(errors))
  const adjusted = new Set(result?.adjustments.map((a) => a.node) ?? [])
  const invalid = errors.length > 0
  const col = (k: string) => (bad.has(k) ? '#e5484d' : drag === k ? '#fff' : adjusted.has(k) ? '#3fb97f' : '#6f8fd8')
  const hipZ = solid.hip[1]
  const mass = extras.torso_mass
  const mz = handleFromMass(mass, hipZ)
  const lines: [string, string][] = [['hip', 'knee'], ['knee', 'ankle']]
  const thigh = dist(solid.hip, solid.knee)
  const shank = dist(solid.knee, solid.ankle)
  const foot = dist(solid.ankle, solid.toe) / 0.75
  const mid = (a: string, b: string): [number, number] => [(solid[a][0] + solid[b][0]) / 2, (solid[a][1] + solid[b][1]) / 2]

  return (
    <div className="sketch2" data-testid="sketch-editor">
      <div className="panel sk-side">
        <h3>Shape your creature</h3>
        <p className="note">
          Grab any <b>joint</b> and drag it: hip, knee, ankle or toe. Drag the <b>side handle on the torso</b> to change its mass. Drawings that are
          <i> almost</i> a supported biped snap into place (and you are told what moved); anything else is explained, not guessed.
        </p>
        <div className="presets" aria-label="starting shapes">
          {PRESETS.map((p) => <button key={p.id} title={p.hint} data-testid={`preset-${p.id}`} onClick={() => loadPreset(p.lengths)}>{p.label}</button>)}
        </div>

        <h4>What your drawing compiles to</h4>
        <table className="compiled" data-testid="sketch-compiled"><tbody>
          {result?.ok && ['thigh_length', 'shank_length', 'foot_length', 'torso_mass'].map((k) => (
            <tr key={k}><td>{k.replace('_', ' ')}</td><td>{result.params[k].toFixed(k === 'torso_mass' ? 1 : 3)} {k === 'torso_mass' ? 'kg' : 'm'}</td></tr>
          ))}
          {!result?.ok && <tr><td colSpan={2} className="dim">{result ? 'not buildable yet; see below' : 'compiling…'}</td></tr>}
        </tbody></table>

        {invalid && (
          <div className="sk-errors" role="alert" data-testid="sketch-errors">
            <b>This shape cannot be simulated</b>
            <ul>{errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
            <small>Nothing was changed or substituted. Move the highlighted joints back, or press a starting shape.</small>
          </div>
        )}
        {result?.ok && (drag ? result.adjustments : notice).length > 0 && (
          <div className="sk-adjust" data-testid="sketch-adjustments">
            <b>{drag ? 'Will snap to the supported biped' : 'Snapped to the supported biped'}</b>
            <ul>{(drag ? result.adjustments : notice).map((a, i) => <li key={i} data-kind={a.kind}>{a.message}</li>)}</ul>
          </div>
        )}
        {result?.ok && result.adjustments.length === 0 && notice.length === 0 && !drag && <p className="sk-good" data-testid="sketch-valid">✓ Valid: this drawing maps exactly to a MuJoCo model.</p>}
        {apiError && <div className="error" data-testid="sketch-api-error">{apiError}</div>}

        <h4>Body and materials</h4>
        {EXTRA_SLIDERS.map((s) => {
          const [lo, hi] = support?.freedoms[s.key] ?? [0, 1]
          return (
            <label className="param" key={s.key}>
              <span>{s.label} <b>{extras[s.key]}</b> {s.unit}</span>
              <input type="range" min={lo} max={hi} step={s.step} value={extras[s.key]} aria-label={s.label}
                onChange={(e) => setExtras((p) => ({ ...p, [s.key]: Number(e.target.value) }))} />
            </label>
          )
        })}

        <button className="forge" data-testid="sketch-simulate" disabled={!result?.ok} onClick={() => result?.ok && onUse(result.params)}>
          Simulate this creature →
        </button>
        <details className="support" data-testid="sketch-support">
          <summary>What can and can’t be built?</summary>
          {support ? (
            <>
              <p>{support.summary}</p>
              <b>Not supported (and refused, never approximated):</b>
              <ul>{support.not_supported.map((s) => <li key={s}>{s}</li>)}</ul>
            </>
          ) : <small>loading…</small>}
        </details>
      </div>

      <svg ref={svg} className={`sketch-svg ${invalid ? 'invalid' : ''}`} viewBox={`0 0 ${VW} ${VH}`} onPointerMove={move} onPointerUp={release} onPointerLeave={release}
        data-testid="sketch-svg" role="application" aria-label="creature sketch: drag the joints">
        <rect x={0} y={sz(0)} width={VW} height={VH - sz(0)} fill="#161d2a" />
        <line x1={0} x2={VW} y1={sz(0)} y2={sz(0)} stroke="#4a5a78" />
        <text x={8} y={sz(0) + 16} className="axis">ground</text>
        {/* magnetic guides */}
        <line x1={sx(solid.ankle[0])} x2={sx(solid.ankle[0])} y1={sz(hipZ + TORSO_HEIGHT + 0.05)} y2={sz(0)} stroke={snaps.includes('vertical') ? '#3fb97f' : '#2b3548'}
          strokeDasharray="4 5" strokeWidth={snaps.includes('vertical') ? 2 : 1} data-testid="guide-vertical" />
        {snaps.includes('ground') && <line x1={0} x2={VW} y1={sz(GROUND_Z)} y2={sz(GROUND_Z)} stroke="#3fb97f" strokeDasharray="4 5" />}
        {/* torso (fixed shape; mass only) */}
        <rect x={sx(-0.06)} y={sz(hipZ + TORSO_HEIGHT)} width={0.12 * S} height={TORSO_HEIGHT * S} rx={6} fill="#6f8fd8" opacity={0.18 + (mass / 15) * 0.5} />
        <text x={sx(-0.06)} y={sz(hipZ + TORSO_HEIGHT) - 6} className="axis">torso {mass.toFixed(1)} kg (shape fixed)</text>
        {/* ghost = what you drew, when it differs from what will be simulated */}
        {ghost && (
          <g data-testid="sketch-ghost" opacity={0.45}>
            {([['hip', 'knee'], ['knee', 'ankle'], ['ankle', 'toe']] as const).map(([a, b]) => (
              <line key={a + b} x1={sx(ghost[a][0])} y1={sz(ghost[a][1])} x2={sx(ghost[b][0])} y2={sz(ghost[b][1])} stroke="#e5ecff" strokeWidth={3} strokeDasharray="5 5" />
            ))}
          </g>
        )}
        {lines.map(([a, b]) => (
          <line key={a + b} x1={sx(solid[a][0])} y1={sz(solid[a][1])} x2={sx(solid[b][0])} y2={sz(solid[b][1])} stroke={invalid ? '#8b6a6c' : '#c9ccd6'} strokeWidth={7} strokeLinecap="round" />
        ))}
        <line x1={sx(solid.ankle[0] - 0.25 * (solid.toe[0] - solid.ankle[0]) / 0.75)} y1={sz(solid.ankle[1])} x2={sx(solid.toe[0])} y2={sz(solid.toe[1])}
          stroke={invalid ? '#8b6a6c' : '#8892a8'} strokeWidth={7} strokeLinecap="round" />
        {/* live dimensions */}
        {([['hip', 'knee', thigh, 'thigh'], ['knee', 'ankle', shank, 'shank']] as const).map(([a, b, len, name]) => (
          <text key={name} x={sx(mid(a, b)[0]) + 14} y={sz(mid(a, b)[1]) + 4} className="dim-label" data-testid={`dim-${name}`}>{name} {len.toFixed(2)} m</text>
        ))}
        <text x={sx(solid.ankle[0])} y={sz(0) + 32} className="dim-label" textAnchor="start">foot {foot.toFixed(2)} m</text>
        {/* mass handle */}
        <g style={{ cursor: 'ns-resize' }} data-testid="handle-mass" onPointerDown={(e) => { (e.target as Element).setPointerCapture(e.pointerId); setDrag('mass'); setNotice([]) }}>
          <rect data-testid="handle-mass-grip" x={sx(0.06) + 6} y={sz(mz) - 9} width={26} height={18} rx={5} fill={drag === 'mass' ? '#fff' : '#a99bff'} stroke="#10141c" strokeWidth={2} />
          <text x={sx(0.06) + 38} y={sz(mz) + 4} className="axis">mass</text>
        </g>
        {Object.entries(solid).map(([k, [x, z]]) => (
          <g key={k}>
            <circle cx={sx(x)} cy={sz(z)} r={11} fill={col(k)} stroke="#10141c" strokeWidth={2} style={{ cursor: 'grab' }} data-testid={`handle-${k}`}
              onPointerDown={(e) => { (e.target as Element).setPointerCapture(e.pointerId); setDrag(k); setNotice([]); pendingCommit.current = false }} />
            <text x={sx(x) + 16} y={sz(z) - 10} className="axis">{k}</text>
          </g>
        ))}
        {invalid && <text x={VW / 2} y={30} textAnchor="middle" fill="#ff7b80" fontSize={13}>Not buildable: see the explanation on the left</text>}
      </svg>

      <div className="sk-preview" data-testid="sketch-preview">
        <h4>Physical preview</h4>
        {preview && okParams ? (
          <Viewport run={preview} label="Compiled MuJoCo model, standing at t = 0" />
        ) : <div className="viewport dimmed"><p className="dim pad">{invalid ? 'No model: the drawing is not buildable.' : 'Compiling the MuJoCo model…'}</p></div>}
        {previewError && <div className="error">{previewError}</div>}
        <small className="dim">This is the real MuJoCo model your drawing compiles to (legs drawn apart for clarity; the physics is planar). Nothing has been pushed or walked yet.</small>
      </div>
    </div>
  )
}
