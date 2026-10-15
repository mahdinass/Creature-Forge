// Real-browser flow for the Forge workspace: draw a creature, "Use this creature", land on the live forge tab, run a Push challenge
// in MuJoCo (background job), check the outcome + real replay (or the honest ERROR when the physics runner is missing), and check that
// AI investigation says "not available yet" while the backend answers 503.
// Usage: BASE_URL=... node e2e/forge-flow.mjs   (SHOT_DIR optional; saves forge-1920.png and forge-390.png)
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync } from 'node:fs'

const BASE = process.env.BASE_URL || process.env.BASE
if (!BASE) throw new Error('BASE_URL is required')
const SHOT = process.env.SHOT_DIR
if (SHOT) mkdirSync(SHOT, { recursive: true })
const exe = [process.env.BROWSER_PATH, 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'].filter(Boolean).find((p) => existsSync(p))
if (!exe) throw new Error('no Chrome/Edge found; set BROWSER_PATH')
let failed = 0
const ok = (c, m) => { console.log(`${c ? 'PASS' : 'FAIL'} ${m}`); if (!c) failed++ }
const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
page.setDefaultNavigationTimeout(150000)
const errors = [], bad = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('response', (r) => {
  if (!r.url().includes('/api/')) return
  if (r.status() >= 400 || !(r.headers()['content-type'] || '').includes('json')) bad.push(`${r.status()} ${r.url()}`)
})
const T = (id) => `[data-testid="${id}"]`
const text = async (sel) => (await page.textContent(sel).catch(() => '')) || ''
const toClient = async ([x, y]) => { const b = await page.locator(T('draw-canvas')).boundingBox(); return [b.x + (x / 1000) * b.width, b.y + (y / 700) * b.height] }
async function drawStroke(pts) {
  const cs = []
  for (const p of pts) cs.push(await toClient(p))
  await page.mouse.move(...cs[0]); await page.mouse.down()
  for (let i = 1; i < cs.length; i++) await page.mouse.move(cs[i][0], cs[i][1], { steps: 5 })
  await page.mouse.up()
}
const G = 620
const figure = { torso: [[480, G - 256 - 120], [520, G - 256 - 120], [520, G - 256], [480, G - 256], [480, G - 256 - 120]], leg: [[500, G - 256], [500, G - 136], [500, G - 16]], foot: [[490, G - 16], [564, G - 16]] }
const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

try {
  // --- draw with the freehand pens
  await page.goto(`${BASE}/?tab=sketch`)
  await page.waitForSelector(T('sketch-page'))
  await page.click(T('pen-torso')); await drawStroke(figure.torso)
  await page.click(T('pen-leg')); await drawStroke(figure.leg)
  await page.click(T('pen-foot')); await drawStroke(figure.foot)
  await page.waitForFunction(() => document.querySelector('[data-testid="outcome"]')?.getAttribute('data-outcome')?.startsWith('valid'), null, { timeout: 30000 })
  ok(await page.isVisible(T('use-creature-btn')) && !(await page.isDisabled(T('use-creature-btn'))), 'a valid drawing offers "Use this creature"')

  // --- hand over to the forge workspace
  await page.click(T('use-creature-btn'))
  await page.waitForSelector(T('forge-page'), { timeout: 30000 })
  await page.waitForSelector(T('creature-bar'), { timeout: 30000 })
  ok(/YOUR CREATURE/.test(await text(T('forge-banner'))) && /LIVE MuJoCo/.test(await text(T('forge-banner'))), 'the provenance banner says YOUR CREATURE · LIVE MuJoCo')
  ok((await text(T('version-chip'))).trim() === 'v1', 'the version chip shows v1')
  ok((await text(T('creature-name'))).includes('My creature'), 'the creature keeps its name')
  ok(/creature=c-[0-9a-f]{8}/.test(page.url()) && /v=1/.test(page.url()), `the URL deep-links the creature (${page.url().split('?')[1]})`)
  ok(await page.isVisible(T('run-empty')), 'before a run, the page says there is no run yet instead of showing old data')

  // --- Push challenge
  await page.click(T('kind-push'))
  ok((await page.inputValue(T('target-force'))) === '10', 'push shows the default target force of 10 N')
  ok(/weakest direction/.test(await text(T('kind-explain'))), 'push explains the score is the weakest direction')
  await page.click(T('run-challenge'))
  await page.waitForSelector(`${T('run-progress')}, ${T('run-result')}, ${T('run-failed')}`, { timeout: 60000 })
  await page.waitForSelector(`${T('run-result')}, ${T('run-failed')}`, { timeout: 420000 })
  const jobFailed = await page.isVisible(T('run-failed'))
  if (jobFailed) {
    const msg = (await text(T('run-failed-message'))).trim()
    ok(await page.getAttribute(`${T('run-failed')} ${T('run-outcome')}`, 'data-outcome') === 'ERROR' && msg.length > 0, `the failed job is shown honestly as ERROR with its message (${msg.slice(0, 80)})`)
  } else {
    const outcome = await page.getAttribute(T('run-outcome'), 'data-outcome')
    ok(['PASS', 'POOR', 'FAIL', 'ERROR'].includes(outcome), `a real outcome badge is shown (${outcome})`)
    ok(/seeds passed|could be run/.test(await text(T('run-headline'))), `a plain-language result line is shown (${(await text(T('run-headline'))).slice(0, 90)})`)
    ok((await page.locator(T('seed-btn')).count()) >= 4, 'the per-seed strip lists the seeds')
    if (outcome !== 'ERROR') {
      await page.waitForSelector(`${T('replay')} canvas`, { timeout: 120000 })
      ok(true, 'a real MuJoCo replay of a seed is drawn in the viewer')
      ok(await page.isVisible('.transport'), 'the shared transport controls the replay')
      const first = await page.locator(T('seed-btn')).first().getAttribute('data-outcome')
      await page.locator(T('seed-btn')).last().click()
      await page.waitForSelector(`${T('replay')} canvas`, { timeout: 120000 })
      ok(true, `clicking another seed loads its replay (first seed ${first})`)
    }
    if (SHOT) await page.screenshot({ path: `${SHOT}/forge-1920.png`, fullPage: true })

    // --- investigation: the live button is gated by the server, the scripted mock runs the whole pipeline (no model is ever called here)
    const status = await page.evaluate(() => fetch('/api/forge/status').then((r) => r.json()))
    if (!status.live_available) {
      ok(await page.isDisabled(T('investigate-btn')) && /Live model calls are off/.test(await text(T('live-hint'))), 'live investigation is disabled with the reason shown (live calls are off on this server)')
    } else {
      ok(!(await page.isDisabled(T('investigate-btn'))), 'live investigation is enabled when the server allows it (not clicked here)')
    }
    ok(await page.isVisible(T('loop-checkbox')) && /3 rounds/.test(await text(T('loop-option'))) && /never accepts for you/.test(await text(T('loop-option'))), 'the keep-investigating option states its limits and that it never accepts')
    ok(await page.isVisible(T('probes-checkbox')), 'the "Run diagnostic probes first" option is offered')
    await page.check(T('probes-checkbox'))
    await page.click(T('investigate-mock-btn'))
    await page.waitForSelector(T('inv-progress'), { timeout: 60000 })
    ok(await page.isVisible(T('inv-stages')), 'live progress shows the six stages')
    await page.waitForSelector(`${T('investigation-record')}, ${T('investigation-failed')}, ${T('investigation-error')}`, { timeout: 900000 })
    ok(await page.isVisible(T('investigation-record')), 'the scripted investigation finished and its record is shown')
    const recStatus = await page.getAttribute(T('investigation-record'), 'data-status')
    ok(/SCRIPTED MOCK/.test(await text(T('inv-provenance'))), 'the provenance banner says SCRIPTED MOCK')
    const chipLabels = await page.locator(`${T('investigation-record')} ${T('prov-chip')}`).allTextContents()
    ok(chipLabels.length > 0 && !chipLabels.some((c) => /NEMOTRON/.test(c)), `no arm is labelled NEMOTRON in a scripted record (${[...new Set(chipLabels)].join(', ')})`)
    ok(/Budget used: .*rollouts/.test(await text(T('budget-line'))), 'the budget line shows the recorded rollouts')
    if (recStatus === 'done') {
      ok(await page.isVisible(T('model-call')), 'the model call card is shown')
      const probeRows = await page.locator(T('probe-row')).count()
      if (probeRows > 0) {
        const verdicts = await page.locator(T('probe-row')).evaluateAll((els) => els.map((e) => e.getAttribute('data-verdict')))
        ok(verdicts.every((v) => ['CONFIRMED', 'REFUTED', 'NOT EVALUATED'].includes(v)), `each probe shows CONFIRMED / REFUTED / NOT EVALUATED (${verdicts.join(', ')})`)
      } else {
        console.log('INFO the scripted record carries no probe rows (probes skipped or not requested by the fixture)')
      }
      ok((await page.locator('[data-step="proposals"] [data-status]').count()) >= 1, 'proposals are listed as accepted or rejected')
      ok((await page.locator(`${T('arms-table')} tbody tr`).count()) >= 2, 'the arms table lists the original and the candidates')
      ok(await page.isVisible(T('verdict-ai')), 'the AI-arm verdict is shown')
      ok(await page.isVisible(T('verdict-twin')), 'its matched random twin is shown next to it')
      const vt = await text(T('verdict-ai'))
      ok(/held-out seeds|No measurable effect|Inconclusive/.test(vt) && !/significan/i.test(vt), `the verdict uses held-out-seed wording (${vt.replace(/\s+/g, ' ').slice(0, 110)})`)
      await page.waitForSelector(`${T('arena-viewports')} canvas`, { timeout: 180000 })
      ok(true, 'the original and the selected arm replay side by side on a held-out seed')
      if (await page.isVisible(T('arena-twin-toggle'))) {
        await page.check(T('arena-twin-toggle'))
        await page.waitForSelector('.fg-pair-3 canvas', { timeout: 180000 })
        ok(true, 'the matched twin can be added as a third synchronized replay')
      }
      const armStatus = await page.getAttribute(T('verdict-ai'), 'data-status')
      const accBtn = T('accept-btn')
      await page.waitForSelector(accBtn)
      if (await page.getAttribute(T('accept-panel'), 'data-can-accept') === 'true') {
        ok(!(await page.isDisabled(accBtn)), `a verified arm can be accepted (${armStatus})`)
        await page.click(accBtn)
        await page.waitForSelector(T('lineage-v2'), { timeout: 60000 })
        ok((await text(T('version-chip'))).trim() === 'v2', 'after accepting, the version chip shows v2')
        const lin = await text(T('lineage-v2'))
        ok(/from v1/.test(lin) && /Scripted mock/.test(lin) && /verified/.test(lin), `the lineage shows parent, source, edits and verdict (${lin.replace(/\s+/g, ' ').slice(0, 120)})`)
        ok(await page.isVisible(T('challenge-new-version')), 'the page offers "Challenge v2"')
        await page.click(T('challenge-new-version'))
        await page.waitForSelector(`${T('run-result')}, ${T('run-failed')}`, { timeout: 420000 })
        ok(await page.isVisible(T('run-result')), 'v2 was challenged in MuJoCo')
      } else {
        ok(await page.isDisabled(accBtn), `accept is disabled because the arm is not a verified improvement (${armStatus})`)
        ok(/Only a verified improvement can be accepted|nothing to accept/.test(await text(T('accept-blocked'))), 'the refusal says why: only a verified improvement can be accepted')
      }
    } else {
      ok(await page.isVisible(T('model-failure')), `a scripted record that did not complete shows an honest failure (${recStatus})`)
    }
    await page.waitForSelector(`${T('investigation-item')}`, { timeout: 30000 })
    ok((await page.locator(`${T('investigation-list')} ${T('prov-chip')}`).allTextContents()).some((c) => /SCRIPTED MOCK/.test(c)), 'the investigations list shows the run with a SCRIPTED MOCK chip')
    if (SHOT) await page.screenshot({ path: `${SHOT}/forge-investigation-1920.png`, fullPage: true })
  }

  // --- reload keeps the creature and the run
  const url = page.url()
  const chipBefore = (await text(T('version-chip'))).trim()
  await page.reload(); await page.waitForSelector(T('creature-bar'), { timeout: 30000 })
  ok((await text(T('version-chip'))).trim() === chipBefore, `after a reload the same creature and version are still on the bench (${chipBefore})`)
  ok(page.url().includes('creature=') && page.url().includes(`v=${chipBefore.slice(1)}`), 'the deep link survives a reload')
  if (!jobFailed) {
    await page.waitForSelector(T('run-result'), { timeout: 60000 })
    ok(page.url() === url, 'the run id is in the link, so the stored result reopens after a reload')
  }

  // --- phone width
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForFunction(() => window.innerWidth === 390)
  ok((await overflow()) <= 1, `no horizontal page overflow at 390 px (${await overflow()}px)`)
  if (SHOT) await page.screenshot({ path: `${SHOT}/forge-390.png`, fullPage: true })
  if (!jobFailed) {
    await page.locator(T('investigation-item')).first().click()
    await page.waitForSelector(T('investigation-record'), { timeout: 60000 })
    ok((await overflow()) <= 1, `no horizontal overflow at 390 px with an investigation open (${await overflow()}px)`)
    if (SHOT) await page.screenshot({ path: `${SHOT}/forge-investigation-390.png`, fullPage: true })
  }

  ok(bad.length === 0, `every API response is JSON and < 400${bad.length ? ': ' + bad.join(' | ') : ''}`)
  ok(errors.length === 0, `no console or page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} catch (e) { ok(false, `flow threw: ${e.message}`) }
await browser.close()
process.exit(failed ? 1 : 0)
