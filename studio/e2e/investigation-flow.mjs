// Real-browser flow for the Investigation Lab. Needs a running Studio server (BASE_URL) with the built frontend.
// Usage: BASE_URL=http://127.0.0.1:8000 node e2e/investigation-flow.mjs   (set SHOT_DIR to save screenshots)
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

const REJECTED = '20261013T010325Z-9d9310'
const INVALID = '20261013T010405Z-9a3be8'
const CONTROL = '20261013T010249Z-ca2db8'

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
const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } })
const pageErrors = []
page.on('pageerror', (e) => pageErrors.push(e.message))

try {
  // ---- history ------------------------------------------------------------------------------------------
  await page.goto(`${BASE}/?tab=lab`)
  await page.waitForSelector('[data-testid="archive-groups"]')
  ok(/sorted by what happened/.test((await page.textContent('[data-testid="archive-purpose"]')) || ''), 'the archive states its purpose in one sentence')
    for (const g of ['verified', 'rejected', 'invalid', 'historical']) ok((await page.$(`[data-testid="group-${g}"]`)) !== null, `the archive has a "${g}" group`)
  if ((await page.getAttribute('[data-testid="group-verified"]', 'data-count')) === '0')
    ok(/no AI intervention is verified/.test((await page.textContent('[data-testid="group-verified-empty"]')) || ''), 'an empty verified group says plainly that no AI intervention is verified as an improvement')
  await page.waitForSelector('.trial-card')
  const statuses = await page.$$eval('.trial-card .chip', (els) => els.map((e) => e.getAttribute('data-status')))
  ok(statuses.length === 4, `history lists the 4 bundled real records (${statuses.length})`)
  ok(statuses.filter((s) => s === 'rejected_by_verifier').length === 3 && statuses.includes('invalid_model_output'),
    'rejected AND invalid experiments are both visible')
  ok(!statuses.includes('accepted'), 'no accepted AI trial is shown (none exists)')
  ok((await page.textContent('.ref-note')).includes('not an AI result'), 'manual 16 cm reference is labelled as not an AI result')
  await page.click('.filters button:has-text("Invalid / failed")')
  ok((await page.$$('.trial-card')).length === 1, 'outcome filter narrows the history')
  await page.click('.filters button:has-text("All")')

  // ---- select experiment -> inspect evidence ------------------------------------------------------------
  await page.click(`[data-testid="trial-${REJECTED}"]`)
  await page.waitForSelector('[data-testid="detail"]')
  ok((await page.textContent('[data-testid="headline"]')).includes('did not pass independent verification'),
    'rejected trial states plainly that verification failed')
  ok((await page.textContent('[data-testid="obs-fall-rate"]')) === '100%', 'observed fall rate comes from the saved MuJoCo evidence (100%)')
  const obsBadge = await page.textContent('[data-testid="observed-block"] .origin')
  ok(obsBadge.includes('Measured by MuJoCo'), 'observed facts are badged as measured by MuJoCo')
  ok((await page.textContent('[data-testid="step-observe"]')).includes('Peak foot slip speed'), 'forensic evidence is shown')
  await shot(page, '1-observe')

  // ---- hypothesis: model claims are distinct from facts -------------------------------------------------
  await page.click('[data-step="hypothesize"]')
  await page.waitForSelector('[data-testid="hypothesis-block"]')
  ok((await page.textContent('[data-testid="hypothesis-block"] .origin')).includes('Model-written'), 'hypothesis is badged as model-written and unverified')
  ok(await page.$eval('[data-testid="hypothesis-block"]', (e) => getComputedStyle(e).borderTopStyle === 'dashed'), 'model claim has a dashed outline (measured facts are solid)')
  ok((await page.textContent('[data-testid="claim"]')).length > 20, 'claim text is shown')
  ok((await page.textContent('[data-testid="step-hypothesize"]')).includes('85%'), 'self-reported confidence is shown separately')
  ok((await page.textContent('[data-testid="step-hypothesize"]')).includes('forensics.detailed.support.com_margin_before_push_m'), 'cited measurements are listed')
  await shot(page, '2-hypothesize')

  // ---- intervention ------------------------------------------------------------------------------------
  await page.click('[data-step="intervene"]')
  await page.waitForSelector('[data-testid="param-table"]')
  ok((await page.$$('[data-testid="param-table"] tr.changed')).length === 1, 'exactly one parameter changed')
  ok((await page.textContent('[data-testid="proposed-value"]')) === '3', 'proposed torso_mass value is 3')

  // ---- verification ------------------------------------------------------------------------------------
  await page.click('[data-step="verify"]')
  await page.waitForSelector('[data-testid="verdict"]')
  ok((await page.textContent('[data-testid="verdict"]')).includes('Rejected by MuJoCo'), 'MuJoCo verdict: rejected')
  const scrTitle = await page.textContent('[data-testid="screening-block"] h4')
  const scrNote = await page.textContent('[data-testid="screening-note"]')
  ok(scrTitle === 'Screening: seeds 0–4' && scrNote.includes('evidence came from seeds 0–2') && !/same seeds/.test(scrNote),
    `screening label uses the saved seed sets ("${scrTitle}"; evidence 0–2 is distinguished)`)
  ok((await page.$$('[data-testid="heldout-table"] tbody tr')).length === 5, 'held-out results for all 5 push levels')
  ok((await page.textContent('[data-testid="verdict-block"]')).includes('fell more often than the original at 15'), 'worse-at-15-N finding is surfaced')
  await shot(page, '4-verify')

  // phone width: no horizontal page scroll on the data-heavy step
  await page.setViewportSize({ width: 390, height: 800 })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  ok(overflow <= 1, `no horizontal page scroll at phone width (overflow ${overflow}px)`)
  await shot(page, '4b-verify-mobile')
  await page.setViewportSize({ width: 1360, height: 1000 })

  // ---- load the real simulation -> compare -------------------------------------------------------------
  await page.click('[data-step="compare"]')
  await page.waitForSelector('[data-testid="load-replay"]')
  ok((await page.$$('canvas')).length === 0, 'no simulation is shown before the user loads it')
  await page.click('[data-testid="load-replay"]')
  await page.waitForSelector('[data-testid="compare-pair"] canvas', { timeout: 60000 })
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="compare-pair"] canvas').length === 2)
  ok(true, 'two WebGL viewports mounted (original + modified)')
  const cons = await page.$$eval('[data-testid="consistency"]', (els) => els.map((e) => e.getAttribute('data-ok')))
  ok(cons.length === 2 && cons.every((c) => c === 'true'), 'fresh MuJoCo statistics match the saved record for both robots')
  const labels = await page.$$eval('.vp-label', (els) => els.map((e) => e.textContent))
  ok(labels.some((l) => l.startsWith('ORIGINAL')) && labels.some((l) => l.startsWith('MODIFIED')), 'viewports are labelled original / modified')

  // synchronized timeline: one scrubber drives both viewports
  await page.$eval('input[aria-label="timeline"]', (el) => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    set.call(el, '4.5')
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await page.waitForFunction(() => document.querySelectorAll('.vp-fall').length === 2, null, { timeout: 15000 })
  const huds = await page.$$eval('.vp-hud', (els) => els.map((e) => e.textContent))
  ok(huds.length === 2, 'both viewports show telemetry at the same sim time')
  const falls = await page.$$eval('.vp-fall', (els) => els.map((e) => e.textContent))
  ok(falls.length === 2 && falls.every((t) => t.includes('FALL detected')), 'both robots fall: the change did not help (matches the rejected verdict)')
  const clock = await page.textContent('.clock b')
  ok(clock.includes('4.50'), `shared clock reads ${clock.trim()}`)
  ok((await page.textContent('[data-testid="outcomes"]')).includes('fell'), 'outcome comparison table is shown')
  await shot(page, '5-compare')

  // a different seed must not silently show the old replay
  await page.selectOption('select[aria-label="replay seed"]', '2')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="compare-pair"]').length === 0)
  ok(true, 'changing the seed clears the stale replay')

  // ---- invalid response: no hypothesis, no verdict, honest about it -------------------------------------
  await page.click(`[data-testid="trial-${INVALID}"]`)
  await page.waitForFunction((id) => document.querySelector('[data-testid="detail"]')?.getAttribute('data-trial') === id, INVALID)
  ok((await page.textContent('[data-testid="headline"]')).includes('never tested'), 'invalid response is described as never tested')
  await page.click('[data-step="hypothesize"]')
  await page.waitForSelector('[data-testid="step-unavailable"]')
  ok(await page.isVisible('[data-testid="raw-reply"]'), 'the raw model reply is shown as untrusted text')
  ok((await page.textContent('[data-testid="step-unavailable"]')).includes('cited evidence path does not exist'), 'validation failure reason is shown')
  await page.click('[data-step="verify"]')
  ok((await page.textContent('[data-testid="step-unavailable"]')).includes('did not test anything'), 'no verdict is fabricated for an untested reply')
  await page.click('[data-step="observe"]')
  await page.click('[data-testid="load-replay"]')
  await page.waitForSelector('.viewport canvas', { timeout: 60000 })
  ok((await page.$$('.viewport')).length === 1, 'original failure can still be replayed for an invalid trial')
  await shot(page, '6-invalid')

  // ---- graceful failures --------------------------------------------------------------------------------
  await page.route(`**/api/lab/trials/${CONTROL}`, (r) => r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"disk on fire"}' }))
  await page.click(`[data-testid="trial-${CONTROL}"]`)
  await page.waitForSelector('[data-testid="detail-error"]')
  ok((await page.textContent('[data-testid="detail-error"]')).includes('disk on fire'), 'record loading errors are shown with a retry option')
  await page.unroute(`**/api/lab/trials/${CONTROL}`)
  await page.click('[data-testid="detail-error"] button')
  await page.waitForSelector('[data-testid="detail"]')
  ok(true, 'retry recovers after the error clears')

  await page.route(`**/api/lab/trials/${CONTROL}/replay**`, (r) => r.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"simulator busy"}' }))
  await page.click('[data-testid="load-replay"]')
  await page.waitForSelector('[data-testid="replay-error"]')
  ok((await page.textContent('[data-testid="replay-error"]')).includes('simulator busy'), 'replay failures are reported, not hidden')

  ok(pageErrors.length === 0, `no uncaught page errors${pageErrors.length ? ': ' + pageErrors.join(' | ') : ''}`)
} catch (e) {
  console.log('FAIL unexpected error:', e.message)
  await shot(page, 'failure')
  failed++
} finally {
  await browser.close()
}
console.log(failed === 0 ? 'INVESTIGATION LAB BROWSER FLOW PASSED' : `INVESTIGATION LAB BROWSER FLOW FAILED (${failed})`)
process.exit(failed === 0 ? 0 : 1)
