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
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message.slice(0, 300)));
  page.on('console', (m) => {
    if (m.type() === 'error') console.log('CONSOLE_ERR', m.text().slice(0, 300));
  });

  await page.goto(BASE + '/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL((u) => !String(u).includes('/auth/login'), { timeout: 20000 }).catch(() => {});

  await page.goto(BASE + '/markets/silver', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(12000);

  const info = await page.evaluate(() => {
    const all = [...document.querySelectorAll('button')];
    const match = (t) => all.filter((b) => (b.innerText || '').trim() === t);
    const describe = (b) => {
      const r = b.getBoundingClientRect();
      const cs = getComputedStyle(b);
      return {
        cls: b.className.slice(0, 140),
        rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
        visible: !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length),
        display: cs.display,
        visibility: cs.visibility,
        navText: b.closest('nav')?.innerText.replace(/\s+/g, ' ').slice(0, 120) ?? null,
        hasReactProps: Object.keys(b).filter((k) => k.startsWith('__reactProps')).length,
        inMain: !!b.closest('main'),
      };
    };
    return {
      mainCount: document.querySelectorAll('main').length,
      mainRects: [...document.querySelectorAll('main')].map((m) => {
        const r = m.getBoundingClientRect();
        return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height), m.innerText.replace(/\s+/g, ' ').length];
      }),
      navCount: document.querySelectorAll('nav').length,
      navTexts: [...document.querySelectorAll('nav')].map((n) => n.innerText.replace(/\s+/g, ' ').slice(0, 140)),
      buttons: ['نمای کلی', 'پیش‌بینی', 'صندوق‌ها'].map((t) => ({ text: t, matches: match(t).map(describe) })),
      bodyLen: document.body.innerText.replace(/\s+/g, ' ').length,
      activeNow: all.filter((b) => b.className.includes('bg-primary-600')).map((b) => b.innerText.trim()),
      url: location.href,
    };
  });
  console.log('INFO', JSON.stringify(info, null, 2));

  // native click on the real tab (the one inside nav, exact text, smallest rect)
  const clickResult = await page.evaluate(() => {
    const navs = [...document.querySelectorAll('nav')];
    const nav = navs.find((n) => n.innerText.includes('پیش‌بینی') && n.innerText.includes('صندوق‌ها'));
    if (!nav) return { ok: false, reason: 'page tab nav not found' };
    const btn = [...nav.querySelectorAll('button')].find((b) => b.innerText.trim() === 'پیش‌بینی');
    if (!btn) return { ok: false, reason: 'tab button not found' };
    const before = (document.querySelector('main')?.innerText || '').replace(/\s+/g, ' ').length;
    btn.click();
    return { ok: true, before, cls: btn.className };
  });
  await page.waitForTimeout(2000);
  const after = await page.evaluate(() => ({
    url: location.href,
    active: [...document.querySelectorAll('nav button')].filter((b) => b.className.includes('bg-primary-600')).map((b) => b.innerText.trim()),
    mainLen: (document.querySelector('main')?.innerText || '').replace(/\s+/g, ' ').length,
    hasForecastMarker: (document.querySelector('main')?.innerText || '').includes('پیش‌بینی انس جهانی نقره'),
    excerpt: (document.querySelector('main')?.innerText || '').replace(/\s+/g, ' ').slice(0, 300),
  }));
  console.log('NATIVE_CLICK', JSON.stringify({ clickResult, after }, null, 2));

  // keyboard attempt on the overview→funds button
  const kb = await page.evaluate(() => {
    const navs = [...document.querySelectorAll('nav')];
    const nav = navs.find((n) => n.innerText.includes('صندوق‌ها') && n.innerText.includes('اخبار'));
    const btn = nav && [...nav.querySelectorAll('button')].find((b) => b.innerText.trim() === 'صندوق‌ها');
    if (!btn) return { ok: false };
    btn.focus();
    return { ok: true, focused: document.activeElement === btn };
  });
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1500);
  const afterKb = await page.evaluate(() => ({
    active: [...document.querySelectorAll('nav button')].filter((b) => b.className.includes('bg-primary-600')).map((b) => b.innerText.trim()),
    mainLen: (document.querySelector('main')?.innerText || '').replace(/\s+/g, ' ').length,
    hasFundsMarker: (document.querySelector('main')?.innerText || '').includes('صندوق‌های نقره و کالایی'),
  }));
  console.log('KEYBOARD', JSON.stringify({ kb, afterKb }, null, 2));

  await page.screenshot({ path: 'audit_out/_tmp/silver_after_native_click.png', fullPage: false });
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
