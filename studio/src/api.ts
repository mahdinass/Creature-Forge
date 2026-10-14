import type { CompileResult, NormalizeResult, Params, Phase0, PushInfo, RunPayload, Schema, Sketch, SketchSupport } from './types'
import type { LabRow, LabView, Replay } from './lab/labTypes'
import type { LocomotionReplay, LocomotionSummary } from './locomotion/locoTypes'
import type { OverviewData } from './overview/overviewTypes'
import type { DemoReplay, DemoRow, DemoRun, DemoStatus } from './demo/demoTypes'

export const STALE_HINT =
  'The running Studio server is probably older than this page. Close it and start the current one with scripts\start_studio.ps1.'

/** Parse a JSON API response; HTML (the SPA fallback of an old server) or a bad body becomes a clear error. */
export async function j<T>(res: Response): Promise<T> {
  const type = res.headers.get('content-type') ?? ''
  const isJson = type.includes('json')
  if (!isJson) {
    throw new Error(`${res.url ? new URL(res.url, 'http://x').pathname : 'API'} returned ${type || 'no content type'} (HTTP ${res.status}) instead of JSON. ${STALE_HINT}`)
  }
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

export const getOverview = () => fetch('/api/overview').then((r) => j<OverviewData>(r))

// Investigation demo (observed failure -> model proposal -> bounded edit -> MuJoCo verification). Replays are fresh deterministic rollouts.
export const getDemoStatus = () => fetch('/api/demo/status').then((r) => j<DemoStatus>(r))
export const getDemoRuns = () => fetch('/api/demo/runs').then((r) => j<DemoRow[]>(r))
export const getDemoRun = (id: string) => fetch(`/api/demo/runs/${encodeURIComponent(id)}`).then((r) => j<DemoRun>(r))
export const getDemoReplay = (id: string, which: string, seed: number) =>
  fetch(`/api/demo/runs/${encodeURIComponent(id)}/replay?which=${encodeURIComponent(which)}&seed=${seed}`).then((r) => j<DemoReplay>(r))
export const startDemoRun = (mode: 'live' | 'mock', confirmLive: boolean) =>
  fetch('/api/demo/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode, confirm_live: confirmLive }) }).then((r) => j<DemoRun>(r))

export const getVersion = () => fetch('/api/version').then((r) => j<{ git_commit: string | null; git_branch: string | null; started_at: string; dist_built: string | null; api_routes: string[] }>(r))

export const getSketchSupport = () => fetch('/api/sketch/support').then((r) => j<SketchSupport>(r))
export const normalizeSketch = (sketch: Sketch, extras: Params) =>
  fetch('/api/sketch/normalize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nodes: sketch.nodes, segments: sketch.segments, extras }),
  }).then((r) => j<NormalizeResult>(r))
