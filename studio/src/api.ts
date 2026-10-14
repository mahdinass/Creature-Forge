import type { CompileResult, Params, Phase0, PushInfo, RunPayload, Schema, Sketch } from './types'
import type { LabRow, LabView, Replay } from './lab/labTypes'
import type { LocomotionReplay, LocomotionSummary } from './locomotion/locoTypes'
import type { DemoReplay, DemoRow, DemoRun, DemoStatus } from './demo/demoTypes'

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep status text */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const getSchema = () => fetch('/api/schema').then((r) => j<Schema>(r))
export const getPhase0 = () => fetch('/api/experiments/phase0').then((r) => j<Phase0>(r))
export const getDefaultSketch = () => fetch('/api/sketch/default').then((r) => j<Sketch>(r))

export const simulate = (body: Params, seed: number, duration: number, push: PushInfo | null) =>
  fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body, seed, duration, push }),
  }).then((r) => j<RunPayload>(r))

export const compileSketch = (sketch: Sketch) =>
  fetch('/api/sketch/compile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sketch),
  }).then((r) => j<CompileResult>(r))

// Investigation Lab (read-only records; replay is a fresh deterministic MuJoCo run, no model call)
export const getLabTrials = () => fetch('/api/lab/trials').then((r) => j<LabRow[]>(r))
export const getLabTrial = (id: string) => fetch(`/api/lab/trials/${encodeURIComponent(id)}`).then((r) => j<LabView>(r))
export const getLabReplay = (id: string, seed: number) =>
  fetch(`/api/lab/trials/${encodeURIComponent(id)}/replay?seed=${seed}`).then((r) => j<Replay>(r))

// Phase 2A locomotion (read-only results; replay is a fresh deterministic MuJoCo rollout, no model call)
export const getLocomotionSummary = () => fetch('/api/locomotion/summary').then((r) => j<LocomotionSummary>(r))
export const getLocomotionReplay = (controller: string, seed: number, duration: number) =>
  fetch(`/api/locomotion/replay?controller=${encodeURIComponent(controller)}&seed=${seed}&duration=${duration}`).then((r) =>
    j<LocomotionReplay>(r))

// Investigation demo (observed failure -> model proposal -> bounded edit -> MuJoCo verification). Replays are fresh deterministic rollouts.
export const getDemoStatus = () => fetch('/api/demo/status').then((r) => j<DemoStatus>(r))
export const getDemoRuns = () => fetch('/api/demo/runs').then((r) => j<DemoRow[]>(r))
export const getDemoRun = (id: string) => fetch(`/api/demo/runs/${encodeURIComponent(id)}`).then((r) => j<DemoRun>(r))
export const getDemoReplay = (id: string, which: string, seed: number) =>
  fetch(`/api/demo/runs/${encodeURIComponent(id)}/replay?which=${encodeURIComponent(which)}&seed=${seed}`).then((r) => j<DemoReplay>(r))
export const startDemoRun = (mode: 'live' | 'mock', confirmLive: boolean) =>
  fetch('/api/demo/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode, confirm_live: confirmLive }) }).then((r) => j<DemoRun>(r))
