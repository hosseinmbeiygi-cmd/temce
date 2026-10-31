const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'});
  const page=await ctx.newPage();
  const css=[]; page.on('response',r=>{const u=r.url(); if(u.endsWith('.css')||u.includes('styles'))css.push(r.status()+' '+u.replace(BASE,''));});
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_demo_20261031');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditDemo-20261031!');
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:25000}).catch(()=>{});
  await page.waitForTimeout(5000);
  await page.goto(BASE+'/backtest',{waitUntil:'domcontentloaded',timeout:90000});
  await page.waitForTimeout(5000);
  const info=await page.evaluate(()=>({
    url:location.href,
    sheets:[...document.styleSheets].map(s=>s.href||'inline'),
    bodyBg:getComputedStyle(document.body).backgroundColor,
    mainBg:getComputedStyle(document.querySelector('main')||document.body).backgroundColor,
    tailwindApplied:getComputedStyle(document.querySelector('main')||document.body).display,
    htmlClass:document.documentElement.className.slice(0,120),
    width:document.documentElement.scrollWidth,
    viewport:window.innerWidth,
  }));
  console.log(JSON.stringify({info,css},null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
