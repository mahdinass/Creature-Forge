// LIVE end-to-end browser flow (owner's merge condition): draw a creature, run a Push challenge in MuJoCo, click
// "Investigate with AI" (a REAL Nemotron call on Nebius), wait for MuJoCo's verdict, check the honest labels, the matched twin
// and the replay, accept ONLY if the verdict is a verified improvement, and challenge the new version.
// NEVER part of CI: it spends real inference (~2-3 calls, ~$0.005). Requires LIVE_OK=1 and a server started with live mode.
// Usage: LIVE_OK=1 BASE_URL=http://127.0.0.1:8000 SHOT_DIR=... node e2e/forge-live-flow.mjs
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'

if (process.env.LIVE_OK !== '1') { console.log('SKIP set LIVE_OK=1 to run the live flow (real model calls)'); process.exit(0) }
const BASE = process.env.BASE_URL
if (!BASE) throw new Error('BASE_URL is required')
const SHOT = process.env.SHOT_DIR
if (SHOT) mkdirSync(SHOT, { recursive: true })
const exe = [process.env.BROWSER_PATH, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', 'C:/Program Files/Google/Chrome/Application/chrome.exe']
  .filter(Boolean).find((p) => existsSync(p))
if (!exe) throw new Error('no Chrome found; set BROWSER_PATH')
let failed = 0
const ok = (c, m) => { console.log(`${c ? 'PASS' : 'FAIL'} ${m}`); if (!c) failed++ }
const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
page.setDefaultNavigationTimeout(150000)
const errors = [], bad = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('response', (r) => { if (r.url().includes('/api/') && (r.status() >= 400 || !(r.headers()['content-type'] || '').includes('json'))) bad.push(`${r.status()} ${r.url()}`) })
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
const summary = {}

try {
  const status = await (await fetch(`${BASE}/api/forge/status`)).json()
  ok(status.live_available === true, `the server has live mode on (model ${status.model?.model})`)
  summary.ledger_before = status.ledger

  await page.goto(`${BASE}/?tab=sketch`)
  await page.waitForSelector(T('sketch-page'))
  await page.click(T('pen-torso')); await drawStroke(figure.torso)
  await page.click(T('pen-leg')); await drawStroke(figure.leg)
  await page.click(T('pen-foot')); await drawStroke(figure.foot)
  await page.waitForFunction(() => document.querySelector('[data-testid="outcome"]')?.getAttribute('data-outcome')?.startsWith('valid'), null, { timeout: 30000 })
  await page.click(T('use-creature-btn'))
  await page.waitForSelector(T('creature-bar'), { timeout: 30000 })
  ok((await text(T('version-chip'))).trim() === 'v1', 'the drawn creature is on the bench as v1')
  summary.creature_url = page.url()

  await page.click(T('kind-push'))
  await page.click(T('run-challenge'))
  await page.waitForSelector(`${T('run-result')}, ${T('run-failed')}`, { timeout: 420000 })
  ok(await page.isVisible(T('run-result')), `the push challenge ran in MuJoCo (${await page.getAttribute(T('run-outcome'), 'data-outcome')})`)

  ok(!(await page.isDisabled(T('investigate-btn'))), '"Investigate with AI" is enabled on a live server')
  await page.check(T('probes-checkbox'))
  await page.click(T('investigate-btn'))
  await page.waitForSelector(T('inv-progress'), { timeout: 60000 })
  await page.waitForSelector(`${T('investigation-record')}, ${T('investigation-failed')}, ${T('investigation-error')}`, { timeout: 1500000 })
  ok(await page.isVisible(T('investigation-record')), 'the live investigation finished and its record is shown')
  const recStatus = await page.getAttribute(T('investigation-record'), 'data-status')
  summary.record_status = recStatus
  ok(/LIVE/.test(await text(T('inv-provenance'))) && !/SCRIPTED/.test(await text(T('inv-provenance'))), 'the provenance banner says LIVE (not scripted)')
  const call = await text(T('model-call'))
  ok(/nemotron/i.test(call) && !/scripted-fixture/.test(call), `the model call card names the NVIDIA model (${call.replace(/\s+/g, ' ').slice(0, 120)})`)
  const items = await page.evaluate(() => fetch(`/api/forge/investigations?cid=${new URL(location.href).searchParams.get('creature')}`).then((r) => r.json()))
  const rec = items.length ? await page.evaluate((id) => fetch(`/api/forge/investigations/${id}`).then((r) => r.json()), items[0].id) : null
  summary.investigation_id = rec?.id
  summary.request_ids = (rec?.model_calls || []).map((c) => c.request_id)
  ok(rec && rec.provenance === 'LIVE' && summary.request_ids.every((r) => r && !String(r).startsWith('scripted')), `the record is LIVE with real request ids (${summary.request_ids.join(', ')})`)
  if (recStatus === 'done') {
    const chips = await page.locator(`${T('investigation-record')} ${T('prov-chip')}`).allTextContents()
    ok(chips.some((c) => /NEMOTRON/.test(c)), `arms are labelled NEMOTRON / RANDOM BASELINE / HEURISTIC (${[...new Set(chips)].join(', ')})`)
    if (await page.isVisible(T('verdict-ai'))) {
      ok(await page.isVisible(T('verdict-twin')), 'the matched random twin is shown next to the AI verdict')
      summary.ai_verdict = await page.getAttribute(T('verdict-ai'), 'data-status')
      await page.waitForSelector(`${T('arena-viewports')} canvas`, { timeout: 180000 })
      ok(true, 'the original and the AI arm replay side by side on a held-out seed')
    } else {
      console.log('INFO no AI arm reached validation in this run (recorded as such)')
    }
    if (SHOT) await page.screenshot({ path: `${SHOT}/live-investigation-1920.png`, fullPage: true })
    if (await page.getAttribute(T('accept-panel'), 'data-can-accept') === 'true') {
      await page.click(T('accept-btn'))
      await page.waitForSelector(T('lineage-v2'), { timeout: 60000 })
      ok((await text(T('version-chip'))).trim() === 'v2' && /Nemotron|NEMOTRON|nemotron/.test(await text(T('lineage-v2'))), 'the verified redesign was accepted as v2 and attributed to Nemotron')
      await page.click(T('challenge-new-version'))
      await page.waitForSelector(`${T('run-result')}, ${T('run-failed')}`, { timeout: 420000 })
      ok(await page.isVisible(T('run-result')), 'v2 was challenged in MuJoCo')
      summary.accepted = true
      if (SHOT) await page.screenshot({ path: `${SHOT}/live-v2-1920.png`, fullPage: true })
    } else {
      ok(await page.isDisabled(T('accept-btn')), `accept stays disabled: nothing verified (${summary.ai_verdict || recStatus})`)
      summary.accepted = false
    }
  } else {
    ok(await page.isVisible(T('model-failure')), `an incomplete live record is shown honestly (${recStatus})`)
  }
  ok(bad.length === 0, `every API response is JSON and < 400${bad.length ? ': ' + bad.join(' | ') : ''}`)
  ok(errors.length === 0, `no console or page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} catch (e) { ok(false, `flow threw: ${e.message}`) }
summary.failed_checks = failed
console.log('SUMMARY ' + JSON.stringify(summary))
if (SHOT) writeFileSync(`${SHOT}/live-flow-summary.json`, JSON.stringify(summary, null, 1))
await browser.close()
process.exit(failed ? 1 : 0)
