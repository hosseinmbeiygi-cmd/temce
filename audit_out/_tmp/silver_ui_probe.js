const { chromium } = require('playwright');

const BASE = 'http://127.0.0.1:3000';
const USER = process.env.AUDIT_UI_USER;
const PASS = process.env.AUDIT_UI_PASS;

const TABS = [
  ['overview', 'نمای کلی', 'مبدل سریع (گرم ⇄ انس ⇄ ریال)'],
  ['forecast', 'پیش‌بینی', 'پیش‌بینی انس جهانی نقره (XAG/USD)'],
  ['funds', 'صندوق‌ها', 'صندوق‌های نقره و کالایی'],
  ['futures', 'آتی (IME)', 'قراردادهای آتی نقره (IME)'],
  ['backtest', 'بک‌تست', 'بک‌تست استراتژی روی نماد نقره'],
  ['ml', 'هوش مصنوعی', 'مدل‌های یادگیری ماشین و اجراهای آموزش'],
  ['news', 'اخبار', 'اخبار بازار نقره'],
];

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe',
  });
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  const net = [];
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 220));
  });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message.slice(0, 220)));
  page.on('response', (r) => {
    const u = r.url();
    if (u.includes('/api/v1/') || u.includes('/auth/')) {
      net.push(r.status() + ' ' + r.request().method() + ' ' + u.replace(BASE, '').replace('http://127.0.0.1:8000', ''));
    }
  });

  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});
  const afterLogin = page.url();

  // The post-login dashboard fires many slow API calls; let them settle before
  // hard-navigating, otherwise they occupy all HTTP/1.1 sockets and the Silver
  // page's JS chunks never arrive (test-environment artifact, not the page).
  await page.waitForLoadState('networkidle', { timeout: 35000 }).catch(() => {});
  await page.waitForTimeout(3000);

  await page.goto(BASE + '/markets/silver', { waitUntil: 'domcontentloaded' });
  let hydrationWaitMs = 0;
  for (let i = 0; i < 45; i++) {
    const ok = await page.evaluate(() => {
      const b = [...document.querySelectorAll('nav button')].find((x) => x.innerText.trim() === 'پیش‌بینی');
      return b ? Reflect.ownKeys(b).map(String).some((k) => /reactProps/i.test(k)) : false;
    });
    if (ok) break;
    await page.waitForTimeout(2000);
    hydrationWaitMs += 2000;
  }

  const bodyText = async () => (await page.locator('body').innerText()).replace(/\s+/g, ' ');
  const mainLen = () => page.evaluate(() => (document.querySelector('main')?.innerText || '').replace(/\s+/g, ' ').length);
  const activeTab = () =>
    page.evaluate(() =>
      [...document.querySelectorAll('nav button')]
        .filter((b) => b.offsetParent !== null && b.className.includes('bg-primary-600'))
        .map((b) => (b.innerText || '').trim()),
    );

  const out = { afterLogin, hydrationWaitMs, tabs: {}, checks: {}, netNon2xx: [], consoleErrors: [] };
  out.hydration = await page.evaluate(() => {
    const b = [...document.querySelectorAll('nav button')].find((x) => x.innerText.trim() === 'پیش‌بینی');
    return {
      readyState: document.readyState,
      tabReactKeys: b ? Reflect.ownKeys(b).map(String).filter((k) => /react/i.test(k)) : null,
      mainLen: (document.querySelector('main')?.innerText || '').replace(/\s+/g, ' ').length,
    };
  });

  for (const [id, label, marker] of TABS) {
    const btn = page.getByRole('button', { name: label, exact: true }).filter({ visible: true }).first();
    const count = await btn.count();
    if (!count) {
      out.tabs[id] = { clicked: false, reason: 'visible tab button not found' };
      continue;
    }
    await btn.click();
    await page.waitForTimeout(1500);
    const text = await bodyText();
    out.tabs[id] = {
      clicked: true,
      active: await activeTab(),
      mainLen: await mainLen(),
      markerPresent: text.includes(marker),
      excerpt: text.slice(0, 160),
      hasErrorBanner: text.includes('دریافت نشد') || text.includes('ناموفق بود'),
      hasLoadingSkeleton: (await page.locator('.animate-pulse').count()) > 0,
      hasEmptyState:
        text.includes('موجود نیست') ||
        text.includes('یافت نشد') ||
        text.includes('ثبت نشده') ||
        text.includes('در دسترس نیست'),
    };
  }

  // ── overview: rules panel + converter ──
  await page.getByRole('button', { name: 'نمای کلی', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(1200);
  out.checks.rulesPanel = {
    loadingVisible: (await page.locator('[data-testid="spec-rules-loading"]').count()) > 0,
    thresholdsVisible: (await page.locator('[data-testid="spec-filter-thresholds"]').count()) > 0,
    unavailableVisible: (await page.locator('[data-testid="spec-rules-unavailable"]').count()) > 0,
    verdict: (await page.locator('[data-testid="spec-trade-verdict"]').first().innerText().catch(() => null)),
  };

  const grams = page.locator('input[placeholder="گرم"]:visible').first();
  const converterText = async () => {
    const sec = grams.locator('xpath=ancestor::div[contains(@class,"rounded-2xl")][1]');
    return (await sec.innerText()).replace(/\s+/g, ' ');
  };
  out.checks.converter = {};
  for (const v of ['10', '0', 'abc', '']) {
    await grams.fill(v);
    await page.waitForTimeout(350);
    out.checks.converter[v === '' ? 'empty' : v] = await converterText();
  }
  await grams.fill('1');

  // ── forecast: horizon buttons + unavailable state ──
  await page.getByRole('button', { name: 'پیش‌بینی', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(2500);
  out.checks.forecast = {
    horizonButtons: await page.getByRole('button', { name: /روز/ }).filter({ visible: true }).count(),
    horizonDisabled: await page.getByRole('button', { name: /روز/ }).filter({ visible: true }).first().isDisabled().catch(() => null),
    unavailableText: (await page.locator('main').innerText()).includes('پیش‌بینی در دسترس نیست'),
  };

  // ── funds / futures empty/error state ──
  await page.getByRole('button', { name: 'صندوق‌ها', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(1500);
  out.checks.funds = {
    tableRows: await page.locator('main table tbody tr').count(),
    emptyState: (await page.locator('main').innerText()).includes('صندوق نقره‌ای در API موجود نیست'),
  };

  await page.getByRole('button', { name: 'آتی (IME)', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(2500);
  out.checks.futures = {
    tableRows: await page.locator('main table tbody tr').count(),
    errorState: (await page.locator('main').innerText()).includes('دریافت قراردادهای آتی ناموفق بود'),
    emptyState: (await page.locator('main').innerText()).includes('قرارداد آتی نقره‌ای در API موجود نیست'),
  };

  // ── backtest form: validation without executing a run ──
  await page.getByRole('button', { name: 'بک‌تست', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(1500);
  const symbolInput = page.locator('input[list="silver-symbol-suggestions"]:visible').first();
  out.checks.backtest = {
    runDisabledEmptySymbol: await page.getByRole('button', { name: 'اجرای بک‌تست' }).isDisabled(),
    strategyOptions: await page.locator('main select option').count(),
    datalistOptions: await page.locator('datalist option').count(),
  };
  await symbolInput.fill('TEST_SILVER_UI');
  await page.locator('label:has-text("پارامترهای استراتژی") input').fill('{');
  await page.getByRole('button', { name: 'اجرای بک‌تست' }).click();
  await page.waitForTimeout(800);
  out.checks.backtest.invalidJsonError = (await page.locator('main').innerText()).includes('پارامترهای JSON نامعتبر است');
  out.checks.backtest.runDisabledAfterSymbol = await page.getByRole('button', { name: 'اجرای بک‌تست' }).isDisabled();

  // ── ML tab: content + search filter ──
  await page.getByRole('button', { name: 'هوش مصنوعی', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(2500);
  const mlText = await page.locator('main').innerText();
  out.checks.ml = {
    modelCards: await page.locator('main section .rounded-2xl.border.border-line.bg-card').count(),
    runsRows: await page.locator('main table tbody tr').count(),
    emptyModels: mlText.includes('مدلی در سرویس ML ثبت نشده است'),
    searchPresent: (await page.locator('input[placeholder^="جستجو: نام مدل"]:visible').count()) > 0,
  };
  const search = page.locator('input[placeholder^="جستجو: نام مدل"]:visible').first();
  if (await search.count()) {
    const before = await page.locator('main table tbody tr').count();
    await search.fill('__no_such_model__');
    await page.waitForTimeout(600);
    const after = await page.locator('main table tbody tr').count();
    out.checks.ml.searchFilter = { rowsBefore: before, rowsAfter: after };
    await search.fill('');
  }

  // ── news tab ──
  await page.getByRole('button', { name: 'اخبار', exact: true }).filter({ visible: true }).first().click();
  await page.waitForTimeout(1500);
  out.checks.news = {
    cards: await page.locator('main section a[target="_blank"]').count(),
    emptyState: (await page.locator('main').innerText()).includes('خبری با کلیدواژهٔ نقره یافت نشد'),
  };

  out.netNon2xx = net.filter((x) => !/^2\d\d /.test(x));
  out.netAll = net;
  out.consoleErrors = consoleErrors;
  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
