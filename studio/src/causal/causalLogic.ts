// Pure display logic of the causal-engineer page. Nothing here invents text: it only reshapes what the record contains.
import type { CausalIndexRow, CausalRecord, Experiment, Hypothesis, MemoryItem, Prediction, ScoredPrediction, Step } from './causalTypes'

export type Tone = 'ok' | 'warn' | 'bad' | 'muted'

/** Outcome of the independent verification (full_recovery_v1), worded as the verifier states it. */
export function statusInfo(status: string | null | undefined): { label: string; tone: Tone } {
  switch (status) {
    case 'FULL_RECOVERY': return { label: 'Fully recovered', tone: 'ok' }
    case 'PARTIAL_IMPROVEMENT': return { label: 'Partly improved', tone: 'warn' }
    case 'NOT_RECOVERED': return { label: 'Not recovered', tone: 'bad' }
    case 'ERROR': return { label: 'Error', tone: 'muted' }
    default: return { label: status ? status.toLowerCase().replace(/_/g, ' ') : 'No verdict', tone: 'muted' }
  }
}

export const fmtCost = (usd: number | null | undefined): string =>
  usd == null ? 'n/a' : usd < 0.1 ? `$${usd.toFixed(3)}` : `$${usd.toFixed(2)}`

export const fmtPct = (x: number | null | undefined): string => (x == null ? 'n/a' : `${Math.round(x * 100)}%`)

/** `no_change` reads "no change"; everything else is shown as stored. */
export const directionWord = (d: string | null | undefined): string => (d == null ? 'not defined' : d === 'no_change' ? 'no change' : d)

export function fmtNum(x: number | null | undefined, digits = 3): string {
  if (x == null || !Number.isFinite(x)) return 'n/a'
  const a = Math.abs(x)
  if (a !== 0 && (a < 0.001 || a >= 10000)) return x.toExponential(2)
  return Number(x.toPrecision(digits)).toString()
}

export const fmtDelta = (x: number | null | undefined): string => (x == null || !Number.isFinite(x) ? 'n/a' : `${x > 0 ? '+' : ''}${fmtNum(x)}`)

export const categoryLabel = (c: string | null | undefined): string => (c ? c.replace(/_/g, ' ') : 'none')

export function robotSummary(r: CausalIndexRow['robot']): string {
  return `leg ${r.leg_length.toFixed(2)} m, torso ${r.torso_mass.toFixed(1)} kg, foot ${(r.foot_length * 100).toFixed(1)} cm, friction ${r.foot_friction.toFixed(2)}`
}

// ---- hypothesis ledger over time

export interface HypothesisState {
  id: string
  status: string
  confidence: number
  reason: string
  experiments: string[]
  cited: { n_scored: number; n_correct: number } | null
  changedAt: number
  created: number
  mechanism: string
  causal_chain: string
  category: string
  evidence: string[]
  /** Statuses it has had up to and including the step, oldest first. */
  path: string[]
}

/** State of one hypothesis after step k: the last history entry with step <= k. Null if it did not exist yet. */
export function hypothesisAt(h: Hypothesis, k: number): HypothesisState | null {
  const hist = (h.history ?? []).filter((e) => e.step <= k)
  if (!hist.length) return null
  const last = hist[hist.length - 1]
  const path: string[] = []
  for (const e of hist) if (path[path.length - 1] !== e.status) path.push(e.status)
  return {
    id: h.id, status: last.status, confidence: last.confidence, reason: last.reason, experiments: last.experiments ?? [],
    cited: last.cited_predictions ?? null, changedAt: last.step, created: h.created_step, mechanism: h.mechanism, causal_chain: h.causal_chain,
    category: h.category, evidence: h.evidence ?? [], path,
  }
}

const idNum = (id: string) => parseInt(id.replace(/\D/g, ''), 10) || 0

/** The ledger as it stood after step k, ordered by id. */
export function ledgerAt(hyps: Record<string, Hypothesis>, k: number): HypothesisState[] {
  return Object.values(hyps).map((h) => hypothesisAt(h, k)).filter((x): x is HypothesisState => x !== null).sort((a, b) => idNum(a.id) - idNum(b.id))
}

