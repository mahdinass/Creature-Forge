// Mirrors creature_forge.render_export.build_run_payload. All poses are MuJoCo output already
// converted to three.js (Y-up) by the backend; the frontend never computes physics.
export type Params = Record<string, number>

export interface Geom {
  type: 'capsule' | 'box'
  size: number[] // capsule: [radius, halfLength]; box: [hx, hy, hz] in three axes
  part: string
}

export interface FailureEvent {
  kind: string
  time: number
  evidence: Record<string, unknown>
}

export interface PushInfo {
  time: number
  force: number
  duration: number
}

export interface RunPayload {
  scene: { frame: string; geoms: Geom[]; display_lateral_offset: number }
  body: Params
  gait: Params
  seed: number
  duration: number
  push: PushInfo | null
  time: number[]
  frames: { pos: number[][][]; quat: number[][][]; contact_pos: number[][][] }
  series: {
    torso_height: number[]
    torso_pitch: number[]
    torso_x: number[]
    foot_contact: number[][]
    foot_slip_speed: number[][]
    max_torque_frac: number[]
  }
  events: FailureEvent[]
  metrics: {
    initial_torso_height: number
    min_torso_height: number
    final_torso_height: number
    max_abs_pitch: number
    peak_torso_vx: number
    fell: boolean
  }
}

export interface Schema {
  body: { bounds: Record<string, [number, number]>; defaults: Params }
  gait: { bounds: Record<string, [number, number]>; defaults: Params }
  preset: { push: PushInfo; seed: number; duration: number }
}

export interface SummaryArm {
  fall_rate: number
  mean_min_torso_height: number
  mean_max_abs_pitch: number
}

export interface Phase0 {
  baseline: RunPayload
  candidate: RunPayload
  matched_seed_summary: { seeds: number[]; baseline: SummaryArm; candidate: SummaryArm }
}

export interface Sketch {
  nodes: Record<string, [number, number]>
  segments: string[][]
}

export type CompileResult = { ok: true; params: Params } | { ok: false; errors: string[] }

export interface SketchAdjustment { kind: 'translate' | 'straighten' | 'level' | 'clamp'; node: string; message: string; amount: number }
export type NormalizeResult =
  | { ok: true; params: Params; sketch: Sketch; adjustments: SketchAdjustment[]; errors: string[] }
  | { ok: false; params: null; sketch: null; adjustments: SketchAdjustment[]; errors: string[] }
export interface SketchSupport {
  summary: string
  freedoms: Record<string, [number, number]>
  snaps: Record<string, number>
  not_supported: string[]
}
