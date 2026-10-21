import { structureLabel } from '../scientist/scientistLogic'
import type { ArmView, Candidate, Experiment, Structure, Study, ValidationRow, W2Case, W2Cross } from './nemotronTypes'

export type Lane = 'A3' | 'A1e'
export const LANE_COLOR: Record<Lane | 'A4', string> = { A3: 'var(--investigate)', A1e: 'var(--simulate)', A4: 'var(--create)' }
export const LANE_NAME: Record<Lane | 'A4', string> = { A3: 'Nemotron scientist', A1e: 'Engine alone', A4: 'Nemotron + memory' }

const SIDE: Record<string, string> = { right: 'Right-side', left: 'Left-side' }

/** "Right-side actuator weakness" for [["actuator_strength","right"]]; the generic label otherwise. */
export function explanationName(s: Structure | null | undefined): string {
  if (s && s.length === 1 && s[0][0] === 'actuator_strength' && SIDE[s[0][1]]) return `${SIDE[s[0][1]]} actuator weakness`
  return structureLabel(s)
}

/** "actuator_strength:right(factor=0.1721)" -> "Right-side actuator weakness (strength ×0.17)". */
export function hypothesisName(pid: string): string {
  const m = /^([a-z_]+):([a-z_]+)\((.*)\)$/.exec(pid)
  if (!m) return pid
  const params = Object.fromEntries(m[3].split(',').map((kv) => kv.split('=')))
  if (m[1] === 'actuator_strength' && SIDE[m[2]]) return `${SIDE[m[2]]} actuator weakness (strength ×${Number(params.factor).toFixed(2)})`
  const label = `${m[1].replace(/_/g, ' ')} (${m[2].replace(/_/g, ' ')})`
  return `${label}: ${Object.entries(params).map(([k, v]) => `${k} ${v}`).join(', ')}`
}

/** "cf:freq@x0.85" -> "Gait frequency ×0.85". */
export function experimentName(id: string): string {
  const m = /^(?:X\d+:)?cf:([a-z_]+)@([x+-])([0-9.]+)(R?)$/.exec(id)
  if (!m) return id === 'X0:observe' ? 'Walk the robot as designed' : id
  const names: Record<string, string> = { freq: 'Gait frequency', torso_mass: 'Torso mass', fp_kd: 'Foot-placement gain', foot_length: 'Foot length',
    torque_limit: 'Torque limit', pitch_ref: 'Pitch reference' }
  const what = names[m[1]] ?? m[1].replace(/_/g, ' ')
  return m[2] === 'x' ? `${what} ×${m[3]}` : `${what} ${m[2]}${m[3]}${m[4] ? ' of range' : ''}`
}

/** Walking seeds of an experiment, recounted from the per-seed rows; fails loudly if the stored count disagrees. */
export function walkingOf(e: Experiment): number {
  const k = e.per_seed.filter((s) => s.walking === 1).length
  if (k !== e.n_walking) throw new Error(`${e.id}: per-seed rows give ${k} walking, the record says ${e.n_walking}`)
  return k
}

/** Validation walking count, checked against the recorded fraction. */
export function verifiedWalking(a: ArmView): { k: number; n: number } {
  const v = a.verification
  if (Math.abs(v.walking_frac * v.n - v.walking) > 1e-9) throw new Error(`${a.arm}: walking ${v.walking}/${v.n} disagrees with fraction ${v.walking_frac}`)
  return { k: v.walking, n: v.n }
}

export type ForkRow = Candidate & { nemotron: boolean; engine: boolean; contrast: boolean }
export interface Fork { candidates: ForkRow[]; eigTied: boolean; nemotron: ForkRow; engine: ForkRow }

/** The turn-0 decision: every candidate, who picked which, and whether its predicted walking separates H1 from H2. */
export function forkOf(c: W2Case): Fork {
  const nb = c.fork.notebook
  const rows = nb.candidates.map((x) => ({ ...x, nemotron: x.id === c.fork.nemotron.experiment, engine: x.id === c.fork.engine.experiment,
    contrast: x.predicted_walking[0] !== x.predicted_walking[1] }))
  const nem = rows.find((r) => r.nemotron), eng = rows.find((r) => r.engine)
  if (!nem || !eng) throw new Error('the chosen experiments are not in the notebook shown to Nemotron')
  if (nb.engine_recommendation !== `experiment ${eng.id}`) throw new Error('the engine recommendation differs from what the engine ran')
  return { candidates: rows, eigTied: new Set(rows.map((r) => r.eig)).size === 1, nemotron: nem, engine: eng }
}

