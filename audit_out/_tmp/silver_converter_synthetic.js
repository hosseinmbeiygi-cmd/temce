const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const USER = process.env.AUDIT_UI_USER;
const PASS = process.env.AUDIT_UI_PASS;

const json = (obj) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(obj) });

// Clearly synthetic, identifiable fixture data — never written to any DB.
const LATEST = [
  { symbol: 'XAGUSD', name: 'SILVER FAKE', price: 30, change_percent: 1.5, date: '2026/10/30', time_unix: 1790000000 },
  { symbol: 'XAUUSD', name: 'GOLD FAKE', price: 2400, change_percent: -0.4, date: '2026/10/30', time_unix: 1790000000 },
];
const HISTORY = [
  { symbol: 'XAGUSD', price: 28, date: '2026/10/28', time_unix: 1790000000 },
  { symbol: 'XAGUSD', price: 29, date: '2026/10/29', time_unix: 1790000100 },
  { symbol: 'XAGUSD', price: 30, date: '2026/10/30', time_unix: 1790000200 },
];
const USD = [{ symbol: 'USD', price: 600000, date: '2026/10/30' }];
const FUTURES = [
  {
    contract_code: 'SILVER_FAKE',
    contract_description: 'قرارداد آزمایشی نقره',
    contract_size: 1000,
    contract_size_unit: 'گرم',
    price_last: 9000000,
    price_last_change_pct: 2,
    trade_volume: 123,
    price_last_settlement: 8950000,
    date_update: '2026/10/30',
  },
];

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 } });
  const page = await ctx.newPage();

  await ctx.route('**/api/v1/brsapi/commodities?*', (route) => {
    const u = route.request().url();
    return route.fulfill(json({ success: true, data: u.includes('latest_only=true') ? LATEST : HISTORY }));
  });
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
  await page.waitForTimeout(2500);

  const out = {};
  out.hero = await page.evaluate(() => {
    const body = document.body.innerText.replace(/\s+/g, ' ');
    const grab = (label) => {
      const i = body.indexOf(label);
      return i < 0 ? null : body.slice(i, i + 80);
    };
    return {
      header: grab('آخرین به‌روزرسانی'),
      xag: grab('انس جهانی نقره (XAG/USD)'),
      gram: grab('نقره گرمی (آتی IME)'),
      usd: grab('دلار آمریکا'),
      funds: grab('صندوق‌های نقره / کالایی'),
      futures: grab('قراردادهای آتی نقره'),
      status: grab('وضعیت لحظه‌ای'),
    };
  });

  const grams = page.locator('input[placeholder="گرم"]:visible').first();
  const converterText = async () => {
    const sec = grams.locator('xpath=ancestor::div[contains(@class,"rounded-2xl")][1]');
    return (await sec.innerText()).replace(/\s+/g, ' ');
  };
  out.converter = {};
  for (const v of ['10', '31.1035', '0', 'abc', '']) {
    await grams.fill(v);
    await page.waitForTimeout(300);
    out.converter[v === '' ? 'empty' : v] = await converterText();
  }

  // hand-computed references
  out.reference = {
    usd10: (10 / 31.1035) * 30,
    irr10: (10 / 31.1035) * 30 * 600000,
    usd1oz: (31.1035 / 31.1035) * 30,
    irr1oz: (31.1035 / 31.1035) * 30 * 600000,
  };

  // futures tab should show the synthetic contract
  await page.getByRole('button', { name: 'آتی (IME)', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(1200);
  out.futuresTab = await page.evaluate(() => ({
    rows: document.querySelectorAll('main table tbody tr').length,
    code: (document.querySelector('main table tbody tr')?.innerText || '').replace(/\s+/g, ' ').slice(0, 140),
    error: document.body.innerText.includes('دریافت قراردادهای آتی ناموفق بود'),
  }));

  // ML tab + search filter (give queries time)
  await page.getByRole('button', { name: 'هوش مصنوعی', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(4000);
  out.ml = await page.evaluate(() => ({
    bodyExcerpt: document.body.innerText.replace(/\s+/g, ' ').slice(0, 200),
    rows: document.querySelectorAll('main table tbody tr').length,
    runsHeading: document.body.innerText.includes('اجراهای آموزش'),
    modelEmpty: document.body.innerText.includes('مدلی در سرویس ML ثبت نشده است'),
  }));
  const search = page.locator('input[placeholder^="جستجو: نام مدل"]:visible').first();
  if (await search.count()) {
    const before = await page.locator('main table tbody tr').count();
    await search.fill('__no_such_model__');
    await page.waitForTimeout(800);
    const after = await page.locator('main table tbody tr').count();
    out.ml.searchFilter = { rowsBefore: before, rowsAfter: after };
  }

  // forecast tab: wait for its queries to settle, then capture state
  await page.getByRole('button', { name: 'پیش‌بینی', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(6000);
  out.forecast = await page.evaluate(() => ({
    skeletons: document.querySelectorAll('main .animate-pulse').length,
    unavailable: document.body.innerText.includes('پیش‌بینی در دسترس نیست'),
    horizonDisabled: [...document.querySelectorAll('button')].filter((b) => /روز/.test(b.innerText)).map((b) => b.disabled),
    advice: document.body.innerText.includes('احتمال جهت از مدل نرسیده'),
  }));

  console.log(JSON.stringify(out, null, 2));
  await page.screenshot({ path: 'audit_out/_tmp/silver_synthetic.png', fullPage: true });
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
