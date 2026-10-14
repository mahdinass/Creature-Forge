// Starter sketches: ordinary strokes (editable, erasable) placed on the canvas, so a first-time user can see what a good
// drawing looks like or jump straight to a deliberately bad one. The wobble is deterministic, not random.
import type { Pt, StrokeIn } from './freehandTypes'
import { PX_PER_M, WORLD } from './strokes'

const CX = 500
const px = (x: number, z: number): Pt => [CX + x * PX_PER_M, WORLD.groundY - z * PX_PER_M]

function line(a: [number, number], b: [number, number], n = 24, wobble = 1.1, seed = 0): Pt[] {
  const out: Pt[] = []
  for (let i = 0; i <= n; i++) {
    const t = i / n
    const [x, y] = px(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    out.push([Math.round((x + wobble * Math.sin(i * 1.3 + seed)) * 10) / 10, Math.round((y + wobble * Math.cos(i * 0.9 + seed)) * 10) / 10])
  }
  return out
}
const poly = (vs: [number, number][], seed = 0) => vs.slice(1).flatMap((v, i) => line(vs[i], v, 18, 1.1, seed + i))
const rect = (cx: number, z0: number, w: number, h: number, seed = 0) =>
  poly([[cx - w / 2, z0], [cx + w / 2, z0], [cx + w / 2, z0 + h], [cx - w / 2, z0 + h], [cx - w / 2, z0]], seed)

interface Spec { thigh: number; shank: number; foot: number; torsoW: number; torsoH: number; kneeBack: number; legGap: number }
const BASE: Spec = { thigh: 0.3, shank: 0.3, foot: 0.16, torsoW: 0.12, torsoH: 0.3, kneeBack: 0, legGap: 0.05 }

function figure(o: Partial<Spec>): StrokeIn[] {
  const s = { ...BASE, ...o }
  const hipZ = s.thigh + s.shank + 0.04
  const strokes: StrokeIn[] = [{ id: 'torso', role: 'torso', points: rect(0, hipZ, s.torsoW, s.torsoH, 1) }]
  ;[-s.legGap / 2, s.legGap / 2].forEach((dx, i) => {
    strokes.push({ id: `leg${i}`, role: 'leg', points: poly([[dx, hipZ], [dx - s.kneeBack, hipZ - s.thigh], [dx, 0.04]], 3 + i) })
    strokes.push({ id: `foot${i}`, role: 'foot', points: line([dx - 0.25 * s.foot, 0.04], [dx + 0.75 * s.foot, 0.04], 10, 0.8, 5 + i) })
  })
  return strokes
}

export interface Starter { id: string; label: string; hint: string; terrible: boolean; strokes: StrokeIn[]; materials?: Record<string, number> }

export const STARTERS: Starter[] = [
  { id: 'balanced', label: 'Balanced biped', hint: 'A sensible creature: it should stand.', terrible: false, strokes: figure({}) },
  { id: 'tiny-feet', label: 'Tiny feet', hint: 'A 3 cm foot under a normal body.', terrible: true, strokes: figure({ foot: 0.03 }) },
  { id: 'top-heavy', label: 'Top-heavy', hint: 'A huge torso on thin legs with small feet.', terrible: true, strokes: figure({ torsoW: 0.4, torsoH: 0.7, foot: 0.08 }) },
  { id: 'stilts', label: 'Stilts', hint: 'Very long legs, short feet.', terrible: true, strokes: figure({ thigh: 0.6, shank: 0.6, foot: 0.07 }) },
  { id: 'bird-knees', label: 'Bird knees', hint: 'Knees that bend the way this model allows.', terrible: false, strokes: figure({ kneeBack: 0.1 }) },
  { id: 'weak-slippery', label: 'Weak and slippery', hint: 'A normal shape with feeble motors and ice-like feet.', terrible: true, strokes: figure({}), materials: { torque_limit: 5, foot_friction: 0.05 } },
]
