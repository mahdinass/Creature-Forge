// TEST-ONLY fixtures: hand-written records in the documented API shapes, used by vitest to exercise rendering logic.
// They are imported only from *.test.ts and are never imported by application code or shown in the UI.
import type { ChallengeRun, Creature, CreatureVersion, InvestigationRecord, Job, JobEvent } from '../forgeTypes'

const body = {
  torso_mass: 6, thigh_length: 0.3, shank_length: 0.3, foot_length: 0.08, foot_friction: 0.9, torque_limit: 40, leg_density: 400,
  thigh_length_r: 0.3, shank_length_r: 0.3, foot_length_r: 0.08, pose: [0, 0, 0, 0, 0, 0, 0],
}

const v = (n: number, parent: number | null, extra: Partial<CreatureVersion> = {}): CreatureVersion => ({
  n, parent, created: `2026-10-15T10:0${n}:00Z`, content_hash: `h${n}`, mode: 'experimental', body,
  controllers: { stand: { kp: 60, kd: 4 }, walk: null }, origin: parent === null ? 'user' : 'ai_accepted', drawing: null, change: null, ...extra,
})

export const creature: Creature = {
  id: 'c-1a2b3c4d', name: 'Stubby', created: '2026-10-15T10:00:00Z', current: 3,
  versions: [
    v(1, null),
    v(2, 1, { change: { source: 'nemotron', edits: [{ param: 'foot_length', op: 'scale', value: 1.3, target: 'both' }], verdict: { status: 'VERIFIED_IMPROVEMENT' } } }),
    v(3, 2, { change: { source: 'heuristic', edits: [{ param: 'stand.kp', op: 'set', value: 70, target: 'rear' }], verdict: { status: 'VERIFIED_IMPROVEMENT' } } }),
    v(4, 9, { origin: 'user' }),
  ],
}

export const pushRun: ChallengeRun = {
  run_id: 'r-0a0b0c0d',
  creature: { cid: 'c-1a2b3c4d', n: 1, content_hash: 'h1' },
  created: '2026-10-15T10:05:00Z',
  spec: { kind: 'push', seeds: [100001, 100002, 100003, 100004], duration: 5, target_force: 25 },
  body,
  controller: { stand: { kind: 'stand-pd', edited: false }, walk: { kind: 'none', vector: null, adaptation: null } },
  per_seed: [
    { seed: 100001, outcome: 'PASS', score: 31.5, metrics: { critical_force_fwd: 40, critical_force_bwd: 31.5, weak_direction: -1 }, events: [], rollouts: 14 },
    { seed: 100002, outcome: 'POOR', score: 17.2, metrics: { critical_force_fwd: 17.2, critical_force_bwd: 22, weak_direction: 'forward' }, events: [], rollouts: 14 },
    { seed: 100003, outcome: 'FAIL', score: 4, metrics: { critical_force_fwd: 9, critical_force_bwd: 4, weak_direction: 'bwd' }, events: [{ time: 1.2, kind: 'fall' }], rollouts: 14 },
    { seed: 100004, outcome: 'PASS', score: 80, metrics: { critical_force_fwd: 80, critical_force_bwd: 80, censored: true }, events: [], rollouts: 14 },
  ],
  outcome: 'POOR',
}

export const errorRun: ChallengeRun = {
  ...pushRun,
  per_seed: [{ seed: 5, outcome: 'ERROR', score: 0, metrics: {}, events: [], rollouts: 0, error: 'mujoco: model failed to compile' }],
  outcome: 'ERROR',
}

export const standRun: ChallengeRun = {
  ...pushRun,
  spec: { kind: 'stand', seeds: [1, 2], duration: 8 },
  per_seed: [
    { seed: 1, outcome: 'FAIL', score: 2.5, metrics: { fell: true, fall_time: 2.5, survival_s: 2.5 }, events: [], rollouts: 1 },
    { seed: 2, outcome: 'POOR', score: 8, metrics: { fell: false, survival_s: 8, max_abs_pitch_after_settle: 0.6, min_height_ratio: 0.65 }, events: [], rollouts: 1 },
  ],
  outcome: 'FAIL',
}

