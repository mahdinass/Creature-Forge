import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getLocomotionReplay, getLocomotionSummary } from '../api'
import { Metrics } from '../Metrics'
import { usePlayback } from '../store'
import { HeightChart, Transport } from '../Timeline'
import { Viewport } from '../Viewport'
import { curvePoints, durationForSeed, METHOD_COLOR, METHOD_NAME, pct, prettyLabel, seedRole, verdictText } from './locoLogic'
import type { LocomotionReplay, LocomotionSummary } from './locoTypes'

const W = 560
const H = 220

function ProgressChart({ s }: { s: LocomotionSummary }) {
  const names = Object.keys(s.methods)
  const all = names.flatMap((n) => s.methods[n].best_so_far)
  const yMin = Math.min(0, ...all)
  const yMax = Math.max(1, ...all)
  return (
    <figure className="loco-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="best fitness so far versus rollouts">
        <rect x="0" y="0" width={W} height={H} fill="none" stroke="#2a3340" />
        {names.map((n) => (
          <polyline key={n} fill="none" stroke={METHOD_COLOR[n] ?? '#aaa'} strokeWidth="2"
            points={curvePoints(s.methods[n].best_so_far, W, H, 28, yMin, yMax)} />
        ))}
        <text x="30" y="16" fontSize="11" fill="#9aa7b5">best training fitness so far (max {yMax.toFixed(1)})</text>
        <text x={W - 150} y={H - 8} fontSize="11" fill="#9aa7b5">0 → {s.methods[names[0]].rollouts} rollouts</text>
      </svg>
      <figcaption>
        {names.map((n) => (
          <span key={n} style={{ color: METHOD_COLOR[n] }}>
            ■ {METHOD_NAME[n] ?? n}: best {s.methods[n].best_so_far.at(-1)?.toFixed(2)} · {s.methods[n].n_feasible} candidate(s) walking on every
            training seed · {s.methods[n].rollouts} rollouts · {s.methods[n].wall_s.toFixed(0)} s
          </span>
        ))}
      </figcaption>
    </figure>
  )
}

