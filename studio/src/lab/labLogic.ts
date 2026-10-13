// Pure presentation logic for the Investigation Lab (unit tested). No simulation happens here.
import type { LabRow, LabView, MetricPair, TrialStatus } from './labTypes'

export type Tone = 'ok' | 'bad' | 'warn' | 'muted'

export const STATUS_INFO: Record<string, { label: string; tone: Tone; summary: string }> = {
  accepted: { label: 'Accepted', tone: 'ok', summary: 'MuJoCo verified that the proposed change helps.' },
  rejected_by_verifier: {
    label: 'Rejected by MuJoCo',
    tone: 'bad',
    summary: 'The model’s change did not pass independent verification.',
  },
  invalid_model_output: {
    label: 'Invalid response',
    tone: 'warn',
    summary: 'The reply broke the answer rules, so it was never tested in MuJoCo.',
  },
  model_error: { label: 'Model error', tone: 'warn', summary: 'The model request failed; nothing was tested.' },
  budget_exceeded: { label: 'Stopped by budget', tone: 'warn', summary: 'A request or token limit stopped this run before a model call.' },
  started: { label: 'Incomplete', tone: 'muted', summary: 'This record stops before a verdict was saved.' },
  unreadable: { label: 'Unreadable', tone: 'muted', summary: 'The record file could not be read.' },
}

export function statusInfo(status: TrialStatus) {
  return STATUS_INFO[status] ?? { label: String(status), tone: 'muted' as Tone, summary: 'Unknown record status.' }
}

export const STEPS = ['observe', 'hypothesize', 'intervene', 'verify', 'compare'] as const
export type Step = (typeof STEPS)[number]

export const STEP_TITLE: Record<Step, string> = {
  observe: 'Observe',
  hypothesize: 'Hypothesize',
  intervene: 'Intervene',
  verify: 'Verify',
  compare: 'Compare',
}

const SECTION_OF: Record<Step, keyof LabView['sections']> = {
  observe: 'observe',
  hypothesize: 'hypothesis',
  intervene: 'intervene',
  verify: 'verify',
  compare: 'compare',
}

/** Whether a step has data to show, and if not, a plain-language reason. */
export function stepState(view: LabView, step: Step): { ready: boolean; reason?: string } {
  if (view.sections[SECTION_OF[step]]) return { ready: true }
  const invalid = view.outcome.status === 'invalid_model_output'
  switch (step) {
    case 'observe':
      return { ready: false, reason: 'No observed evidence was saved with this record.' }
    case 'hypothesize':
      return {
        ready: false,
        reason: invalid
          ? 'The model’s reply was rejected as invalid, so there is no accepted hypothesis.'
          : 'No hypothesis was recorded.',
      }
    case 'intervene':
      return { ready: false, reason: 'No valid change was proposed, so nothing was applied.' }
    case 'verify':
      return { ready: false, reason: 'MuJoCo did not test anything because there was no valid change to test.' }
    case 'compare':
      return { ready: false, reason: 'There is no modified robot to compare with the original failure.' }
  }
}

export function parseDeepLink(search: string): { trial: string | null; step: Step | null } {
  const q = new URLSearchParams(search)
  const step = q.get('step')
  return { trial: q.get('trial'), step: (STEPS as readonly string[]).includes(step ?? '') ? (step as Step) : null }
}

export const METRIC_LABEL: Record<string, string> = {
  fall_rate: 'fall rate',
  mean_min_torso_height: 'lowest torso height (mean)',
  mean_max_abs_pitch: 'largest torso tilt (mean)',
}

export const metricLabel = (m: string) => METRIC_LABEL[m] ?? m.replace(/_/g, ' ')

export const pct = (x: number | null | undefined) => (x == null ? '—' : `${Math.round(x * 100)}%`)

export function fmtNum(x: number | null | undefined, digits = 3): string {
  return x == null || !Number.isFinite(x) ? '—' : x.toFixed(digits)
}

export function fmtDelta(x: number, digits = 3): string {
  const s = x.toFixed(digits)
  return x > 0 ? `+${s}` : s
}

/** Unit-aware value for one metric from the screening table. */
export function fmtMetric(metric: string, x: number): string {
  if (metric === 'fall_rate') return pct(x)
  if (metric === 'mean_max_abs_pitch') return `${((x * 180) / Math.PI).toFixed(1)}°`
  return `${x.toFixed(3)} m`
}

