import { describe, expect, it } from 'vitest'
import { DEFAULT_VIEW, fitView, MAX_K, MIN_K, panBy, pathD, strokeHit, thin, toWorld, viewBox, WORLD, zoomAt } from './strokes'

describe('stroke geometry', () => {
  it('thins jitter but keeps the first and last point', () => {
    const pts: [number, number][] = [[0, 0], [0.5, 0], [1, 0], [3, 0], [3.5, 0], [10, 0]]
    const t = thin(pts, 2)
    expect(t[0]).toEqual([0, 0])
    expect(t[t.length - 1]).toEqual([10, 0])
    expect(t.length).toBeLessThan(pts.length)
  })
  it('builds smooth paths, and a dot for a single tap', () => {
    expect(pathD([])).toBe('')
    expect(pathD([[5, 5]])).toContain('l0.01 0')
    expect(pathD([[0, 0], [10, 0]])).toBe('M0.0 0.0L10.0 0.0')
    expect(pathD([[0, 0], [10, 5], [20, 0]])).toContain('Q')
  })
  it('hit-tests strokes for the eraser', () => {
    const s: [number, number][] = [[0, 0], [100, 0]]
    expect(strokeHit(s, [50, 6], 8)).toBe(true)
    expect(strokeHit(s, [50, 20], 8)).toBe(false)
    expect(strokeHit([[10, 10]], [12, 10], 5)).toBe(true)
  })
})

describe('view transforms', () => {
  const rect = { left: 100, top: 50, width: 500, height: 350 }
  it('maps client pixels to world points at any zoom and pan', () => {
    expect(toWorld(DEFAULT_VIEW, rect, 100, 50)).toEqual([0, 0])
    expect(toWorld(DEFAULT_VIEW, rect, 600, 400)).toEqual([WORLD.w, WORLD.h])
    const p = toWorld({ x: 100, y: 40, k: 2 }, rect, 350, 225)
    expect(p[0]).toBeCloseTo(100 + WORLD.w / 2 / 2)
    expect(p[1]).toBeCloseTo(40 + WORLD.h / 2 / 2)
  })
  it('zooms about the cursor so the point under it does not move, within limits', () => {
    expect(zoomAt(DEFAULT_VIEW, 100, [0, 0]).k).toBe(MAX_K)
    expect(zoomAt(DEFAULT_VIEW, 0.001, [0, 0]).k).toBe(MIN_K)
    const before = toWorld(DEFAULT_VIEW, rect, 350, 225)
    const back = toWorld(zoomAt(DEFAULT_VIEW, 1.5, before), rect, 350, 225)
    expect(back[0]).toBeCloseTo(before[0])
    expect(back[1]).toBeCloseTo(before[1])
  })
  it('pans with the pointer and formats the viewBox', () => {
    expect(panBy(DEFAULT_VIEW, 50, 0, 500, 350).x).toBeCloseTo(-100)
    expect(viewBox({ x: 10, y: 20, k: 2 })).toBe(`10 20 ${WORLD.w / 2} ${WORLD.h / 2}`)
  })
  it('fits the view around strokes', () => {
    expect(fitView([[[400, 300], [600, 600]]]).k).toBeGreaterThan(1)
    expect(fitView([])).toEqual(DEFAULT_VIEW)
  })
})
