import { useEffect, useMemo, useState } from 'react'
import { getDo1Index, getDo1Payload } from '../api'
import { ReplayBoundary } from '../forge/ReplayBoundary'
import { usePlayback } from '../store'
import { HeightChart, Transport } from '../Timeline'
import { Viewport } from '../Viewport'
import { cards, checkText, DESIGN_COLOR, DESIGN_NAME, DESIGNS, fmtM, outcomeText, rowFor, seedOptionText, shortHash, whyNotFull, type Card } from './do1Logic'
import type { DesignId, Do1Index, Do1Payload, Do1Row } from './do1Types'
import './do1.css'

type Mode = 'validation' | 'confirmation'

/** 24 validation seeds of one design: filled = walked. Click a seed to replay it in all three viewports. */
function SeedDots({ id, rows, selected, onPick }: { id: DesignId; rows: Do1Row[]; selected: number | null; onPick: (s: number) => void }) {
  return (
    <div className="do1-dots" role="group" aria-label={`${DESIGN_NAME[id]}: walking per validation seed`}>
      {rows.map((r) => (
        <button key={r.seed} type="button" className={`do1-dot ${r.walking ? 'on' : ''} ${r.seed === selected ? 'sel' : ''}`}
          title={`seed ${r.seed}: ${outcomeText(r)}, ${fmtM(r.score)}`} aria-label={`seed ${r.seed} ${r.walking ? 'walked' : 'did not walk'}`}
          onClick={() => onPick(r.seed)} />
      ))}
    </div>
  )
}

function CardView({ c, idx, seed, onPick }: { c: Card; idx: Do1Index; seed: number | null; onPick: (s: number) => void }) {
  return (
    <article className={`do1-card tone-${c.tone}`} data-testid={`do1-card-${c.id}`} style={{ ['--c' as string]: DESIGN_COLOR[c.id] }}>
      <header>
        <span className="do1-swatch" />
        <h3>{c.name}</h3>
        {c.status ? <span className={`fg-chip do1-status do1-status-${c.tone}`} data-testid={`do1-status-${c.id}`}>{c.status}</span>
          : <span className="fg-chip fg-chip-original">BASELINE</span>}
      </header>
      <div className="do1-big"><b data-testid={`do1-walk-${c.id}`}>{c.walking}/{c.n}</b><span>validation seeds walking</span></div>
      <SeedDots id={c.id} rows={idx.rows[c.id]} selected={seed} onPick={onPick} />
      <dl>
        <dt>Median distance</dt><dd data-testid={`do1-median-${c.id}`}>{fmtM(c.median)}</dd>
        <dt>Vs the faulty robot</dt>
        <dd>{c.gain ? <><b>{fmtM(c.gain.median, true)}</b> median paired gain · {c.gain.wins}/{c.gain.losses}/{c.gain.ties} better/worse/tied · {c.gain.status.replace(/_/g, ' ').toLowerCase()}</>
          : 'the reference every repair is paired against'}</dd>
        {c.confirmation && <>
          <dt>20 s confirmation</dt>
          <dd data-testid={`do1-confirm-${c.id}`}>{c.confirmation.run
            ? <><b>{c.confirmation.walking}/{c.confirmation.n}</b> walking · {c.confirmation.passed ? 'passed' : 'failed'}</>
            : <>not run ({c.confirmation.reason})</>}</dd>
        </>}
      </dl>
    </article>
  )
}

