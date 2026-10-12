// Pure playback / timeline helpers (unit tested). Simulation time (t, from MuJoCo) is distinct from
// replay time (wall-clock seconds the viewer has been playing).
export function frameIndex(times: number[], t: number): number {
  const n = times.length
  if (n === 0) return 0
  if (t <= times[0]) return 0
  if (t >= times[n - 1]) return n - 1
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (times[mid] <= t) lo = mid
    else hi = mid
  }
  return lo
}

export interface Clock {
  simTime: number
  replayTime: number
  playing: boolean
}

// Advance by `wallDt` real seconds at `speed` x. Stops (pauses) at `duration`.
export function advance(c: Clock, wallDt: number, speed: number, duration: number): Clock {
  if (!c.playing) return c
  const simTime = Math.min(duration, c.simTime + wallDt * speed)
  return { simTime, replayTime: c.replayTime + wallDt, playing: simTime < duration }
}

export function restart(): Clock {
  return { simTime: 0, replayTime: 0, playing: true }
}

export function fallEvent<T extends { kind: string; time: number }>(events: T[]): T | undefined {
  return events.find((e) => e.kind === 'fall')
}

export function fmtPct(x: number): string {
  return `${Math.round(x * 100)}%`
}
