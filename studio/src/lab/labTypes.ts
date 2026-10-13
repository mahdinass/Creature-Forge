// Mirrors creature_forge.lab (read-only investigation records). Nothing here is computed in the browser.
import type { RunPayload } from '../types'

export type TrialStatus =
  | 'accepted'
  | 'rejected_by_verifier'
  | 'invalid_model_output'
  | 'model_error'
  | 'budget_exceeded'
  | 'started'
  | 'unreadable'
  | string

export interface LabRow {
  trial_id: string
  status: TrialStatus
  mode?: string | null
  created_utc: string | null
  source: 'local' | 'bundled-demo' | string
  readable: boolean
  label?: string | null
  variant?: string
  claim?: string | null
  parameter?: string | null
  value?: number | null
  confidence?: number | null
  tier?: string | null
  fall_rate?: { baseline: number | null; candidate: number | null } | null
  reason?: string | null
  error?: string
  also_bundled?: boolean
}

export interface Cited {
  path: string
  value: unknown
  missing?: boolean
}

export interface MetricPair {
  baseline: number
  candidate: number
  delta: number
}

export interface PushStats {
  fall_rate: number
  mean_survival_s: number
  mean_min_torso_height_m: number
  mean_max_abs_pitch_rad: number
  falls: number
  n: number
}

export interface Verdict {
  tier: 'success' | 'partial' | 'none' | string
  primary_fall_rate: { baseline: number; candidate: number; reduction: number }
  levels_where_candidate_worse: string[]
  primary_survival_not_worse: boolean
  falls_by_push: Record<string, [number, number]>
}

export interface LabView {
  trial_id: string
  mode?: string | null
  label?: string | null
  variant: string
  source: string
  created_utc?: string | null
  degraded?: string
  missing: string[]
  provenance: Record<'observed' | 'hypothesis' | 'confidence' | 'measured', string>
  integrity: { verified: boolean; sha256: string; note?: string } | null
  sections: Record<'observe' | 'hypothesis' | 'intervene' | 'verify' | 'compare', boolean>
  observed: {
    scenario: { push: { time_s: number; force_N: number; duration_s: number }; duration_s: number; seeds: number[] } | null
    matched_seed_results: { fall_rate: number; mean_min_torso_height_m: number; mean_max_abs_pitch_rad: number } | null
    forensic_highlights: Record<string, number | null> | null
    timeline: { columns: string[]; rows: (number | null)[][] } | null
  } | null
  rationale: {
    source: string
    mechanism?: string | null
    claim: string
    confidence: number
    cited: Cited[]
  } | null
  design_change: {
    parameter: string
    original: number
    modified: number
    original_body: Record<string, number>
    modified_body: Record<string, number>
  } | null
  predicted_vs_measured: {
    metric: string
    direction: string
    held_on_screening_seeds: boolean
    held_on_heldout_primary: boolean | null
    screening_observed: Record<string, MetricPair>
    heldout_by_push: Record<string, { baseline: PushStats; candidate: PushStats }> | null
  } | null
  outcome: { status: TrialStatus; reason?: string | null; tier?: string | null }
  verdict: Verdict | null
  screening: { prediction_held: boolean; improved: boolean; accepted: boolean; seeds: number[] } | null
  seeds: { evidence: number[] | null; screening: number[] | null }
  protocol_simulations?: number | null
  protocol_config: { heldout_seeds: number[]; primary_push_N: number; push_levels_N: number[] } | null
  raw_model_reply: { text: string; truncated: boolean; note: string } | null
  replay: { available: boolean; seeds: number[]; has_candidate: boolean }
  model_call?: {
    model?: string
    usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
    latency_s?: number
    finish_reason?: string
  } | null
}

export interface Consistency {
  checked: boolean
  reason?: string
  matches_saved_record?: boolean
  max_rel_diff?: number
  saved?: { fell: boolean; min_torso_height: number; max_abs_pitch: number }
  fresh?: { fell: boolean; min_torso_height: number; max_abs_pitch: number }
  failures?: string[]
}

export interface Replay {
  seed: number
  baseline: RunPayload
  candidate: RunPayload | null
  engine: { mujoco: string; model_calls: number; source: string }
  consistency: { baseline: Consistency; candidate?: Consistency }
}
