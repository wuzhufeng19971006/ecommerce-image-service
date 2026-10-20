import { chromium } from 'playwright-core'
import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve(process.cwd(), '..')
const SHOTS = path.join(ROOT, 'screenshots')
const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8001'
fs.mkdirSync(SHOTS, { recursive: true })

const config = await fetch(`${BASE_URL}/api/config`).then((response) => response.json())
if (!config.mock) {
  console.error(
    `拒绝运行 UI 冒烟：${BASE_URL} 未处于 mock 模式，继续操作会产生真实接口费用。` +
      ' 请用 IMAGE_MOCK=true 启动隔离测试服务，并设置 BASE_URL。',
  )
  process.exit(2)
}

const candidates = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean)
const executablePath = candidates.find((candidate) => fs.existsSync(candidate))
if (!executablePath) {
  throw new Error('未找到 Chrome/Edge，请设置 CHROME_PATH 环境变量')
}

const browser = await chromium.launch({
  headless: true,
  executablePath,
  args: ['--disable-gpu', '--font-render-hinting=none'],
})
const context = await browser.newContext({
  viewport: { width: 1440, height: 1080 },
  deviceScaleFactor: 1,
  locale: 'zh-CN',
})
const page = await context.newPage()
const errors = []
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(`console: ${msg.text()}`)
})
page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`))

await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' })
await page.waitForTimeout(900)
console.log('title:', await page.title())
console.log('hero:', (await page.locator('.page-hero h2').first().innerText()).replace(/\n/g, ' '))
console.log('workflow cards:', await page.locator('.workflow-card').count())
await page.screenshot({ path: path.join(SHOTS, 'studio-empty.png'), fullPage: true })

// Test workflow switching and styles.
await page.locator('.workflow-card').nth(1).click()
await page.waitForTimeout(250)
console.log('white-bg styles:', await page.locator('.style-option').count())
console.log('white-bg active:', await page.locator('.workflow-card.active .workflow-name').innerText())
await page.locator('.workflow-card').nth(0).click()

// Use the bundled three-view model sheet as an identity reference.
await page.getByRole('button', { name: /使用示例三视图模特/ }).click()
await page.waitForFunction(
  () => document.querySelectorAll('.upload-slot.has-asset').length >= 1,
  undefined,
  { timeout: 20_000 },
)
console.log('sample model uploaded:', await page.locator('.upload-slot.has-asset').count())

// Upload the sample garment into the first upload slot.
const fileInputs = page.locator('input[type=file]')
console.log('file inputs:', await fileInputs.count())
await fileInputs.first().setInputFiles(path.join(ROOT, 'samples', 'garment.png'))
await page.waitForTimeout(800)
await page.waitForFunction(
  () => {
    const btn = document.querySelector('.generate-btn')
    return btn && !btn.classList.contains('is-disabled') && !btn.hasAttribute('disabled')
  },
  undefined,
  { timeout: 15_000 },
)
console.log(
  'uploaded assets before generate:',
  await page.locator('.upload-slot.has-asset').count(),
)
await page.screenshot({ path: path.join(SHOTS, 'studio-ready.png'), fullPage: true })

await page.locator('.generate-btn').click()
await page.waitForSelector('.status-tag.is-success', { timeout: 30_000 })
await page.waitForTimeout(700)
console.log('result images:', await page.locator('.result-viewer img').count())
await page.screenshot({ path: path.join(SHOTS, 'studio-result.png'), fullPage: true })
const hideForStage = await page.addStyleTag({
  content: '.topbar{opacity:0!important}.el-message{display:none!important}',
})
await page.locator('.stage-card').screenshot({ path: path.join(SHOTS, 'result-stage.png') })
await hideForStage.evaluate((node) => node.remove())

// Targeted revision using the generated output as the edit target.
await page.getByRole('button', { name: /调整这张/ }).click()
await page.waitForSelector('.revision-dialog')
await page.waitForTimeout(400)
await page.getByRole('button', { name: /站姿太僵/ }).click()
await page.getByRole('button', { name: /开始调整/ }).click()
await page.waitForFunction(
  () =>
    Boolean(document.querySelector('.stage-head .revision-badge')) &&
    Boolean(document.querySelector('.status-tag.is-success')),
  undefined,
  { timeout: 30_000 },
)
await page.waitForTimeout(600)
console.log('revision badge:', await page.locator('.stage-head .revision-badge').count())
await page.screenshot({ path: path.join(SHOTS, 'studio-revision.png'), fullPage: true })

// Prompt dialog.
await page.getByRole('button', { name: /查看提示词/ }).click()
await page.waitForSelector('.prompt-preview')
await page.waitForTimeout(450)
console.log('prompt chars:', (await page.locator('.prompt-preview').innerText()).length)
await page.screenshot({ path: path.join(SHOTS, 'prompt-dialog.png') })
await page.locator('.el-dialog__headerbtn:visible').click()
await page.waitForTimeout(450)

// Five-shot series: exactly two product images -> five independent photos.
await page.locator('.workflow-card').filter({ hasText: '五图套图' }).click()
await page.waitForTimeout(300)
console.log('five-shot plan items:', await page.locator('.five-plan-item').count())
const fiveInputs = page.locator('input[type=file]')
console.log('five-shot file inputs:', await fiveInputs.count())
await fiveInputs.nth(0).setInputFiles(path.join(ROOT, 'samples', 'garment.png'))
await fiveInputs.nth(1).setInputFiles(path.join(ROOT, 'samples', 'garment-detail.png'))
await page.waitForFunction(
  () => document.querySelectorAll('.upload-slot.has-asset').length >= 2,
  undefined,
  { timeout: 20_000 },
)
await page.waitForFunction(
  () => {
    const btn = document.querySelector('.generate-btn')
    return btn && !btn.classList.contains('is-disabled') && !btn.hasAttribute('disabled')
  },
  undefined,
  { timeout: 15_000 },
)
await page.locator('.generate-btn').click()
await page.waitForFunction(
  () =>
    document.querySelectorAll('.result-thumbs button').length === 5 &&
    Boolean(document.querySelector('.status-tag.is-success')),
  undefined,
  { timeout: 45_000 },
)
await page.waitForTimeout(700)
console.log('five-shot outputs:', await page.locator('.result-thumbs button').count())
console.log('five-shot progress:', await page.locator('.stage-meta').innerText())
await page.screenshot({ path: path.join(SHOTS, 'studio-five.png'), fullPage: true })
await page.getByRole('button', { name: /查看提示词/ }).click()
await page.waitForSelector('.prompt-preview')
console.log('five-shot prompt chars:', (await page.locator('.prompt-preview').innerText()).length)
await page.locator('.el-dialog__headerbtn:visible').click()

// Gallery and detail / reuse.
await page.goto(`${BASE_URL}/gallery`, { waitUntil: 'networkidle' })
await page.waitForTimeout(700)
console.log('gallery cards:', await page.locator('.gallery-card').count())
await page.screenshot({ path: path.join(SHOTS, 'gallery.png'), fullPage: true })
await page.locator('.gallery-card').first().click()
await page.waitForSelector('.gallery-detail')
await page.waitForTimeout(450)
await page.screenshot({ path: path.join(SHOTS, 'gallery-detail.png') })
await page.getByRole('button', { name: /复用这组参数/ }).click()
await page.waitForURL(`${BASE_URL}/`)
await page.waitForFunction(
  () => document.querySelectorAll('.upload-slot.has-asset').length > 0,
  undefined,
  { timeout: 15_000 },
)
await page.waitForTimeout(500)
console.log('reuse uploaded assets:', await page.locator('.upload-slot.has-asset').count())
await page.screenshot({ path: path.join(SHOTS, 'studio-reuse.png'), fullPage: true })

// Jobs table / detail.
await page.goto(`${BASE_URL}/jobs`, { waitUntil: 'networkidle' })
await page.waitForTimeout(700)
console.log('job rows:', await page.locator('.job-row').count())
await page.screenshot({ path: path.join(SHOTS, 'jobs.png'), fullPage: true })
await page.locator('.job-row').first().click()
await page.waitForSelector('.job-detail')
await page.waitForTimeout(450)
await page.screenshot({ path: path.join(SHOTS, 'job-detail.png') })
await page.locator('.el-dialog__headerbtn:visible').click()

// Responsive check.
await page.setViewportSize({ width: 390, height: 844 })
await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' })
await page.waitForTimeout(700)
const overflow = await page.evaluate(() => ({
  scrollWidth: document.documentElement.scrollWidth,
  innerWidth: window.innerWidth,
}))
console.log('mobile overflow:', overflow)
await page.screenshot({ path: path.join(SHOTS, 'mobile-studio.png'), fullPage: true })

console.log('console errors:', errors.length ? errors : 'none')
fs.writeFileSync(
  path.join(SHOTS, 'ui-smoke.json'),
  JSON.stringify({ errors, overflow }, null, 2),
)
await browser.close()
