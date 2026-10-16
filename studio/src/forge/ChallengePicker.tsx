import { DEFAULT_TARGET_FORCE, KIND_INFO, KINDS, walkCostNote } from './forgeLogic'
import type { ChallengeRun, Kind } from './forgeTypes'

const SEED_OPTIONS = [4, 8, 16]
export const MAX_TARGET_FORCE = 200

/** Three challenges with the physical meaning of each, the push target, and the honest cost of a walk. */
export function ChallengePicker({ kind, onKind, targetForce, onTargetForce, seeds, onSeeds, onRun, busy, lastRun, versionLabel }: {
  kind: Kind
  onKind: (k: Kind) => void
  targetForce: number
  onTargetForce: (n: number) => void
  seeds: number
  onSeeds: (n: number) => void
  onRun: () => void
  busy: boolean
  lastRun: ChallengeRun | null
  versionLabel: string
}) {
  const forceOk = Number.isFinite(targetForce) && targetForce > 0 && targetForce <= MAX_TARGET_FORCE
  const canRun = !busy && (kind !== 'push' || forceOk)
  return (
    <section className="fg-card fg-picker" data-testid="challenge-picker" aria-label="choose a challenge">
      <h3>Choose a challenge</h3>
      <div className="fg-kinds" role="radiogroup" aria-label="challenge">
        {KINDS.map((k) => (
          <button key={k} role="radio" aria-checked={kind === k} className={`fg-kind ${kind === k ? 'on' : ''}`} data-testid={`kind-${k}`} onClick={() => onKind(k)}>
            <b>{KIND_INFO[k].label}</b>
            <span>{KIND_INFO[k].meaning}</span>
          </button>
        ))}
      </div>
      <p className="fg-explain" data-testid="kind-explain">{KIND_INFO[kind].scoreMeaning}</p>
      {kind === 'push' && (
        <label className="fg-field">
          <span>Target force (N)</span>
          <input type="number" min={1} max={MAX_TARGET_FORCE} step={1} value={Number.isFinite(targetForce) ? targetForce : ''} data-testid="target-force"
            onChange={(e) => onTargetForce(e.target.value === '' ? NaN : Number(e.target.value))} />
          <small>
            Each seed searches for the hardest push (forward and backward) the creature survives. The score is the smaller of the two, so the weakest direction decides.
            PASS needs the score to reach the target ({DEFAULT_TARGET_FORCE} N is the default).
          </small>
          {!forceOk && <small className="fg-bad">Enter a force between 1 and {MAX_TARGET_FORCE} N.</small>}
        </label>
      )}
      {kind === 'walk' && <p className="fg-explain" data-testid="walk-cost">{walkCostNote(lastRun?.spec.kind === 'walk' ? lastRun : null)}</p>}
      <label className="fg-field fg-inline">
        <span>Seeds</span>
        <select value={seeds} onChange={(e) => onSeeds(Number(e.target.value))} data-testid="seed-count" aria-label="number of seeds">
          {SEED_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <small>Each seed is a different random start. More seeds give a steadier verdict and take longer.</small>
      </label>
      <button className="btn btn-simulate btn-lg" disabled={!canRun} data-testid="run-challenge" onClick={onRun}>
        {busy ? 'Starting...' : `Run ${KIND_INFO[kind].label.toLowerCase()} challenge on ${versionLabel}`}
      </button>
    </section>
  )
}
