const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
const ROUTES=['/admin/users','/data-import','/sync-manager'];
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_admin_20261030_a1');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditUi-20261030!');
  const lp=page.waitForResponse(r=>r.url().includes('/auth/login')&&r.request().method()==='POST',{timeout:20000}).catch(()=>null);
  await page.locator('button[type="submit"]:visible').click();
  const lr=await lp; await page.waitForTimeout(4000);
  const out={loginStatus:lr?lr.status():null,url:page.url(),pages:{}};
  for(const route of ROUTES){
    const net=[];
    const onResp=r=>{if(r.url().includes('/api/'))net.push(r.status()+' '+r.request().method()+' '+r.url().replace(BASE,''));};
    page.on('response',onResp);
    await page.goto(BASE+route,{waitUntil:'domcontentloaded',timeout:90000});
    await page.waitForTimeout(7000);
    const body=(await page.locator('body').innerText()).replace(/\s+/g,' ');
    out.pages[route]={url:page.url(),net:[...net].slice(0,20),tables:await page.locator('main table').count(),inputs:await page.locator('main input').count(),excerpt:body.slice(0,240)};
    page.off('response',onResp);
  }
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
