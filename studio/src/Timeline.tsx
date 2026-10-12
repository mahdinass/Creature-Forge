import { usePlayback } from './store'
import type { RunPayload } from './types'

export interface ChartRun {
  run: RunPayload
  label: string
  color: string
}

const W = 600
const H = 110
const PAD = { l: 34, r: 8, t: 8, b: 16 }

/** Torso height vs simulation time, with detector events and the playhead; click to scrub. */
export function HeightChart({ runs }: { runs: ChartRun[] }) {
  const t = usePlayback((s) => s.simTime)
  const duration = usePlayback((s) => s.duration)
  const seek = usePlayback((s) => s.seek)
  const yMax = Math.max(...runs.map((r) => Math.max(...r.run.series.torso_height))) * 1.05
  const x = (time: number) => PAD.l + (time / duration) * (W - PAD.l - PAD.r)
  const y = (v: number) => H - PAD.b - (v / yMax) * (H - PAD.t - PAD.b)
  const onClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * W
    seek(((px - PAD.l) / (W - PAD.l - PAD.r)) * duration)
  }
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} onClick={onClick} role="img" aria-label="torso height over time">
      <text x={PAD.l + 4} y={11} className="axis">torso height (m)</text>
      <text x={W - 70} y={H - 3} className="axis">sim time (s)</text>
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(f * yMax)} y2={y(f * yMax)} className="grid" />
          <text x={4} y={y(f * yMax) + 3} className="axis">{(f * yMax).toFixed(2)}</text>
        </g>
      ))}
      {[0, 1, 2, 3, 4, 5].filter((s) => s <= duration).map((s) => (
        <text key={s} x={x(s)} y={H - 3} className="axis" textAnchor="middle">{s}</text>
      ))}
      {runs.map(({ run, color, label }) => (
        <g key={label}>
          <polyline fill="none" stroke={color} strokeWidth={1.6}
            points={run.time.map((tt, i) => `${x(tt).toFixed(1)},${y(run.series.torso_height[i]).toFixed(1)}`).join(' ')} />
          {run.push && (
            <rect x={x(run.push.time)} y={PAD.t} width={Math.max(2, x(run.push.time + run.push.duration) - x(run.push.time))}
              height={H - PAD.t - PAD.b} fill="#f5a524" opacity={0.18} />
          )}
          {run.events.map((e, i) => (
            <g key={i}>
              <line x1={x(e.time)} x2={x(e.time)} y1={PAD.t} y2={H - PAD.b} stroke={color} strokeDasharray="3 3" />
              <text x={x(e.time) + 3} y={PAD.t + 10 + 10 * runs.indexOf(runs.find((r) => r.label === label)!)}
                fill={color} className="axis">{e.kind} {e.time.toFixed(2)}s</text>
            </g>
          ))}
        </g>
      ))}
      <line x1={x(t)} x2={x(t)} y1={PAD.t} y2={H - PAD.b} stroke="#fff" strokeWidth={1.5} />
    </svg>
  )
}

const SPEEDS = [0.1, 0.25, 0.5, 1]

export function Transport({ runs }: { runs: ChartRun[] }) {
  const s = usePlayback()
  const marks = runs.flatMap(({ run, color, label }) =>
    run.events.map((e) => ({ time: e.time, color, title: `${label}: ${e.kind} @ ${e.time.toFixed(2)} s` })))
  return (
    <div className="transport">
      <div className="row">
        <button onClick={s.toggle}>{s.playing ? '⏸ Pause' : '▶ Play'}</button>
        <button onClick={s.restart}>⟲ Restart</button>
        <span className="speed">
          speed
          {SPEEDS.map((v) => (
            <button key={v} className={s.speed === v ? 'on' : ''} onClick={() => s.setSpeed(v)}>{v}×</button>
          ))}
        </span>
        <label className="follow"><input type="checkbox" checked={s.follow} onChange={(e) => s.setFollow(e.target.checked)} /> follow</label>
        <span className="clock">
          <b>sim t = {s.simTime.toFixed(2)} / {s.duration.toFixed(1)} s</b>
          <span title="Wall-clock seconds the replay has been running; differs from sim time when speed ≠ 1×"> · replay {s.replayTime.toFixed(1)} s @ {s.speed}×</span>
        </span>
      </div>
      <div className="scrub">
        <input type="range" min={0} max={s.duration} step={0.005} value={s.simTime}
          onChange={(e) => s.seek(parseFloat(e.target.value))} aria-label="timeline" />
        {marks.map((m, i) => (
          <span key={i} className="mark" title={m.title} style={{ left: `${(m.time / s.duration) * 100}%`, background: m.color }} />
        ))}
      </div>
    </div>
  )
}