export function Do1Recovery() {
  const [idx, setIdx] = useState<Do1Index | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>('validation')
  const [seed, setSeed] = useState<number | null>(null)
  const [confSeed, setConfSeed] = useState<number | null>(null)
  const [runs, setRuns] = useState<{ id: DesignId; run: Do1Payload }[] | null>(null)
  const [runError, setRunError] = useState<string | null>(null)

  useEffect(() => {
    getDo1Index()
      .then((i) => { setIdx(i); setSeed(i.default_seed); setConfSeed(i.seeds.confirm[0]) })
      .catch((e: Error) => setError(e.message))
  }, [])

  const derived = useMemo(() => {
    if (!idx) return null
    try {
      return { cards: cards(idx), why: whyNotFull(idx) }
    } catch (e) {
      return { error: (e as Error).message }
    }
  }, [idx])

  const shown = mode === 'validation' ? seed : confSeed
  useEffect(() => {
    if (!idx || shown === null) return
    let alive = true
    setRuns(null)
    setRunError(null)
    const ids: DesignId[] = mode === 'validation' ? DESIGNS : ['do1']
    Promise.all(ids.map((id) => getDo1Payload(id, mode === 'validation' ? 10 : 20, shown)))
      .then((rs) => {
        if (!alive) return
        setRuns(rs.map((run, i) => ({ id: ids[i], run })))
        const pb = usePlayback.getState()
        pb.setDuration(Math.max(...rs.map((r) => r.do1_demo.duration_s)))
        pb.restart()
      })
      .catch((e: Error) => alive && setRunError(e.message))
    return () => { alive = false }
  }, [idx, mode, shown])

  if (error) return <main className="do1"><div className="error" role="alert" data-testid="do1-error">Could not load the verified DO-1 replays: {error}</div></main>
  if (!idx || !derived) return <main className="do1"><div className="fg-skeleton skeleton" data-testid="do1-loading" /></main>
  if ('error' in derived) return <main className="do1"><div className="error" role="alert" data-testid="do1-error">The DO-1 evidence is inconsistent: {derived.error}</div></main>

  const { cards: cs, why } = derived
  const pick = (s: number) => { setMode('validation'); setSeed(s) }
  const chart = runs?.map((r) => ({ run: r.run, label: DESIGN_NAME[r.id].toLowerCase(), color: DESIGN_COLOR[r.id] })) ?? []
  const env = idx.provenance.environment
  const noModel = idx.provenance.arms_nemotron.every((x) => x === null)

  return (
    <main className="do1" data-testid="do1-recovery">
      <section className="do1-hero">
        <div>
          <p className="do1-kicker">Verified repair · robot L4 · hidden low-friction fault</p>
          <h2>One hidden fault, two optimizer repairs</h2>
          <p className="do1-lede">The same damaged robot, the same starting state and the same {idx.rows.faulty.length} held-out validation
            conditions. The two repairs differ only in the objective the plant optimizer ranked its candidates by. Every replay
            below is the exact rollout the independent verifier scored.</p>
        </div>
        <ul className="do1-flags">
          <li className="do1-flag do1-flag-noai" data-testid="do1-attribution">{idx.captions.attribution}</li>
          <li className="do1-flag" data-testid="do1-scope">{idx.captions.scope}</li>
        </ul>
      </section>

      <section className="do1-cards" data-testid="do1-cards">
        {cs.map((c) => <CardView key={c.id} c={c} idx={idx} seed={mode === 'validation' ? seed : null} onPick={pick} />)}
      </section>

      <section className="fg-card do1-stage" data-testid="do1-stage">
        <div className="do1-controls">
          <div className="do1-seg" role="tablist" aria-label="replay set">
            <button role="tab" aria-selected={mode === 'validation'} data-testid="do1-mode-validation" onClick={() => setMode('validation')}>Validation · 10 s · all three</button>
            <button role="tab" aria-selected={mode === 'confirmation'} data-testid="do1-mode-confirmation" onClick={() => setMode('confirmation')}>DO-1 confirmation · 20 s</button>
          </div>
          {mode === 'validation' ? (
            <>
              <label className="fg-field fg-inline">
                <span>Validation seed</span>
                <select value={seed ?? ''} onChange={(e) => setSeed(Number(e.target.value))} aria-label="validation seed" data-testid="do1-seed">
                  {idx.seeds.validate.map((s) => <option key={s} value={s}>{seedOptionText(idx, s)}</option>)}
                </select>
              </label>
              {seed === idx.default_seed
                ? <span className="do1-badge" data-testid="do1-illustrative">Illustrative seed · pre-declared rule</span>
                : <button type="button" className="do1-link" onClick={() => setSeed(idx.default_seed)} data-testid="do1-reset-seed">Back to the illustrative seed</button>}
            </>
          ) : (
            <label className="fg-field fg-inline">
              <span>Confirmation seed</span>
              <select value={confSeed ?? ''} onChange={(e) => setConfSeed(Number(e.target.value))} aria-label="confirmation seed" data-testid="do1-conf-seed">
                {idx.seeds.confirm.map((s) => <option key={s} value={s}>{`${s} · DO-1 ${rowFor(idx, 'do1_confirm', s).walking ? '✓' : '✗'}`}</option>)}
              </select>
            </label>
          )}
        </div>
        <p className="do1-note" data-testid="do1-seed-note">{mode === 'validation' ? idx.captions.seed
          : 'DO-1 only: the frozen repair failed the validation walking gate, so the verifier never ran its 20 s confirmation.'}</p>

        {runError && <div className="error" role="alert" data-testid="do1-replay-error">Replay failed: {runError}</div>}
        {!runs && !runError && <div className="fg-skeleton skeleton" data-testid="do1-replay-loading" />}
        {runs && shown !== null && (
          <ReplayBoundary resetKey={`${mode}-${shown}`}>
            <div className={`do1-views do1-views-${runs.length}`} data-testid="do1-viewports">
              {runs.map(({ id, run }) => {
                const row = mode === 'validation' ? rowFor(idx, id, shown) : rowFor(idx, 'do1_confirm', shown)
                return (
                  <figure key={id} className="do1-view" style={{ ['--c' as string]: DESIGN_COLOR[id] }} data-testid={`do1-view-${id}`}>
                    <Viewport closeup run={run} label={`${DESIGN_NAME[id]} · seed ${shown}`} />
                    <figcaption className={row.walking ? 'ok' : 'bad'} data-testid={`do1-outcome-${id}`}>
                      <b>{outcomeText(row)}</b> · scored distance {fmtM(row.score)}
                    </figcaption>
                  </figure>
                )
              })}
            </div>
            <Transport runs={chart} />
            <HeightChart runs={chart} />
          </ReplayBoundary>
        )}
      </section>

      <section className="fg-card do1-why" data-testid="do1-why">
        <h3>Why the frozen repair's longer walk is not a full recovery</h3>
        <ol>
          <li><b>Distance.</b> The frozen repair's median distance is {fmtM(why.frozenMedian)}, {fmtM(why.frozenAhead)} more than DO-1's {fmtM(why.do1Median)}.
            Both beat the faulty robot by a verified margin: median paired gains {fmtM(why.frozenGain, true)} and {fmtM(why.do1Gain, true)}.</li>
          <li><b>Reliability.</b> {idx.criteria.rule} also requires at least {why.passPct}% of the {why.n} validation seeds to walk, i.e. {why.needWalking}/{why.n}.
            The frozen repair walks on <b data-testid="do1-why-frozen">{why.frozenWalking}/{why.n}</b> (aggregate {why.frozenAggregate}); DO-1 walks on <b>{why.do1Walking}/{why.n}</b>.</li>
          <li><b>Endurance.</b> {why.frozenConfirmationRan ? 'The frozen repair ran the 20 s confirmation.' : 'Because the frozen repair failed the walking gate, its 20 s confirmation was never run.'} DO-1's confirmation:{' '}
            {why.do1Checks.map(checkText).join('; ')}.</li>
        </ol>
        <blockquote data-testid="do1-why-reason">Recorded verifier reason for the frozen repair: “{why.frozenReasons.join('; ')}”</blockquote>
        <p className="do1-note">DO-1 travels less far but walks on more seeds and passes the long run. It is a deterministic change to the optimizer's objective;
          the recorded provenance of both arms is {idx.provenance.arms_provenance_recorded.join(' and ')}{noModel ? ', and no Nemotron call was made in either' : ''}.
          This is one exploratory technical replicate on one robot: it shows that the objective can recover this instance, not how often it would.
          A later pre-registered replication on this same robot with fresh optimizer seeds, and a pilot on two other fault families, is reported with its limits in <code>docs/DO1_REPLICATION_REPORT.md</code>.</p>
      </section>

      <footer className="do1-prov" data-testid="do1-provenance">
        <b>Evidence.</b> Audited record <code>{idx.provenance.record}</code> (sha256 {shortHash(idx.provenance.record_sha256)}), harness {idx.provenance.harness_commit.slice(0, 7)}.
        Replays exported by {idx.exporter} at {idx.provenance.exporter_commit.slice(0, 7)} on {env.system} {env.machine}, Python {env.python}, numpy {env.numpy}, MuJoCo {env.mujoco}:
        {' '}<span data-testid="do1-fidelity">{idx.fidelity.production_rows_exact} rows on the verifier's own path and {idx.fidelity.trace_rows_exact} on the frame path reproduced exactly, max frame error {idx.fidelity.fk_max_err_m} m</span>.
        Frames are the {idx.frame_state} simulation state. The page only plays these files back; nothing is simulated in the browser or the server.
      </footer>
    </main>
  )
}
