const { chromium } = require('playwright');
const { execFileSync } = require('child_process');

const BASE = 'http://127.0.0.1:3000';
const API = 'http://127.0.0.1:8000/api/v1';
const USER = 'audit_ui_storage_20261031';
const PASS = 'AuditStorage-20261031!';
const UID = 'usr_c443b9d595154fa1adebc6b4';

const HOLD_SYMBOL = 'AUD-UI-COIN-STORAGE';
const HOLD_NAME = 'AUD-UI سکه تست';
const HOLD_NOTE = 'AUD-UI-HOLDING-20261031';
const DCA_NAME = 'AUD-UI-DCA-20261031';
const ALERT_NAME = 'AUD-UI-ALERT-20261031';
const ALERT_SYMBOL = 'AUD-UI-SYM';
const EVENT_MSG = 'AUD-UI-EVENT-20261031';
const TOKEN_NAME = 'AUD-UI-TOKEN-20261031';

const out = { startedAt: new Date().toISOString(), phases: {}, ids: {}, errors: [] };
const secret = { token: null };

function db(sql) {
  return execFileSync(
    'docker',
    ['exec', 'tse_timescaledb', 'psql', '-U', 'quant_dev', '-d', 'tse_quant_verify', '-At', '-F', '|', '-c', sql],
    { encoding: 'utf8' },
  ).trim();
}

function redis(args) {
  return execFileSync('docker', ['exec', '-e', 'REDISCLI_AUTH', 'tse_redis', 'redis-cli', ...args], {
    encoding: 'utf8',
    env: process.env,
  }).trim();
}

async function apiLogin() {
  const r = await fetch(API + '/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USER, password: PASS }),
  });
  const j = await r.json();
  if (!j?.data?.access_token) throw new Error('api login failed: ' + JSON.stringify(j).slice(0, 300));
  return j.data.access_token;
}

async function apiGet(token, path) {
  const r = await fetch(API + path, { headers: { Authorization: 'Bearer ' + token } });
  const text = await r.text();
  let body = null;
  try { body = JSON.parse(text); } catch { body = text.slice(0, 200); }
  return { status: r.status, body };
}

async function poll(fn, ok, timeoutMs = 20000, step = 700) {
  const t0 = Date.now();
  let last = null;
  while (Date.now() - t0 < timeoutMs) {
    last = await fn();
    if (ok(last)) return last;
    await new Promise((r) => setTimeout(r, step));
  }
  return last;
}

async function waitHydrated(page, maxSec = 60) {
  for (let i = 0; i < maxSec; i++) {
    const ok = await page
      .evaluate(() => {
        const b = [...document.querySelectorAll('main button')][0];
        return b ? Reflect.ownKeys(b).map(String).some((k) => /reactProps/.test(k)) : false;
      })
      .catch(() => false);
    if (ok) return i;
    await page.waitForTimeout(1000);
  }
  return -1;
}

async function ensureHydrated(page, tries = 2) {
  for (let t = 0; t < tries; t++) {
    const waited = await waitHydrated(page, 60);
    if (waited >= 0) return { ok: true, waited, url: page.url() };
    await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(2500);
  }
  return { ok: false, waited: -1, url: page.url() };
}

async function reloadPage(page) {
  await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForTimeout(2500);
  const r = await ensureHydrated(page, 2);
  await settle(page);
  return r;
}

async function settle(page) {
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(800);
}

async function uiLogin(page) {
  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 35000 }).catch(() => {});
}

async function navigate(page, path) {
  await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
  const r = await ensureHydrated(page, 2);
  await settle(page);
  return r;
}

