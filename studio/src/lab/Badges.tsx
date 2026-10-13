import type { ReactNode } from 'react'
import { statusInfo } from './labLogic'
import type { TrialStatus } from './labTypes'

/** Where a statement comes from. Solid = measured by MuJoCo; dashed = written by the model. */
export type Origin = 'measured' | 'model' | 'confidence'

const ORIGIN_TEXT: Record<Origin, string> = {
  measured: 'Measured by MuJoCo',
  model: 'Model-written · unverified',
  confidence: 'Self-reported by the model',
}

export function OriginBadge({ kind, hint }: { kind: Origin; hint?: string }) {
  return (
    <span className={`origin origin-${kind}`} title={hint} data-origin={kind}>
      {ORIGIN_TEXT[kind]}
    </span>
  )
}

export function StatusChip({ status }: { status: TrialStatus }) {
  const s = statusInfo(status)
  return (
    <span className={`chip chip-${s.tone}`} data-status={status}>
      {s.label}
    </span>
  )
}

/** A block whose border style encodes its origin. */
export function Block({
  kind,
  title,
  hint,
  children,
  testid,
}: {
  kind: Origin
  title: string
  hint?: string
  children: ReactNode
  testid?: string
}) {
  return (
    <section className={`block block-${kind}`} data-testid={testid}>
      <header>
        <h4>{title}</h4>
        <OriginBadge kind={kind} hint={hint} />
      </header>
      {children}
    </section>
  )
}

export function Notice({ tone = 'muted', children, testid }: { tone?: 'muted' | 'warn' | 'bad'; children: ReactNode; testid?: string }) {
  return (
    <div className={`notice notice-${tone}`} role={tone === 'bad' ? 'alert' : 'status'} data-testid={testid}>
      {children}
    </div>
  )
}
