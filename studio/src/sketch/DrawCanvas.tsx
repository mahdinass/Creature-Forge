import { useEffect, useRef, useState } from 'react'
import type { PenRole, Pt, Skeleton } from './freehandTypes'
import { useSketch } from './sketchStore'
import { pathD, PX_PER_M, panBy, toWorld, viewBox, WORLD, zoomAt } from './strokes'

export const ROLE_COLOR: Record<PenRole, string> = { auto: '#c4ccda', torso: '#7aa2ff', leg: '#f1f4fa', foot: '#4fd18b', ignore: '#6b7587' }

function SkeletonOverlay({ sk, tone, label }: { sk: Skeleton; tone: string; label: boolean }) {
  const { base, top, half_width: hw } = sk.torso
  const dx = top[0] - base[0]
  const dy = top[1] - base[1]
  const len = Math.hypot(dx, dy) || 1
  const nx = (-dy / len) * hw
  const ny = (dx / len) * hw
  const poly = [[base[0] - nx, base[1] - ny], [base[0] + nx, base[1] + ny], [top[0] + nx, top[1] + ny], [top[0] - nx, top[1] - ny]].map((p) => p.join(',')).join(' ')
  return (
    <g className="skel" style={{ color: tone }}>
      <polygon points={poly} fill="currentColor" fillOpacity={0.12} stroke="currentColor" strokeWidth={1.5} strokeDasharray="5 4" />
      {sk.legs.map((l, i) => (
        <g key={i}>
          <polyline points={`${l.hip[0]},${l.hip[1]} ${l.knee[0]},${l.knee[1]} ${l.ankle[0]},${l.ankle[1]}`} fill="none" stroke="currentColor" strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" opacity={0.85} />
          <line x1={l.heel[0]} y1={l.heel[1]} x2={l.toe[0]} y2={l.toe[1]} stroke="currentColor" strokeWidth={4} strokeLinecap="round" opacity={0.85} />
          {(['hip', 'knee', 'ankle', 'toe'] as const).map((j) => (
            <g key={j}>
              <circle cx={l[j][0]} cy={l[j][1]} r={5.5} fill="#0d1016" stroke="currentColor" strokeWidth={2.5} />
              {label && i === 0 && <text x={l[j][0] + 9} y={l[j][1] - 8} className="joint-label">{j}</text>}
            </g>
          ))}
        </g>
      ))}
    </g>
  )
}

export interface CanvasOverlay { compiled: Skeleton | null; before: Skeleton | null; showInterpretation: boolean; showRaw: boolean; template: boolean; highlight: string | null }

