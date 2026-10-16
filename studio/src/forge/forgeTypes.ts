// Mirrors the /api/forge/* responses (docs/FORGE_LOOP_CONTRACTS.md sections 3, 4, 6, 8, 9; creature_forge/studio/forge_api.py).
// Everything shown on the forge page comes from these shapes; nothing is invented client-side.
import type { SandboxBodyDict } from '../sketch/freehandTypes'

export type Origin = 'user' | 'ai_accepted' | 'baseline_accepted'
export type Kind = 'stand' | 'push' | 'walk'
export type Outcome = 'PASS' | 'POOR' | 'FAIL' | 'ERROR'
export type JobStatus = 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
export type VerdictStatus = 'VERIFIED_IMPROVEMENT' | 'NOT_VERIFIED' | 'WORSE' | 'INCONCLUSIVE'
export type ArmSource = 'original' | 'nemotron' | 'scripted_mock' | 'random_baseline' | 'heuristic'

export interface ForgeStatus {
  live_available: boolean
  model: { model: string; selected?: string } | null
  ledger: { requests?: number; usd?: number; caps?: { requests: number; usd: number }; error?: string } | null
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
  provenance?: string
  round?: number
  // walking recovery change records
  kind?: string
  recovery_id?: string
  director?: string
  status?: string
}

export interface CreatureVersion {
  n: number
  parent: number | null
  created: string
  content_hash: string
  mode: 'guided' | 'experimental'
  body: SandboxBodyDict
  controllers: Controllers
  origin: Origin
  drawing: { strokes?: unknown[]; interpretation?: unknown; approximation?: unknown } | null
  change: VersionChange | null
}

export interface Creature { id: string; name: string; created: string; current: number; versions: CreatureVersion[] }

