import { describe, expect, it } from 'vitest'
import { pct, proposalLine } from './overviewLogic'

describe('overview wording', () => {
  it('formats exact interval bounds without rounding up to 100%', () => {
    expect(pct(0.9757074028338915)).toBe('97.6%')
    expect(pct(1)).toBe('100.0%')
  })
  it('states plainly whether the model edit beat, matched or lost to the random edit', () => {
    const base = { edits: ['kp', 'kd'], model_verdict: 'improved', random_verdict: 'improved' }
    expect(proposalLine({ ...base, model_walking: 28, random_walking: 25 }, 19, 32)).toContain('walked more than the random one')
    expect(proposalLine({ ...base, model_walking: 25, random_walking: 30 }, 19, 32)).toContain('walked fewer than the random one')
    expect(proposalLine({ ...base, model_walking: 25, random_walking: 25 }, 19, 32)).toContain('walked the same as the random one')
    expect(proposalLine({ ...base, model_walking: 25, random_walking: 30 }, 19, 32)).toContain('frozen controller 19/32')
  })
})
