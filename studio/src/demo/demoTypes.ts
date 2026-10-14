// Mirrors creature_forge.demo records. Measurements are MuJoCo output; "model" fields are untrusted model text.
import type { LocomotionReplay } from '../locomotion/locoTypes'

export type Kind = 'LIVE' | 'RECORDED_LIVE' | 'SCRIPTED_MOCK'

export interface DemoStatus {
  live_enabled: boolean
  live_calls_this_process: number
  live_calls_cap_per_process: number
  combined_budget: { requests_used: number; requests_cap: number; tokens_used: number; tokens_cap: number }
  setting: { reasoning_effort: string; max_tokens: number }
  limits: string[]
  kinds: Record<Kind, string>
}

export interface DemoRow {
  run_id: string
  source: 'bundled-recording' | 'local'
  kind: Kind | null
  created_utc: string | null
  label?: string | null
  status?: string
  n_valid_proposals?: number
  gain_seeds?: number | null
  verdict?: string | null
  hash_verified?: boolean | null
  readable?: boolean
}

export interface Edit { parameter: string; delta_u: number }
export interface Proposal {
  claim: string
  cited_evidence: string[]
  edits: Edit[]
  prediction: { metric: string; direction: string; min_gain_seeds: number }
  confidence: number
}
export interface Slot { proposal: Proposal | null; reason: string | null }
export interface Realised { parameter: string; requested_delta_u: number; realised_delta_u: number; reflected: boolean }
export interface Intervention {
  slot: number
  proposal: Proposal
  realised: Realised[]
  vector: number[]
  matched_random: { edits: Edit[]; realised: Realised[]; vector: number[] }
}
export interface Verdict { gain_seeds: number; kind: 'improved' | 'no_clear_change' | 'worse'; prediction_met?: boolean }
export interface VResult {
  walking_count: number
  survival_count: number
  walking_by_seed: boolean[]
  n: number
  labels: Record<string, number>
  verdict?: Verdict
}
export interface DemoRun {
  id: string // file stem: the identity used by every /api/demo route
  source?: string
  run_id: string
  created_utc: string
  label?: string | null
  provenance: {
    kind: Kind
    model: string | null
    request_id: string | null
    prompt_sha256: string
    setting: { reasoning_effort: string; max_tokens: number }
    usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number; reasoning_tokens?: number } | null
    note: string
    recorded_from?: { original_kind: string; original_sha256: string; note: string }
  }
  controller: { name: string; vector: number[]; params: Record<string, { value: number; lower: number; upper: number; u: number; meaning: string }> }
  observed: { failing_seed: number; walking_seed: number; metrics: Record<string, Record<string, unknown>>; failing_seed_walked: boolean }
  context: Record<string, unknown>
  prompt: { system: string; user: string; sha256: string }
  model_reply: {
    status: 'ok' | 'invalid_response' | 'model_error' | 'budget_exceeded'
    reason: string | null
    raw_reply: string | null
    call: { finish_reason?: string; latency_s?: number; reasoning_present?: boolean; content_is_null?: boolean; usage?: Record<string, number> } | null
    slots: Slot[]
    temperature: number
  }
  interventions: Intervention[]
  verification: { seeds: number[]; results: Record<string, VResult>; rollouts: number; rule: string } | null
  limits: string[]
  elapsed_s: number
  integrity?: { verified: boolean }
}

export type DemoReplay = LocomotionReplay
