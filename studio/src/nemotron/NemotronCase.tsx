import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { getNemotronCase } from '../api'
import { Chip } from '../causal/Investigation'
import { statusInfo } from '../causal/causalLogic'
import {
  beliefShift, crossCheck, experimentName, explanationName, fmtUsd, fmtW, followed, forkOf, hypothesisName, LANE_COLOR, LANE_NAME,
  illustrativeSeed, outcomeOfFeatures, outcomeOfRow, shortId, studyTone, verifiedWalking, walkingOf, type Lane,
} from './nemotronLogic'
import type { ArmView, Experiment, NemotronCaseResponse, ReplayStatus, SeedFeatures, W2Case } from './nemotronTypes'
import { PlantReplay, type ReplayLane } from './PlantReplay'
import '../causal/causal.css'
import './nemotron.css'

const f2 = (x: number | null | undefined, d = 2) => (x == null ? 'n/a' : x.toFixed(d))
const twinCheck = (a: ArmView) => { const d = a.designs.find((x) => x.source.startsWith('twin:') && x.check); return d?.check ? `${d.check[0]}/${d.check[1]}` : 'n/a' }

function Stage({ n, title, children, testid }: { n: number; title: string; children: ReactNode; testid: string }) {
  return (
    <section className="nm-stage" data-testid={testid}>
      <header className="nm-stage-head"><span className="nm-num" aria-hidden="true">{n}</span><h2>{title}</h2></header>
      <div className="nm-stage-body">{children}</div>
    </section>
  )
}

function LaneTag({ lane }: { lane: Lane | 'A4' }) {
  return <span className="nm-lanetag" style={{ ['--c' as string]: LANE_COLOR[lane] }}>{LANE_NAME[lane]}</span>
}

