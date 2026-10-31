const { chromium } = require('playwright');
const fs=require('fs');
const BASE='http://127.0.0.1:3000';
const ROUTES=['/admin/users','/data-import','/sync-manager'];
const P='audit_out/_tmp/admin_pages_probe2.jsonl'; fs.writeFileSync(P,'');
function rec(o){fs.appendFileSync(P,JSON.stringify(o)+'\n');}
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:120000});
  for(let i=0;i<25;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_admin_20261030_a1');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditUi-20261030!');
  const lp=page.waitForResponse(r=>r.url().includes('/auth/login')&&r.request().method()==='POST',{timeout:20000}).catch(()=>null);
  await page.locator('button[type="submit"]:visible').click();
  const lr=await lp; await page.waitForTimeout(3000);
  rec({route:'LOGIN',status:lr?lr.status():null,url:page.url()});
  for(const route of ROUTES){
    const net=[];
    const onResp=r=>{if(r.url().includes('/api/'))net.push(r.status()+' '+r.request().method()+' '+r.url().replace(BASE,''));};
    page.on('response',onResp);
    let navErr=null;
    try{await page.goto(BASE+route,{waitUntil:'domcontentloaded',timeout:120000});}catch(e){navErr=String(e).slice(0,120);}
    await page.waitForTimeout(7000);
    let data={};
    try{data=await page.evaluate(()=>{const main=document.querySelector('main');const body=document.body.innerText.replace(/\s+/g,' ');return {url:location.href,heading:main?.querySelector('h1,h2,h3')?.textContent?.trim()??null,tables:main?main.querySelectorAll('table').length:0,inputs:main?main.querySelectorAll('input').length:0,buttons:main?main.querySelectorAll('button').length:0,excerpt:body.slice(0,240)};});}catch(e){data={evalError:String(e).slice(0,120)};}
    rec({route,net:[...new Set(net)].slice(0,20),navError:navErr,...data});
    page.off('response',onResp);
  }
  await browser.close();
  console.log('done');
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
