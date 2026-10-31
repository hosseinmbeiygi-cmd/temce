const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const USER = process.env.AUDIT_UI_USER;
const PASS = process.env.AUDIT_UI_PASS;

const TABS = [
  ['overview', 'نمای کلی'],
  ['forecast', 'پیش‌بینی'],
  ['funds', 'صندوق‌ها'],
  ['futures', 'آتی (IME)'],
  ['backtest', 'بک‌تست'],
  ['ml', 'هوش مصنوعی'],
  ['news', 'اخبار'],
];

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 } });
  const page = await ctx.newPage();
  const responses = [];
  page.on('response', (r) => {
    const u = r.url();
    if (u.includes('/api/v1/')) responses.push({ t: Date.now(), s: r.status(), u: u.replace(BASE, '') });
  });

  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 35000 }).catch(() => {});

  await page.goto(BASE + '/markets/silver', { waitUntil: 'domcontentloaded' });
  for (let i = 0; i < 50; i++) {
    const ok = await page.evaluate(() => {
      const b = [...document.querySelectorAll('nav button')].find((x) => x.innerText.trim() === 'پیش‌بینی');
      return b ? Reflect.ownKeys(b).map(String).some((k) => /reactProps/i.test(k)) : false;
    });
    if (ok) break;
    await page.waitForTimeout(2000);
  }
  await page.waitForLoadState('networkidle', { timeout: 40000 }).catch(() => {});

  const out = {};
  for (const [id, label] of TABS) {
    const before = responses.length;
    await page.getByRole('button', { name: label, exact: true }).filter({ visible: true }).first().click();
    await page.waitForTimeout(1000);
    await page.waitForLoadState('networkidle', { timeout: 25000 }).catch(() => {});
    const data = await page.evaluate(() => {
      const body = document.body.innerText.replace(/\s+/g, ' ');
      const main = document.querySelector('main');
      const mtext = (main?.innerText || '').replace(/\s+/g, ' ');
      const bodyAt = (needle) => body.includes(needle);
      return {
        bodyLen: body.length,
        mainLen: mtext.length,
        mainScrollHeight: main?.scrollHeight ?? null,
        mainClientHeight: main?.clientHeight ?? null,
        bodyHasMainText: body.includes(mtext.slice(-80)),
        active: [...document.querySelectorAll('nav button')].filter((b) => b.className.includes('bg-primary-600')).map((b) => b.innerText.trim()).filter((t) => t !== 'smart_toy'),
        tables: document.querySelectorAll('main table').length,
        rows: document.querySelectorAll('main table tbody tr').length,
        skeletons: document.querySelectorAll('main .animate-pulse').length,
        texts: {
          banner: bodyAt('بخشی از داده‌های نقره دریافت نشد'),
          forecastUnavailable: bodyAt('پیش‌بینی در دسترس نیست'),
          fundsEmpty: bodyAt('صندوق نقره‌ای در API موجود نیست'),
          fundsError: bodyAt('دریافت صندوق‌ها ناموفق بود'),
          futuresEmpty: bodyAt('قرارداد آتی نقره‌ای در API موجود نیست'),
          futuresError: bodyAt('دریافت قراردادهای آتی ناموفق بود'),
          mlEmpty: bodyAt('مدلی در سرویس ML ثبت نشده است'),
          mlRunsHeading: bodyAt('اجراهای آموزش'),
          newsEmpty: bodyAt('خبری با کلیدواژهٔ نقره یافت نشد'),
          newsError: bodyAt('دریافت اخبار ناموفق بود'),
          backtestForm: bodyAt('بک‌تست استراتژی روی نماد نقره'),
          chartEmpty: bodyAt('داده تاریخی روزانه XAG برای نمودار موجود نیست'),
          rulesLoaded: !!document.querySelector('[data-testid="spec-filter-thresholds"]'),
          rulesLoading: !!document.querySelector('[data-testid="spec-rules-loading"]'),
          converter: (() => {
            const s = body.indexOf('مبدل سریع');
            return s >= 0 ? body.slice(s, s + 180) : null;
          })(),
        },
      };
    });
    data.requests = responses.slice(before).map((x) => x.s + ' ' + x.u);
    out[id] = data;
  }

  console.log(JSON.stringify(out, null, 2));
  await page.screenshot({ path: 'audit_out/_tmp/silver_tabs_final.png', fullPage: true });
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