/** Freehand drawing surface: mouse, touch and pen (pointer events), smooth strokes, eraser, pan, wheel/pinch zoom. */
export function DrawCanvas({ overlay }: { overlay: CanvasOverlay }) {
  const { strokes, tool, pen, view, guides } = useSketch()
  const st = useSketch.getState
  const svg = useRef<SVGSVGElement>(null)
  const [draft, setDraft] = useState<Pt[] | null>(null)
  const draftRef = useRef<Pt[] | null>(null)
  const pressure = useRef<number[]>([])
  const mode = useRef<'none' | 'draw' | 'erase' | 'pan' | 'pinch'>('none')
  const pointers = useRef(new Map<number, [number, number]>())
  const last = useRef<[number, number]>([0, 0])
  const pinch = useRef(0)
  const space = useRef(false)
  const [cursor, setCursor] = useState<Pt | null>(null)

  const rect = () => svg.current!.getBoundingClientRect()
  const world = (cx: number, cy: number) => toWorld(useSketch.getState().view, rect(), cx, cy)

  // wheel zoom needs a non-passive listener to stop the page from scrolling
  useEffect(() => {
    const el = svg.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const v = useSketch.getState().view
      useSketch.getState().setView(zoomAt(v, Math.exp(-e.deltaY * 0.0015), toWorld(v, el.getBoundingClientRect(), e.clientX, e.clientY)))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  useEffect(() => {
    const typing = (t: EventTarget | null) => t instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)
    const down = (e: KeyboardEvent) => {
      if (typing(e.target)) return
      const mod = e.ctrlKey || e.metaKey
      if (e.code === 'Space') { space.current = true; e.preventDefault() }
      else if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? st().redo() : st().undo() }
      else if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); st().redo() }
      else if (!mod && e.key.toLowerCase() === 'p') st().setTool('pen')
      else if (!mod && e.key.toLowerCase() === 'e') st().setTool('eraser')
      else if (!mod && e.key.toLowerCase() === 'h') st().setTool('pan')
    }
    const up = (e: KeyboardEvent) => { if (e.code === 'Space') space.current = false }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
  }, [st])

  const onDown = (e: React.PointerEvent) => {
    ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
    pointers.current.set(e.pointerId, [e.clientX, e.clientY])
    if (pointers.current.size === 2) {
      draftRef.current = null; setDraft(null)
      mode.current = 'pinch'
      const [a, b] = [...pointers.current.values()]
      pinch.current = Math.hypot(a[0] - b[0], a[1] - b[1])
      return
    }
    last.current = [e.clientX, e.clientY]
    if (e.button === 1 || e.button === 2 || space.current || tool === 'pan') { mode.current = 'pan'; return }
    if (e.button !== 0) return
    if (tool === 'eraser') {
      mode.current = 'erase'
      st().beginErase()
      st().eraseAt(world(e.clientX, e.clientY), 12 / view.k)
      return
    }
    mode.current = 'draw'
    pressure.current = [e.pressure || 0.5]
    draftRef.current = [world(e.clientX, e.clientY)]
    setDraft(draftRef.current)
  }
  const onMove = (e: React.PointerEvent) => {
    const w = world(e.clientX, e.clientY)
    setCursor(w)
    if (pointers.current.has(e.pointerId)) pointers.current.set(e.pointerId, [e.clientX, e.clientY])
    const r = rect()
    if (mode.current === 'pinch' && pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()]
      const d = Math.hypot(a[0] - b[0], a[1] - b[1])
      if (pinch.current > 0) {
        const v = st().view
        const mid = toWorld(v, r, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        st().setView(zoomAt(v, d / pinch.current, mid))
      }
      pinch.current = d
    } else if (mode.current === 'pan') {
      st().setView(panBy(st().view, e.clientX - last.current[0], e.clientY - last.current[1], r.width, r.height))
      last.current = [e.clientX, e.clientY]
    } else if (mode.current === 'erase') {
      st().eraseAt(w, 12 / st().view.k)
    } else if (mode.current === 'draw' && draftRef.current) {
      const p = draftRef.current[draftRef.current.length - 1]
      if (Math.hypot(w[0] - p[0], w[1] - p[1]) >= 1.2 / st().view.k) {
        draftRef.current = [...draftRef.current, w]
        pressure.current.push(e.pressure || 0.5)
        setDraft(draftRef.current)
      }
    }
  }
  const onUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId)
    if (mode.current === 'draw' && draftRef.current && draftRef.current.length >= 2) {
      const avg = pressure.current.reduce((a, b) => a + b, 0) / pressure.current.length
      st().addStroke(draftRef.current, e.pointerType === 'pen' ? 3 + 5 * avg : 5)
    }
    if (pointers.current.size < 2 && mode.current === 'pinch') mode.current = 'none'
    if (pointers.current.size === 0) mode.current = 'none'
    draftRef.current = null
    setDraft(null)
  }

  const cur = tool === 'pan' || space.current ? 'grab' : tool === 'eraser' ? 'cell' : 'crosshair'
  const gx = []
  for (let x = 0; x <= WORLD.w; x += PX_PER_M / 4) gx.push(x)
  const gy = []
  for (let y = WORLD.groundY % (PX_PER_M / 4); y <= WORLD.h; y += PX_PER_M / 4) gy.push(y)
  return (
    <svg ref={svg} className="draw-canvas" data-testid="draw-canvas" viewBox={viewBox(view)} style={{ cursor: cur }} role="application"
      aria-label="Drawing canvas. Draw a side view of a two-legged creature facing right."
      onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onPointerLeave={() => setCursor(null)} onContextMenu={(e) => e.preventDefault()}>
      <rect x={-2000} y={-2000} width={5000} height={5000} fill="#10141c" />
      {guides && (
        <g className="guides" data-testid="guides">
          {gx.map((x) => <line key={`x${x}`} x1={x} x2={x} y1={-2000} y2={3000} className={x % PX_PER_M === 0 ? 'g-major' : 'g-minor'} />)}
          {gy.map((y) => <line key={`y${y}`} x1={-2000} x2={3000} y1={y} y2={y} className="g-minor" />)}
          <line x1={-2000} x2={3000} y1={WORLD.groundY} y2={WORLD.groundY} className="g-ground" />
          <text x={16} y={WORLD.groundY + 22} className="g-label">ground</text>
          <g transform={`translate(${WORLD.w - 40 - PX_PER_M}, ${WORLD.groundY + 34})`}>
            <line x1={0} x2={PX_PER_M} y1={0} y2={0} stroke="#8f9aae" strokeWidth={2} /><line x1={0} x2={0} y1={-5} y2={5} stroke="#8f9aae" strokeWidth={2} /><line x1={PX_PER_M} x2={PX_PER_M} y1={-5} y2={5} stroke="#8f9aae" strokeWidth={2} />
            <text x={PX_PER_M / 2} y={20} textAnchor="middle" className="g-label">1 metre</text>
          </g>
          <g transform={`translate(${WORLD.w - 150}, 36)`}><text className="g-label">faces right →</text></g>
        </g>
      )}
      {overlay.template && (
        <g className="template" opacity={0.35} aria-hidden="true">
          <rect x={500 - 24} y={WORLD.groundY - 0.64 * PX_PER_M - 0.3 * PX_PER_M} width={48} height={0.3 * PX_PER_M} fill="none" stroke="#8f9aae" strokeDasharray="6 6" />
          <polyline points={`500,${WORLD.groundY - 0.64 * PX_PER_M} 500,${WORLD.groundY - 0.34 * PX_PER_M} 500,${WORLD.groundY - 0.04 * PX_PER_M}`} fill="none" stroke="#8f9aae" strokeDasharray="6 6" strokeWidth={3} />
          <line x1={500 - 16} x2={500 + 48} y1={WORLD.groundY - 0.04 * PX_PER_M} y2={WORLD.groundY - 0.04 * PX_PER_M} stroke="#8f9aae" strokeDasharray="6 6" strokeWidth={3} />
        </g>
      )}
      {overlay.showRaw && strokes.map((s) => (
        <path key={s.id} d={pathD(s.points)} data-testid="stroke" data-role={s.role} data-id={s.id} fill="none" stroke={ROLE_COLOR[s.role]} strokeWidth={s.width / view.k * 0.9 + 1.2}
          strokeLinecap="round" strokeLinejoin="round" opacity={overlay.highlight && overlay.highlight !== s.id ? 0.35 : 1} strokeDasharray={s.role === 'ignore' ? '2 8' : undefined} />
      ))}
      {draft && <path d={pathD(draft)} fill="none" stroke={ROLE_COLOR[pen]} strokeWidth={5 / view.k * 0.9 + 1.2} strokeLinecap="round" strokeLinejoin="round" opacity={0.9} />}
      {overlay.before && <SkeletonOverlay sk={overlay.before} tone="#f2b441" label={false} />}
      {overlay.showInterpretation && overlay.compiled && <SkeletonOverlay sk={overlay.compiled} tone="#3cc9d6" label />}
      {tool === 'eraser' && cursor && <circle cx={cursor[0]} cy={cursor[1]} r={12 / view.k} fill="none" stroke="#ff5d6c" strokeDasharray="3 3" pointerEvents="none" />}
    </svg>
  )
}
