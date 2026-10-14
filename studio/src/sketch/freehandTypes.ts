// Mirrors creature_forge.freehand / creature_forge.sandbox.
export type PenRole = 'auto' | 'torso' | 'leg' | 'foot' | 'ignore'
export type Pt = [number, number]
export interface StrokeIn { id: string; role: PenRole; points: Pt[] }
export type Outcome = 'valid' | 'valid_with_snaps' | 'questionable' | 'unrepresentable'

export interface SandboxBodyDict {
  torso_mass: number; thigh_length: number; shank_length: number; foot_length: number
  foot_friction: number; torque_limit: number; leg_density: number
  thigh_length_r: number | null; shank_length_r: number | null; foot_length_r: number | null
  pose: number[]
}
export interface Skeleton {
  torso: { base: Pt; top: Pt; half_width: number }
  legs: { hip: Pt; knee: Pt; ankle: Pt; toe: Pt; heel: Pt }[]
  ground_y: number
}
export interface Ambiguity { kind: string; strokes: string[]; message: string; options: { label: string; assign: Record<string, PenRole> }[] }
export interface Change { what: string; from: number; to: number; why: string }
export interface Approximation { body: SandboxBodyDict; changes: Change[]; before: Skeleton; after: Skeleton; notice: string }
export interface Adjustment { kind: string; what: string; message: string }
export interface FreehandResult {
  status: 'ok' | 'needs_input' | 'unbuildable'
  outcome: Outcome
  roles: Record<string, { role: string; source: string; reason: string }>
  ambiguities: Ambiguity[]
  errors: string[]
  notes: string[]
  assumptions: string[]
  adjustments: Adjustment[]
  body: SandboxBodyDict | null
  approximation: Approximation | null
  skeleton: Skeleton | null
  detected?: Skeleton
  guided: boolean
}
export interface SandboxSchema {
  sandbox_bounds: Record<string, [number, number]>
  scientific_bounds: Record<string, [number, number]>
  pose_ranges: [number, number][]
  defaults: { push: { time: number; force: number; duration: number } }
}
export interface Explanation {
  verdict: 'fell' | 'stayed_upright'
  headline: string
  reasons: { kind: string; text: string; measured: Record<string, unknown> }[]
  design_notes: string[]
  caveat: string
}