/** Per-seed plant measurements, one tile per seed. Measured by MuJoCo on the hidden (damaged) plant during the recorded run. */
function SeedTiles({ e, testid }: { e: Experiment; testid: string }) {
  const k = walkingOf(e)
  return (
    <div className="nm-tiles-wrap" data-testid={testid}>
      <p className="nm-tiles-sum"><b>{k}/{e.per_seed.length}</b> trials walked · {experimentName(e.id)}</p>
      <ul className="nm-tiles">
        {e.per_seed.map((s: SeedFeatures) => (
          <li key={s.seed} className={s.walking === 1 ? 'walk' : 'nowalk'} title={`seed ${s.seed}`}>
            <b>{s.walking === 1 ? 'walks' : (s.time_upright ?? 10) < 10 ? `falls at ${f2(s.time_upright, 1)} s` : 'upright, not walking'}</b>
            <span>{f2(s.com_vx_mean)} m/s · {f2(s.step_freq_hz, 1)} steps/s</span>
            <span>double support {f2((s.double_support_fraction ?? 0) * 100, 0)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Bars({ rows, testid }: { rows: { name: string; w: number }[]; testid?: string }) {
  return (
    <ul className="nm-bars" data-testid={testid}>
      {rows.map((r, i) => (
        <li key={i}><span className="nm-bar-name">{r.name}</span>
          <span className="nm-bar"><span className={`nm-bar-fill nm-fill-${r.name.startsWith('Right') ? 'right' : r.name.startsWith('Left') ? 'left' : 'other'}`}
            style={{ width: `${Math.max(1.5, r.w * 100)}%` }} /></span>
          <b className="nm-bar-w">{fmtW(r.w)}</b></li>
      ))}
    </ul>
  )
}

function Words({ who, children }: { who: string; children: ReactNode }) {
  return <blockquote className="nm-words"><cite>{who}</cite>{children}</blockquote>
}

function Fork({ c }: { c: W2Case }) {
  const fk = forkOf(c)
  const nem = c.fork.nemotron, eng = c.fork.engine
  const H = ['H1 right-side weakness', 'H2 left-side weakness', 'H3']
  return (
    <>
      <p className="nm-p">Both arms now hold the same notebook. The belief engine lists seven experiments, each with its expected information gain
        and the walking it predicts under the leading explanations. {fk.eigTied ? <b>Every candidate shows the same expected information gain ({fk.candidates[0].eig.toFixed(2)} nats) — the
        engine's own measure cannot tell them apart.</b> : null}</p>
      <div className="nm-tablewrap">
        <table className="nm-cands" data-testid="nm-candidates">
          <caption>Candidate experiments shown to Nemotron on turn 0 (predicted walking out of {c.fork.notebook.predicted_out_of} trials)</caption>
          <thead><tr><th>Experiment</th><th>EIG (nats)</th>{H.map((h) => <th key={h}>{h}</th>)}<th>Separates H1 from H2?</th><th>Chosen by</th></tr></thead>
          <tbody>
            {fk.candidates.map((x) => (
              <tr key={x.id} className={`${x.nemotron ? 'pick-nem' : ''} ${x.engine ? 'pick-eng' : ''}`}>
                <td><code>{x.id}</code><small>{experimentName(x.id)}</small></td>
                <td>{x.eig.toFixed(2)}</td>
                {x.predicted_walking.map((p, i) => <td key={i}>{p}/{c.fork.notebook.predicted_out_of}</td>)}
                <td>{x.contrast ? 'yes' : '—'}</td>
                <td>{x.nemotron && <LaneTag lane="A3" />}{x.engine && <LaneTag lane="A1e" />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="nm-lanes">
        <div className="nm-lane" style={{ ['--c' as string]: LANE_COLOR.A3 }} data-testid="nm-fork-nemotron">
          <LaneTag lane="A3" />
          <h3>Picks <code>{nem.experiment}</code></h3>
          <Words who="Nemotron, turn 0 (recorded reply, verbatim)"><p>{nem.words.why}</p></Words>
          <p className="nm-small">Recorded EIG of its pick {nem.eig.toFixed(3)} vs best {nem.best_eig.toFixed(3)} nats. Its claim that this is
            "more informative than the engine's default" holds for the predicted walking contrast it cites ({nem.predicted_walking?.[0]}/{c.fork.notebook.predicted_out_of} vs{' '}
            {nem.predicted_walking?.[1]}/{c.fork.notebook.predicted_out_of}), not for the engine's EIG.</p>
          <p className="nm-flag nm-flag-warn" data-testid="nm-prediction">Registered prediction: <b>none</b>. Nemotron stated its expectation only in the words
            above and returned an empty structured prediction, so the agent recorded it as missing ({nem.prediction_issue}). Nothing here is scored as a
            registered forecast.</p>
          <p className="nm-small nm-callmeta">request <code>{nem.call.request_id}</code> · {nem.call.latency_s} s · {nem.call.prompt_tokens} prompt +{' '}
            {nem.call.completion_tokens} completion tokens ({nem.call.reasoning_tokens} reasoning) · {fmtUsd(nem.call.cost_usd)} · temperature {nem.call.temperature}</p>
        </div>
        <div className="nm-lane" style={{ ['--c' as string]: LANE_COLOR.A1e }} data-testid="nm-fork-engine">
          <LaneTag lane="A1e" />
          <h3>Picks <code>{eng.experiment}</code></h3>
          <p className="nm-p">Rule: "{eng.why}". EIG {eng.eig.toFixed(3)} nats — ahead of Nemotron's pick by {(eng.eig - nem.eig).toFixed(3)}. Its predicted walking is {eng.predicted_walking?.join('/')} out of{' '}
            {c.fork.notebook.predicted_out_of}: the same under both sides, so a left/right answer must come from subtler gait features.</p>
          <p className="nm-small">Deterministic; no model call (provenance NO_AI).</p>
        </div>
      </div>
    </>
  )
}

function Verification({ a, testid }: { a: ArmView; testid: string }) {
  const st = statusInfo(a.verification.status)
  const { k, n } = verifiedWalking(a)
  return (
    <div className="nm-verify" style={{ ['--c' as string]: LANE_COLOR[a.arm] }} data-testid={testid}>
      <LaneTag lane={a.arm} />
      <p className="nm-bigstatus"><Chip tone={st.tone}>{st.label}</Chip></p>
      <p className="nm-big"><b>{k}/{n}</b> hidden validation starts walk</p>
      <p className="nm-small">{a.verification.rollouts.confirmation ? `20 s confirmation on ${a.verification.rollouts.confirmation} more starts: ${a.verification.reasons.length ? 'failed' : 'passed'}.`
        : '20 s confirmation not run (validation below 80%).'}</p>
      {a.verification.reasons.map((r) => <p key={r} className="nm-reason">Verifier: "{r}"</p>)}
      <p className="nm-small">Submitted design {a.submitted.index}: <code>{a.submitted.source}</code> ({a.submitted.design_hash})</p>
    </div>
  )
}

function RepairLane({ a }: { a: ArmView }) {
  const checks = Object.fromEntries(a.designs.map((d) => [d.index, d.check]))
  return (
    <div className="nm-lane" style={{ ['--c' as string]: LANE_COLOR[a.arm] }} data-testid={`nm-repair-${a.arm}`}>
      <LaneTag lane={a.arm} />
      <ol className="nm-repairlog">
        {a.repair_log.map((r, i) => {
          const ck = checks[r.design]
          return (
            <li key={i} className={r.design === a.submitted.index ? 'submitted' : ''}>
              <b>{r.step === 'twin' ? `Simulator design against its belief (${explanationName(a.final_belief.structure)})` : `Optimiser on the real robot: ${r.tool.replace(/_/g, ' ')}`}</b>
              <span>{r.step === 'twin' ? `walks ${r.twin_walking}/8 in the simulator` : `${r.budget} robot trials, training ${r.train_walking}/4`}
                {ck ? ` → real-robot check ${ck[0]}/${ck[1]}` : ''}{r.design === a.submitted.index ? ' · submitted' : ''}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function Representative({ d }: { d: NemotronCaseResponse }) {
  const x = crossCheck(d.cross)
  const g = d.cross.aggregates
  const a4 = d.case.arms.A4
  return (
    <>
      <div className="nm-lanes">
        <div className="nm-lane" style={{ ['--c' as string]: LANE_COLOR.A4 }} data-testid="nm-a4">
          <LaneTag lane="A4" />
          <h3>A second Nemotron run on the same robot did not verify</h3>
          <p className="nm-p">The A4 arm (Nemotron plus memory and a learned posterior) made the same choice, <code>{d.case.fork.nemotron.experiment}</code>, measured the identical
            per-seed results ({d.case.determinism.x1_identical_A3_A4 ? 'bit-identical' : 'different'}) and reached the correct right-side belief. Its delegated repair produced a
            different simulator design, and verification gave <b>{statusInfo(a4.verification.status).label.toLowerCase()} ({a4.verification.walking}/{a4.verification.n})</b>.
            A correct diagnosis did not by itself produce a verified repair.</p>
        </div>
        <div className="nm-lane" data-testid="nm-cross">
          <h3>All {x.n} paired instances (Stage 2 transfer, development)</h3>
          <div className="nm-dotrows">
            {(['A3', 'A1e', 'A4'] as const).map((arm) => (
              <div key={arm} className="nm-dotrow" style={{ ['--c' as string]: LANE_COLOR[arm] }}>
                <span>{LANE_NAME[arm]}</span>
                <span className="nm-dots">{d.cross.rows.map((r) => <i key={r.instance_id} className={`${r[arm].full ? 'on' : ''} ${r.instance_id === d.case.instance_id ? 'this' : ''}`} title={`${shortId(r.instance_id)}: ${r[arm].status}`} />)}</span>
                <b>{arm === 'A3' ? x.a3 : arm === 'A1e' ? x.a1 : x.a4}/{x.n}</b>
              </div>
            ))}
          </div>
          <p className="nm-p">Verified recovery: Nemotron {x.a3}, engine alone {x.a1} — discordant {x.a3Only} vs {x.a1Only}, one-sided exact McNemar p = {g.mcnemar_one_sided_p_A3_gt_A1e}.
            Correct final diagnosis: {g.map_correct.A3} vs {g.map_correct.A1e}. Nemotron's first experiment differed from the engine's in {g.first_experiment_differs} of {x.n}.</p>
          <p className="nm-p"><b>This robot is the only one of {x.n}</b> where Nemotron's diagnosis was right, the engine's wrong, and only Nemotron's repair verified. The engine alone
            verified {g.A1e_full_only.length} instances Nemotron did not ({g.A1e_full_only.map(shortId).join('; ')}), and was right where Nemotron's diagnosis was wrong in{' '}
            {g.A3_map_wrong_A1e_right.length} ({g.A3_map_wrong_A1e_right.map(shortId).join('; ')}).</p>
        </div>
      </div>
    </>
  )
}

function Studies({ d }: { d: NemotronCaseResponse }) {
  return (
    <div className="nm-tablewrap">
      <table className="nm-studies" data-testid="nm-studies">
        <caption>{d.studies.note}</caption>
        <thead><tr><th>Date</th><th>Study</th><th>Registration · n</th><th>Outcome</th><th>Credited to</th></tr></thead>
        <tbody>
          {d.studies.studies.map((s) => (
            <tr key={s.id} data-testid={`nm-study-${s.id}`}>
              <td>{s.date}</td>
              <td>{s.study}<small>vs {s.comparator}</small></td>
              <td>{s.registration}<small>{s.n}</small></td>
              <td><Chip tone={studyTone(s.direction)}>{s.direction}</Chip> {s.outcome}</td>
              <td>{s.credited_to}<small title={s.quote}>source: {s.source}</small></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

type Slot = 'failure' | 'experiment' | 'verify'

/** One damaged-plant viewer at a time (the playback clock is shared): the others show a "watch" button. */
function ReplaySlot({ id, active, onWatch, status, label, children }: {
  id: Slot; active: Slot | null; onWatch: (s: Slot) => void; status: ReplayStatus; label: string; children: () => ReactNode
}) {
  if (!status.available) return <p className="nm-small" data-testid={`nm-slot-${id}-unavailable`}>No damaged-robot replay: {status.reason}</p>
  if (active !== id) {
    return <button type="button" className="nm-watch" onClick={() => onWatch(id)} data-testid={`nm-watch-${id}`}>▶ {label}</button>
  }
  return <>{children()}</>
}

function CaseView({ d }: { d: NemotronCaseResponse }) {
  const c = d.case
  const a3 = c.arms.A3, a1 = c.arms.A1e
  const turns = useMemo(() => followed(a3), [a3])
  const s3 = beliefShift(a3), s1 = beliefShift(a1)
  const hyps = a3.steps.flatMap((s) => s.result.hypotheses ?? [])
  const later = a3.steps.filter((s) => s.actor === 'nemotron' && (s.turn ?? 0) > 0)
  const x1n = a3.experiments[1], x1e = a1.experiments[1]
  const truth = explanationName(c.evaluation_only.injected_structure)
  const prior = c.shared.belief_after_observation.slice(0, 2).map((t) => ({ name: explanationName(t.structure), w: t.w }))
  const pn = c.fork.nemotron.predicted_walking, pe = c.fork.engine.predicted_walking, po = c.fork.notebook.predicted_out_of
  const check = a3.model?.calls.find((k) => k.model_check.some((l) => l.startsWith('X1:')))?.model_check ?? []
  const rule = /;\s*(.+?)\):?$/.exec(check[0] ?? '')?.[1] ?? 'n/a'
  const residual = check.find((l) => l.startsWith('X1:')) ?? 'n/a'
  const rp = d.replays
  const [active, setActive] = useState<Slot | null>(rp.available ? 'experiment' : null)
  const [obsSeed, setObsSeed] = useState(c.shared.observation.seeds[0])
  const [x1Seed, setX1Seed] = useState(x1n.seeds[0])
  const valRows = rp.validation
  const defaultVal = valRows ? illustrativeSeed(valRows.a3_submitted.rows, valRows.a1e_submitted.rows) : null
  const [valSeed, setValSeed] = useState<number | null>(defaultVal)
  const env = rp.environment
  const expNote = rp.available ? `Reconstructed MuJoCo replay (${env?.system} ${env?.machine}, MuJoCo ${env?.mujoco}) of the recorded designs on the hidden plant. `
    + `Every per-seed measurement of this experiment was reproduced exactly from the recorded run; frame error ${rp.fidelity?.fk_max_err_m} m. Playback only; nothing is simulated here.` : ''
  const valNote = rp.available ? 'Reconstructed simulation replay, not an archived original: Stage 2 stored no per-seed verification rows. This re-run reproduced the recorded '
    + "verification of both designs exactly at the level the record allows (status, walking fraction, reasons); the per-seed trajectories are this re-run's. " + (valSeed === defaultVal
      ? "Illustrative seed by a pre-declared rule (first validation seed where Nemotron's design walks and the engine's does not); the counts above are the result." : '') : ''
  const obsLane: ReplayLane[] = [{ name: 'observe', label: 'Damaged robot, nominal design', color: 'var(--bad)', outcome: (s) => outcomeOfFeatures(c.shared.observation, s) }]
  const x1Lanes: ReplayLane[] = [
    { name: 'x1_nem', label: `Nemotron's experiment ${x1n.id.replace(/^X\d+:cf:/, '')}`, color: LANE_COLOR.A3, outcome: (s) => outcomeOfFeatures(x1n, s) },
    { name: 'x1_eng', label: `Engine's experiment ${x1e.id.replace(/^X\d+:cf:/, '')}`, color: LANE_COLOR.A1e, outcome: (s) => outcomeOfFeatures(x1e, s) }]
  const valLanes: ReplayLane[] = valRows ? [
    { name: 'nominal', label: 'Faulty robot (no repair)', color: 'var(--bad)', outcome: (s) => outcomeOfRow(valRows.nominal.rows, s) },
    { name: 'a3_submitted', label: "Nemotron's lane: submitted design", color: LANE_COLOR.A3, outcome: (s) => outcomeOfRow(valRows.a3_submitted.rows, s) },
    { name: 'a1e_submitted', label: 'Engine alone: submitted design', color: LANE_COLOR.A1e, outcome: (s) => outcomeOfRow(valRows.a1e_submitted.rows, s) }] : []
  return (
    <div className="nm-case">
      <Stage n={1} title="The failure: a robot with hidden damage" testid="nm-stage-failure">
        <p className="nm-p">Robot <b>gen-0137</b>, the same base robot as the Verified repair page, with a different hidden fault. Every arm sees only the nominal design and its own
          measurements. On four trials of its normal gait the real robot stays upright but barely moves. It fails the eligibility check on {c.eligibility_check.n - c.eligibility_check.walking} of {c.eligibility_check.n} starts.</p>
        <SeedTiles e={c.shared.observation} testid="nm-observe" />
        <p className="nm-small">Measured during the recorded run by MuJoCo on the hidden plant ({c.shared.identical_in_all_arms ? 'identical in all three arms' : 'arms differ'}). The plant numbers are recorded; no simulation runs on this page.</p>
        <ReplaySlot id="failure" active={active} onWatch={setActive} status={rp} label="Watch the damaged robot">
          {() => <PlantReplay lanes={obsLane} seeds={c.shared.observation.seeds} seed={obsSeed} onSeed={setObsSeed} note={expNote} testid="nm-replay-failure" />}
        </ReplaySlot>
      </Stage>

      <Stage n={2} title="Hypotheses: which side is weak?" testid="nm-stage-hypotheses">
        <p className="nm-p">The Bayesian belief engine simulates candidate explanations against the measurements. Two survive: a weak right side or a weak left side.</p>
        <Bars rows={prior} testid="nm-prior" />
        <Words who="Nemotron, turn 0 (recorded, verbatim)"><p>{c.fork.nemotron.words.uncertainty}</p></Words>
      </Stage>

      <Stage n={3} title="Nemotron's experiment: the decision that differs" testid="nm-stage-fork"><Fork c={c} /></Stage>

      <Stage n={4} title="Deterministic measurements on the damaged robot" testid="nm-stage-measure">
        <div className="nm-lanes">
          <div className="nm-lane" style={{ ['--c' as string]: LANE_COLOR.A3 }}><LaneTag lane="A3" /><SeedTiles e={x1n} testid="nm-x1-A3" />
            <p className="nm-small">Predicted in the notebook: walks {pn?.[0]}/{po} if the right side is weak, {pn?.[1]}/{po} if the left. Observed {walkingOf(x1n)}/{x1n.per_seed.length}.</p></div>
          <div className="nm-lane" style={{ ['--c' as string]: LANE_COLOR.A1e }}><LaneTag lane="A1e" /><SeedTiles e={x1e} testid="nm-x1-A1e" />
            <p className="nm-small">Predicted: walks {pe?.[0]}/{po} if the right side is weak, {pe?.[1]}/{po} if the left. Observed {walkingOf(x1e)}/{x1e.per_seed.length}.</p></div>
        </div>
        <ReplaySlot id="experiment" active={active} onWatch={setActive} status={rp} label="Watch both experiments on the damaged robot">
          {() => <PlantReplay lanes={x1Lanes} seeds={x1n.seeds} seed={x1Seed} onSeed={setX1Seed} note={expNote} testid="nm-replay-experiment" />}
        </ReplaySlot>
      </Stage>

      <Stage n={5} title="Updated belief" testid="nm-stage-belief">
        <div className="nm-lanes">
          <div className="nm-lane" style={{ ['--c' as string]: LANE_COLOR.A3 }}><LaneTag lane="A3" /><p className="nm-small">after {x1n.id.replace(/^X\d+:/, '')}</p><Bars rows={s3.after} testid="nm-after-A3" /></div>
          <div className="nm-lane" style={{ ['--c' as string]: LANE_COLOR.A1e }}><LaneTag lane="A1e" /><p className="nm-small">after {x1e.id.replace(/^X\d+:/, '')}</p><Bars rows={s1.after} testid="nm-after-A1e" /></div>
        </div>
        <p className="nm-p">The same engine, updating on its own measurements, becomes near-certain in both lanes — on opposite sides. Final belief: Nemotron's lane{' '}
          <b>{explanationName(a3.final_belief.structure)} ({fmtW(a3.final_belief.mass)})</b>; engine alone <b>{explanationName(a1.final_belief.structure)} ({fmtW(a1.final_belief.mass)})</b>.</p>
        <details className="nm-eval" data-testid="nm-truth"><summary>Hidden truth (evaluation only — no arm saw it)</summary>
          <p>{c.evaluation_only.note} Injected: <b>{truth}</b> ({c.evaluation_only.family.replace(/_/g, ' ')}, severity {c.evaluation_only.severity}, {c.evaluation_only.mult}× its failure threshold).
            Nemotron's lane put {fmtW(a3.final_belief.mass_on_truth)} on the truth; the engine alone {fmtW(a1.final_belief.mass_on_truth)}.</p></details>
      </Stage>

      <Stage n={6} title="Repair: delegated to the engine's optimiser" testid="nm-stage-repair">
        <p className="nm-p">After the experiment Nemotron took three more decisions. The engine's own recommendation each time is from the recorded prompt.</p>
        <ul className="nm-turns">
          {later.map((s) => {
            const t = turns.find((x) => x.turn === s.turn)
            return (
              <li key={s.seq}><b>Turn {s.turn}: {s.action.action.replace(/_/g, ' ')}</b>{' '}
                <span className="nm-small">(engine recommended: {t?.recommended ?? 'n/a'}{t?.same ? ', followed' : ''})</span>
                {s.action.action === 'propose' && <span className="nm-small"> — {hyps.length} hypotheses: {hyps.map((h) => `${hypothesisName(h.fitted ?? h.pid)} → ${h.status ?? `rank ${h.rank}`}, weight ${h.weight.toFixed(3)}`).join('; ')}</span>}
              </li>
            )
          })}
        </ul>
        <p className="nm-flag nm-flag-warn" data-testid="nm-hyp-note">Nemotron's extra hypotheses added {hyps.every((h) => h.weight === 0) ? 'no weight' : 'weight'} to the belief
          ({hyps.map((h) => h.weight.toFixed(3)).join(', ')}). It called the residual "<code>{residual}</code>" systematic; the notebook's rule is "{rule}".
          The repair below was run by the engine; Nemotron only chose to delegate it.</p>
        <div className="nm-lanes"><RepairLane a={a3} /><RepairLane a={a1} /></div>
        <p className="nm-small">The simulator designs differ because each lane optimises against its own belief: real-robot check of the simulator design {twinCheck(a3)} in Nemotron's
          lane, {twinCheck(a1)} in the engine's. The engine then submits the design with the best real-robot check.</p>
      </Stage>

      <Stage n={7} title="Independent verification (hidden starts the agents never saw)" testid="nm-stage-verify">
        <div className="nm-lanes"><Verification a={a3} testid="nm-verify-A3" /><Verification a={a1} testid="nm-verify-A1e" /></div>
        <p className="nm-small">Rule <code>full_recovery_v1</code>: at least 80% of the {a3.verification.n} validation starts walk, a verified gain over the faulty robot, then a 20 s confirmation.</p>
        <ReplaySlot id="verify" active={active} onWatch={setActive} status={rp} label="Watch the faulty robot and both repairs on the hidden starts">
          {() => valSeed == null ? null : <PlantReplay lanes={valLanes} seeds={valRows?.a3_submitted.rows.map((r) => r.seed) ?? []} seed={valSeed} onSeed={setValSeed} note={valNote} testid="nm-replay-verify" />}
        </ReplaySlot>
      </Stage>

      <Stage n={8} title="How representative is this?" testid="nm-stage-scope"><Representative d={d} /></Stage>

      <Stage n={9} title="Nemotron's role across every study" testid="nm-stage-studies">
        <p className="nm-p">Favourable, mixed and negative results, in date order. The DO-1 recovery on the Verified repair page is listed as what it is: deterministic, NO_AI.</p>
        <Studies d={d} />
      </Stage>

      <section className="nm-replays" data-testid="nm-replays">
        <h2>About the damaged-robot replays</h2>
        {rp.available ? <>
          <p className="nm-p" data-testid="nm-replay-fidelity">Exported by <code>{rp.exporter}</code> in the recorded environment ({env?.system} {env?.machine}, Python {env?.python},
            numpy {env?.numpy}, MuJoCo {env?.mujoco}) from the recorded designs on the hidden plant. Experiments: {rp.fidelity?.experiments}. Verification: {rp.fidelity?.validation}.
            Frames are the {rp.frame_state} simulation state; forward-kinematics error {rp.fidelity?.fk_max_err_m} m (tolerance {rp.fidelity?.fk_tol_m}).</p>
          <p className="nm-small">These are reconstructions of the recorded runs, not frames archived at the time. The model is not called again: Nemotron's decisions are the recorded ones.</p>
        </> : <p className="nm-p">{rp.reason}</p>}
        <p className="nm-small">The "AI scientist" tab's animations show designs on the <b>nominal</b> robot, without this hidden damage, and are labelled so.</p>
      </section>

      <footer className="nm-prov" data-testid="nm-prov">
        <p>Playback of recorded runs. Model {a3.model?.name}; {a3.costs.llm_calls} calls, {fmtUsd(a3.costs.cost_usd)} in the A3 episode; request ids found in the inference ledger:{' '}
          {d.cross.ledger.this_case.A3.filter((x) => x.in_ledger === 1).length}/{d.cross.ledger.this_case.A3.length} (<code>{d.cross.ledger.file}</code>).</p>
        {c.sources.map((s) => <p key={s.arm}>{s.arm}: <code>{s.source}</code> line {s.source_line} · file sha256 <code>{s.source_sha256.slice(0, 12)}…</code> · line sha256 <code>{s.line_sha256.slice(0, 12)}…</code></p>)}
      </footer>
    </div>
  )
}

/** Who decides and which deterministic instrument does what in the recorded investigation (has_agent.py and its tools). */
function Laboratory({ d }: { d: NemotronCaseResponse }) {
  const a3 = d.case.arms.A3
  return (
    <section className="nm-lab" data-testid="nm-lab" aria-label="How the laboratory works">
      <div className="nm-lab-node nm-lab-model">
        <b>Nemotron</b>
        <span>{a3.model?.name} on Nebius Token Factory · {a3.costs.llm_calls} recorded calls in this run</span>
        <small>Reads the lab notebook; picks the next action: an experiment, new hypotheses, a tool screen, delegate the repair, stop.</small>
      </div>
      <span className="nm-lab-arrow" aria-hidden="true">→</span>
      <div className="nm-lab-tools">
        <div className="nm-lab-node"><b>MuJoCo experiments</b><small>run on the damaged robot (the hidden plant)</small></div>
        <div className="nm-lab-node"><b>Bayesian belief engine</b><small>simulates each hypothesis, weighs it against the measurements, scores experiments by EIG</small></div>
        <div className="nm-lab-node"><b>CMA-ES optimiser</b><small>repairs in the simulator twin and on the robot</small></div>
        <div className="nm-lab-node"><b>Memory</b><small>dossiers from earlier cases (A4 arm only)</small></div>
      </div>
      <span className="nm-lab-arrow" aria-hidden="true">→</span>
      <div className="nm-lab-node nm-lab-verify">
        <b>Independent verifier</b>
        <span><code>full_recovery_v1</code> on hidden starts</span>
        <small>The agent never sees these trials. It decides FULL / PARTIAL / NOT.</small>
      </div>
      <p className="nm-small nm-lab-note">Deterministic code does the inference, the optimisation and the judging; Nemotron decides what to do with them. Simulation and the export ran on a
        Nebius AI Cloud VM. The engine-alone arm (A1e) runs the same laboratory with the engine's own recommendation at every step.</p>
    </section>
  )
}

/** W2: Nemotron's recorded investigation of gen-0137 one_side_weakness, against the engine alone on the same evidence. Read-only playback. */
export function NemotronCase() {
  const [d, setD] = useState<NemotronCaseResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { getNemotronCase().then(setD).catch((e: Error) => setError(e.message)) }, [])
  if (error) return <main><div className="state error" role="alert" data-testid="nm-error"><b>The recorded case could not be loaded</b><span>{error}</span></div></main>
  if (!d) return <main><div className="skeleton" style={{ height: 420 }} aria-label="Loading" /></main>
  return (
    <main className="nm" data-testid="nemotron-case">
      <section className="nm-hero">
        <div>
          <p className="nm-kicker">Recorded live · playback, no model call</p>
          <h2>Same robot, same evidence — one decision apart</h2>
          <p className="nm-lede">Nemotron and the deterministic belief engine start from identical measurements and an identical belief. They differ in one choice: which
            experiment to run. Follow both from the failure to independent verification.</p>
        </div>
        <ul className="nm-flags">
          <li className="nm-flag nm-flag-live" data-testid="nm-flag-playback">{d.case.captions.playback}</li>
          <li className="nm-flag nm-flag-scope" data-testid="nm-flag-scope">{d.case.captions.scope}</li>
          <li className="nm-flag nm-flag-attr" data-testid="nm-flag-repair">{d.case.captions.repair}</li>
          <li className="nm-flag nm-flag-attr" data-testid="nm-flag-do1">{d.case.captions.do1}</li>
        </ul>
      </section>
      <Laboratory d={d} />
      <CaseView d={d} />
    </main>
  )
}
