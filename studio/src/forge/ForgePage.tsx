import { useCallback, useEffect, useState } from 'react'
import { getCreature, getForgeStatus, listCreatures, setCurrentVersion, startChallenge } from '../api'
import { ChallengePicker } from './ChallengePicker'
import { CreatureBar } from './CreatureBar'
import { DEFAULT_TARGET_FORCE, forgeUrl, parseForgeLink } from './forgeLogic'
import type { ChallengeRun, Creature, ForgeStatus, Kind } from './forgeTypes'
import { InvestigationList, InvestigationView } from './InvestigationView'
import { RecoveryList, RecoveryPanel } from './RecoveryView'
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
  const [openInv, setOpenInv] = useState<string | null>(null)
  const [invNonce, setInvNonce] = useState(0)
  const [acceptedN, setAcceptedN] = useState<number | null>(null)
  const [openRec, setOpenRec] = useState<string | null>(null)
  const [recNonce, setRecNonce] = useState(0)

  useEffect(() => { getForgeStatus().then(setStatus).catch(() => undefined) }, [])

  // resolve which creature to show: explicit link, then the last one used, then the newest one
  useEffect(() => {
    if (target?.cid && target.cid !== cid) { setCid(target.cid); setViewN(target.n); setJobId(null); setRunId(null); setOpenRec(null) }
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
  /** "Run walk challenge on v(n+1)" after a recovery was accepted: a walk challenge of that version, same seed count. */
  const runWalkOn = async (n: number) => {
    if (!creature) return
    setKind('walk')
    setStarting(true)
    setStartError(null)
    try {
      const r = await startChallenge(creature.id, n, { kind: 'walk', seeds })
      setViewN(n)
      setJobId(r.job_id)
      setRunId(r.run_id)
      setRun(null)
    } catch (e) {
      setStartError((e as Error).message)
    } finally {
      setStarting(false)
    }
  }
  const selectVersion = (n: number) => { setViewN(n); setJobId(null); setRunId(null); setRun(null); setAcceptedN(null) }
  const makeCurrent = async (n: number) => {
    if (!creature) return
    setBarBusy(true)
    setBarError(null)
    try { const c = await setCurrentVersion(creature.id, n); setCreature(c); selectVersion(n) } catch (e) { setBarError((e as Error).message) } finally { setBarBusy(false) }
  }
  const accepted = (c: Creature) => {
    const done = (x: Creature) => { setCreature(x); selectVersion(x.current); setAcceptedN(x.current); setInvNonce((k) => k + 1) }
    if (c && Array.isArray(c.versions)) done(c)
    else if (cid) void getCreature(cid).then(done)
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
            <InvestigationList cid={creature.id} nonce={invNonce} openId={openInv} onOpen={setOpenInv} />
            <RecoveryList cid={creature.id} nonce={recNonce} openId={openRec} onOpen={setOpenRec} />
          </div>
          <div className="fg-main">
            {acceptedN !== null && acceptedN === version.n && (
              <div className="fg-note-box fg-accepted" role="status" data-testid="accepted-banner">
                <b>Accepted as v{acceptedN}.</b> Your creature changed; the version history above records what changed and why.
                <button className="btn btn-simulate fg-small" data-testid="challenge-new-version" onClick={() => void run_()}>Challenge v{acceptedN}</button>
              </div>
            )}
            <RunView jobId={jobId} runId={runId} onRun={onRun} />
            <RecoveryPanel cid={creature.id} version={version} versions={creature.versions} run={run} status={status} openId={openRec} onOpenId={setOpenRec}
              onChanged={() => setRecNonce((k) => k + 1)} onAccepted={accepted} onRunWalk={(n) => void runWalkOn(n)} />
            <InvestigationView cid={creature.id} version={version} versions={creature.versions} run={run} status={status} openId={openInv} onOpenId={setOpenInv}
              onChanged={() => setInvNonce((k) => k + 1)} onAccepted={accepted} />
          </div>
        </div>
      )}
    </main>
  )
}
