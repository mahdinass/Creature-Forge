import type { RunPayload } from './types'

/** Measured values only: everything shown is read from MuJoCo telemetry or the detectors' own output. */
export function Metrics({ run, label }: { run: RunPayload; label: string }) {
  const m = run.metrics
  return (
    <div className="metrics">
      <h4>{label}</h4>
      <table>
        <tbody>
          <tr><td>initial torso height</td><td>{m.initial_torso_height.toFixed(3)} m</td></tr>
          <tr><td>minimum torso height</td><td>{m.min_torso_height.toFixed(3)} m</td></tr>
          <tr><td>final torso height</td><td>{m.final_torso_height.toFixed(3)} m</td></tr>
          <tr><td>max |torso pitch|</td><td>{(m.max_abs_pitch * 57.2958).toFixed(1)}°</td></tr>
          <tr><td>peak torso speed (x)</td><td>{m.peak_torso_vx.toFixed(2)} m/s</td></tr>
          <tr><td>fall detector fired</td><td><b className={m.fell ? 'bad' : ''}>{m.fell ? 'yes' : 'no'}</b></td></tr>
        </tbody>
      </table>
      <div className="events">
        {run.events.length === 0 ? <i>no failure events detected</i> : run.events.map((e, i) => (
          <div key={i} className="event">
            <b>{e.kind}</b> @ sim t = {e.time.toFixed(2)} s
            <div className="ev">{Object.entries(e.evidence).filter(([, v]) => typeof v === 'number')
              .map(([k, v]) => `${k}=${(v as number).toFixed(3)}`).join('  ')}</div>
          </div>
        ))}
      </div>
      <small>
        Fall = torso height &lt; 50% of initial or |pitch| &gt; 1 rad for ≥ 0.1 s. seed {run.seed}
        {run.push ? `, ${run.push.force} N push at t=${run.push.time} s` : ', no push'}.
      </small>
    </div>
  )
}