export function Locomotion() {
  const [summary, setSummary] = useState<LocomotionSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [controller, setController] = useState('random_search')
  const [seed, setSeed] = useState(3000)
  const [replay, setReplay] = useState<LocomotionReplay | null>(null)
  const [busy, setBusy] = useState(false)
  const [replayError, setReplayError] = useState<string | null>(null)
  const setDuration = usePlayback((s) => s.setDuration)
  const requestId = useRef(0) // identifies the latest replay request; older responses are discarded

  useEffect(() => {
    getLocomotionSummary().then(setSummary).catch((e: Error) => setError(e.message))
  }, [])

  const seeds = useMemo(
    () => (summary ? [...summary.seed_roles.heldout, ...summary.seed_roles.diagnostic, ...summary.seed_roles.train] : []),
    [summary],
  )

  // Changing the controller or seed invalidates the loaded simulation and any request still in flight.
  const select = useCallback((apply: () => void) => {
    requestId.current += 1
    apply()
    setReplay(null)
    setReplayError(null)
    setBusy(false)
  }, [])

  const load = useCallback(async () => {
    if (!summary) return
    const mine = ++requestId.current
    setBusy(true)
    setReplayError(null)
    try {
      const r = await getLocomotionReplay(controller, seed, durationForSeed(seed, summary.seed_roles, summary.durations))
      if (mine !== requestId.current) return
      setReplay(r)
      setDuration(r.duration)
      usePlayback.getState().restart()
    } catch (e) {
      if (mine === requestId.current) setReplayError((e as Error).message)
    } finally {
      if (mine === requestId.current) setBusy(false)
    }
  }, [summary, controller, seed, setDuration])

  if (error) return <main><div className="notice notice-bad" role="alert">No Phase 2A locomotion results available: {error}</div></main>
  if (!summary) return <main><div className="notice">Loading locomotion results…</div></main>

  const h = summary.heldout
  const loco = replay?.locomotion
  const methodNames = Object.keys(summary.methods)
  return (
    <main className="loco">
      <div className="banner">
        Phase 2A diagnostic search ({summary.protocol_id}): a compact phase-based, contact-aware gait controller on one fixed biped,
        random search vs differential evolution at an identical budget of {summary.methods[methodNames[0]].rollouts} rollouts each
        (one run each). Walking is decided by physical gates, never by distance alone.
      </div>

      <section>
        <h3>Training progress</h3>
        <ProgressChart s={summary} />
        <div className="table-scroll"><table className="loco-table">
          <thead>
            <tr><td>Candidates by majority outcome over their 3 training seeds</td>{methodNames.map((m) => <td key={m}>{METHOD_NAME[m] ?? m}</td>)}</tr>
          </thead>
          <tbody>
            {[...new Set(methodNames.flatMap((m) => Object.keys(summary.methods[m].label_counts)))].sort().map((l) => (
              <tr key={l}>
                <td>{prettyLabel(l)}</td>
                {methodNames.map((m) => <td key={m}>{summary.methods[m].label_counts[l] ?? 0}</td>)}
              </tr>
            ))}
          </tbody>
        </table></div>
      </section>

      {h && (
        <section>
          <h3>Held-out evaluation ({h.seeds.length} unseen seeds × {h.duration} s, evaluated once)</h3>
          <div className="table-scroll"><table className="loco-table" data-testid="heldout-table">
            <thead><tr><td>Controller</td><td>walking seeds</td><td>survived</td><td>median speed</td><td>steps/s</td><td>verdict</td></tr></thead>
            <tbody>
              {Object.entries(h.controllers).map(([name, c]) => {
                const v = verdictText(c.verdict)
                return (
                  <tr key={name}>
                    <td>{METHOD_NAME[name] ?? name.replace(/_/g, ' ')}</td>
                    <td>{pct(c.verdict.fraction_seeds_walking)}</td>
                    <td>{pct(c.summary.survival_rate)}</td>
                    <td>{c.verdict.median_speed_upright.toFixed(2)} m/s</td>
                    <td>{c.summary.mean_valid_step_rate.toFixed(2)}</td>
                    <td><span className={`chip ${v.tone === 'ok' ? 'chip-ok' : v.tone === 'partial' ? 'chip-warn' : 'chip-bad'}`}>{v.text}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table></div>
          {summary.success_criteria && (
            <small>
              Pre-registered walking criterion: ≥ {pct(summary.success_criteria.walking.min_fraction_seeds_walking)} of seeds pass every gate and
              median speed ≥ {summary.success_criteria.walking.min_median_speed_upright} m/s; partial: ≥{' '}
              {pct(summary.success_criteria.partial.min_fraction_seeds_walking)} of seeds.
            </small>
          )}
        </section>
      )}

      <section>
        <h3>Replay</h3>
        <div className="replay-bar">
          <label>Controller{' '}
            <select value={controller} onChange={(e) => select(() => setController(e.target.value))} aria-label="controller">
              {Object.entries(summary.controllers).map(([k, d]) => (
                <option key={k} value={k} title={d}>{METHOD_NAME[k] ?? k.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </label>
          <label>Seed{' '}
            <select value={seed} onChange={(e) => select(() => setSeed(Number(e.target.value)))} aria-label="seed">
              {seeds.map((s) => <option key={s} value={s}>{s} ({seedRole(s, summary.seed_roles)})</option>)}
            </select>
          </label>
          <button data-testid="load-loco-replay" onClick={() => void load()} disabled={busy}>
            {busy ? 'Running MuJoCo…' : 'Load MuJoCo replay'}
          </button>
          <small>{summary.controllers[controller]}. Fresh deterministic rollout; no model call.</small>
        </div>
        {replayError && <div className="notice notice-bad" role="alert">{replayError}</div>}
        {replay && loco && (
          <>
            <Viewport run={replay} label={`${METHOD_NAME[controller] ?? controller} · seed ${replay.seed} (${replay.role})`} />
            <Transport runs={[{ run: replay, label: 'run', color: '#4cc2ff' }]} />
            <div className="below">
              <HeightChart runs={[{ run: replay, label: 'run', color: '#4cc2ff' }]} />
              <div className="summary" data-testid="loco-verdict">
                <h4>Gait verdict: <span className={`chip ${loco.walking ? 'chip-ok' : 'chip-bad'}`}>{prettyLabel(loco.label)}</span></h4>
                <table>
                  <tbody>
                    <tr><td>forward distance while upright</td><td>{loco.forward_disp_upright.toFixed(2)} m ({loco.speed_upright.toFixed(2)} m/s)</td></tr>
                    <tr><td>valid alternating steps</td><td>{loco.valid_steps} ({loco.valid_step_rate.toFixed(2)}/s, advance {loco.mean_step_advance.toFixed(2)} m)</td></tr>
                    <tr><td>stance / swing</td><td>{loco.mean_stance_s.toFixed(2)} s / {loco.mean_swing_s.toFixed(2)} s</td></tr>
                    <tr><td>single / double support / flight</td><td>{pct(loco.single_support_frac)} / {pct(loco.double_support_frac)} / {pct(loco.flight_frac)}</td></tr>
                    <tr><td>touchdowns per foot per s</td><td>{loco.raw_touchdown_rate.toFixed(2)}</td></tr>
                    <tr><td>slip · saturation · effort</td><td>{pct(loco.slip_frac)} · {pct(loco.saturation_frac)} · {loco.effort.toFixed(3)}</td></tr>
                    <tr><td>violated gates</td><td>{loco.violations.length ? loco.violations.map(prettyLabel).join(', ') : 'none'}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
            <Metrics run={replay} label="Measured results" />
          </>
        )}
      </section>
    </main>
  )
}
