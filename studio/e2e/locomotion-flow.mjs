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
page.setDefaultNavigationTimeout(150000)
const pageErrors = []
page.on('pageerror', (e) => pageErrors.push(e.message))

try {
  await page.goto(`${BASE}/?tab=locomotion`)
  // Walking lab leads with the robots: two synchronized replays, the one-line result, then the numbers
  await page.waitForSelector('[data-testid="wl-replay"] canvas', { timeout: 120000 })
  ok((await page.$$('[data-testid="wl-replay"] canvas')).length === 2, 'the Walking lab shows the starting and the improved robot side by side')
  const nums = ((await page.textContent('[data-testid="wl-numbers"]')) || '').replace(/\s+/g, ' ')
  ok(nums.includes('91') && nums.includes('150'), `the result is stated before any table (${nums})`)
  ok(/falls at/.test((await page.textContent('[data-testid="wl-result-0"]')) || '') && /walks/.test((await page.textContent('[data-testid="wl-result-1"]')) || ''), 'on the featured start the old controller falls and the improved one walks (measured now)')
  ok(/No language model/.test((await page.textContent('[data-testid="wl-attribution"]')) || ''), 'the improvement is attributed to a classical optimiser')
  ok(/fresh MuJoCo run on this computer/.test((await page.textContent('[data-testid="wl-provenance"]')) || ''), 'the committed record and the local replay are kept distinct')
  const dots = await page.$$('.seed-dots .dots button')
  ok(dots.length === 300, 'every test start is a clickable dot')
  await dots[7].click()
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="wl-replay"] canvas').length === 2, null, { timeout: 300000 })
  if (SHOT) await page.screenshot({ path: `${SHOT}/walking-lab.png` })
  await page.click('[data-testid="walking-advanced"] summary')
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

  // changing controller or seed must invalidate the loaded simulation
  await page.selectOption('select[aria-label="controller"]', 'random_search')
  await page.click('[data-testid="load-loco-replay"]')
  await page.waitForSelector('[data-testid="loco-verdict"]', { timeout: 120000 })
  await page.selectOption('select[aria-label="seed"]', '3001')
  ok((await page.$('[data-testid="loco-verdict"]')) === null, 'changing the seed clears the previously loaded replay')
  await page.click('[data-testid="load-loco-replay"]')
  await page.waitForSelector('[data-testid="loco-verdict"]', { timeout: 120000 })
  await page.selectOption('select[aria-label="controller"]', 'standing')
  ok((await page.$('[data-testid="loco-verdict"]')) === null, 'changing the controller clears the previously loaded replay')

  // a slow earlier request must not overwrite a newer selection
  let held = null
  await page.route('**/api/locomotion/replay**', async (route) => {
    if (route.request().url().includes('seed=3002')) { held = route; return } // hold the first request open
    await route.continue()
  })
  await page.selectOption('select[aria-label="controller"]', 'random_search')
  await page.selectOption('select[aria-label="seed"]', '3002')
  await page.click('[data-testid="load-loco-replay"]')
  await page.waitForFunction(() => true)
  for (let i = 0; i < 50 && !held; i++) await page.waitForTimeout(100)
  ok(held !== null, 'first replay request is in flight')
  await page.selectOption('select[aria-label="seed"]', '3003') // newer selection while the old request is pending
  await held.continue() // the stale response now arrives
  await page.waitForTimeout(4000)
  ok((await page.$('[data-testid="loco-verdict"]')) === null, 'a stale response does not display a replay for the superseded selection')
  ok(await page.isEnabled('[data-testid="load-loco-replay"]'), 'load button is usable again after the selection changed')
  await page.unroute('**/api/locomotion/replay**')

  // phone widths: no horizontal page scroll; wide tables scroll inside their own container.
  // 360 and 320 px are stricter than 390 and expose font-dependent overflow even where the CI font is narrower.
  for (const w of [390, 360, 320]) {
    await page.setViewportSize({ width: w, height: 900 })
    const m = await page.evaluate((w) => {
      const d = document.documentElement
      const wide = [...document.querySelectorAll('body *')].filter((e) => !e.closest('.table-scroll') && e.getBoundingClientRect().right > w + 1)
        .slice(0, 5).map((e) => `${e.tagName}.${e.className?.baseVal ?? e.className}@${Math.round(e.getBoundingClientRect().right)}`)
      return { overflow: d.scrollWidth - d.clientWidth, wide }
    }, w)
    ok(m.overflow <= 1, `no horizontal page overflow at ${w}px (${m.overflow}px; offenders outside scroll containers: ${m.wide.join(', ') || 'none'})`)
  }
  const scrolls = await page.$$eval('.table-scroll', (els) => els.map((e) => e.scrollWidth > e.clientWidth))
  ok(scrolls.some(Boolean), 'at 320 px a wide table scrolls inside its own container instead of the page')

  ok(pageErrors.length === 0, `no page errors (${pageErrors.join(' | ')})`)
} catch (e) {
  console.log('FAIL', e.message)
  failed++
} finally {
  await browser.close()
}
process.exit(failed ? 1 : 0)
