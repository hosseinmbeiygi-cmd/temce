const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe' });
  const page = await (await browser.newContext({ viewport: { width: 1680, height: 1400 } })).newPage();
  const net = [];
  page.on('response', (r) => { if (r.url().includes('/api/v1/ml/')) net.push(r.status() + ' ' + r.url().replace(BASE, '')); });
  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(process.env.AUDIT_UI_USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(process.env.AUDIT_UI_PASS);
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
  await page.getByRole('button', { name: 'هوش مصنوعی', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(8000);
  const out = await page.evaluate(() => ({
    url: location.href,
    rows: document.querySelectorAll('main table tbody tr').length,
    runsText: (document.querySelector('main table tbody')?.innerText || '').replace(/\s+/g, ' ').slice(0, 200),
    modelEmpty: document.body.innerText.includes('مدلی در سرویس ML ثبت نشده است'),
  }));
  const search = page.locator('input[placeholder^="جستجو: نام مدل"]:visible').first();
  out.searchPresent = (await search.count()) > 0;
  if (out.searchPresent) {
    await search.fill('__no_such_model__');
    await page.waitForTimeout(800);
    out.afterFilter = await page.evaluate(() => ({
      rows: document.querySelectorAll('main table tbody tr').length,
      emptyRunMsg: document.body.innerText.includes('اجرای آموزشی ثبت نشده است'),
      emptyModelMsg: document.body.innerText.includes('مدلی در سرویس ML ثبت نشده است'),
    }));
    await search.fill('');
    await page.waitForTimeout(800);
    out.afterClear = await page.evaluate(() => document.querySelectorAll('main table tbody tr').length);
  }
  out.mlNet = net;
  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
