const { chromium } = require('playwright');
const fs=require('fs');
const BASE='http://127.0.0.1:3000';
const USER='audit_ui_admin_20261031_b1', PASS='AuditUi-20261031!';
const ROUTES=['/gold','/gold/alerts','/gold/analytics','/gold/antigravity','/gold/backtest','/gold/chat','/gold/coins','/gold/coverage','/gold/dashboard','/gold/dca','/gold/etf','/gold/funds','/gold/futures','/gold/health','/gold/macro','/gold/options','/gold/physical','/gold/portfolio','/gold/settings','/gold/technical','/gold/terminal','/gold/tokens'];
const P='audit_out/_tmp/gold_all_smoke.jsonl'; fs.writeFileSync(P,'');
function rec(o){fs.appendFileSync(P,JSON.stringify(o)+'\n');}
async function waitHydrated(page,maxSec=25){
  for(let i=0;i<maxSec;i++){
    const ok=await page.evaluate(()=>{const b=[...document.querySelectorAll('main button, main input, main select, main table')][0];return b?Reflect.ownKeys(b).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false);
    if(ok)return i; await page.waitForTimeout(1000);
  } return -1;
}
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  page.on('requestfailed',r=>{});
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:120000});
  for(let i=0;i<25;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  const lp=page.waitForResponse(r=>r.url().includes('/auth/login')&&r.request().method()==='POST',{timeout:20000}).catch(()=>null);
  await page.locator('button[type="submit"]:visible').click();
  const lr=await lp; await page.waitForTimeout(3000);
  rec({route:'LOGIN',status:lr?lr.status():null,url:page.url()});
  for(const route of ROUTES){
    const net=[]; const errs=[];
    const onResp=r=>{if(r.url().includes('/api/')&&r.status()>=400)net.push(r.status()+' '+r.request().method()+' '+r.url().replace(BASE,''));};
    const onErr=m=>{if(m.type()==='error')errs.push(m.text().slice(0,140));};
    page.on('response',onResp); page.on('console',onErr);
    let navErr=null;
    try{await page.goto(BASE+route,{waitUntil:'domcontentloaded',timeout:120000});}catch(e){navErr=String(e).slice(0,120);}
    const waited=await waitHydrated(page,25);
    await page.waitForTimeout(3000);
    let data={};
    try{data=await page.evaluate(()=>{const main=document.querySelector('main');const body=document.body.innerText.replace(/\s+/g,' ');return {url:location.href,heading:main?.querySelector('h1,h2,h3')?.textContent?.trim()??null,bodyLen:body.length,buttons:main?main.querySelectorAll('button').length:0,inputs:main?main.querySelectorAll('input').length:0,selects:main?main.querySelectorAll('select').length:0,tables:main?main.querySelectorAll('table').length:0,svgs:main?main.querySelectorAll('svg').length:0,hasErrorText:/خطا|ناموفق|در دسترس نیست|Internal error|HTTP 5\d\d/.test(body),excerpt:body.slice(0,180)};});}catch(e){data={evalError:String(e).slice(0,120)};}
    data.hydrateWaitSec=waited; data.navError=navErr; data.badResponses=[...new Set(net)].slice(0,8); data.consoleErrors=[...new Set(errs)].slice(0,4);
    rec({route,...data});
    page.off('response',onResp); page.off('console',onErr);
  }
  console.log('done');
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
