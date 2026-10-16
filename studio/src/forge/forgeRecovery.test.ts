import { describe, expect, it } from 'vitest'
import {
  buildReasoning, canOfferRecovery, changeSummary, controllerChange, countWalking, editRows, evidenceMap, expectationChip, fmtRatio, ledgerSegments, lineageRows,
  measuredText, modelCostText, newestRecoveryFirst, originLabel, recoveryAcceptState, recoveryBudgetBar, recoveryHeadline, recoveryPhaseText, recoveryProvenance,
  recoveryStageStates, recoverySummaryText,
} from './forgeLogic'
import type { Creature, Job, JobEvent, RecoverySummary } from './forgeTypes'
import { creature, pushRun, walkRun } from './__fixtures__/forgeFixtures'
import { assessPartial, directorLive, pipeline, recFullLive, recNotFix, recPartialMock } from './__fixtures__/recoveryFixtures'

describe('recovery status wording', () => {
  it('FULL_RECOVERY states the validation and confirmation counts from the record', () => {
    const h = recoveryHeadline(recFullLive)
    expect(h.tone).toBe('ok')
    expect(h.text).toBe('Walks: recovered (4/4 validation seeds walking, confirmed 4/4 at 20 s)')
  })
  it('PARTIAL_IMPROVEMENT is never called a recovery', () => {
    const h = recoveryHeadline(recPartialMock)
    expect(h.text).toBe('Improved, but does not walk reliably (not a recovery)')
    expect(h.text).not.toMatch(/Walks|recovered/)
    expect(h.tone).toBe('warn')
  })
  it('NOT_RECOVERED names the budget it was given', () => {
    expect(recoveryHeadline(recNotFix).text).toBe('Not recovered within 2000 rollouts')
    expect(recoveryHeadline(recNotFix).tone).toBe('bad')
  })
  it('errors, failures and cancellations are not successes', () => {
    expect(recoveryHeadline({ ...recNotFix, status: 'INCONCLUSIVE_ERROR' }).text).toMatch(/never counted as success/)
    expect(recoveryHeadline({ ...recNotFix, status: 'failed', error: 'boom' }).text).toBe('The recovery failed: boom')
    expect(recoveryHeadline({ ...recNotFix, status: 'cancelled' }).tone).toBe('error')
    expect(recoveryHeadline({ ...recNotFix, status: 'weird' }).text).toMatch(/Unknown recovery status: weird/)
  })
  it('the history line mirrors the status', () => {
    const s = (status: string, walking_frac: number | null): RecoverySummary => ({
      id: 'r-1', created: 'x', creature: { cid: 'c', n: 1 }, director: 'ai', mode: 'scripted', provenance: 'SCRIPTED_MOCK', model: null, status, budget: {}, n_edits: 0, walking_frac,
    })
    expect(recoverySummaryText(s('FULL_RECOVERY', 1))).toBe('Recovered, 100% of validation seeds walking')
    expect(recoverySummaryText(s('PARTIAL_IMPROVEMENT', 0.75))).toBe('Improved, not a recovery, 75% of validation seeds walking')
    expect(recoverySummaryText(s('failed', null))).toBe('Failed')
  })
  it('counts walking seeds only for PASS', () => {
    expect(countWalking(assessPartial.validation.candidate)).toEqual({ walking: 3, n: 4 })
    expect(countWalking(undefined)).toEqual({ walking: 0, n: 0 })
  })
  it('provenance labels: scripted mock and no-AI are never LIVE', () => {
    expect(recoveryProvenance('LIVE').label).toBe('LIVE')
    expect(recoveryProvenance('SCRIPTED_MOCK').label).toBe('SCRIPTED MOCK')
    expect(recoveryProvenance('SCRIPTED_MOCK').text).toMatch(/Not a model/)
    expect(recoveryProvenance('NON_AI').label).toBe('NO AI')
  })
})

