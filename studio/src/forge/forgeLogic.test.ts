import { describe, expect, it } from 'vitest'
import {
  acceptBlockReason, armChip, armList, armScores, bodyDiffs, buildTimeline, canAccept, controllerDiffs, controllerNote, countOutcomes, fmtMinEffect,
  defaultSeed, forgeUrl, initialPoll, isModelFailed, isTerminal, jobFailureMessage, lineageRows, median, outcomeInfo, parseForgeLink, phaseText, pollReducer,
  progressFraction, pushDirection, replayChoices, resolveCitation, runHeadline, seedReason, shouldKeepPolling, verdictText, walkCostNote,
} from './forgeLogic'
import {
  creature, errorRun, ev, failedInvestigation, investigation, job, mockInvestigation, pushRun, standRun, walkRun,
} from './__fixtures__/forgeFixtures'

describe('outcome mapping', () => {
  it('keeps FAIL, POOR, PASS and ERROR textually and tonally distinct', () => {
    const infos = (['PASS', 'POOR', 'FAIL', 'ERROR'] as const).map((o) => outcomeInfo(o))
    expect(new Set(infos.map((i) => i.tone)).size).toBe(4)
    expect(new Set(infos.map((i) => i.text)).size).toBe(4)
    expect(infos.map((i) => i.label)).toEqual(['PASS', 'POOR', 'FAIL', 'ERROR'])
    expect(outcomeInfo('POOR').text).toMatch(/not a pass/)
    expect(outcomeInfo('ERROR').text).toMatch(/says nothing about the creature/)
  })
  it('does not hide an unknown outcome', () => {
    expect(outcomeInfo('WEIRD').label).toBe('WEIRD')
  })
  it('counts outcomes per seed', () => {
    expect(countOutcomes(pushRun.per_seed)).toEqual({ PASS: 2, POOR: 1, FAIL: 1, ERROR: 0 })
  })
  it('median handles odd, even and empty', () => {
    expect(median([3, 1, 2])).toBe(2)
    expect(median([1, 2, 3, 4])).toBe(2.5)
    expect(median([])).toBeNull()
  })
})

describe('plain-language reasons come from the records', () => {
  it('push headline states counts, median and the target from the spec', () => {
    const h = runHeadline(pushRun)
    expect(h).toMatch(/2 of 4 seeds passed, 1 poor, 1 failed/)
    expect(h).toMatch(/against a target of 25 N/)
  })
  it('an ERROR run says so and does not claim a result', () => {
    expect(runHeadline(errorRun)).toBe('Not one seed could be run.')
    expect(seedReason('push', errorRun.per_seed[0])).toBe('Could not run: mujoco: model failed to compile')
  })
  it('push seed reason names both critical forces and the weakest direction', () => {
    expect(seedReason('push', pushRun.per_seed[0])).toBe('Withstood 40.0 N forward and 31.5 N backward before falling. Weakest direction: backward.')
    expect(seedReason('push', pushRun.per_seed[3])).toMatch(/never fell at the highest force/)
  })
  it('stand reasons separate a fall from a poor stance', () => {
    expect(seedReason('stand', standRun.per_seed[0])).toBe('Fell after 2.50 s.')
    expect(seedReason('stand', standRun.per_seed[1])).toMatch(/leaned 34 degrees and sagged to 65%/)
  })
  it('walk reasons use the fall event time', () => {
    expect(seedReason('walk', walkRun.per_seed[1])).toBe('Fell at 0.80 s.')
    expect(seedReason('walk', walkRun.per_seed[0])).toMatch(/Walked 3.14 m/)
  })
})

describe('push direction and replay choices', () => {
  it('understands numbers and words', () => {
    expect(pushDirection(1)).toBe(1)
    expect(pushDirection(-1)).toBe(-1)
    expect(pushDirection('forward')).toBe(1)
    expect(pushDirection('bwd')).toBe(-1)
    expect(pushDirection(undefined)).toBeNull()
  })
  it('push replays carry direction and force (target first, then critical, then the other direction)', () => {
    const c = replayChoices(pushRun, pushRun.per_seed[0])
    expect(c[0]).toMatchObject({ direction: -1, force: 25 })
    expect(c[1]).toMatchObject({ direction: -1, force: 31.5 })
    expect(c[2]).toMatchObject({ direction: 1, force: 25 })
  })
  it('stand and walk replays have no push parameters', () => {
    const c = replayChoices(standRun, standRun.per_seed[0])
    expect(c).toHaveLength(1)
    expect(c[0].direction).toBeUndefined()
    expect(c[0].force).toBeUndefined()
  })
})

