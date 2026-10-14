// Real-browser flow for the AI investigation: provenance, the five steps, synchronized before/after simulations, parameter changes,
// outcome graphics, honest verdict wording, the rejected-reply and scripted-mock runs, advanced evidence, and the 390 px layout.
// Uses only bundled records: no model call, no live budget is spent.
// Usage: BASE_URL=http://127.0.0.1:8000 node e2e/demo-flow.mjs   (SHOT_DIR optional)
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
const errors = []
const api = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('response', (r) => { if (r.url().includes('/api/demo/')) api.push({ url: r.url(), status: r.status() }) })
const T = (id) => `[data-testid="${id}"]`
const text = async (sel) => (await page.textContent(sel).catch(() => '')) || ''
const ready = () => page.waitForSelector(`${T('demo-replay')} canvas`, { timeout: 240000 })

try {
  await page.goto(`${BASE}/?tab=demo`)
  await page.waitForSelector(T('investigation'), { timeout: 60000 })
  const chips = await page.$$eval('.run-chip .kind-chip', (e) => e.map((x) => x.textContent))
  ok(chips.includes('RECORDED LIVE') && chips.includes('SCRIPTED MOCK') && !chips.includes('LIVE'), 'recorded and scripted runs are labelled; nothing bundled claims to be LIVE')
  ok((await page.getAttribute(T('kind-banner'), 'data-kind')) === 'RECORDED_LIVE', 'the default run is a recorded live call, with its provenance visible')
  ok(/Nothing is re-sent/.test(await text(T('kind-banner'))), 'the provenance label says nothing is re-sent to the model')
  ok(/Live mode is off/.test(await text(T('live-disabled'))) && (await page.isDisabled(T('run-live'))), 'live inference is off, explained, and its button disabled by default')

  // step 1: the failure, two real simulations
  await ready()
  ok((await page.$$(`${T('demo-replay')} canvas`)).length === 2, 'two large synchronized simulations are the centrepiece')
  ok(/falls at/.test(await text(T('result-0'))) && /walks/.test(await text(T('result-1'))), 'the failure: the same controller falls on one start and walks on another')
  ok(/Seed 9101/.test(await text(T('inspect-failure'))), 'the inspector states the measured failure')
  if (SHOT) await page.screenshot({ path: `${SHOT}/inv-1-failure.png` })

  // step 2: evidence
  await page.click(T('step-evidence'))
  ok(/Measurements only/i.test(await text(T('inspect-evidence'))) && /controller parameters/.test(await text(T('inspect-evidence'))), 'evidence: says the model received measurements only')
  ok((await page.$$('.cites code')).length >= 1, 'evidence: the values the model cited are listed')

  // step 3: proposal and parameter changes
  await page.click(T('step-proposal')); await ready()
  ok(/Model-written/i.test(await text(T('story-claim'))), 'the model claim is shown and marked as model-written')
  const changed = await page.$$eval('[data-testid^="ptrack-"][data-changed="true"]', (e) => e.map((x) => x.getAttribute('data-testid')))
  ok(changed.length >= 1, `the changed parameters are visualised on their allowed ranges (${changed.join(', ')})`)
  await page.waitForFunction(() => [...document.querySelectorAll('.vp-label')].some((e) => /Nemotron/.test(e.textContent || '')), null, { timeout: 120000 })
  const titles = await page.$$eval('.vp-label', (e) => e.map((x) => x.textContent))
  ok(titles.some((t) => /Unchanged/.test(t)), 'the stage compares the unchanged controller with the edited one')
  await page.click(T('slot-1')); await page.waitForTimeout(500)
  ok((await page.$$('[data-testid^="ptrack-"][data-changed="true"]')).length >= 1, 'you can move between proposals')
  await page.click(T('slot-0'))

  // step 4: verification graphics, matched random edit
  await page.click(T('step-verification'))
  ok((await page.$$('[data-testid^="outcome-"]')).length === 3, 'outcome graphics: unchanged, AI-edited and matched-random controllers')
  ok((await page.$$('.strip i')).length === 96, 'every verification seed is drawn for the three controllers (3 x 32)')
  await page.click(T('arm-random'))
  await page.waitForFunction(() => [...document.querySelectorAll('.vp-label')].some((e) => /random edit/.test(e.textContent || '')), null, { timeout: 240000 })
  ok(true, 'the stage can show the matched random edit instead')
  await page.click(T('arm-model'))
  if (SHOT) await page.screenshot({ path: `${SHOT}/inv-4-verification.png` })

  // step 5: verdict, honest wording
  await page.click(T('step-verdict'))
  const verdict = await text(T('story-verdict'))
  ok(/random edit/.test(verdict) && /not a statistical comparison/.test(verdict) && /classical optimiser/.test(verdict), 'verdict: names the random baseline, says it is not a statistical comparison, separates the classical result')
  ok(!/outperform|beats random edits|better than random/i.test(verdict.replace(/not[^.]*\./gi, '')), 'verdict never claims the model beats random edits')
  ok(/not available/.test(await text(T('inspect-verdict'))), 'it is honest that an investigation on a drawn creature does not exist')
  if (SHOT) await page.screenshot({ path: `${SHOT}/inv-5-verdict.png` })

  // advanced evidence on demand
  await page.click(`${T('advanced')} summary`)
  ok(/Observed failure/.test(await text(T('advanced'))), 'advanced: the full step-by-step evidence is available on demand')
  await page.click(`${T('advanced')} button[data-step="proposal"]`)
  await page.click('summary:has-text("Raw reply exactly as received")')
  ok(((await text(T('demo-raw'))) || '').length > 2, 'advanced: the raw model reply is shown exactly as received')

  // the recorded run whose reply was rejected
  await page.locator('.run-chip', { hasText: 'reply rejected' }).first().click()
  await page.waitForSelector(T('investigation'))
  ok(await page.isDisabled(T('step-verification')) && await page.isDisabled(T('step-verdict')), 'a rejected reply cannot be "verified": those steps are disabled')
  await page.click(T('step-proposal'))
  ok(/Nothing was simulated or substituted/.test(await text(T('story-noproposal'))), 'the stop is explained: nothing was simulated or substituted')

  // scripted mock
  await page.locator('.run-chip', { hasText: 'Scripted mock' }).first().click()
  await page.waitForFunction(() => document.querySelector('[data-testid="kind-banner"]')?.getAttribute('data-kind') === 'SCRIPTED_MOCK')
  ok(/not Nemotron/.test(await text(T('kind-banner'))), 'the scripted mock says it is not Nemotron')
  await page.click(T('step-proposal'))
  ok(/not Nemotron/.test(await text(T('story-claim'))), 'the scripted claim is itself tagged "not Nemotron"')

  // phone width
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`${BASE}/?tab=demo`); await page.waitForSelector(T('investigation'))
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  ok(over <= 1, `no horizontal page overflow at 390 px (${over}px)`)
  const badApi = api.filter((a) => a.status >= 400)
  ok(badApi.length === 0, `no failed demo API calls${badApi.length ? ': ' + badApi.map((a) => a.status + ' ' + a.url).join(' | ') : ''}`)
  ok(errors.length === 0, `no console or page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} catch (e) { ok(false, `flow threw: ${e.message}`) }
await browser.close()
process.exit(failed ? 1 : 0)
