// Pure logic of the forge workspace (unit tested). It formats and routes what the API returned; it never computes a
// physics result and never decides a verdict: statuses, scores and verdict fields are read from the records.
import type { ParamDiff } from '../demo/demoLogic'
import type {
  Arm, ArmSource, ChallengeRun, Creature, CreatureVersion, Controllers, Hypothesis, InvestigationRecord, Job, JobEvent, JobPoll, Kind, ModelCall,
  Outcome, SeedResult, Verdict, VerdictStatus,
} from './forgeTypes'

// ---- challenges and outcomes ------------------------------------------------------------------------------------
export const KINDS: Kind[] = ['stand', 'push', 'walk']

export const KIND_INFO: Record<Kind, { label: string; meaning: string; scoreMeaning: string; unit: string }> = {
  stand: {
    label: 'Stand',
    meaning: 'Can it keep standing after a small random nudge at the start?',
    scoreMeaning: 'Score = how many seconds it stayed up.',
    unit: 's',
  },
  push: {
    label: 'Push',
    meaning: 'How hard can you shove it, forwards or backwards, before it falls?',
    scoreMeaning: 'Score = the critical push force in newtons, taken from its weakest direction.',
    unit: 'N',
  },
  walk: {
    label: 'Walk',
    meaning: 'Can it walk forward without falling over?',
    scoreMeaning: 'Score = metres walked upright with a valid gait (0 if it falls in the first second).',
    unit: 'm',
  },
}

export const DEFAULT_TARGET_FORCE = 10

export const OUTCOME_INFO: Record<Outcome, { label: string; tone: 'ok' | 'warn' | 'bad' | 'error'; text: string }> = {
  PASS: { label: 'PASS', tone: 'ok', text: 'It did the job with a safe margin.' },
  POOR: { label: 'POOR', tone: 'warn', text: 'It managed it, but only just or not convincingly. This is not a pass.' },
  FAIL: { label: 'FAIL', tone: 'bad', text: 'It could not do it: it fell or never got going.' },
  ERROR: { label: 'ERROR', tone: 'error', text: 'The run could not be carried out. This says nothing about the creature.' },
}

export function outcomeInfo(o: string): { label: string; tone: 'ok' | 'warn' | 'bad' | 'error'; text: string } {
  return OUTCOME_INFO[o as Outcome] ?? { label: String(o), tone: 'error', text: 'Unknown outcome from the server.' }
}

export function countOutcomes(per: SeedResult[]): Record<Outcome, number> {
  const c: Record<Outcome, number> = { PASS: 0, POOR: 0, FAIL: 0, ERROR: 0 }
  for (const s of per) if (s.outcome in c) c[s.outcome] += 1
  return c
}

export function median(xs: number[]): number | null {
  const v = xs.filter((x) => Number.isFinite(x)).sort((a, b) => a - b)
  if (v.length === 0) return null
  const m = v.length >> 1
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2
}

export function fmtScore(kind: Kind, score: number | null | undefined): string {
  if (score === null || score === undefined || !Number.isFinite(score)) return 'n/a'
  const u = KIND_INFO[kind].unit
  return `${score.toFixed(kind === 'walk' ? 2 : 1)} ${u}`
}

const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null)

/** +1 forward, -1 backward, null when the metric is missing or not understood. */
export function pushDirection(v: unknown): 1 | -1 | null {
  if (typeof v === 'number') return v > 0 ? 1 : v < 0 ? -1 : null
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase()
    if (s === '+1' || s === '1' || s.startsWith('f') || s === '+') return 1
    if (s === '-1' || s.startsWith('b') || s === '-') return -1
  }
  return null
}

export const directionWord = (d: 1 | -1): string => (d === 1 ? 'forward' : 'backward')

