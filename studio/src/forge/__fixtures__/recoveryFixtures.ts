// TEST-ONLY fixtures: hand-written recovery records in the documented API shapes (creature_forge/recoveries.py, walk_pipelines.py,
// director.py, recovery.py), used by vitest. Never imported by application code or shown in the UI.
import type { DirectorRecord, PipelineRecord, RecoveryAssessment, RecoveryRecord, RecoverySeedRow } from '../forgeTypes'

const row = (seed: number, walking: boolean, extra: Partial<RecoverySeedRow> = {}): RecoverySeedRow => ({
  seed, outcome: walking ? 'PASS' : 'FAIL', score: walking ? 3 : 0.4, walking, fell: !walking, ...extra,
})

export const validateSeeds = [100001, 100002, 100003, 100004]
export const confirmSeeds = [100011, 100012, 100013, 100014]

export const pipeline: PipelineRecord = {
  total_budget: 400,
  used: 300,
  budget_lines: [
    { item: 'screen_reserve', n: 30, cumulative: 30 },
    { item: 'start_eval', n: 10, cumulative: 40 },
    { item: 'probe:opt_posture', n: 40, cumulative: 80 },
    { item: 'probe:opt_posture:refund', n: -10, cumulative: 70 },
    { item: 'probe:opt_timing', n: 40, cumulative: 110 },
    { item: 'plan:r1p0', n: 160, cumulative: 270 },
    { item: 'plan:r1p0:refund', n: -20, cumulative: 250 },
    { item: 'screen_reserve:release', n: -30, cumulative: 220 },
    { item: 'screen:r1p0', n: 40, cumulative: 260 },
    { item: 'screen:start', n: 40, cumulative: 300 },
  ],
  rounds: [{
    round: 1,
    probes: [
      { probe_id: 'opt_posture', round: 1, status: 'ok', rollouts: 30, delta_walking: 2, delta_mean_fitness: 0.31 },
      { probe_id: 'opt_timing', round: 1, status: 'ok', rollouts: 40, delta_walking: 0, delta_mean_fitness: -0.05 },
    ],
    rejected_probes: [{ probe_id: 'opt_bogus', reason: 'unknown probe' }],
    plans: [{
      plan_id: 'r1p0', round: 1, budget: 160, status: 'ok', rollouts_used: 140, refunded: 20,
      plan: { init: 'opt_posture', ctrl_subspaces: ['posture', 'placement'], body_params: ['foot_length'], budget_share: 0.5 },
      improvement: { delta_walking: 3, delta_mean_fitness: 0.9 },
    }],
    rejected_plans: [{ index: 1, plan: {}, reasons: ['cumulative budget shares 1.5 exceed 1'] }],
  }],
  final: { body: { foot_length: 0.1 }, vector: [], edits: [{ param: 'foot_length', op: 'scale', value: 1.25, target: 'both' }], source: 'r1p0' },
}

const userMsg = [
  'ROUND 1 of 2. FAMILY 17: the controller has 17 parameters.',
  '',
  'EVIDENCE:',
  'baseline.outcomes.0.label = fell_early',
  'creature.features.foot_to_leg = 0.267',
  '',
  'TASK: probe call.',
].join('\n')

export const directorLive: DirectorRecord = {
  provenance: 'LIVE',
  model: 'nvidia/nemotron-3-super',
  cost_usd: 0.0123,
  calls: [
    { model: 'nvidia/nemotron-3-super', request_id: 'req-aaa', latency_s: 3.2, usage: { total_tokens: 900 }, cost_usd: 0.006, finish_reason: 'stop', sent: true,
      messages: [{ role: 'system', content: 'You are...' }, { role: 'user', content: userMsg }] },
    { model: 'nvidia/nemotron-3-super', request_id: 'req-bbb', latency_s: 4.1, usage: { total_tokens: 1100 }, cost_usd: 0.0063, finish_reason: 'stop', sent: true, messages: [] },
  ],
  decisions: [
    { kind: 'probes', round: 1, status: 'ok', calls: [0], returned: ['opt_posture', 'opt_timing'] },
    { kind: 'plans', round: 1, status: 'ok', calls: [1], returned: [], diagnosis: 'Posture, not timing, limits the gait.' },
  ],
  hypotheses: {
    H1: { round: 1, mechanism: 'The feet are too short to catch the fall.', evidence: ['creature.features.foot_to_leg', 'baseline.outcomes.0.label'], competing: ['Torque is too low.'], refuted: false, refuted_round: null },
    H2: { round: 1, mechanism: 'Timing is wrong.', evidence: ['not.in.the.prompt'], competing: [], refuted: true, refuted_round: 1 },
  },
  plan_meta: { r1p0: { init: 'opt_posture', ctrl_subspaces: ['posture', 'placement'], body_params: ['foot_length'], budget_share: 0.5, hypothesis: 'H1', prediction: 'Longer feet and posture let it walk.', evidence: [] } },
  expectations: {
    opt_posture: { hypothesis: 'H1', expect: 'improves', round: 1 },
    opt_timing: { hypothesis: 'H2', expect: 'improves', round: 1 },
  },
  refuted_by_round: { '1': ['H2'] },
}

