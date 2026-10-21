// DEMO VIDEO CAPTURE: one continuous, human-paced take of the real Studio for the submission video (raw footage; the edit
// and voice-over come later). Shots follow docs/submission/STORYBOARD.md: the Verified repair tab (DO-1, NO_AI) and then
// "Nemotron's experiment" (recorded LIVE investigation, played back; reconstructed damaged-plant replays).
// Nothing is simulated and no model is called: both pages only play back hash-pinned files (/api/do1/*, /api/nemotron/*);
// every other /api request is blocked and listed in the manifest. The script adds one thing to the picture, a cursor
// dot (Chrome draws no cursor into a screencast); the manifest says so.
// Rendering: headless Edge/Chrome on the REAL GPU (ANGLE D3D11), so no window is shown and nothing on the desktop can crop
// it. The manifest records the WebGL renderer; a software renderer is refused unless SOFTWARE=1 (smoke tests only).
// Framing: the page is laid out at (1920/ZOOM)x(1080/ZOOM) CSS px and rendered at device scale ZOOM, so every frame is
// exactly 1920x1080 and whole sections (all viewports, transport and chart) fit on screen. ZOOM=1 gives a 1:1 layout.
// Output (OUT_DIR): frames/*.jpg (CDP screencast with timestamps), take.mp4 (constant 30 fps H.264, via FFMPEG), stills/*.png,
// manifest.json (chapters with start/end times keyed to the storyboard shots, checks, renderer, blocked requests).
// Usage: BASE_URL=http://127.0.0.1:8000 OUT_DIR=<dir> [FFMPEG=ffmpeg] [ZOOM=0.8] [SOFTWARE=1] [PACE=1] [SHOTS=hook,do1,...] node e2e/demo-video-capture.mjs
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync, rmSync, writeFileSync, readdirSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

