import { describe, expect, it } from 'vitest'
import {
  acceptBlockReason, armChip, armList, armScores, bodyDiffs, budgetLine, buildTimeline, canAccept, controllerDiffs, controllerNote, countOutcomes, defaultSeed,
  describeEdit, describeEdits, fmtMinEffect, forgeUrl, hypotheticalNote, initialPoll, isHypothetical, isModelFailed, isTerminal, jobFailureMessage, lineageRows,
  loopLines, median, modelResponseOf, newestFirst, originLabel, outcomeInfo, parseForgeLink, probeRows, phaseText, pollReducer, progressFraction, provenanceLabel, pushDirection,
  replayChoices, resolveCitation, runHeadline, seedReason, shouldKeepPolling, stageStates, stopText, summaryChips, validationTriplet, verdictText, walkCostNote,
} from './forgeLogic'
import type { InvestigationSummary, LoopResult } from './forgeTypes'
import {
  creature, errorRun, ev, job, mockVariant, modelFailedVariant, pushRun, standRun, walkRun,
} from './__fixtures__/forgeFixtures'
import { liveHypothetical } from './__fixtures__/real_liveHypothetical'
import { liveNotVerified } from './__fixtures__/real_liveNotVerified'
import { liveStand } from './__fixtures__/real_liveStand'
import { liveVerified } from './__fixtures__/real_liveVerified'

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
    expect(rows[2].summary).toBe('Nemotron: both legs: foot length x 1.3 \u00b7 verified')
    expect(rows[1].summary).toBe('Heuristic: stand kp set to 70 \u00b7 verified')
    expect(rows[2].origin).toBe('ai_accepted')
    expect(originLabel('ai_accepted', 'scripted_mock')).toBe('Scripted mock change, accepted')
    expect(originLabel('ai_accepted', 'nemotron')).toBe('AI change, accepted')
    expect(originLabel('user')).toBe('Yours')
  })
})

describe('verdict wording from real LIVE records', () => {
  const v = liveVerified.verdicts!['ai:P1']
  it('a verified improvement reads as held-out seeds with the tally, never as "significant"', () => {
    const t = verdictText(v)
    expect(t).toMatch(/^Verified improvement on 12 held-out seeds \(12 wins \/ 0 losses \/ 0 ties\)\./)
    expect(t).toMatch(/Median paired difference \+3\.13 N/)
    expect(t).toMatch(/one-sided sign-test p = 2\.4e-4/)
    expect(t).toMatch(/3 absolute and 10% relative/)
    expect(t).not.toMatch(/significan|bproves?b/i)
  })
  it('NOT_VERIFIED keeps its losses visible', () => {
    expect(verdictText(liveNotVerified.verdicts!['ai:P1'])).toMatch(/^Not verified on 12 held-out seeds \(0 wins \/ 8 losses \/ 4 ties\)\./)
  })
  it('INCONCLUSIVE with every pair tied says there was no measurable effect', () => {
    expect(verdictText(liveHypothetical.verdicts!['ai:P1'])).toMatch(/^No measurable effect on these seeds \(all 12 pairs tied\)\./)
    expect(verdictText(liveNotVerified.verdicts!.heuristic)).toMatch(/^No measurable effect on these seeds/)
  })
  it('INCONCLUSIVE with some differing pairs is not described as "no effect"', () => {
    const t = verdictText({ status: 'INCONCLUSIVE', n: 12, wins: 3, losses: 0, ties: 9 })
    expect(t).toMatch(/^Inconclusive: too few seeds differed/)
  })
  it('never invents a missing verdict', () => {
    expect(verdictText(undefined)).toBe('No verdict was recorded for this arm.')
  })
  it('formats a scalar and a structured minimum effect', () => {
    expect(fmtMinEffect(3)).toBe('3')
    expect(fmtMinEffect({ abs: 3, rel: 0.1, required: 3 })).toBe('3 absolute and 10% relative')
    expect(fmtMinEffect(undefined)).toBe('n/a')
  })
})