/** One plain sentence about one seed, built only from the seed's own record. */
export function seedReason(kind: Kind, s: SeedResult): string {
  if (s.outcome === 'ERROR') return s.error ? `Could not run: ${s.error}` : 'Could not run (no message was returned).'
  const m = s.metrics
  if (kind === 'stand') {
    const fell = m.fell === true
    const t = num(m.fall_time) ?? num(m.survival_s)
    if (fell) return `Fell${t !== null ? ` after ${t.toFixed(2)} s` : ''}.`
    const bits: string[] = ['Stayed up for the whole run']
    const pitch = num(m.max_abs_pitch_after_settle)
    const hr = num(m.min_height_ratio)
    if (s.outcome === 'POOR') {
      if (pitch !== null && pitch > 0.5) bits.push(`but leaned ${(pitch * 57.2958).toFixed(0)} degrees`)
      if (hr !== null && hr < 0.7) bits.push(`and sagged to ${(hr * 100).toFixed(0)}% of its starting height`)
    }
    return `${bits.join(' ')}.`
  }
  if (kind === 'push') {
    const fwd = num(m.critical_force_fwd)
    const bwd = num(m.critical_force_bwd)
    const dir = pushDirection(m.weak_direction)
    const parts: string[] = []
    if (fwd !== null) parts.push(`${fwd.toFixed(1)} N forward`)
    if (bwd !== null) parts.push(`${bwd.toFixed(1)} N backward`)
    const weak = dir !== null ? ` Weakest direction: ${directionWord(dir)}.` : ''
    const cens = m.censored === true ? ' It never fell at the highest force tried.' : ''
    return `Withstood ${parts.length ? parts.join(' and ') : fmtScore('push', s.score)} before falling.${weak}${cens}`
  }
  const fell = s.events.find((e) => e.kind === 'fall')
  if (fell) return `Fell at ${fell.time.toFixed(2)} s.`
  return s.outcome === 'PASS' ? `Walked ${fmtScore('walk', s.score)} with a valid gait.` : `Stayed upright but did not walk properly (${fmtScore('walk', s.score)}).`
}

/** One plain-language headline for the whole run: counts and score statistics come from the per-seed records. */
export function runHeadline(run: ChallengeRun): string {
  const n = run.per_seed.length
  const c = countOutcomes(run.per_seed)
  const kind = run.spec.kind
  if (run.outcome === 'ERROR') {
    return c.ERROR === n ? 'Not one seed could be run.' : `${c.ERROR} of ${n} seeds could not be run.`
  }
  const med = median(run.per_seed.filter((s) => s.outcome !== 'ERROR').map((s) => s.score))
  const parts = [`${c.PASS} of ${n} seeds passed`]
  if (c.POOR) parts.push(`${c.POOR} poor`)
  if (c.FAIL) parts.push(`${c.FAIL} failed`)
  let line = `${parts.join(', ')}.`
  if (kind === 'push') {
    const target = run.spec.target_force ?? DEFAULT_TARGET_FORCE
    line += ` Median critical push force ${fmtScore('push', med)} against a target of ${target} N.`
  } else if (med !== null) {
    line += ` Median score ${fmtScore(kind, med)}.`
  }
  return line
}

/** Text shown for the controller that drove the run (walk: how it was chosen and what adaptation cost). */
export function controllerNote(run: ChallengeRun): string | null {
  const w = run.controller?.walk
  if (run.spec.kind === 'walk') {
    if (!w) return null
    if (w.kind === 'adapted' && w.adaptation) {
      const used = w.adaptation.rollouts_used
      return `Walking controller adapted to this body${used !== undefined ? ` using ${used} extra physics rollouts` : ''}${w.adaptation.budget !== undefined ? ` (budget ${w.adaptation.budget})` : ''}.`
    }
    if (w.kind === 'r2-transfer') return 'Walking controller transferred unchanged from the earlier tuned biped (no adaptation to this body).'
    if (w.kind === 'none') return 'This creature has no walking controller yet.'
    return `Walking controller: ${w.kind ?? 'unknown'}.`
  }
  const s = run.controller?.stand
  if (s) return s.edited ? 'Standing controller with edits from an accepted version.' : 'Default standing controller.'
  return null
}

