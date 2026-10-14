import { useState } from 'react'
import { Block, Notice } from '../lab/Badges'
import { citedEvidence, KIND_INFO, paramDiffs, proposalOutcome, statusMessage, verdictText, type ParamDiff } from './demoLogic'
import { ReplayStep } from './Replay'
import type { DemoRun } from './demoTypes'

const num = (x: unknown, nd = 2) => (typeof x === 'number' ? x.toFixed(nd) : '—')
const fmt = (x: number) => (Math.abs(x) >= 100 ? x.toFixed(0) : Math.abs(x) >= 10 ? x.toFixed(1) : x.toFixed(3))

function Section({ n, title, children, testid }: { n: number; title: string; children: React.ReactNode; testid: string }) {
  return (
    <section className="story-sec" data-testid={testid}>
      <h3><span className="n">{n}</span>{title}</h3>
      <div className="story-body">{children}</div>
    </section>
  )
}

/** One parameter on its allowed range: the tick is where it was, the glowing marker is where the edit moved it. */
export function ParamTrack({ d, tone }: { d: ParamDiff; tone: 'model' | 'random' }) {
  const lo = Math.min(d.uBefore, d.uAfter)
  const hi = Math.max(d.uBefore, d.uAfter)
  return (
    <div className={`ptrack ${d.changed ? 'changed' : ''} ptrack-${tone}`} data-testid={`ptrack-${d.name}`} data-changed={d.changed}>
      <div className="pt-head">
        <b>{d.name}</b> <span className="dim">{d.meaning}</span>
        <span className="pt-val">{d.changed ? <>{fmt(d.before)} → <b>{fmt(d.after)}</b></> : fmt(d.before)}</span>
      </div>
      <div className="pt-rail" role="img" aria-label={`${d.name}: ${d.changed ? `${fmt(d.before)} to ${fmt(d.after)}` : fmt(d.before)} within ${fmt(d.lower)} to ${fmt(d.upper)}`}>
        {d.changed && <span className="pt-span" style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }} />}
        <span className="pt-before" style={{ left: `${d.uBefore * 100}%` }} />
        {d.changed && <span className="pt-after" style={{ left: `${d.uAfter * 100}%` }} />}
      </div>
      <div className="pt-bounds dim"><span>{fmt(d.lower)}</span><span>allowed range</span><span>{fmt(d.upper)}</span></div>
      {d.reflected && <small className="tone-warn">The requested step left the range, so the verifier reflected it at the bound.</small>}
    </div>
  )
}

function Diffs({ run, slot, who }: { run: DemoRun; slot: number; who: 'model' | 'random' }) {
  const all = paramDiffs(run, slot, who)
  const changed = all.filter((d) => d.changed)
  const rest = all.filter((d) => !d.changed)
  return (
    <div className="diffs">
      {changed.map((d) => <ParamTrack key={d.name} d={d} tone={who} />)}
      {rest.length > 0 && (
        <details>
          <summary>{rest.length} other controller parameters stay fixed</summary>
          <div className="diffs-rest">{rest.map((d) => <ParamTrack key={d.name} d={d} tone={who} />)}</div>
        </details>
      )}
    </div>
  )
}

function OutcomeBars({ run, slot }: { run: DemoRun; slot: number }) {
  const o = proposalOutcome(run, slot)
  if (!o) return null
  const rows = [
    { key: 'frozen', label: 'Unchanged controller', v: o.frozen, cls: 'bar-frozen' },
    { key: 'model', label: 'With the model’s edit', v: o.model, cls: 'bar-model' },
    { key: 'random', label: 'With a matched random edit', v: o.random, cls: 'bar-random' },
  ]
  return (
    <div className="outcome" data-testid="story-outcome">
      {rows.map((r) => (
        <div key={r.key} className="orow" data-testid={`outcome-${r.key}`}>
          <span className="olabel">{r.label}</span>
          <span className="otrack"><span className={`ofill ${r.cls}`} style={{ width: `${(r.v / o.n) * 100}%` }} /></span>
          <b>{r.v}/{o.n}</b><span className="dim"> walk</span>
        </div>
      ))}
    </div>
  )
}

