// Real-browser flow for freehand sketching: draw with the mouse, undo/redo/erase/clear/zoom, interpretation, guided ON vs OFF,
// approximation consent, and the hand-off to a real MuJoCo run. Usage: BASE_URL=... node e2e/freehand-flow.mjs (SHOT_DIR optional)
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
const errors = [], bad = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('response', (r) => { if (r.url().includes('/api/') && (r.status() >= 400 || !(r.headers()['content-type'] || '').includes('json'))) bad.push(`${r.status()} ${r.url()}`) })
const T = (id) => `[data-testid="${id}"]`
const text = async (sel) => (await page.textContent(sel).catch(() => '')) || ''
const nStrokes = () => page.locator(T('stroke')).count()
// world (canvas px, 400 px = 1 m, y down) -> client pixels at the default view
const toClient = async ([x, y]) => { const b = await page.locator(T('draw-canvas')).boundingBox(); return [b.x + (x / 1000) * b.width, b.y + (y / 700) * b.height] }
async function drawStroke(pts) {
  const cs = []
  for (const p of pts) cs.push(await toClient(p))
  await page.mouse.move(...cs[0]); await page.mouse.down()
  for (let i = 1; i < cs.length; i++) await page.mouse.move(cs[i][0], cs[i][1], { steps: 5 })
  await page.mouse.up()
}
const outcome = async () => page.getAttribute(T('outcome'), 'data-outcome')
const settle = async (want) => { await page.waitForFunction((w) => { const o = document.querySelector('[data-testid="outcome"]'); return o && (!w || w.includes(o.getAttribute('data-outcome'))) }, want, { timeout: 15000 }); await page.waitForTimeout(400) }
// a stick figure in world px: torso box, bent-free leg, foot
const G = 620
const figure = { torso: [[480, G - 256 - 120], [520, G - 256 - 120], [520, G - 256], [480, G - 256], [480, G - 256 - 120]], leg: [[500, G - 256], [500, G - 136], [500, G - 16]], foot: [[490, G - 16], [564, G - 16]] }

