// Real-browser flow for "Recover walking": pick a starter that cannot walk, run a walk challenge, start a recovery with the SCRIPTED MOCK AI
// director and with the fixed rule (smoke scale, test server, no model is ever called), check that the RecoveryView renders every section with
// honest wording, that Accept is enabled only for FULL_RECOVERY, and that a 360 px phone has no horizontal overflow.
// Usage: BASE_URL=... node e2e/forge-recovery-flow.mjs   (SHOT_DIR optional)
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
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
const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
const shot = async (name) => { if (SHOT) await page.screenshot({ path: `${SHOT}/${name}.png`, fullPage: true }) }
const HEADLINE = {
  FULL_RECOVERY: /^Walks: recovered \(\d+\/\d+ validation seeds walking, confirmed \d+\/\d+ at 20 s\)$/,
  PARTIAL_IMPROVEMENT: /^Improved, but does not walk reliably \(not a recovery\)$/,
  NOT_RECOVERED: /^Not recovered within \d+ rollouts$/,
  INCONCLUSIVE_ERROR: /^Inconclusive/,
}

/** Checks one rendered RecoveryView. `want` = { provenance, ai }. Returns its status. */
async function checkRecord(want) {
  await page.waitForSelector(T('recovery-view'), { timeout: 900000 })
  const status = await page.getAttribute(T('recovery-view'), 'data-status')
  ok(Object.keys(HEADLINE).includes(status), `the recovery finished with a real assessment status (${status})`)
  const head = (await text(T('rec-status'))).trim()
  ok(HEADLINE[status]?.test(head), `the outcome is stated in plain words for ${status}: "${head.slice(0, 100)}"`)
  if (status !== 'FULL_RECOVERY') ok(!/^Walks: recovered/.test(head), 'a result that is not a full recovery is never called a recovery')
  const prov = await text(T('rec-provenance'))
  ok(prov.includes(want.chip), `the provenance pill says ${want.chip}`)
  ok(!(want.chip !== 'LIVE' && /\bLIVE\b/.test(await text(T('rec-provenance')))), 'a non-live record never wears the LIVE label')
  ok(want.model === '' || (await text(T('rec-model'))).trim() === want.model, `the model is shown (${(await text(T('rec-model'))).trim()})`)
  ok(/model call/.test(await text(T('rec-cost'))), 'the cost line is shown')

  // reasoning
  ok(await page.isVisible(T('rec-reasoning')), 'the reasoning section is shown')
  ok((await text(`${T('rec-reasoning')} h3`)).trim() === want.title, `the reasoning section is titled "${want.title}"`)
  ok((await page.locator(T('rec-round')).count()) >= 1, 'at least one round is listed')
  ok((await page.locator(T('rec-probe')).count()) >= 1, 'probes are listed with their measured result')
  const probeText = await page.locator(T('rec-probe')).first().textContent()
  ok(/Measured by MuJoCo/.test(probeText || ''), 'a probe states what MuJoCo measured')
  ok((await page.locator(T('rec-plan')).count()) >= 1, 'plans are listed')
  ok((await page.locator(`${T('rec-plan')} [data-kind]`).count()) >= 1, 'a plan lists its subsystems as chips (control subspaces and body parameters)')
  if (!want.ai) ok((await page.locator(T('rec-hypothesis')).count()) === 0, 'the fixed rule shows no hypotheses')
  if (want.ai) ok(/not a model/i.test(await text(T('rec-reasoning'))), 'the scripted mock says it is not a model')

  // ledger
  ok(await page.isVisible(T('rec-ledger')), 'the budget ledger is shown')
  ok((await page.locator(`${T('rec-ledger-legend')} li`).count()) === 5, 'the ledger legend lists start, probes, plans, screening and unspent')
  ok(/Every arm in a comparison gets the same total budget/.test(await text(T('rec-ledger-note'))), 'the equal-budget note is shown')

  // candidate
  ok(await page.isVisible(T('rec-candidate')), 'the candidate section is shown')
  ok((await page.locator(`${T('rec-edits')} tbody tr`).count()) >= 1 || (await page.isVisible(T('rec-no-body-edits'))), 'body edits (old -> new, ratio) or an explicit "body unchanged" are shown')
  ok((await page.locator(`${T('rec-fp')} [data-active]`).count()) === 2, 'the foot-placement gains fp_kd and fp_kv are listed')

  // verification
  ok(await page.isVisible(T('rec-verification')), 'the verification section is shown')
  const strip = await page.locator(`${T('rec-strip')} [data-seed]`).count()
  ok(strip >= 2, `the per-seed validation strip lists the held-out seeds (${strip})`)
  ok(/verdict_v1/.test(await text(T('rec-verdict'))), 'the verdict_v1 summary is shown')
  ok((await page.isVisible(T('rec-confirm'))) || (await page.isVisible(T('rec-confirm-skipped'))), 'the confirmation checks (or why they were not run) are shown')
  await page.waitForSelector(`${T('rec-viewports')} canvas`, { timeout: 240000 })
  ok((await page.locator(`${T('rec-viewports')} canvas`).count()) >= 2, 'original and candidate replay side by side on a validation seed')
  const labels = await page.$$eval(`${T('rec-viewports')} .vp-label`, (els) => els.map((e) => e.textContent))
  ok(labels.some((l) => l.startsWith('ORIGINAL')) && labels.some((l) => l.startsWith('CANDIDATE')), `the viewports are labelled original / candidate (${labels.join(' | ')})`)
  ok(await page.isVisible('.transport'), 'one shared transport drives both replays')
  return status
}

