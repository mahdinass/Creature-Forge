import { describe, expect, it } from 'vitest'
import {
  diagnosisVerdict, directionWord, fmtCost, fmtDelta, fmtNum, hypothesisAt, hypothesisTone, ledgerAt, linkifyIds, memoryUse, memoryVerdictInfo,
  predictionRows, repairLine, scoreTally, selfClaim, statusCounts, statusInfo, stepExperiments, stepTitle, walkingChange,
} from './causalLogic'
import type { CausalRecord, Experiment, Hypothesis, Step } from './causalTypes'

const hyp = (id: string, created: number, hist: [number, string, string?, string[]?][]): Hypothesis => ({
  id, mechanism: `m-${id}`, causal_chain: `c-${id}`, category: 'posture_bias', evidence: [], status: hist[hist.length - 1][1], confidence: 0.5, created_step: created,
  history: hist.map(([step, status, reason, experiments]) => ({ step, status, confidence: 0.5, reason: reason ?? 'created', experiments: experiments ?? [] })),
})

// H1 is created at step 1, supported at step 2, supported again at step 3; H2 is created at step 1 and refuted at step 2; H3 appears at step 3.
const ledger = {
  H1: hyp('H1', 1, [[1, 'open'], [2, 'supported', 'E1 matched', ['E1']], [3, 'supported', 'R1 walked', ['R1']]]),
  H2: hyp('H2', 1, [[1, 'open'], [2, 'refuted', 'E1 contradicted', ['E1']]]),
  H10: hyp('H10', 3, [[3, 'open']]),
}

const cf: Experiment = {
  id: 'E1', kind: 'counterfactual', step: 1, change: 'balance_gain@x1.5', cost: 4,
  predictions: [
    { hypothesis: 'H1', quantity: 'n_fell', direction: 'decrease' },
    { hypothesis: 'H1', quantity: 'pitch_mean', direction: 'decrease' },
    { hypothesis: 'H2', quantity: 'step_freq_hz', direction: 'no_change' },
  ],
  scoring: [
    { hypothesis: 'H1', quantity: 'n_fell', predicted: 'decrease', observed: 'decrease', status: 'correct', base: 4, new: 3, delta: -1, tolerance: 0 },
    { hypothesis: 'H2', quantity: 'step_freq_hz', predicted: 'no_change', observed: 'increase', status: 'incorrect', base: 3.8, new: 4.4, delta: 0.6, tolerance: 0.2 },
  ],
  outcome: { n_walking: 1, n_walking_base: 0, n_fell: 3, n_fell_base: 4 },
}
const rep: Experiment = { id: 'R1', kind: 'repair', step: 2, tool: 'posture', hypothesis: 'H1', budget: 207, budget_share: 0.3, n_train: 4, start_walking: 0, train_walking: 4, rollouts_used: 196 }

const rec = {
  steps: [
    { step: 1, action: 'counterfactual', experiments: ['E1'], parsed: { result_reading: 'See M1 and M10.' } },
    { step: 2, action: 'repair', experiments: ['R1'], parsed: { result_reading: 'Later, M1 again.', memory_assessments: [{ item: 'M1', verdict: 'applies', reason: 'same shape' }] } },
    { step: 3, action: 'conclude', status: 'ok' },
  ] as Step[],
  experiments: [cf, rep, { id: 'O0', kind: 'observe', cost: 4, step: 0 }],
  hypotheses: ledger,
  memory: {
    items: [{ id: 'M1', kind: 'episode', text: 'earlier robot' }, { id: 'M10', kind: 'card', text: 'a card' }, { id: 'M2', kind: 'card', text: 'unused' }],
    assessments: { M1: { item: 'M1', verdict: 'applies', reason: 'same shape', step: 1 }, M10: { item: 'M10', verdict: 'test_first', reason: 'unclear', step: 1 } },
  },
} as unknown as CausalRecord

describe('hypothesisAt', () => {
  it('is null before the hypothesis exists and follows the history afterwards', () => {
    expect(hypothesisAt(ledger.H10, 2)).toBeNull()
    expect(hypothesisAt(ledger.H1, 0)).toBeNull()
    expect(hypothesisAt(ledger.H1, 1)?.status).toBe('open')
    expect(hypothesisAt(ledger.H1, 2)?.status).toBe('supported')
    expect(hypothesisAt(ledger.H1, 2)?.experiments).toEqual(['E1'])
    expect(hypothesisAt(ledger.H1, 3)?.reason).toBe('R1 walked')
    expect(hypothesisAt(ledger.H1, 99)?.status).toBe('supported')
  })
  it('records the path of distinct statuses and when it last changed', () => {
    const s = hypothesisAt(ledger.H1, 3)!
    expect(s.path).toEqual(['open', 'supported'])
    expect(s.changedAt).toBe(3)
    expect(hypothesisAt(ledger.H2, 2)!.path).toEqual(['open', 'refuted'])
  })
})

describe('ledgerAt', () => {
  it('lists only hypotheses that exist at the step, ordered by numeric id', () => {
    expect(ledgerAt(ledger, 1).map((h) => h.id)).toEqual(['H1', 'H2'])
    expect(ledgerAt(ledger, 3).map((h) => h.id)).toEqual(['H1', 'H2', 'H10'])
  })
  it('counts statuses at a step', () => {
    expect(statusCounts(ledgerAt(ledger, 1))).toEqual({ open: 2 })
    expect(statusCounts(ledgerAt(ledger, 2))).toEqual({ supported: 1, refuted: 1 })
  })
  it('does not mutate the record', () => {
    const before = JSON.stringify(ledger)
    ledgerAt(ledger, 2)
    expect(JSON.stringify(ledger)).toBe(before)
  })
})