/** Belief before / after the chosen experiment in one lane. */
export function beliefShift(a: ArmView): { before: { name: string; w: number }[]; after: { name: string; w: number }[] } {
  const [h0, h1] = a.belief_history
  const pick = (top: ArmView['belief_history'][number]['top']) => top.slice(0, 2).map((t) => ({ name: explanationName(t.structure), w: t.w }))
  return { before: pick(h0.top), after: pick(h1.top) }
}

export const fmtW = (w: number): string => (w >= 0.9995 ? '1.000' : w.toFixed(3))
export const fmtUsd = (x: number | null | undefined): string => (x == null ? 'n/a' : `$${x.toFixed(4)}`)

/** Engine recommendation shown to Nemotron on its turn t (from the recorded prompt), and what Nemotron did instead. */
export function followed(a: ArmView): { turn: number; recommended: string | null; chose: string; same: boolean }[] {
  const calls = a.model?.calls ?? []
  return a.steps.filter((s) => s.actor === 'nemotron' && s.turn != null).map((s) => {
    const rec = calls[s.turn as number]?.engine_recommendation ?? null
    const chose = s.action.action === 'experiment' ? `experiment ${String(s.action.experiment)}` : s.action.action
    return { turn: s.turn as number, recommended: rec, chose, same: rec === chose }
  })
}

export function studyTone(direction: string): 'ok' | 'warn' | 'bad' | 'muted' {
  if (direction.startsWith('favourable')) return 'ok'
  if (direction.startsWith('negative')) return 'bad'
  if (direction.startsWith('mixed')) return 'warn'
  return 'muted'
}

/** Cross-instance counts recomputed from the 36 rows; fails loudly on any disagreement with the stored aggregates. */
export function crossCheck(x: W2Cross): { a3: number; a1: number; a4: number; a3Only: number; a1Only: number; n: number } {
  const n = x.rows.length
  const cnt = (f: (r: W2Cross['rows'][number]) => boolean) => x.rows.filter(f).length
  const out = { a3: cnt((r) => r.A3.full), a1: cnt((r) => r.A1e.full), a4: cnt((r) => r.A4.full),
    a3Only: cnt((r) => r.A3.full && !r.A1e.full), a1Only: cnt((r) => r.A1e.full && !r.A3.full), n }
  const g = x.aggregates
  if (n !== g.n || out.a3 !== g.full.A3 || out.a1 !== g.full.A1e || out.a4 !== g.full.A4 ||
      out.a3Only !== g.full_discordant_A3_vs_A1e.A3_only || out.a1Only !== g.full_discordant_A3_vs_A1e.A1e_only) {
    throw new Error('cross-instance rows disagree with the stored aggregates')
  }
  return out
}

export const shortId = (id: string): string => id.replace(/^hdb-v1-/, '').replace(/:(\d+)$/, ' · sev $1').replace(/_/g, ' ')

export const favourable = (s: Study[]): Study[] => s.filter((r) => studyTone(r.direction) === 'ok')

/** Recorded outcome of one experiment seed (from its per-seed features). */
export function outcomeOfFeatures(e: Experiment, seed: number): { text: string; ok: boolean } {
  const f = e.per_seed.find((x) => x.seed === seed)
  if (!f) throw new Error(`${e.id}: no recorded features for seed ${seed}`)
  if (f.walking === 1) return { text: 'walks', ok: true }
  const t = f.time_upright ?? 10
  return t < 10 ? { text: `falls at ${t.toFixed(1)} s`, ok: false } : { text: 'upright, not walking', ok: false }
}

/** Outcome of one validation seed in the reconstructed verification rows. */
export function outcomeOfRow(rows: ValidationRow[], seed: number): { text: string; ok: boolean } {
  const r = rows.find((x) => x.seed === seed)
  if (!r) throw new Error(`no validation row for seed ${seed}`)
  if (r.walking) return { text: 'walks', ok: true }
  if (r.fell) return { text: `falls${r.fall_time != null ? ` at ${r.fall_time.toFixed(1)} s` : ''}`, ok: false }
  return { text: (r.label ?? 'not walking').replace(/_/g, ' '), ok: false }
}

/** Pre-declared: the first validation seed (stored order) where Nemotron's design walks and the engine's does not. */
export function illustrativeSeed(a3: ValidationRow[], a1: ValidationRow[]): number | null {
  for (const r of a3) {
    const o = a1.find((x) => x.seed === r.seed)
    if (r.walking && o && !o.walking) return r.seed
  }
  return a3[0]?.seed ?? null
}