export interface JobProgress { phase: string | null; done: number; total: number }
export interface Job {
  id: string
  kind: 'challenge' | 'investigation' | 'loop' | 'recovery'
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

// ---- investigation record (creature_forge/investigation.py, arena.py, verdict.py; real LIVE records in experiments/forge_loop/dev_live_records)
export interface MinEffect { abs?: number; rel?: number; required?: number }
export interface Verdict {
  status: VerdictStatus
  rule?: string
  kind?: Kind
  n?: number
  wins?: number
  losses?: number
  ties?: number
  non_tied?: number
  median_diff?: number
  p_one_sided?: number
  p_worse?: number
  resolution?: number
  alpha?: number
  min_non_tied?: number
  min_effect?: number | MinEffect
  pass_rate?: Record<string, unknown>
  reasons?: string[]
  errors?: string[]
  source?: string
  provenance?: string
}

export interface Edit { param: string; op: string; value: number; target?: string }

export interface Arm {
  arm_id: string
  source: ArmSource
  proposal_id?: string | null
  hypothesis?: string
  edits?: Edit[]
  category?: string | null
  body?: Record<string, number | number[] | null>
  controllers?: Controllers
  controller_provenance?: ControllerProvenance
  retune?: null | { budget: number; noise_seed: number; rollouts_used: number }
  unavailable?: string
  error?: string | null
  provenance?: string
  rollouts?: { adaptation?: number; screening?: number; validation?: number; total?: number }
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
  ok?: boolean
  sent?: boolean
}

export interface ValidatedProposal { id: string; status: 'accepted' | 'rejected'; reasons?: string[]; hypothesis?: string; edits?: Edit[]; category?: string; prediction?: { expected_change?: string }; tradeoffs?: string; confidence?: number }
export interface Hypothesis { id: string; mechanism: string; evidence?: string[]; competing?: string[] }
export interface ValidatedHypothesis extends Hypothesis { status?: string; reasons?: string[]; values?: Record<string, string | number | boolean | null> }

export interface SeedRecord { seed: number; score: number | null; outcome: Outcome; rollouts?: number; error?: string | null; metrics?: Record<string, unknown> }
export interface ArmResults { seeds: SeedRecord[]; summary?: { median?: number | null; mean?: number | null; n?: number; errors?: number; counts?: Record<string, number>; rollouts?: number } }
export interface RankRow { arm_id: string; median: number | null; mean: number | null; order: number }
export interface Selection {
  rule?: string
  excluded?: Record<string, string>
  ranking?: { ai?: RankRow[]; baseline?: RankRow[] }
  ai?: string | null
  baseline?: string | null
  matched_twin?: string | null
  validated?: string[]
}

export interface ProbeResult {
  probe_id: string
  measurement?: string
  transformation?: string
  status: string
  error?: string
  median?: number | null
  median_delta?: number | null
  mean_delta?: number | null
  n_seeds?: number
  wins?: number
  losses?: number
  ties?: number
  static_fall_frac?: number | null
}
export interface ProbeExpectation { probe_id: string; hypothesis?: string | null; expect?: string | null; observed?: string | null; confirmed?: boolean | null }
export interface ProbesRecord {
  requested?: { probe_id: string; hypothesis?: string | null; expect?: string | null }[]
  skipped?: string
  seeds?: number[]
  resolution?: number
  rollouts?: number
  kind?: Kind
  original?: { median?: number | null; status?: string } | null
  results?: Record<string, ProbeResult>
  expectations?: ProbeExpectation[]
  provenance?: string
}

export interface InvestigationRecord {
  id: string
  created: string
  mode: 'live' | 'scripted'
  provenance: 'LIVE' | 'SCRIPTED_MOCK'
  creature: { cid: string; n: number; content_hash: string; round?: number; hypothetical_parent?: unknown; loop_id?: string }
  challenge_run_id: string
  spec?: ChallengeSpecDict
  evidence?: Record<string, unknown>
  model_calls?: ModelCall[]
  reply?: { diagnosis?: { summary?: string; hypotheses?: Hypothesis[] }; proposals?: ValidatedProposal[] } | null
  probes?: ProbesRecord | null
  memory?: { used: boolean; retrieved: { lesson_id: string; similarity: number }[]; bank_size: number | null; k: number | null } | null
  validation?: { proposals?: ValidatedProposal[]; hypotheses?: ValidatedHypothesis[]; summary?: string; warnings?: string[]; schema_errors?: string[] } | null
  arms?: Arm[]
  seeds?: { train?: number[]; screen?: number[]; validate?: number[]; round_used?: number }
  screening?: Record<string, ArmResults>
  selection?: Selection
  validation_results?: Record<string, ArmResults>
  verdicts?: Record<string, Verdict>
  budget?: { rollouts?: number; wall_s?: number; calls?: number; tokens?: number; usd?: number }
  status: string
  error?: string | null
}

export interface InvestigationSummary {
  id: string
  created: string
  mode: 'live' | 'scripted'
  provenance: 'LIVE' | 'SCRIPTED_MOCK'
  creature: { cid: string; n: number; round?: number }
  challenge_run_id: string
  status: string
  error?: string | null
  n_arms: number
  verdicts: Record<string, string | null>
  budget?: InvestigationRecord['budget']
}

export interface LoopRound { round: number; investigation_id: string; status: string; run_id: string; hypothetical_parent: unknown; best_verified_arm: string | null; best_verdict: Verdict | null }
export interface LoopResult {
  loop_id: string
  mode: string
  provenance: string
  rounds: LoopRound[]
  stop_reason: string
  best: LoopRound | null
  budget: { rollouts: number; calls: number; wall_s: number }
  auto_accepted: boolean
}

// ---- walking recovery (creature_forge/recoveries.py, recovery.py, walk_pipelines.py, director.py)
export type RecoveryStatus = 'FULL_RECOVERY' | 'PARTIAL_IMPROVEMENT' | 'NOT_RECOVERED' | 'INCONCLUSIVE_ERROR'
export type RecoveryProvenance = 'LIVE' | 'SCRIPTED_MOCK' | 'NON_AI'
export type RecoveryDirector = 'ai' | 'fix'
export type RecoveryPhase = 'diagnostics' | 'probes' | 'plans' | 'screening' | 'validation' | 'confirmation' | 'done'

export interface RecoverySummary {
  id: string
  created: string
  creature: { cid: string; n: number; content_hash?: string }
  director: RecoveryDirector
  mode: 'live' | 'scripted' | null
  provenance: RecoveryProvenance
  model: string | null
  status: string   // a RecoveryStatus, or failed / cancelled
  error?: string | null
  scale?: string
  budget: { total?: number | null; used?: number | null }
  n_edits: number
  walking_frac: number | null
}

export interface BudgetLine { item: string; n: number; detail?: Record<string, unknown>; cumulative: number }
export interface ScoreDict { walking_count?: number; survival_count?: number; mean_fitness?: number }
export interface PipelineProbe {
  probe_id: string
  round: number
  status: string
  reason?: string
  rollouts?: number
  delta_walking?: number
  delta_mean_fitness?: number
  best_score?: ScoreDict | null
  edits?: Edit[]
}
export interface PlanSpec { init: string; ctrl_subspaces: string[]; body_params: string[]; budget_share: number; rationale?: string }
export interface PipelinePlan {
  plan_id: string
  round: number
  plan: PlanSpec
  budget: number
  status: string
  reason?: string
  rollouts_used?: number
  refunded?: number
  best_score?: ScoreDict | null
  walking_count?: number
  init_score?: ScoreDict | null
  improvement?: { delta_mean_fitness?: number; delta_walking?: number }
  edits?: Edit[]
}
export interface PipelineRound {
  round: number
  probes: PipelineProbe[]
  rejected_probes: { probe_id: unknown; reason: string }[]
  plans: PipelinePlan[]
  rejected_plans: { index: number | null; plan: unknown; reasons: string[] }[]
}
export interface PipelineRecord {
  total_budget: number
  budget_lines: BudgetLine[]
  used: number
  rounds: PipelineRound[]
  start_score?: ScoreDict
  decisions?: { round: number; kind: 'probes' | 'plans'; returned: unknown }[]
  final: { body: Record<string, number>; vector: number[]; edits: Edit[]; source: string; aliases?: string[]; train_score?: number[]; screen?: Record<string, unknown> }
  settings?: Record<string, unknown>
}

export interface DirectorDecision {
  kind: 'probes' | 'plans'
  round: number
  status: string
  calls?: number[]
  returned?: unknown
  diagnosis?: string
  validation_errors?: string[]
  repaired?: boolean
}
export interface DirectorHypothesis { round: number; mechanism: string; evidence: string[]; competing: string[]; refuted: boolean; refuted_round: number | null }
export interface DirectorCall {
  model?: string
  request_id?: string | null
  latency_s?: number | null
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null
  cost_usd?: number | null
  finish_reason?: string | null
  error?: string | null
  sent?: boolean
  ok?: boolean
  messages?: { role?: string; content?: string }[]
}
export interface DirectorRecord {
  provenance: string
  model: string
  calls: DirectorCall[]
  decisions: DirectorDecision[]
  hypotheses: Record<string, DirectorHypothesis>
  plan_meta?: Record<string, { init: string; ctrl_subspaces: string[]; body_params: string[]; budget_share: number; hypothesis: string; prediction: string; evidence: string[] }>
  expectations?: Record<string, { hypothesis: string; expect: 'improves' | 'no_change' | string; round: number }>
  refuted_by_round?: Record<string, string[]>
  cost_usd: number
  tokens?: { prompt: number; completion: number }
  note?: string
}

export interface RecoverySeedRow {
  seed: number
  outcome: Outcome
  score: number | null
  walking: boolean
  fell?: boolean | null
  label?: string | null
  fall_time?: number | null
  speed_upright?: number | null
  body_contact_frac?: number | null
  error?: string | null
}
export interface RecoveryConfirmation {
  run: boolean
  reason?: string
  duration?: number
  per_seed?: RecoverySeedRow[]
  aggregate?: string
  passed?: boolean
  checks?: {
    walking_frac: { value: number; need: number; passed: boolean }
    median_speed_upright: { value: number; need: number; passed: boolean }
    body_contact: { seeds_over: number[]; max_frac: number; passed: boolean }
  }
}
export interface RecoveryAssessment {
  rule: string
  status: RecoveryStatus
  reasons: string[]
  validation: { original: RecoverySeedRow[]; candidate: RecoverySeedRow[]; verdict: Verdict; aggregate: string; walking_frac: number }
  confirmation: RecoveryConfirmation
  rollouts?: { validation?: number; confirmation?: number }
  seeds: { validate: number[]; confirm: number[] }
  errors?: { arm: string; seed: number; error: string }[]
  worse?: boolean
}

export interface RecoveryRecord {
  id: string
  created: string
  finished?: string
  creature: { cid: string; n: number; content_hash: string }
  director: RecoveryDirector
  mode: 'live' | 'scripted' | null
  provenance: RecoveryProvenance
  model: string | null
  budget: { requested: number; total: number; used: number | null; probe_budget?: number }
  scale?: string
  rule?: string
  seeds?: Record<string, number[]>
  pipeline: PipelineRecord | null
  director_record: DirectorRecord | null
  assessment: RecoveryAssessment | null
  candidate: { body: Record<string, number>; vector: number[]; edits: Edit[]; source: string; train_score?: number[]; screen?: Record<string, unknown> } | null
  status: string   // a RecoveryStatus, or failed / cancelled
  error: string | null
  cost?: { usd: number; tokens?: unknown; calls: number; pipeline_rollouts?: number | null }
}
export interface StartedRecovery { job_id: string; recovery_id: string }
