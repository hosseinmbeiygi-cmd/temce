const { chromium } = require('playwright');
const fs = require('fs');
const BASE='http://127.0.0.1:3000';
const ADMIN='audit_ui_admin_20261030_a1', USER='audit_ui_user_20261030_u1', PASS='AuditUi-20261030!';
const BACKTEST=['/backtest','/backtest/engine','/backtest/walk-forward','/backtest/monte-carlo'];
const ADMINR=['/admin','/admin/users','/data-import','/sync-manager'];
const PROGRESS='audit_out/_tmp/wave5_smoke_progress.jsonl';
fs.writeFileSync(PROGRESS,'');
function rec(o){fs.appendFileSync(PROGRESS,JSON.stringify(o)+'\n');}
async function waitHydrated(page,maxSec=25){
  for(let i=0;i<maxSec;i++){
    const ok=await page.evaluate(()=>{const b=[...document.querySelectorAll('main button, main input, main select')][0];return b?Reflect.ownKeys(b).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false);
    if(ok)return i; await page.waitForTimeout(1000);
  } return -1;
}
async function login(page,u){
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(u);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:20000}).catch(()=>{});
  await page.waitForLoadState('networkidle',{timeout:25000}).catch(()=>{}); await page.waitForTimeout(1500);
}
async function inspect(page,route){
  const bad=[]; const errs=[];
  const onResp=r=>{if(r.url().includes('/api/')&&r.status()>=400)bad.push(r.status()+' '+r.request().method()+' '+r.url().replace(BASE,''));};
  const onErr=m=>{if(m.type()==='error')errs.push(m.text().slice(0,140));};
  page.on('response',onResp); page.on('console',onErr);
  await page.goto(BASE+route,{waitUntil:'domcontentloaded'});
  const waited=await waitHydrated(page,25);
  await page.waitForLoadState('networkidle',{timeout:12000}).catch(()=>{});
  await page.waitForTimeout(800);
  const data=await page.evaluate(()=>{
    const main=document.querySelector('main');
    const text=(main?.innerText||'').replace(/\s+/g,' ');
    const body=document.body.innerText.replace(/\s+/g,' ');
    return {url:location.href,heading:main?.querySelector('h1,h2,h3')?.textContent?.trim()??null,bodyLen:body.length,
      buttons:main?main.querySelectorAll('button').length:0,inputs:main?main.querySelectorAll('input').length:0,
      selects:main?main.querySelectorAll('select').length:0,tables:main?main.querySelectorAll('table').length:0,
      svgs:main?main.querySelectorAll('svg').length:0,
      hasErrorText:/خطا|ناموفق|در دسترس نیست|Internal error|HTTP 5\d\d/.test(text),excerpt:text.slice(0,180)};
  });
  data.hydrateWaitSec=waited; data.badResponses=[...new Set(bad)].slice(0,6); data.consoleErrors=[...new Set(errs)].slice(0,4);
  page.off('response',onResp); page.off('console',onErr); rec({route,...data}); return data;
}
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const out={fixedLoginMessage:{},backtest:{},admin:{},normalUser:{}};
  const ctx=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  // F1 wrong-password
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(ADMIN);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('definitely-wrong');
  await page.locator('button[type="submit"]:visible').click(); await page.waitForTimeout(2500);
  out.fixedLoginMessage={url:page.url(),text:(await page.locator('body').innerText()).replace(/\s+/g,' ').slice(0,240)};
  rec({route:'LOGIN_WRONG',...out.fixedLoginMessage});
  await login(page,ADMIN);
  for(const r of BACKTEST) out.backtest[r]=await inspect(page,r);
  for(const r of ADMINR) out.admin[r]=await inspect(page,r);
  // normal user on admin
  const ctx2=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx2.route(p,r=>r.abort());
  const p2=await ctx2.newPage(); await login(p2,USER);
  await p2.goto(BASE+'/admin',{waitUntil:'domcontentloaded'}); await p2.waitForTimeout(5000);
  out.normalUser={url:p2.url(),text:(await p2.locator('body').innerText()).replace(/\s+/g,' ').slice(0,240)};
  rec({route:'NORMAL_ADMIN',...out.normalUser});
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
