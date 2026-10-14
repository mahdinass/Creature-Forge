import type { DemoRun, DemoRow, Edit, Kind, Realised, VResult, Verdict } from './demoTypes'

export const KIND_INFO: Record<Kind, { label: string; tone: 'ok' | 'info' | 'warn'; text: string }> = {
  LIVE: { label: 'LIVE', tone: 'ok', text: 'A real Nebius Token Factory call made during this run.' },
  RECORDED_LIVE: { label: 'RECORDED LIVE', tone: 'info', text: 'A stored, hash-verified copy of an earlier real call. Nothing is re-sent to the model.' },
  SCRIPTED_MOCK: { label: 'SCRIPTED MOCK — not a model', tone: 'warn', text: 'Text written by this repository to exercise the pipeline. It is not Nemotron and is not a result.' },
}

export const STEPS = ['observe', 'prompt', 'proposal', 'verify', 'replay'] as const
export type Step = (typeof STEPS)[number]
export const STEP_TITLE: Record<Step, string> = {
  observe: 'Observed failure', prompt: 'What the model saw', proposal: 'Model proposal', verify: 'Verification', replay: 'Replay and verdict',
}

export function sgn(x: number, nd = 2): string {
  return `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(nd)}`
}

export function describeEdit(e: Edit, realised?: Realised): string {
  const base = `${e.parameter} ${sgn(e.delta_u)}`
  if (!realised) return base
  return realised.reflected ? `${base} → realised ${sgn(realised.realised_delta_u)} (reflected at a bound)` : `${base} → realised ${sgn(realised.realised_delta_u)}`
}

export function verdictText(v: Verdict | undefined): { text: string; tone: 'ok' | 'bad' | 'muted' } {
  if (!v) return { text: 'not verified', tone: 'muted' }
  if (v.kind === 'improved') return { text: `improved by ${v.gain_seeds} seeds`, tone: 'ok' }
  if (v.kind === 'worse') return { text: `worse by ${-v.gain_seeds} seeds`, tone: 'bad' }
  return { text: `no clear change (${v.gain_seeds >= 0 ? '+' : '−'}${Math.abs(v.gain_seeds)})`, tone: 'muted' }
}

export function predictionText(v: Verdict | undefined, predicted: number): string {
  if (!v || v.prediction_met === undefined) return 'prediction not evaluated'
  return v.prediction_met ? `model predicted ≥ +${predicted} seeds: met` : `model predicted ≥ +${predicted} seeds: not met`
}

export function replayOptions(run: DemoRun): { id: string; label: string }[] {
  const out = [{ id: 'baseline', label: 'frozen controller (baseline)' }]
  for (const iv of run.interventions) {
    out.push({ id: `slot${iv.slot}`, label: `model proposal ${iv.slot + 1}: ${iv.proposal.edits.map((e) => e.parameter).join(' + ')}` })
    out.push({ id: `slot${iv.slot}_random`, label: `matched random edit for proposal ${iv.slot + 1}` })
  }
  return out
}

export function statusMessage(run: DemoRun): { tone: 'ok' | 'warn' | 'bad'; text: string } {
  const m = run.model_reply
  if (m.status === 'ok' && run.interventions.length > 0) return { tone: 'ok', text: `${run.interventions.length} schema-valid proposal(s) received.` }
  if (m.status === 'ok') return { tone: 'warn', text: 'The model replied, but no proposal passed validation. Nothing was simulated or substituted.' }
  const why = m.reason ?? 'no further detail'
  return { tone: 'bad', text: `No usable reply (${m.status}): ${why}. Nothing was simulated or substituted.` }
}

export function lookupPath(ctx: unknown, path: string): unknown {
  let cur: unknown = ctx
  for (const part of path.split('.')) {
    if (Array.isArray(cur)) cur = cur[Number(part)]
    else if (cur && typeof cur === 'object') cur = (cur as Record<string, unknown>)[part]
    else return undefined
  }
  return cur
}

/** The id the API serves this record under. NOT run_id (the id stored inside the record), which can differ for bundled recordings. */
export function apiId(run: DemoRun): string {
  return run.id
}

export function bar(v: VResult): string {
  return v.walking_by_seed.map((w) => (w ? '■' : '□')).join('')
}

export function rowBadge(r: DemoRow): string {
  if (r.readable === false) return 'unreadable'
  return r.kind ?? 'unknown'
}

export function honestHeadline(run: DemoRun): string {
  const ver = run.verification
  if (!ver) return 'No verification was run, so this record says nothing about whether any edit works.'
  const base = ver.results['theta0'].walking_count
  const parts = run.interventions.map((iv) => {
    const e = ver.results[`slot${iv.slot}`]
    const r = ver.results[`slot${iv.slot}_random`]
    return `proposal ${iv.slot + 1} walked on ${e.walking_count}/${e.n} seeds vs ${base}/${e.n} for the frozen controller and ${r.walking_count}/${e.n} for a matched random edit`
  })
  return `Measured on ${ver.seeds.length} fresh seeds: ${parts.join('; ')}. One instance; not a statistical claim.`
}
