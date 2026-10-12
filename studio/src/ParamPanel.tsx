import type { Params, Schema } from './types'

const LABELS: Record<string, [string, string]> = {
  torso_mass: ['Torso mass', 'kg'],
  thigh_length: ['Thigh length', 'm'],
  shank_length: ['Shank length', 'm'],
  foot_length: ['Foot length', 'm'],
  foot_friction: ['Foot friction μ', ''],
  torque_limit: ['Motor torque limit', 'N·m'],
  leg_density: ['Leg density', 'kg/m³'],
}

export interface PushSettings {
  enabled: boolean
  force: number
}

interface Props {
  schema: Schema
  body: Params
  onBody: (b: Params) => void
  push: PushSettings
  onPush: (p: PushSettings) => void
  seed: number
  onSeed: (s: number) => void
  onForge: () => void
  busy: boolean
  error: string | null
}

export function ParamPanel({ schema, body, onBody, push, onPush, seed, onSeed, onForge, busy, error }: Props) {
  return (
    <div className="panel">
      <h3>Morphology</h3>
      {Object.entries(schema.body.bounds).map(([k, [lo, hi]]) => {
        const [label, unit] = LABELS[k] ?? [k, '']
        const step = (hi - lo) / 200
        return (
          <label key={k} className="param">
            <span>{label} <b>{body[k].toFixed(k === 'leg_density' || k === 'torque_limit' ? 0 : 3)} {unit}</b></span>
            <input type="range" min={lo} max={hi} step={step} value={body[k]}
              onChange={(e) => onBody({ ...body, [k]: parseFloat(e.target.value) })} />
            <small>{lo} – {hi}</small>
          </label>
        )
      })}
      <button className="link" onClick={() => onBody({ ...schema.body.defaults })}>reset to defaults</button>
      <h3>Experiment</h3>
      <label className="param inline">
        <input type="checkbox" checked={push.enabled} onChange={(e) => onPush({ ...push, enabled: e.target.checked })} />
        horizontal push on torso (0.15 s at t = {schema.preset.push.time} s)
      </label>
      <label className="param">
        <span>Push force <b>{push.force} N</b></span>
        <input type="range" min={0} max={80} step={1} value={push.force} disabled={!push.enabled}
          onChange={(e) => onPush({ ...push, force: parseFloat(e.target.value) })} />
      </label>
      <label className="param inline">seed
        <input type="number" min={0} value={seed} onChange={(e) => onSeed(Math.max(0, parseInt(e.target.value || '0', 10)))} />
      </label>
      <button className="forge" onClick={onForge} disabled={busy}>{busy ? 'Simulating…' : '🔥 Forge / Run Simulation'}</button>
      {error && <div className="error">Rejected: {error}</div>}
    </div>
  )
}
