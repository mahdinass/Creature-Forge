// Real-browser smoke of EVERY top-level tab against a running Studio: nav is complete, no tab shows a load/parse error,
// no API call returns HTML or an error status. Usage: BASE_URL=http://127.0.0.1:8000 node e2e/tabs-smoke.mjs  (SHOT_DIR optional)
import { chromium } from 'playwright-core'
import { existsSync, mkdirSync } from 'node:fs'

const BASE = process.env.BASE_URL || process.env.BASE
if (!BASE) throw new Error('BASE_URL is required')
const SHOT = process.env.SHOT_DIR
if (SHOT) mkdirSync(SHOT, { recursive: true })
const exe = [process.env.BROWSER_PATH, 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe', '/usr/bin/google-chrome', '/usr/bin/chromium'].filter(Boolean).find((p) => existsSync(p))
if (!exe) throw new Error('no Chrome/Edge found; set BROWSER_PATH')
let failed = 0
const ok = (c, m) => { console.log(`${c ? 'PASS' : 'FAIL'} ${m}`); if (!c) failed++ }
const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } })
const bad = [], errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('response', (r) => {
  if (!r.url().includes('/api/')) return
  const t = r.headers()['content-type'] || ''
  if (r.status() >= 400 || !t.includes('json')) bad.push(`${r.status()} ${t} ${r.url()}`)
})
const ERR = /Unexpected token|is not valid JSON|Could not load|No Phase 2A locomotion results available|instead of JSON/i
try {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  const nav = (await page.$$eval('nav button, header button', (bs) => bs.map((b) => b.textContent.trim())))
  for (const label of ['Overview', 'Studio', 'Investigations', 'Locomotion', 'AI Investigation', 'Sketch'])
    ok(nav.some((n) => n.includes(label)), `nav has "${label}"`)
  for (const tab of ['overview', 'studio', 'compare', 'lab', 'locomotion', 'demo', 'sketch']) {
    await page.goto(`${BASE}/?tab=${tab}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)
    const text = await page.innerText('body')
    ok(!ERR.test(text), `tab ${tab}: no load/parse error text`)
    if (SHOT) await page.screenshot({ path: `${SHOT}/tab-${tab}.png` })
  }
  ok(bad.length === 0, `every API response is JSON and < 400${bad.length ? ': ' + bad.join(' | ') : ''}`)
  ok(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} catch (e) { ok(false, `flow threw: ${e.message}`) }
await browser.close()
process.exit(failed ? 1 : 0)