try {
  await page.goto(`${BASE}/?tab=sketch`)
  await page.waitForSelector(T('sketch-page'))
  ok(await page.isVisible(T('canvas-empty')), 'an empty canvas invites drawing')
  ok(((await text(T('guided-switch'))) || '').includes('Guided constraints: ON'), 'Guided constraints is ON by default, in plain view')

  // --- freehand drawing with the mouse and role pens
  await page.click(T('pen-torso')); await drawStroke(figure.torso)
  await page.click(T('pen-leg')); await drawStroke(figure.leg)
  await page.click(T('pen-foot')); await drawStroke(figure.foot)
  ok((await nStrokes()) === 3, 'three freehand strokes are on the canvas')
  await page.waitForFunction(() => document.querySelector('[data-testid="outcome"]')?.getAttribute('data-outcome')?.startsWith('valid'), null, { timeout: 15000 })
  ok(['valid', 'valid_with_snaps'].includes(await outcome()), `a sensible drawing is read as valid (${await outcome()})`)
  ok((await page.locator('.skel').count()) > 0, 'the interpreted skeleton is drawn over the raw strokes')
  ok(((await text(T('strokes-list'))) || '').length > 0, 'each stroke is listed with the role it was read as')
  await page.waitForSelector(`${T('sketch-preview')} canvas`, { timeout: 60000 })
  ok(true, 'the real MuJoCo model preview appears')
  if (SHOT) await page.screenshot({ path: `${SHOT}/draw-valid.png` })

  // --- undo / redo / erase / clear / zoom
  await page.click(T('undo')); ok((await nStrokes()) === 2, 'undo removes the last stroke')
  await page.click(T('redo')); ok((await nStrokes()) === 3, 'redo brings it back')
  await page.click(T('tool-eraser'))
  const [ex, ey] = await toClient([500, G - 136])
  await page.mouse.move(ex, ey); await page.mouse.down(); await page.mouse.move(ex + 1, ey + 1); await page.mouse.up()
  ok((await nStrokes()) === 2, 'the eraser removes the stroke under the pointer')
  await page.click(T('undo')); ok((await nStrokes()) === 3, 'erasing is undoable')
  const vb0 = await page.getAttribute(T('draw-canvas'), 'viewBox')
  await page.click(T('zoom-in')); const vb1 = await page.getAttribute(T('draw-canvas'), 'viewBox')
  ok(vb0 !== vb1, 'zoom changes the view')
  await page.click(T('zoom-fit'))
  const raw = await page.locator(T('stroke')).first().getAttribute('d')
  ok(!!raw && raw.includes('Q'), 'strokes render as smooth curves, not polylines')

  // --- the same strokes always read the same way (reload keeps the raw drawing and the reading)
  const first = await text(T('outcome'))
  await page.reload(); await page.waitForSelector(T('sketch-page')); await settle(['valid', 'valid_with_snaps', 'questionable'])
  ok((await nStrokes()) === 3 && (await text(T('outcome'))) === first, 'the raw drawing survives a reload and is interpreted identically')

  // --- guided ON snaps, OFF keeps the raw angle
  await page.click(T('clear'))
  await page.click(T('pen-torso')); await drawStroke(figure.torso)
  await page.click(T('pen-leg')); await drawStroke([[500, G - 256], [512, G - 136], [524, G - 16]]) // ~2.7 degrees off vertical
  await page.click(T('pen-foot')); await drawStroke([[500, G - 16], [570, G - 16]])
  await page.waitForFunction(() => document.querySelector('[data-testid="adjustments"]'), null, { timeout: 15000 })
  ok(/vertical|straight/i.test(await text(T('adjustments'))), 'guided ON: a nearly vertical leg is snapped in the interpretation and says so')
  await page.click(T('guided-switch')); await settle()
  ok((await page.$(T('adjustments'))) === null, 'guided OFF: no snapping, the raw angle is kept')
  ok(((await text(T('guided-switch'))) || '').includes('OFF'), 'the switch shows OFF · Experimental')
  await page.click(T('guided-switch')); await settle()

  // --- an ambiguous drawing asks instead of guessing
  await page.click(T('clear'))
  await page.click(T('pen-auto'))
  await drawStroke(figure.torso)
  await drawStroke([[560, G - 256 - 120], [600, G - 256 - 120], [600, G - 256], [560, G - 256], [560, G - 256 - 120]])
  await drawStroke([[500, G - 256], [500, G - 16]])
  await page.waitForSelector(T('ambiguity'), { timeout: 15000 })
  ok(await outcome() === 'needs_input' && (await page.isDisabled(T('simulate-btn'))), 'two possible torsos: it asks which one, and Simulate waits')
  await page.locator(`${T('ambiguity')} button`).first().click(); await settle(['valid', 'valid_with_snaps', 'questionable', 'unrepresentable'])
  ok((await page.$(T('ambiguity'))) === null, 'choosing a reading resolves the ambiguity')

  // --- a deliberately terrible creature in experimental mode runs in MuJoCo
  await page.click(T('starter-tiny-feet')); await settle(['questionable'])
  ok(((await text(T('guided-switch'))) || '').includes('OFF'), 'picking a deliberately bad starter turns Guided constraints off, and tells you')
  ok(await outcome() === 'questionable' && /outside the verified/i.test(await text(T('notes'))), 'experimental: a 3 cm foot is buildable but flagged as questionable')
  await page.waitForSelector(`${T('sketch-preview')} canvas`, { timeout: 60000 })
  if (SHOT) await page.screenshot({ path: `${SHOT}/draw-bad-experimental.png` })
  await page.click(T('simulate-btn'))
  await page.waitForSelector(T('sandbox-result'), { timeout: 90000 })
  const verdict = await page.getAttribute(T('sandbox-result'), 'data-verdict')
  ok(verdict === 'fell', `the bad creature really ran in MuJoCo and fell (${await text(T('sandbox-headline'))})`)
  ok((await page.locator(T('sandbox-reasons') + ' li').count()) >= 1 && (await page.locator(T('sandbox-design-notes')).count()) === 1, 'the result explains what failed physically and which design choices were unusual')
  await page.waitForSelector('.viewport canvas')
  if (SHOT) await page.screenshot({ path: `${SHOT}/sandbox-fall.png` })
  ok(/different robot/.test(await text('.link-ai')), 'the AI investigation link says the recording was on a different robot, not this drawing')

  // --- guided ON refuses the same drawing and offers a consent-gated approximation
  await page.click(T('edit-drawing')); await page.waitForSelector(T('sketch-page'))
  await page.waitForSelector(T('guided-switch'))
  await page.click(T('guided-switch')); await settle(['unrepresentable'])
  ok(await outcome() === 'unrepresentable' && (await page.isDisabled(T('simulate-btn'))), 'guided ON: the tiny foot is refused and Simulate is disabled')
  ok(/foot/i.test(await text(T('why-not'))), 'the refusal names the exact limitation')
  await page.waitForSelector(T('approximation'))
  ok(await page.isVisible(T('approx-compare')), 'a before/after comparison of the approximation is shown')
  ok(await page.isDisabled(T('approx-simulate')), 'approximate-and-simulate is blocked until the user consents')
  if (SHOT) await page.screenshot({ path: `${SHOT}/draw-approximation.png` })
  await page.check(T('approx-consent')); await page.click(T('approx-simulate'))
  await page.waitForSelector(T('sandbox-approximated'), { timeout: 90000 })
  ok(true, 'after consent the approximated creature runs, and the result says it was approximated')

  // --- refine mode (handle editor) is still available
  await page.click(T('nav-create')); await page.waitForSelector(T('sketch-page'))
  await page.click(T('mode-refine')); await page.waitForSelector(T('sketch-editor'))
  ok(true, 'the handle-based editor is available as Refine mode')

  // --- phone width
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`${BASE}/?tab=sketch`); await page.waitForSelector(T('sketch-page'))
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  ok(overflow <= 1, `no horizontal page overflow at 390 px (${overflow}px)`)
  if (SHOT) await page.screenshot({ path: `${SHOT}/draw-mobile.png`, fullPage: true })
  ok(bad.length === 0, `every API response is JSON and < 400${bad.length ? ': ' + bad.join(' | ') : ''}`)
  ok(errors.length === 0, `no console or page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} catch (e) { ok(false, `flow threw: ${e.message}`) }
await browser.close()
process.exit(failed ? 1 : 0)
