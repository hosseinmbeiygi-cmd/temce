const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const USER = process.env.AUDIT_UI_USER;
const PASS = process.env.AUDIT_UI_PASS;
const json = (obj) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(obj) });

const LATEST = [
  { symbol: 'XAGUSD', name: 'SILVER FAKE', price: 30, change_percent: 1.5, date: '2026/10/30', time_unix: 1790000000 },
];
const HISTORY = [
  { symbol: 'XAGUSD', price: 28, date: '2026/10/28', time_unix: 1790000000 },
  { symbol: 'XAGUSD', price: 29, date: '2026/10/29', time_unix: 1790000100 },
  { symbol: 'XAGUSD', price: 30, date: '2026/10/30', time_unix: 1790000200 },
];
const USD = [{ symbol: 'USD', price: 600000, date: '2026/10/30' }];
const FUTURES = [{
  contract_code: 'SILVER_FAKE', contract_description: 'قرارداد آزمایشی نقره',
  contract_size: 1000, contract_size_unit: 'گرم', price_last: 9000000,
  price_last_change_pct: 2, trade_volume: 123, price_last_settlement: 8950000, date_update: '2026/10/30',
}];

async function login(page) {
  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 35000 }).catch(() => {});
}

async function waitHidrated(page) {
  for (let i = 0; i < 50; i++) {
    const ok = await page.evaluate(() => {
      const b = [...document.querySelectorAll('nav button')].find((x) => x.innerText.trim() === 'پیش‌بینی');
      return b ? Reflect.ownKeys(b).map(String).some((k) => /reactProps/i.test(k)) : false;
    });
    if (ok) return true;
    await page.waitForTimeout(1000);
  }
  return false;
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe',
  });
  const out = {};

  // ── A) synthetic price/converter/hero (service worker disabled) ──
  {
    const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 }, serviceWorkers: 'block' });
    const page = await ctx.newPage();
    let hits = 0;
    await page.route('**/api/v1/brsapi/commodities?*', (route) => {
      hits++;
      return route.fulfill(json({ success: true, data: route.request().url().includes('latest_only=true') ? LATEST : HISTORY }));
    });
    await page.route('**/api/v1/brsapi/currency', (route) => { hits++; return route.fulfill(json({ success: true, data: USD })); });
    await page.route('**/api/v1/gold/ime/futures', (route) => { hits++; return route.fulfill(json({ success: true, data: FUTURES })); });
    await login(page);
    await page.goto(BASE + '/markets/silver', { waitUntil: 'domcontentloaded' });
    out.hydratedA = await waitHidrated(page);
    await page.waitForTimeout(2500);

    out.A = await page.evaluate(() => {
      const main = document.querySelector('main');
      const hero = main?.querySelector('section .grid');
      const cards = hero ? [...hero.children].map((c) => c.innerText.replace(/\s+/g, ' ').trim()) : [];
      const headerP = [...main.querySelectorAll('p')].find((x) => x.innerText.includes('آخرین به‌روزرسانی'));
      return {
        heroCards: cards,
        header: headerP ? headerP.innerText.replace(/\s+/g, ' ') : null,
        chartHint: document.body.innerText.includes('کمینه بسته‌شدن') ? 'stats-shown' : 'stats-hidden',
      };
    });
    out.A.routeHits = hits;
    out.A.converter = {};
    const grams = page.locator('input[placeholder="گرم"]:visible').first();
    for (const v of ['10', '31.1035']) {
      await grams.fill(v);
      await page.waitForTimeout(300);
      const sec = grams.locator('xpath=ancestor::div[contains(@class,"rounded-2xl")][1]');
      out.A.converter[v] = (await sec.innerText()).replace(/\s+/g, ' ');
    }
    await ctx.close();
  }

  // ── B) ML tab with real API (service worker disabled) ──
  {
    const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 }, serviceWorkers: 'block' });
    const page = await ctx.newPage();
    const mlNet = [];
    page.on('response', (r) => {
      if (r.url().includes('/api/v1/ml/')) mlNet.push(r.status() + ' ' + r.url().replace(BASE, ''));
    });
    await login(page);
    await page.goto(BASE + '/markets/silver', { waitUntil: 'domcontentloaded' });
    await waitHidrated(page);
    await page.getByRole('button', { name: 'هوش مصنوعی', exact: true }).filter({ visible: true }).first().click();
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
    out.B = await page.evaluate(() => ({
      rows: document.querySelectorAll('main table tbody tr').length,
      runsHeading: document.body.innerText.includes('اجراهای آموزش'),
      modelsCount: document.body.innerText.includes('مدلی در سرویس ML ثبت نشده است') ? 0 : null,
      bodyHasML: document.body.innerText.includes('مدل‌های یادگیری ماشین و اجراهای آموزش'),
    }));
    out.B.mlNet = mlNet;
    const search = page.locator('input[placeholder^="جستجو: نام مدل"]:visible').first();
    if (await search.count()) {
      const before = await page.locator('main table tbody tr').count();
      await search.fill('__no_such_model__');
      await page.waitForTimeout(800);
      const after = await page.locator('main table tbody tr').count();
      const emptyMsg = await page.evaluate(() =>
        document.body.innerText.includes('اجرای آموزشی ثبت نشده است') ||
        document.body.innerText.includes('مدلی در سرویس ML ثبت نشده است'));
      await search.fill('');
      await page.waitForTimeout(800);
      const restored = await page.locator('main table tbody tr').count();
      out.B.search = { before, after, emptyMsg, restored };
    }
    await ctx.close();
  }

  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