describe('the accept rule', () => {
  const arms = armList(liveVerified)
  const byId = (id: string) => arms.find((a) => a.arm_id === id)
  it('accept is enabled only for VERIFIED_IMPROVEMENT (real verdicts)', () => {
    expect(canAccept(byId('ai:P1'), liveVerified.verdicts!['ai:P1'])).toBe(true)
    expect(canAccept(byId('random:P2'), liveVerified.verdicts!['random:P2'])).toBe(false)
    expect(canAccept(byId('original'), { status: 'VERIFIED_IMPROVEMENT' })).toBe(false)
    expect(canAccept(byId('ai:P1'), undefined)).toBe(false)
    const nv = armList(liveNotVerified).find((a) => a.arm_id === 'ai:P1')
    expect(canAccept(nv, liveNotVerified.verdicts!['ai:P1'])).toBe(false)
  })
  it('explains why accept is blocked', () => {
    expect(acceptBlockReason(byId('ai:P1'), liveVerified.verdicts!['ai:P1'])).toBeNull()
    const nv = armList(liveNotVerified).find((a) => a.arm_id === 'heuristic')
    expect(acceptBlockReason(nv, liveNotVerified.verdicts!.heuristic)).toMatch(/inconclusive/)
    expect(acceptBlockReason(byId('original'), undefined)).toMatch(/starting point/)
    expect(acceptBlockReason(undefined, undefined)).toBe('Pick an arm first.')
  })
  it('a round that started from an unaccepted proposal says it cannot be accepted directly', () => {
    expect(hypotheticalNote(liveHypothetical)).toMatch(/Round 3 evaluated an earlier, unaccepted proposal/)
    expect(hypotheticalNote(liveVerified)).toBeNull()
    expect(isHypothetical(liveHypothetical)).toBe(true)
  })
})

describe('provenance chips', () => {
  it('labels every arm source of a real record', () => {
    expect(armList(liveVerified).map((a) => armChip(a, liveVerified.provenance).label)).toEqual(
      ['ORIGINAL', 'NEMOTRON', 'NEMOTRON', 'RANDOM BASELINE', 'RANDOM BASELINE', 'HEURISTIC'])
  })
  it('a scripted mock never wears NEMOTRON, whichever field carries the mark', () => {
    expect(armList(mockVariant).filter((a) => a.proposal_id).map((a) => armChip(a, mockVariant.provenance).label)).toEqual(['SCRIPTED MOCK', 'SCRIPTED MOCK', 'RANDOM BASELINE', 'RANDOM BASELINE'])
    expect(armChip({ source: 'nemotron' }, 'SCRIPTED_MOCK').label).toBe('SCRIPTED MOCK')
    expect(provenanceLabel('SCRIPTED_MOCK')).toBe('SCRIPTED MOCK')
  })
})

describe('edits in plain language', () => {
  it('names the leg, the part and the factor', () => {
    expect(describeEdit({ param: 'foot_length', op: 'scale', value: 1.25, target: 'rear' })).toBe('rear leg: foot length x 1.25')
    expect(describeEdit({ param: 'foot_friction', op: 'scale', value: 1.5, target: 'both' })).toBe('both legs: foot grip x 1.5')
    expect(describeEdit({ param: 'thigh_length', op: 'scale', value: 0.6666666666666666, target: 'both' })).toBe('both legs: thigh length x 0.667')
    expect(describeEdit({ param: 'stand.kp', op: 'set', value: 120 })).toBe('stand kp set to 120')
    expect(describeEdits([])).toBe('no change')
  })
})

