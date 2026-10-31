const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  const net=[];
  page.on('response',r=>{const u=r.url(); if(u.includes('/auth/')||u.includes('/api/v1/dashboard')||u.includes('/api/v1/jobs')||u.includes('/api/v1/brsapi/sync')||u.includes('/api/v1/admin')) net.push(r.status()+' '+r.request().method()+' '+u.replace(BASE,''));});
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){
    const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false);
    if(ok) break; await page.waitForTimeout(1000);
  }
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_user_20261030_u1');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditUi-20261030!');
  const loginResp=page.waitForResponse(r=>r.url().includes('/auth/login')&&r.request().method()==='POST',{timeout:20000}).catch(()=>null);
  await page.locator('button[type="submit"]:visible').click();
  const lr=await loginResp;
  await page.waitForTimeout(5000);
  const out={loginStatus:lr?lr.status():null,afterLoginUrl:page.url(),cookies:(await ctx.cookies()).map(c=>({name:c.name,httpOnly:c.httpOnly}))};
  net.length=0;
  await page.goto(BASE+'/admin',{waitUntil:'domcontentloaded',timeout:90000});
  await page.waitForTimeout(8000);
  const body=(await page.locator('body').innerText()).replace(/\s+/g,' ');
  out.admin={url:page.url(),net:[...net],hasForbidden:/403|دسترسی|مجاز نیست/.test(body),tables:await page.locator('main table').count(),excerpt:body.slice(0,260)};
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
