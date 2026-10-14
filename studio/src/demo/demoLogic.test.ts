import { describe, expect, it } from 'vitest'
import { apiId, bar, describeEdit, honestHeadline, KIND_INFO, lookupPath, predictionText, replayOptions, statusMessage, verdictText } from './demoLogic'
import type { DemoRun, VResult } from './demoTypes'

const vres = (walking: number, n = 4, verdict?: VResult['verdict']): VResult => ({
  walking_count: walking, survival_count: walking, n, labels: {}, walking_by_seed: Array.from({ length: n }, (_, i) => i < walking), verdict,
})

function run(over: Partial<DemoRun> = {}): DemoRun {
  const base = {
    id: 'stem-r1', run_id: 'r1', created_utc: '2026-10-14T00:00:00+00:00',
    provenance: { kind: 'RECORDED_LIVE', model: 'm', request_id: 'x', prompt_sha256: 'h', setting: { reasoning_effort: 'low', max_tokens: 8000 }, usage: null, note: '' },
    controller: { name: 'c', vector: [], params: {} },
    observed: { failing_seed: 9101, walking_seed: 9100, metrics: {}, failing_seed_walked: false },
    context: { controller: { kp: { u: 0.5 } }, failing_seeds: [{ fall_time: 1.5 }] }, prompt: { system: '', user: '', sha256: 'h' },
    model_reply: { status: 'ok', reason: null, raw_reply: '{}', call: null, temperature: 0.7, slots: [] },
    interventions: [], verification: null, limits: ['x'], elapsed_s: 1,
  }
  return { ...base, ...over } as unknown as DemoRun
}

const withProposal = (): DemoRun => run({
  interventions: [{
    slot: 0, vector: [], realised: [{ parameter: 'kp', requested_delta_u: 0.1, realised_delta_u: 0.1, reflected: false }],
    proposal: { claim: 'c', cited_evidence: ['controller.kp.u'], edits: [{ parameter: 'kp', delta_u: 0.1 }], prediction: { metric: 'm', direction: 'increase', min_gain_seeds: 2 }, confidence: 0.5 },
    matched_random: { edits: [{ parameter: 'kd', delta_u: -0.1 }], realised: [], vector: [] },
  }],
  verification: { seeds: [1, 2, 3, 4], rules: 'x', rollouts: 20, rule: 'r', results: {
    theta0: vres(2), slot0: vres(3, 4, { gain_seeds: 1, kind: 'no_clear_change', prediction_met: false }), slot0_random: vres(4, 4, { gain_seeds: 2, kind: 'improved' }),
  } } as unknown as DemoRun['verification'],
})

describe('provenance labels', () => {
  it('distinguishes live, recorded and scripted runs, and calls the mock "not a model"', () => {
    expect(Object.keys(KIND_INFO).sort()).toEqual(['LIVE', 'RECORDED_LIVE', 'SCRIPTED_MOCK'])
    expect(KIND_INFO.SCRIPTED_MOCK.label).toMatch(/not a model/)
    expect(KIND_INFO.SCRIPTED_MOCK.tone).toBe('warn')
    expect(KIND_INFO.RECORDED_LIVE.text).toMatch(/Nothing is re-sent/)
    expect(KIND_INFO.LIVE.label).not.toBe(KIND_INFO.RECORDED_LIVE.label)
  })
})

describe('verdicts are measured only', () => {
  it('maps verdict kinds', () => {
    expect(verdictText({ gain_seeds: 3, kind: 'improved' })).toEqual({ text: 'improved by 3 seeds', tone: 'ok' })
    expect(verdictText({ gain_seeds: -3, kind: 'worse' })).toEqual({ text: 'worse by 3 seeds', tone: 'bad' })
    expect(verdictText({ gain_seeds: 1, kind: 'no_clear_change' }).text).toBe('no clear change (+1)')
    expect(verdictText(undefined).text).toBe('not verified')
  })
  it('reports prediction hits and misses without softening', () => {
    expect(predictionText({ gain_seeds: 3, kind: 'improved', prediction_met: true }, 2)).toMatch(/met$/)
    expect(predictionText({ gain_seeds: 1, kind: 'no_clear_change', prediction_met: false }, 2)).toMatch(/not met$/)
    expect(predictionText(undefined, 2)).toBe('prediction not evaluated')
  })
  it('headline states the numbers, the random baseline and that it is one instance', () => {
    const h = honestHeadline(withProposal())
    expect(h).toContain('3/4')
    expect(h).toContain('2/4')
    expect(h).toContain('4/4 for a matched random edit')
    expect(h).toContain('One instance; not a statistical claim')
    expect(honestHeadline(run())).toMatch(/says nothing about whether any edit works/)
  })
})

describe('failure handling shows what happened', () => {
  it('describes unusable replies and never claims a result', () => {
    const bad = run({ model_reply: { status: 'invalid_response', reason: 'model returned no content (finish_reason=length)', raw_reply: null, call: null, temperature: 0.7, slots: [] } })
    expect(statusMessage(bad).tone).toBe('bad')
    expect(statusMessage(bad).text).toMatch(/Nothing was simulated or substituted/)
    expect(statusMessage(run()).tone).toBe('warn')
    expect(statusMessage(withProposal()).tone).toBe('ok')
  })
})

describe('replay identity', () => {
  it('addresses the API by the served id (file stem), never the id stored inside the record', () => {
    const r = run({ id: 'live-002-two-valid-proposals', run_id: '20261014T111733Z-live-9f5ab0' })
    expect(apiId(r)).toBe('live-002-two-valid-proposals')
    expect(apiId(r)).not.toBe(r.run_id)
  })
})

describe('helpers', () => {
  it('lists replay options only when there are proposals', () => {
    expect(replayOptions(run()).map((o) => o.id)).toEqual(['baseline'])
    expect(replayOptions(withProposal()).map((o) => o.id)).toEqual(['baseline', 'slot0', 'slot0_random'])
  })
  it('formats edits with requested and realised values', () => {
    expect(describeEdit({ parameter: 'kp', delta_u: -0.1 })).toBe('kp −0.10')
    expect(describeEdit({ parameter: 'start_lean', delta_u: -0.1 }, { parameter: 'start_lean', requested_delta_u: -0.1, realised_delta_u: 0.1, reflected: true }))
      .toMatch(/realised \+0\.10 \(reflected at a bound\)/)
  })
  it('resolves cited paths into the measured context', () => {
    const c = run().context
    expect(lookupPath(c, 'controller.kp.u')).toBe(0.5)
    expect(lookupPath(c, 'failing_seeds.0.fall_time')).toBe(1.5)
    expect(lookupPath(c, 'failing_seeds.fell')).toBeUndefined()
    expect(bar(vres(2))).toBe('■■□□')
  })
})
