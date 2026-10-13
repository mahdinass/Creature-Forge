import { describe, expect, it } from 'vitest'
import {
  changeRows, directionWord, filterRows, fmtDelta, fmtForensic, fmtMetric, formatWhen, metricLabel, parseDeepLink,
  fmtSeeds, pct, predictionVerdict, screeningText, statusInfo, stepState, STEPS,
} from './labLogic'
import type { LabRow, LabView } from './labTypes'

const row = (status: string, id = status): LabRow => ({ trial_id: id, status, created_utc: null, source: 'bundled-demo', readable: true })

const view = (over: Partial<LabView> = {}): LabView =>
  ({
    trial_id: 't', variant: 'forensic', source: 'bundled-demo', missing: [],
    sections: { observe: true, hypothesis: true, intervene: true, verify: true, compare: true },
    outcome: { status: 'rejected_by_verifier' }, ...over,
  }) as LabView

describe('statusInfo', () => {
  it('never presents a rejected or invalid trial as a success', () => {
    expect(statusInfo('rejected_by_verifier').tone).toBe('bad')
    expect(statusInfo('invalid_model_output').tone).toBe('warn')
    expect(statusInfo('invalid_model_output').summary).toMatch(/never tested/)
    expect(statusInfo('accepted').tone).toBe('ok')
  })
  it('handles unknown statuses without throwing', () => {
    expect(statusInfo('something_new').label).toBe('something_new')
    expect(statusInfo('something_new').tone).toBe('muted')
  })
})

describe('stepState', () => {
  it('is ready when the section exists', () => {
    for (const s of STEPS) expect(stepState(view(), s).ready).toBe(true)
  })
  it('explains why an invalid response has no hypothesis, change, verdict or comparison', () => {
    const v = view({
      outcome: { status: 'invalid_model_output' },
      sections: { observe: true, hypothesis: false, intervene: false, verify: false, compare: false },
    })
    expect(stepState(v, 'observe').ready).toBe(true)
    for (const s of ['hypothesize', 'intervene', 'verify', 'compare'] as const) {
      const st = stepState(v, s)
      expect(st.ready).toBe(false)
      expect(st.reason).toBeTruthy()
    }
    expect(stepState(v, 'hypothesize').reason).toMatch(/invalid/)
  })
})

describe('parseDeepLink', () => {
  it('reads trial and step and ignores unknown steps', () => {
    expect(parseDeepLink('?tab=lab&trial=abc&step=verify')).toEqual({ trial: 'abc', step: 'verify' })
    expect(parseDeepLink('?step=nonsense')).toEqual({ trial: null, step: null })
    expect(parseDeepLink('')).toEqual({ trial: null, step: null })
  })
})

describe('formatting', () => {
  it('formats percentages, deltas and units', () => {
    expect(pct(1)).toBe('100%')
    expect(pct(0.9)).toBe('90%')
    expect(pct(null)).toBe('—')
    expect(fmtDelta(0.0123)).toBe('+0.012')
    expect(fmtDelta(-0.5, 1)).toBe('-0.5')
    expect(fmtMetric('fall_rate', 0.2)).toBe('20%')
    expect(fmtMetric('mean_min_torso_height', 0.1054)).toBe('0.105 m')
    expect(fmtMetric('mean_max_abs_pitch', Math.PI / 2)).toBe('90.0°')
  })
  it('shows a never-recovered balance honestly', () => {
    expect(fmtForensic('xcom_margin_recovered_s', null)).toBe('never')
    expect(fmtForensic('fall_time_s', 1.846)).toBe('1.846')
  })
  it('survives missing or bad timestamps', () => {
    expect(formatWhen(null)).toBe('unknown time')
    expect(formatWhen('not a date')).toBe('unknown time')
    expect(formatWhen('2026-10-13T01:03:25+00:00')).toBe('2026-10-13 01:03 UTC')
  })
  it('words predictions plainly', () => {
    expect(directionWord('decrease')).toBe('go down')
    expect(metricLabel('fall_rate')).toBe('fall rate')
    expect(predictionVerdict(false)).toEqual({ text: 'did not hold', tone: 'bad' })
    expect(predictionVerdict(null).tone).toBe('muted')
  })
})

describe('changeRows', () => {
  it('flags exactly the parameters that differ', () => {
    const rows = changeRows({ a: 1, b: 2, c: 3 }, { a: 1, b: 9, c: 3 })
    expect(rows.filter((r) => r.changed).map((r) => r.name)).toEqual(['b'])
    expect(rows).toHaveLength(3)
  })
})

describe('filterRows', () => {
  const rows = [row('accepted'), row('rejected_by_verifier', 'r1'), row('invalid_model_output'), row('model_error'), row('unreadable')]
  it('filters by outcome class and keeps failures visible under "all"', () => {
    expect(filterRows(rows, 'all')).toHaveLength(5)
    expect(filterRows(rows, 'accepted').map((r) => r.status)).toEqual(['accepted'])
    expect(filterRows(rows, 'rejected').map((r) => r.trial_id)).toEqual(['r1'])
    expect(filterRows(rows, 'invalid').map((r) => r.status)).toEqual(['invalid_model_output', 'model_error', 'unreadable'])
  })
})

describe('screeningText (seed roles come from the saved record)', () => {
  it('distinguishes evidence seeds 0-2 from screening seeds 0-4 without claiming they are the same', () => {
    const t = screeningText([0, 1, 2], [0, 1, 2, 3, 4])
    expect(t.title).toBe('Screening: seeds 0–4')
    expect(t.count).toBe('5 screening seeds')
    expect(t.note).toContain('evidence came from seeds 0–2')
    expect(t.note).toContain('re-uses all of them')
    expect(t.note).toContain('adds seeds 3, 4')
    expect(t.note).not.toMatch(/same seeds/)
  })
  it('says "the same seeds" only when the sets are identical', () => {
    expect(screeningText([3, 1, 2], [1, 2, 3]).note).toMatch(/^The same seeds \(1–3\)/)
  })
  it('adapts to other seed sets, partial overlap and no overlap', () => {
    expect(screeningText([0, 1], [1, 7, 9]).note).toBe('The evidence came from seeds 0, 1; screening re-uses seeds 1 and adds seeds 7, 9.')
    expect(screeningText([0, 1, 2], [10, 11, 12, 13]).note).toBe('None of these overlap the evidence seeds (0–2).')
    expect(screeningText([0], [100]).count).toBe('1 screening seed')
  })
  it('stays honest when seed metadata is missing', () => {
    expect(screeningText([0, 1, 2], null).note).toMatch(/does not list/)
    expect(screeningText(null, [0, 1]).note).toMatch(/evidence seeds were not recorded/)
  })
  it('formats seed lists', () => {
    expect(fmtSeeds([0, 1, 2, 3, 4])).toBe('0–4')
    expect(fmtSeeds([4, 0, 2])).toBe('0, 2, 4')
    expect(fmtSeeds([5, 6])).toBe('5, 6')
  })
})
