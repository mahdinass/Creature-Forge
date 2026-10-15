import { useEffect, useState } from 'react'
import { acceptArm, getSandboxSchema } from '../api'
import { ParamTrack } from '../demo/parts'
import type { SandboxSchema } from '../sketch/freehandTypes'
import { acceptBlockReason, armChip, bodyDiffs, canAccept, controllerDiffs, verdictText } from './forgeLogic'
import type { Arm, Creature, CreatureVersion, InvestigationRecord } from './forgeTypes'
import { ProvChip } from './ArenaCompare'

/** What the arm changes, and the one decision: accept (only for a verified improvement) or reject (dismiss). */
export function AcceptPanel({ cid, version, record, arm, onAccepted }: {
  cid: string
  version: CreatureVersion
  record: InvestigationRecord
  arm: Arm
  onAccepted: (c: Creature) => void
}) {
  const [schema, setSchema] = useState<SandboxSchema | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState(false)
  useEffect(() => { getSandboxSchema().then(setSchema).catch(() => undefined) }, [])
  useEffect(() => { setDismissed(false); setError(null) }, [arm.arm_id, record.id])

  const verdict = record.verdicts?.[arm.arm_id]
  const allowed = canAccept(arm, verdict)
  const reason = acceptBlockReason(arm, verdict)
  const bounds = schema ? (version.mode === 'guided' ? schema.scientific_bounds : schema.sandbox_bounds) : {}
  const diffs = bodyDiffs(version.body as unknown as Record<string, unknown>, arm.body, bounds)
  const changed = diffs.filter((d) => d.changed)
  const ctrl = controllerDiffs(version.controllers, arm.controllers)
  const chip = armChip(arm, record.provenance)

  const accept = async () => {
    setBusy(true)
    setError(null)
    try {
      onAccepted(await acceptArm(cid, { investigation_id: record.id, arm_id: arm.arm_id }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (dismissed) return <section className="fg-card" data-testid="accept-dismissed"><p>Dismissed. Nothing was changed; your creature stays at v{version.n}.</p></section>
  return (
    <section className="fg-card fg-accept" data-testid="accept-panel" data-can-accept={allowed}>
      <h3>What this change does <ProvChip {...chip} /></h3>
      {arm.edits && arm.edits.length > 0 && (
        <ul className="fg-edits">{arm.edits.map((e, i) => <li key={i}><b>{e.param}</b> {e.op === 'scale' ? `x ${e.value}` : `set to ${e.value}`}{e.target && e.target !== 'both' ? ` (${e.target} leg)` : ''}</li>)}</ul>
      )}
      {changed.map((d) => <ParamTrack key={d.name} d={d} tone="model" />)}
      {ctrl.length > 0 && (
        <div className="table-scroll"><table><thead><tr><td>controller value</td><td>before</td><td>after</td></tr></thead>
          <tbody>{ctrl.map((r) => <tr key={r.name}><td className="fg-left">{r.name}</td><td>{r.before}</td><td>{r.after}</td></tr>)}</tbody></table></div>
      )}
      {changed.length === 0 && ctrl.length === 0 && <p className="fg-dim">No parameter differences were recorded for this arm.</p>}
      <p className="fg-dim" data-testid="accept-verdict">{verdictText(verdict)}</p>
      {reason && <p className="fg-note-box" data-testid="accept-blocked">{reason}</p>}
      {error && <div className="error" role="alert" data-testid="accept-error">{error}</div>}
      <div className="fg-actions">
        <button className="btn btn-investigate" disabled={!allowed || busy} data-testid="accept-btn" onClick={() => void accept()}>{busy ? 'Accepting...' : 'Accept as a new version'}</button>
        <button className="btn btn-ghost" disabled={busy} data-testid="reject-btn" onClick={() => setDismissed(true)}>Reject</button>
      </div>
    </section>
  )
}
