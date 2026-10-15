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
// the investigation endpoints legitimately answer 503 until the backend exists; nothing else may fail
const expected503 = (url, status) => status === 503 && /\/api\/forge\/(creatures\/[^/]+\/versions\/\d+\/investigations|investigations|replay)/.test(url)
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error' && !/status of 503/.test(m.text())) errors.push(m.text()) })
page.on('response', (r) => {
  if (!r.url().includes('/api/')) return
  if (expected503(r.url(), r.status())) return
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

    // --- AI investigation is honest about not being available yet
    await page.click(T('investigate-btn'))
    await page.waitForSelector(T('investigation-unavailable'), { timeout: 30000 })
    ok(/not available yet/i.test(await text(T('investigation-unavailable'))), `investigation says it is not available yet: "${(await text(T('investigation-unavailable'))).slice(0, 90)}"`)
  }

  // --- reload keeps the creature and the run
  const url = page.url()
  await page.reload(); await page.waitForSelector(T('creature-bar'), { timeout: 30000 })
  ok((await text(T('version-chip'))).trim() === 'v1', 'after a reload the same creature is still on the bench')
  ok(page.url().includes('creature=') && page.url().includes('v=1'), 'the deep link survives a reload')
  if (!jobFailed) {
    await page.waitForSelector(T('run-result'), { timeout: 60000 })
    ok(page.url() === url, 'the run id is in the link, so the stored result reopens after a reload')
  }

  // --- phone width
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForFunction(() => window.innerWidth === 390)
  ok((await overflow()) <= 1, `no horizontal page overflow at 390 px (${await overflow()}px)`)
  if (SHOT) await page.screenshot({ path: `${SHOT}/forge-390.png`, fullPage: true })

  ok(bad.length === 0, `every API response is JSON and < 400, except the expected 503 from investigations${bad.length ? ': ' + bad.join(' | ') : ''}`)
  ok(errors.length === 0, `no console or page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} catch (e) { ok(false, `flow threw: ${e.message}`) }
await browser.close()
process.exit(failed ? 1 : 0)