describe('investigation timeline from a real record', () => {
  const steps = buildTimeline(liveVerified)
  const kinds = steps.map((s) => s.kind)
  it('orders evidence, model call, hypotheses, proposals, arms, screening, validation', () => {
    expect(kinds).toEqual(['evidence', 'model_call', 'hypotheses', 'proposals', 'arena', 'screening', 'validation'])
  })
  it('model call card carries model, request id, latency, tokens and finish reason', () => {
    const s = steps[1]
    if (s.kind !== 'model_call') throw new Error('x')
    expect(s.call.model).toBe('nvidia/nemotron-3-super-120b-a12b')
    expect(s.call.request_id).toBe('094f7fc829906d21d023e25a866a65b1')
    expect(s.call.latency_s).toBeCloseTo(2.7, 1)
    expect(s.call.finish_reason).toBe('stop')
    expect(s.tokens).toBe(5760)
  })
  it('hypotheses show the evidence values the validator resolved', () => {
    const s = steps[2]
    if (s.kind !== 'hypotheses') throw new Error('x')
    expect(s.items[0].cited).toEqual([
      { path: 'forensics.support.min_xcom_margin_after_push_m', value: -0.5385 },
      { path: 'creature.body.rear.foot_length', value: 0.1608 },
    ])
  })
  it('proposals carry status, plain-language edits and the model prediction', () => {
    const s = steps[3]
    if (s.kind !== 'proposals') throw new Error('x')
    expect(s.items.map((p) => [p.id, p.status])).toEqual([['P1', 'accepted'], ['P2', 'accepted']])
    expect(s.items[0].edits).toBe('rear leg: foot length x 1.25')
    expect(s.items[0].expected).toBe('+2.5 N')
  })
  it('arm table lists every arm with chip, edits and rollouts', () => {
    const s = steps[4]
    if (s.kind !== 'arena') throw new Error('x')
    expect(s.arms.map((a) => a.arm_id)).toEqual(['original', 'ai:P1', 'ai:P2', 'random:P1', 'random:P2', 'heuristic'])
    expect(s.arms[1].edits).toBe('rear leg: foot length x 1.25')
    expect(s.arms[1].rollouts).toBe(306)
    expect(s.screenSeeds).toBe(6)
    expect(s.validateSeeds).toBe(12)
  })
  it('screening ranking is the recorded one and says which arms were selected', () => {
    const s = steps[5]
    if (s.kind !== 'screening') throw new Error('x')
    expect(s.ai.map((r) => r.arm_id)).toEqual(['ai:P1', 'ai:P2'])
    expect(s.selected.ai).toBe('ai:P1')
    expect(s.selected.baseline).toBe('random:P2')
  })
  it('validation puts the AI arm, its twin (when recorded) and the best baseline side by side', () => {
    const s = steps[6]
    if (s.kind !== 'validation') throw new Error('x')
    expect(s.ai?.verdict?.status).toBe('VERIFIED_IMPROVEMENT')
    expect(s.ai?.text).toMatch(/^Verified improvement on 12 held-out seeds/)
    expect(s.baseline?.arm_id).toBe('random:P2')
    expect(s.baseline?.verdict?.status).toBe('NOT_VERIFIED')
    expect(s.twin).toBeNull() // this early record validated a different random arm, not the AI arm's own twin; nothing is faked
  })
  it('a record with the AI arm\'s own twin validated shows it as the twin', () => {
    const t = validationTriplet(liveNotVerified)
    expect(t.ai?.arm_id).toBe('ai:P1')
    expect(t.twin).toBeNull()
    const rec = { ...liveHypothetical, selection: { ...liveHypothetical.selection!, matched_twin: 'random:P1' } }
    expect(validationTriplet(rec).twin?.arm_id).toBe('random:P1')
    expect(validationTriplet(rec).baseline).toBeNull() // the baseline IS the twin, so it is not shown twice
  })
  it('falls back to the random arm of the same proposal when it was validated', () => {
    expect(validationTriplet(liveHypothetical).twin?.arm_id).toBe('random:P1')
    expect(validationTriplet(liveHypothetical).baseline).toBeNull()
  })
  it('a failed model step is an honest failure step with no hypotheses, proposals or verdicts', () => {
    const f = buildTimeline(modelFailedVariant)
    expect(isModelFailed(modelFailedVariant)).toBe(true)
    const last = f[f.length - 1]
    if (last.kind !== 'failure') throw new Error('x')
    expect(last.message).toMatch(/HTTP 429/)
    expect(f.some((s) => ['hypotheses', 'proposals', 'validation'].includes(s.kind))).toBe(false)
  })
  it('validation scores come from the per-seed results of the arm', () => {
    const o = armScores(liveVerified, 'original')
    expect(o).toHaveLength(12)
    expect(o[0].seed).toBe(285592)
    expect(armScores(liveVerified, 'ai:P1')[0]).toEqual({ seed: 285592, score: 16.875 })
    expect(armScores(liveVerified, 'nope')).toEqual([])
    expect(armScores(liveVerified, 'ai:P1', 'screening')).toHaveLength(6)
  })
  it('the budget line is the record numbers', () => {
    expect(budgetLine(liveVerified.budget)).toBe('1,208 physics rollouts, 163 s, 1 model call, 5,760 tokens, $0.0020')
    expect(budgetLine(undefined)).toMatch(/No budget/)
  })
  it('stand records have the same shape', () => {
    const t = buildTimeline(liveStand)
    expect(t.map((s) => s.kind)).toContain('validation')
    const v = t.find((s) => s.kind === 'validation')
    if (!v || v.kind !== 'validation') throw new Error('x')
    expect(v.ai?.text).toMatch(/^Not verified on/)
    expect(v.ai?.text).toMatch(/edian paired difference .* s[;.]/)
  })
})

