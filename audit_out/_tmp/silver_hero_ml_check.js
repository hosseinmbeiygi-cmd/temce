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

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 } });
  const page = await ctx.newPage();
  await ctx.route('**/api/v1/brsapi/commodities?*', (route) =>
    route.fulfill(json({ success: true, data: route.request().url().includes('latest_only=true') ? LATEST : HISTORY })));
  await ctx.route('**/api/v1/brsapi/currency', (route) => route.fulfill(json({ success: true, data: USD })));
  await ctx.route('**/api/v1/gold/ime/futures', (route) => route.fulfill(json({ success: true, data: FUTURES })));

  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 35000 }).catch(() => {});

  await page.goto(BASE + '/markets/silver', { waitUntil: 'domcontentloaded' });
  for (let i = 0; i < 40; i++) {
    const ok = await page.evaluate(() => {
      const b = [...document.querySelectorAll('nav button')].find((x) => x.innerText.trim() === 'پیش‌بینی');
      return b ? Reflect.ownKeys(b).map(String).some((k) => /reactProps/i.test(k)) : false;
    });
    if (ok) break;
    await page.waitForTimeout(1000);
  }
  await page.waitForTimeout(2000);

  const out = {};
  out.heroCards = await page.evaluate(() => {
    const main = document.querySelector('main');
    const cards = [...main.querySelectorAll('.grid > div')].filter((d) => /انس جهانی نقره|نقره گرمی|دلار آمریکا|صندوق‌های نقره|قراردادهای آتی/.test(d.innerText));
    return cards.map((c) => c.innerText.replace(/\s+/g, ' ').trim()).slice(0, 6);
  });
  out.header = await page.evaluate(() => {
    const main = document.querySelector('main');
    const p = [...main.querySelectorAll('p')].find((x) => x.innerText.includes('آخرین به‌روزرسانی'));
    return p ? p.innerText.replace(/\s+/g, ' ') : null;
  });
  out.sections = await page.evaluate(() => ({
    mainSections: document.querySelectorAll('main section').length,
    gauge: document.body.innerText.includes('مبدل سریع'),
  }));

  // ML filter with generous settle
  await page.getByRole('button', { name: 'هوش مصنوعی', exact: true }).filter({ visible: true }).first().click();
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(2500);
  out.ml = await page.evaluate(() => ({
    rows: document.querySelectorAll('main table tbody tr').length,
    runs: document.querySelector('main table tbody')?.innerText.replace(/\s+/g, ' ').slice(0, 220) || null,
  }));
  const search = page.locator('input[placeholder^="جستجو: نام مدل"]:visible').first();
  if (await search.count()) {
    await search.fill('__no_such_model__');
    await page.waitForTimeout(800);
    out.ml.filtered = {
      rows: await page.locator('main table tbody tr').count(),
      bodyHasNoMatch: (await page.locator('main').innerText()).includes('__no_such_model__'),
    };
    await search.fill('');
    await page.waitForTimeout(500);
    out.ml.afterClear = await page.locator('main table tbody tr').count();
  }

  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
