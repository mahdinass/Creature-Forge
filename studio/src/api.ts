import type { CompileResult, NormalizeResult, Params, Phase0, PushInfo, RunPayload, Schema, Sketch, SketchSupport } from './types'
import type { LabRow, LabView, Replay } from './lab/labTypes'
import type { LocomotionReplay, LocomotionSummary } from './locomotion/locoTypes'
import type { OverviewData } from './overview/overviewTypes'
import type { WalkingReplay, WalkingSummary } from './walking/walkingTypes'
import type { FreehandResult, SandboxBodyDict, SandboxSchema, StrokeIn } from './sketch/freehandTypes'
import type { DemoReplay, DemoRow, DemoRun, DemoStatus } from './demo/demoTypes'
import type { CausalIndex, CausalRecord, CausalReplay, DesignKey } from './causal/causalTypes'
import type { ScientistIndex, ScientistRecord } from './scientist/scientistTypes'
import type { DesignId, Do1Index, Do1Payload } from './do1/do1Types'
import type { NemotronCaseResponse } from './nemotron/nemotronTypes'
import type { ChallengeRun, Creature, CreatureSummary, ForgeStatus, InvestigationRecord, InvestigationSummary, Job, JobPoll, Kind, RecoveryRecord, RecoverySummary, StartedChallenge, StartedInvestigation, StartedRecovery } from './forge/forgeTypes'

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

// Walking lab (committed R2 records; replays are fresh deterministic rollouts, no model call)
export const getWalkingSummary = () => fetch('/api/walking/summary').then((r) => j<WalkingSummary>(r))
export const getWalkingReplay = (which: string, seed: number) =>
  fetch(`/api/walking/replay?which=${encodeURIComponent(which)}&seed=${seed}`).then((r) => j<WalkingReplay>(r))

// Creative sandbox: freehand interpretation and wider-bounds simulation (registered experiments keep their bounds)
export const getSandboxSchema = () => fetch('/api/sandbox/schema').then((r) => j<SandboxSchema>(r))
export const interpretFreehand = (strokes: StrokeIn[], guided: boolean, materials: Record<string, number>) =>
  fetch('/api/freehand/interpret', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strokes, guided, materials }) }).then((r) => j<FreehandResult>(r))
export const sandboxSimulate = (body: SandboxBodyDict, push: PushInfo | null, seed = 0, duration = 5) =>
  fetch('/api/sandbox/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ body, seed, duration, push }) }).then((r) => j<RunPayload & { sandbox: true; explanation: import('./sketch/freehandTypes').Explanation }>(r))

// ---- Forge workspace (/api/forge/*): your own creature, live MuJoCo. Errors keep the HTTP status so the UI can tell 503 (not available) apart.
export class ForgeApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ForgeApiError'
    this.status = status
  }
}
export async function fj<T>(res: Response): Promise<T> {
  try {
    return await j<T>(res)
  } catch (e) {
    throw new ForgeApiError((e as Error).message, res.status)
  }
}
const FORGE = '/api/forge'
const postJson = (url: string, body: unknown) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export interface ForgeReplayQuery { runId: string; seed: number; direction?: 1 | -1; force?: number | null }
/** Query string of GET /api/forge/replay for a challenge run (direction and force only for push replays). */
export function forgeReplayUrl(q: ForgeReplayQuery): string {
  const p = new URLSearchParams({ run_id: q.runId, seed: String(q.seed) })
  if (q.direction !== undefined) p.set('direction', String(q.direction))
  if (q.force !== undefined && q.force !== null) p.set('force', String(q.force))
  return `${FORGE}/replay?${p.toString()}`
}
/** Replay of one arm of an investigation (503 until the investigation backend exists). */
export function forgeArmReplayUrl(investigationId: string, arm: string, seed: number): string {
  return `${FORGE}/replay?${new URLSearchParams({ investigation_id: investigationId, arm, seed: String(seed) }).toString()}`
}

export const getForgeStatus = () => fetch(`${FORGE}/status`).then((r) => fj<ForgeStatus>(r))
export const listCreatures = () => fetch(`${FORGE}/creatures`).then((r) => fj<CreatureSummary[]>(r))
export const createCreature = (b: { name: string; body: unknown; mode: 'guided' | 'experimental'; drawing: unknown }) =>
  postJson(`${FORGE}/creatures`, b).then((r) => fj<Creature>(r))
export const getCreature = (cid: string) => fetch(`${FORGE}/creatures/${encodeURIComponent(cid)}`).then((r) => fj<Creature>(r))
export const setCurrentVersion = (cid: string, n: number) =>
  postJson(`${FORGE}/creatures/${encodeURIComponent(cid)}/current`, { n }).then((r) => fj<Creature>(r))
export const startChallenge = (cid: string, n: number, b: { kind: Kind; seeds?: number; overrides?: Record<string, number | string> }) =>
  postJson(`${FORGE}/creatures/${encodeURIComponent(cid)}/versions/${n}/challenges`, b).then((r) => fj<StartedChallenge>(r))
