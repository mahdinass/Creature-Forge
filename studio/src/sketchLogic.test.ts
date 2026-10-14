import { describe, expect, it } from 'vitest'
import { errorNodes, GROUND_Z, handleFromMass, massFromHandle, nodesEqual, PRESETS, sketchFromLengths, snapDrag } from './sketchLogic'

describe('sketch geometry helpers', () => {
  it('builds the same default skeleton as the backend (ankle on the ground, toe at 0.75 of the foot)', () => {
    const s = sketchFromLengths(0.3, 0.3, 0.16)
    expect(s.nodes.ankle).toEqual([0, GROUND_Z])
    expect(s.nodes.knee[1]).toBeCloseTo(0.34)
    expect(s.nodes.hip[1]).toBeCloseTo(0.64)
    expect(s.nodes.toe[0]).toBeCloseTo(0.12)
  })
  it('every preset stays inside the physical bounds', () => {
    for (const p of PRESETS) for (const l of p.lengths.slice(0, 2)) expect(l).toBeGreaterThanOrEqual(0.15)
  })
})

describe('magnetic snapping', () => {
  const n = sketchFromLengths(0.3, 0.3, 0.16).nodes
  it('snaps a knee that is almost over the ankle onto the vertical, and says so', () => {
    const r = snapDrag('knee', [0.02, 0.4], n)
    expect(r.point[0]).toBe(0)
    expect(r.snaps).toContain('vertical')
  })
  it('does not snap when far away: the soft constraint leaves the drag alone', () => {
    const r = snapDrag('knee', [0.2, 0.4], n)
    expect(r.point).toEqual([0.2, 0.4])
    expect(r.snaps).toEqual([])
  })
  it('snaps the ankle to the ground and the toe to ankle height, and keeps the toe in front', () => {
    expect(snapDrag('ankle', [0, 0.06], n).point[1]).toBe(GROUND_Z)
    expect(snapDrag('toe', [0.1, GROUND_Z + 0.015], n).point[1]).toBe(GROUND_Z)
    expect(snapDrag('toe', [-0.3, GROUND_Z], n).point[0]).toBeCloseTo(0.02)
  })
})

describe('torso mass handle', () => {
  it('maps handle height to mass within [1, 15] kg and back', () => {
    expect(massFromHandle(0.64, 0.64)).toBe(1)
    expect(massFromHandle(0.94, 0.64)).toBe(15)
    expect(massFromHandle(5, 0.64)).toBe(15)
    expect(massFromHandle(0.79, 0.64)).toBe(8)
    expect(massFromHandle(handleFromMass(5, 0.64), 0.64)).toBe(5)
  })
})

describe('error highlighting', () => {
  it('finds the nodes an error is about', () => {
    expect(errorNodes(['The knee is 0.30 m sideways of the ankle.', 'something else'])).toEqual(['knee', 'ankle'])
    expect(errorNodes(['kneeling is fine'])).toEqual([])
  })
  it('compares node sets with a tolerance', () => {
    const a = sketchFromLengths(0.3, 0.3, 0.16).nodes
    expect(nodesEqual(a, { ...a, knee: [1e-9, a.knee[1]] })).toBe(true)
    expect(nodesEqual(a, { ...a, knee: [0.1, a.knee[1]] })).toBe(false)
  })
})