describe('offering and accepting', () => {
  it('Recover walking is offered only for a FAIL or POOR walk challenge of this version', () => {
    expect(canOfferRecovery(walkRun, walkRun.creature.n)).toBe(walkRun.outcome === 'FAIL' || walkRun.outcome === 'POOR')
    expect(canOfferRecovery({ ...walkRun, outcome: 'FAIL' }, walkRun.creature.n)).toBe(true)
    expect(canOfferRecovery({ ...walkRun, outcome: 'POOR' }, walkRun.creature.n)).toBe(true)
    expect(canOfferRecovery({ ...walkRun, outcome: 'PASS' }, walkRun.creature.n)).toBe(false)
    expect(canOfferRecovery({ ...walkRun, outcome: 'ERROR' }, walkRun.creature.n)).toBe(false)
    expect(canOfferRecovery({ ...walkRun, outcome: 'FAIL' }, walkRun.creature.n + 1)).toBe(false)
    expect(canOfferRecovery({ ...pushRun, outcome: 'FAIL' }, pushRun.creature.n)).toBe(false)
    expect(canOfferRecovery(null, 1)).toBe(false)
  })
  it('accept is allowed only for FULL_RECOVERY and the refusal says why', () => {
    expect(recoveryAcceptState(recFullLive)).toEqual({ allowed: true, reason: null })
    const p = recoveryAcceptState(recPartialMock)
    expect(p.allowed).toBe(false)
    expect(p.reason).toMatch(/Only FULL_RECOVERY can be accepted/)
    expect(p.reason).toMatch(/confirmation: walking on 50%/)
    expect(recoveryAcceptState(recNotFix).allowed).toBe(false)
    expect(recoveryAcceptState({ ...recFullLive, status: 'INCONCLUSIVE_ERROR' }).allowed).toBe(false)
    // a record whose top-level status says FULL but whose assessment does not is not acceptable either
    expect(recoveryAcceptState({ ...recFullLive, assessment: assessPartial }).allowed).toBe(false)
    expect(recoveryAcceptState({ ...recFullLive, candidate: null }).allowed).toBe(false)
  })
  it('lineage labels the origins, including the rule-based accept', () => {
    expect(originLabel('baseline_accepted')).toBe('Rule-based change, accepted')
    expect(originLabel('ai_accepted', 'nemotron')).toBe('AI change, accepted')
    expect(originLabel('ai_accepted', 'scripted_mock')).toBe('Scripted mock change, accepted')
    const c: Creature = {
      ...creature, current: 2,
      versions: [creature.versions[0], {
        ...creature.versions[1], n: 2, parent: 1, origin: 'baseline_accepted',
        change: { kind: 'recovery', source: 'fix_rule', recovery_id: 'r-0123456789ab', status: 'FULL_RECOVERY', edits: [{ param: 'foot_length', op: 'scale', value: 1.25, target: 'both' }] },
      }],
    }
    const row = lineageRows(c)[0]
    expect(row.origin).toBe('baseline_accepted')
    expect(changeSummary(row.version)).toMatch(/Fixed engineering rule: walking recovery, both legs: foot length x 1.25 · full recovery/)
  })
})

describe('expectation against measurement', () => {
  const ok = { status: 'ok' }
  it('improves matches when more seeds walk or fitness rises', () => {
    expect(expectationChip('improves', { ...ok, delta_walking: 2, delta_mean_fitness: -1 }).label).toBe('MATCHED EXPECTATION')
    expect(expectationChip('improves', { ...ok, delta_walking: 0, delta_mean_fitness: 0.2 }).label).toBe('MATCHED EXPECTATION')
    expect(expectationChip('improves', { ...ok, delta_walking: 0, delta_mean_fitness: 0 })).toEqual({ label: 'DID NOT MATCH', tone: 'bad' })
    expect(expectationChip('improves', { ...ok, delta_walking: -1, delta_mean_fitness: -0.1 }).label).toBe('DID NOT MATCH')
  })
  it('no_change matches when nothing improved', () => {
    expect(expectationChip('no_change', { ...ok, delta_walking: 0, delta_mean_fitness: -0.2 }).label).toBe('MATCHED EXPECTATION')
    expect(expectationChip('no_change', { ...ok, delta_walking: 1, delta_mean_fitness: 0 }).label).toBe('DID NOT MATCH')
  })
  it('an unmeasured probe or a missing expectation is not scored', () => {
    expect(expectationChip('improves', { status: 'error' })).toEqual({ label: 'NOT MEASURED', tone: 'muted' })
    expect(expectationChip(undefined, ok).label).toBe('NO EXPECTATION RECORDED')
    expect(expectationChip('wild', ok).label).toBe('NO EXPECTATION RECORDED')
  })
  it('measured text shows signed deltas and the reason for a failure', () => {
    expect(measuredText({ status: 'ok', delta_walking: 2, delta_mean_fitness: 0.31 })).toBe('+2 walking training seeds, +0.31 mean fitness, against the unchanged creature')
    expect(measuredText({ status: 'ok', delta_walking: 0, delta_mean_fitness: -0.05 })).toMatch(/^0 walking training seeds, −0.05 mean fitness/)
    expect(measuredText({ status: 'error', reason: 'ValueError: x' })).toBe('not measured: ValueError: x')
  })
})