/** What the picker tells the user about the cost of a walk challenge, from the last run's provenance when known. */
export function walkCostNote(run: ChallengeRun | null): string {
  const used = run?.controller?.walk?.adaptation?.rollouts_used
  const base = 'Walking may adapt its controller to your body first, which costs extra physics rollouts.'
  if (used === undefined || used === null) return `${base} The exact number is reported with the result.`
  return `${base} The last walk run used ${used} extra rollouts.`
}

/** The seed to replay first: the first FAIL, else the first POOR, else the first seed that ran. ERROR seeds have no replay. */
export function defaultSeed(run: ChallengeRun): number | null {
  const ran = run.per_seed.filter((s) => s.outcome !== 'ERROR')
  return (ran.find((s) => s.outcome === 'FAIL') ?? ran.find((s) => s.outcome === 'POOR') ?? ran[0])?.seed ?? null
}

export interface ReplayChoice { key: string; label: string; direction?: 1 | -1; force?: number }

/** Replays offered for a seed. Push replays need a direction and a force; the server has no default for them. */
export function replayChoices(run: ChallengeRun, seed: SeedResult): ReplayChoice[] {
  if (run.spec.kind !== 'push') return [{ key: 'run', label: 'The run as scored' }]
  const dir = pushDirection(seed.metrics.weak_direction) ?? 1
  const other = (dir === 1 ? -1 : 1) as 1 | -1
  const target = run.spec.target_force ?? DEFAULT_TARGET_FORCE
  const crit = (d: 1 | -1) => num(seed.metrics[d === 1 ? 'critical_force_fwd' : 'critical_force_bwd'])
  const out: ReplayChoice[] = [{ key: `t${dir}`, label: `Weakest direction (${directionWord(dir)}) at the target ${target} N`, direction: dir, force: target }]
  const wc = crit(dir)
  if (wc !== null) out.push({ key: `c${dir}`, label: `Weakest direction at its critical force ${wc.toFixed(1)} N`, direction: dir, force: wc })
  out.push({ key: `t${other}`, label: `Other direction (${directionWord(other)}) at the target ${target} N`, direction: other, force: target })
  return out
}

// ---- jobs: polling reducer --------------------------------------------------------------------------------------
export interface PollState { job: Job | null; events: JobEvent[]; since: number; error: string | null; failures: number }
export const MAX_POLL_FAILURES = 5
export const POLL_MS = 1000

export const initialPoll: PollState = { job: null, events: [], since: 0, error: null, failures: 0 }

export type PollAction = { type: 'reset' } | { type: 'data'; poll: JobPoll } | { type: 'error'; message: string }

export function pollReducer(state: PollState, action: PollAction): PollState {
  if (action.type === 'reset') return initialPoll
  if (action.type === 'error') return { ...state, error: action.message, failures: state.failures + 1 }
  const seen = new Set(state.events.map((e) => e.i))
  const fresh = action.poll.events.filter((e) => !seen.has(e.i))
  const events = [...state.events, ...fresh].sort((a, b) => a.i - b.i)
  const since = events.reduce((m, e) => Math.max(m, e.i), state.since)
  return { job: action.poll.job, events, since, error: null, failures: 0 }
}

export const isTerminal = (s: string | undefined): boolean => s === 'done' || s === 'failed' || s === 'cancelled'
export const shouldKeepPolling = (st: PollState): boolean => !isTerminal(st.job?.status) && st.failures < MAX_POLL_FAILURES

export function progressFraction(job: Job | null): number | null {
  if (!job) return null
  if (job.status === 'done') return 1
  const { done, total } = job.progress
  return total > 0 ? Math.max(0, Math.min(1, done / total)) : null
}