export const walkRun: ChallengeRun = {
  ...pushRun,
  spec: { kind: 'walk', seeds: [1, 2], duration: 10 },
  controller: { walk: { kind: 'adapted', vector: null, adaptation: { budget: 64, rollouts_used: 60 } } },
  per_seed: [
    { seed: 1, outcome: 'PASS', score: 3.14159, metrics: {}, events: [], rollouts: 1 },
    { seed: 2, outcome: 'FAIL', score: 0, metrics: {}, events: [{ time: 0.8, kind: 'fall' }], rollouts: 1 },
  ],
  outcome: 'POOR',
}

export const job = (over: Partial<Job> = {}): Job => ({
  id: 'j-00000001', kind: 'challenge', status: 'running', created: 'x', started: 'x', finished: null,
  progress: { phase: 'challenge', done: 2, total: 8 }, result_ref: null, error: null, ...over,
})
export const ev = (i: number, type = 'progress', data: Record<string, unknown> = {}): JobEvent => ({ i, t: i * 0.5, type, data })

const verified = { status: 'VERIFIED_IMPROVEMENT' as const, rule: 'verdict_v1', n: 24, wins: 20, losses: 2, ties: 2, median_diff: 6.5, p_one_sided: 0.0001, min_effect: { abs: 3, rel: 0.1 } }

export const investigation: InvestigationRecord = {
  id: 'i-aaaa1111', created: '2026-10-15T11:00:00Z', mode: 'live', provenance: 'LIVE',
  creature: { cid: 'c-1a2b3c4d', n: 1, content_hash: 'h1' }, challenge_run_id: 'r-0a0b0c0d',
  evidence: { creature: { mode: 'experimental' }, outcome: { aggregate: 'FAIL' }, seeds: [{ seed: 100003, score: 4, metrics: { critical_force_bwd: 4 } }] },
  model_calls: [{ model: 'nvidia/nemotron-test', request_id: 'req-1', latency_s: 12.3, usage: { prompt_tokens: 2000, completion_tokens: 800 }, cost_usd: 0.01, finish_reason: 'stop', http_status: 200, error: null }],
  reply: {
    diagnosis: { summary: 'Falls backwards.', hypotheses: [{ id: 'H1', mechanism: 'Short feet.', evidence: ['seeds[0].metrics.critical_force_bwd', 'seeds[0].metrics.nothing', 'seeds[0]'] }] },
    proposals: [{ id: 'P1', hypothesis: 'H1', category: 'morphology', prediction: { expected_change: 'more force' } }, { id: 'P2', hypothesis: 'H1' }],
  },
  validation: { proposals: [{ id: 'P1', status: 'accepted' }, { id: 'P2', status: 'rejected', reasons: ['foot_length: ratio 2.0 outside [0.5, 1.5]'] }] },
  arms: [
    { arm_id: 'original', source: 'original' },
    { arm_id: 'ai:P1', source: 'nemotron', proposal_id: 'P1', body: { ...body, foot_length: 0.104 } },
    { arm_id: 'random:P1', source: 'random_baseline' },
    { arm_id: 'heuristic', source: 'heuristic', unavailable: undefined },
  ],
  seeds: { screen: [1, 2, 3], validate: [11, 12, 13, 14] },
  validation_results: {
    original: [{ seed: 11, score: 10 }, { seed: 12, score: 12 }],
    'ai:P1': { 11: { score: 20 }, 12: { score: 22 } },
  },
  verdicts: {
    'ai:P1': verified,
    'random:P1': { status: 'NOT_VERIFIED', n: 24, wins: 9, losses: 8, ties: 7, median_diff: 0.4, p_one_sided: 0.4, min_effect: 3, reasons: ['effect below minimum'] },
    heuristic: { status: 'WORSE', reasons: ['mirrored test significant'] },
  },
  status: 'done',
}

export const mockInvestigation: InvestigationRecord = { ...investigation, id: 'i-bbbb2222', mode: 'scripted', provenance: 'SCRIPTED_MOCK' }

export const failedInvestigation: InvestigationRecord = {
  id: 'i-cccc3333', created: 'x', mode: 'live', provenance: 'LIVE', creature: { cid: 'c-1a2b3c4d', n: 1, content_hash: 'h1' },
  challenge_run_id: 'r-0a0b0c0d', evidence: { a: 1 },
  model_calls: [{ model: 'nvidia/nemotron-test', error: 'HTTP 429 rate limited', http_status: 429 }],
  arms: [{ arm_id: 'original', source: 'original' }, { arm_id: 'heuristic', source: 'heuristic' }],
  status: 'model_failed', error: 'model call failed: HTTP 429 rate limited',
}
