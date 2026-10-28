// Records of the autonomous HaS scientist (schema scientist_record_v1, scripts/has_export_records.py). Read-only.

export interface ScientistIndexRow {
  id: string
  arm: string
  provenance: string
  status: string | null
  walking_frac: number | null
  n_steps: number
  n_experiments: number
  llm_calls: number | null
  cost_usd: number | null
  robot: Record<string, number>
  conclusion_by: string | null
}

export interface ScientistIndex {
  schema: string
  records: ScientistIndexRow[]
  replay: { seeds: number[]; duration_s: number; designs: string[]; note: string }
}

export interface ScientistWords { understanding: string; uncertainty: string; why: string }

export interface AddedHypothesis { pid: string; weight: number; rank: number | null; loglik_gap?: number | null; status?: string }

export interface Evidence {
  twin_pred?: number
  robust8?: number
  robust16?: number
  stress4?: number
  p_full?: number | string
  train?: string
  contradiction?: string
}

export interface StepResult {
  ok?: boolean
  refused?: string
  id?: string
  eig?: number | null
  best_eig?: number | null
  measured?: Record<string, number | null>
  posterior?: [string[][], number][]
  proposals?: { added?: AddedHypothesis[] }
  ran?: string[]
  ranking?: { tool: string; probe: string; score: number; cma_walking?: number | null }[]
  design?: number
  mode?: string
  tool?: string
  twin_walking?: string
  evidence?: Evidence
  before?: [string[][], number][]
  after?: [string[][], number][]
  accepted?: boolean
  suggested?: [string, number][]
}

export interface Step {
  seq: number
  turn: number | null
  actor: 'nemotron' | 'engine' | 'fallback' | string
  action: Record<string, unknown> & { action: string }
  result: StepResult
  plant_cost: number
  twin_cost: number
  plant_used: number
  twin_used: number
  scientist: ScientistWords | null
}

export interface BeliefSnapshot { label: string; plant_used: number; twin_used: number; structures: { structure: string[][]; w: number }[] }

export interface ScientistRecord {
  schema: string
  id: string
  arm: string
  provenance: string
  robot: { initial: { body: Record<string, number>; vector: number[] }; submitted: { body: Record<string, number>; vector: number[] }; submitted_source: string }
  steps: Step[]
  belief_history: BeliefSnapshot[]
  experiments: { id: string; kind: string; panel: Record<string, number | null> }[]
  evidence: Record<string, Evidence & { checks?: Record<string, string[]> }> | null
  conclusion: { design?: number; by?: string }
  predictions: { experiment: string; predictions: { quantity: string; q05: number; q25: number; q50: number; q75: number; q95: number }[] }[] | null
  memory_views: { turn: number; shown: [string, number][] }[]
  memory_uses: { dossier: string; turn: number }[] | null
  verification: { status: string; walking_frac: number; reasons: string[] }
  costs: { plant_used: number; plant_total: number; twin_used: number; twin_total: number; llm_calls: number; cost_usd: number | null; tokens: { prompt: number; completion: number } | null; wall_s: number | null }
  model: { name: string | null; system_prompt_sha256: string; calls: { purpose: string | null; usage: Record<string, number> | null; latency_s: number | null; cost_usd: number | null; ok: boolean | null }[] }
  evaluation_only: { note: string; injected_structure: string[][]; family: string; severity_multiple: number | null; final_belief: string[][] | null; final_belief_mass: number; mass_on_injected: number; belief_matched: boolean }
  source: { file: string; line: number; record_version: string | null }
}
