import { describe, expect, it } from 'vitest'
import { curvePoints, durationForSeed, prettyLabel, seedRole, verdictText } from './locoLogic'

const roles = { train: [1000, 1001], diagnostic: [2000], heldout: [3000, 3001] }
const dur = { train: 6, diagnostic: 8, heldout: 10 }

describe('locoLogic', () => {
  it('scales a series into the plot box with y up', () => {
    const pts = curvePoints([0, 1], 100, 50, 10, 0, 1).split(' ')
    expect(pts[0]).toBe('10.0,40.0')
    expect(pts[1]).toBe('90.0,10.0')
    expect(curvePoints([], 100, 50, 10, 0, 1)).toBe('')
  })
  it('handles a flat series without dividing by zero', () => {
    expect(curvePoints([2, 2, 2], 100, 50, 10, 2, 2)).not.toContain('NaN')
  })
  it('words verdicts from the saved criteria flags only', () => {
    const base = { fraction_seeds_walking: 0.7, median_speed_upright: 0.4, body_dragging_seeds: 0 }
    expect(verdictText({ ...base, meets_walking_criteria: false, meets_partial_criteria: true }).tone).toBe('partial')
    expect(verdictText({ ...base, meets_walking_criteria: true, meets_partial_criteria: true }).tone).toBe('ok')
    expect(verdictText({ ...base, meets_walking_criteria: false, meets_partial_criteria: false }).text).toBe('does not walk')
  })
  it('labels seed roles and picks the registered duration', () => {
    expect(seedRole(3000, roles)).toBe('held-out')
    expect(seedRole(5, roles)).toBeNull()
    expect(durationForSeed(1000, roles, dur)).toBe(6)
    expect(durationForSeed(2000, roles, dur)).toBe(8)
    expect(durationForSeed(3001, roles, dur)).toBe(10)
  })
  it('prettifies labels', () => expect(prettyLabel('contact_chatter')).toBe('contact chatter'))
})