describe('diagnostic probes (shape from creature_forge/probes.py; no live record with probes exists yet, so this fixture is test-only)', () => {
  const probes = {
    requested: [{ probe_id: 'foot_x1_5', hypothesis: 'H1', expect: 'increase' }, { probe_id: 'friction_x2', hypothesis: 'H2', expect: 'increase' }, { probe_id: 'no_push', hypothesis: 'H1', expect: 'no_change' }],
    seeds: [1, 2, 3, 4], resolution: 0.625, rollouts: 120, original: { median: 10 },
    results: {
      foot_x1_5: { probe_id: 'foot_x1_5', transformation: 'foot_length x1.5 (both feet)', status: 'ok', median: 14, median_delta: 4.4, n_seeds: 4, wins: 4, losses: 0, ties: 0 },
      friction_x2: { probe_id: 'friction_x2', transformation: 'foot_friction x2', status: 'ok', median: 10, median_delta: 0, n_seeds: 4, wins: 0, losses: 0, ties: 4 },
      no_push: { probe_id: 'no_push', transformation: 'push challenge run without a push', status: 'ok', median: 8, n_seeds: 4, static_fall_frac: 0 },
    },
    expectations: [
      { probe_id: 'foot_x1_5', hypothesis: 'H1', expect: 'increase', observed: 'increase', confirmed: true },
      { probe_id: 'friction_x2', hypothesis: 'H2', expect: 'increase', observed: 'no_change', confirmed: false },
      { probe_id: 'no_push', hypothesis: 'H1', expect: 'no_change', observed: null, confirmed: null },
    ],
  }
  it('lists what was changed, expected vs observed and CONFIRMED / REFUTED, with the median change', () => {
    const rows = probeRows(probes, 'push')
    expect(rows.map((r) => [r.probe_id, r.verdict])).toEqual([['foot_x1_5', 'CONFIRMED'], ['friction_x2', 'REFUTED'], ['no_push', 'NOT EVALUATED']])
    expect(rows[0].transformation).toBe('foot_length x1.5 (both feet)')
    expect(rows[0].detail).toBe('Median change +4.40 N over 4 probe seeds (4 better / 0 worse / 0 tied).')
    expect(rows[1].observed).toBe('no_change')
    expect(rows[2].detail).toMatch(/Measurement only, no comparison: median survival 8 s; fell without a push in 0% of seeds/)
  })
  it('never calls an errored probe confirmed', () => {
    const rows = probeRows({ requested: [{ probe_id: 'x', expect: 'increase' }], results: { x: { probe_id: 'x', status: 'error', error: 'boom' } } }, 'push')
    expect(rows[0].verdict).toBe('NOT EVALUATED')
    expect(rows[0].detail).toBe('The probe could not run: boom.')
  })
  it('is absent when the record has no probes, and appears in the timeline before hypotheses when present', () => {
    expect(probeRows(null)).toEqual([])
    expect(buildTimeline(liveVerified).some((s) => s.kind === 'probes')).toBe(false)
    const kinds = buildTimeline({ ...liveVerified, probes }).map((s) => s.kind)
    expect(kinds.indexOf('probes')).toBeGreaterThan(kinds.indexOf('model_call'))
    expect(kinds.indexOf('probes')).toBeLessThan(kinds.indexOf('hypotheses'))
  })
  it('a skipped probe protocol says why', () => {
    const t = buildTimeline({ ...liveVerified, probes: { requested: [], skipped: 'only 1 model request(s) available; the probe protocol needs 2' } }).find((s) => s.kind === 'probes')
    if (!t || t.kind !== 'probes') throw new Error('x')
    expect(t.skipped).toMatch(/needs 2/)
  })
})

