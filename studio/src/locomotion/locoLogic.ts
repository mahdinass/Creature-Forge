import type { HeldoutVerdict } from './locoTypes'

export const METHOD_COLOR: Record<string, string> = { random_search: '#4cc2ff', differential_evolution: '#f5a524' }
export const METHOD_NAME: Record<string, string> = {
  random_search: 'Random search',
  differential_evolution: 'Differential evolution',
}

export const prettyLabel = (l: string) => l.replace(/_/g, ' ')

/** SVG polyline points for a series scaled into a w x h box with padding. */
export function curvePoints(values: number[], w: number, h: number, pad: number, yMin: number, yMax: number): string {
  if (values.length === 0) return ''
  const span = yMax - yMin || 1
  const n = Math.max(1, values.length - 1)
  return values
    .map((v, i) => {
      const x = pad + (i / n) * (w - 2 * pad)
      const y = h - pad - ((v - yMin) / span) * (h - 2 * pad)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

export function verdictText(v: HeldoutVerdict): { text: string; tone: 'ok' | 'partial' | 'fail' } {
  if (v.meets_walking_criteria) return { text: 'meets walking criteria', tone: 'ok' }
  if (v.meets_partial_criteria) return { text: 'partial: walks on some seeds only', tone: 'partial' }
  return { text: 'does not walk', tone: 'fail' }
}

export function seedRole(seed: number, roles: { train: number[]; diagnostic: number[]; heldout: number[] }): string | null {
  if (roles.train.includes(seed)) return 'train'
  if (roles.diagnostic.includes(seed)) return 'diagnostic'
  if (roles.heldout.includes(seed)) return 'held-out'
  return null
}

export function durationForSeed(seed: number, roles: { train: number[]; diagnostic: number[]; heldout: number[] },
  d: { train: number; diagnostic: number; heldout: number }): number {
  if (roles.train.includes(seed)) return d.train
  if (roles.diagnostic.includes(seed)) return d.diagnostic
  return d.heldout
}

export const pct = (x: number) => `${Math.round(x * 100)}%`
