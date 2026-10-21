// Real-browser flow for "Nemotron's experiment" (W2). Needs a running Studio server (BASE_URL) with the built frontend and the
// pinned files in experiments/w2. The page may only read GET /api/nemotron/case and the verified damaged-plant replays
// GET /api/nemotron/replay/<name>/<seed> (playback of static files; no model call, no simulation).
// Every number checked on screen is compared with the API response, which the backend reads from the hash-pinned case files.
// Usage: BASE_URL=http://127.0.0.1:8000 [SHOT_DIR=dir] node e2e/nemotron-flow.mjs
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
const browser = await chromium.launch({ executablePath: exe, headless: true,
  args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await ctx.newPage()
page.setDefaultTimeout(60000)
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const apiCalls = []
page.on('request', (r) => { if (r.url().includes('/api/nemotron') || r.url().includes('/replay')) apiCalls.push(`${r.method()} ${new URL(r.url()).pathname}`) })
const txt = async (sel) => ((await page.textContent(sel)) || '').replace(/\s+/g, ' ').trim()

try {
  await page.goto(`${BASE}/?tab=nemotron`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="nemotron-case"]')
  const d = await page.evaluate(() => fetch('/api/nemotron/case').then((r) => r.json()))
  const c = d.case
  ok(d.playback === 'RECORDED_LIVE', 'the API marks the case as recorded playback')
  ok((await txt('[data-testid="nm-flag-playback"]')).includes('No model is called on this page'), 'the playback caption is shown')
  ok((await txt('[data-testid="nm-flag-scope"]')).includes('the engine alone won 3 instances Nemotron lost'), 'the scope caption is shown')
  ok((await txt('[data-testid="nm-flag-repair"]')).includes("engine's optimiser"), 'the repair caption credits the optimiser')
  ok((await txt('[data-testid="nm-flag-do1"]')).includes('NO_AI'), 'DO-1 is stated as NO_AI')

  // stages in order
  const stages = await page.$$eval('[data-testid^="nm-stage-"]', (els) => els.map((e) => e.getAttribute('data-testid')))
  ok(JSON.stringify(stages) === JSON.stringify(['nm-stage-failure', 'nm-stage-hypotheses', 'nm-stage-fork', 'nm-stage-measure', 'nm-stage-belief',
    'nm-stage-repair', 'nm-stage-verify', 'nm-stage-scope', 'nm-stage-studies']), `the nine stages are in story order (${stages.join(', ')})`)

  // failure: observation tiles = recorded per-seed rows
  const obs = c.shared.observation
  ok((await page.$$('[data-testid="nm-observe"] li')).length === obs.per_seed.length, `${obs.per_seed.length} observation tiles`)
  ok((await txt('[data-testid="nm-observe"]')).startsWith(`${obs.n_walking}/${obs.per_seed.length} trials walked`), 'observation walking count matches the record')

  // fork: candidate table and both picks
  const rows = await page.$$('[data-testid="nm-candidates"] tbody tr')
  ok(rows.length === c.fork.notebook.candidates.length, `all ${c.fork.notebook.candidates.length} candidate experiments are listed`)
  const nemRow = await page.$eval('[data-testid="nm-candidates"] tr.pick-nem td code', (e) => e.textContent)
  const engRow = await page.$eval('[data-testid="nm-candidates"] tr.pick-eng td code', (e) => e.textContent)
  ok(nemRow === c.fork.nemotron.experiment && engRow === c.fork.engine.experiment, `picks highlighted: Nemotron ${nemRow}, engine ${engRow}`)
  ok((await txt('[data-testid="nm-fork-nemotron"]')).includes(c.fork.nemotron.call.request_id), 'the recorded request id is shown')
  ok((await txt('[data-testid="nm-prediction"]')).includes('Registered prediction: none'), 'the missing registered prediction is stated')

  // measurements and beliefs
  for (const arm of ['A3', 'A1e']) {
    const e = c.arms[arm].experiments[1]
    ok((await txt(`[data-testid="nm-x1-${arm}"]`)).startsWith(`${e.n_walking}/${e.per_seed.length} trials walked`), `${arm}: X1 walking ${e.n_walking}/${e.per_seed.length}`)
  }
  ok((await txt('[data-testid="nm-after-A3"]')).startsWith('Right-side actuator weakness'), "Nemotron's lane ends on the right side")
  ok((await txt('[data-testid="nm-after-A1e"]')).startsWith('Left-side actuator weakness'), "the engine's lane ends on the left side")
  ok((await txt('[data-testid="nm-hyp-note"]')).includes('no weight'), "Nemotron's added hypotheses are shown as adding no weight")

  // verification
  for (const arm of ['A3', 'A1e']) {
    const v = c.arms[arm].verification
    ok((await txt(`[data-testid="nm-verify-${arm}"]`)).includes(`${v.walking}/${v.n} hidden validation starts walk`), `${arm}: verification ${v.walking}/${v.n} ${v.status}`)
  }
  ok((await txt('[data-testid="nm-a4"]')).includes(`(${c.arms.A4.verification.walking}/${c.arms.A4.verification.n})`), 'the A4 replicate that did not verify is shown')
  const g = d.cross.aggregates
  const cross = await txt('[data-testid="nm-cross"]')
  ok(cross.includes(`Nemotron ${g.full.A3}, engine alone ${g.full.A1e}`) && cross.includes(`p = ${g.mcnemar_one_sided_p_A3_gt_A1e}`), 'cross-instance parity is shown with its p value')
  ok((await page.$$('[data-testid="nm-cross"] .nm-dots i.this')).length === 3, 'this instance is marked in all three dot rows')

  // studies
  const studyRows = await page.$$('[data-testid^="nm-study-"]')
  ok(studyRows.length === d.studies.studies.length, `all ${d.studies.studies.length} studies are listed`)
  ok((await txt('[data-testid="nm-study-do1"]')).includes('NO_AI'), 'the DO-1 row is credited NO_AI')
  ok(d.replays.available ? (await txt('[data-testid="nm-replay-fidelity"]')).includes('reproduced') || (await txt('[data-testid="nm-replay-fidelity"]')).includes('equal to the record')
    : (await txt('[data-testid="nm-replays"]')).includes('awaits owner approval'), 'damaged-plant replay status / fidelity is stated')

  // damaged-plant replays: one viewer at a time; captions = recorded outcomes; reconstruction labelled
  if (d.replays.available) {
    const x1 = { x1_nem: c.arms.A3.experiments[1], x1_eng: c.arms.A1e.experiments[1] }
    const outcome = (e, s) => { const f = e.per_seed.find((x) => x.seed === s); return f.walking === 1 ? 'walks' : f.time_upright < 10 ? `falls at ${f.time_upright.toFixed(1)} s` : 'upright, not walking' }
    await page.waitForSelector('[data-testid="nm-replay-experiment"] canvas')
    ok((await page.$$('[data-testid="nm-replay-experiment"] canvas')).length === 2, 'the experiment replay shows both experiments side by side')
    ok((await txt('[data-testid="nm-replay-experiment"]')).includes('Reconstructed MuJoCo replay'), 'the experiment replay is labelled as a reconstruction')
    for (const s of x1.x1_nem.seeds) {
      await page.click(`[data-testid="nm-replay-experiment-seed-${s}"]`)
      await page.waitForFunction((s) => [...document.querySelectorAll('[data-testid="nm-replay-experiment"] .vp-label')].every((e) => e.textContent.endsWith(`seed ${s}`)), s)
      const caps = await page.$$eval('[data-testid="nm-replay-experiment"] figcaption', (els) => els.map((e) => e.textContent.trim()))
      ok(caps[0] === outcome(x1.x1_nem, s) && caps[1] === outcome(x1.x1_eng, s), `seed ${s}: captions are the recorded outcomes (${caps.join(' | ')})`)
    }
    const p = await page.evaluate((s) => fetch(`/api/nemotron/replay/x1_nem/${s}`).then((r) => r.json()), x1.x1_nem.seeds[0])
    ok(p.w2_demo.plant.includes('hidden') && p.w2_demo.fk_max_err_m === 0, 'payloads are the hidden-plant export with exact frames')
    await page.click('[data-testid="nm-watch-verify"]')
    await page.waitForSelector('[data-testid="nm-replay-verify"] canvas')
    ok((await page.$$('[data-testid="nm-replay-experiment"]')).length === 0, 'only one replay viewer is mounted at a time')
    ok((await page.$$('[data-testid="nm-replay-verify"] canvas')).length === 3, 'verification replay: faulty robot and both submitted designs')
    const v = d.replays.validation
    const want = v.a3_submitted.rows.find((r) => r.walking && !v.a1e_submitted.rows.find((x) => x.seed === r.seed).walking).seed
    ok((await txt('[data-testid="nm-replay-verify"] .vp-label')).endsWith(`seed ${want}`), `the verification replay opens on the pre-declared illustrative seed ${want}`)
    ok((await txt('[data-testid="nm-replay-verify-note"]')).includes('not an archived original'), 'validation replays are labelled reconstructed, not archived originals')
    ok((await page.$$('[data-testid^="nm-replay-verify-seed-"]')).length === v.a3_submitted.rows.length, `all ${v.a3_submitted.rows.length} validation seeds are selectable`)
    if (SHOT) {
      await page.waitForTimeout(2500)
      await page.locator('[data-testid="nm-stage-verify"]').screenshot({ path: `${SHOT}/nemotron-verify-replay.png` })
      await page.click('[data-testid="nm-watch-experiment"]')
      await page.waitForSelector('[data-testid="nm-replay-experiment"] canvas')
      await page.click(`[data-testid="nm-replay-experiment-seed-${x1.x1_nem.seeds[2]}"]`)
      await page.waitForTimeout(3000)
      await page.locator('[data-testid="nm-stage-measure"]').screenshot({ path: `${SHOT}/nemotron-experiment-replay.png` })
    }
  }
  if (SHOT) {
    await page.screenshot({ path: `${SHOT}/nemotron-full.png`, fullPage: true })
    for (const s of ['fork', 'measure', 'belief', 'verify', 'scope']) {
      await page.locator(`[data-testid="nm-stage-${s}"]`).screenshot({ path: `${SHOT}/nemotron-${s}.png` })
    }
  }
  ok(apiCalls.every((x) => x === 'GET /api/nemotron/case' || /^GET \/api\/nemotron\/replay\/[a-z0-9_]+\/\d+$/.test(x)),
    `the page only issued GET /api/nemotron/case and /api/nemotron/replay/* (${[...new Set(apiCalls.map((x) => x.replace(/\/\d+$/, '/<seed>')))].join(', ')})`)

  // narrow layout
  await page.setViewportSize({ width: 390, height: 900 })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  ok(overflow <= 1, `no horizontal page scroll at 390 px (${overflow} px)`)
  if (SHOT) await page.screenshot({ path: `${SHOT}/nemotron-narrow.png`, fullPage: false })
  ok(errors.length === 0, `no page errors (${errors.join(' | ')})`)
} finally {
  await browser.close()
}
console.log(failed ? `${failed} FAILED` : 'ALL PASSED')
process.exit(failed ? 1 : 0)
