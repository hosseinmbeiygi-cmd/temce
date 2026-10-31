const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1600,height:1200}});
  for (const p of ['**/api/v1/market/**','**/api/v1/market-dashboard**','**/api/v1/news**','**/api/v1/economic-calendar**','**/api/v1/brsapi/**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_storage_20261031');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditStorage-20261031!');
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(u=>!String(u).includes('/auth/login'),{timeout:20000}).catch(()=>{});
  await page.waitForTimeout(3000);
  await page.goto(BASE+'/gold/portfolio',{waitUntil:'domcontentloaded'});
  await page.waitForTimeout(12000);
  const info=await page.evaluate(async()=>{
    const sw = navigator.serviceWorker;
    const regs = await sw.getRegistrations();
    const keys = await caches.keys();
    const perCache = {};
    for (const k of keys) {
      const c = await caches.open(k);
      const reqs = await c.keys();
      perCache[k] = reqs.map(r=>r.url.replace(location.origin,'')).slice(0,20);
    }
    let matchInfo=null;
    try {
      const c = await caches.open('golddesk-static-v2');
      const res = await c.match('/gold/portfolio');
      if (res) {
        const body = await res.clone().text();
        matchInfo = { status: res.status, type: res.type, redirected: res.redirected, url: res.url, ct: res.headers.get('content-type'), bodyStart: body.slice(0,180) };
      }
    } catch(e) { matchInfo = { err: String(e) }; }
    return {
      controller: sw.controller?.scriptURL ?? null,
      regs: regs.map(r=>({scope:r.scope, script:r.active?.scriptURL||r.installing?.scriptURL||r.waiting?.scriptURL})),
      keys, perCache, golddeskPortfolio: matchInfo,
    };
  });
  console.log(JSON.stringify(info,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