const BASE = process.env.BASE_URL
const OUT = process.env.OUT_DIR
if (!BASE || !OUT) throw new Error('BASE_URL and OUT_DIR are required')
const SOFTWARE = process.env.SOFTWARE === '1'       // SwiftShader, for smoke tests only
const ZOOM = Number(process.env.ZOOM || '0.8')
const VIEW = { width: Math.round(1920 / ZOOM), height: Math.round(1080 / ZOOM) }
const PACE = Number(process.env.PACE || '1')            // < 1 = faster (smoke tests); every pause is multiplied by it
const SHOTS = (process.env.SHOTS || 'hook,do1,why,nemo-intro,failure,hypotheses,fork,measure,belief,repair,verify,lab,scope,close').split(',')
const FFMPEG = process.env.FFMPEG || 'ffmpeg'
rmSync(`${OUT}/frames`, { recursive: true, force: true })
for (const d of ['frames', 'stills']) mkdirSync(`${OUT}/${d}`, { recursive: true })
const exe = [process.env.BROWSER_PATH, 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe', '/usr/bin/google-chrome'].filter(Boolean).find((p) => existsSync(p))
if (!exe) throw new Error('no Edge/Chrome found; set BROWSER_PATH')

const T = (id) => `[data-testid="${id}"]`
const sleep = (ms) => new Promise((r) => setTimeout(r, ms * PACE))
const t0 = Date.now()
const now = () => +((Date.now() - t0) / 1000).toFixed(2)
const manifest = { kind: 'demo-video-capture', base: BASE, started_utc: new Date().toISOString(), software: SOFTWARE, pace: PACE, shots: SHOTS,
  layout: { css_viewport: VIEW, device_scale: ZOOM, frame: '1920x1080' },
  overlay: 'cursor dot drawn by the capture script (no cursor in a screencast); nothing else is added to the page',
  playback_only: 'no simulation and no model call: the pages play back hash-pinned files; other /api requests are blocked',
  chapters: [], checks: [], errors: [], blocked: [] }
let open = null
const chapter = (shot, title) => {
  if (open) { open.end = now(); open.video_end = +(open.end - manifest.video_t0).toFixed(2) }
  open = { shot, title, start: now(), end: null, video_start: +(now() - manifest.video_t0).toFixed(2) }
  manifest.chapters.push(open)
  console.log(`[${open.start}s] ${shot}: ${title}`)
}
const check = (c, m) => { manifest.checks.push({ ok: !!c, m }); console.log(`${c ? 'PASS' : 'FAIL'} ${m}`) }

const args = ['--hide-scrollbars', '--force-color-profile=srgb', '--disable-features=Translate', '--no-first-run', '--no-default-browser-check']
if (SOFTWARE) args.push('--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist')
else args.push('--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist')
const browser = await chromium.launch({ executablePath: exe, headless: true, args })
const ctx = await browser.newContext({ viewport: VIEW, deviceScaleFactor: ZOOM, colorScheme: 'dark' })   // fresh profile
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
// playback only: the two filmed pages read only their pinned files; the app shell's start-up data is the only other read
await ctx.route('**/api/**', (r) => {
  const u = new URL(r.request().url())
  const allowed = r.request().method() === 'GET' && (/^\/api\/(do1|nemotron)\//.test(u.pathname) || ['/api/schema', '/api/experiments/phase0', '/api/version'].includes(u.pathname))
  if (allowed) return r.continue()
  manifest.blocked.push(`${r.request().method()} ${u.pathname}`)
  return r.abort()
})
const page = await ctx.newPage()
page.setDefaultTimeout(60000)
page.on('pageerror', (e) => manifest.errors.push(`pageerror ${e.message}`))
// console errors are reported, not fatal (the Studio has no /favicon.ico, so every page load logs one 404)
manifest.console_errors = []
page.on('console', (m) => { if (m.type() === 'error') manifest.console_errors.push(m.text()) })
page.on('response', (r) => { if (r.status() >= 400 && r.url().includes('/api/')) manifest.errors.push(`HTTP ${r.status()} ${new URL(r.url()).pathname}`) })

const cdp = await ctx.newCDPSession(page)
const frames = []
cdp.on('Page.screencastFrame', async (f) => {
  const i = frames.length
  frames.push(f.metadata.timestamp)
  writeFileSync(`${OUT}/frames/${String(i).padStart(6, '0')}.jpg`, Buffer.from(f.data, 'base64'))
  await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {})
})

// --- human-paced input (as forge-demo-capture.mjs)
let mouse = [VIEW.width / 2, VIEW.height / 2]
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
/** Smooth-scroll so `sel` sits at `block` ('start' | 'center'), with the top 70 px kept clear of the sticky header. */
async function view(sel, block = 'start', pause = 1200) {
  const el = page.locator(sel).first()
  await el.waitFor({ state: 'visible' })
  await el.evaluate((n, block) => {
    const r = n.getBoundingClientRect()
    const y = block === 'center' ? r.top + scrollY - (innerHeight - r.height) / 2 : r.top + scrollY - 76
    scrollTo({ top: Math.max(0, y), behavior: 'smooth' })
  }, block)
  await sleep(1100)
  await sleep(pause)
}
async function point(sel, pause = 900) {
  const b = await page.locator(sel).first().boundingBox()
  if (b) await glide(b.x + Math.min(b.width / 2, 300), b.y + Math.min(b.height / 2, 40), 600)   // CSS px (Playwright input space)
  await sleep(pause)
}
async function click(sel, pause = 700) {
  const loc = typeof sel === 'string' ? page.locator(sel).first() : sel
  await loc.scrollIntoViewIfNeeded()
  const b = await loc.boundingBox()
  if (!b) throw new Error(`not clickable: ${sel}`)
  await glide(b.x + b.width / 2, b.y + b.height / 2, 450)
  await page.mouse.down(); await sleep(90); await page.mouse.up()
  await sleep(pause)
}
async function still(name) { await page.screenshot({ path: `${OUT}/stills/${String(manifest.chapters.length).padStart(2, '0')}-${name}.png` }) }
const text = async (sel) => ((await page.textContent(sel).catch(() => '')) || '').replace(/\s+/g, ' ').trim()
/** Real-time playback of the replay inside `scope`: 1x, from the start. */
async function play(scope, seconds) {
  await click(page.locator(`${scope} button`, { hasText: /^1×$/ }), 200)
  await click(page.locator(`${scope} button`, { hasText: 'Restart' }), 200)
  await glide(mouse[0], mouse[1] - 200, 400)
  await sleep(seconds * 1000)
}
const want = (s) => SHOTS.includes(s)

let exitCode = 0
try {
  await page.goto(`${BASE}/?tab=recovery`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector(T('do1-viewports') + ' canvas')
  manifest.renderer = await page.evaluate(() => {
    const g = document.createElement('canvas').getContext('webgl2') || document.createElement('canvas').getContext('webgl')
    const x = g && g.getExtension('WEBGL_debug_renderer_info')
    return x ? g.getParameter(x.UNMASKED_RENDERER_WEBGL) : null
  })
  const software = /swiftshader|llvmpipe|software/i.test(manifest.renderer || '')
  check(SOFTWARE || !software, `WebGL renderer: ${manifest.renderer}${SOFTWARE ? ' (software smoke test)' : ''}`)
  if (!SOFTWARE && software) throw new Error('software renderer: final footage must come from the real GPU')
  const do1 = await page.evaluate(() => fetch('/api/do1/index').then((r) => r.json()))
  const nem = await page.evaluate(() => fetch('/api/nemotron/case').then((r) => r.json()))
  manifest.evidence = { do1_default_seed: do1.default_seed, do1_walking: Object.fromEntries(['faulty', 'frozen', 'do1'].map((k) => [k, do1.rows[k].filter((r) => r.walking).length])),
    nemotron_instance: nem.case.instance_id, replays_available: nem.replays.available, playback: nem.playback }
  check(nem.replays.available, 'damaged-plant replays are available and verified')
  await page.evaluate(() => scrollTo(0, 0))
  await sleep(600)
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 })
  manifest.video_t0 = now()        // chapter times minus video_t0 = times in take.mp4

  // ---------------------------------------------------------------- 1. hook: the damaged robot, three ways
  if (want('hook')) {
    chapter('hook', 'Verified repair: faulty / frozen / DO-1 on the illustrative seed, real time')
    check((await text(T('do1-illustrative'))).includes('Illustrative'), 'the pre-declared illustrative seed is selected')
    await view(T('do1-stage'), 'start', 300)
    await play(T('do1-stage'), 10.5)
    await still('do1-three-way')
  }
  // ---------------------------------------------------------------- 2. DO-1 result cards
  if (want('do1')) {
    chapter('do1', 'Validation and confirmation counts, deterministic attribution')
    await view(T('do1-recovery'), 'start', 600)
    for (const id of ['faulty', 'frozen', 'do1']) await point(T(`do1-card-${id}`), 4200)
    await point(T('do1-attribution'), 6000)
    await still('do1-cards')
  }
  if (want('why')) {
    chapter('why', 'Why the longer walk is not a full recovery')
    await view(T('do1-why'), 'center', 13000)
    await still('do1-why')
  }

  // ---------------------------------------------------------------- 3. Nemotron's experiment
  await page.goto(`${BASE}/?tab=nemotron`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector(T('nemotron-case'))
  if (want('nemo-intro')) {
    chapter('nemo-intro', 'Recorded LIVE investigation, playback; captions')
    await sleep(1500)
    await point(T('nm-flag-playback'), 2200)
    await point(T('nm-flag-scope'), 2200)
    await still('nemotron-hero')
  }
  if (want('failure')) {
    chapter('failure', 'Stage 1: the damaged robot (recorded measurements, reconstructed replay)')
    await view(T('nm-stage-failure'), 'start', 1200)
    await click(T('nm-watch-failure'), 600)
    await view(T('nm-replay-failure'), 'center', 200)
    await play(T('nm-replay-failure'), 7)
    await still('failure-replay')
  }
  if (want('hypotheses')) {
    chapter('hypotheses', 'Stage 2: competing hypotheses, belief 0.895 / 0.105')
    await view(T('nm-stage-hypotheses'), 'start', 4500)
  }
  if (want('fork')) {
    chapter('fork', 'Stage 3: tied EIG; Nemotron freq@x0.85 vs engine freq@x1.2; no registered prediction')
    await view(T('nm-stage-fork'), 'start', 1500)
    await point(`${T('nm-candidates')} tr.pick-eng`, 1800)
    await point(`${T('nm-candidates')} tr.pick-nem`, 1800)
    await view(T('nm-fork-nemotron'), 'center', 3500)
    await point(T('nm-prediction'), 2500)
    await still('fork')
  }
  if (want('measure')) {
    chapter('measure', 'Stage 4: both experiments on the damaged robot (exact recorded measurements)')
    await view(T('nm-stage-measure'), 'start', 2500)
    if (await page.isVisible(T('nm-watch-experiment'))) await click(T('nm-watch-experiment'), 600)
    const seeds = nem.case.arms.A3.experiments[1].seeds
    const differ = seeds.find((s) => {
      const a = nem.case.arms.A3.experiments[1].per_seed.find((x) => x.seed === s), b = nem.case.arms.A1e.experiments[1].per_seed.find((x) => x.seed === s)
      return a.walking === 1 && b.walking !== 1
    })
    const fell = seeds.find((s) => nem.case.arms.A3.experiments[1].per_seed.find((x) => x.seed === s).walking !== 1)
    await view(T('nm-replay-experiment'), 'center', 200)
    await click(T(`nm-replay-experiment-seed-${differ}`), 600)
    await play(T('nm-replay-experiment'), 9)
    await still('experiment-replay')
    chapter('measure-fall', "Stage 4: the start where Nemotron's own experiment fell")
    await click(T(`nm-replay-experiment-seed-${fell}`), 600)
    await play(T('nm-replay-experiment'), 4)
    manifest.measure_seeds = { differ, fell }
  }
  if (want('belief')) {
    chapter('belief', 'Stage 5: the same engine ends on opposite sides')
    await view(T('nm-stage-belief'), 'start', 9500)
    await still('belief')
  }
  if (want('repair')) {
    chapter('repair', "Stage 6: Nemotron delegates; the engine's optimiser repairs")
    await view(T('nm-stage-repair'), 'start', 2500)
    await point(T('nm-hyp-note'), 2500)
    await view(T('nm-repair-A3'), 'center', 3000)
    await still('repair')
  }
  if (want('verify')) {
    chapter('verify', 'Stage 7: independent verification; reconstructed replays on the illustrative hidden start')
    await view(T('nm-stage-verify'), 'start', 2500)
    await click(T('nm-watch-verify'), 600)
    await view(T('nm-replay-verify'), 'center', 200)
    await play(T('nm-replay-verify'), 10)
    await still('verify-replay')
  }
  if (want('lab')) {
    chapter('lab', 'How the laboratory works: Nemotron decides, deterministic instruments act, an independent verifier judges')
    await view(T('nm-lab'), 'center', 18000)
    await still('lab')
  }
  if (want('scope')) {
    chapter('scope', 'How representative: A4 replicate PARTIAL; 36 instances 15 vs 14')
    await view(T('nm-stage-scope'), 'start', 11000)
    await still('scope')
    chapter('studies', 'Every study: favourable, mixed, negative; DO-1 NO_AI')
    await view(T('nm-stage-studies'), 'start', 2500)
    await point(T('nm-study-forge-scoreboard'), 5000)
    await point(T('nm-study-do1'), 5000)
    await still('studies')
  }
  if (want('close')) {
    chapter('close', 'Provenance footer')
    await view(T('nm-prov'), 'center', 3000)
  }
  if (open) { open.end = now(); open.video_end = +(open.end - manifest.video_t0).toFixed(2) }
  await cdp.send('Page.stopScreencast')
  await sleep(300)
} catch (e) {
  manifest.errors.push(`capture ${e.message}`)
  console.log('ERROR', e.message)
  exitCode = 1
} finally {
  await browser.close()
}

manifest.duration_s = now()
manifest.frames = frames.length
if (frames.length > 1) {
  // constant 30 fps from the screencast's wall-clock timestamps (the concat demuxer holds each frame for its real duration)
  const names = readdirSync(`${OUT}/frames`).filter((f) => f.endsWith('.jpg')).sort()
  const lines = ['ffconcat version 1.0']
  names.forEach((n, i) => { lines.push(`file 'frames/${n}'`); lines.push(`duration ${(i + 1 < frames.length ? frames[i + 1] - frames[i] : 1 / 30).toFixed(4)}`) })
  lines.push(`file 'frames/${names[names.length - 1]}'`)
  writeFileSync(`${OUT}/frames.txt`, lines.join('\n') + '\n')
  const r = spawnSync(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', 'frames.txt', '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264',
    '-preset', 'slow', '-crf', '16', '-movflags', '+faststart', 'take.mp4'], { cwd: OUT, encoding: 'utf8' })
  manifest.video = r.status === 0 ? { file: 'take.mp4', fps: 30, codec: 'h264', note: 'constant 30 fps from screencast timestamps' } : { error: (r.stderr || String(r.error)).slice(0, 400) }
  manifest.screencast_fps = +(frames.length / (frames[frames.length - 1] - frames[0])).toFixed(1)
}
if (manifest.errors.length) exitCode = 1
writeFileSync(`${OUT}/manifest.json`, JSON.stringify(manifest, null, 1))
console.log('MANIFEST ' + JSON.stringify({ duration_s: manifest.duration_s, frames: manifest.frames, screencast_fps: manifest.screencast_fps, renderer: manifest.renderer,
  video: manifest.video, blocked: manifest.blocked.length, errors: manifest.errors.length, failed_checks: manifest.checks.filter((c) => !c.ok).length }))
process.exit(exitCode || (manifest.checks.some((c) => !c.ok) ? 1 : 0))