describe('experiments and predictions', () => {
  it('finds the experiments of a step', () => {
    expect(stepExperiments(rec, rec.steps[0]).map((e) => e.id)).toEqual(['E1'])
    expect(stepExperiments(rec, rec.steps[1]).map((e) => e.id)).toEqual(['R1'])
    expect(stepExperiments(rec, rec.steps[2])).toEqual([])
  })
  it('joins each pre-registered prediction to its score, and shows an unscored one as such', () => {
    const rows = predictionRows(cf)
    expect(rows).toHaveLength(3)
    expect(rows[0].score?.status).toBe('correct')
    expect(rows[1].score).toBeNull()
    expect(rows[2].score?.status).toBe('incorrect')
  })
  it('tallies correct, incorrect and unscored', () => {
    expect(scoreTally(cf.scoring)).toEqual({ correct: 1, incorrect: 1, unscored: 0, total: 2 })
    expect(scoreTally(undefined).total).toBe(0)
  })
  it('reads walking before and after for counterfactuals and repairs', () => {
    expect(walkingChange(cf)).toEqual({ before: 0, after: 1, of: 4 })
    expect(walkingChange(rep)).toEqual({ before: 0, after: 4, of: 4 })
    expect(walkingChange({ id: 'O0', kind: 'observe' })).toBeNull()
  })
  it('describes a repair from the record fields only', () => {
    expect(repairLine(rep)).toBe('tool posture, directed by H1, budget 207 rollouts (30% of the total), 196 used')
  })
})

describe('memory', () => {
  it('pairs items with verdicts and the steps whose model text names them (whole ids only)', () => {
    const use = memoryUse(rec)
    expect(use.map((u) => u.item.id)).toEqual(['M1', 'M10', 'M2'])
    expect(use[0].verdict).toBe('applies')
    expect(use[0].citedInSteps).toEqual([1, 2])
    expect(use[1].citedInSteps).toEqual([1])
    expect(use[2].verdict).toBeNull()
    expect(use[2].citedInSteps).toEqual([])
  })
  it('linkifies ids as whole tokens, longest first', () => {
    expect(linkifyIds('see M10, M1 and XM1.', ['M1', 'M10'])).toEqual([
      { text: 'see ' }, { text: 'M10', item: 'M10' }, { text: ', ' }, { text: 'M1', item: 'M1' }, { text: ' and XM1.' },
    ])
    expect(linkifyIds('plain', [])).toEqual([{ text: 'plain' }])
    expect(linkifyIds('', ['M1'])).toEqual([])
    expect(linkifyIds('a.b (a+b)', ['a+b'])).toEqual([{ text: 'a.b (' }, { text: 'a+b', item: 'a+b' }, { text: ')' }])
  })
  it('words the four verdicts', () => {
    expect(memoryVerdictInfo('does_not_apply').label).toBe('does not apply')
    expect(memoryVerdictInfo('applies').tone).toBe('ok')
    expect(memoryVerdictInfo('whatever').label).toBe('whatever')
  })
})

describe('wording', () => {
  it('never shows a failure as a success', () => {
    expect(statusInfo('NOT_RECOVERED').tone).toBe('bad')
    expect(statusInfo('PARTIAL_IMPROVEMENT').tone).toBe('warn')
    expect(statusInfo('FULL_RECOVERY').tone).toBe('ok')
    expect(statusInfo(null).label).toBe('No verdict')
    expect(statusInfo('NEW_THING').tone).toBe('muted')
  })
  it('formats numbers and directions', () => {
    expect(directionWord('no_change')).toBe('no change')
    expect(directionWord(null)).toBe('not defined')
    expect(fmtCost(0.0182643)).toBe('$0.018')
    expect(fmtCost(1.2345)).toBe('$1.23')
    expect(fmtCost(null)).toBe('n/a')
    expect(fmtDelta(-1)).toBe('-1')
    expect(fmtDelta(0.034)).toBe('+0.034')
    expect(fmtNum(0.00001234)).toBe('1.23e-5')
    expect(hypothesisTone('refuted')).toBe('bad')
    expect(stepTitle({ step: 4, action: 'conclude' })).toBe('Step 4: concluded')
    expect(stepTitle({ step: 4, action: null, status: 'invalid_after_repair' })).toMatch(/could not be used/)
  })
  it('states the evaluation-only diagnosis match without overclaiming', () => {
    const ev = (m: boolean | null, c: string | null) => ({ note: '', fault: 'f', severity: 1, matching_tool: 't', injected_category: 'x', diagnosis_category: c, diagnosis_match: m })
    expect(diagnosisVerdict(ev(true, 'x'))).toMatch(/named the injected/)
    expect(diagnosisVerdict(ev(false, 'unresolved'))).toMatch(/did not name/)
    expect(diagnosisVerdict(ev(false, 'y'))).toMatch(/different/)
    expect(diagnosisVerdict(ev(null, null))).toMatch(/no diagnosis/)
  })
  it('summarises the AI own training-seed claims separately', () => {
    expect(selfClaim(rec)).toEqual({ repairs: 1, trainWalking: [{ tool: 'posture', before: 0, after: 4, of: 4 }] })
  })
})