export function Story({ run }: { run: DemoRun }) {
  const slots = run.interventions.map((i) => i.slot)
  const [slot, setSlot] = useState(slots[0] ?? 0)
  const iv = run.interventions.find((i) => i.slot === slot)
  const msg = statusMessage(run)
  const f = run.observed.metrics[String(run.observed.failing_seed)] ?? {}
  const w = run.observed.metrics[String(run.observed.walking_seed)] ?? {}
  const o = proposalOutcome(run, slot)
  const kind = run.provenance.kind
  const modelTag = kind === 'SCRIPTED_MOCK' ? 'SCRIPTED TEXT — not Nemotron' : kind === 'LIVE' ? 'Nemotron, live call' : 'Nemotron, recorded call'
  return (
    <div className="story" data-testid="demo-story">
      <Section n={1} title="What the robot is trying to do, and where it failed" testid="story-failure">
        <p>
          A 2-D biped is driven by the frozen Phase 2A walking controller. The goal is to walk upright for 10 s. On <b>seed {run.observed.failing_seed}</b> it{' '}
          {run.observed.failing_seed_walked ? 'walked' : <>falls at <b>{num(f.fall_time)} s</b> after {num(f.backward_steps, 0)} backward steps and {num(f.valid_steps, 0)} valid steps</>}; on{' '}
          <b>seed {run.observed.walking_seed}</b> the same controller walks ({num(w.valid_steps, 0)} valid steps, {num(w.speed_upright)} m/s).
        </p>
        <small className="dim">Only the random initial pose differs between seeds. All values are MuJoCo measurements.</small>
      </Section>

      <Section n={2} title="What evidence the AI received" testid="story-evidence">
        <p>The model got <b>measurements only</b>: the controller’s parameters, per-seed outcomes, step counts, pitch and timing. No conclusion and no hint of a fix.</p>
        {iv ? (
          <>
            <p>It cited these values in its proposal:</p>
            <ul className="cites">
              {citedEvidence(run, slot).map((c) => (
                <li key={c.path}><code>{c.path}</code> = <b>{c.value}</b> {!c.resolved && <span className="tone-bad">(not in the evidence sent)</span>}</li>
              ))}
            </ul>
          </>
        ) : <small className="dim">No usable proposal, so no citations were accepted.</small>}
        <small className="dim">The full context sent is under “Step-by-step details → What the model saw”.</small>
      </Section>

      <Section n={3} title="What Nemotron suggested" testid="story-proposal">
        {!iv ? (
          <Notice tone={msg.tone === 'ok' ? 'muted' : msg.tone} testid="story-noproposal">
            {msg.text} The investigation stops here, and no outcome is substituted. The raw reply is under “Step-by-step details → Model proposal”.
          </Notice>
        ) : (
          <>
            {slots.length > 1 && (
              <div className="slot-pick" role="tablist" aria-label="proposal">
                {slots.map((s) => (
                  <button key={s} role="tab" aria-selected={s === slot} className={s === slot ? 'on' : ''} data-testid={`story-slot-${s}`} onClick={() => setSlot(s)}>
                    Proposal {s + 1}: {run.interventions.find((i) => i.slot === s)!.proposal.edits.map((e) => e.parameter).join(' + ')}
                  </button>
                ))}
              </div>
            )}
            <Block kind="model" title={modelTag} testid="story-claim">
              <p>“{iv.proposal.claim}”</p>
              <small>Predicted: at least {iv.proposal.prediction.min_gain_seeds} more seeds walk · the model’s own confidence {(iv.proposal.confidence * 100).toFixed(0)}% (not calibrated). This is the model’s claim, not a result.</small>
            </Block>
          </>
        )}
      </Section>

      {iv && (
        <>
          <Section n={4} title="Which physical parameters change" testid="story-params">
            <p>Each edit is a bounded step on a controller parameter. The white tick marks where it was; the glowing marker shows where the edit moved it.</p>
            <Diffs run={run} slot={slot} who="model" />
          </Section>

          <Section n={5} title="What happened when MuJoCo tested it" testid="story-verify">
            {o ? (
              <>
                <p>Each controller ran on <b>{o.n} fresh seeds</b> that the model never saw.</p>
                <OutcomeBars run={run} slot={slot} />
                <p data-testid="story-verdict" className={`tone-${o.verdict ? verdictText(o.verdict).tone : 'muted'}`}>
                  {o.verdict ? <>Verdict: <b>{verdictText(o.verdict).text}</b> vs the unchanged controller. {o.predictionMet ? 'The prediction was met.' : 'The prediction was not met.'}</> : 'Not evaluated.'}{' '}
                  {o.beatRandom ? 'This proposal walked on more seeds than its matched random edit.' : <b>A matched random edit did as well or better ({o.random}/{o.n}), so this does not show the model chose well.</b>}
                </p>
                <details>
                  <summary>See the matched random edit that was used for comparison</summary>
                  <Diffs run={run} slot={slot} who="random" />
                </details>
              </>
            ) : <Notice tone="warn">No verification data in this record.</Notice>}
          </Section>

          <Section n={6} title="Watch the before and after, in sync" testid="story-replay">
            <ReplayStep key={slot} run={run} autoLoad initialWhich={`slot${slot}`} />
          </Section>
        </>
      )}
      <Notice tone="muted" testid="story-honesty">
        <b>Honest reading.</b> {KIND_INFO[kind].text} This is one recorded instance, not a statistical comparison of Nemotron against random edits (that experiment was not completed).
        The 150/150 vs 91/150 walking result on the Overview came from a classical optimiser, not from this model.
      </Notice>
    </div>
  )
}
