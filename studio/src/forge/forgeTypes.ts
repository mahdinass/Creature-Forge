// Mirrors the /api/forge/* responses (docs/FORGE_LOOP_CONTRACTS.md sections 3, 4, 6, 8, 9; creature_forge/studio/forge_api.py).
// Everything shown on the forge page comes from these shapes; nothing is invented client-side.
import type { SandboxBodyDict } from '../sketch/freehandTypes'

export type Kind = 'stand' | 'push' | 'walk'
export type Outcome = 'PASS' | 'POOR' | 'FAIL' | 'ERROR'
export type JobStatus = 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
export type VerdictStatus = 'VERIFIED_IMPROVEMENT' | 'NOT_VERIFIED' | 'WORSE' | 'INCONCLUSIVE'
export type ArmSource = 'original' | 'nemotron' | 'random_baseline' | 'heuristic'

export interface ForgeStatus {
  live_available: boolean
  model: string | null
  ledger: Record<string, unknown> | null
  workers: number
  version: string
}

export interface CreatureSummary { id: string; name: string; current: number; n_versions: number; created: string }

export interface Controllers {
  stand: Record<string, number>
  walk: null | { vector: number[]; provenance: Record<string, unknown> | null }
}

export interface VersionChange {
  edits?: { param: string; op: string; value: number; target?: string }[]
  category?: string
  rationale?: string
  source?: string
  model?: string
  investigation_id?: string
  arm_id?: string
  verdict?: Verdict
}

export interface CreatureVersion {
  n: number
  parent: number | null
  created: string
  content_hash: string
  mode: 'guided' | 'experimental'
  body: SandboxBodyDict
  controllers: Controllers
  origin: 'user' | 'ai_accepted'
  drawing: { strokes?: unknown[]; interpretation?: unknown; approximation?: unknown } | null
  change: VersionChange | null
}

export interface Creature { id: string; name: string; created: string; current: number; versions: CreatureVersion[] }

export interface JobProgress { phase: string | null; done: number; total: number }
export interface Job {
  id: string
  kind: 'challenge' | 'investigation' | 'loop'
  status: JobStatus
  created: string
  started: string | null
  finished: string | null
  progress: JobProgress
  result_ref: { run_id?: string; investigation_id?: string } | null
  error: string | null
}
export interface JobEvent { i: number; t: number; type: string; data: Record<string, unknown> }
export interface JobPoll { job: Job; events: JobEvent[] }

export interface ForgeEvent { time: number; kind: string; evidence?: Record<string, unknown> }
export interface SeedResult {
  seed: number
  outcome: Outcome
  score: number
  metrics: Record<string, unknown>
  events: ForgeEvent[]
  rollouts: number
  error?: string | null
}

export interface ControllerProvenance {
  stand?: { kind?: string; params?: Record<string, number>; edited?: boolean }
  walk?: { kind?: string; vector?: number[] | null; adaptation?: null | { budget?: number; rollouts_used?: number; train_seeds?: number[]; noise_seed?: number } }
}

export interface ChallengeSpecDict {
  kind: Kind
  seeds: number[]
  duration: number
  perturb?: number
  target_force?: number
  push_time?: number
  push_duration?: number
  max_force?: number
  start?: string
  settle_s?: number
}

export interface ChallengeRun {
  run_id: string
  creature: { cid: string; n: number; content_hash: string }
  created: string
  spec: ChallengeSpecDict
  body: Record<string, unknown>
  controller?: ControllerProvenance
  controllers?: Controllers
  per_seed: SeedResult[]
  outcome: Outcome
  summary?: Record<string, unknown>
  forensics?: Record<string, unknown>
  rollouts?: number
  wall_s?: number
}

export interface StartedChallenge { job_id: string; run_id: string }
export interface StartedInvestigation { job_id: string; investigation_id: string }

// ---- investigation record (contracts section 8; exact sub-shapes of arms/screening are tolerated in both list and map form)
export interface Verdict {
  status: VerdictStatus
  rule?: string
  n?: number
  wins?: number
  losses?: number
  ties?: number
  median_diff?: number
  p_one_sided?: number
  min_effect?: number | Record<string, number>
  pass_rate?: Record<string, unknown>
  reasons?: string[]
}

export interface Arm {
  arm_id: string
  source: ArmSource
  proposal_id?: string
  edits?: { param: string; op: string; value: number; target?: string }[]
  category?: string
  body?: Record<string, number | number[] | null>
  controllers?: Controllers
  controller_provenance?: ControllerProvenance
  retune?: null | { budget: number; noise_seed: number; rollouts_used: number }
  unavailable?: string
}

export interface ModelCall {
  model: string
  request_id?: string | null
  latency_s?: number | null
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null
  cost_usd?: number | null
  finish_reason?: string | null
  http_status?: number | null
  error?: string | null
  reasoning_present?: boolean
}

export interface ValidatedProposal { id: string; status: 'accepted' | 'rejected'; reasons?: string[]; edits?: unknown[] }
export interface Hypothesis { id: string; mechanism: string; evidence?: string[]; competing?: string[] }

export interface InvestigationRecord {
  id: string
  created: string
  mode: 'live' | 'scripted'
  provenance: 'LIVE' | 'SCRIPTED_MOCK'
  creature: { cid: string; n: number; content_hash: string }
  challenge_run_id: string
  spec?: ChallengeSpecDict
  evidence?: Record<string, unknown>
  model_calls?: ModelCall[]
  reply?: { diagnosis?: { summary?: string; hypotheses?: Hypothesis[] }; proposals?: { id: string; hypothesis?: string; category?: string; prediction?: { expected_change?: string }; tradeoffs?: string; confidence?: number }[] } | null
  validation?: { proposals?: ValidatedProposal[]; hypotheses?: { id: string; status?: string; reasons?: string[] }[] } | null
  arms?: Arm[] | Record<string, Arm>
  seeds?: { train?: number[]; screen?: number[]; validate?: number[] }
  screening?: unknown
  selection?: unknown
  validation_results?: unknown
  verdicts?: Record<string, Verdict>
  budget?: { rollouts?: number; wall_s?: number; calls?: number; tokens?: number; usd?: number }
  status: string
  error?: string | null
}

export interface InvestigationSummary { id: string; created?: string; status?: string; provenance?: string; creature?: { cid: string; n: number } }
