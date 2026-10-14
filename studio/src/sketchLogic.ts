// Pure helpers for the direct-manipulation sketch editor. Geometry here is only for feedback while dragging;
// the authoritative projection onto the supported biped is POST /api/sketch/normalize (creature_forge.sketch).
import type { Sketch } from './types'

export const GROUND_Z = 0.04 // ankle joint to sole, as in creature_forge.sketch.ANKLE_HEIGHT
export const TOE_FRACTION = 0.75
export const TORSO_HEIGHT = 0.3 // display extent above the hip (the torso shape is fixed)
export const MASS_RANGE: [number, number] = [1, 15]

export const SNAP = { vertical: 0.03, ground: 0.03, level: 0.02 }

type Pt = [number, number]
export type Nodes = Record<string, Pt>

export function sketchFromLengths(thigh: number, shank: number, foot: number): Sketch {
  const ankleZ = GROUND_Z
  const kneeZ = ankleZ + shank
  return {
    nodes: { hip: [0, kneeZ + thigh], knee: [0, kneeZ], ankle: [0, ankleZ], toe: [TOE_FRACTION * foot, ankleZ] },
    segments: [['hip', 'knee'], ['knee', 'ankle'], ['ankle', 'toe']],
  }
}

export const PRESETS: { id: string; label: string; hint: string; lengths: [number, number, number] }[] = [
  { id: 'default', label: 'Default', hint: '0.30 / 0.30 m legs, 16 cm foot', lengths: [0.3, 0.3, 0.16] },
  { id: 'long', label: 'Long legs', hint: 'taller, higher centre of mass', lengths: [0.45, 0.45, 0.16] },
  { id: 'stubby', label: 'Stubby', hint: 'short legs, low and stable', lengths: [0.18, 0.18, 0.16] },
  { id: 'big-feet', label: 'Big feet', hint: 'a 24 cm foot', lengths: [0.3, 0.3, 0.24] },
]

export interface DragResult { point: Pt; snaps: ('vertical' | 'ground' | 'level')[] }

/** Magnetic snapping while dragging `node` to `p` (soft constraints: only when already close). */
export function snapDrag(node: string, p: Pt, nodes: Nodes): DragResult {
  let [x, z] = p
  const snaps: DragResult['snaps'] = []
  const ankle = nodes.ankle
  if (node === 'ankle') {
    if (Math.abs(z - GROUND_Z) <= SNAP.ground) { z = GROUND_Z; snaps.push('ground') }
  } else if (node === 'hip' || node === 'knee') {
    if (Math.abs(x - ankle[0]) <= SNAP.vertical) { x = ankle[0]; snaps.push('vertical') }
  } else if (node === 'toe') {
    if (Math.abs(z - ankle[1]) <= SNAP.level) { z = ankle[1]; snaps.push('level') }
    x = Math.max(ankle[0] + 0.02, x)
  }
  return { point: [x, z], snaps }
}

export function massFromHandle(z: number, hipZ: number): number {
  const f = Math.min(1, Math.max(0, (z - hipZ) / TORSO_HEIGHT))
  return Math.round((MASS_RANGE[0] + f * (MASS_RANGE[1] - MASS_RANGE[0])) * 10) / 10
}

export function handleFromMass(mass: number, hipZ: number): number {
  return hipZ + ((mass - MASS_RANGE[0]) / (MASS_RANGE[1] - MASS_RANGE[0])) * TORSO_HEIGHT
}

/** Which nodes an error message talks about, so those handles can be shown in red. */
export function errorNodes(errors: string[]): string[] {
  const names = ['hip', 'knee', 'ankle', 'toe']
  return names.filter((n) => errors.some((e) => new RegExp(`\\b${n}\\b`, 'i').test(e)))
}

export function nodesEqual(a: Nodes, b: Nodes, tol = 1e-6): boolean {
  return Object.keys(a).every((k) => b[k] && Math.abs(a[k][0] - b[k][0]) <= tol && Math.abs(a[k][1] - b[k][1]) <= tol)
}
