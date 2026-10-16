// Pure logic of the forge workspace (unit tested). It formats and routes what the API returned; it never computes a
// physics result and never decides a verdict: statuses, scores and verdict fields are read from the records.
import type { ParamDiff } from '../demo/demoLogic'
import type {
  Arm, ArmSource, ChallengeRun, Creature, CreatureVersion, Controllers, Edit, Hypothesis, InvestigationRecord, InvestigationSummary, Job, JobEvent, JobPoll, Kind,
  LoopResult, ModelCall, Outcome, ProbesRecord, RankRow, SeedResult, ValidatedHypothesis, Verdict, VerdictStatus,
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

const SOURCE_LABEL: Record<string, string> = {
  nemotron: 'Nemotron', scripted_mock: 'Scripted mock', random_baseline: 'Random baseline', heuristic: 'Heuristic',
}

/** One line for the lineage: who proposed the change, what it was, and the recorded verdict summary. */
export function changeSummary(v: CreatureVersion): string {
  if (v.origin === 'user' || !v.change) return v.parent === null ? 'Drawn by you' : 'Saved by you'
  const ch = v.change
  const src = SOURCE_LABEL[ch.source ?? ''] ?? 'Accepted change'
  const ver = ch.verdict
  const verified = ver
    ? ver.n !== undefined ? `verified on ${ver.n} held-out seeds (${ver.wins ?? 0} wins / ${ver.losses ?? 0} losses / ${ver.ties ?? 0} ties)` : 'verified'
    : 'no verdict recorded'
  return `${src}: ${describeEdits(ch.edits as Edit[] | undefined)} \u00b7 ${verified}`
}

export function originLabel(o: 'user' | 'ai_accepted', source?: string): string {
  if (o === 'user') return 'Yours'
  if (source === 'scripted_mock') return 'Scripted mock change, accepted'
  if (source === 'random_baseline' || source === 'heuristic') return 'Baseline change, accepted'
  return 'AI change, accepted'
}

// ---- investigation record ---------------------------------------------------------------------------------------
export const ARM_CHIP: Record<ArmSource, { label: string; tone: string }> = {
  original: { label: 'ORIGINAL', tone: 'original' },
  nemotron: { label: 'NEMOTRON', tone: 'model' },
  scripted_mock: { label: 'SCRIPTED MOCK', tone: 'mock' },
  random_baseline: { label: 'RANDOM BASELINE', tone: 'random' },
  heuristic: { label: 'HEURISTIC', tone: 'heuristic' },
}

/** Chip for an arm. A scripted mock never wears the NEMOTRON label: the arm source and the record's provenance decide. */
export function armChip(arm: Pick<Arm, 'source'>, provenance: string | undefined): { label: string; tone: string } {
  if (arm.source === 'nemotron' && provenance === 'SCRIPTED_MOCK') return ARM_CHIP.scripted_mock
  return ARM_CHIP[arm.source] ?? { label: String(arm.source).toUpperCase(), tone: 'random' }
}

export const provenanceLabel = (p: string | undefined): string => (p === 'SCRIPTED_MOCK' ? 'SCRIPTED MOCK' : p === 'LIVE' ? 'LIVE' : String(p ?? 'unknown'))

export function armList(rec: InvestigationRecord): Arm[] {
  return Array.isArray(rec.arms) ? rec.arms : []
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
  const parts: string[] = []
  if (m.abs !== undefined) parts.push(`${m.abs} absolute`)
  if (m.rel !== undefined) parts.push(`${(m.rel * 100).toFixed(0)}% relative`)
  return parts.length ? parts.join(' and ') : m.required !== undefined ? String(m.required) : 'n/a'
}

const signed = (x: number, nd = 2): string => `${x >= 0 ? '+' : '-'}${Math.abs(x).toFixed(nd)}`

/** Plain wording of a recorded verdict. Counts, median and p come from the record; the status is never derived here. */
export function verdictText(v: Verdict | undefined): string {
  if (!v) return 'No verdict was recorded for this arm.'
  const n = v.n ?? ((v.wins ?? 0) + (v.losses ?? 0) + (v.ties ?? 0))
  const tally = `${v.wins ?? 0} wins / ${v.losses ?? 0} losses / ${v.ties ?? 0} ties`
  const unit = v.kind ? KIND_INFO[v.kind].unit : ''
  let head: string
  switch (v.status) {
    case 'VERIFIED_IMPROVEMENT': head = `Verified improvement on ${n} held-out seeds (${tally})`; break
    case 'WORSE': head = `Worse than the original on ${n} held-out seeds (${tally})`; break
    case 'NOT_VERIFIED': head = `Not verified on ${n} held-out seeds (${tally})`; break
    default:
      head = (v.wins ?? 0) === 0 && (v.losses ?? 0) === 0 && n > 0
        ? `No measurable effect on these seeds (all ${n} pairs tied)`
        : `Inconclusive: too few seeds differed to judge (${tally} of ${n})`
  }
  const bits: string[] = []
  if (v.median_diff !== undefined) bits.push(`median paired difference ${signed(v.median_diff)}${unit ? ` ${unit}` : ''}`)
  if (v.p_one_sided !== undefined) bits.push(`one-sided sign-test p = ${v.p_one_sided < 0.001 ? v.p_one_sided.toExponential(1) : v.p_one_sided.toFixed(3)}`)
  if (v.min_effect !== undefined) bits.push(`smallest effect that counts: ${fmtMinEffect(v.min_effect)}`)
  return `${head}.${bits.length ? ` ${bits[0].charAt(0).toUpperCase()}${bits.join('; ').slice(1)}.` : ''}`
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
  if (v.status === 'INCONCLUSIVE') return 'Only a verified improvement can be accepted. This arm was inconclusive: the held-out seeds could not tell it apart from the original.'
  return `Only a verified improvement can be accepted. This arm's verdict is "${VERDICT_LABEL[v.status] ?? v.status}".`
}

/** Round 2+ of a loop evaluates the unaccepted proposal of an earlier round as its parent. */
export const isHypothetical = (rec: InvestigationRecord): boolean => !!rec.creature.hypothetical_parent

export function hypotheticalNote(rec: InvestigationRecord): string | null {
  if (!isHypothetical(rec)) return null
  return `Round ${rec.creature.round ?? '?'} evaluated an earlier, unaccepted proposal as its starting point. A change verified here cannot be accepted directly: accept the earlier arm first, or investigate the resulting version.`
}

const PARAM_LABEL: Record<string, string> = {
  torso_mass: 'torso mass', thigh_length: 'thigh length', shank_length: 'shank length', foot_length: 'foot length', foot_friction: 'foot grip',
  torque_limit: 'motor strength', leg_density: 'leg density',
}
const TARGET_LABEL: Record<string, string> = { both: 'both legs', rear: 'rear leg', front: 'front leg' }

/** One edit in plain language, e.g. "rear leg: foot length x 1.25". */
export function describeEdit(e: Edit): string {
  const name = PARAM_LABEL[e.param] ?? e.param.replace('.', ' ').replace(/_/g, ' ')
  const where = e.target && e.param in PARAM_LABEL ? `${TARGET_LABEL[e.target] ?? e.target}: ` : ''
  return `${where}${name} ${e.op === 'scale' ? `x ${Number(e.value.toPrecision(3))}` : `set to ${Number(e.value.toPrecision(4))}`}`
}
export const describeEdits = (edits: Edit[] | undefined): string => (edits && edits.length ? edits.map(describeEdit).join('; ') : 'no change')

const asNum = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null)

