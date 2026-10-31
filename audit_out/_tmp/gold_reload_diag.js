const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
const USER='audit_ui_storage_20261031', PASS='AuditStorage-20261031!';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  for (const mode of ['block-sw','allow-sw']) {
    const ctx=await browser.newContext({viewport:{width:1600,height:1200}, ...(mode==='block-sw'?{serviceWorkers:'block'}:{})});
    for (const p of ['**/api/v1/market/**','**/api/v1/market-dashboard**','**/api/v1/news**','**/api/v1/economic-calendar**','**/api/v1/brsapi/**']) await ctx.route(p,r=>r.abort());
    const page=await ctx.newPage();
    const navs=[]; page.on('framenavigated',f=>{ if(f===page.mainFrame()) navs.push(Date.now()+' '+f.url()); });
    const errs=[]; page.on('pageerror',e=>errs.push(e.message.slice(0,120)));
    await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(6000);
    await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
    await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
    await page.locator('button[type="submit"]:visible').click();
    await page.waitForURL(u=>!String(u).includes('/auth/login'),{timeout:20000}).catch(()=>{});
    await page.waitForTimeout(3000);
    await page.goto(BASE+'/gold/portfolio',{waitUntil:'domcontentloaded'});
    await page.waitForTimeout(15000);
    const beforeReload=navs.length;
    await page.reload({waitUntil:'domcontentloaded'}).catch(()=>{});
    await page.waitForTimeout(15000);
    let hydrated=false;
    try { hydrated=await page.evaluate(()=>{const b=[...document.querySelectorAll('main button')][0];return b?Reflect.ownKeys(b).map(String).some(k=>/reactProps/.test(k)):false;}); } catch(e){}
    let dcaInput=0;
    try { await page.getByRole('button',{name:'پلن‌های DCA',exact:true}).last().click({timeout:8000}); await page.waitForTimeout(1500); dcaInput=await page.locator('input[placeholder="نام پلن"]').count(); } catch(e){}
    console.log(JSON.stringify({mode,url:page.url(),navCountAfterReload:navs.length-beforeReload,navs:navs.slice(-8),hydrated,dcaInput,errs:errs.slice(0,5)},null,2));
    await ctx.close();
  }
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
