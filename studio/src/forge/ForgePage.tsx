import { useCallback, useEffect, useState } from 'react'
import { getCreature, getForgeStatus, listCreatures, setCurrentVersion, startChallenge } from '../api'
import { ChallengePicker } from './ChallengePicker'
import { CreatureBar } from './CreatureBar'
import { DEFAULT_TARGET_FORCE, forgeUrl, parseForgeLink } from './forgeLogic'
import type { ChallengeRun, Creature, ForgeStatus, Kind } from './forgeTypes'
import { InvestigationView } from './InvestigationView'
import { RunView } from './RunView'
import './forge.css'

const LAST_KEY = 'cf.forge.creature'
const remember = (cid: string) => { try { localStorage.setItem(LAST_KEY, cid) } catch { /* storage may be blocked */ } }
const recall = (): string | null => { try { return localStorage.getItem(LAST_KEY) } catch { return null } }

/** The live workspace for the creature you drew: challenge it in MuJoCo, investigate, accept, repeat. */
export function ForgePage({ target, go }: { target: { cid: string; n: number | null } | null; go: (t: 'sketch') => void }) {
  const link = parseForgeLink(window.location.search)
  const [cid, setCid] = useState<string | null>(target?.cid ?? link.creature ?? null)
  const [creature, setCreature] = useState<Creature | null>(null)
  const [viewN, setViewN] = useState<number | null>(target?.n ?? link.v ?? null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [empty, setEmpty] = useState(false)
  const [status, setStatus] = useState<ForgeStatus | null>(null)
  const [kind, setKind] = useState<Kind>('push')
  const [targetForce, setTargetForce] = useState(DEFAULT_TARGET_FORCE)
  const [seeds, setSeeds] = useState(8)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(link.run)
  const [run, setRun] = useState<ChallengeRun | null>(null)
  const [barBusy, setBarBusy] = useState(false)
  const [barError, setBarError] = useState<string | null>(null)

  useEffect(() => { getForgeStatus().then(setStatus).catch(() => undefined) }, [])

  // resolve which creature to show: explicit link, then the last one used, then the newest one
  useEffect(() => {
    if (target?.cid && target.cid !== cid) { setCid(target.cid); setViewN(target.n); setJobId(null); setRunId(null) }
  }, [target]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (cid) return
    let alive = true
    const last = recall()
    if (last) { setCid(last); return }
    listCreatures().then((l) => { if (!alive) return; if (l.length) setCid(l[0].id); else setEmpty(true) }).catch((e: Error) => alive && setLoadError(e.message))
    return () => { alive = false }
  }, [cid])
  useEffect(() => {
    if (!cid) return
    let alive = true
    setLoadError(null)
    getCreature(cid)
      .then((c) => { if (!alive) return; setCreature(c); remember(c.id); setViewN((n) => (n && c.versions.some((v) => v.n === n) ? n : c.current)) })
      .catch((e: Error) => { if (alive) { setLoadError(e.message); setCreature(null) } })
    return () => { alive = false }
  }, [cid])

  useEffect(() => {
    if (cid && viewN) history.replaceState(null, '', forgeUrl(cid, viewN, runId))
  }, [cid, viewN, runId])

  const onRun = useCallback((r: ChallengeRun | null) => setRun(r), [])

  if (empty) {
    return (
      <main className="fg-page">
        <div className="fg-empty" data-testid="forge-empty"><b>No creature on the bench yet</b>
          <span>Draw one, then press "Use this creature" to bring it here.</span>
          <button className="btn btn-create" onClick={() => go('sketch')}>Draw a creature</button></div>
      </main>
    )
  }
  const version = creature && viewN ? creature.versions.find((v) => v.n === viewN) ?? null : null

  const run_ = async () => {
    if (!creature || !version) return
    setStarting(true)
    setStartError(null)
    try {
      const r = await startChallenge(creature.id, version.n, { kind, seeds, overrides: kind === 'push' ? { target_force: targetForce } : undefined })
      setJobId(r.job_id)
      setRunId(r.run_id)
    } catch (e) {
      setStartError((e as Error).message)
    } finally {
      setStarting(false)
    }
  }
  const selectVersion = (n: number) => { setViewN(n); setJobId(null); setRunId(null); setRun(null) }
  const makeCurrent = async (n: number) => {
    if (!creature) return
    setBarBusy(true)
    setBarError(null)
    try { const c = await setCurrentVersion(creature.id, n); setCreature(c); selectVersion(n) } catch (e) { setBarError((e as Error).message) } finally { setBarBusy(false) }
  }
  const accepted = (c: Creature) => {
    if (c && Array.isArray(c.versions)) { setCreature(c); selectVersion(c.current) } else if (cid) void getCreature(cid).then((x) => { setCreature(x); selectVersion(x.current) })
  }

  return (
    <main className="fg-page" data-testid="forge-page">
      <div className="fg-banner" data-testid="forge-banner">
        <span className="fg-live"><i />YOUR CREATURE · LIVE MuJoCo</span>
        <span className="fg-dim">Every result here is a fresh simulation of the creature you drew. Archived experiments and the recorded AI demo live under Investigate.</span>
      </div>
      {loadError && <div className="error" role="alert" data-testid="forge-load-error">Could not load the creature: {loadError}</div>}
      {!creature && !loadError && cid && <div className="fg-skeleton skeleton" />}
      {creature && version && (
        <div className="fg-grid">
          <div className="fg-side">
            <CreatureBar creature={creature} viewN={version.n} onView={selectVersion} onMakeCurrent={(n) => void makeCurrent(n)} busy={barBusy} error={barError} />
            <ChallengePicker kind={kind} onKind={setKind} targetForce={targetForce} onTargetForce={setTargetForce} seeds={seeds} onSeeds={setSeeds}
              onRun={() => void run_()} busy={starting} lastRun={run} versionLabel={`v${version.n}`} />
            {startError && <div className="error" role="alert" data-testid="start-error">Could not start the challenge: {startError}</div>}
          </div>
          <div className="fg-main">
            <RunView jobId={jobId} runId={runId} onRun={onRun} />
            {run && <InvestigationView cid={creature.id} version={version} run={run} status={status} onAccepted={accepted} />}
          </div>
        </div>
      )}
    </main>
  )
}
