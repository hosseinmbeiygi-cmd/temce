const { chromium } = require('playwright');
const fs = require('fs');
const BASE='http://127.0.0.1:3000';
const ADMIN='audit_ui_admin_20261030_a1', USER='audit_ui_user_20261030_u1', PASS='AuditUi-20261030!';
const ROUTES=['/backtest/engine','/backtest/walk-forward','/admin','/admin/users','/data-import','/sync-manager'];
const PROGRESS='audit_out/_tmp/wave5_smoke_progress.jsonl';
function rec(o){fs.appendFileSync(PROGRESS,JSON.stringify(o)+'\n');}
async function waitHydrated(page,maxSec=30){
  for(let i=0;i<maxSec;i++){
    const ok=await page.evaluate(()=>{const b=[...document.querySelectorAll('main button, main input, main select')][0];return b?Reflect.ownKeys(b).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false);
    if(ok)return i; await page.waitForTimeout(1000);
  } return -1;
}
async function login(page,u){
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000}); await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(u);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:20000}).catch(()=>{});
  await page.waitForLoadState('networkidle',{timeout:25000}).catch(()=>{}); await page.waitForTimeout(1500);
}
async function inspect(page,route){
  const bad=[];
  const onResp=r=>{if(r.url().includes('/api/')&&r.status()>=400)bad.push(r.status()+' '+r.request().method()+' '+r.url().replace(BASE,''));};
  page.on('response',onResp);
  let navError=null;
  try{await page.goto(BASE+route,{waitUntil:'domcontentloaded',timeout:90000});}catch(e){navError=String(e).slice(0,120);}
  const waited=await waitHydrated(page,30);
  await page.waitForLoadState('networkidle',{timeout:12000}).catch(()=>{});
  await page.waitForTimeout(800);
  const data=await page.evaluate(()=>{
    const main=document.querySelector('main');
    const text=(main?.innerText||'').replace(/\s+/g,' ');
    const body=document.body.innerText.replace(/\s+/g,' ');
    return {url:location.href,heading:main?.querySelector('h1,h2,h3')?.textContent?.trim()??null,bodyLen:body.length,
      buttons:main?main.querySelectorAll('button').length:0,inputs:main?main.querySelectorAll('input').length:0,
      selects:main?main.querySelectorAll('select').length:0,tables:main?main.querySelectorAll('table').length:0,
      hasErrorText:/خطا|ناموفق|دسترسی|403|Internal error|HTTP 5\d\d/.test(text),excerpt:text.slice(0,200)};
  });
  data.hydrateWaitSec=waited; data.navError=navError; data.badResponses=[...new Set(bad)].slice(0,6);
  page.off('response',onResp); rec({route,...data}); return data;
}
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const out={loginWrong:{},routes:{},normalAdmin:{}};
  const ctx=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000}); await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(ADMIN);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('definitely-wrong');
  await page.locator('button[type="submit"]:visible').click(); await page.waitForTimeout(2500);
  const wrongText=(await page.locator('body').innerText()).replace(/\s+/g,' ');
  out.loginWrong={url:page.url(),hasServerMsg:wrongText.includes('Invalid username or password'),hasMissingToken:wrongText.includes('missing access token'),snippet:(wrongText.match(/.{0,80}Invalid username or password.{0,80}/)||wrongText.match(/.{0,80}Login failed.{0,80}/)||[''])[0]};
  rec({route:'LOGIN_WRONG',...out.loginWrong});
  await login(page,ADMIN);
  for(const r of ROUTES) out.routes[r]=await inspect(page,r);
  const ctx2=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx2.route(p,r=>r.abort());
  const p2=await ctx2.newPage(); await login(p2,USER);
  await p2.goto(BASE+'/admin',{waitUntil:'domcontentloaded',timeout:90000}); await p2.waitForTimeout(5000);
  const t2=(await p2.locator('body').innerText()).replace(/\s+/g,' ');
  out.normalAdmin={url:p2.url(),has403:/403|دسترسی|مجاز نیست/.test(t2),snippet:t2.slice(0,220)};
  rec({route:'NORMAL_ADMIN',...out.normalAdmin});
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
