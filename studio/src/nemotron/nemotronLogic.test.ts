import { describe, expect, it } from 'vitest'
import caseText from '../../../experiments/w2/gen0137_one_side_weakness/case.json?raw'
import crossText from '../../../experiments/w2/gen0137_one_side_weakness/cross_instance.json?raw'
import studiesText from '../../../experiments/w2/studies.json?raw'
import replayIndexText from '../../../experiments/w2/gen0137_one_side_weakness/plant_replays/index.json?raw'
import { beliefShift, crossCheck, experimentName, explanationName, followed, forkOf, hypothesisName, illustrativeSeed, outcomeOfFeatures, outcomeOfRow, studyTone, verifiedWalking, walkingOf } from './nemotronLogic'
import type { ReplayStatus, Study, W2Case, W2Cross } from './nemotronTypes'

// The committed, pinned W2 files: the same bytes /api/nemotron/case serves.
const c: W2Case = JSON.parse(caseText)
const x: W2Cross = JSON.parse(crossText)
const studies: Study[] = JSON.parse(studiesText).studies
const rp: ReplayStatus = JSON.parse(replayIndexText)

describe('Nemotron case logic on the committed record', () => {
  it('finds the fork: tied EIG, Nemotron picks the walking-contrast experiment, the engine its top EIG', () => {
    const f = forkOf(c)
    expect(f.eigTied).toBe(true)
    expect(f.nemotron.id).toBe('cf:freq@x0.85')
    expect(f.engine.id).toBe('cf:freq@x1.2')
    expect(f.nemotron.contrast).toBe(true)
    expect(f.engine.contrast).toBe(false)
    expect(c.fork.nemotron.words.why).toMatch(/4\/4/)
  })

  it('recounts measurements and verification from the rows', () => {
    expect(walkingOf(c.shared.observation)).toBe(0)
    expect(walkingOf(c.arms.A3.experiments[1])).toBe(3)
    expect(walkingOf(c.arms.A1e.experiments[1])).toBe(2)
    expect(verifiedWalking(c.arms.A3)).toEqual({ k: 23, n: 24 })
    expect(verifiedWalking(c.arms.A1e)).toEqual({ k: 20, n: 24 })
    expect(verifiedWalking(c.arms.A4)).toEqual({ k: 19, n: 24 })
  })

  it('fails loudly when a stored count disagrees with its rows', () => {
    const bad = structuredClone(c.arms.A3.experiments[1])
    bad.n_walking = 4
    expect(() => walkingOf(bad)).toThrow(/record says/)
    const badX = structuredClone(x)
    badX.rows[0].A3.full = !badX.rows[0].A3.full
    expect(() => crossCheck(badX)).toThrow(/disagree/)
  })

  it('shows the belief moving to opposite sides', () => {
    expect(beliefShift(c.arms.A3).after[0].name).toBe('Right-side actuator weakness')
    expect(beliefShift(c.arms.A1e).after[0].name).toBe('Left-side actuator weakness')
    expect(explanationName(c.evaluation_only.injected_structure)).toBe('Right-side actuator weakness')
  })

  it('records where Nemotron followed the engine recommendation', () => {
    const t = followed(c.arms.A3)
    expect(t.map((r) => r.same)).toEqual([false, false, false, true])
    expect(t[3].chose).toBe('delegate_repair')
  })

  it('cross-instance counts match the Stage 2 report (15 vs 14, discordant 4 vs 3)', () => {
    expect(crossCheck(x)).toEqual({ a3: 15, a1: 14, a4: 14, a3Only: 4, a1Only: 3, n: 36 })
  })

  it('labels names and keeps only the pre-registered scoreboard as favourable', () => {
    expect(hypothesisName('actuator_strength:left(factor=0.1975)')).toBe('Left-side actuator weakness (strength ×0.20)')
    expect(experimentName('cf:freq@x0.85')).toBe('Gait frequency ×0.85')
    expect(studies.filter((s) => studyTone(s.direction) === 'ok').map((s) => s.id)).toEqual(['forge-scoreboard'])
    expect(studies.find((s) => s.id === 'do1')?.credited_to).toMatch(/NO_AI/)
  })

  it('the damaged-plant export agrees with the recorded case', () => {
    const v = rp.validation!
    expect(v.a3_submitted.rows.filter((r) => r.walking).length).toBe(c.arms.A3.verification.walking)
    expect(v.a1e_submitted.rows.filter((r) => r.walking).length).toBe(c.arms.A1e.verification.walking)
    expect(v.nominal.rows.filter((r) => r.walking).length).toBe(0)
    expect(rp.experiments!.x1_nem.seeds).toEqual(c.arms.A3.experiments[1].seeds)
    expect(rp.fidelity!.fk_max_err_m).toBe(0)
  })

  it('picks the illustrative validation seed by the pre-declared rule and labels outcomes from the record', () => {
    const v = rp.validation!
    const s = illustrativeSeed(v.a3_submitted.rows, v.a1e_submitted.rows)!
    expect(outcomeOfRow(v.a3_submitted.rows, s).ok).toBe(true)
    expect(outcomeOfRow(v.a1e_submitted.rows, s).ok).toBe(false)
    const first = v.a3_submitted.rows.find((r) => r.walking && !v.a1e_submitted.rows.find((x) => x.seed === r.seed)!.walking)!.seed
    expect(s).toBe(first)
    const x1 = c.arms.A3.experiments[1]
    expect(x1.seeds.map((q) => outcomeOfFeatures(x1, q).text)).toEqual(['walks', 'walks', 'falls at 1.7 s', 'walks'])
    expect(() => outcomeOfFeatures(x1, 1)).toThrow(/no recorded features/)
  })
})
