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
  const bad = [];
  const failed = [];
  page.on('response', (r) => {
    if (r.status() >= 400) bad.push(r.status() + ' ' + r.request().method() + ' ' + r.url());
  });
  page.on('requestfailed', (r) => failed.push((r.failure()?.errorText || 'failed') + ' ' + r.url()));

  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});

  await page.goto(BASE + '/markets/silver', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(15000);

  const info = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('nav button')].find((b) => b.innerText.trim() === 'پیش‌بینی');
    const main = document.querySelector('main');
    const html = document.documentElement.outerHTML;
    return {
      readyState: document.readyState,
      nextF: Array.isArray(self.__next_f) ? self.__next_f.length : null,
      reactKeysOnTab: btn ? Reflect.ownKeys(btn).map(String).filter((k) => /react/i.test(k)) : [],
      reactKeysOnMain: main ? Reflect.ownKeys(main).map(String).filter((k) => /react/i.test(k)) : [],
      main: main
        ? {
            textLen: main.innerText.replace(/\s+/g, ' ').length,
            scrollHeight: main.scrollHeight,
            clientHeight: main.clientHeight,
            overflow: getComputedStyle(main).overflow,
            contentVisibility: getComputedStyle(main).contentVisibility,
            rect: (() => {
              const r = main.getBoundingClientRect();
              return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)];
            })(),
          }
        : null,
      hiddenDescendants: document.querySelectorAll('main [hidden]').length,
      cvAuto: [...document.querySelectorAll('main *')].filter((e) => getComputedStyle(e).contentVisibility === 'auto').length,
      htmlHasConverter: html.includes('مبدل سریع'),
      htmlHasRulesLoading: html.includes('spec-rules-loading'),
      htmlHasForecast: html.includes('پیش‌بینی انس جهانی نقره'),
      htmlHasChartHint: html.includes('نمودار انس جهانی نقره'),
      scriptChunkCount: document.querySelectorAll('script[src*="_next/static/chunks"]').length,
      styleSheets: document.styleSheets.length,
      buttonHeight: btn ? Math.round(btn.getBoundingClientRect().height) : null,
      paddingTop: btn ? getComputedStyle(btn).paddingTop : null,
    };
  });

  console.log(JSON.stringify({ info, bad, failed }, null, 2));

  // Try a real user-like interaction on the converter to see if state updates
  const conv = page.locator('input[placeholder="گرم"]').first();
  const hasConv = (await conv.count()) > 0;
  let typed = null;
  if (hasConv) {
    await conv.fill('5');
    typed = await conv.inputValue();
  }
  console.log('CONVERTER_PRESENT', hasConv, 'VALUE_AFTER_FILL', typed);

  await page.screenshot({ path: 'audit_out/_tmp/silver_diag_view.png', fullPage: false });
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