describe('how the director reasoned', () => {
  it('reads the cited values from the evidence the model actually saw', () => {
    const m = evidenceMap(directorLive.calls[0])
    expect(m.get('creature.features.foot_to_leg')).toBe('0.267')
    expect(m.get('baseline.outcomes.0.label')).toBe('fell_early')
    expect(m.has('TASK:')).toBe(false)
    expect(evidenceMap(undefined).size).toBe(0)
  })
  it('builds hypotheses, probes with expectation chips, refutations, diagnosis and plans per round', () => {
    const v = buildReasoning(recFullLive)
    expect(v.title).toBe('How the AI reasoned')
    expect(v.mock).toBe(false)
    const r = v.rounds[0]
    expect(r.hypotheses.map((h) => h.id)).toEqual(['H1', 'H2'])
    expect(r.hypotheses[0].cites).toEqual([
      { path: 'creature.features.foot_to_leg', value: '0.267' }, { path: 'baseline.outcomes.0.label', value: 'fell_early' },
    ])
    expect(r.hypotheses[1].cites[0].value).toBeNull()
    expect(r.hypotheses[1].refuted).toBe(true)
    expect(r.refuted).toEqual(['H2'])
    expect(r.probes.map((p) => [p.id, p.chip.label])).toEqual([['opt_posture', 'MATCHED EXPECTATION'], ['opt_timing', 'DID NOT MATCH']])
    expect(r.probes[0].hypothesis).toBe('H1')
    expect(r.diagnosis).toBe('Posture, not timing, limits the gait.')
    expect(r.rejectedProbes).toEqual(['opt_bogus: unknown probe'])
    expect(r.rejectedPlans[0]).toMatch(/shares 1.5 exceed 1/)
    const p = r.plans[0]
    expect(p.subsystems).toEqual([{ kind: 'control', name: 'posture' }, { kind: 'control', name: 'placement' }, { kind: 'body', name: 'foot_length' }])
    expect(p.share).toBe(0.5)
    expect(p.hypothesis).toBe('H1')
    expect(p.prediction).toBe('Longer feet and posture let it walk.')
    expect(p.measured).toMatch(/^\+3 walking training seeds, \+0.9 mean fitness/)
    expect(p.refunded).toBe(20)
  })
  it('the fixed rule view is labelled as such and has no hypotheses or expectations', () => {
    const v = buildReasoning(recNotFix)
    expect(v.title).toBe('Rule decisions (no AI)')
    expect(v.isAi).toBe(false)
    expect(v.rounds[0].hypotheses).toEqual([])
    expect(v.rounds[0].probes.every((p) => p.expect === null && p.chip.label === 'NO EXPECTATION RECORDED')).toBe(true)
    expect(v.rounds[0].plans[0].subsystems.length).toBe(3)
  })
  it('a scripted mock is never presented as a model', () => {
    const v = buildReasoning(recPartialMock)
    expect(v.mock).toBe(true)
    expect(v.title).toMatch(/not a model/)
    expect(v.rounds[0].diagnosis).toMatch(/not a model/)
    expect(v.rounds[0].hypotheses).toEqual([])
  })
  it('reports a director decision that failed instead of hiding it', () => {
    const d = { ...directorLive, decisions: [{ kind: 'plans' as const, round: 1, status: 'invalid', validation_errors: ['plans[0]: bad share'] }] }
    const v = buildReasoning({ ...recFullLive, director_record: d })
    expect(v.rounds[0].directorIssues[0]).toBe('plans decision invalid: plans[0]: bad share')
  })
  it('handles a record without a pipeline', () => {
    expect(buildReasoning({ ...recFullLive, pipeline: null }).rounds).toEqual([])
  })
  it('model cost text counts sent calls', () => {
    expect(modelCostText(directorLive)).toBe('2 model calls, $0.012')
    expect(modelCostText(null)).toBe('no model calls')
  })
})

describe('budget ledger', () => {
  it('aggregates the pipeline lines by category, nets refunds and ignores the screening reserve', () => {
    const l = ledgerSegments(pipeline)
    const by = Object.fromEntries(l.segments.map((s) => [s.key, s.n]))
    expect(by).toEqual({ start: 10, probes: 70, plans: 140, screening: 80, unspent: 100 })
    expect(l.refunded).toBe(30)
    expect(l.total).toBe(400)
    expect(l.used).toBe(300)
    expect(by.start + by.probes + by.plans + by.screening).toBe(l.used)
    expect(by.start + by.probes + by.plans + by.screening + by.unspent).toBe(l.total)
  })
  it('is empty and safe without a pipeline', () => {
    const l = ledgerSegments(null)
    expect(l.total).toBe(0)
    expect(l.segments.every((s) => s.n === 0)).toBe(true)
  })
})