export const directorMock: DirectorRecord = {
  provenance: 'SCRIPTED_MOCK', model: 'scripted-fixture', cost_usd: 0, calls: [], hypotheses: {},
  decisions: [
    { kind: 'probes', round: 1, status: 'ok', returned: ['opt_posture'] },
    { kind: 'plans', round: 1, status: 'ok', returned: [], diagnosis: 'Scripted mock: the fixed engineering rule’s choice, not a model’s reasoning.' },
  ],
}

const seedsOk = validateSeeds.map((s) => row(s, true))
const seedsBad = validateSeeds.map((s) => row(s, false))
const verdictOk = { status: 'VERIFIED_IMPROVEMENT', n: 4, wins: 4, losses: 0, ties: 0, kind: 'walk' } as const
const verdictNo = { status: 'NOT_VERIFIED', n: 4, wins: 1, losses: 0, ties: 3, kind: 'walk' } as const

export const assessFull: RecoveryAssessment = {
  rule: 'full_recovery_v1', status: 'FULL_RECOVERY', reasons: [],
  validation: { original: seedsBad, candidate: seedsOk, verdict: verdictOk, aggregate: 'PASS', walking_frac: 1 },
  confirmation: {
    run: true, duration: 20, passed: true, aggregate: 'PASS', per_seed: confirmSeeds.map((s) => row(s, true)),
    checks: {
      walking_frac: { value: 1, need: 0.8, passed: true }, median_speed_upright: { value: 0.31, need: 0.2, passed: true },
      body_contact: { seeds_over: [], max_frac: 0.05, passed: true },
    },
  },
  rollouts: { validation: 8, confirmation: 4 }, seeds: { validate: validateSeeds, confirm: confirmSeeds },
}

export const assessPartial: RecoveryAssessment = {
  rule: 'full_recovery_v1', status: 'PARTIAL_IMPROVEMENT', reasons: ['confirmation: walking on 50% of seeds at 20 s, needs >= 80%'],
  validation: { original: seedsBad, candidate: [row(100001, true), row(100002, true), row(100003, true), row(100004, false)], verdict: verdictOk, aggregate: 'PASS', walking_frac: 0.75 },
  confirmation: {
    run: true, duration: 20, passed: false, per_seed: [row(100011, true), row(100012, true), row(100013, false), row(100014, false)],
    checks: {
      walking_frac: { value: 0.5, need: 0.8, passed: false }, median_speed_upright: { value: 0.1, need: 0.2, passed: false },
      body_contact: { seeds_over: [100013], max_frac: 0.05, passed: false },
    },
  },
  seeds: { validate: validateSeeds, confirm: confirmSeeds },
}

export const assessNot: RecoveryAssessment = {
  rule: 'full_recovery_v1', status: 'NOT_RECOVERED', reasons: ['candidate aggregate is FAIL, not PASS'],
  validation: { original: seedsBad, candidate: seedsBad, verdict: verdictNo, aggregate: 'FAIL', walking_frac: 0 },
  confirmation: { run: false, reason: 'validation conditions not met' }, seeds: { validate: validateSeeds, confirm: confirmSeeds },
}

const base: Omit<RecoveryRecord, 'director' | 'mode' | 'provenance' | 'model' | 'director_record' | 'assessment' | 'status'> = {
  id: 'r-0123456789ab', created: '2026-10-17T10:00:00Z', creature: { cid: 'c-1a2b3c4d', n: 1, content_hash: 'h1' },
  budget: { requested: 2000, total: 2000, used: 300 }, scale: 'full', pipeline, error: null,
  candidate: { body: { foot_length: 0.1, torso_mass: 6 }, vector: [...Array(15).fill(1), 0.4, 0], edits: pipeline.final.edits, source: 'r1p0' },
}

export const recFullLive: RecoveryRecord = {
  ...base, director: 'ai', mode: 'live', provenance: 'LIVE', model: 'nvidia/nemotron-3-super', director_record: directorLive, assessment: assessFull, status: 'FULL_RECOVERY',
}
export const recPartialMock: RecoveryRecord = {
  ...base, director: 'ai', mode: 'scripted', provenance: 'SCRIPTED_MOCK', model: 'scripted-fixture', director_record: directorMock, assessment: assessPartial, status: 'PARTIAL_IMPROVEMENT',
}
export const recNotFix: RecoveryRecord = {
  ...base, director: 'fix', mode: null, provenance: 'NON_AI', model: null, director_record: null, assessment: assessNot, status: 'NOT_RECOVERED',
}
