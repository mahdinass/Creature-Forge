// Pure helpers for the freehand canvas. World units are canvas pixels (400 px = 1 m, y down), the same as the backend interpreter.
import type { Pt } from './freehandTypes'

export const PX_PER_M = 400
export const WORLD = { w: 1000, h: 700, groundY: 620 }

export interface View { x: number; y: number; k: number } // top-left world point of the viewport and zoom factor
export const MIN_K = 0.4
export const MAX_K = 4

/** Drop points closer than `min` to the previous kept point (keeps the last point so the stroke ends where the pen did). */
export function thin(points: Pt[], min = 2): Pt[] {
  if (points.length < 3) return points.slice()
  const out: Pt[] = [points[0]]
  for (let i = 1; i < points.length - 1; i++) {
    const p = out[out.length - 1]
    if (Math.hypot(points[i][0] - p[0], points[i][1] - p[1]) >= min) out.push(points[i])
  }
  out.push(points[points.length - 1])
  return out
}

/** Smooth SVG path through the points (quadratic curves through midpoints); a single tap becomes a dot. */
export function pathD(points: Pt[]): string {
  if (points.length === 0) return ''
  const f = (n: number) => n.toFixed(1)
  if (points.length === 1) return `M${f(points[0][0])} ${f(points[0][1])}l0.01 0`
  if (points.length === 2) return `M${f(points[0][0])} ${f(points[0][1])}L${f(points[1][0])} ${f(points[1][1])}`
  let d = `M${f(points[0][0])} ${f(points[0][1])}`
  for (let i = 1; i < points.length - 1; i++) {
    const mx = (points[i][0] + points[i + 1][0]) / 2
    const my = (points[i][1] + points[i + 1][1]) / 2
    d += `Q${f(points[i][0])} ${f(points[i][1])} ${f(mx)} ${f(my)}`
  }
  const last = points[points.length - 1]
  return d + `L${f(last[0])} ${f(last[1])}`
}

function distToSegment(p: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const len2 = dx * dx + dy * dy
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2))
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))
}

export function strokeHit(points: Pt[], p: Pt, radius: number): boolean {
  if (points.length === 1) return Math.hypot(points[0][0] - p[0], points[0][1] - p[1]) <= radius
  for (let i = 0; i < points.length - 1; i++) if (distToSegment(p, points[i], points[i + 1]) <= radius) return true
  return false
}

export const viewBox = (v: View) => `${v.x} ${v.y} ${WORLD.w / v.k} ${WORLD.h / v.k}`

/** Client pixel -> world point, given the svg's bounding rect and the current view. */
export function toWorld(v: View, rect: { left: number; top: number; width: number; height: number }, cx: number, cy: number): Pt {
  return [v.x + ((cx - rect.left) / rect.width) * (WORLD.w / v.k), v.y + ((cy - rect.top) / rect.height) * (WORLD.h / v.k)]
}

/** Zoom by `factor` keeping the world point under the cursor fixed. */
export function zoomAt(v: View, factor: number, pivot: Pt): View {
  const k = Math.max(MIN_K, Math.min(MAX_K, v.k * factor))
  const f = v.k / k
  return { k, x: pivot[0] - (pivot[0] - v.x) * f, y: pivot[1] - (pivot[1] - v.y) * f }
}

export function panBy(v: View, dxPx: number, dyPx: number, rectW: number, rectH: number): View {
  return { ...v, x: v.x - (dxPx / rectW) * (WORLD.w / v.k), y: v.y - (dyPx / rectH) * (WORLD.h / v.k) }
}

export const DEFAULT_VIEW: View = { x: 0, y: 0, k: 1 }

export function fitView(all: Pt[][], margin = 60): View {
  const pts = all.flat()
  if (pts.length === 0) return DEFAULT_VIEW
  const xs = pts.map((p) => p[0])
  const ys = pts.map((p) => p[1])
  const w = Math.max(80, Math.max(...xs) - Math.min(...xs)) + 2 * margin
  const h = Math.max(80, Math.max(...ys) - Math.min(...ys)) + 2 * margin
  const k = Math.max(MIN_K, Math.min(MAX_K, Math.min(WORLD.w / w, WORLD.h / h)))
  return { k, x: (Math.min(...xs) + Math.max(...xs)) / 2 - WORLD.w / k / 2, y: (Math.min(...ys) + Math.max(...ys)) / 2 - WORLD.h / k / 2 }
}
