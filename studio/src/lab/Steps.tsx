import { Block, Notice } from './Badges'
import {
  changeRows, directionWord, FORENSIC_LABEL, fmtDelta, fmtForensic, fmtMetric, fmtNum, metricLabel, metricRows, pct,
  predictionVerdict, statusInfo,
} from './labLogic'
import type { Consistency, LabView, Replay } from './labTypes'
import { Metrics } from '../Metrics'
import { HeightChart, Transport } from '../Timeline'
import { Viewport } from '../Viewport'

export type ReplayState =
  | { status: 'idle' }
  | { status: 'loading'; seed: number }
  | { status: 'error'; message: string; seed: number }
  | { status: 'ready'; data: Replay }

export interface ReplayControls {
  state: ReplayState
  seeds: number[]
  seed: number
  onSeed: (s: number) => void
  onLoad: () => void
}

/* ------------------------------------------------------------------ replay loader shared by Observe/Compare */

export function ReplayBar({ ctl, what }: { ctl: ReplayControls; what: string }) {
  const { state } = ctl
  const busy = state.status === 'loading'
  return (
    <div className="replay-bar">
      <label>
        Seed{' '}
        <select value={ctl.seed} onChange={(e) => ctl.onSeed(Number(e.target.value))} disabled={busy} aria-label="replay seed">
          {ctl.seeds.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <button data-testid="load-replay" onClick={ctl.onLoad} disabled={busy}>
        {busy ? 'Running MuJoCo…' : state.status === 'ready' ? 'Re-run MuJoCo replay' : `Load MuJoCo replay`}
      </button>
      <small>
        {what} Uses the saved parameters; no model call.
      </small>
    </div>
  )
}

export function ConsistencyBadge({ c, label }: { c: Consistency | undefined; label: string }) {
  if (!c) return null
  if (!c.checked) return <span className="cons cons-muted" data-testid="consistency">{label}: {c.reason}</span>
  const ok = c.matches_saved_record
  return (
    <span className={`cons ${ok ? 'cons-ok' : 'cons-bad'}`} data-testid="consistency" data-ok={String(ok)}
      title={ok ? `Max relative difference ${c.max_rel_diff?.toExponential(1)}` : (c.failures ?? []).join('\n')}>
      {ok ? '✓' : '✗'} {label}: {ok ? 'matches the saved record' : 'DIFFERS from the saved record'}
    </span>
  )
}

function ReplayProblem({ state }: { state: ReplayState }) {
  if (state.status === 'error')
    return <Notice tone="bad" testid="replay-error">Could not run the replay: {state.message}</Notice>
  return null
}

/* ------------------------------------------------------------------ 1 Observe */

export function ObserveStep({ view, ctl }: { view: LabView; ctl: ReplayControls }) {
  const o = view.observed
  if (!o) return null
  const sc = o.scenario
  const m = o.matched_seed_results
  const f = o.forensic_highlights
  return (
    <div className="step-body">
      <Block kind="measured" title="The original failure" hint={view.provenance.observed} testid="observed-block">
        {sc && (
          <p>
            A {sc.push.force_N} N push for {sc.push.duration_s} s at t = {sc.push.time_s} s, simulated for {sc.duration_s} s, with the
            same controller on seeds {sc.seeds.join(', ')}.
          </p>
        )}
        {m && (
          <div className="facts">
            <div><b data-testid="obs-fall-rate">{pct(m.fall_rate)}</b><span>of seeds fell</span></div>
            <div><b>{fmtNum(m.mean_min_torso_height_m)} m</b><span>lowest torso height (mean)</span></div>
            <div><b>{((m.mean_max_abs_pitch_rad * 180) / Math.PI).toFixed(0)}°</b><span>largest torso tilt (mean)</span></div>
          </div>
        )}
      </Block>

      {f ? (
        <Block kind="measured" title="Forensics: how it fell" hint={view.provenance.observed}>
          <dl className="kv">
            {Object.keys(FORENSIC_LABEL).filter((k) => k in f).map((k) => (
              <div key={k}><dt>{FORENSIC_LABEL[k]}</dt><dd>{fmtForensic(k, f[k])}</dd></div>
            ))}
          </dl>
          {o.timeline && (
            <details>
              <summary>Timeline around the push ({o.timeline.rows.length} samples)</summary>
              <div className="scroll">
                <table className="timeline">
                  <thead><tr>{o.timeline.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>
                    {o.timeline.rows.map((r, i) => (
                      <tr key={i}>{r.map((v, j) => <td key={j}>{v == null ? '—' : v}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </Block>
      ) : (
        <Notice testid="no-forensics">This record used the compact evidence format, so there is no forensic timeline. Only aggregate results were shown to the model.</Notice>
      )}

      {view.replay.available ? (
        <Block kind="measured" title="Watch the original robot" hint="Poses come from a fresh MuJoCo run of the saved scenario.">
          <ReplayBar ctl={ctl} what="Re-simulates the original failure." />
          <ReplayProblem state={ctl.state} />
          {ctl.state.status === 'ready' && (
            <>
              <ConsistencyBadge c={ctl.state.data.consistency.baseline} label="original" />
              <Viewport run={ctl.state.data.baseline} label={`ORIGINAL · seed ${ctl.state.data.seed}`} />
              <Transport runs={[{ run: ctl.state.data.baseline, label: 'original', color: '#e5484d' }]} />
            </>
          )}
        </Block>
      ) : (
        <Notice tone="warn">The saved scenario is incomplete, so it cannot be replayed.</Notice>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ 2 Hypothesize */

export function HypothesizeStep({ view }: { view: LabView }) {
  const r = view.rationale
  if (!r) return null
  const pv = view.predicted_vs_measured
  return (
    <div className="step-body">
      <Block kind="model" title="What the model claimed" hint={view.provenance.hypothesis} testid="hypothesis-block">
        <blockquote data-testid="claim">{r.claim}</blockquote>
        {r.mechanism && <p className="dim">Mechanism label: <code>{r.mechanism}</code></p>}
        <Notice>This is a hypothesis, not an established cause. MuJoCo decides whether it holds.</Notice>
      </Block>

      <Block kind="confidence" title="How sure it said it was" hint={view.provenance.confidence}>
        <div className="meter" role="img" aria-label={`self-reported confidence ${Math.round(r.confidence * 100)}%`}>
          <i style={{ width: `${Math.round(r.confidence * 100)}%` }} />
        </div>
        <p><b>{Math.round(r.confidence * 100)}%</b> <span className="dim">— self-reported and uncalibrated. The verifier never uses it.</span></p>
      </Block>

      <Block kind="measured" title="Measurements it cited" hint="Each value is looked up in the saved MuJoCo evidence.">
        {r.cited.length === 0 ? <p className="dim">The model cited no measurements.</p> : (
          <table className="cited">
            <tbody>
              {r.cited.map((c) => (
                <tr key={c.path} className={c.missing ? 'missing' : ''}>
                  <td><code>{c.path}</code></td>
                  <td>{c.missing ? 'not found in the evidence' : typeof c.value === 'number' ? c.value : JSON.stringify(c.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Block>

      {pv && (
        <Block kind="model" title="What it predicted" hint={view.provenance.hypothesis}>
          <p>
            The <b>{metricLabel(pv.metric)}</b> should <b>{directionWord(pv.direction)}</b> after the change.
            <span className="dim"> Checked in the Verify step.</span>
          </p>
        </Block>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ 3 Intervene */

export function InterveneStep({ view }: { view: LabView }) {
  const d = view.design_change
  if (!d) return null
  const rows = changeRows(d.original_body, d.modified_body)
  return (
    <div className="step-body">
      <Block kind="model" title="The change it proposed" hint="The model chose one parameter and a new value; the code only checks it is within bounds." testid="change-block">
        <p>
          Change <code>{d.parameter}</code> from <b>{d.original}</b> to <b data-testid="proposed-value">{d.modified}</b>.
        </p>
      </Block>
      <Block kind="measured" title="Everything else stays the same" hint="The candidate body is the original with exactly one value replaced.">
        <table className="params" data-testid="param-table">
          <thead><tr><th>Parameter</th><th>Original</th><th>Modified</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className={r.changed ? 'changed' : ''}>
                <td>{r.name}</td><td>{r.original}</td><td>{r.changed ? <b>{r.modified}</b> : r.modified}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <small>Controller, push, seeds and duration are identical for both robots.</small>
      </Block>
    </div>
  )
}

/* ------------------------------------------------------------------ 4 Verify */

export function VerifyStep({ view }: { view: LabView }) {
  const pv = view.predicted_vs_measured
  const v = view.verdict
  if (!pv) return null
  const info = statusInfo(view.outcome.status)
  const screening = predictionVerdict(pv.held_on_screening_seeds)
  const heldout = predictionVerdict(pv.held_on_heldout_primary)
  const levels = pv.heldout_by_push ? Object.keys(pv.heldout_by_push).sort((a, b) => Number(a) - Number(b)) : []
  const heldSeeds = view.protocol_config?.heldout_seeds
  return (
    <div className="step-body">
      <Block kind="measured" title="Verdict" hint={view.provenance.measured} testid="verdict-block">
        <p className={`verdict verdict-${info.tone}`} data-testid="verdict">
          <b>{info.label}</b>{v ? ` — tier “${v.tier}”` : ''}. {info.summary}
        </p>
        {view.outcome.reason && <p className="dim">Recorded reason: <code>{view.outcome.reason}</code></p>}
        <p>
          Prediction (<i>{metricLabel(pv.metric)} should {directionWord(pv.direction)}</i>):{' '}
          <span className={`tone-${screening.tone}`}>{screening.text}</span> on the 5 screening seeds,{' '}
          <span className={`tone-${heldout.tone}`}>{heldout.text}</span> at the primary held-out push.
        </p>
        {v && v.levels_where_candidate_worse.length > 0 && (
          <Notice tone="warn">The modified robot fell more often than the original at {v.levels_where_candidate_worse.map((l) => `${l} N`).join(', ')}.</Notice>
        )}
      </Block>

      <Block kind="measured" title="Screening: same seeds as the evidence" hint={view.provenance.measured}>
        <table className="cmp">
          <thead><tr><th>Metric</th><th>Original</th><th>Modified</th><th>Change</th></tr></thead>
          <tbody>
            {metricRows(pv.screening_observed).map(({ metric, pair }) => (
              <tr key={metric}>
                <td>{metricLabel(metric)}</td>
                <td>{fmtMetric(metric, pair.baseline)}</td>
                <td>{fmtMetric(metric, pair.candidate)}</td>
                <td>{metric === 'fall_rate' ? `${fmtDelta(pair.delta * 100, 0)} pts` : fmtDelta(pair.delta)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Block>

      {pv.heldout_by_push && (
        <Block kind="measured" title="Held-out test: seeds never used for evidence" hint="The original evaluation protocol, recorded when the trial ran.">
          <table className="cmp" data-testid="heldout-table">
            <thead><tr><th>Push</th><th>Original fall rate</th><th>Modified fall rate</th><th>Mean time standing (s)</th></tr></thead>
            <tbody>
              {levels.map((k) => {
                const row = pv.heldout_by_push![k]
                const primary = Number(k) === view.protocol_config?.primary_push_N
                return (
                  <tr key={k} className={primary ? 'primary' : ''}>
                    <td>{Number(k)} N{primary ? ' · primary' : ''}</td>
                    <td>{pct(row.baseline.fall_rate)} <span className="dim">({row.baseline.falls}/{row.baseline.n})</span></td>
                    <td>{pct(row.candidate.fall_rate)} <span className="dim">({row.candidate.falls}/{row.candidate.n})</span></td>
                    <td>{fmtNum(row.baseline.mean_survival_s, 2)} → {fmtNum(row.candidate.mean_survival_s, 2)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <small>
            {view.protocol_simulations ?? '—'} simulations on held-out seeds {heldSeeds ? `${heldSeeds[0]}–${heldSeeds[heldSeeds.length - 1]}` : ''}.
            Success needs a primary fall rate ≤ 20% and no push level where the modified robot is worse.
          </small>
        </Block>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ 5 Compare */

export function CompareStep({ view, ctl }: { view: LabView; ctl: ReplayControls }) {
  const d = view.design_change
  const ready = ctl.state.status === 'ready' ? ctl.state.data : null
  const cand = ready?.candidate ?? null
  return (
    <div className="step-body">
      <Block kind="measured" title="Original and modified robot, side by side" hint="A fresh MuJoCo run of both bodies from the saved parameters." testid="compare-block">
        <ReplayBar ctl={ctl} what={`Re-simulates both robots on one seed${d ? `; only ${d.parameter} differs.` : '.'}`} />
        <ReplayProblem state={ctl.state} />
        {ctl.state.status === 'idle' && <p className="dim">Load the replay to watch both robots on one synchronized clock.</p>}
        {ready && cand && (
          <>
            <div className="cons-row">
              <ConsistencyBadge c={ready.consistency.baseline} label="original" />
              <ConsistencyBadge c={ready.consistency.candidate} label="modified" />
            </div>
            <div className="pair" data-testid="compare-pair">
              <Viewport run={ready.baseline} label={`ORIGINAL · ${d?.parameter} ${d?.original}`} />
              <Viewport run={cand} label={`MODIFIED · ${d?.parameter} ${d?.modified}`} />
            </div>
            <Transport runs={[{ run: ready.baseline, label: 'original', color: '#e5484d' },
              { run: cand, label: 'modified', color: '#4cc2ff' }]} />
            <div className="below">
              <HeightChart runs={[{ run: ready.baseline, label: 'original', color: '#e5484d' },
                { run: cand, label: 'modified', color: '#4cc2ff' }]} />
              <div className="outcomes" data-testid="outcomes">
                <h4>This replay (seed {ready.seed})</h4>
                <table className="cmp">
                  <thead><tr><th></th><th>Original</th><th>Modified</th></tr></thead>
                  <tbody>
                    <tr><td>fell</td><td>{ready.baseline.metrics.fell ? 'yes' : 'no'}</td><td>{cand.metrics.fell ? 'yes' : 'no'}</td></tr>
                    <tr><td>lowest torso height</td><td>{ready.baseline.metrics.min_torso_height.toFixed(3)} m</td><td>{cand.metrics.min_torso_height.toFixed(3)} m</td></tr>
                    <tr><td>largest tilt</td><td>{((ready.baseline.metrics.max_abs_pitch * 180) / Math.PI).toFixed(0)}°</td><td>{((cand.metrics.max_abs_pitch * 180) / Math.PI).toFixed(0)}°</td></tr>
                  </tbody>
                </table>
                <small>One seed is an illustration. The verdict in the Verify step rests on many seeds.</small>
              </div>
            </div>
            <div className="pair">
              <Metrics run={ready.baseline} label="Original" />
              <Metrics run={cand} label="Modified" />
            </div>
          </>
        )}
      </Block>
    </div>
  )
}

