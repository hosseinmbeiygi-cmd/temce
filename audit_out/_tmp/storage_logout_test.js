const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
const USER='audit_ui_storage_20261031', PASS='AuditStorage-20261031!';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1680,height:1400}, serviceWorkers:'block'});
  for (const p of ['**/api/v1/market/**','**/api/v1/market-dashboard**','**/api/v1/news**','**/api/v1/economic-calendar**','**/api/v1/brsapi/**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  const out={};
  async function login(){
    await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(6000);
    await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
    await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
    await page.locator('button[type="submit"]:visible').click();
    await page.waitForURL(u=>!String(u).includes('/auth/login'),{timeout:20000}).catch(()=>{});
    await page.waitForLoadState('networkidle',{timeout:30000}).catch(()=>{});
    await page.waitForTimeout(2500);
  }
  await login();
  await page.goto(BASE+'/',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(6000);
  const logoutBtn=page.locator('button[aria-label="خروج"]').first();
  out.logoutButtonFound=(await logoutBtn.count())>0;
  if (out.logoutButtonFound){
    await logoutBtn.click();
    await page.waitForURL(u=>String(u).includes('/auth/login'),{timeout:15000}).catch(()=>{});
    await page.waitForTimeout(2000);
    out.afterLogoutUrl=page.url();
    out.refreshAfterLogout=await page.evaluate(async()=>{
      const r=await fetch('/api/v1/auth/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',credentials:'include'});
      return r.status;
    }).catch(()=>null);
  }
  // protected page while logged out
  await page.goto(BASE+'/gold/portfolio',{waitUntil:'domcontentloaded'});
  await page.waitForTimeout(4000);
  out.protectedWhileLoggedOutUrl=page.url();
  // login again and verify persisted storage
  await login();
  await page.goto(BASE+'/gold/portfolio',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(5000);
  await page.getByRole('button',{name:'نمای کلی',exact:true}).last().click(); await page.waitForTimeout(800);
  const ov=(await page.locator('main').innerText()).replace(/\s+/g,' ');
  out.portfolioAfterLogoutLogin={hasHolding:ov.includes('AUD-UI سکه تست'), qty2:ov.includes('2.00')};
  await page.getByRole('button',{name:'پلن‌های DCA',exact:true}).click(); await page.waitForTimeout(1000);
  const dca=(await page.locator('main').innerText()).replace(/\s+/g,' ');
  out.dcaAfterLogoutLogin={hasPlan:dca.includes('AUD-UI-DCA-20261031'), shows1of3:dca.includes('اجرا: 1/3')};
  await page.goto(BASE+'/gold/tokens',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(5000);
  out.tokensAfterLogoutLogin=(await page.locator('main').innerText()).includes('AUD-UI-TOKEN-20261031');
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