describe('default replay seed', () => {
  it('prefers a failing seed, then a poor one, and never an ERROR seed', () => {
    expect(defaultSeed(pushRun)).toBe(100003)
    expect(defaultSeed({ ...pushRun, per_seed: pushRun.per_seed.filter((s) => s.outcome !== 'FAIL') })).toBe(100002)
    expect(defaultSeed({ ...pushRun, per_seed: [pushRun.per_seed[0], pushRun.per_seed[3]] })).toBe(100001)
    expect(defaultSeed(errorRun)).toBeNull()
  })
})

describe('controller provenance text', () => {
  it('walk reports adaptation and how many rollouts it cost', () => {
    expect(controllerNote(walkRun)).toMatch(/adapted to this body using 60 extra physics rollouts \(budget 64\)/)
    expect(walkCostNote(walkRun)).toMatch(/used 60 extra rollouts/)
  })
  it('without a previous run the cost is stated as reported with the result, not guessed', () => {
    expect(walkCostNote(null)).toMatch(/reported with the result/)
  })
})

describe('job polling reducer', () => {
  it('merges events by index without duplicates and tracks since', () => {
    let s = pollReducer(initialPoll, { type: 'data', poll: { job: job(), events: [ev(1), ev(2)] } })
    expect(s.since).toBe(2)
    s = pollReducer(s, { type: 'data', poll: { job: job(), events: [ev(2), ev(3)] } })
    expect(s.events.map((e) => e.i)).toEqual([1, 2, 3])
    expect(s.since).toBe(3)
  })
  it('stops on a terminal status and keeps going while running', () => {
    const running = pollReducer(initialPoll, { type: 'data', poll: { job: job(), events: [] } })
    expect(shouldKeepPolling(running)).toBe(true)
    for (const status of ['done', 'failed', 'cancelled'] as const) {
      expect(shouldKeepPolling(pollReducer(initialPoll, { type: 'data', poll: { job: job({ status }), events: [] } }))).toBe(false)
      expect(isTerminal(status)).toBe(true)
    }
  })
  it('gives up after repeated network failures instead of spinning forever, and resets the count on success', () => {
    let s = initialPoll
    for (let i = 0; i < 5; i++) s = pollReducer(s, { type: 'error', message: 'offline' })
    expect(shouldKeepPolling(s)).toBe(false)
    expect(s.error).toBe('offline')
    s = pollReducer(s, { type: 'data', poll: { job: job(), events: [] } })
    expect(s.failures).toBe(0)
    expect(s.error).toBeNull()
  })
  it('progress and phase text', () => {
    expect(progressFraction(job())).toBe(0.25)
    expect(progressFraction(job({ progress: { phase: null, done: 0, total: 0 } }))).toBeNull()
    expect(progressFraction(job({ status: 'done' }))).toBe(1)
    expect(phaseText(job(), [])).toBe('challenge: 2 of 8 rollouts done')
    expect(phaseText(job({ status: 'queued' }), [])).toMatch(/Waiting/)
  })
  it('failure message prefers the job error and falls back to the last error event', () => {
    expect(jobFailureMessage(job({ status: 'failed', error: 'ImportError: no challenges' }), [])).toBe('ImportError: no challenges')
    expect(jobFailureMessage(job({ status: 'failed', error: null }), [ev(1, 'error', { message: 'boom' })])).toBe('boom')
    expect(jobFailureMessage(job({ status: 'failed', error: null }), [])).toMatch(/without a message/)
  })
})

describe('lineage ordering', () => {
  it('lists the newest version first and marks the current one', () => {
    const rows = lineageRows(creature)
    expect(rows.map((r) => r.n)).toEqual([4, 3, 2, 1])
    expect(rows.find((r) => r.current)?.n).toBe(3)
  })
  it('computes depth along the parent chain; an unknown parent is a root', () => {
    const d = Object.fromEntries(lineageRows(creature).map((r) => [r.n, r.depth]))
    expect(d).toEqual({ 1: 0, 2: 1, 3: 2, 4: 0 })
  })
  it('summarises origin and change from the record', () => {
    const rows = lineageRows(creature)
    expect(rows[3].summary).toBe('Drawn by you')
    expect(rows[2].summary).toBe('AI-proposed, verified: foot_length x1.3')
    expect(rows[1].summary).toBe('heuristic, verified: stand.kp = 70 (rear)')
    expect(rows[2].origin).toBe('ai_accepted')
  })
})

