import { chromium } from 'playwright-core'
import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve(process.cwd(), '..')
const SHOTS = path.join(ROOT, 'screenshots')
const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8000'
fs.mkdirSync(SHOTS, { recursive: true })

const candidates = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean)
const executablePath = candidates.find((candidate) => fs.existsSync(candidate))
if (!executablePath) throw new Error('未找到 Chrome/Edge')

const browser = await chromium.launch({ headless: true, executablePath })
const page = await browser.newPage({ viewport: { width: 1440, height: 1080 }, locale: 'zh-CN' })
const errors = []
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(msg.text())
})
page.on('pageerror', (err) => errors.push(err.message))
await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
console.log('status:', await page.locator('.topbar .status-pill').innerText())
console.log('mock banner:', await page.locator('.demo-banner').count())
console.log('console errors:', errors.length ? errors : 'none')
await page.screenshot({ path: path.join(SHOTS, 'studio-real.png'), fullPage: true })
await browser.close()