describe('candidate formatting', () => {
  it('edit rows give old -> new and the ratio', () => {
    const rows = editRows([{ param: 'foot_length', op: 'scale', value: 1.25, target: 'both' }], { foot_length: 0.08 }, { foot_length: 0.1 })
    expect(rows).toEqual([{ param: 'foot_length', label: 'foot length', before: 0.08, after: 0.1, ratio: 1.25 }])
    expect(fmtRatio(1.25)).toBe('x 1.25')
    expect(fmtRatio(NaN)).toBe('n/a')
  })
  it('derives the after value from the ratio when the candidate body lacks it', () => {
    const rows = editRows([{ param: 'torso_mass', op: 'scale', value: 0.7, target: 'both' }], { torso_mass: 6 }, {})
    expect(rows[0].after).toBeCloseTo(4.2)
  })
  it('controller change highlights the foot-placement gains and compares with the version vector when it has one', () => {
    const after = [...Array(15).fill(1), 0.4, 0]
    const none = controllerChange(null, after)
    expect(none.hasBefore).toBe(false)
    expect(none.changed).toBeNull()
    expect(none.fpActive).toBe(true)
    expect(none.rows.filter((r) => r.fp).map((r) => r.name)).toEqual(['fp_kd', 'fp_kv'])
    const before = [...Array(15).fill(1)]
    before[3] = 0.5
    const some = controllerChange(before, after)
    expect(some.changed).toBe(2)   // knee_amp and fp_kd; fp_kv stays 0
    expect(some.rows[3]).toMatchObject({ name: 'knee_amp', before: 0.5, after: 1, changed: true })
    expect(controllerChange(before, [...before, 0, 0]).fpActive).toBe(false)
  })
})

describe('job progress', () => {
  const job = (status: Job['status'], phase: string | null, done = 0, total = 0): Job => ({
    id: 'j', kind: 'recovery', status, created: '', started: null, finished: null, progress: { phase, done, total }, result_ref: null, error: null,
  })
  const ev = (phase: string): JobEvent => ({ i: 1, t: 0, type: 'phase', data: { phase } })
  it('marks earlier phases done and the current one active', () => {
    const s = recoveryStageStates(job('running', 'screening', 4, 400), [])
    expect(s).toMatchObject({ diagnostics: 'done', probes: 'done', plans: 'done', screening: 'active', validation: 'pending', confirmation: 'pending' })
    expect(recoveryStageStates(job('done', null), []).confirmation).toBe('done')
    expect(recoveryStageStates(null, [ev('probes')]).probes).toBe('active')
    expect(recoveryStageStates(null, []).diagnostics).toBe('pending')
  })
  it('the budget bar shows search rollouts, then validation rollouts', () => {
    expect(recoveryBudgetBar(job('running', 'plans', 100, 400), 2000)).toMatchObject({ done: 100, total: 400, fraction: 0.25 })
    expect(recoveryBudgetBar(job('running', 'diagnostics', 0, 0), 2000)?.total).toBe(2000)
    expect(recoveryBudgetBar(job('running', 'validation', 3, 8), 2000)).toMatchObject({ label: 'validation rollouts', fraction: 0.375 })
    expect(recoveryBudgetBar(job('done', null), 2000)?.fraction).toBe(1)
    expect(recoveryBudgetBar(null, 2000)).toBeNull()
  })
  it('phase text', () => {
    expect(recoveryPhaseText(job('running', 'probes', 40, 400), [])).toBe('Probes: 40 of 400 rollouts')
    expect(recoveryPhaseText(job('queued', null), [])).toMatch(/Waiting/)
    expect(recoveryPhaseText(job('failed', null), [])).toBe('The recovery failed.')
  })
  it('lists newest first', () => {
    const a = { id: 'r-a', created: '2026-10-17T10:00:00Z' } as RecoverySummary
    const b = { id: 'r-b', created: '2026-10-17T11:00:00Z' } as RecoverySummary
    expect(newestRecoveryFirst([a, b]).map((x) => x.id)).toEqual(['r-b', 'r-a'])
  })
})
