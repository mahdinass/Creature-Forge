import { describe, expect, it } from 'vitest'
import { advance, fallEvent, frameIndex, restart } from './playback'

const times = Array.from({ length: 11 }, (_, i) => i * 0.005)

describe('frameIndex', () => {
  it('clamps and finds the latest frame at or before t', () => {
    expect(frameIndex(times, -1)).toBe(0)
    expect(frameIndex(times, 0.012)).toBe(2)
    expect(frameIndex(times, 0.01)).toBe(2)
    expect(frameIndex(times, 99)).toBe(10)
  })
})

describe('advance', () => {
  it('advances sim time by wall dt * speed and replay time by wall dt', () => {
    const c = advance({ simTime: 0, replayTime: 0, playing: true }, 0.5, 0.25, 5)
    expect(c.simTime).toBeCloseTo(0.125)
    expect(c.replayTime).toBeCloseTo(0.5)
  })
  it('stops at the end of the simulation', () => {
    const c = advance({ simTime: 4.9, replayTime: 1, playing: true }, 1, 1, 5)
    expect(c.simTime).toBe(5)
    expect(c.playing).toBe(false)
  })
  it('does nothing while paused', () => {
    const c0 = { simTime: 1, replayTime: 2, playing: false }
    expect(advance(c0, 1, 1, 5)).toBe(c0)
  })
  it('restart resets both clocks and plays', () => {
    expect(restart()).toEqual({ simTime: 0, replayTime: 0, playing: true })
  })
})

describe('fallEvent', () => {
  it('returns only fall events', () => {
    expect(fallEvent([{ kind: 'foot_slip', time: 0.2 }])).toBeUndefined()
    expect(fallEvent([{ kind: 'foot_slip', time: 0.2 }, { kind: 'fall', time: 1.8 }])?.time).toBe(1.8)
  })
})
