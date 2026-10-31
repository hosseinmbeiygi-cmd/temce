const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const USER = process.env.AUDIT_UI_USER;
const PASS = process.env.AUDIT_UI_PASS;

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 } });
  const page = await ctx.newPage();
  const started = new Map();
  const done = new Map();
  page.on('request', (r) => started.set(r, Date.now()));
  page.on('requestfinished', (r) => done.set(r, Date.now()));
  page.on('requestfailed', (r) => done.set(r, Date.now()));

  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});

  await page.goto(BASE + '/markets/silver', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(15000);

  const now = Date.now();
  const pending = [...started.entries()]
    .filter(([r]) => !done.has(r))
    .map(([r, t]) => ({ url: r.url(), type: r.resourceType(), ageMs: now - t }));
  const resources = await page.evaluate(() =>
    performance.getEntriesByType('resource').map((e) => ({
      name: e.name.replace('http://127.0.0.1:3000', ''),
      type: e.initiatorType,
      duration: Math.round(e.duration),
      size: e.transferSize,
    })),
  );
  const state = await page.evaluate(() => ({
    readyState: document.readyState,
    dcl: performance.timing.domContentLoadedEventEnd
      ? performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart
      : null,
    loadEnd: performance.timing.loadEventEnd
      ? performance.timing.loadEventEnd - performance.timing.navigationStart
      : null,
    tabReact: (() => {
      const b = [...document.querySelectorAll('nav button')].find((x) => x.innerText.trim() === 'پیش‌بینی');
      return b ? Reflect.ownKeys(b).map(String).filter((k) => /react/i.test(k)) : null;
    })(),
  }));
  console.log(JSON.stringify({ state, pending, resources: resources.filter((r) => r.type === 'script').slice(-30) }, null, 2));
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