describe('verdict text and the accept rule', () => {
  const arms = armList(investigation)
  const byId = (id: string) => arms.find((a) => a.arm_id === id)
  it('verdict text is assembled from the record fields', () => {
    const t = verdictText(investigation.verdicts!['ai:P1'])
    expect(t).toMatch(/^Verified improvement:/)
    expect(t).toMatch(/20 wins, 2 losses, 2 ties over 24 paired seeds/)
    expect(t).toMatch(/median difference \+6.50/)
    expect(t).toMatch(/one-sided p = 0.000/)
    expect(t).toMatch(/abs 3 and rel 10%/)
  })
  it('includes the recorded reasons and never invents a missing verdict', () => {
    expect(verdictText(investigation.verdicts!['random:P1'])).toMatch(/Not verified.*Reasons: effect below minimum/)
    expect(verdictText(undefined)).toBe('No verdict was recorded for this arm.')
  })
  it('formats a scalar and a structured minimum effect', () => {
    expect(fmtMinEffect(3)).toBe('3')
    expect(fmtMinEffect({ abs: 3, rel: 0.1 })).toBe('abs 3 and rel 10%')
    expect(fmtMinEffect(undefined)).toBe('n/a')
  })
  it('accept is enabled only for VERIFIED_IMPROVEMENT', () => {
    expect(canAccept(byId('ai:P1'), investigation.verdicts!['ai:P1'])).toBe(true)
    expect(canAccept(byId('random:P1'), investigation.verdicts!['random:P1'])).toBe(false)
    expect(canAccept(byId('heuristic'), investigation.verdicts!.heuristic)).toBe(false)
    expect(canAccept(byId('original'), { status: 'VERIFIED_IMPROVEMENT' })).toBe(false)
    expect(canAccept(byId('ai:P1'), undefined)).toBe(false)
  })
  it('explains why accept is blocked', () => {
    expect(acceptBlockReason(byId('ai:P1'), investigation.verdicts!['ai:P1'])).toBeNull()
    expect(acceptBlockReason(byId('heuristic'), investigation.verdicts!.heuristic)).toMatch(/Worse than the original/)
    expect(acceptBlockReason(byId('original'), undefined)).toMatch(/starting point/)
    expect(acceptBlockReason(undefined, undefined)).toBe('Pick an arm first.')
  })
})

describe('provenance chips', () => {
  it('labels every arm source, and a scripted mock never wears NEMOTRON', () => {
    const arms = armList(investigation)
    expect(arms.map((a) => armChip(a, investigation.provenance).label)).toEqual(['ORIGINAL', 'NEMOTRON', 'RANDOM BASELINE', 'HEURISTIC'])
    expect(armChip(arms[1], mockInvestigation.provenance).label).toBe('SCRIPTED MOCK')
    expect(armChip(arms[2], mockInvestigation.provenance).label).toBe('RANDOM BASELINE')
  })
  it('accepts arms recorded as a map keyed by arm id', () => {
    const rec = { ...investigation, arms: { original: { arm_id: 'original', source: 'original' as const }, h: { source: 'heuristic' as const } as never } }
    expect(armList(rec).map((a) => a.arm_id)).toEqual(['original', 'h'])
  })
})

