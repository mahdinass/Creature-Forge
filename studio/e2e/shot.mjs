// Dev helper: full-page screenshot of a URL after an optional selector appears. Usage: node e2e/shot.mjs <url> <out.png> [selector] [width]
import { chromium } from 'playwright-core'
const [url, out, sel, w] = process.argv.slice(2)
const b = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] })
const p = await b.newPage({ viewport: { width: Number(w || 1360), height: 900 } })
await p.goto(url)
if (sel) await p.waitForSelector(sel, { timeout: 120000 })
await p.waitForTimeout(1500)
await p.screenshot({ path: out, fullPage: true })
await b.close()