export function statusCounts(states: HypothesisState[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const s of states) out[s.status] = (out[s.status] ?? 0) + 1
  return out
}

export const hypothesisTone = (status: string): Tone =>
  status === 'supported' ? 'ok' : status === 'refuted' ? 'bad' : status === 'unresolved' ? 'warn' : 'muted'

// ---- experiments

export function experimentMap(rec: CausalRecord): Record<string, Experiment> {
  return Object.fromEntries(rec.experiments.map((e) => [e.id, e]))
}

/** Experiments and repairs produced by a step, in id order. A step lists them in `experiments`; fall back to the experiments' own step field. */
export function stepExperiments(rec: CausalRecord, step: Step): Experiment[] {
  const map = experimentMap(rec)
  const ids = step.experiments?.length ? step.experiments : rec.experiments.filter((e) => e.step === step.step && e.kind !== 'observe').map((e) => e.id)
  return ids.map((id) => map[id]).filter((e): e is Experiment => !!e)
}

export interface ScoreTally { correct: number; incorrect: number; unscored: number; total: number }
export function scoreTally(scoring: ScoredPrediction[] | undefined): ScoreTally {
  const t = { correct: 0, incorrect: 0, unscored: 0, total: 0 }
  for (const s of scoring ?? []) {
    t.total += 1
    if (s.status === 'correct') t.correct += 1
    else if (s.status === 'incorrect') t.incorrect += 1
    else t.unscored += 1
  }
  return t
}

/** Pre-registered predictions joined to their scores (same order). A prediction without a score is shown as not scored. */
export function predictionRows(e: Experiment): { pred: Prediction; score: ScoredPrediction | null }[] {
  const scores = [...(e.scoring ?? [])]
  return (e.predictions ?? []).map((pred) => {
    const i = scores.findIndex((s) => s.hypothesis === pred.hypothesis && s.quantity === pred.quantity && s.predicted === pred.direction)
    const score = i >= 0 ? scores.splice(i, 1)[0] : null
    return { pred, score }
  })
}

export const scoreTone = (status: string | undefined): Tone => (status === 'correct' ? 'ok' : status === 'incorrect' ? 'bad' : 'muted')

/** "walking 0 -> 1 of 4 seeds" for a counterfactual; falls back to what the record has. */
export function walkingChange(e: Experiment): { before: number; after: number; of: number | null } | null {
  const o = e.outcome
  if (o && typeof o.n_walking === 'number' && typeof o.n_walking_base === 'number') {
    const of = typeof o.n_fell === 'number' ? o.n_walking + o.n_fell : null
    return { before: o.n_walking_base, after: o.n_walking, of }
  }
  if (e.kind === 'repair' && typeof e.train_walking === 'number' && typeof e.start_walking === 'number') {
    return { before: e.start_walking, after: e.train_walking, of: e.n_train ?? null }
  }
  return null
}

export function repairLine(e: Experiment): string {
  const parts = [`tool ${e.tool ?? 'unknown'}`]
  if (e.hypothesis) parts.push(`directed by ${e.hypothesis}`)
  if (e.budget != null) parts.push(`budget ${e.budget} rollouts${e.budget_share != null ? ` (${Math.round(e.budget_share * 100)}% of the total)` : ''}`)
  if (e.rollouts_used != null) parts.push(`${e.rollouts_used} used`)
  return parts.join(', ')
}

export function stepTitle(step: Step): string {
  const n = step.step
  switch (step.action) {
    case 'counterfactual': return `Step ${n}: ran an experiment`
    case 'repair': return `Step ${n}: ran a repair`
    case 'conclude': return `Step ${n}: concluded`
    default: return `Step ${n}: ${step.status && step.status !== 'ok' ? 'the model reply could not be used' : 'no action'}`
  }
}

// ---- memory

export const MEMORY_VERDICTS = ['applies', 'needs_adaptation', 'test_first', 'does_not_apply'] as const
export function memoryVerdictInfo(v: string): { label: string; tone: Tone } {
  switch (v) {
    case 'applies': return { label: 'applies', tone: 'ok' }
    case 'needs_adaptation': return { label: 'needs adaptation', tone: 'warn' }
    case 'test_first': return { label: 'test first', tone: 'warn' }
    case 'does_not_apply': return { label: 'does not apply', tone: 'muted' }
    default: return { label: v.replace(/_/g, ' '), tone: 'muted' }
  }
}