export function phaseText(job: Job | null, events: JobEvent[]): string {
  if (!job) return 'Starting...'
  if (job.status === 'queued') return 'Waiting for the physics worker...'
  const { phase, done, total } = job.progress
  const lastPhase = [...events].reverse().find((e) => e.type === 'phase')
  const label = phase ?? (typeof lastPhase?.data.phase === 'string' ? (lastPhase.data.phase as string) : null)
  if (job.status === 'done') return 'Finished.'
  if (job.status === 'failed') return 'The run failed.'
  if (job.status === 'cancelled') return 'The run was cancelled.'
  const what = label ? `${label}` : 'running'
  return total > 0 ? `${what}: ${done} of ${total} rollouts done` : `${what}...`
}

/** Honest failure text of a job: the job error plus the last error event message when it adds something. */
export function jobFailureMessage(job: Job | null, events: JobEvent[]): string {
  const ev = [...events].reverse().find((e) => e.type === 'error')
  const evMsg = typeof ev?.data.message === 'string' ? (ev.data.message as string) : null
  const err = job?.error ?? evMsg
  if (!err) return job?.status === 'cancelled' ? 'The run was cancelled.' : 'The run failed without a message.'
  return err
}

// ---- lineage ----------------------------------------------------------------------------------------------------
export interface LineageRow { n: number; parent: number | null; depth: number; current: boolean; origin: 'user' | 'ai_accepted'; summary: string; version: CreatureVersion }

/** Newest version first, each with its depth in the parent chain; unknown parents count as roots. */
export function lineageRows(c: Creature): LineageRow[] {
  const byN = new Map(c.versions.map((v) => [v.n, v]))
  const depth = (v: CreatureVersion, guard = 0): number => (v.parent !== null && byN.has(v.parent) && guard < 100 ? 1 + depth(byN.get(v.parent)!, guard + 1) : 0)
  return [...c.versions].sort((a, b) => b.n - a.n).map((v) => ({
    n: v.n, parent: v.parent, depth: depth(v), current: v.n === c.current, origin: v.origin, summary: changeSummary(v), version: v,
  }))
}

export function changeSummary(v: CreatureVersion): string {
  if (v.origin === 'user' || !v.change) return v.parent === null ? 'Drawn by you' : 'Saved by you'
  const ch = v.change
  const edits = (ch.edits ?? []).map((e) => `${e.param} ${e.op === 'scale' ? `x${e.value}` : `= ${e.value}`}${e.target && e.target !== 'both' ? ` (${e.target})` : ''}`)
  const src = ch.source === 'nemotron' ? 'AI-proposed' : ch.source === 'heuristic' ? 'heuristic' : ch.source === 'random_baseline' ? 'random baseline' : 'accepted'
  return `${src}, verified: ${edits.length ? edits.join(', ') : 'no edit list'}`
}

export const originLabel = (o: 'user' | 'ai_accepted'): string => (o === 'user' ? 'Yours' : 'AI change, accepted')

// ---- investigation record ---------------------------------------------------------------------------------------
export const ARM_CHIP: Record<ArmSource, { label: string; tone: string }> = {
  original: { label: 'ORIGINAL', tone: 'original' },
  nemotron: { label: 'NEMOTRON', tone: 'model' },
  random_baseline: { label: 'RANDOM BASELINE', tone: 'random' },
  heuristic: { label: 'HEURISTIC', tone: 'heuristic' },
}

/** Chip for an arm. A scripted mock never wears the NEMOTRON label: the record's provenance decides. */
export function armChip(arm: Pick<Arm, 'source'>, provenance: string | undefined): { label: string; tone: string } {
  if (arm.source === 'nemotron' && provenance === 'SCRIPTED_MOCK') return { label: 'SCRIPTED MOCK', tone: 'mock' }
  return ARM_CHIP[arm.source] ?? { label: String(arm.source).toUpperCase(), tone: 'random' }
}

