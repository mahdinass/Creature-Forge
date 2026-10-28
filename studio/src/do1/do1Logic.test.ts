import { describe, expect, it } from 'vitest'
import indexText from '../../../experiments/do1/demo/index.json?raw'
import recordText from '../../../experiments/do1/l4_r0/do1_l4_r0.jsonl?raw'
import { aggregateOf, cards, checkText, median, outcomeText, requiredWalking, rowFor, seedOptionText, whyNotFull } from './do1Logic'
import type { Do1Index, Do1Verification } from './do1Types'

// The committed, verified export; the verification block mirrors what /api/do1/index adds from the audited record.
const exported = JSON.parse(indexText)
const record = recordText.trim().split('\n').map((l: string) => JSON.parse(l))
const verification = (arm: string): Do1Verification => {
  const f = record.find((r: { harness: { do1: { arm: string } } }) => r.harness.do1.arm === arm).verification.full
  return { rule: f.rule, status: f.status, reasons: f.reasons, aggregate: f.validation.aggregate, walking_frac: f.validation.walking_frac,
    verdict: f.validation.verdict, verdict_reasons: f.validation.verdict.reasons, confirmation: f.confirmation }
}
const idx: Do1Index = { ...exported, verification: { frozen: verification('frozen'), do1: verification('do1') },
  criteria: { rule: 'full_recovery_v1', pass_frac: 0.8 } }

describe('DO-1 recovery logic on the verified export', () => {
  it('recomputes the aggregates from the per-seed rows', () => {
    expect(aggregateOf(idx, 'faulty').walking).toBe(5)
    expect(aggregateOf(idx, 'frozen').walking).toBe(19)
    expect(aggregateOf(idx, 'do1').walking).toBe(21)
    expect(aggregateOf(idx, 'do1_confirm').walking).toBe(22)
    expect(aggregateOf(idx, 'frozen').median).toBeCloseTo(3.429721, 6)
  })

  it('refuses rows that disagree with the exported aggregates', () => {
    const bad = structuredClone(idx)
    bad.rows.frozen[0].walking = !bad.rows.frozen[0].walking
    expect(() => aggregateOf(bad, 'frozen')).toThrow(/disagree/)
  })

  it('builds the three cards from the recorded verifier outcome', () => {
    const [f, z, d] = cards(idx)
    expect([f.status, z.status, d.status]).toEqual([null, 'PARTIAL_IMPROVEMENT', 'FULL_RECOVERY'])
    expect([z.tone, d.tone]).toEqual(['warn', 'ok'])
    expect(z.gain).toMatchObject({ wins: 20, losses: 1, ties: 3, status: 'VERIFIED_IMPROVEMENT' })
    expect(d.gain?.median).toBeCloseTo(0.710007, 6)
    expect(z.confirmation).toMatchObject({ run: false, walking: null })
    expect(d.confirmation).toMatchObject({ run: true, walking: 22, n: 24, passed: true })
  })

  it('explains why the longer frozen walk is not FULL', () => {
    const w = whyNotFull(idx)
    expect(w.needWalking).toBe(20)
    expect(w.frozenWalking).toBeLessThan(w.needWalking)
    expect(w.do1Walking).toBeGreaterThanOrEqual(w.needWalking)
    expect(w.frozenAhead).toBeGreaterThan(0)
    expect(w.frozenAggregate).toBe('POOR')
    expect(w.frozenConfirmationRan).toBe(false)
    expect(w.do1Checks.map((c) => c.passed)).toEqual([true, true, true])
    expect(w.do1Checks.map(checkText)).toEqual([
      '92% of seeds walked the full 20 s (needs ≥ 80%) ✓', 'median upright speed 0.324 m/s (needs ≥ 0.233) ✓', 'no seed dragged its body on the floor ✓'])
  })

  it('labels seeds from their own rows and marks the pre-declared seed', () => {
    const s = idx.default_seed
    expect(rowFor(idx, 'frozen', s).walking).toBe(false)
    expect(rowFor(idx, 'do1', s).walking).toBe(true)
    expect(seedOptionText(idx, s)).toMatch(/frozen ✗ · DO-1 ✓ · illustrative$/)
    expect(seedOptionText(idx, idx.seeds.validate[0])).not.toMatch(/illustrative/)
    expect(() => rowFor(idx, 'do1', 1)).toThrow()
  })

  it('pure helpers', () => {
    expect(median([3, 1, 2])).toBe(2)
    expect(median([4, 1, 2, 3])).toBe(2.5)
    expect(requiredWalking(0.8, 24)).toBe(20)
    expect(requiredWalking(0.8, 25)).toBe(20)
    expect(outcomeText({ ...idx.rows.faulty[0], label: 'fall', fell: true, fall_time: 1.234 })).toBe('fell at 1.23 s')
  })
})
