// Real-browser flow for the Verified repair (DO-1) page. Needs a running Studio server (BASE_URL) with the built frontend and the
// committed export in experiments/do1/demo. The DO-1 page itself must only read /api/do1/* (static, verified files).
// The regression pass over the other tabs aborts every simulation-backed request (replay, simulate, POST), so no physics
// runs; blocked requests are listed.
// Usage: BASE_URL=http://127.0.0.1:8000 [SHOT_DIR=dir] node e2e/do1-flow.mjs   (SHOT_DIR also gets a frame sequence)
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync } from 'node:fs'

const BASE = process.env.BASE_URL
if (!BASE) throw new Error('BASE_URL is required')
const SHOT = process.env.SHOT_DIR
if (SHOT) mkdirSync(SHOT, { recursive: true })
const exe = [process.env.BROWSER_PATH, 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe', '/usr/bin/google-chrome', '/usr/bin/chromium'].filter(Boolean).find((p) => existsSync(p))
if (!exe) throw new Error('no Chrome/Edge found; set BROWSER_PATH')

let failed = 0
const ok = (c, m) => { console.log(`${c ? 'PASS' : 'FAIL'} ${m}`); if (!c) failed++ }
const SIM = /\/replay|simulate|\/challenges|\/recoveries|\/investigate/
const browser = await chromium.launch({ executablePath: exe, headless: true,
  args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] })
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
const page = await ctx.newPage()
page.setDefaultTimeout(60000)
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const txt = async (sel) => ((await page.textContent(sel)) || '').trim()
const m2 = (x) => `${x.toFixed(2)} m`

