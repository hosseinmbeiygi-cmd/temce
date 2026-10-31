const { chromium } = require('playwright');
const _cp = require('child_process');
const execFileSync = _cp.execFileSync;

const BASE = 'http://127.0.0.1:3000';
const API = 'http://127.0.0.1:8000/api/v1';
const USER = 'audit_ui_storage_20261031';
const PASS = 'AuditStorage-20261031!';
const UID = 'usr_c443b9d595154fa1adebc6b4';
const out = {};

function db(sql) {
  return execFileSync('docker', ['exec', 'tse_timescaledb', 'psql', '-U', 'quant_dev', '-d', 'tse_quant_verify', '-At', '-F', '|', '-c', sql], { encoding: 'utf8' }).trim();
}

async function apiLogin() {
  const r = await fetch(API + '/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: USER, password: PASS }) });
  return (await r.json()).data.access_token;
}
async function apiGet(t, p) {
  const r = await fetch(API + p, { headers: { Authorization: 'Bearer ' + t } });
  return { status: r.status, body: await r.json().catch(() => null) };
}
async function poll(fn, ok, ms = 15000) {
  const t0 = Date.now(); let last = null;
  while (Date.now() - t0 < ms) { last = await fn(); if (ok(last)) return last; await new Promise((r) => setTimeout(r, 600)); }
  return last;
}

(async () => {
  const apiToken = await apiLogin();
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 }, serviceWorkers: 'block' });
  for (const p of ['**/api/v1/market/**', '**/api/v1/market-dashboard**', '**/api/v1/news**', '**/api/v1/economic-calendar**', '**/api/v1/brsapi/**']) await ctx.route(p, (r) => r.abort());
  const page = await ctx.newPage();
  const authNet = [];
  page.on('request', (r) => { if (r.url().includes('/auth/')) authNet.push('REQ ' + r.method() + ' ' + r.url().replace(BASE, '')); });
  page.on('response', (r) => { if (r.url().includes('/auth/')) authNet.push('RES ' + r.status() + ' ' + r.url().replace(BASE, '')); });

  // login
  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 35000 }).catch(() => {});

  await page.goto(BASE + '/gold/portfolio', { waitUntil: 'domcontentloaded' });
  for (let i = 0; i < 60; i++) {
    const ok = await page.evaluate(() => { const b = [...document.querySelectorAll('main button')][0]; return b ? Reflect.ownKeys(b).map(String).some((k) => /reactProps/.test(k)) : false; }).catch(() => false);
    if (ok) break; await page.waitForTimeout(1000);
  }
  await page.waitForTimeout(1500);

  out.logoutButtons = await page.evaluate(() =>
    [...document.querySelectorAll('button[aria-label]')].map((b) => ({
      label: b.getAttribute('aria-label'),
      visible: !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length),
      rect: (() => { const r = b.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })(),
    })).slice(0, 30),
  );

  // P&L display text
  out.pnlText = await page.evaluate(() => {
    const main = document.querySelector('main');
    const i = main.innerText.indexOf('P&L');
    return i < 0 ? null : main.innerText.slice(i, i + 180).replace(/\s+/g, ' ');
  });

  // DCA persistence after fresh login
  await page.getByRole('button', { name: 'پلن‌های DCA', exact: true }).click();
  await page.waitForTimeout(1200);
  const dcaText = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  out.dcaAfterFreshLogin = { hasName: dcaText.includes('AUD-UI-DCA-20261031'), shows1of3: dcaText.includes('اجرا: 1/3') };

  // logout via the real button
  const logoutBtn = page.locator('button[aria-label="خروج"]').first();
  out.logoutFound = (await logoutBtn.count()) > 0;
  if (out.logoutFound) {
    await logoutBtn.click();
    out.logout = { clicked: true };
    await page.waitForURL((u) => String(u).includes('/auth/login'), { timeout: 12000 }).catch(() => {});
    await page.waitForTimeout(3000);
    out.logout.url = page.url();
    out.logout.loginInputs = await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').count();
    out.logout.buttonText = await page.locator('button[aria-label="خروج"]').first().innerText().catch(() => null);
    if (out.logout.url.includes('/auth/login')) {
      const refresh = await page.evaluate(async () => {
        const r = await fetch('/api/v1/auth/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}', credentials: 'include' });
        return r.status;
      }).catch(() => null);
      out.logout.refreshAfterLogout = refresh;
    }
  }
  out.authNet = authNet;

  // login again (or continue) then verify portfolio
  if (!page.url().includes('/auth/login')) {
    await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
  }
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 35000 }).catch(() => {});
  await page.goto(BASE + '/gold/portfolio', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  await page.getByRole('button', { name: 'نمای کلی', exact: true }).last().click();
  await page.waitForTimeout(800);
  const ov = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  out.afterRealRelogin = { hasHolding: ov.includes('AUD-UI سکه تست'), qty2: ov.includes('2.00') };
  await page.screenshot({ path: 'audit_out/_tmp/w4_followup_portfolio.png', fullPage: true });

  // seed after all rules deleted
  await page.goto(BASE + '/gold/alerts', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  const before = (await apiGet(apiToken, '/gold/alerts/rules')).body?.data ?? [];
  await page.getByRole('button', { name: 'درج قوانین پیش‌فرض', exact: true }).click();
  const seededList = await poll(
    async () => (await apiGet(apiToken, '/gold/alerts/rules')).body?.data,
    (d) => (d ?? []).length > before.length,
  );
  out.seedAfterDelete = { before: before.length, after: (seededList ?? []).length, names: (seededList ?? []).map((r) => r.name) };
  out.seededRuleIds = (seededList ?? []).map((r) => r.id);

  // cleanup seeded rules via API (test-created, non-AUD-UI names but ours)
  for (const r of seededList ?? []) {
    await fetch(API + '/gold/alerts/rules/' + r.id, { method: 'DELETE', headers: { Authorization: 'Bearer ' + apiToken } });
  }
  out.seedCleanupRemaining = db(`select count(*) from gold_alert_rules where user_id='${UID}'`);

  // metrics-scope token probe (API only, not UI)
  const cr = await fetch(API + `/gold/tokens?name=${encodeURIComponent('AUD-UI-TOKEN-METRICS')}&scopes=metrics`, { method: 'POST', headers: { Authorization: 'Bearer ' + apiToken } });
  const crj = await cr.json();
  const mTok = crj?.data?.token;
  const mId = crj?.data?.token_id;
  out.metricsToken = { created: Boolean(mTok), status: cr.status };
  if (mTok) {
    const m = await fetch(API + '/gold/metrics', { headers: { Authorization: 'Bearer ' + mTok } });
    out.metricsToken.metricsStatus = m.status;
    await fetch(API + '/gold/tokens/' + mId, { method: 'DELETE', headers: { Authorization: 'Bearer ' + apiToken } });
    const after = await fetch(API + '/gold/metrics', { headers: { Authorization: 'Bearer ' + mTok } });
    out.metricsToken.metricsAfterRevoke = after.status;
  }

  console.log(JSON.stringify(out, null, 2));
  await browser.close();
 })().catch((e) => { console.error('FATAL', e); console.log(JSON.stringify(out, null, 2)); process.exit(1); });
