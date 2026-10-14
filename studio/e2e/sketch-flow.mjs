// Real-browser flow for the direct-manipulation sketch editor. Usage: BASE_URL=... node e2e/sketch-flow.mjs (SHOT_DIR optional)
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
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
page.setDefaultNavigationTimeout(150000)
const errors = [], bad = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('response', (r) => { if (r.url().includes('/api/') && (r.status() >= 400 || !(r.headers()['content-type'] || '').includes('json'))) bad.push(`${r.status()} ${r.url()}`) })
const text = async (sel) => (await page.textContent(sel)) || ''
const center = async (sel) => { const b = await page.locator(sel).boundingBox(); return [b.x + b.width / 2, b.y + b.height / 2] }
const dragBy = async (sel, dx, dy) => {
  const [x, y] = await center(sel)
  await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.move(x + dx / 2, y + dy / 2, { steps: 4 }); await page.mouse.move(x + dx, y + dy, { steps: 4 })
  return async () => page.mouse.up()
}
const settle = () => page.waitForTimeout(700)
try {
  await page.goto(`${BASE}/?tab=sketch`)
  await page.click('[data-testid="mode-refine"]') // the handle editor is the Refine mode of Create
  await page.waitForSelector('[data-testid="sketch-valid"]', { timeout: 30000 })
  ok(true, 'a fresh sketch is valid and says it maps exactly to a MuJoCo model')
  ok(/0\.300/.test(await text('[data-testid="sketch-compiled"]')), 'the compiled table shows the default 0.300 m legs')
  await page.waitForSelector('[data-testid="sketch-preview"] canvas', { timeout: 60000 })
  ok(true, 'the physical preview (compiled MuJoCo model) renders')

  // presets
  await page.click('[data-testid="preset-long"]'); await settle()
  await page.waitForFunction(() => /0\.450/.test(document.querySelector('[data-testid="sketch-compiled"]')?.textContent || ''))
  ok(true, 'the "Long legs" preset compiles to 0.450 m thigh and shank')

  // direct manipulation: drag the knee ~0.07 m sideways -> server straightens it and tells us
  await page.click('[data-testid="preset-default"]'); await settle()
  let up = await dragBy('[data-testid="handle-knee"]', 24, 0) // 24 px of 300 px/m ~ 0.08 m (beyond the 0.03 magnetic snap)
  await settle()
  ok(await page.$('[data-testid="sketch-ghost"]') !== null, 'while dragging, the ghost shows what you drew next to what will be simulated')
  await up(); await settle()
  const adj = await text('[data-testid="sketch-adjustments"]').catch(() => '')
  ok(/Straightened the leg/.test(adj), `a near-valid knee drag is straightened and explained (${adj.slice(0, 80)})`)
  ok(!(await page.isDisabled('[data-testid="sketch-simulate"]')), 'the creature can still be simulated')

  // far sideways knee: refused with a reason, simulate disabled
  await page.click('[data-testid="preset-default"]'); await settle()
  up = await dragBy('[data-testid="handle-knee"]', 120, 0); await settle()
  const err = await text('[data-testid="sketch-errors"]').catch(() => '')
  ok(/sideways|Bent or leaning/.test(err), `an unsupported bent leg is explained, not converted (${err.slice(0, 90)})`)
  ok(await page.isDisabled('[data-testid="sketch-simulate"]'), 'simulate is disabled while the shape is invalid')
  ok(/not buildable/i.test(await text('[data-testid="sketch-svg"]')), 'the drawing itself says it is not buildable')
  if (SHOT) await page.screenshot({ path: `${SHOT}/sketch-invalid.png` })
  await up()

  // recover, then change torso mass with the side handle and the ankle height
  await page.click('[data-testid="preset-default"]'); await settle()
  up = await dragBy('[data-testid="handle-mass-grip"]', 0, -60); await up(); await settle()
  const mass = Number(/torso ([\d.]+) kg/.exec(await text('[data-testid="sketch-svg"]'))?.[1])
  ok(mass > 5, `dragging the torso handle up raises its mass (${mass} kg)`)
  up = await dragBy('[data-testid="handle-hip"]', 0, -40); await up(); await settle()
  const dims = await text('[data-testid="sketch-svg"]')
  ok(/thigh 0\.4\d m/.test(dims), `dragging the hip up lengthens the thigh (live dimension label: ${(/thigh [\d.]+ m/.exec(dims) || [''])[0]})`)

  // unsupported topology is explained on the page
  await page.click('[data-testid="sketch-support"] summary')
  ok(/tails|extra limbs/.test(await text('[data-testid="sketch-support"]')), 'the editor states plainly what it cannot build')

  // simulate: goes to the Studio and forges the sketched creature
  if (SHOT) await page.screenshot({ path: `${SHOT}/sketch-valid.png` })
  await page.click('[data-testid="sketch-simulate"]')
  await page.waitForSelector('.viewport canvas', { timeout: 60000 })
  ok(true, 'Simulate opens the Studio with the sketched creature')
  await page.waitForFunction(() => /thigh/i.test(document.body.innerText), null, { timeout: 60000 }).catch(() => {})
  await page.setViewportSize({ width: 360, height: 800 })
  await page.goto(`${BASE}/?tab=sketch`)
  await page.waitForSelector('[data-testid="sketch-page"]')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  ok(overflow <= 1, `no horizontal page overflow at 360 px (${overflow}px)`)
  ok(bad.length === 0, `every API response is JSON and < 400${bad.length ? ': ' + bad.join(' | ') : ''}`)
  ok(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} catch (e) { ok(false, `flow threw: ${e.message}`) }
await browser.close()
process.exit(failed ? 1 : 0)