export function armList(rec: InvestigationRecord): Arm[] {
  const a = rec.arms
  if (!a) return []
  return Array.isArray(a) ? a : Object.entries(a).map(([id, v]) => ({ ...v, arm_id: v.arm_id ?? id }))
}

export const VERDICT_TONE: Record<VerdictStatus, 'ok' | 'bad' | 'warn' | 'muted'> = {
  VERIFIED_IMPROVEMENT: 'ok', WORSE: 'bad', NOT_VERIFIED: 'muted', INCONCLUSIVE: 'warn',
}
export const VERDICT_LABEL: Record<VerdictStatus, string> = {
  VERIFIED_IMPROVEMENT: 'Verified improvement', NOT_VERIFIED: 'Not verified', WORSE: 'Worse than the original', INCONCLUSIVE: 'Inconclusive',
}

export function fmtMinEffect(m: Verdict['min_effect']): string {
  if (m === undefined || m === null) return 'n/a'
  if (typeof m === 'number') return String(m)
  return Object.entries(m).map(([k, v]) => (k === 'rel' ? `${k} ${(v * 100).toFixed(0)}%` : `${k} ${v}`)).join(' and ')
}

/** The verdict sentence is assembled from the record's own fields; the status is never derived here. */
export function verdictText(v: Verdict | undefined): string {
  if (!v) return 'No verdict was recorded for this arm.'
  const label = VERDICT_LABEL[v.status] ?? v.status
  const bits: string[] = []
  if (v.n !== undefined) bits.push(`${v.wins ?? 0} wins, ${v.losses ?? 0} losses, ${v.ties ?? 0} ties over ${v.n} paired seeds`)
  if (v.median_diff !== undefined) bits.push(`median difference ${v.median_diff >= 0 ? '+' : ''}${v.median_diff.toFixed(2)}`)
  if (v.p_one_sided !== undefined) bits.push(`one-sided p = ${v.p_one_sided.toFixed(3)}`)
  if (v.min_effect !== undefined) bits.push(`smallest effect that counts: ${fmtMinEffect(v.min_effect)}`)
  const why = v.reasons && v.reasons.length ? ` Reasons: ${v.reasons.join('; ')}.` : ''
  return `${label}${bits.length ? `: ${bits.join(', ')}` : ''}.${why}`
}

/** Accept is allowed only when the recorded verdict of that arm is VERIFIED_IMPROVEMENT. */
export function canAccept(arm: Pick<Arm, 'arm_id' | 'source'> | undefined, v: Verdict | undefined): boolean {
  return !!arm && arm.source !== 'original' && v?.status === 'VERIFIED_IMPROVEMENT'
}

export function acceptBlockReason(arm: Pick<Arm, 'arm_id' | 'source'> | undefined, v: Verdict | undefined): string | null {
  if (!arm) return 'Pick an arm first.'
  if (arm.source === 'original') return 'The original is the starting point, there is nothing to accept.'
  if (!v) return 'No verdict was recorded for this arm, so it cannot be accepted.'
  if (v.status === 'VERIFIED_IMPROVEMENT') return null
  return `Only a verified improvement can be accepted. This arm's verdict is "${VERDICT_LABEL[v.status] ?? v.status}".`
}

const asNum = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null)

/** Scores of one arm on the validation seeds, from either `{arm: [{seed, score}]}` or `{arm: {seed: {score}}}`. */
export function armScores(rec: InvestigationRecord, armId: string): { seed: number; score: number }[] {
  const vr = rec.validation_results as Record<string, unknown> | undefined
  const raw = vr?.[armId]
  if (!raw) return []
  if (Array.isArray(raw)) {
    return raw.flatMap((r) => {
      const o = r as { seed?: unknown; score?: unknown }
      const seed = asNum(o.seed)
      const score = asNum(o.score)
      return seed !== null && score !== null ? [{ seed, score }] : []
    })
  }
  return Object.entries(raw as Record<string, { score?: unknown }>).flatMap(([k, v]) => {
    const score = asNum(v?.score)
    return Number.isFinite(Number(k)) && score !== null ? [{ seed: Number(k), score }] : []
  })
}