export function predictionVerdict(held: boolean | null | undefined): { text: string; tone: Tone } {
  if (held === true) return { text: 'held', tone: 'ok' }
  if (held === false) return { text: 'did not hold', tone: 'bad' }
  return { text: 'not tested', tone: 'muted' }
}

export function directionWord(direction: string): string {
  return direction === 'decrease' ? 'go down' : direction === 'increase' ? 'go up' : direction
}

export interface ChangeRow {
  name: string
  original: number
  modified: number
  changed: boolean
}

export function changeRows(original: Record<string, number>, modified: Record<string, number>): ChangeRow[] {
  return Object.keys(original).map((name) => ({
    name,
    original: original[name],
    modified: modified[name],
    changed: original[name] !== modified[name],
  }))
}

export function metricRows(obs: Record<string, MetricPair>): { metric: string; pair: MetricPair }[] {
  return Object.keys(obs).map((metric) => ({ metric, pair: obs[metric] }))
}

export function filterRows(rows: LabRow[], filter: 'all' | 'accepted' | 'rejected' | 'invalid'): LabRow[] {
  if (filter === 'all') return rows
  const want: Record<string, string[]> = {
    accepted: ['accepted'],
    rejected: ['rejected_by_verifier'],
    invalid: ['invalid_model_output', 'model_error', 'budget_exceeded', 'unreadable', 'started'],
  }
  return rows.filter((r) => want[filter].includes(r.status))
}

export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return 'unknown time'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? 'unknown time' : d.toISOString().replace('T', ' ').slice(0, 16) + ' UTC'
}

export const FORENSIC_LABEL: Record<string, string> = {
  fall_time_s: 'Fell at (s)',
  instability_onset_s: 'Became unstable at (s)',
  xcom_margin_recovered_s: 'Balance recovered at (s)',
  support_length_before_push_m: 'Foot support length before push (m)',
  com_margin_before_push_m: 'Balance margin before push (m)',
  peak_abs_pitch_within_1s_rad: 'Peak tilt in the 1 s after the push (rad)',
  ankle_demand_over_limit_peak: 'Peak ankle torque demand ÷ limit',
  peak_slip_speed_mps: 'Peak foot slip speed (m/s)',
}

export function fmtForensic(key: string, v: number | null): string {
  if (v === null || v === undefined) return key === 'xcom_margin_recovered_s' ? 'never' : '—'
  return v.toFixed(3)
}

/** "0–4" for a consecutive run, otherwise "0, 2, 5". */
export function fmtSeeds(seeds: number[]): string {
  const s = [...seeds].sort((a, b) => a - b)
  if (s.length > 2 && s.every((v, i) => i === 0 || v === s[i - 1] + 1)) return `${s[0]}–${s[s.length - 1]}`
  return s.join(', ')
}

/** Wording for the screening table, derived only from the seed sets saved with the record. */
export function screeningText(evidence: number[] | null, screening: number[] | null): { title: string; note: string; count: string } {
  if (!screening || screening.length === 0)
    return { title: 'Screening', note: 'This record does not list its screening seeds.', count: 'screening seeds' }
  const count = `${screening.length} screening seed${screening.length === 1 ? '' : 's'}`
  const title = `Screening: seeds ${fmtSeeds(screening)}`
  if (!evidence || evidence.length === 0) return { title, note: 'The evidence seeds were not recorded.', count }
  const ev = new Set(evidence)
  const same = screening.length === ev.size && screening.every((s) => ev.has(s))
  const overlap = screening.filter((s) => ev.has(s))
  const fresh = screening.filter((s) => !ev.has(s))
  let note: string
  if (same) note = `The same seeds (${fmtSeeds(evidence)}) the model saw evidence from.`
  else if (overlap.length === 0) note = `None of these overlap the evidence seeds (${fmtSeeds(evidence)}).`
  else
    note =
      `The evidence came from seeds ${fmtSeeds(evidence)}; screening re-uses ${overlap.length === evidence.length ? 'all of them' : `seeds ${fmtSeeds(overlap)}`}` +
      ` and adds ${fresh.length === 0 ? 'none' : `seeds ${fmtSeeds(fresh)}`}.`
  return { title, note, count }
}
