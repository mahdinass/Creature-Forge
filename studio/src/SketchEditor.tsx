import { useEffect, useRef, useState } from 'react'
import { compileSketch, getDefaultSketch } from './api'
import type { CompileResult, Params, Sketch } from './types'

// View: x in [-0.6, 0.6] m, z in [-0.05, 1.0] m (side view, x forward, z up).
const VW = 360
const VH = 520
const X0 = -0.45
const X1 = 0.75
const Z0 = -0.05
const Z1 = 1.0
const sx = (x: number) => ((x - X0) / (X1 - X0)) * VW
const sz = (z: number) => VH - ((z - Z0) / (Z1 - Z0)) * VH
const ux = (px: number) => X0 + (px / VW) * (X1 - X0)
const uz = (py: number) => Z0 + ((VH - py) / VH) * (Z1 - Z0)

/** Constrained editor: hip/knee/ankle slide vertically (straight leg), the toe slides horizontally. */
export function SketchEditor({ onUse }: { onUse: (params: Params) => void }) {
  const [sketch, setSketch] = useState<Sketch | null>(null)
  const [result, setResult] = useState<CompileResult | null>(null)
  const [drag, setDrag] = useState<string | null>(null)
  const svg = useRef<SVGSVGElement>(null)

  useEffect(() => void getDefaultSketch().then(setSketch), [])
  useEffect(() => {
    if (!sketch) return
    const id = setTimeout(() => void compileSketch(sketch).then(setResult).catch(() => setResult(null)), 150)
    return () => clearTimeout(id)
  }, [sketch])
  if (!sketch) return <div className="panel">Loading sketch…</div>

  const move = (e: React.PointerEvent) => {
    if (!drag || !svg.current) return
    const r = svg.current.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * VW
    const py = ((e.clientY - r.top) / r.height) * VH
    const nodes = { ...sketch.nodes }
    if (drag === 'toe') nodes.toe = [Math.max(sketch.nodes.ankle[0] + 0.02, ux(px)), sketch.nodes.ankle[1]]
    else {
      const z = Math.min(Z1, Math.max(0.04, uz(py)))
      nodes[drag] = [0, z]
      if (drag === 'ankle') nodes.toe = [sketch.nodes.toe[0], z]
    }
    setSketch({ ...sketch, nodes })
  }
  const n = sketch.nodes
  const col = (k: string) => (drag === k ? '#fff' : '#6f8fd8')
  return (
    <div className="sketch">
      <div className="panel">
        <h3>Sketch → Creature</h3>
        <p className="note">
          Constrained skeleton editor for the supported biped template. Drag the <b>hip</b>, <b>knee</b>, <b>ankle</b> (vertical) and
          <b> toe</b> (horizontal). Lengths are compiled to MuJoCo parameters by the same validator the server uses.
          Arbitrary drawings and bent-knee poses are <b>not</b> supported and are rejected with reasons.
        </p>
        {result?.ok && (
          <table className="compiled"><tbody>
            {['thigh_length', 'shank_length', 'foot_length'].map((k) => (
              <tr key={k}><td>{k}</td><td>{result.params[k].toFixed(3)} m</td></tr>
            ))}
          </tbody></table>
        )}
        {result && !result.ok && <div className="error">{result.errors.map((e, i) => <div key={i}>{e}</div>)}</div>}
        <button className="forge" disabled={!result?.ok} onClick={() => result?.ok && onUse(result.params)}>
          Use in Studio →
        </button>
        <button className="link" onClick={() => void getDefaultSketch().then(setSketch)}>reset</button>
      </div>
      <svg ref={svg} className="sketch-svg" viewBox={`0 0 ${VW} ${VH}`} onPointerMove={move}
        onPointerUp={() => setDrag(null)} onPointerLeave={() => setDrag(null)}>
        <line x1={0} x2={VW} y1={sz(0)} y2={sz(0)} stroke="#4a5a78" />
        <rect x={sx(-0.06)} y={sz(n.hip[1] + 0.3)} width={sx(0.06) - sx(-0.06)}
          height={sz(n.hip[1]) - sz(n.hip[1] + 0.3)} fill="#6f8fd8" opacity={0.25} />
        <text x={sx(-0.06)} y={sz(n.hip[1] + 0.3) - 4} className="axis">torso (fixed geometry)</text>
        {(['hip', 'knee', 'ankle', 'toe'] as const).slice(0, 3).map((a, i, arr) => i < 2 && (
          <line key={a} x1={sx(n[a][0])} y1={sz(n[a][1])} x2={sx(n[arr[i + 1]][0])} y2={sz(n[arr[i + 1]][1])}
            stroke="#c9ccd6" strokeWidth={6} strokeLinecap="round" />
        ))}
        <line x1={sx(n.ankle[0] - 0.25 * (n.toe[0] - n.ankle[0]) / 0.75)} y1={sz(n.ankle[1])} x2={sx(n.toe[0])} y2={sz(n.toe[1])}
          stroke="#8892a8" strokeWidth={6} strokeLinecap="round" />
        {Object.entries(n).map(([k, [x, z]]) => (
          <g key={k}>
            <circle cx={sx(x)} cy={sz(z)} r={9} fill={col(k)} stroke="#10141c" strokeWidth={2} style={{ cursor: 'grab' }}
              onPointerDown={(e) => { (e.target as Element).setPointerCapture(e.pointerId); setDrag(k) }} />
            <text x={sx(x) + 13} y={sz(z) + 4} className="axis">{k}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}