/** Resolve a dotted/indexed citation (`seeds[0].score`) in the evidence pack; only scalars count. */
export function resolveCitation(evidence: Record<string, unknown> | undefined, path: string): string | number | boolean | null | undefined {
  if (!evidence) return undefined
  let cur: unknown = evidence
  for (const part of path.split('.')) {
    const m = /^([^[\]]+)((?:\[\d+\])*)$/.exec(part)
    if (!m) return undefined
    cur = (cur as Record<string, unknown> | null)?.[m[1]]
    for (const idx of m[2].matchAll(/\[(\d+)\]/g)) cur = Array.isArray(cur) ? cur[Number(idx[1])] : undefined
    if (cur === undefined) return undefined
  }
  return cur === null || typeof cur === 'string' || typeof cur === 'number' || typeof cur === 'boolean' ? cur : undefined
}

export type TimelineStep =
  | { kind: 'evidence'; id: string; keys: string[]; bytes: number }
  | { kind: 'model_call'; id: string; call: ModelCall; tokens: number | null }
  | { kind: 'hypotheses'; id: string; summary: string | null; items: (Hypothesis & { cited: { path: string; value: string | number | boolean | null | undefined }[] })[] }
  | { kind: 'proposals'; id: string; items: { id: string; status: 'accepted' | 'rejected'; reasons: string[]; hypothesis?: string; expected?: string }[] }
  | { kind: 'arena'; id: string; arms: { arm_id: string; chip: { label: string; tone: string }; unavailable?: string }[]; screenSeeds: number; validateSeeds: number }
  | { kind: 'verdicts'; id: string; items: { arm_id: string; chip: { label: string; tone: string }; status: VerdictStatus | null; text: string }[] }
  | { kind: 'failure'; id: string; status: string; message: string }

/** Ordered timeline of a finished investigation record: evidence, model call, hypotheses, proposals, arena, verdicts. */
export function buildTimeline(rec: InvestigationRecord): TimelineStep[] {
  const steps: TimelineStep[] = []
  if (rec.evidence) steps.push({ kind: 'evidence', id: 'evidence', keys: Object.keys(rec.evidence), bytes: JSON.stringify(rec.evidence).length })
  ;(rec.model_calls ?? []).forEach((call, i) => {
    const u = call.usage
    const tokens = u ? (u.total_tokens ?? ((u.prompt_tokens ?? 0) + (u.completion_tokens ?? 0))) : null
    steps.push({ kind: 'model_call', id: `call-${i}`, call, tokens })
  })
  const hyps = rec.reply?.diagnosis?.hypotheses ?? []
  if (hyps.length) {
    steps.push({
      kind: 'hypotheses', id: 'hypotheses', summary: rec.reply?.diagnosis?.summary ?? null,
      items: hyps.map((h) => ({ ...h, cited: (h.evidence ?? []).map((path) => ({ path, value: resolveCitation(rec.evidence, path) })) })),
    })
  }
  const vprops = rec.validation?.proposals ?? []
  if (vprops.length) {
    const replyProps = rec.reply?.proposals ?? []
    steps.push({
      kind: 'proposals', id: 'proposals',
      items: vprops.map((p) => {
        const rp = replyProps.find((x) => x.id === p.id)
        return { id: p.id, status: p.status, reasons: p.reasons ?? [], hypothesis: rp?.hypothesis, expected: rp?.prediction?.expected_change }
      }),
    })
  }
  const arms = armList(rec)
  if (arms.length) {
    steps.push({
      kind: 'arena', id: 'arena', screenSeeds: rec.seeds?.screen?.length ?? 0, validateSeeds: rec.seeds?.validate?.length ?? 0,
      arms: arms.map((a) => ({ arm_id: a.arm_id, chip: armChip(a, rec.provenance), unavailable: a.unavailable })),
    })
  }
  const verdicts = rec.verdicts ?? {}
  const vItems = arms.filter((a) => verdicts[a.arm_id]).map((a) => ({
    arm_id: a.arm_id, chip: armChip(a, rec.provenance), status: verdicts[a.arm_id].status, text: verdictText(verdicts[a.arm_id]),
  }))
  if (vItems.length) steps.push({ kind: 'verdicts', id: 'verdicts', items: vItems })
  if (rec.status === 'model_failed' || rec.error) {
    steps.push({ kind: 'failure', id: 'failure', status: rec.status, message: rec.error ?? 'The model call failed without a message.' })
  }
  return steps
}