try {
  // --- a starter that cannot walk -> use it in the forge
  await page.goto(`${BASE}/?tab=sketch`)
  await page.waitForSelector(T('sketch-page'))
  await page.click(T('starter-weak-slippery'))
  await page.waitForFunction(() => /^(valid|questionable)/.test(document.querySelector('[data-testid="outcome"]')?.getAttribute('data-outcome') || ''), null, { timeout: 30000 })
  await page.waitForFunction(() => { const b = document.querySelector('[data-testid="use-creature-btn"]'); return b && !b.disabled }, null, { timeout: 30000 })
  await page.click(T('use-creature-btn'))
  await page.waitForSelector(T('creature-bar'), { timeout: 30000 })
  ok((await text(T('version-chip'))).trim() === 'v1', 'the starter creature is on the bench as v1')
  ok((await page.locator(T('recover-btn')).count()) === 0, 'before any walk challenge, "Recover walking" is not offered')

  // --- walk challenge
  await page.click(T('kind-walk'))
  await page.selectOption(T('seed-count'), { index: 0 })
  await page.click(T('run-challenge'))
  await page.waitForSelector(`${T('run-result')}, ${T('run-failed')}`, { timeout: 600000 })
  const outcome = await page.isVisible(T('run-result')) ? await page.getAttribute(T('run-outcome'), 'data-outcome') : 'ERROR'
  ok(['PASS', 'POOR', 'FAIL', 'ERROR'].includes(outcome), `the walk challenge finished with a real outcome (${outcome})`)
  if (outcome !== 'FAIL' && outcome !== 'POOR') {
    ok((await page.locator(T('recover-btn')).count()) === 0, `"Recover walking" is not offered for a ${outcome} walk challenge`)
    console.log(`INFO the starter did not fail the walk challenge (${outcome}); the rest of the recovery flow needs a failing creature`)
  } else {
    ok(await page.isVisible(T('recover-btn')), `"Recover walking" is offered next to the investigation for a ${outcome} walk challenge`)
    ok(await page.isVisible(T('investigate-mock-btn')), 'the existing investigate action is still there')
    ok((await page.inputValue(T('rec-budget'))) === '2000', 'the default budget is 2000 rollouts')
    ok(JSON.stringify(await page.locator(`${T('rec-budget')} option`).evaluateAll((os) => os.map((o) => o.value))) === '["1000","2000","4000"]', 'the budget choices are 1000, 2000 and 4000')
    const live = (await page.evaluate(() => fetch('/api/forge/status').then((r) => r.json()))).live_available
    const dirLabel = await text('label:has([data-testid="rec-dir-ai"])')
    ok(live ? /LIVE/.test(dirLabel) : /SCRIPTED MOCK/.test(dirLabel), `the AI director option is labelled ${live ? 'LIVE' : 'SCRIPTED MOCK (not a model)'}`)
    ok(/Fixed engineering rule \(no AI\)/.test(await text('label:has([data-testid="rec-dir-fix"])')), 'the fixed-rule option is offered')
    await shot('recovery-offer')

    // --- 1. AI director (scripted mock on this test server)
    await page.click(T('recover-btn'))
    await page.waitForSelector(T('rec-progress'), { timeout: 60000 })
    ok((await page.locator(`${T('rec-stages')} li`).count()) === 6, 'progress shows the six phases (diagnostics, probes, plans, screening, validation, confirmation)')
    ok(await page.isVisible(T('rec-budget-bar')), 'a budget bar shows rollouts used / total')
    const aiChip = live ? 'LIVE' : 'SCRIPTED MOCK'
    const aiStatus = await checkRecord({ chip: aiChip, model: live ? '' : 'scripted-fixture', title: live ? 'How the AI reasoned' : 'Scripted decisions (fixed rule in the AI layout, not a model)', ai: true })
    await shot('recovery-ai-1440')

    // --- accept is for FULL_RECOVERY only
    if (aiStatus !== 'FULL_RECOVERY') {
      ok(await page.isDisabled(T('rec-accept-btn')), `Accept is disabled because the status is ${aiStatus}`)
      ok(/Only FULL_RECOVERY can be accepted/.test(await text(T('rec-accept-blocked'))), 'the reason says only a full recovery can be accepted')
    } else {
      ok(!(await page.isDisabled(T('rec-accept-btn'))) && /Accept as version 2/.test(await text(T('rec-accept-btn'))), 'a full recovery can be accepted as version 2')
    }

    // --- 2. the fixed rule (no AI)
    await page.click(T('rec-dir-fix'))
    await page.click(T('recover-btn'))
    await page.waitForSelector(T('rec-progress'), { timeout: 60000 })
    await page.waitForFunction(() => document.querySelector('[data-testid="recovery-view"]')?.getAttribute('data-provenance') === 'NON_AI', null, { timeout: 900000 })
    await checkRecord({ chip: 'NO AI', model: 'no model', title: 'Rule decisions (no AI)', ai: false })
    ok(/No model was called/.test(await text(T('rec-header'))), 'the fixed-rule record says no model was called')
    await shot('recovery-fix-1440')

    // --- history lists both
    const items = await page.locator(T('recovery-item')).count()
    ok(items >= 2, `the recovery history lists both recoveries (${items})`)
    const chips = (await page.locator(`${T('recovery-list')} ${T('prov-chip')}`).allTextContents()).join('|')
    ok(/NO AI/.test(chips) && /SCRIPTED MOCK|LIVE/.test(chips), `the history shows provenance chips (${chips})`)

    // --- phone width, with the recovery open
    await page.setViewportSize({ width: 360, height: 800 })
    await page.waitForFunction(() => window.innerWidth === 360)
    await page.waitForTimeout(500)
    ok((await overflow()) <= 1, `no horizontal page overflow at 360 px with a recovery open (${await overflow()}px)`)
    await shot('recovery-360')
    await page.locator(T('recovery-item')).nth(items - 1).click()
    await page.waitForSelector(T('recovery-view'))
    await page.waitForTimeout(500)
    ok((await overflow()) <= 1, `no horizontal page overflow at 360 px with the other recovery open (${await overflow()}px)`)
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.waitForFunction(() => window.innerWidth === 1440)

    // --- accept (only when a full recovery exists) and challenge the new version
    const fullId = await page.locator(`${T('recovery-item')}[data-status="FULL_RECOVERY"]`).first().getAttribute('data-id').catch(() => null)
    if (fullId) {
      await page.locator(`${T('recovery-item')}[data-id="${fullId}"]`).click()
      await page.waitForSelector(`${T('recovery-view')}[data-status="FULL_RECOVERY"]`)
      await page.click(T('rec-accept-btn'))
      await page.waitForSelector(T('lineage-v2'), { timeout: 60000 })
      ok((await text(T('version-chip'))).trim() === 'v2', 'after accepting, the version chip shows v2')
      const lin = await text(T('lineage-v2'))
      ok(/from v1/.test(lin) && /(Scripted mock|Rule-based) change, accepted/.test(lin) && /walking recovery/.test(lin), `the lineage shows the origin and the recovery (${lin.replace(/\s+/g, ' ').slice(0, 130)})`)
      ok(await page.isVisible(T('rec-run-walk')) && /Run walk challenge on v2/.test(await text(T('rec-run-walk'))), 'the page offers "Run walk challenge on v2"')
      await page.click(T('rec-run-walk'))
      await page.waitForSelector(`${T('run-result')}, ${T('run-failed')}`, { timeout: 600000 })
      ok(await page.isVisible(T('run-result')), 'v2 was challenged with the walk challenge')
    } else {
      console.log('INFO no recovery reached FULL_RECOVERY at smoke scale; accept stays disabled (checked above)')
    }
  }
  ok(bad.length === 0, `every API response is JSON and < 400${bad.length ? ': ' + bad.join(' | ') : ''}`)
  ok(errors.length === 0, `no console or page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} catch (e) { ok(false, `flow threw: ${e.message}`); await shot('recovery-failure').catch(() => undefined) }
await browser.close()
process.exit(failed ? 1 : 0)