try {
  // ---------------------------------------------------------------- the DO-1 page
  await page.goto(`${BASE}/?tab=recovery`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="do1-recovery"]')
  const apiCalls = []
  page.on('request', (r) => { if (r.url().includes('/api/')) apiCalls.push(`${r.method()} ${new URL(r.url()).pathname}`) })
  const idx = await page.evaluate(() => fetch('/api/do1/index').then((r) => r.json()))
  const n = idx.rows.faulty.length
  ok(n === 24 && idx.seeds.validate.length === 24, 'the export has 24 validation seeds')
  for (const d of ['faulty', 'frozen', 'do1']) {
    const walking = idx.rows[d].filter((r) => r.walking).length
    ok(walking === idx.aggregates.walking[d], `${d}: walking count recomputed from rows equals the exported aggregate (${walking})`)
    ok(await txt(`[data-testid="do1-walk-${d}"]`) === `${walking}/${n}`, `${d}: card shows ${walking}/${n} from the evidence`)
    ok(await txt(`[data-testid="do1-median-${d}"]`) === m2(idx.aggregates.median_score_m[d]), `${d}: card median ${m2(idx.aggregates.median_score_m[d])} from the evidence`)
  }
  ok(await txt('[data-testid="do1-status-frozen"]') === idx.verification.frozen.status && idx.verification.frozen.status === 'PARTIAL_IMPROVEMENT', 'frozen status is the recorded PARTIAL_IMPROVEMENT')
  ok(await txt('[data-testid="do1-status-do1"]') === idx.verification.do1.status && idx.verification.do1.status === 'FULL_RECOVERY', 'DO-1 status is the recorded FULL_RECOVERY')
  ok((await txt('[data-testid="do1-confirm-do1"]')).startsWith(`${idx.aggregates.walking.do1_confirm}/${n}`), `DO-1 20 s confirmation shows ${idx.aggregates.walking.do1_confirm}/${n}`)
  ok((await txt('[data-testid="do1-confirm-frozen"]')).startsWith('not run'), 'frozen confirmation is shown as not run')
  ok(/No Nemotron/.test(await txt('[data-testid="do1-attribution"]')), 'attribution: no Nemotron in this repair')
  ok(/not a recovery rate/.test(await txt('[data-testid="do1-scope"]')), 'scope: one replicate, not a recovery rate')
  const why = await txt('[data-testid="do1-why"]')
  ok(why.includes(`${idx.aggregates.walking.frozen}/${n}`) && why.includes('20/24') && why.includes(m2(idx.aggregates.median_score_m.frozen)), 'the explanation cites the frozen walking count, the 20/24 requirement and the measured median')
  ok((await txt('[data-testid="do1-why-reason"]')).includes(idx.verification.frozen.reasons[0]), 'the recorded verifier reason is quoted verbatim')
  ok((await txt('[data-testid="do1-fidelity"]')).startsWith(`${idx.fidelity.production_rows_exact} rows`), 'provenance shows the export fidelity')

  // default seed, three synchronised viewports
  ok(Number(await page.inputValue('[data-testid="do1-seed"]')) === idx.default_seed && idx.default_seed === 66645963, 'the pre-declared default seed 66645963 is selected')
  ok(await page.isVisible('[data-testid="do1-illustrative"]'), 'it is labelled as an illustrative selection')
  await page.waitForSelector('[data-testid="do1-viewports"] canvas')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="do1-viewports"] canvas').length === 3)
  ok(true, 'three viewports render')
  for (const d of ['faulty', 'frozen', 'do1']) {
    const row = idx.rows[d].find((r) => r.seed === idx.default_seed)
    const cap = await txt(`[data-testid="do1-outcome-${d}"]`)
    ok(cap.includes(m2(row.score)), `${d}: per-seed caption shows the recorded distance ${m2(row.score)}`)
  }
  const clock = async () => Number(((await txt('.transport .clock')).match(/[\d.]+/) || ['NaN'])[0])
  await page.getByRole('button', { name: '1×', exact: true }).click()
  await page.click('.transport button:has-text("Restart")')
  await page.waitForTimeout(1500)
  const t0 = await clock()
  await page.waitForTimeout(1500)
  const t1 = await clock()
  // headless software rendering draws ~2 fps and the app caps each frame's step at 0.1 s, so only monotonic progress is checked
  ok(t1 > t0 && t0 > 0, `the shared clock advances (t = ${t0} -> ${t1} s)`)
  // captures only: keep the sticky app header from covering element screenshots (no effect on the checks)
  if (SHOT) await page.addStyleTag({ content: 'header.shell { position: static !important; }' })
  if (SHOT) await page.screenshot({ path: `${SHOT}/do1-page.png`, fullPage: true })
  const box = await page.locator('.do1-stage svg.chart').boundingBox()
  await page.mouse.click(box.x + box.width * 0.6, box.y + box.height / 2)
  const t2 = await clock()
  ok(t2 > 4 && t2 < 8, `clicking the chart scrubs every viewport to one time (t = ${t2} s)`)
  if (SHOT) await page.locator('[data-testid="do1-stage"]').screenshot({ path: `${SHOT}/do1-viewports-t${t2.toFixed(1)}.png` })

  // switch seeds: aggregates stay, payloads load per seed
  const other = idx.seeds.validate[0]
  const loads = []
  const onReq = (r) => { const m = new URL(r.url()).pathname.match(/\/api\/do1\/payload\/(\w+)\/(\d+)\/(\d+)/); if (m) loads.push(m.slice(1).join('/')) }
  page.on('request', onReq)
  await page.selectOption('[data-testid="do1-seed"]', String(other))
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="do1-viewports"] canvas').length === 3)
  await page.waitForTimeout(500)
  ok(['faulty', 'frozen', 'do1'].every((d) => loads.includes(`${d}/10/${other}`)) && loads.length === 3, `switching seed loads exactly the 3 payloads of seed ${other} (${loads.join(', ')})`)
  ok(!(await page.isVisible('[data-testid="do1-illustrative"]')) && await page.isVisible('[data-testid="do1-reset-seed"]'), 'a non-default seed is not labelled illustrative')
  ok(await txt('[data-testid="do1-walk-frozen"]') === `${idx.aggregates.walking.frozen}/${n}`, 'aggregate statistics stay visible after the switch')
  await page.click('[data-testid="do1-card-do1"] .do1-dot >> nth=5')
  await page.waitForTimeout(300)
  ok(Number(await page.inputValue('[data-testid="do1-seed"]')) === idx.seeds.validate[5], 'clicking a seed dot selects that seed')
  await page.click('[data-testid="do1-reset-seed"]')
  ok(Number(await page.inputValue('[data-testid="do1-seed"]')) === idx.default_seed, 'back to the illustrative seed')
  page.off('request', onReq)

  // DO-1 20 s confirmation
  await page.click('[data-testid="do1-mode-confirmation"]')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="do1-viewports"] canvas').length === 1)
  const c0 = idx.rows.do1_confirm[0]
  ok((await txt('[data-testid="do1-outcome-do1"]')).includes(m2(c0.score)), `confirmation replay of seed ${c0.seed} shows its recorded distance ${m2(c0.score)}`)
  await page.click('.transport button:has-text("Restart")')
  await page.waitForTimeout(1500)
  if (SHOT) await page.locator('[data-testid="do1-stage"]').screenshot({ path: `${SHOT}/do1-confirmation.png` })
  await page.click('[data-testid="do1-mode-validation"]')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="do1-viewports"] canvas').length === 3)

  // the page reads only /api/do1, and the API refuses arbitrary paths
  ok(apiCalls.length > 0 && apiCalls.every((c) => c.startsWith('GET /api/do1/')), `the DO-1 page made only GET /api/do1/* requests (${apiCalls.length})`)
  const codes = await page.evaluate(async () => Promise.all(['/api/do1/payload/do1/10/..%2f..%2fSHA256SUMS', '/api/do1/payload/robot/10/66645963',
    '/api/do1/payload/do1/10/12345', '/api/do1/payload/frozen/20/79386176'].map((u) => fetch(u).then((r) => r.status))))
  ok(codes.every((c) => c === 404 || c === 422), `invalid design / seed / path requests are refused (${codes.join(', ')})`)
  ok(errors.length === 0, `no page errors on the DO-1 page${errors.length ? ': ' + errors.join(' | ') : ''}`)

  // ---------------------------------------------------------------- regression: every other tab still renders (no physics)
  const blocked = []
  await page.route('**/api/**', (route) => {
    const r = route.request()
    if (r.method() !== 'GET' || SIM.test(new URL(r.url()).pathname)) { blocked.push(`${r.method()} ${new URL(r.url()).pathname}`); return route.abort() }
    return route.continue()
  })
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="nav-home"]')
  await page.click('[data-testid="nav-investigate"]')
  ok(await page.isVisible('[data-testid="tab-recovery"]') && await page.isVisible('[data-testid="tab-scientist"]') && await page.isVisible('[data-testid="tab-demo"]'),
    'Investigate offers Verified repair next to the existing views')
  const before = errors.length
  for (const tab of ['overview', 'sketch', 'studio', 'compare', 'forge', 'demo', 'scientist', 'causal', 'locomotion', 'lab']) {
    await page.goto(`${BASE}/?tab=${tab}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1200)
    if (tab !== 'overview') ok(((await page.textContent('[data-testid="purpose"]')) || '').length > 20, `tab ${tab} still renders its purpose`)
    else ok(await page.isVisible('[data-testid="nav-home"]'), 'home still renders')
  }
  ok(errors.length === before, `no page errors on the other tabs${errors.length > before ? ': ' + errors.slice(before).join(' | ') : ''}`)
  console.log(`INFO simulation-backed requests blocked during the regression pass (${blocked.length}): ${[...new Set(blocked)].join(', ') || 'none'}`)
  await page.unroute('**/api/**')
} catch (e) { ok(false, `flow threw: ${e.message}`) }
await ctx.close()

// ---------------------------------------------------------------- frame sequence of the illustrative seed (stills at fixed sim times)
if (SHOT && !failed) {
  const fctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const fp = await fctx.newPage()
  await fp.goto(`${BASE}/?tab=recovery`, { waitUntil: 'domcontentloaded' })
  await fp.waitForFunction(() => document.querySelectorAll('[data-testid="do1-viewports"] canvas').length === 3, null, { timeout: 60000 })
  await fp.getByRole('button', { name: 'Pause' }).click().catch(() => {})
  await fp.addStyleTag({ content: 'header.shell { position: static !important; }' })
  const chart = fp.locator('.do1-stage svg.chart')
  for (const t of [0, 1, 2, 4, 6, 10]) {
    const b = await chart.boundingBox()
    // HeightChart maps sim time to x = 34 + t / duration * 558 in a 600-wide viewBox (Timeline.tsx)
    await fp.mouse.click(b.x + b.width * ((34 + (t / 10) * 558) / 600), b.y + b.height / 2)
    await fp.waitForTimeout(900)
    await fp.locator('[data-testid="do1-viewports"]').screenshot({ path: `${SHOT}/frame-t${String(t).padStart(2, '0')}s.png` })
  }
  await fctx.close()
  console.log(`INFO frame sequence saved in ${SHOT}`)
}
await browser.close()
process.exit(failed ? 1 : 0)