export const isModelFailed = (rec: InvestigationRecord): boolean => rec.status === 'model_failed'

// ---- parameter diff for the accept panel --------------------------------------------------------------------------
const MEANING: Record<string, string> = {
  torso_mass: 'body weight', thigh_length: 'upper leg', shank_length: 'lower leg', foot_length: 'foot length',
  foot_friction: 'foot grip', torque_limit: 'motor strength', leg_density: 'leg material',
}

/** Body parameters before/after on their allowed range. Bounds come from the sandbox schema; `_r` fields use their leg's bound. */
export function bodyDiffs(before: Record<string, unknown>, after: Record<string, unknown> | undefined, bounds: Record<string, [number, number]>): ParamDiff[] {
  if (!after) return []
  const out: ParamDiff[] = []
  for (const [name, a] of Object.entries(after)) {
    const b = before[name]
    if (typeof a !== 'number' || typeof b !== 'number') continue
    const [lo, hi] = bounds[name] ?? bounds[name.replace(/_r$/, '')] ?? [NaN, NaN]
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) continue
    const u = (x: number) => Math.max(0, Math.min(1, (x - lo) / (hi - lo)))
    out.push({ name, meaning: MEANING[name.replace(/_r$/, '')] ?? '', lower: lo, upper: hi, before: b, after: a, uBefore: u(b), uAfter: u(a), changed: a !== b, reflected: false })
  }
  return out
}

/** Standing-controller or walking-vector differences as plain rows (these have no schema bounds on the page). */
export function controllerDiffs(before: Controllers | undefined, after: Controllers | undefined): { name: string; before: number; after: number }[] {
  const rows: { name: string; before: number; after: number }[] = []
  for (const [k, v] of Object.entries(after?.stand ?? {})) {
    const b = before?.stand?.[k]
    if (typeof b === 'number' && typeof v === 'number' && b !== v) rows.push({ name: `stand.${k}`, before: b, after: v })
  }
  const bv = before?.walk?.vector
  const av = after?.walk?.vector
  if (bv && av) av.forEach((x, i) => { if (bv[i] !== x) rows.push({ name: `walk[${i}]`, before: bv[i], after: x }) })
  return rows
}

// ---- deep link / persistence ------------------------------------------------------------------------------------
export interface ForgeLink { creature: string | null; v: number | null; run: string | null }
export function parseForgeLink(search: string): ForgeLink {
  const q = new URLSearchParams(search)
  const v = parseInt(q.get('v') ?? '', 10)
  return { creature: q.get('creature'), v: Number.isFinite(v) && v >= 1 ? v : null, run: q.get('run') }
}
export function forgeUrl(cid: string, n?: number | null, run?: string | null): string {
  const p = new URLSearchParams({ tab: 'forge', creature: cid })
  if (n) p.set('v', String(n))
  if (run) p.set('run', run)
  return `?${p.toString()}`
}

/** Seed ids are large block numbers; show them compactly but never alter the id used for requests. */
export const shortSeed = (seed: number): string => (seed >= 100000 ? `…${String(seed).slice(-3)}` : String(seed))
