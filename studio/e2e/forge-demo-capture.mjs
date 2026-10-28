// DEMO CAPTURE of the real Forge Loop, for the submission video (raw footage; the owner edits and adds the voice-over).
// One continuous take at 1920x1080 driven at a human pace: draw a creature -> Push challenge in MuJoCo -> replay of the
// failure -> "Investigate with AI" (probes on) -> probes, model call, proposal, held-out verdict beside the matched twin ->
// accept as v2 ONLY if MuJoCo verified it -> challenge v2. Nothing is staged: every result on screen comes from the server.
// MODE=live (default) makes REAL Nemotron calls (~2-3 calls, ~$0.005) and requires LIVE_OK=1 and a live server.
// MODE=scripted is a pacing/frame-rate dry run with the labelled SCRIPTED MOCK fixture (never footage of a model).
// The only thing the script adds to the picture is a cursor dot (headless Chrome draws no cursor); the manifest says so.
// Output (OUT_DIR): frames/ (JPEG, CDP screencast), take.mp4 (if FFMPEG is set), stills/*.png, manifest.json.
// KIND=push|walk picks the challenge on screen; TARGET_FORCE (push only) is typed into the target box as the user's requirement.
// Usage: LIVE_OK=1 BASE_URL=http://127.0.0.1:8000 OUT_DIR=... ATTEMPT=1 [KIND=push] [TARGET_FORCE=15] [FFMPEG=...] node e2e/forge-demo-capture.mjs
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync, writeFileSync, readdirSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

const MODE = process.env.MODE || 'live'
if (MODE === 'live' && process.env.LIVE_OK !== '1') { console.log('SKIP set LIVE_OK=1 for a live capture (real model calls)'); process.exit(0) }
const BASE = process.env.BASE_URL
const OUT = process.env.OUT_DIR
if (!BASE || !OUT) throw new Error('BASE_URL and OUT_DIR are required')
for (const d of ['frames', 'stills']) mkdirSync(`${OUT}/${d}`, { recursive: true })
const exe = [process.env.BROWSER_PATH, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable'].filter(Boolean).find((p) => existsSync(p))
if (!exe) throw new Error('no Chrome found; set BROWSER_PATH')

const T = (id) => `[data-testid="${id}"]`
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const t0 = Date.now()
const now = () => +((Date.now() - t0) / 1000).toFixed(2)
const manifest = { kind: 'forge-demo-capture', mode: MODE, attempt: process.env.ATTEMPT || null, base: BASE, started_utc: new Date().toISOString(),
  overlay: 'cursor dot drawn by the capture script (headless Chrome renders no cursor); nothing else is added to the page',
  chapters: [], checks: [], errors: [] }
const chapter = (name, extra = {}) => { const c = { t: now(), name, ...extra }; manifest.chapters.push(c); console.log(`[${c.t}s] ${name}`, Object.keys(extra).length ? JSON.stringify(extra) : '') }
const check = (c, m) => { manifest.checks.push({ ok: !!c, m }); console.log(`${c ? 'PASS' : 'FAIL'} ${m}`) }

const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox', '--hide-scrollbars'] })
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, colorScheme: 'dark' })
await ctx.addInitScript(() => {
  window.addEventListener('DOMContentLoaded', () => {
    const d = document.createElement('div')
    d.id = '__capture_cursor'
    d.style.cssText = 'position:fixed;left:-50px;top:-50px;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;background:rgba(255,255,255,.9);box-shadow:0 0 0 2px rgba(0,0,0,.55),0 2px 8px rgba(0,0,0,.5);pointer-events:none;z-index:2147483647;transition:transform .12s'
    document.body.appendChild(d)
    addEventListener('mousemove', (e) => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px' }, true)
    addEventListener('mousedown', () => { d.style.transform = 'scale(.7)' }, true)
    addEventListener('mouseup', () => { d.style.transform = 'scale(1)' }, true)
  })
})
const page = await ctx.newPage()
page.setDefaultTimeout(60000)
page.on('pageerror', (e) => manifest.errors.push(`pageerror ${e.message}`))
page.on('console', (m) => { if (m.type() === 'error') manifest.errors.push(`console ${m.text()}`) })

// --- recording: CDP screencast frames with wall-clock timestamps (assembled to constant 30 fps afterwards)
const cdp = await ctx.newCDPSession(page)
const frames = []
cdp.on('Page.screencastFrame', async (f) => {
  const i = frames.length
  frames.push(f.metadata.timestamp)
  writeFileSync(`${OUT}/frames/${String(i).padStart(6, '0')}.jpg`, Buffer.from(f.data, 'base64'))
  await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {})
})
const startRec = () => cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 })