export interface MemoryUse { item: MemoryItem; verdict: string | null; reason: string | null; step: number | null; citedInSteps: number[] }

/** Each retrieved item with the model's latest verdict and the steps whose model text mentions its id. */
export function memoryUse(rec: CausalRecord): MemoryUse[] {
  const items = rec.memory?.items ?? []
  return items.map((item) => {
    const a = rec.memory.assessments?.[item.id]
    const re = idRegex(item.id)
    const cited = rec.steps.filter((s) => re.test(modelText(s))).map((s) => s.step)
    return { item, verdict: a?.verdict ?? null, reason: a?.reason ?? null, step: a?.step ?? null, citedInSteps: cited }
  })
}

function modelText(s: Step): string {
  const p = s.parsed
  if (!p) return ''
  return [p.result_reading, ...(p.status_updates ?? []).map((u) => u.reason), ...(p.new_hypotheses ?? []).flatMap((h) => [h.mechanism, h.causal_chain]),
    ...(p.conclude ?? []).map((c) => c.explanation), ...(p.memory_assessments ?? []).map((m) => m.reason)].filter(Boolean).join('\n')
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const idRegex = (id: string) => new RegExp(`(?<![A-Za-z0-9_-])${escapeRe(id)}(?![A-Za-z0-9_-])`)

export type Segment = { text: string; item?: string }
/** Split model text so every mention of a retrieved memory item id can become a link. Whole-token matches only. */
export function linkifyIds(text: string, ids: string[]): Segment[] {
  if (!text) return []
  if (!ids.length) return [{ text }]
  const re = new RegExp(`(?<![A-Za-z0-9_-])(${[...ids].sort((a, b) => b.length - a.length).map(escapeRe).join('|')})(?![A-Za-z0-9_-])`, 'g')
  const out: Segment[] = []
  let last = 0
  for (const m of text.matchAll(re)) {
    const i = m.index ?? 0
    if (i > last) out.push({ text: text.slice(last, i) })
    out.push({ text: m[0], item: m[0] })
    last = i + m[0].length
  }
  if (last < text.length) out.push({ text: text.slice(last) })
  return out
}

// ---- headline / claims vs verification

export function headline(rec: CausalRecord): string {
  const v = statusInfo(rec.verification.status)
  const calls = rec.llm?.calls ?? 0
  const n = (k: number, w: string) => `${k} ${w}${k === 1 ? '' : 's'}`
  const cf = rec.experiments.filter((e) => e.kind === 'counterfactual').length
  const rp = rec.experiments.filter((e) => e.kind === 'repair').length
  return `${v.label}: the independent check found ${fmtPct(rec.verification.walking_frac)} of its hidden test starts walking. ${n(rec.steps.length, 'step')}, ${n(cf, 'experiment')}, ${n(rp, 'repair')}, ${n(calls, 'model call')}, ${fmtCost(rec.llm?.cost_usd)}.`
}

export function diagnosisVerdict(ev: CausalRecord['evaluation_only']): string {
  if (ev.diagnosis_match === true) return 'The AI named the injected mechanism.'
  if (ev.diagnosis_match === false) return ev.diagnosis_category === 'unresolved' ? 'The AI did not name a mechanism (unresolved).' : 'The AI named a different mechanism than the injected one.'
  return 'The AI gave no diagnosis.'
}

/** Count of the AI's own training-seed claims: repairs that reached walking on the seeds the AI could see. */
export function selfClaim(rec: CausalRecord): { repairs: number; trainWalking: { tool: string; before: number; after: number; of: number | null }[] } {
  const reps = rec.experiments.filter((e) => e.kind === 'repair')
  return {
    repairs: reps.length,
    trainWalking: reps.map((e) => ({ tool: e.tool ?? 'unknown', before: e.start_walking ?? 0, after: e.train_walking ?? 0, of: e.n_train ?? null })),
  }
}

export function stepErrors(step: Step): string[] {
  return [...(step.validation_errors ?? [])]
}
