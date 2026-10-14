// Real-browser flow for the Overview landing page: the story and the two separate lines of evidence, with honest wording.
// Usage: BASE_URL=http://127.0.0.1:8000 node e2e/overview-flow.mjs   (set SHOT_DIR to save screenshots)
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
const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } })
const pageErrors = []
page.on('pageerror', (e) => pageErrors.push(e.message))
const bad = []
page.on('response', (r) => { if (r.url().includes('/api/') && r.status() >= 400) bad.push(`${r.status()} ${r.url()}`) })

try {
  await page.goto(`${BASE}/`)
  await page.waitForSelector('[data-testid="overview"]', { timeout: 30000 })
  ok(true, 'the landing page is Home')
  const h1 = ((await page.textContent('h1')) || '').replace(/\s+/g, ' ')
  ok(/Create\.\s*Simulate\.\s*Investigate\./.test(h1), `the headline is "Create. Simulate. Investigate." (${h1})`)
  await page.waitForSelector('[data-testid="hero-stage"] canvas', { timeout: 120000 })
  ok(true, 'the hero is a real MuJoCo replay rendered in WebGL')
  await page.waitForFunction(() => /walks the full/.test(document.querySelector('[data-testid="hero-caption"]')?.textContent || ''), null, { timeout: 60000 })
  ok(true, 'the hero shows the improved controller walking the full 10 s')
  await page.click('[data-testid="hero-start"]')
  await page.waitForFunction(() => /falls at/.test(document.querySelector('[data-testid="hero-caption"]')?.textContent || ''), null, { timeout: 60000 })
  ok(true, 'the hero can switch to the starting controller, which falls')
  ok((await page.$$('[data-testid="seed-dots"] .dots i')).length === 300, 'every one of the 150 test starts is drawn for both controllers (300 dots)')
  const nemText = (await page.textContent('[data-testid="nemotron-preview"]')) || ''
  ok(/not that the model beats random edits/.test(nemText) && /Recorded real Nemotron call/.test(nemText), 'the AI preview is labelled as a recorded call and states it does not beat random edits')
  ok(((await page.textContent('[data-testid="r2-band"]')) || '').includes('not from an AI model'), 'the walking result is attributed to a classical optimiser, not an AI model')
  await page.click('[data-testid="research-details"] summary')
  await page.waitForSelector('[data-testid="overview-research"]')
  ok((await page.$$('[data-testid="pipeline"] li')).length === 5, 'the five-step story is shown: failure, evidence, Nemotron proposes, MuJoCo tests, replay and verdict')
  const classical = (await page.textContent('[data-testid="card-classical"]')) || ''
  ok(classical.includes('150/150') && classical.includes('91/150'), 'the classical card reports 150/150 vs 91/150 read from the records')
  ok(classical.toLowerCase().includes('no language model'), 'the classical result is explicitly not attributed to the language model')
  ok(classical.includes('not “100%”'), 'the exact interval is shown instead of claiming 100%')
  const nem = (await page.textContent('[data-testid="card-nemotron"]')) || ''
  ok(/not a superiority claim/i.test(nem), 'the Nemotron card says it is not a superiority claim')
  ok(nem.includes('matched random edit reached'), 'proposals are shown against matched random edits')
  ok(((await page.textContent('[data-testid="r3-status"]')) || '').includes('not completed'), 'the unfinished systematic comparison is stated plainly')
  const whole = (await page.textContent('[data-testid="overview"]')) || ''
  ok(!/outperform|better than random|beats random/i.test(whole.replace(/not (a )?claim|does not show[^.]*\.|not that the model [^.;]*/gi, '')), 'no sentence claims the model outperforms random edits')
  ok(((await page.textContent('[data-testid="limits"]')) || '').includes('classical optimisation, not from the language model'), 'the limits box repeats the attribution')

  await page.click('[data-testid="cta-ai"]')
  await page.waitForSelector('[data-testid="investigation"]', { timeout: 30000 })
  ok(true, 'Watch an AI investigation opens the investigation')
  await page.goto(`${BASE}/`)
  await page.waitForSelector('[data-testid="overview"]')
  await page.click('[data-testid="cta-walking"]')
  await page.waitForSelector('[data-testid="walking-lab"]', { timeout: 30000 })
  ok(true, 'the walking summary opens the Walking lab')
  await page.goto(`${BASE}/`)
  await page.click('[data-testid="cta-draw"]')
  await page.waitForSelector('[data-testid="sketch-page"]', { timeout: 30000 })
  ok(true, 'Draw a creature opens the drawing canvas')

  await page.goto(`${BASE}/`)
  await page.waitForSelector('[data-testid="overview"]')
  await page.setViewportSize({ width: 390, height: 900 })
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  ok(over <= 1, `no horizontal page overflow at 390 px (${over}px)`)
  if (SHOT) await page.screenshot({ path: `${SHOT}/overview-mobile.png`, fullPage: true })
  await page.setViewportSize({ width: 1360, height: 1000 })
  if (SHOT) await page.screenshot({ path: `${SHOT}/overview.png`, fullPage: true })
} catch (e) {
  console.log('FAIL flow error:', e.message)
  failed++
} finally {
  ok(bad.length === 0, `no API errors (${bad.join(' | ')})`)
  ok(pageErrors.length === 0, `no page errors (${pageErrors.join(' | ')})`)
  await browser.close()
}
process.exit(failed ? 1 : 0)
