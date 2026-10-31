const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1920,height:1080},serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_demo_20261031');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditDemo-20261031!');
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:25000}).catch(()=>{});
  await page.waitForTimeout(5000);
  const info=await page.evaluate(()=>{
    const R=(el)=>{if(!el)return null;const r=el.getBoundingClientRect();return [Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)];};
    const C=(el)=>({tag:el.tagName,cls:(el.className||'').toString().slice(0,120),rect:R(el),display:getComputedStyle(el).display,pos:getComputedStyle(el).position,ml:getComputedStyle(el).marginLeft,mr:getComputedStyle(el).marginRight,pl:getComputedStyle(el).paddingLeft,pr:getComputedStyle(el).paddingRight,dir:getComputedStyle(el).direction});
    const main=document.querySelector('main');
    const chain=[]; let el=main; for(let i=0;i<6&&el;i++,el=el.parentElement) chain.push(C(el));
    const bodyKids=[...document.body.children].map(C);
    const leftBand=[...document.querySelectorAll('body *')].filter(x=>{const r=x.getBoundingClientRect();return r.width>250&&r.width<400&&r.x<20&&r.height>400;}).slice(0,6).map(C);
    return {bodyKids,chain,leftBand,scrollWidth:document.documentElement.scrollWidth,innerWidth:innerWidth};
  });
  console.log(JSON.stringify(info,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
