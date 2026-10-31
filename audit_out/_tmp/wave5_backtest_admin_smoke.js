const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const ADMIN = 'audit_ui_admin_20261030_a1';
const USER = 'audit_ui_user_20261030_u1';
const PASS = 'AuditUi-20261030!';

const BACKTEST_ROUTES = [
  '/backtest',
  '/backtest/adaptive',
  '/backtest/cascade',
  '/backtest/compose',
  '/backtest/decision',
  '/backtest/engine',
  '/backtest/full-scan',
  '/backtest/generate',
  '/backtest/methods',
  '/backtest/monte-carlo',
  '/backtest/walk-forward',
];
const ADMIN_ROUTES = ['/admin', '/admin/users', '/sync-manager', '/data-import'];

async function waitHydrated(page, maxSec = 45) {
  for (let i = 0; i < maxSec; i++) {
    const ok = await page.evaluate(() => {
      const b = [...document.querySelectorAll('main button, main input, main select')][0];
      return b ? Reflect.ownKeys(b).map(String).some((k) => /reactProps/.test(k)) : false;
    }).catch(() => false);
    if (ok) return i;
    await page.waitForTimeout(1000);
  }
  return -1;
}

async function login(page, username) {
  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(username);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(2000);
}

async function inspect(page, route) {
  const bad = [];
  const onResp = (r) => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.request().method() + ' ' + r.url().replace(BASE, '')); };
  page.on('response', onResp);
  const consoleErrors = [];
  const onErr = (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 160)); };
  page.on('console', onErr);
  await page.goto(BASE + route, { waitUntil: 'domcontentloaded' });
  const waited = await waitHydrated(page, 45);
  await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(1200);
  const data = await page.evaluate(() => {
    const main = document.querySelector('main');
    const text = (main?.innerText || '').replace(/\s+/g, ' ');
    const body = document.body.innerText.replace(/\s+/g, ' ');
    const h = main?.querySelector('h1, h2, h3')?.textContent?.trim() ?? null;
    return {
      url: location.href,
      heading: h,
      bodyLen: body.length,
      buttons: main ? main.querySelectorAll('button').length : 0,
      inputs: main ? main.querySelectorAll('input').length : 0,
      selects: main ? main.querySelectorAll('select').length : 0,
      tables: main ? main.querySelectorAll('table').length : 0,
      svgs: main ? main.querySelectorAll('svg').length : 0,
      hasErrorText: /خطا|ناموفق|در دسترس نیست|Internal error|HTTP 5\d\d/.test(text),
      excerpt: text.slice(0, 220),
    };
  });
  data.hydrateWaitSec = waited;
  data.badResponses = [...new Set(bad)].slice(0, 8);
  data.consoleErrors = [...new Set(consoleErrors)].slice(0, 5);
  page.off('response', onResp);
  page.off('console', onErr);
  return data;
}

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe' });
  const out = { fixedLoginMessage: {}, backtest: {}, admin: {}, normalUser: {}, errors: [] };
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 }, serviceWorkers: 'block' });
  // Shell-only slow calls; keep APIs the pages under test may need.
  for (const p of ['**/api/v1/market/enriched-heatmap**', '**/api/v1/market-dashboard**', '**/api/v1/news**']) await ctx.route(p, (r) => r.abort());
  const page = await ctx.newPage();

  // wrong password after the F1 fix
  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(ADMIN);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('definitely-wrong');
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForTimeout(2500);
  out.fixedLoginMessage = {
    url: page.url(),
    text: (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 300),
  };

  await login(page, ADMIN);

  for (const route of BACKTEST_ROUTES) {
    out.backtest[route] = await inspect(page, route);
  }
  for (const route of ADMIN_ROUTES) {
    out.admin[route] = await inspect(page, route);
  }

  // normal user hitting an admin page
  const ctx2 = await browser.newContext({ viewport: { width: 1680, height: 1400 }, serviceWorkers: 'block' });
  for (const p of ['**/api/v1/market/enriched-heatmap**', '**/api/v1/market-dashboard**', '**/api/v1/news**']) await ctx2.route(p, (r) => r.abort());
  const page2 = await ctx2.newPage();
  await login(page2, USER);
  await page2.goto(BASE + '/admin', { waitUntil: 'domcontentloaded' });
  await page2.waitForTimeout(6000);
  out.normalUser = {
    url: page2.url(),
    text: (await page2.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 300),
  };

  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