describe('live progress stages', () => {
  it('marks stages done / active / pending from the events', () => {
    const events = [ev(1, 'phase', { phase: 'evidence' }), ev(2, 'model_request'), ev(3, 'model_response'), ev(4, 'phase', { phase: 'arms' })]
    expect(stageStates(events)).toEqual({ evidence: 'done', model: 'done', arms: 'active', screen: 'pending', validate: 'pending', verdict: 'pending' })
    expect(stageStates([])).toMatchObject({ evidence: 'pending' })
    expect(stageStates([...events, ev(5, 'phase', { phase: 'screen' }), ev(6, 'phase', { phase: 'validate' }), ev(7, 'verdict', { arm_id: 'x' })]).verdict).toBe('active')
  })
  it('shows the model response as soon as its event arrives', () => {
    const events = [ev(1, 'model_response', { request_id: 'req-9', ok: true, finish_reason: 'stop', latency_s: 2.5, usage: { total_tokens: 100 }, model: 'm' })]
    expect(modelResponseOf(events)).toMatchObject({ model: 'm', request_id: 'req-9', latency_s: 2.5, finish_reason: 'stop' })
    expect(modelResponseOf([])).toBeNull()
  })
})

describe('loop results', () => {
  const loop: LoopResult = {
    loop_id: 'l-1', mode: 'live', provenance: 'LIVE', stop_reason: 'no_verified_arm', auto_accepted: false, best: null, budget: { rollouts: 1, calls: 1, wall_s: 1 },
    rounds: [
      { round: 1, investigation_id: 'i-1', status: 'done', run_id: 'r-1', hypothetical_parent: null, best_verified_arm: null, best_verdict: null },
      { round: 2, investigation_id: 'i-2', status: 'done', run_id: 'r-1', hypothetical_parent: null, best_verified_arm: 'ai:P1', best_verdict: null },
      { round: 3, investigation_id: 'i-3', status: 'model_failed', run_id: 'r-2', hypothetical_parent: { investigation_id: 'i-2' }, best_verified_arm: null, best_verdict: null },
    ],
  }
  it('lists each round, the stop reason, and states that nothing was accepted for the user', () => {
    const lines = loopLines(loop)
    expect(lines[0]).toBe('Round 1: no verified change')
    expect(lines[1]).toBe('Round 2: verified change ai:P1')
    expect(lines[2]).toMatch(/Round 3: The model step failed \(on an unaccepted earlier proposal\)/)
    expect(lines[3]).toMatch(/two rounds in a row/)
    expect(lines[4]).toMatch(/Nothing was accepted for you/)
  })
  it('stop reasons', () => {
    expect(stopText('round_status:failed')).toBe('Stopped: a round ended as "failed".')
    expect(stopText('max_rounds')).toMatch(/round limit/)
  })
})

describe('investigation list', () => {
  const list = [
    { id: 'i-a', created: '2026-10-15T10:00:00Z', mode: 'live', provenance: 'LIVE', creature: { cid: 'c', n: 1 }, challenge_run_id: 'r', status: 'done', n_arms: 6, verdicts: { 'ai:P1': 'VERIFIED_IMPROVEMENT' } },
    { id: 'i-b', created: '2026-10-15T11:00:00Z', mode: 'scripted', provenance: 'SCRIPTED_MOCK', creature: { cid: 'c', n: 1 }, challenge_run_id: 'r', status: 'model_failed', n_arms: 1, verdicts: {} },
  ] as InvestigationSummary[]
  it('sorts newest first and labels provenance and status', () => {
    expect(newestFirst(list).map((s) => s.id)).toEqual(['i-b', 'i-a'])
    expect(summaryChips(list[1]).map((c) => c.label)).toEqual(['SCRIPTED MOCK', 'The model step failed'])
    expect(summaryChips(list[0]).map((c) => c.label)).toEqual(['LIVE', 'Completed', 'VERIFIED CHANGE'])
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