// --- human-paced input
let mouse = [960, 540]
async function glide(x, y, ms = 600) {
  const steps = Math.max(8, Math.round(ms / 16))
  const [x0, y0] = mouse
  for (let i = 1; i <= steps; i++) {
    const k = i / steps, e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2
    await page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
    await sleep(ms / steps)
  }
  mouse = [x, y]
}
async function show(sel, pause = 1200) {
  const el = page.locator(sel).first()
  await el.evaluate((n) => n.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  await sleep(900)
  const b = await el.boundingBox()
  if (b) await glide(b.x + Math.min(b.width / 2, 260), b.y + Math.min(b.height / 2, 40), 500)
  await sleep(pause)
}
async function click(sel, pause = 700) {
  await show(sel, 300)
  const b = await page.locator(sel).first().boundingBox()
  if (!b) throw new Error(`not clickable: ${sel}`)
  await glide(b.x + b.width / 2, b.y + b.height / 2, 250)
  await page.mouse.down(); await sleep(90); await page.mouse.up()
  await sleep(pause)
}
async function still(name) { await page.screenshot({ path: `${OUT}/stills/${String(manifest.chapters.length).padStart(2, '0')}-${name}.png` }) }
const text = async (sel) => ((await page.textContent(sel).catch(() => '')) || '').replace(/\s+/g, ' ').trim()
const vis = (sel) => page.isVisible(sel).catch(() => false)

// The drawing: a biped with a short foot (the stubby figure used by the live end-to-end test). Coordinates in canvas units.
const G = 620
// FIGURE (JSON, canvas units {torso, leg, foot} polylines) replaces the default stubby drawing; it is stored in the manifest.
const figure = process.env.FIGURE ? JSON.parse(process.env.FIGURE)
  : { torso: [[480, G - 376], [520, G - 376], [520, G - 256], [480, G - 256], [480, G - 376]], leg: [[500, G - 256], [500, G - 136], [500, G - 16]], foot: [[490, G - 16], [564, G - 16]] }
manifest.figure = figure
const STOP_AFTER = process.env.STOP_AFTER || ''   // 'challenge': screening take, ends after the v1 result and replay (no model call)
const runIds = []
page.on('response', (r) => { const m = r.url().match(/\/api\/forge\/runs\/(r-[0-9a-f]+)/); if (m && !runIds.includes(m[1])) runIds.push(m[1]) })
async function runDetails() {
  const id = runIds[runIds.length - 1]
  const run = id ? await (await fetch(`${BASE}/api/forge/runs/${id}`)).json().catch(() => null) : null
  return { run_id: id ?? null, outcome_overall: run?.outcome ?? null, spec: run?.spec ?? null,
    per_seed: (run?.per_seed || []).map((s) => ({ seed: s.seed, outcome: s.outcome, score: s.score, error: s.error ?? null, events: (s.events || []).map((e) => e.kind ?? e) })) }
}
async function drawStroke(pts) {
  const b = await page.locator(T('draw-canvas')).boundingBox()
  const cs = pts.map(([x, y]) => [b.x + (x / 1000) * b.width, b.y + (y / 700) * b.height])
  await glide(...cs[0], 500)
  await page.mouse.down()
  for (let i = 1; i < cs.length; i++) {
    const [xa, ya] = cs[i - 1], [xb, yb] = cs[i], n = 22
    for (let j = 1; j <= n; j++) { await page.mouse.move(xa + (xb - xa) * j / n, ya + (yb - ya) * j / n); await sleep(14) }
  }
  await page.mouse.up(); mouse = cs[cs.length - 1]
  await sleep(450)
}
async function playReplayFromStart(scope, seconds) {
  const restart = page.locator(`${scope} button:has-text("Restart")`).first()
  if (await restart.isVisible().catch(() => false)) { await click(`${scope} button:has-text("Restart")`, 200) }
  await page.locator(`${scope} canvas`).first().evaluate((n) => n.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => {})
  await sleep(seconds * 1000)
}
const runOutcome = async () => (await page.getAttribute(T('run-result'), 'data-outcome').catch(() => null)) ?? (await page.getAttribute(T('run-outcome'), 'data-outcome').catch(() => null))
const TARGET = process.env.TARGET_FORCE || ''
const KIND = process.env.KIND || 'push'   // push (default) or walk: the challenge the user picks on screen

let exitCode = 0
try {
  const status = await (await fetch(`${BASE}/api/forge/status`)).json()
  const version = await (await fetch(`${BASE}/api/version`)).json().catch(() => ({}))
  manifest.server = { live_available: status.live_available, model: status.model?.model ?? null, settings: status.model ?? null, version }
  manifest.ledger_before = status.ledger ?? null
  if (MODE === 'live') check(status.live_available === true, `server live mode on (model ${status.model?.model})`)

  await page.goto(`${BASE}/?tab=sketch`)
  await page.waitForSelector(T('sketch-page'))
  await sleep(1500)
  await startRec()
  chapter('sketch: empty canvas')
  await sleep(2500)
  await click(T('pen-torso')); await drawStroke(figure.torso)
  await click(T('pen-leg')); await drawStroke(figure.leg)
  await click(T('pen-foot')); await drawStroke(figure.foot)
  await page.waitForFunction(() => document.querySelector('[data-testid="outcome"]')?.getAttribute('data-outcome')?.startsWith('valid'), null, { timeout: 30000 })
  chapter('sketch: drawing interpreted as a valid creature')
  await show(T('sketch-preview'), 2500); await still('drawing')
  await click(T('use-creature-btn'))
  await page.waitForSelector(T('creature-bar'), { timeout: 30000 })
  manifest.creature_url = page.url()
  chapter('creature on the bench as v1', { version: await text(T('version-chip')) })
  await sleep(2500)

  await click(T(`kind-${KIND}`), 1200)
  if (await vis(T('kind-explain'))) await show(T('kind-explain'), 2000)
  if (TARGET && KIND === 'push') {   // the user's own requirement, typed on screen: the creature must withstand TARGET newtons
    await click(T('target-force'), 300)
    await page.keyboard.press('Control+A'); await sleep(250)
    for (const ch of TARGET) { await page.keyboard.type(ch); await sleep(220) }
    chapter('target force set by the user', { target_force_n: Number(TARGET) }); await sleep(1500)
  }
  manifest.kind = KIND
  if (KIND === 'push') manifest.target_force_n = Number(await page.inputValue(T('target-force')).catch(() => 'NaN'))
  await click(T('run-challenge'))
  chapter(`${KIND} challenge started (MuJoCo)`)
  await page.waitForSelector(`${T('run-result')}, ${T('run-failed')}`, { timeout: 420000 })
  manifest.v1_run = { outcome: await runOutcome(), headline: await text(T('run-headline')) }
  chapter(`${KIND} challenge result`, manifest.v1_run)
  Object.assign(manifest.v1_run, await runDetails())
  const cid = new URL(page.url()).searchParams.get('creature')
  const cr = cid ? await (await fetch(`${BASE}/api/forge/creatures/${cid}`)).json().catch(() => null) : null
  manifest.creature = { id: cid, v1: (cr?.versions || []).find((v) => v.n === 1) ?? null }
  await show(T('run-headline'), 3000); await still('v1-result')
  if (await vis(T('score-bars'))) await show(T('score-bars'), 2500)
  if (await vis(T('seed-strip'))) await show(T('seed-strip'), 1500)
  await page.waitForSelector(`${T('replay')} canvas`, { timeout: 120000 }).catch(() => {})
  chapter('replay of the failure')
  await playReplayFromStart(T('replay'), 7); await still('v1-replay')

  flow: {
  if (STOP_AFTER === 'challenge') { chapter('end of screening take (no investigation, no model call)'); break flow }
  await show(T('probes-option'), 800)
  await page.check(T('probes-checkbox')); await sleep(900)
  await click(MODE === 'live' ? T('investigate-btn') : T('investigate-mock-btn'))
  chapter(MODE === 'live' ? 'investigate with AI clicked (LIVE Nemotron)' : 'scripted mock investigation clicked (NOT a model)')
  await page.waitForSelector(T('inv-progress'), { timeout: 60000 })
  await show(T('inv-progress'), 1500)
  const done = `${T('investigation-record')}, ${T('investigation-failed')}, ${T('investigation-error')}`
  const deadline = Date.now() + 1500000
  let lastStages = ''
  while (!(await vis(done)) && Date.now() < deadline) {
    const st = await text(T('inv-stages'))
    if (st && st !== lastStages) { chapter('investigation progress', { stages: st.slice(0, 160) }); lastStages = st }
    await sleep(3000)
  }
  check(await vis(T('investigation-record')), 'investigation finished and its record is shown')
  const recStatus = await page.getAttribute(T('investigation-record'), 'data-status').catch(() => null)
  const items = await page.evaluate(() => fetch(`/api/forge/investigations?cid=${new URL(location.href).searchParams.get('creature')}`).then((r) => r.json()))
  const rec = items.length ? await page.evaluate((id) => fetch(`/api/forge/investigations/${id}`).then((r) => r.json()), items[0].id) : null
  manifest.investigation = rec && { id: rec.id, status: rec.status, provenance: rec.provenance, model_calls: (rec.model_calls || []).map((c) => ({ model: c.model, request_id: c.request_id, latency_s: c.latency_s, usage: c.usage, cost_usd: c.cost_usd, ok: c.ok })),
    selection: rec.selection && { ai: rec.selection.ai, matched_twin: rec.selection.matched_twin, baseline: rec.selection.baseline },
    verdicts: Object.fromEntries(Object.entries(rec.verdicts || {}).map(([k, v]) => [k, { status: v.status, median_diff: v.median_diff, n: v.n ?? null }])),
    ai_edits: (rec.arms || []).find((a) => a.arm_id === rec.selection?.ai)?.edits ?? null, probes: (rec.probes?.results || rec.probes || []).length ?? null, code: rec.code }
  chapter('investigation record shown', { status: recStatus, provenance: rec?.provenance })
  if (MODE === 'live') check(rec?.provenance === 'LIVE' && (rec.model_calls || []).every((c) => c.request_id && !String(c.request_id).startsWith('scripted')), 'record is LIVE with real request ids')

  await show(T('inv-provenance'), 2500); await still('provenance')
  for (const sel of [T('model-response-live'), T('model-call')]) if (await vis(sel)) { await show(sel, 4000); await still('model-call'); break }
  if (await vis(T('probe-row'))) { chapter('probe results'); await show(T('probe-row'), 4500); await still('probes') }
  if (await vis(T('arms-table'))) { chapter('arms screened'); await show(T('arms-table'), 3500) }
  if (await vis(T('validation-grid'))) { chapter('held-out validation: AI vs matched twin vs baseline'); await show(T('validation-grid'), 5000); await still('verdicts') }
  if (await vis(T('arena-twin-toggle'))) { await click(T('arena-twin-toggle'), 800) }
  if (await vis(T('arena-viewports'))) {
    await page.waitForSelector(`${T('arena-viewports')} canvas`, { timeout: 180000 }).catch(() => {})
    chapter('side-by-side replay on a held-out seed'); await playReplayFromStart(T('arena-compare'), 9); await still('arena-replay')
  }
  await show(T('accept-panel'), 2500)
  const canAccept = (await page.getAttribute(T('accept-panel'), 'data-can-accept').catch(() => null)) === 'true'
  manifest.ai_verdict = manifest.investigation?.verdicts?.[manifest.investigation?.selection?.ai]?.status ?? null
  if (canAccept) {
    chapter('accept enabled: MuJoCo verified the AI redesign', { verdict: manifest.ai_verdict })
    await click(T('accept-btn'), 1500)
    await page.waitForSelector(T('lineage-v2'), { timeout: 60000 })
    chapter('accepted as v2', { version: await text(T('version-chip')), lineage: await text(T('lineage-v2')) })
    await show(T('lineage'), 3500); await still('v2-lineage')
    await click(T('challenge-new-version'))
    chapter(`v2 ${KIND} challenge started`)
    await page.waitForSelector(`${T('run-result')}, ${T('run-failed')}`, { timeout: 420000 })
    manifest.v2_run = { outcome: await runOutcome(), headline: await text(T('run-headline')) }
    chapter(`v2 ${KIND} challenge result`, manifest.v2_run)
    Object.assign(manifest.v2_run, await runDetails())
    await show(T('run-headline'), 3500); await still('v2-result')
    await page.waitForSelector(`${T('replay')} canvas`, { timeout: 120000 }).catch(() => {})
    await playReplayFromStart(T('replay'), 7); await still('v2-replay')
    manifest.accepted = true
  } else {
    chapter('accept stays disabled: nothing verified', { verdict: manifest.ai_verdict, status: recStatus })
    for (const sel of [T('accept-blocked'), T('why-not'), T('model-failure')]) if (await vis(sel)) { await show(sel, 4000); break }
    await still('not-verified')
    manifest.accepted = false
  }
  }   // flow
  await sleep(2000)
  chapter('end of take')
} catch (e) { manifest.errors.push(`flow threw: ${e.message}`); exitCode = 1; console.log('FAIL flow threw:', e.message) }

await cdp.send('Page.stopScreencast').catch(() => {})
await sleep(500)
manifest.finished_utc = new Date().toISOString()
manifest.duration_s = now()
manifest.ledger_after = (await (await fetch(`${BASE}/api/forge/status`)).json().catch(() => ({}))).ledger ?? null
manifest.frames = { count: frames.length, mean_fps: frames.length > 1 ? +((frames.length - 1) / (frames[frames.length - 1] - frames[0])).toFixed(2) : 0 }

// Constant-30-fps H.264 from the variable-rate screencast (each frame held until the next one arrived).
if (process.env.FFMPEG && frames.length > 1) {
  const lines = []
  for (let i = 0; i < frames.length; i++) {
    lines.push(`file 'frames/${String(i).padStart(6, '0')}.jpg'`)
    lines.push(`duration ${(i + 1 < frames.length ? frames[i + 1] - frames[i] : 1 / 30).toFixed(4)}`)
  }
  lines.push(`file 'frames/${String(frames.length - 1).padStart(6, '0')}.jpg'`)
  writeFileSync(`${OUT}/frames.txt`, lines.join('\n') + '\n')
  const r = spawnSync(process.env.FFMPEG, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', 'frames.txt', '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-movflags', '+faststart', 'take.mp4'], { cwd: OUT, encoding: 'utf8' })
  manifest.video = r.status === 0 ? { file: 'take.mp4', fps: 30, codec: 'h264', crf: 16 } : { error: (r.stderr || '').slice(-500) }
}
manifest.stills = readdirSync(`${OUT}/stills`)
writeFileSync(`${OUT}/manifest.json`, JSON.stringify(manifest, null, 1))
console.log('MANIFEST ' + JSON.stringify({ attempt: manifest.attempt, mode: MODE, duration_s: manifest.duration_s, frames: manifest.frames, ai_verdict: manifest.ai_verdict, accepted: manifest.accepted, video: manifest.video, errors: manifest.errors.length }))
await browser.close()
process.exit(exitCode || (manifest.checks.some((c) => !c.ok) ? 1 : 0))