export const getForgeRun = (runId: string) => fetch(`${FORGE}/runs/${encodeURIComponent(runId)}`).then((r) => fj<ChallengeRun>(r))
export const getForgeJob = (jobId: string, since = 0) =>
  fetch(`${FORGE}/jobs/${encodeURIComponent(jobId)}?since=${since}`).then((r) => fj<JobPoll>(r))
export const cancelForgeJob = (jobId: string) => postJson(`${FORGE}/jobs/${encodeURIComponent(jobId)}/cancel`, {}).then((r) => fj<Job>(r))
export const getForgeReplay = (q: ForgeReplayQuery) => fetch(forgeReplayUrl(q)).then((r) => fj<RunPayload>(r))
export const getForgeArmReplay = (investigationId: string, arm: string, seed: number) =>
  fetch(forgeArmReplayUrl(investigationId, arm, seed)).then((r) => fj<RunPayload>(r))
export const startInvestigation = (cid: string, n: number, b: { run_id: string; mode: 'live' | 'scripted'; loop?: boolean; probes?: boolean; memory?: boolean; profile?: 'default' | 'deep' }) =>
  postJson(`${FORGE}/creatures/${encodeURIComponent(cid)}/versions/${n}/investigations`, b).then((r) => fj<StartedInvestigation>(r))
export const getInvestigation = (id: string) => fetch(`${FORGE}/investigations/${encodeURIComponent(id)}`).then((r) => fj<InvestigationRecord>(r))
export const listInvestigations = (cid: string) => fetch(`${FORGE}/investigations?cid=${encodeURIComponent(cid)}`).then((r) => fj<InvestigationSummary[]>(r))
export const acceptArm = (cid: string, b: { investigation_id: string; arm_id: string }) =>
  postJson(`${FORGE}/creatures/${encodeURIComponent(cid)}/accept`, b).then((r) => fj<Creature>(r))

// ---- walking recovery ("Recover walking"): creature_forge/recoveries.py
export function forgeRecoveryReplayUrl(recoveryId: string, arm: 'original' | 'candidate', seed: number): string {
  return `${FORGE}/recoveries/${encodeURIComponent(recoveryId)}/replay?${new URLSearchParams({ arm, seed: String(seed) }).toString()}`
}
export const startRecovery = (cid: string, n: number, b: { director: 'ai' | 'fix'; mode?: 'live' | 'scripted'; budget: number }) =>
  postJson(`${FORGE}/creatures/${encodeURIComponent(cid)}/versions/${n}/recoveries`, b).then((r) => fj<StartedRecovery>(r))
export const listRecoveries = (cid: string) => fetch(`${FORGE}/recoveries?cid=${encodeURIComponent(cid)}`).then((r) => fj<RecoverySummary[]>(r))
export const getRecovery = (id: string) => fetch(`${FORGE}/recoveries/${encodeURIComponent(id)}`).then((r) => fj<RecoveryRecord>(r))
export const getRecoveryReplay = (id: string, arm: 'original' | 'candidate', seed: number) =>
  fetch(forgeRecoveryReplayUrl(id, arm, seed)).then((r) => fj<RunPayload>(r))
export const acceptRecovery = (cid: string, recoveryId: string) =>
  postJson(`${FORGE}/creatures/${encodeURIComponent(cid)}/accept-recovery`, { recovery_id: recoveryId }).then((r) => fj<Creature>(r))

// Causal engineer (/api/causal/*): recorded investigations of why a robot falls; replays are fresh deterministic MuJoCo rollouts, no model call
export const getCausalRecords = () => fetch('/api/causal/records').then((r) => j<CausalIndex>(r))
export const getCausalRecord = (id: string) => fetch(`/api/causal/records/${encodeURIComponent(id)}`).then((r) => j<CausalRecord>(r))
export const getCausalReplay = (id: string, design: DesignKey, seed: number) =>
  fetch(`/api/causal/records/${encodeURIComponent(id)}/replay?design=${design}&seed=${seed}`).then((r) => j<CausalReplay>(r))

// Autonomous HaS scientist (/api/scientist/*): recorded Stage-2 investigations; same replay contract as the causal records
export const getScientistRecords = () => fetch('/api/scientist/records').then((r) => j<ScientistIndex>(r))
export const getScientistRecord = (id: string) => fetch(`/api/scientist/records/${encodeURIComponent(id)}`).then((r) => j<ScientistRecord>(r))
export const getScientistReplay = (id: string, design: DesignKey, seed: number) =>
  fetch(`/api/scientist/records/${encodeURIComponent(id)}/replay?design=${design}&seed=${seed}`).then((r) => j<CausalReplay>(r))

// DO-1 L4 recovery (/api/do1/*): verified static replays of the faulty, frozen and DO-1 designs; no simulation
export const getDo1Index = () => fetch('/api/do1/index').then((r) => j<Do1Index>(r))
export const getDo1Payload = (design: DesignId, duration: 10 | 20, seed: number) =>
  fetch(`/api/do1/payload/${design}/${duration}/${seed}`).then((r) => j<Do1Payload>(r))

// Nemotron's recorded gen-0137 investigation (/api/nemotron/*): pinned W2 case files; playback, no model call, no simulation
export const getNemotronCase = () => fetch('/api/nemotron/case').then((r) => j<NemotronCaseResponse>(r))
