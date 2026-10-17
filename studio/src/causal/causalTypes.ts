// Mirrors the trimmed records of scripts/ce_export_records.py (causal_record_v1). Everything the page shows comes from these fields.
import type { LocomotionReplay } from '../locomotion/locoTypes'

export interface CausalIndexRow {
  id: string
  policy: string
  status: string | null
  walking_frac: number | null
  n_steps: number
  n_experiments: number
  cost_usd: number | null
  llm_calls: number | null
  model: string | null
  robot: { leg_length: number; torso_mass: number; foot_length: number; foot_friction: number; torque_limit: number }
  final_category: string | null
  has_memory: boolean
}
export interface CausalIndex {
  schema: string
  records: CausalIndexRow[]
  replay: { seeds: number[]; duration_s: number; designs: string[]; note: string }
}

export interface Prediction { hypothesis: string; quantity: string; direction: string }
export interface ScoredPrediction {
  hypothesis: string
  quantity: string
  predicted: string
  observed: string | null
  status: 'correct' | 'incorrect' | 'unscored' | string
  base: number | null
  new: number | null
  delta: number | null
  tolerance: number | null
}
export interface Experiment {
  id: string
  kind: 'counterfactual' | 'repair' | 'observe' | string
  step?: number
  cost?: number
  status?: string
  // counterfactual
  change?: string
  atoms?: { param: string; level: string }[]
  purpose?: string
  predictions?: Prediction[]
  scoring?: ScoredPrediction[]
  outcome?: { n_walking?: number; n_walking_base?: number; n_fell?: number; n_fell_base?: number }
  // repair
  tool?: string
  hypothesis?: string
  budget?: number
  budget_share?: number
  n_train?: number
  start_walking?: number
  train_walking?: number
  train_fitness?: number
  predicted_n_walking?: number
  prediction_error?: number
  rollouts_used?: number
  is_current_best?: boolean
}

export interface HypothesisHistory {
  step: number
  status: string
  confidence: number
  reason: string
  experiments: string[]
  cited_predictions?: { n_scored: number; n_correct: number }
}
export interface Hypothesis {
  id: string
  mechanism: string
  causal_chain: string
  category: string
  evidence: string[]
  status: string
  confidence: number
  created_step: number
  history: HypothesisHistory[]
}
export interface HypothesisTransition {
  id: string
  from: string | null
  to: string
  reason: string
  experiments: string[]
  cited_predictions?: { n_scored: number; n_correct: number }
}
export interface NewHypothesis { id: string; mechanism: string; causal_chain: string; category: string; evidence: string[]; confidence: number }
export interface MemoryAssessment { item: string; verdict: string; reason: string; step?: number }
export interface Step {
  step: number
  action?: string | null
  status?: string
  experiments?: string[]
  experiment?: string
  parsed?: {
    result_reading?: string
    new_hypotheses?: NewHypothesis[]
    status_updates?: { id: string; status: string; reason: string; experiments: string[]; confidence: number }[]
    repair?: { hypothesis: string; tool: string; budget_share: number; predicted_n_walking: number }[]
    conclude?: { diagnosis_category: string; explanation: string; confidence: number; submit: string }[]
    memory_assessments?: MemoryAssessment[]
  } | null
  hypothesis_transitions?: HypothesisTransition[]
  memory_assessments?: MemoryAssessment[]
  first_attempt_errors?: string[]
  validation_errors?: string[]
  repaired?: boolean
  remaining_before?: number
  remaining_after?: number
  user_message?: { sha256: string; length: number }
  calls?: { index: number; cost_usd?: number; latency_s?: number }[]
}
export interface MemoryItem { id: string; kind: string; text: string }

export interface Design { body: Record<string, number | number[]> | null; vector: number[] | null; design_index?: number; source?: string }
export interface Verification {
  status: string | null
  walking_frac: number | null
  reasons?: string[]
  rollouts?: Record<string, number>
  independent?: boolean
  note?: string
}
export interface CausalRecord {
  schema: string
  id: string
  source: { file: string; line: number; policy: string; runner_version?: string; scientist_version?: string; note?: string }
  config: {
    model: string | null; prompt_version: string | null; thinking: boolean; max_steps: number | null; budget: number | null
    n_train: number | null; n_obs: number | null; tolerance: string | null; system_prompt: { sha256: string; length: number } | null; provenance: string | null
  }
  robot: { vector_names: string[]; initial: Design; initial_matches_prompt: boolean | null; submitted: Design; base_region?: string | null }
  initial_observation: { n_walking?: number; n_fell?: number } | null
  steps: Step[]
  hypotheses: Record<string, Hypothesis>
  experiments: Experiment[]
  memory: { items: MemoryItem[]; assessments: Record<string, MemoryAssessment>; log?: MemoryAssessment[]; error?: string | null }
  final: { diagnosis_category?: string; explanation?: string; confidence?: number; ended_by?: string; step?: number; submit?: string; detail?: string } | null
  prediction_summary: {
    n_scored: number; n_correct: number; accuracy: number | null; chance_three_way?: number; majority_observed_baseline?: number
    observed_directions?: Record<string, number>; repair_predictions?: { n: number; within_one: number }
  } | null
  budget: { total: number | null; used: number | null; remaining: number | null; lines?: { item: string; n: number; cumulative: number }[] }
  verification: Verification
  llm: { calls: number; cost_usd: number; latency_s: number; model?: string; provenance?: string; tokens?: { prompt: number; completion: number } } | null
  error: string | null
  evaluation_only: {
    note: string; fault: string; severity: number; matching_tool: string | null; injected_category: string | null
    diagnosis_category: string | null; diagnosis_match: boolean | null
  }
  no_ai_comparison: { policy: string; status: string | null; walking_frac: number | null; rollouts_used: number | null; error: string | null }[]
}

export type CausalReplay = LocomotionReplay & { condition?: { perturb: number; push_time: number; friction_used: number } }
export type DesignKey = 'initial' | 'submitted'
