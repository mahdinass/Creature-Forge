// Mirrors creature_forge/studio/do1_api.py: the verified DO-1 export (scripts/do1_demo_export.py) plus the verifier's
// recorded outcome from the audited DO1-L4-r0 record. Every number on the page comes from here.
import type { RunPayload } from '../types'

export type DesignId = 'faulty' | 'frozen' | 'do1'
export type RowGroup = DesignId | 'do1_confirm'

export interface Do1Row {
  seed: number
  outcome: string
  score: number
  walking: boolean
  fell: boolean
  label: string
  fall_time: number | null
  forward_disp_upright: number
  speed_upright: number
  body_contact_frac: number
  valid_steps: number
  error: string | null
  perturb: number
  push_time: number
  friction_used: number
}

export interface Do1Verdict {
  status: string
  wins: number
  losses: number
  ties: number
  non_tied: number
  median_diff: number
  p_one_sided: number
  min_effect: { abs: number; rel: number | null; required: number }
}

export interface Do1Check { value?: number; need?: number; passed: boolean; seeds_over?: number[]; max_frac?: number }

export interface Do1Verification {
  rule: string
  status: string
  reasons: string[]
  aggregate: string
  walking_frac: number
  verdict: Do1Verdict
  verdict_reasons: string[]
  confirmation: { run: boolean; reason?: string; passed?: boolean; duration?: number; checks?: Record<string, Do1Check> }
}

export interface Do1Index {
  schema: string
  exporter: string
  instance: string
  default_seed: number
  frame_state: string
  max_hz: number
  captions: { attribution: string; scope: string; seed: string }
  provenance: {
    record: string
    record_sha256: string
    manifest_sha256: string
    harness_commit: string
    arms_provenance: string
    exporter_commit: string
    environment: Record<string, string>
    arms_nemotron: (null | unknown)[]
    arms_provenance_recorded: string[]
  }
  seeds: { validate: number[]; confirm: number[] }
  rows: Record<RowGroup, Do1Row[]>
  aggregates: { walking: Record<RowGroup, number>; median_score_m: Record<RowGroup, number>; n: Record<RowGroup, number>; status: Record<'frozen' | 'do1', string> }
  fidelity: { production_rows_exact: number; trace_rows_exact: number; fk_max_err_m: number; fk_tol_m: number }
  verification: Record<'frozen' | 'do1', Do1Verification>
  criteria: { rule: string; pass_frac: number }
  available: string[]
}

export interface Do1Payload extends RunPayload {
  do1_demo: { design: DesignId; design_hash: string; duration_s: number; frame_state: string; evidence_row: Do1Row; fk_max_err_m: number }
}
