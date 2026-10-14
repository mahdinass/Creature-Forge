import { create } from 'zustand'
import type { PenRole, Pt, StrokeIn } from './freehandTypes'
import { DEFAULT_VIEW, strokeHit, thin, type View } from './strokes'

export type Tool = 'pen' | 'eraser' | 'pan'
export interface Stroke extends StrokeIn { width: number }

const KEY = 'creature-forge:sketch:v1'
const LIMIT = 100
export const DEFAULT_MATERIALS: Record<string, number> = { foot_friction: 1, torque_limit: 60, leg_density: 1000 }

interface State {
  strokes: Stroke[]
  past: Stroke[][]
  future: Stroke[][]
  nextId: number
  tool: Tool
  pen: PenRole
  guided: boolean
  guides: boolean
  materials: Record<string, number>
  view: View
  setTool: (t: Tool) => void
  setPen: (p: PenRole) => void
  setGuided: (g: boolean) => void
  setGuides: (g: boolean) => void
  setMaterial: (k: string, v: number) => void
  setView: (v: View) => void
  addStroke: (points: Pt[], width?: number) => void
  beginErase: () => void
  eraseAt: (p: Pt, radius: number) => number
  setRole: (id: string, role: PenRole) => void
  undo: () => void
  redo: () => void
  clear: () => void
  load: (strokes: StrokeIn[], opts?: { materials?: Record<string, number>; guided?: boolean }) => void
}

const push = (past: Stroke[][], cur: Stroke[]) => [...past, cur].slice(-LIMIT)

function restore(): Partial<State> {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return {}
    const d = JSON.parse(raw)
    if (!Array.isArray(d.strokes)) return {}
    return { strokes: d.strokes, nextId: d.nextId ?? d.strokes.length + 1, guided: d.guided !== false, materials: { ...DEFAULT_MATERIALS, ...(d.materials ?? {}) } }
  } catch {
    return {}
  }
}

function persist(s: State) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ strokes: s.strokes, nextId: s.nextId, guided: s.guided, materials: s.materials }))
  } catch {
    /* storage unavailable: the drawing still lives in memory */
  }
}

export const useSketch = create<State>((set, get) => ({
  strokes: [], past: [], future: [], nextId: 1, tool: 'pen', pen: 'auto', guided: true, guides: true, materials: { ...DEFAULT_MATERIALS }, view: DEFAULT_VIEW,
  ...restore(),
  setTool: (tool) => set({ tool }),
  setPen: (pen) => set({ pen, tool: 'pen' }),
  setGuided: (guided) => { set({ guided }); persist(get()) },
  setGuides: (guides) => set({ guides }),
  setMaterial: (k, v) => { set((s) => ({ materials: { ...s.materials, [k]: v } })); persist(get()) },
  setView: (view) => set({ view }),
  addStroke: (points, width = 5) => {
    const pts = thin(points)
    if (pts.length === 0) return
    set((s) => ({ strokes: [...s.strokes, { id: `s${s.nextId}`, role: s.pen, points: pts, width }], past: push(s.past, s.strokes), future: [], nextId: s.nextId + 1 }))
    persist(get())
  },
  beginErase: () => set((s) => ({ past: push(s.past, s.strokes), future: [] })),
  eraseAt: (p, radius) => {
    const keep = get().strokes.filter((st) => !strokeHit(st.points, p, radius))
    const removed = get().strokes.length - keep.length
    if (removed) { set({ strokes: keep }); persist(get()) }
    return removed
  },
  setRole: (id, role) => {
    set((s) => ({ strokes: s.strokes.map((st) => (st.id === id ? { ...st, role } : st)), past: push(s.past, s.strokes), future: [] }))
    persist(get())
  },
  undo: () => {
    const { past, strokes, future } = get()
    if (!past.length) return
    set({ strokes: past[past.length - 1], past: past.slice(0, -1), future: [strokes, ...future] })
    persist(get())
  },
  redo: () => {
    const { past, strokes, future } = get()
    if (!future.length) return
    set({ strokes: future[0], future: future.slice(1), past: push(past, strokes) })
    persist(get())
  },
  clear: () => {
    if (!get().strokes.length) return
    set((s) => ({ strokes: [], past: push(s.past, s.strokes), future: [] }))
    persist(get())
  },
  load: (strokes, opts) => {
    set((s) => ({
      strokes: strokes.map((st, i) => ({ ...st, id: `s${s.nextId + i}`, width: 5 })), past: push(s.past, s.strokes), future: [], nextId: s.nextId + strokes.length,
      materials: { ...DEFAULT_MATERIALS, ...(opts?.materials ?? {}) }, guided: opts?.guided ?? s.guided,
    }))
    persist(get())
  },
}))
