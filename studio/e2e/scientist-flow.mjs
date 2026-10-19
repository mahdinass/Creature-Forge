// Real-browser flow for the AI scientist page (Stage-2 recorded investigations). Needs a running Studio server (BASE_URL) with the
// built frontend and the committed records in experiments/causal_engineer/dev/scientist_records.
// Usage: BASE_URL=http://127.0.0.1:8000 node e2e/scientist-flow.mjs   (set SHOT_DIR to save screenshots)
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
const ok = (cond, msg) => { console.log(`${cond ? 'PASS' : 'FAIL'} ${msg}`); if (!cond) failed++ }
const shot = async (page, name) => { if (SHOT) await page.screenshot({ path: `${SHOT}/${name}.png`, fullPage: true }) }

const browser = await chromium.launch({
  executablePath: exe, headless: true,
  args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } })
page.setDefaultNavigationTimeout(150000)
const pageErrors = []
page.on('pageerror', (e) => pageErrors.push(e.message))
try {
  await page.goto(`${BASE}/?tab=scientist`)
  await page.waitForSelector('[data-testid="scientist-lab"]')
  const cards = await page.$$('[data-testid^="sc-card-"]')
  ok(cards.length >= 1, `recorded investigations are listed (${cards.length})`)
  await page.waitForSelector('[data-testid="sc-record"]')
  ok(/Nemotron|engine alone/.test((await page.textContent('[data-testid="sc-headline"]')) || ''), 'the headline says who decided')
  const steps = await page.$$('[data-testid^="sc-step-"]')
  ok(steps.length >= 3, `the decision timeline has steps (${steps.length})`)
  ok((await page.$$('[data-testid="sc-words"]')).length >= 1, "Nemotron's own reasoning is shown")
  ok((await page.$('[data-testid="sc-belief"]')) !== null, 'the belief-over-time panel renders')
  ok((await page.$('[data-testid="sc-eval"]')) !== null, 'evaluation-only ground truth is separated')
  await page.waitForSelector('[data-testid="cz-duo"]', { timeout: 150000 })
  ok((await page.$$('[data-testid="cz-duo"] canvas')).length >= 1, 'the replay of the faulty and the submitted design renders')
  await shot(page, 'scientist')
  if (cards.length > 1) {
    await cards[1].click()
    await page.waitForSelector('[data-testid="sc-record"]')
    ok((await page.$$('[data-testid^="sc-step-"]')).length >= 1, 'a second record opens')
  }
  ok(pageErrors.length === 0, `no page errors (${pageErrors.join(' | ')})`)
} finally {
  await browser.close()
}
console.log(failed ? `${failed} FAILED` : 'ALL PASSED')
process.exit(failed ? 1 : 0)