describe('investigation timeline', () => {
  const steps = buildTimeline(investigation)
  it('orders evidence, model call, hypotheses, proposals, arena, verdicts', () => {
    expect(steps.map((s) => s.kind)).toEqual(['evidence', 'model_call', 'hypotheses', 'proposals', 'arena', 'verdicts'])
  })
  it('model call card carries model, request id, token total and latency', () => {
    const s = steps[1]
    if (s.kind !== 'model_call') throw new Error('x')
    expect(s.call.model).toBe('nvidia/nemotron-test')
    expect(s.call.request_id).toBe('req-1')
    expect(s.call.latency_s).toBe(12.3)
    expect(s.tokens).toBe(2800)
  })
  it('hypothesis citations resolve to scalars in the evidence pack; unresolved ones are flagged undefined', () => {
    const s = steps[2]
    if (s.kind !== 'hypotheses') throw new Error('x')
    expect(s.items[0].cited.map((c) => c.value)).toEqual([4, undefined, undefined])
  })
  it('each proposal shows accepted or rejected with its reasons', () => {
    const s = steps[3]
    if (s.kind !== 'proposals') throw new Error('x')
    expect(s.items.map((p) => [p.id, p.status])).toEqual([['P1', 'accepted'], ['P2', 'rejected']])
    expect(s.items[1].reasons[0]).toMatch(/outside/)
    expect(s.items[0].expected).toBe('more force')
  })
  it('verdict step uses the recorded status for every arm that has one', () => {
    const s = steps[5]
    if (s.kind !== 'verdicts') throw new Error('x')
    expect(s.items.map((i) => [i.arm_id, i.status])).toEqual([['ai:P1', 'VERIFIED_IMPROVEMENT'], ['random:P1', 'NOT_VERIFIED'], ['heuristic', 'WORSE']])
  })
  it('a model failure is an honest failure step and flagged', () => {
    const f = buildTimeline(failedInvestigation)
    expect(isModelFailed(failedInvestigation)).toBe(true)
    const last = f[f.length - 1]
    if (last.kind !== 'failure') throw new Error('x')
    expect(last.message).toMatch(/HTTP 429/)
    expect(f.some((s) => s.kind === 'hypotheses' || s.kind === 'proposals')).toBe(false)
  })
  it('validation scores read in both recorded shapes', () => {
    expect(armScores(investigation, 'original')).toEqual([{ seed: 11, score: 10 }, { seed: 12, score: 12 }])
    expect(armScores(investigation, 'ai:P1')).toEqual([{ seed: 11, score: 20 }, { seed: 12, score: 22 }])
    expect(armScores(investigation, 'nope')).toEqual([])
  })
})

describe('citation resolver', () => {
  const ev1 = { a: { b: [{ c: 5 }, { c: 'x' }] }, list: [1, 2] }
  it('resolves dotted and indexed scalar paths', () => {
    expect(resolveCitation(ev1, 'a.b[0].c')).toBe(5)
    expect(resolveCitation(ev1, 'a.b[1].c')).toBe('x')
  })
  it('rejects lists, objects and missing paths', () => {
    expect(resolveCitation(ev1, 'list')).toBeUndefined()
    expect(resolveCitation(ev1, 'a.b[0]')).toBeUndefined()
    expect(resolveCitation(ev1, 'a.z')).toBeUndefined()
    expect(resolveCitation(undefined, 'a')).toBeUndefined()
  })
})

describe('parameter diffs', () => {
  const bounds: Record<string, [number, number]> = { foot_length: [0.02, 0.2], torso_mass: [1, 20] }
  it('puts before and after on the allowed range and flags what changed', () => {
    const d = bodyDiffs({ foot_length: 0.08, foot_length_r: 0.08, torso_mass: 6, other: 1 }, { foot_length: 0.104, foot_length_r: 0.104, torso_mass: 6 }, bounds)
    expect(d.map((x) => [x.name, x.changed])).toEqual([['foot_length', true], ['foot_length_r', true], ['torso_mass', false]])
    expect(d[0].uBefore).toBeCloseTo(0.333, 2)
    expect(d[0].uAfter).toBeCloseTo(0.467, 2)
  })
  it('skips parameters without a known range rather than inventing one', () => {
    expect(bodyDiffs({ x: 1 }, { x: 2 }, bounds)).toEqual([])
    expect(bodyDiffs({ foot_length: 0.08 }, undefined, bounds)).toEqual([])
  })
  it('lists changed controller values', () => {
    const rows = controllerDiffs({ stand: { kp: 60, kd: 4 }, walk: null }, { stand: { kp: 70, kd: 4 }, walk: null })
    expect(rows).toEqual([{ name: 'stand.kp', before: 60, after: 70 }])
  })
})

describe('deep links', () => {
  it('parses creature, version and run', () => {
    expect(parseForgeLink('?tab=forge&creature=c-1&v=3&run=r-9')).toEqual({ creature: 'c-1', v: 3, run: 'r-9' })
    expect(parseForgeLink('?tab=forge')).toEqual({ creature: null, v: null, run: null })
    expect(parseForgeLink('?tab=forge&creature=c-1&v=zero').v).toBeNull()
  })
  it('builds a link that parses back', () => {
    expect(parseForgeLink(forgeUrl('c-1', 2, 'r-5'))).toEqual({ creature: 'c-1', v: 2, run: 'r-5' })
    expect(forgeUrl('c-1')).toBe('?tab=forge&creature=c-1')
  })
})
