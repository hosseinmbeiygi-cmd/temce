const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
const USERS={admin:'audit_ui_admin_20261030_a1', user:'audit_ui_user_20261030_u1'};
const PASS='AuditUi-20261030!';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const out={};
  for (const [role,user] of Object.entries(USERS)) {
    const ctx=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
    for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
    const page=await ctx.newPage();
    const net=[];
    page.on('response',r=>{const u=r.url(); if(u.includes('/auth/')||u.includes('/api/v1/dashboard')||u.includes('/api/v1/jobs')||u.includes('/api/v1/brsapi/sync')) net.push(r.status()+' '+r.request().method()+' '+u.replace(BASE,''));});
    await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000}); await page.waitForTimeout(6000);
    await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(user);
    await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
    await page.locator('button[type="submit"]:visible').click();
    await page.waitForTimeout(4000);
    const cookies1=(await ctx.cookies()).map(c=>({name:c.name,domain:c.domain,httpOnly:c.httpOnly,secure:c.secure,path:c.path}));
    const afterLogin={url:page.url(),cookies:cookies1,net:[...net]};
    net.length=0;
    await page.goto(BASE+'/admin',{waitUntil:'domcontentloaded',timeout:90000});
    await page.waitForTimeout(7000);
    const cookies2=(await ctx.cookies()).map(c=>({name:c.name,domain:c.domain,httpOnly:c.httpOnly,secure:c.secure,path:c.path}));
    const body=(await page.locator('body').innerText()).replace(/\s+/g,' ');
    out[role]={afterLogin, afterAdmin:{url:page.url(),cookies:cookies2,net:[...net],hasAdminText:/پنل مدیریت/.test(body),has403:/403|دسترسی|مجاز نیست/.test(body),excerpt:body.slice(0,220)}};
    await ctx.close();
  }
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
