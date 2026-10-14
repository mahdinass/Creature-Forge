import type { OverviewProposal } from './overviewTypes'

export const pct = (x: number): string => `${(x * 100).toFixed(1)}%`

/** One honest line per verified proposal: the model's edit, the matched random edit, and the frozen baseline, all measured. */
export function proposalLine(p: OverviewProposal, frozen: number, n: number): string {
  const edit = p.edits.join(' + ')
  const cmp = p.model_walking > p.random_walking ? 'more than' : p.model_walking < p.random_walking ? 'fewer than' : 'the same as'
  return `${edit}: ${p.model_walking}/${n} walking (frozen controller ${frozen}/${n}); a matched random edit reached ${p.random_walking}/${n}, so the model's edit walked ${cmp} the random one.`
}
