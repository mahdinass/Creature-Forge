// Real-browser flow for the AI Investigation demo tab. Needs a running Studio server (BASE_URL) with the built frontend.
// Uses only bundled records (a recorded live call and a labelled scripted mock): no model call, no live budget is spent.
// Usage: BASE_URL=http://127.0.0.1:8000 node e2e/demo-flow.mjs   (set SHOT_DIR to save screenshots)
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync } from 'node:fs'

const BASE = process.env.BASE_URL || process.env.BASE
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
const ok = (cond, msg) => { console.log(`${cond ? 'PASS' : 'FAIL'} ${msg}`); if (!cond) failed++ }
const shot = async (page, name) => { if (SHOT) await page.screenshot({ path: `${SHOT}/${name}.png`, fullPage: true }) }

const browser = await chromium.launch({
  executablePath: exe, headless: true,
  args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1360, height: 1100 } })
const pageErrors = []
page.on('pageerror', (e) => pageErrors.push(e.message))

try {
  await page.goto(`${BASE}/?tab=demo`)
  await page.waitForSelector('[data-testid="demo"]')
  await page.waitForSelector('.trial-card')
  const chips = await page.$$eval('.trial-card[data-source="bundled-recording"] .kind-chip', (e) => e.map((x) => x.textContent))
  ok(chips.includes('RECORDED LIVE'), 'the run list shows a recorded live call')
  ok(chips.includes('SCRIPTED MOCK'), 'the scripted mock example is listed and labelled')
  ok(!chips.includes('LIVE'), 'no bundled recording is labelled LIVE (only a run made in the current session can be)')

  await page.waitForSelector('[data-testid="kind-banner"]')
  const kind0 = await page.getAttribute('[data-testid="kind-banner"]', 'data-kind')
  ok(kind0 === 'RECORDED_LIVE', `default selection is a recorded live run with a RECORDED_LIVE banner (${kind0})`)
  ok(((await page.textContent('[data-testid="kind-banner"]')) || '').includes('Nothing is re-sent'), 'the banner says nothing is re-sent to the model')
  ok(await page.isDisabled('[data-testid="run-live"]'), 'the live button is disabled (server flag off / not confirmed)')
  ok(((await page.textContent('[data-testid="live-disabled"]')) || '').includes('Live mode is off'), 'the page explains why live mode is off')
  ok(/seed 9101/.test((await page.textContent('[data-testid="demo-observed"]')) || ''), 'step 1 shows the measured failing seed')

  await page.click('button[data-step="prompt"]')
  ok(((await page.textContent('[data-testid="demo-context"]')) || '').includes('Exact context sent'), 'step 2 shows the exact context sent to the model')
  await page.click('button[data-step="proposal"]')
  await page.waitForSelector('[data-testid="demo-status"]')
  await page.click('summary:has-text("Raw reply exactly as received")')
  const raw = (await page.textContent('[data-testid="demo-raw"]')) || ''
  ok(raw.length > 2, 'step 3 shows the raw reply exactly as received')
  const dashed = await page.$$eval('.block-model', (e) => e.length)
  ok(dashed >= 1, 'model-written content is rendered in dashed "model" blocks')
  await shot(page, 'demo-recorded-proposal')

  // the recorded live run with valid proposals: verification table, matched random edits, synchronized replay
  await page.click('button[data-step="verify"]')
  await page.waitForSelector('[data-testid="demo-verify"]')
  const rows = await page.$$eval('[data-testid="demo-verify"] tbody tr', (r) => r.map((x) => x.textContent))
  ok(rows.length === 5, `verification lists the frozen controller, 2 proposals and 2 matched random edits (${rows.length})`)
  ok(rows.some((r) => r.includes('matched random')), 'every proposal is shown next to a matched random edit')
  ok(rows.every((r) => /\d+\/32/.test(r)), 'each row reports walking seeds out of 32')
  await shot(page, 'demo-verify')
  await page.click('button[data-step="replay"]')
  await page.click('[data-testid="demo-load-replay"]')
  await page.waitForSelector('[data-testid="demo-replay"]', { timeout: 240000 })
  await page.waitForSelector('canvas')
  ok((await page.$$('canvas')).length >= 2, 'two synchronized MuJoCo replays render side by side')
  const verdict = (await page.textContent('[data-testid="demo-verdict"]')) || ''
  ok(verdict.includes('One instance; not a statistical claim'), 'the verdict states it is one instance, not a statistical claim')
  ok(verdict.includes('matched random edit'), 'the verdict names the matched random baseline')
  await page.click('button:has-text("Pause")').catch(() => {})
  await shot(page, 'demo-replay')
  await page.selectOption('select[aria-label="seed"]', { index: 1 })
  ok((await page.$('[data-testid="demo-replay"]')) === null, 'changing the seed clears the loaded replay')

  // the recorded run whose reply was rejected: shown honestly, nothing simulated or substituted
  await page.locator('.trial-card', { hasText: 'reply rejected' }).first().click()
  await page.click('button[data-step="proposal"]')
  await page.waitForSelector('[data-testid="demo-slot-0"]')
  ok(((await page.textContent('[data-testid="demo-slot-0"]')) || '').includes('Rejected by schema validation'), 'an invalid proposal is shown as rejected, with the reason')
  ok(((await page.textContent('[data-testid="demo-status"]')) || '').includes('Nothing was simulated or substituted'), 'the page says nothing was simulated or substituted')
  await page.click('button[data-step="verify"]')
  await page.waitForSelector('[data-testid="demo-noverify"]')
  ok(true, 'no verification is shown for a run without a valid proposal')

  // the scripted mock example: labelled everywhere
  await page.locator('.trial-card', { hasText: 'SCRIPTED MOCK' }).first().click()
  await page.waitForFunction(() => document.querySelector('[data-testid="kind-banner"]')?.getAttribute('data-kind') === 'SCRIPTED_MOCK')
  ok(((await page.textContent('[data-testid="kind-banner"]')) || '').includes('not a model'), 'the mock banner says it is not a model')
  await page.click('button[data-step="proposal"]')
  ok(((await page.textContent('[data-testid="demo-slot-0"]')) || '').includes('SCRIPTED MOCK'), 'the mock proposal text itself says SCRIPTED MOCK')

  // phone width: no page-level horizontal overflow
  await page.setViewportSize({ width: 360, height: 900 })
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  ok(over <= 1, `no horizontal page overflow at 360 px (${over}px)`)
} catch (e) {
  console.log('FAIL flow error:', e.message)
  failed++
} finally {
  ok(pageErrors.length === 0, `no page errors (${pageErrors.join(' | ')})`)
  await browser.close()
}
process.exit(failed ? 1 : 0)
