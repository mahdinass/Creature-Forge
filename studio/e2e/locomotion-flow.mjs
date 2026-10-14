// Real-browser flow for the Phase 2A Locomotion tab. Needs a running Studio server (BASE_URL) with the built frontend.
// Usage: BASE_URL=http://127.0.0.1:8000 node e2e/locomotion-flow.mjs   (set SHOT_DIR to save screenshots)
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync } from 'node:fs'

const BASE = process.env.BASE_URL
if (!BASE) throw new Error('BASE_URL is required')
const SHOT = process.env.SHOT_DIR
if (SHOT) mkdirSync(SHOT, { recursive: true })

const CANDIDATES = [
  process.env.BROWSER_PATH,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser',
].filter(Boolean)
const exe = CANDIDATES.find((p) => existsSync(p))
if (!exe) throw new Error('no Chrome/Edge found; set BROWSER_PATH')

let failed = 0
const ok = (cond, msg) => {
  console.log(`${cond ? 'PASS' : 'FAIL'} ${msg}`)
  if (!cond) failed++
}
const shot = async (page, name) => { if (SHOT) await page.screenshot({ path: `${SHOT}/${name}.png`, fullPage: true }) }

const browser = await chromium.launch({
  executablePath: exe, headless: true,
  args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1360, height: 1100 } })
const pageErrors = []
page.on('pageerror', (e) => pageErrors.push(e.message))

try {
  await page.goto(`${BASE}/?tab=locomotion`)
  await page.waitForSelector('[data-testid="heldout-table"]')
  ok((await page.$$('.loco-chart polyline')).length === 2, 'progress chart draws both optimiser curves')
  const rows = await page.$$eval('[data-testid="heldout-table"] tbody tr', (r) => r.map((x) => x.textContent))
  ok(rows.length === 5, `held-out table lists 3 baselines + 2 learned controllers (${rows.length})`)
  const rs = rows.find((r) => r.startsWith('Random search'))
  ok(rs && rs.includes('70%') && rs.includes('partial'), 'random-search row shows 70% walking and the partial verdict, not a success claim')
  ok(!rows.some((r) => r.includes('meets walking criteria')), 'no controller is labelled as meeting the walking criteria')

  await page.click('[data-testid="load-loco-replay"]')
  await page.waitForSelector('[data-testid="loco-verdict"]', { timeout: 120000 })
  await page.waitForSelector('canvas')
  const verdict = await page.textContent('[data-testid="loco-verdict"]')
  ok(/walking|fall/.test(verdict), 'replay shows a measured gait verdict')
  ok(verdict.includes('valid alternating steps'), 'replay lists measured step metrics')
  ok((await page.$$('canvas')).length >= 1, 'replay renders in the 3D viewport')
  await page.click('button:has-text("Pause")').catch(() => {}) // stop the render loop before capturing
  await shot(page, 'locomotion')

  // a standing replay must be classified as stationary, not walking
  await page.selectOption('select[aria-label="controller"]', 'standing')
  await page.click('[data-testid="load-loco-replay"]')
  await page.waitForFunction(() => document.querySelector('[data-testid="loco-verdict"]')?.textContent?.includes('stationary'),
    null, { timeout: 120000 })
  ok(true, 'standing controller replay is classified stationary')

  // phone width: no horizontal page scroll
  await page.setViewportSize({ width: 390, height: 900 })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  ok(overflow <= 1, `no horizontal page overflow at phone width (${overflow}px)`)

  ok(pageErrors.length === 0, `no page errors (${pageErrors.join(' | ')})`)
} catch (e) {
  console.log('FAIL', e.message)
  failed++
} finally {
  await browser.close()
}
process.exit(failed ? 1 : 0)
