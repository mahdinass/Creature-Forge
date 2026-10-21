// W2 case files served by /api/nemotron/case (scripts/w2_case_build.py, schema w2_case_v1). Read-only playback.

export type Structure = string[][]
export interface Weighted { structure: Structure; w: number }

export interface SeedFeatures {
  seed: number
  walking: number | null
  time_upright: number | null
  fall_direction: number | null
  pitch_mean: number | null
  com_vx_mean: number | null
  step_freq_hz: number | null
  step_length_over_L: number | null
  double_support_fraction: number | null
  capture_margin_over_L_mean: number | null
  slip_fraction: number | null
}

export interface Experiment { id: string; kind: string; seeds: number[]; cost: number; per_seed: SeedFeatures[]; n_walking: number }

export interface Candidate { id: string; cost: number; eig: number; predicted_walking: number[] }

export interface Words { understanding: string; uncertainty: string; why: string }

export interface ModelCall {
  request_id: string | null; ok: boolean | null; finish_reason: string | null; latency_s: number | null
  prompt_tokens: number | null; completion_tokens: number | null; reasoning_tokens: number | null; cost_usd: number | null
  prompt_sha256: string | null; schema_name: string | null; temperature: number | null; engine_recommendation: string | null
  model_check: string[]
}

export interface HypothesisFate { pid: string; fitted: string | null; weight: number; rank: number | null; status: string | null; loglik_gap: number | null }

export interface StepView {
  seq: number; turn: number | null; actor: string
  action: Record<string, unknown> & { action: string }
  words: Words | null
  result: { ok?: boolean; id?: string; eig?: number; best_eig?: number; accepted?: boolean; design?: number; posterior?: Weighted[]
    ranking?: { tool: string; probe: string; score: number; cma_walking: number | null }[]; hypotheses?: HypothesisFate[] }
  plant_cost: number; twin_cost: number; plant_used: number; twin_used: number
}

export interface RepairLogEntry { step: string; tool: string; design: number; twin_walking?: number; check?: number; budget?: number; train_walking?: number; check16?: number }

export interface ArmView {
  arm: 'A3' | 'A1e' | 'A4'; label: string; provenance: 'LIVE' | 'NO_AI'
  steps: StepView[]
  experiments: Experiment[]
  belief_history: { label: string; plant_used: number; twin_used: number; top: Weighted[] }[]
  designs: { index: number; source: string; design_hash: string; check: [number, number] | null }[]
  repair_log: RepairLogEntry[]; repair_accepted: boolean
  submitted: { index: number; source: string; design_hash: string }
  conclusion: { design?: number; by?: string }
  verification: { status: string; walking_frac: number; reasons: string[]; walking: number; n: number
    rollouts: { validation: number; confirmation: number } }
  final_belief: { structure: Structure; mass: number; mass_on_truth: number; correct: boolean }
  costs: { plant_used: number; plant_total: number; twin_used: number; twin_total: number; llm_calls: number; cost_usd: number | null
    tokens: { prompt: number; completion: number } | null; wall_s: number | null }
  model: { name: string | null; system_prompt_sha256: string; calls: ModelCall[] } | null
  predictions_registered: number
}

export interface W2Case {
  schema: string; instance_id: string
  sources: { arm: string; file: string; source: string; source_line: number; source_sha256: string; line_sha256: string }[]
  captions: Record<'playback' | 'scope' | 'repair' | 'do1', string>
  evaluation_only: { note: string; injected_structure: Structure; family: string; severity: number; mult: number; strength: number }
  nominal_design: { body: Record<string, unknown>; design_hash: string }
  eligibility_check: { walking: number; n: number; labels: string[] }
  shared: { observation: Experiment & { id: string }; belief_after_observation: Weighted[]; identical_in_all_arms: boolean }
  fork: {
    notebook: { belief: { weight: number; hypothesis: string; proposed_by: string }[]; entropy_nats: number | null; candidates: Candidate[]
      predicted_out_of: number | null; hypotheses: string[]; engine_recommendation: string }
    nemotron: { experiment: string; eig: number; best_eig: number; predicted_walking: number[] | null; words: Words
      registered_prediction: unknown; prediction_issue: string | null; call: ModelCall }
    engine: { experiment: string; eig: number; best_eig: number; predicted_walking: number[] | null; why: string }
    a4_same_choice: boolean
  }
  arms: Record<'A3' | 'A1e' | 'A4', ArmView>
  determinism: Record<string, boolean>
}

export interface CrossRow { instance_id: string; A1e: CrossArm; A3: CrossArm; A4: CrossArm }
export interface CrossArm { full: boolean; status: string; map_correct: boolean; first_experiment: { experiment: string; actor: string } | null }

export interface W2Cross {
  population: string
  aggregates: {
    n: number; full: Record<string, number>; map_correct: Record<string, number>
    full_discordant_A3_vs_A1e: { A3_only: number; A1e_only: number }; map_discordant_A3_vs_A1e: { A3_only: number; A1e_only: number }
    first_experiment_differs: number; map_and_full_both_favour_A3: string[]; A3_full_only: string[]; A1e_full_only: string[]
    A3_map_wrong_A1e_right: string[]; mcnemar_one_sided_p_A3_gt_A1e: number | null
  }
  rows: CrossRow[]
  ledger: { file: string; sha256: string; this_case: Record<string, { request_id: string; in_ledger: number; ledger_model: string | null; ledger_cost_usd: number | null }[]> }
  sources: Record<string, { file: string; sha256: string }>
}

export interface Study {
  id: string; date: string; study: string; registration: string; n: string; comparator: string; outcome: string; direction: string
  nemotron_decided: string; tools_did: string; credited_to: string; source: string; quote: string
}

export interface NemotronCaseResponse {
  case: W2Case; cross: W2Cross; studies: { schema: string; note: string; studies: Study[] }
  replays: { available: boolean; reason: string }; playback: 'RECORDED_LIVE'
}