async function logout(page) {
  const btn = page.locator('button[aria-label="خروج"]:visible').first();
  if (await btn.count()) {
    await btn.click();
    await page.waitForURL((u) => String(u).includes('/auth/login'), { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1500);
    return true;
  }
  return false;
}

(async () => {
  const apiToken = await apiLogin();
  // Preflight: remove only this test user's previously-aborted AUD-UI rows so a
  // rerun starts clean. User was created solely for this wave.
  db(`delete from gold_trades where user_id='${UID}' and symbol='${HOLD_SYMBOL}'`);
  db(`delete from gold_holdings where user_id='${UID}' and symbol='${HOLD_SYMBOL}'`);
  db(`delete from gold_dca_plans where user_id='${UID}' and name='${DCA_NAME}'`);
  db(`delete from gold_alert_events where user_id='${UID}' and message='${EVENT_MSG}'`);
  db(`delete from gold_alert_rules where user_id='${UID}' and name <> '${ALERT_NAME}'`);
  db(`delete from gold_alert_rules where user_id='${UID}' and name='${ALERT_NAME}'`);
  out.preflight = {
    holdings: db(`select count(*) from gold_holdings where user_id='${UID}'`),
    trades: db(`select count(*) from gold_trades where user_id='${UID}'`),
    plans: db(`select count(*) from gold_dca_plans where user_id='${UID}'`),
    rules: db(`select count(*) from gold_alert_rules where user_id='${UID}'`),
  };
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe',
  });
  // The GoldDesk service worker (scope /gold) cache-firsts HTML and causes an
  // infinite reload loop on /gold/* reloads (see W4 finding). Disable SW for the
  // storage test; the loop itself is reported as evidence, not worked around.
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 }, serviceWorkers: 'block' });
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: BASE });
  // Isolate the pages under test: the global shell's slow market/news calls are
  // unrelated to storage and otherwise occupy all six HTTP/1.1 sockets, which
  // prevents the page's own JS chunks from loading (test-environment artifact).
  for (const pattern of [
    '**/api/v1/market/**',
    '**/api/v1/market-dashboard**',
    '**/api/v1/news**',
    '**/api/v1/economic-calendar**',
    '**/api/v1/brsapi/**',
  ]) {
    await ctx.route(pattern, (route) => route.abort());
  }
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message.slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });

  await uiLogin(page);
  out.login = { url: page.url() };

  // ═══════════════ PORTFOLIO ═══════════════
  const pf = {};
  pf.hydrateWaitSec = await navigate(page, '/gold/portfolio');

  // add holding
  await page.getByRole('button', { name: 'ثبت خرید', exact: true }).first().click();
  await page.locator('input[placeholder="IR_COIN_EMAMI"]:visible').fill(HOLD_SYMBOL);
  await page.locator('input[placeholder="نام"]:visible').fill(HOLD_NAME);
  await page.locator('main select:visible').first().selectOption('coin');
  await page.locator('input[placeholder="تعداد"]:visible').fill('2');
  await page.locator('input[placeholder="قیمت خرید (ریال)"]:visible').fill('50000000');
  await page.locator('input[placeholder="مبلغ کل (ریال، اختیاری)"]:visible').fill('100000000');
  await page.locator('input[placeholder="کارمزد (٪، اختیاری)"]:visible').fill('0.5');
  await page.locator('input[placeholder="یادداشت (اختیاری)"]:visible').fill(HOLD_NOTE);
  await page.getByRole('button', { name: 'ثبت خرید', exact: true }).last().click();

  const portfolio = await poll(
    async () => (await apiGet(apiToken, '/gold/portfolio')).body?.data,
    (d) => (d?.holdings ?? []).some((h) => h.symbol === HOLD_SYMBOL),
  );
  const holding = (portfolio?.holdings ?? []).find((h) => h.symbol === HOLD_SYMBOL);
  pf.apiAfterAdd = holding ? {
    symbol: holding.symbol, display_name: holding.display_name, quantity: holding.quantity,
    avg_buy_price: holding.avg_buy_price, cost_basis: holding.cost_basis, holding_ids: holding.holding_ids,
  } : null;
  pf.dbAfterAdd = db(`select id, symbol, quantity, buy_price, buy_amount_irt, buy_fee_pct, note, user_id, deleted_at from gold_holdings where user_id='${UID}' and symbol='${HOLD_SYMBOL}' order by id`);
  out.ids.holdingId = holding?.holding_ids?.[0] ?? null;

  // overview row
  await page.getByRole('button', { name: 'نمای کلی', exact: true }).last().click();
  await page.waitForTimeout(1200);
  const overviewText = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  pf.uiOverviewHasHolding = overviewText.includes(HOLD_NAME) && overviewText.includes('2.00');
  pf.uiOverviewExcerpt = overviewText.slice(0, 500);

  // sell 1 @ 55,000,000
  await page.getByRole('button', { name: `ثبت فروش برای ${HOLD_NAME}`, exact: true }).click();
  const sellDialog = page.getByRole('dialog');
  await sellDialog.locator('input[aria-label="تعداد فروش"]').fill('1');
  await sellDialog.locator('input[aria-label="قیمت فروش (ریال)"]').fill('55000000');
  await sellDialog.getByRole('button', { name: 'ثبت فروش', exact: true }).click();

  const trades = await poll(
    async () => (await apiGet(apiToken, '/gold/portfolio/trades?limit=20')).body?.data,
    (d) => (d ?? []).some((t) => t.symbol === HOLD_SYMBOL && t.action === 'sell'),
  );
  const sellTrade = (trades ?? []).find((t) => t.symbol === HOLD_SYMBOL && t.action === 'sell');
  pf.apiAfterSell = sellTrade ? {
    id: sellTrade.id, action: sellTrade.action, quantity: sellTrade.quantity,
    price: sellTrade.price, amount_irt: sellTrade.amount_irt, pnl_irt: sellTrade.pnl_irt,
  } : null;
  const portfolioAfterSell = (await apiGet(apiToken, '/gold/portfolio')).body?.data;
  pf.apiHoldingQtyAfterSell = (portfolioAfterSell?.holdings ?? []).find((h) => h.symbol === HOLD_SYMBOL)?.quantity ?? null;
  pf.dbTrades = db(`select id, action, quantity, price, amount_irt, pnl_irt, note, user_id from gold_trades where user_id='${UID}' and symbol='${HOLD_SYMBOL}' order by id`);

  // refresh and verify
  pf.reloadAfterSell = await reloadPage(page);
  const afterRefresh = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  pf.uiAfterRefreshQty = afterRefresh.includes('2.00') ? '2.00' : afterRefresh.includes('1.00') ? '1.00' : 'not-found';

  // DCA create + execute
  await page.getByRole('button', { name: 'پلن‌های DCA', exact: true }).click();
  await page.locator('input[placeholder="نام پلن"]:visible').fill(DCA_NAME);
  await page.locator('input[placeholder="سرمایه (ریال)"]:visible').fill('100000000');
  await page.getByRole('button', { name: 'ساخت پلن', exact: true }).click();
  const plans = await poll(
    async () => (await apiGet(apiToken, '/gold/portfolio/dca')).body?.data,
    (d) => (d ?? []).some((p) => p.name === DCA_NAME),
  );
  const plan = (plans ?? []).find((p) => p.name === DCA_NAME);
  out.ids.planId = plan?.plan_id ?? null;
  pf.apiDcaAfterCreate = plan ? { plan_id: plan.plan_id, name: plan.name, status: plan.status } : null;

  await page.getByRole('button', { name: /علامت‌گذاری پله/ }).first().click();
  const plansExec = await poll(
    async () => (await apiGet(apiToken, '/gold/portfolio/dca')).body?.data,
    (d) => ((d ?? []).find((p) => p.name === DCA_NAME)?.status?.executed ?? 0) >= 1,
  );
  pf.apiDcaExecuted = (plansExec ?? []).find((p) => p.name === DCA_NAME)?.status?.executed ?? null;
  pf.dbDca = db(`select id, name, executed_tranches, total_capital_irt, user_id from gold_dca_plans where user_id='${UID}' and name='${DCA_NAME}'`);

  // refresh after DCA
  pf.reloadAfterDca = await reloadPage(page);
  await page.getByRole('button', { name: 'پلن‌های DCA', exact: true }).click();
  await page.waitForTimeout(1200);
  const dcaText = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  pf.uiDcaAfterRefresh = { hasName: dcaText.includes(DCA_NAME), shows1of3: dcaText.includes('اجرا: 1/3') };

  // logout / login then verify persistence
  pf.logoutOk = await logout(page);
  await uiLogin(page);
  await navigate(page, '/gold/portfolio');
  await page.getByRole('button', { name: 'نمای کلی', exact: true }).last().click();
  await page.waitForTimeout(1000);
  const loginOverview = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  pf.uiAfterRelogin = {
    hasHolding: loginOverview.includes(HOLD_NAME),
    qty: loginOverview.includes('2.00') ? '2.00' : loginOverview.includes('1.00') ? '1.00' : 'not-found',
  };
  await page.getByRole('button', { name: 'تاریخچه', exact: true }).click();
  await page.waitForTimeout(800);
  const tradesText = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  pf.uiTradesHasSell = tradesText.includes('فروش');
  await page.screenshot({ path: 'audit_out/_tmp/w4_portfolio.png', fullPage: true });

  out.phases.portfolio = pf;

  // ═══════════════ ALERTS ═══════════════
  const al = {};
  al.hydrateWaitSec = await navigate(page, '/gold/alerts');
  const form = page.locator('form').first();
  await page.locator('input[placeholder="نام قانون"]:visible').fill(ALERT_NAME);
  await page.locator('input[placeholder^="نماد (اختیاری"]:visible').fill(ALERT_SYMBOL);
  const numInputs = form.locator('input[type="number"]');
  await numInputs.nth(0).fill('20');
  await numInputs.nth(1).fill('30');
  await page.getByRole('button', { name: 'ثبت قانون', exact: true }).click();

  const rules = await poll(
    async () => (await apiGet(apiToken, '/gold/alerts/rules')).body?.data,
    (d) => (d ?? []).some((r) => r.name === ALERT_NAME),
  );
  const rule = (rules ?? []).find((r) => r.name === ALERT_NAME);
  out.ids.alertRuleId = rule?.id ?? null;
  al.apiAfterCreate = rule ? { id: rule.id, name: rule.name, rule_type: rule.rule_type, symbol: rule.symbol, threshold: rule.threshold, enabled: rule.enabled } : null;
  al.dbAfterCreate = db(`select id, name, rule_type, symbol, threshold, enabled, user_id from gold_alert_rules where user_id='${UID}' and name='${ALERT_NAME}'`);

  // toggle off then on
  const card = page.getByText(ALERT_NAME, { exact: true }).locator('xpath=ancestor::div[contains(@class,"rounded")][1]');
  await card.getByRole('button', { name: 'فعال', exact: true }).click();
  const off = await poll(
    async () => (await apiGet(apiToken, '/gold/alerts/rules')).body?.data?.find((r) => r.name === ALERT_NAME)?.enabled,
    (v) => v === false,
  );
  await card.getByRole('button', { name: 'غیرفعال', exact: true }).click();
  const on = await poll(
    async () => (await apiGet(apiToken, '/gold/alerts/rules')).body?.data?.find((r) => r.name === ALERT_NAME)?.enabled,
    (v) => v === true,
  );
  al.toggle = { afterOff: off, afterOn: on };

  // seed default rules
  const beforeSeed = (await apiGet(apiToken, '/gold/alerts/rules')).body?.data?.length ?? 0;
  await page.getByRole('button', { name: 'درج قوانین پیش‌فرض', exact: true }).click();
  const afterSeedList = await poll(
    async () => (await apiGet(apiToken, '/gold/alerts/rules')).body?.data,
    (d) => (d ?? []).length > beforeSeed,
  );
  const seeded = (afterSeedList ?? []).filter((r) => r.name !== ALERT_NAME);
  out.ids.seededRuleIds = seeded.map((r) => r.id);
  al.seed = { before: beforeSeed, after: (afterSeedList ?? []).length, seededNames: seeded.map((r) => r.name) };

  // fixture event for ack (single row, identifiable, our own user/rule)
  if (!rule?.id) throw new Error('alert rule id missing; cannot create ACK fixture event');
  const evRaw = db(`insert into gold_alert_events (user_id, rule_id, rule_name, symbol, trigger_value, threshold, message, channel, sent_at) values ('${UID}', ${rule.id}, '${ALERT_NAME}', '${ALERT_SYMBOL}', 25, 20, '${EVENT_MSG}', 'inapp', now()) returning id`);
  const eventId = Number((String(evRaw).match(/\d+/) || [0])[0]);
  out.ids.eventId = eventId;
  al.dbEventBeforeAck = db(`select id, rule_id, rule_name, message, read_at, user_id from gold_alert_events where id=${eventId}`);

  al.reloadForEvents = await reloadPage(page);
  await page.getByRole('button', { name: /رویدادها/ }).click();
  await page.waitForTimeout(1500);
  const eventsText = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  al.uiEventVisible = eventsText.includes(EVENT_MSG);
  await page.getByRole('button', { name: 'خواندم', exact: true }).first().click();
  const acked = await poll(
    async () => (await apiGet(apiToken, '/gold/alerts/events?days=7')).body?.data?.find((e) => e.id === eventId),
    (e) => Boolean(e?.read_at),
  );
  al.apiAfterAck = { read_at: acked?.read_at ?? null };
  al.dbAfterAck = db(`select id, read_at from gold_alert_events where id=${eventId}`);

  // refresh + verify
  al.reloadAfterAck = await reloadPage(page);
  await page.getByRole('button', { name: /رویدادها/ }).click();
  await page.waitForTimeout(1000);
  const eventsText2 = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  al.uiAfterRefresh = { eventVisible: eventsText2.includes(EVENT_MSG), ackButtonGone: !eventsText2.includes('خواندم') };

  // logout/login
  await logout(page);
  await uiLogin(page);
  await navigate(page, '/gold/alerts');
  const rulesText = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  al.uiAfterRelogin = { hasRule: rulesText.includes(ALERT_NAME) };
  await page.getByRole('button', { name: /رویدادها/ }).click();
  await page.waitForTimeout(1000);
  const eventsText3 = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  al.uiAfterRelogin.eventVisible = eventsText3.includes(EVENT_MSG);
  await page.screenshot({ path: 'audit_out/_tmp/w4_alerts.png', fullPage: true });

  // delete our rule via UI
  await page.getByRole('button', { name: /قوانین/ }).click();
  await page.waitForTimeout(800);
  const cardDel = page.getByText(ALERT_NAME, { exact: true }).locator('xpath=ancestor::div[contains(@class,"rounded")][1]');
  await cardDel.getByRole('button', { name: 'حذف', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'حذف', exact: true }).click();
  const ruleGone = await poll(
    async () => (await apiGet(apiToken, '/gold/alerts/rules')).body?.data?.some((r) => r.name === ALERT_NAME),
    (v) => v === false,
  );
  al.delete = { goneFromApi: ruleGone === false, db: db(`select count(*) from gold_alert_rules where id=${rule?.id}`) };
  out.phases.alerts = al;

  // ═══════════════ TOKENS ═══════════════
  const tk = {};
  tk.hydrateWaitSec = await navigate(page, '/gold/tokens');
  await page.locator('input[placeholder="نام (مثلاً Telegram Bot)"]:visible').fill(TOKEN_NAME);
  await page.locator('main select:visible').first().selectOption('read');
  await page.getByRole('button', { name: 'ساخت Token', exact: true }).click();
  const tokenPanel = page.getByText(/Token جدید/).locator('xpath=ancestor::div[contains(@class,"rounded-xl")][1]');
  await tokenPanel.waitFor({ state: 'visible', timeout: 15000 }).catch(() => {});
  secret.token = (await tokenPanel.locator('code').innerText().catch(() => '')).trim();
  tk.created = { hasRawToken: secret.token.length > 20, rawLen: secret.token.length };

  // copy button
  await page.getByRole('button', { name: 'کپی', exact: true }).click();
  const clip = await page.evaluate(() => navigator.clipboard.readText().catch(() => ''));
  tk.copy = { clipboardMatches: clip === secret.token };

  // API surface checks with the raw token (no token value in output)
  const tokenList = (await apiGet(apiToken, '/gold/tokens')).body?.data ?? [];
  const ourToken = tokenList.find((t) => t.name === TOKEN_NAME);
  out.ids.tokenId = ourToken?.token_id ?? null;
  const bearerSnap = await fetch(API + '/gold/snapshot', { headers: { Authorization: 'Bearer ' + secret.token } });
  const bearerMetrics = await fetch(API + '/gold/metrics', { headers: { Authorization: 'Bearer ' + secret.token } });
  const xApiKey = await fetch(API + '/golddesk/snapshot', { headers: { 'X-API-Key': secret.token } });
  tk.apiUse = {
    goldSnapshotBearer: bearerSnap.status,
    goldMetricsBearer: bearerMetrics.status,
    golddeskSnapshotXApiKey: xApiKey.status,
  };

  const metaKey = `golddesk:api_tokens:meta:${ourToken?.token_id}`;
  const metaRaw = redis(['GET', metaKey]);
  let meta = null;
  try { meta = JSON.parse(metaRaw); } catch { meta = null; }
  const hashKey = meta?.token_hash ? `golddesk:api_tokens:hash:${meta.token_hash}` : null;
  tk.redisBefore = {
    metaHasName: meta?.name === TOKEN_NAME,
    scopes: meta?.scopes ?? null,
    enabled: meta?.enabled ?? null,
    hashKeyExists: hashKey ? redis(['EXISTS', hashKey]) === '1' : false,
    rawTokenStored: metaRaw.includes(secret.token),
  };

  // refresh -> token listed
  tk.reloadBeforeRevoke = await reloadPage(page);
  const tokensText = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  tk.uiAfterRefresh = { listed: tokensText.includes(TOKEN_NAME), rawVisible: secret.token ? tokensText.includes(secret.token) : false };

  // revoke
  await page.getByRole('button', { name: `لغو token ${TOKEN_NAME}`, exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'لغو token', exact: true }).click();
  const revoked = await poll(
    async () => (await apiGet(apiToken, '/gold/tokens')).body?.data?.find((t) => t.token_id === ourToken?.token_id)?.enabled,
    (v) => v === false,
  );
  tk.apiAfterRevoke = { enabled: revoked ?? null };
  const metaAfter = redis(['GET', metaKey]);
  let metaA = null;
  try { metaA = JSON.parse(metaAfter); } catch { metaA = null; }
  tk.redisAfter = {
    enabled: metaA?.enabled ?? null,
    hashKeyExists: hashKey ? redis(['EXISTS', hashKey]) === '1' : false,
  };
  const bearerAfter = await fetch(API + '/gold/snapshot', { headers: { Authorization: 'Bearer ' + secret.token } });
  tk.apiUseAfterRevoke = { goldSnapshotBearer: bearerAfter.status };

  // refresh + logout/login
  tk.reloadAfterRevoke = await reloadPage(page);
  const tokensText2 = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  tk.uiAfterRevokeRefresh = { listed: tokensText2.includes(TOKEN_NAME), enabledCountText: (tokensText2.match(/فعال \(([^)]*)\)/) || [])[1] ?? null };
  await logout(page);
  await uiLogin(page);
  await navigate(page, '/gold/tokens');
  const tokensText3 = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
  tk.uiAfterRelogin = { listed: tokensText3.includes(TOKEN_NAME) };
  const bearerFinal = await fetch(API + '/gold/snapshot', { headers: { Authorization: 'Bearer ' + secret.token } });
  tk.apiUseAfterRelogin = { goldSnapshotBearer: bearerFinal.status };
  await page.screenshot({ path: 'audit_out/_tmp/w4_tokens.png', fullPage: true });

  out.phases.tokens = tk;
  out.consoleErrors = consoleErrors;
  out.finishedAt = new Date().toISOString();
  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
