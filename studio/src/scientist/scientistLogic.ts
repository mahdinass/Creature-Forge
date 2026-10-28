import type { Evidence, ScientistRecord, Step } from './scientistTypes'

/** "payload:torso + sensor_bias:pitch" from [[kind, target], ...]. */
export const structureLabel = (s: string[][] | null | undefined): string =>
  !s || !s.length ? 'nominal (no deviation)' : s.map(([k, t]) => `${k.replace(/_/g, ' ')} (${t.replace(/_/g, ' ')})`).join(' + ')

/** "payload:torso(mass_kg=1.2,x_m=0.1)" -> "payload (torso): mass_kg 1.2, x_m 0.1". */
export function hypothesisLabel(pid: string): string {
  if (pid === 'nominal') return 'nominal (no deviation)'
  return pid.split('+').map((part) => {
    const m = /^([a-z_]+):([a-z_]+)\((.*)\)$/.exec(part)
    if (!m) return part
    const params = m[3].split(',').map((kv) => kv.replace('=', ' ')).join(', ')
    return `${m[1].replace(/_/g, ' ')} (${m[2].replace(/_/g, ' ')}): ${params}`
  }).join(' + ')
}

const ACTION_TITLE: Record<string, string> = {
  observe: 'Watches the failing robot',
  experiment: 'Runs an experiment on the robot',
  propose: 'Proposes explanations',
  delegate_diagnosis: 'Delegates diagnosis to the belief engine',
  screen_tools: 'Asks the engine to rank repair tools',
  repair: 'Engineers a repair',
  check: 'Checks a design on fresh trials',
  assimilate: 'Uses a repair result as evidence about the cause',
  apply_dossier: 'Applies a lesson from memory',
  use_learned: 'Consults the learned posterior',
  delegate_repair: 'Delegates the repair to the engine',
  conclude: 'Submits a design for independent verification',
}

export function stepTitle(s: Step): string {
  const a = String(s.action.action)
  const base = ACTION_TITLE[a] ?? a
  if (a === 'experiment' && s.action.experiment) return `${base}: ${String(s.action.experiment)}`
  if (a === 'repair' && s.action.tool) return `${base}: ${String(s.action.tool)} (${String(s.action.mode ?? 'twin')})`
  if ((a === 'check' || a === 'conclude' || a === 'assimilate') && s.action.design != null) return `${base}: design ${String(s.action.design)}`
  if (a === 'apply_dossier' && s.action.dossier) return `${base}: ${String(s.action.dossier)}`
  return base
}

export function actorInfo(actor: string): { label: string; tone: string } {
  if (actor === 'nemotron') return { label: 'Nemotron decided', tone: 'cat' }
  if (actor === 'engine') return { label: 'engine', tone: 'cf' }
  if (actor === 'fallback') return { label: 'engine fallback (invalid model reply)', tone: 'warn' }
  return { label: actor, tone: 'muted' }
}

export function evidenceLine(e: Evidence | undefined): string {
  if (!e) return ''
  const parts: string[] = []
  if (e.twin_pred != null) parts.push(`simulator predicted ${Math.round(e.twin_pred * 100)}% walking`)
  if (e.train) parts.push(`training trials ${e.train}`)
  if (e.robust8 != null) parts.push(`${e.robust8}/8 fresh trials walk`)
  if (e.robust16 != null) parts.push(`${e.robust16}/16 fresh trials walk`)
  if (e.stress4 != null) parts.push(`${e.stress4}/4 walk for 20 s`)
  if (e.p_full != null) parts.push(typeof e.p_full === 'number' ? `P(pass) ${e.p_full.toFixed(2)}` : `P(pass) ${e.p_full}`)
  return parts.join(' · ')
}

/** Counts of who made the decisions, for the headline. */
export function decisionCounts(rec: ScientistRecord): { nemotron: number; engine: number; fallback: number } {
  const c = { nemotron: 0, engine: 0, fallback: 0 }
  for (const s of rec.steps) if (s.actor in c) c[s.actor as keyof typeof c] += 1
  return c
}

export function scientistHeadline(rec: ScientistRecord): string {
  const c = decisionCounts(rec)
  const v = rec.verification.status.replace(/_/g, ' ').toLowerCase()
  const by = rec.conclusion.by?.startsWith('forced') ? 'the budget ran out and the best-evidence design was submitted'
    : rec.conclusion.by === 'engine_repair' ? 'it delegated the final repair to the engine' : 'it chose when to stop and which design to submit'
  return `${rec.arm === 'A1e' ? 'The belief engine alone' : 'Nemotron'} ran ${rec.steps.length} steps (${c.nemotron} decided by Nemotron, ${c.engine} by the engine${c.fallback ? `, ${c.fallback} engine fallbacks` : ''}); ${by}. Independent verification: ${v} (${Math.round(rec.verification.walking_frac * 100)}% of hidden starts walk).`
}
