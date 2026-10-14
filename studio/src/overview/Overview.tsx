import { useEffect, useState } from 'react'
import { getOverview } from '../api'
import { Notice } from '../lab/Badges'
import type { OverviewData } from './overviewTypes'
import { pct, proposalLine } from './overviewLogic'

export function Overview({ go }: { go: (tab: 'demo' | 'locomotion' | 'compare' | 'studio') => void }) {
  const [data, setData] = useState<OverviewData | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { getOverview().then(setData).catch((e: Error) => setError(e.message)) }, [])
  if (error) return <main><Notice tone="bad" testid="overview-error">Could not load the overview: {error}</Notice></main>
  if (!data) return <main><Notice>Loading the project overview…</Notice></main>
  const c = data.classical
  const n = data.nemotron
  return (
    <main className="overview" data-testid="overview">
      <section className="hero">
        <h2>{data.headline}</h2>
        <p>
          Creature Forge turns a physical failure in MuJoCo into evidence, lets NVIDIA Nemotron propose bounded fixes, and lets the simulator decide.
          Two separate lines of evidence are shown below; they are not mixed.
        </p>
        <div className="hero-cta">
          <button className="cta" data-testid="cta-demo" onClick={() => go('demo')}>▶ Watch a real, recorded AI investigation</button>
          <small className="dim">Failure → evidence → Nemotron’s proposal → the parameters it changes → MuJoCo’s verdict → side-by-side replay. No API key needed.</small>
        </div>
      </section>

      <ol className="pipeline" aria-label="how Creature Forge works" data-testid="pipeline">
        {data.pipeline.map((p, i) => (
          <li key={p.step}><span className="n">{i + 1}</span><b>{p.step}</b><small>{p.text}</small></li>
        ))}
      </ol>

      <div className="cards">
        <section className="card card-classical" data-testid="card-classical">
          <header><h3>Classical optimisation: statistically confirmed</h3><span className="tag tag-classical">no language model</span></header>
          {c ? (
            <>
              <p className="big">{c.winner_walking}/{c.n} <small>walk</small> vs {c.incumbent_walking}/{c.n} <small>for the starting controller</small></p>
              <ul>
                <li>150 untouched seeds; paired outcomes: {c.paired.winner_only} seeds only the new controller walks, {c.paired.incumbent_only} only the old one.</li>
                <li>Non-inferiority (margin 5 points): {c.non_inferior ? 'confirmed' : 'not confirmed'}; superiority (exact McNemar p = {c.mcnemar_p?.toExponential(1)}): {c.superior ? 'confirmed' : 'not confirmed'}.</li>
                <li>Exact 95% interval for the new controller: {pct(c.winner_exact_ci[0])}–{pct(c.winner_exact_ci[1])}, not “100%”.</li>
              </ul>
              <p className="attrib">{c.attribution}</p>
            </>
          ) : <p className="dim">Result files not found.</p>}
          <footer><button onClick={() => go('locomotion')}>Open the locomotion replays</button></footer>
        </section>

        <section className="card card-nemotron" data-testid="card-nemotron">
          <header><h3>Nemotron investigation: real, verified, not a superiority claim</h3><span className="tag tag-model">NVIDIA Nemotron via Nebius</span></header>
          <p>{n.claim}</p>
          <ul>
            {n.recorded_runs.filter((r) => r.kind === 'RECORDED_LIVE').map((r) => (
              <li key={r.id}>
                <b>{r.label}</b>
                {r.proposals.length === 0 ? <> — reply rejected by validation; nothing was simulated.</> : (
                  <ul>{r.proposals.map((p, i) => <li key={i}>{proposalLine(p, r.frozen_walking ?? 0, r.n ?? 32)}</li>)}</ul>
                )}
              </li>
            ))}
          </ul>
          <Notice tone="warn" testid="r3-status">
            <b>Systematic comparison: {n.systematic_comparison.status}.</b> {n.systematic_comparison.reason}
          </Notice>
          <small className="dim">Shared Nebius budget used: {n.usage.requests}/{n.usage.requests_cap} requests · {n.usage.tokens.toLocaleString()}/{n.usage.tokens_cap.toLocaleString()} tokens.</small>
          <footer><button onClick={() => go('demo')}>Open the AI Investigation demo</button></footer>
        </section>
      </div>

      <section className="earlier">
        <h3>How we got here</h3>
        <ul>
          {data.earlier.phase2a && <li>{data.earlier.phase2a.text}</li>}
          {data.earlier.r1 && <li>{data.earlier.r1.text}</li>}
          <li>Local optimisation around the working controller (the classical result above) succeeded where the global search did not.</li>
        </ul>
      </section>

      <section className="limits-box" data-testid="limits">
        <h3>What this does not show</h3>
        <ul>{data.limits.map((l) => <li key={l}>{l}</li>)}</ul>
        <small>Every number on this page is read from the committed experiment records. Provenance labels in the demo: LIVE (real call made now), RECORDED LIVE (stored real call), SCRIPTED MOCK (not a model).</small>
      </section>
    </main>
  )
}
