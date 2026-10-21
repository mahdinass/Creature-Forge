// Pure helpers for the DO-1 recovery page (unit tested). Every number is derived from the verified export or the
// verifier's recorded outcome; nothing here restates a result.
import type { DesignId, Do1Index, Do1Row, RowGroup } from './do1Types'

export const DESIGNS: DesignId[] = ['faulty', 'frozen', 'do1']
export const DESIGN_NAME: Record<DesignId, string> = { faulty: 'Faulty robot', frozen: 'Frozen optimizer repair', do1: 'DO-1 optimizer repair' }
export const DESIGN_SHORT: Record<DesignId, string> = { faulty: 'faulty', frozen: 'frozen', do1: 'DO-1' }
export const DESIGN_COLOR: Record<DesignId, string> = { faulty: '#e5484d', frozen: '#f2b441', do1: '#4fd18b' }

export function walkingCount(rows: Do1Row[]): number {
  return rows.filter((r) => r.walking).length
}

export function median(xs: number[]): number {
  if (xs.length === 0) return NaN
  const s = [...xs].sort((a, b) => a - b)
  const m = s.length >> 1
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** Walking seeds needed for an aggregate PASS under the recorded criterion (full_recovery_v1: >= pass_frac of seeds). */
export function requiredWalking(passFrac: number, n: number): number {
  return Math.ceil(passFrac * n - 1e-9)
}

/** Aggregates recomputed from the per-seed rows, checked against the exporter's own aggregates (a mismatch is an error). */
export function aggregateOf(idx: Do1Index, g: RowGroup): { walking: number; n: number; median: number } {
  const rows = idx.rows[g]
  const a = { walking: walkingCount(rows), n: rows.length, median: median(rows.map((r) => r.score)) }
  if (a.walking !== idx.aggregates.walking[g] || a.n !== idx.aggregates.n[g] || Math.abs(a.median - idx.aggregates.median_score_m[g]) > 1e-12) {
    throw new Error(`the ${g} rows disagree with the exported aggregates`)
  }
  return a
}

export interface Card {
  id: DesignId
  name: string
  walking: number
  n: number
  median: number
  status: string | null
  tone: 'bad' | 'warn' | 'ok'
  gain: { median: number; wins: number; losses: number; ties: number; status: string; required: number } | null
  confirmation: { run: boolean; walking: number | null; n: number | null; passed: boolean | null; reason: string | null } | null
}

export function cards(idx: Do1Index): Card[] {
  return DESIGNS.map((id) => {
    const a = aggregateOf(idx, id)
    if (id === 'faulty') return { id, name: DESIGN_NAME[id], ...a, status: null, tone: 'bad', gain: null, confirmation: null }
    const v = idx.verification[id]
    const conf = v.confirmation.run
      ? { run: true, walking: aggregateOf(idx, 'do1_confirm').walking, n: aggregateOf(idx, 'do1_confirm').n, passed: !!v.confirmation.passed, reason: null }
      : { run: false, walking: null, n: null, passed: null, reason: v.confirmation.reason ?? null }
    if (id !== 'do1' && conf.run) throw new Error('only the DO-1 confirmation run was exported')
    return {
      id, name: DESIGN_NAME[id], ...a, status: v.status,
      tone: v.status === 'FULL_RECOVERY' ? 'ok' : v.status === 'PARTIAL_IMPROVEMENT' ? 'warn' : 'bad',
      gain: { median: v.verdict.median_diff, wins: v.verdict.wins, losses: v.verdict.losses, ties: v.verdict.ties,
        status: v.verdict.status, required: v.verdict.min_effect.required },
      confirmation: conf,
    }
  })
}

export function rowFor(idx: Do1Index, g: RowGroup, seed: number): Do1Row {
  const r = idx.rows[g].find((x) => x.seed === seed)
  if (!r) throw new Error(`no ${g} row for seed ${seed}`)
  return r
}

export const LABEL_TEXT: Record<string, string> = {
  walking: 'walked', fall: 'fell', slow_or_few_steps: 'too slow / too few steps', contact_chatter: 'feet chattered, no gait',
}

export function outcomeText(r: Do1Row): string {
  const what = LABEL_TEXT[r.label] ?? r.label.replace(/_/g, ' ')
  return r.fell && r.fall_time !== null ? `${what} at ${r.fall_time.toFixed(2)} s` : what
}

export function seedOptionText(idx: Do1Index, seed: number): string {
  const mark = (g: DesignId) => `${DESIGN_SHORT[g]} ${rowFor(idx, g, seed).walking ? '✓' : '✗'}`
  return `${seed} · ${DESIGNS.map(mark).join(' · ')}${seed === idx.default_seed ? ' · illustrative' : ''}`
}

export interface WhyNotFull {
  needWalking: number
  n: number
  passPct: number
  frozenWalking: number
  do1Walking: number
  frozenMedian: number
  do1Median: number
  frozenAhead: number
  frozenGain: number
  do1Gain: number
  frozenAggregate: string
  frozenConfirmationRan: boolean
  frozenReasons: string[]
  do1Checks: { name: string; value: number | null; need: number | null; passed: boolean }[]
}

/** Why the frozen repair (which travels further) is not a FULL recovery, from the verifier's recorded outcome. */
export function whyNotFull(idx: Do1Index): WhyNotFull {
  const fz = aggregateOf(idx, 'frozen')
  const d1 = aggregateOf(idx, 'do1')
  const need = requiredWalking(idx.criteria.pass_frac, fz.n)
  const checks = idx.verification.do1.confirmation.checks ?? {}
  return {
    needWalking: need, n: fz.n, passPct: Math.round(idx.criteria.pass_frac * 100),
    frozenWalking: fz.walking, do1Walking: d1.walking, frozenMedian: fz.median, do1Median: d1.median,
    frozenAhead: fz.median - d1.median,
    frozenGain: idx.verification.frozen.verdict.median_diff, do1Gain: idx.verification.do1.verdict.median_diff,
    frozenAggregate: idx.verification.frozen.aggregate,
    frozenConfirmationRan: idx.verification.frozen.confirmation.run,
    frozenReasons: idx.verification.frozen.reasons,
    do1Checks: Object.entries(checks).map(([name, c]) => ({ name, value: c.value ?? null, need: c.need ?? null, passed: c.passed })),
  }
}

/** One recorded confirmation check as a sentence fragment, e.g. "92% of seeds walked the full 20 s (needs >= 80%) ✓". */
export function checkText(c: { name: string; value: number | null; need: number | null; passed: boolean }): string {
  const mark = c.passed ? '✓' : '✗'
  const pct = (x: number) => `${Math.round(x * 100)}%`
  if (c.name === 'walking_frac' && c.value !== null && c.need !== null) return `${pct(c.value)} of seeds walked the full 20 s (needs ≥ ${pct(c.need)}) ${mark}`
  if (c.name === 'median_speed_upright' && c.value !== null && c.need !== null) return `median upright speed ${c.value.toFixed(3)} m/s (needs ≥ ${c.need.toFixed(3)}) ${mark}`
  if (c.name === 'body_contact') return `no seed dragged its body on the floor ${mark}`
  return `${c.name.replace(/_/g, ' ')}${c.value !== null ? ` ${c.value}` : ''} ${mark}`
}

export const fmtM = (x: number, signed = false) => `${signed && x >= 0 ? '+' : ''}${x.toFixed(2)} m`
export const shortHash = (h: string) => h.slice(0, 8)