/** Per-seed scores of one arm: `which` picks the held-out validation results or the screening results. */
export function armScores(rec: InvestigationRecord, armId: string, which: 'validation' | 'screening' = 'validation'): { seed: number; score: number }[] {
  const res = (which === 'validation' ? rec.validation_results : rec.screening)?.[armId]
  return (res?.seeds ?? []).flatMap((r) => {
    const score = asNum(r.score)
    return score !== null && r.outcome !== 'ERROR' ? [{ seed: r.seed, score }] : []
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

export interface ProbeRow {
  probe_id: string
  transformation: string
  hypothesis: string | null
  expect: string | null
  observed: string | null
  verdict: 'CONFIRMED' | 'REFUTED' | 'NOT EVALUATED'
  detail: string
}

/** Each requested probe: what was changed, what the model expected, what MuJoCo observed (the record's own deterministic check). */
export function probeRows(pr: ProbesRecord | null | undefined, kind?: Kind): ProbeRow[] {
  if (!pr) return []
  const unit = kind ? KIND_INFO[kind].unit : (pr.kind ? KIND_INFO[pr.kind].unit : '')
  const exps = pr.expectations ?? []
  const ids = exps.length ? exps.map((e) => e.probe_id) : (pr.requested ?? []).map((r) => r.probe_id)
  return ids.map((id) => {
    const e = exps.find((x) => x.probe_id === id) ?? (pr.requested ?? []).find((x) => x.probe_id === id) ?? { probe_id: id }
    const r = pr.results?.[id]
    const confirmed = 'confirmed' in e ? (e as { confirmed?: boolean | null }).confirmed : undefined
    let detail: string
    if (!r) detail = 'No result was recorded for this probe.'
    else if (r.status !== 'ok') detail = `The probe could not run${r.error ? `: ${r.error}` : ''}.`
    else if (r.median_delta !== undefined && r.median_delta !== null) {
      detail = `Median change ${signed(r.median_delta)}${unit ? ` ${unit}` : ''} over ${r.n_seeds ?? '?'} probe seeds (${r.wins ?? 0} better / ${r.losses ?? 0} worse / ${r.ties ?? 0} tied).`
    } else if (r.static_fall_frac !== undefined && r.static_fall_frac !== null) {
      detail = `Measurement only, no comparison: median survival ${r.median ?? 'n/a'} s; fell without a push in ${(r.static_fall_frac * 100).toFixed(0)}% of seeds.`
    } else detail = 'Measurement only, no comparison.'
    return {
      probe_id: id, transformation: r?.transformation ?? 'transformation not recorded', hypothesis: e.hypothesis ?? null, expect: e.expect ?? null,
      observed: (e as { observed?: string | null }).observed ?? null,
      verdict: confirmed === true ? 'CONFIRMED' : confirmed === false ? 'REFUTED' : 'NOT EVALUATED', detail,
    }
  })
}

export type Scalar = string | number | boolean | null | undefined
export interface ArmView { arm_id: string; chip: { label: string; tone: string }; edits: string; verdict: Verdict | undefined; text: string; rollouts?: number }

/** The arm the arena selected, its matched-random twin (same proposal, same size of edit) and the best baseline arm. */
export function validationTriplet(rec: InvestigationRecord): { ai: Arm | null; twin: Arm | null; baseline: Arm | null } {
  const arms = armList(rec)
  const byId = (id: string | null | undefined) => arms.find((a) => a.arm_id === id) ?? null
  const ai = byId(rec.selection?.ai)
  let twin = byId(rec.selection?.matched_twin)
  if (!twin && ai?.proposal_id) {
    // records written before the arena recorded the twin: the twin is the random arm of the same proposal, if it was validated
    twin = arms.find((a) => a.source === 'random_baseline' && a.proposal_id === ai.proposal_id && !!rec.verdicts?.[a.arm_id]) ?? null
  }
  let baseline = byId(rec.selection?.baseline)
  if (baseline && twin && baseline.arm_id === twin.arm_id) baseline = null
  return { ai, twin, baseline }
}

export function armView(rec: InvestigationRecord, arm: Arm): ArmView {
  const v = rec.verdicts?.[arm.arm_id]
  return { arm_id: arm.arm_id, chip: armChip(arm, rec.provenance), edits: describeEdits(arm.edits), verdict: v, text: verdictText(v), rollouts: arm.rollouts?.total }
}

export type TimelineStep =
  | { kind: 'evidence'; id: string; keys: string[]; bytes: number }
  | { kind: 'model_call'; id: string; call: ModelCall; tokens: number | null }
  | { kind: 'probes'; id: string; rows: ProbeRow[]; seeds: number; rollouts: number | null; skipped: string | null }
  | { kind: 'hypotheses'; id: string; summary: string | null; items: (Hypothesis & { cited: { path: string; value: Scalar }[] })[] }
  | { kind: 'proposals'; id: string; items: { id: string; status: 'accepted' | 'rejected'; reasons: string[]; hypothesis?: string; expected?: string; edits: string }[] }
  | { kind: 'arena'; id: string; arms: (ArmView & { unavailable?: string; error?: string | null })[]; screenSeeds: number; validateSeeds: number }
  | { kind: 'screening'; id: string; rule: string | null; ai: RankRow[]; baseline: RankRow[]; selected: { ai: string | null; baseline: string | null; twin: string | null }; excluded: string[] }
  | { kind: 'validation'; id: string; seeds: number; ai: ArmView | null; twin: ArmView | null; baseline: ArmView | null; others: ArmView[] }
  | { kind: 'failure'; id: string; status: string; message: string }

export const STATUS_TEXT: Record<string, string> = {
  done: 'Completed', model_failed: 'The model step failed', no_valid_proposals: 'The model gave no valid proposal', cancelled: 'Cancelled', failed: 'Failed',
}

/** Ordered timeline of a finished investigation record: evidence, model call, hypotheses, proposals, arms, screening, validation. */
export function buildTimeline(rec: InvestigationRecord): TimelineStep[] {
  const steps: TimelineStep[] = []
  if (rec.evidence) steps.push({ kind: 'evidence', id: 'evidence', keys: Object.keys(rec.evidence), bytes: JSON.stringify(rec.evidence).length })
  ;(rec.model_calls ?? []).forEach((call, i) => {
    const u = call.usage
    const tokens = u ? (u.total_tokens ?? ((u.prompt_tokens ?? 0) + (u.completion_tokens ?? 0))) : null
    steps.push({ kind: 'model_call', id: `call-${i}`, call, tokens })
  })
  if (rec.probes && ((rec.probes.requested ?? []).length > 0 || rec.probes.skipped)) {
    steps.push({ kind: 'probes', id: 'probes', rows: probeRows(rec.probes, rec.spec?.kind), seeds: rec.probes.seeds?.length ?? 0, rollouts: rec.probes.rollouts ?? null, skipped: rec.probes.skipped ?? null })
  }
  const hyps: ValidatedHypothesis[] = rec.validation?.hypotheses ?? rec.reply?.diagnosis?.hypotheses ?? []
  if (hyps.length) {
    steps.push({
      kind: 'hypotheses', id: 'hypotheses', summary: rec.reply?.diagnosis?.summary ?? null,
      items: hyps.map((h) => ({
        ...h,
        cited: (h.evidence ?? []).map((path) => ({ path, value: h.values && path in h.values ? h.values[path] : resolveCitation(rec.evidence, path) })),
      })),
    })
  }
  const vprops = rec.validation?.proposals ?? []
  if (vprops.length) {
    steps.push({
      kind: 'proposals', id: 'proposals',
      items: vprops.map((p) => ({ id: p.id, status: p.status, reasons: p.reasons ?? [], hypothesis: p.hypothesis, expected: p.prediction?.expected_change, edits: describeEdits(p.edits) })),
    })
  }
  const arms = armList(rec)
  if (arms.length) {
    steps.push({
      kind: 'arena', id: 'arena', screenSeeds: rec.seeds?.screen?.length ?? 0, validateSeeds: rec.seeds?.validate?.length ?? 0,
      arms: arms.map((a) => ({ ...armView(rec, a), unavailable: a.unavailable, error: a.error })),
    })
  }
  const sel = rec.selection
  if (sel?.ranking) {
    steps.push({
      kind: 'screening', id: 'screening', rule: sel.rule ?? null, ai: sel.ranking.ai ?? [], baseline: sel.ranking.baseline ?? [],
      selected: { ai: sel.ai ?? null, baseline: sel.baseline ?? null, twin: validationTriplet(rec).twin?.arm_id ?? null },
      excluded: Object.entries(sel.excluded ?? {}).map(([k, v]) => `${k}: ${v}`),
    })
  }
  const { ai, twin, baseline } = validationTriplet(rec)
  const shown = new Set([ai?.arm_id, twin?.arm_id, baseline?.arm_id])
  const others = arms.filter((a) => a.source !== 'original' && rec.verdicts?.[a.arm_id] && !shown.has(a.arm_id)).map((a) => armView(rec, a))
  if (ai || twin || baseline || others.length) {
    steps.push({
      kind: 'validation', id: 'validation', seeds: rec.seeds?.validate?.length ?? 0,
      ai: ai ? armView(rec, ai) : null, twin: twin ? armView(rec, twin) : null, baseline: baseline ? armView(rec, baseline) : null, others,
    })
  }
  if (rec.status !== 'done' || rec.error) {
    steps.push({ kind: 'failure', id: 'failure', status: rec.status, message: rec.error ?? STATUS_TEXT[rec.status] ?? rec.status })
  }
  return steps
}

export const isModelFailed = (rec: InvestigationRecord): boolean => rec.status === 'model_failed'

/** Budget of an investigation as one line, every number from the record. */
export function budgetLine(b: InvestigationRecord['budget']): string {
  if (!b) return 'No budget was recorded.'
  const parts: string[] = []
  if (b.rollouts !== undefined) parts.push(`${b.rollouts.toLocaleString()} physics rollouts`)
  if (b.wall_s !== undefined) parts.push(`${b.wall_s.toFixed(0)} s`)
  if (b.calls !== undefined) parts.push(`${b.calls} model call${b.calls === 1 ? '' : 's'}`)
  if (b.tokens !== undefined) parts.push(`${b.tokens.toLocaleString()} tokens`)
  if (b.usd !== undefined) parts.push(`$${b.usd.toFixed(4)}`)
  return parts.join(', ')
}

// ---- live progress of an investigation job ------------------------------------------------------------------------
export const STAGES = ['evidence', 'model', 'arms', 'screen', 'validate', 'verdict'] as const
export const PROBE_EVENTS = ['probe_request', 'probe_result']
export type Stage = (typeof STAGES)[number]
export const STAGE_LABEL: Record<Stage, string> = {
  evidence: 'Evidence', model: 'Model', arms: 'Build arms', screen: 'Screen', validate: 'Validate', verdict: 'Verdict',
}

/** Which of the six stages are done / active / pending, from the job's own events. */
export function stageStates(events: JobEvent[]): Record<Stage, 'done' | 'active' | 'pending'> {
  let latest = -1
  for (const e of events) {
    const p = typeof e.data.phase === 'string' ? e.data.phase : null
    let idx = -1
    if (e.type === 'phase' && p === 'evidence') idx = 0
    else if (e.type === 'model_request' || e.type === 'model_response') idx = 1
    else if (e.type === 'phase' && p === 'arms') idx = 2
    else if (e.type === 'phase' && (p === 'screen' || p === 'build' || p === 'retune' || p === 'arena')) idx = 3
    else if (e.type === 'phase' && p === 'validate') idx = 4
    else if (e.type === 'verdict') idx = 5
    latest = Math.max(latest, idx)
  }
  const out = {} as Record<Stage, 'done' | 'active' | 'pending'>
  STAGES.forEach((s, i) => { out[s] = i < latest ? 'done' : i === latest ? 'active' : 'pending' })
  return out
}

/** The model response card the moment its event arrives (before the investigation record exists). */
export function modelResponseOf(events: JobEvent[]): ModelCall | null {
  const e = [...events].reverse().find((x) => x.type === 'model_response')
  if (!e) return null
  const d = e.data as Record<string, unknown>
  return {
    model: String(d.model ?? 'unknown'), request_id: (d.request_id as string | null) ?? null, latency_s: asNum(d.latency_s), usage: (d.usage as ModelCall['usage']) ?? null,
    cost_usd: asNum(d.cost_usd), finish_reason: (d.finish_reason as string | null) ?? null, error: (d.error as string | null) ?? null, ok: d.ok as boolean | undefined,
  }
}

export const STOP_TEXT: Record<string, string> = {
  no_verified_arm: 'Stopped: two rounds in a row produced no verified change.',
  max_rounds: 'Stopped: the round limit was reached.',
  max_rollouts: 'Stopped: the physics budget was used up.',
  max_model_calls: 'Stopped: the model-call limit was reached.',
  wall_clock: 'Stopped: the time limit was reached.',
  cancelled: 'Stopped: cancelled.',
}
export function stopText(reason: string): string {
  return STOP_TEXT[reason] ?? (reason.startsWith('round_status:') ? `Stopped: a round ended as "${reason.slice(13)}".` : `Stopped: ${reason}.`)
}

/** Result summary of a loop job; it never accepts anything for the user. */
export function loopLines(l: LoopResult): string[] {
  const lines = l.rounds.map((r) => `Round ${r.round}: ${r.status === 'done' ? (r.best_verified_arm ? `verified change ${r.best_verified_arm}` : 'no verified change') : (STATUS_TEXT[r.status] ?? r.status)}${r.hypothetical_parent ? ' (on an unaccepted earlier proposal)' : ''}`)
  lines.push(stopText(l.stop_reason))
  lines.push(l.auto_accepted ? 'A change was accepted automatically.' : 'Nothing was accepted for you. Open a round below and accept it yourself.')
  return lines
}

/** Chips for the creature's investigation list. */
export function summaryChips(s: InvestigationSummary): { label: string; tone: string }[] {
  const chips = [{ label: provenanceLabel(s.provenance), tone: s.provenance === 'SCRIPTED_MOCK' ? 'mock' : 'ok' }]
  chips.push({ label: STATUS_TEXT[s.status] ?? s.status, tone: s.status === 'done' ? 'ok' : 'bad' })
  const verified = Object.values(s.verdicts ?? {}).filter((x) => x === 'VERIFIED_IMPROVEMENT').length
  if (verified) chips.push({ label: 'VERIFIED CHANGE', tone: 'ok' })
  return chips
}
export const newestFirst = (l: InvestigationSummary[]): InvestigationSummary[] => [...l].sort((a, b) => b.created.localeCompare(a.created) || b.id.localeCompare(a.id))

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
