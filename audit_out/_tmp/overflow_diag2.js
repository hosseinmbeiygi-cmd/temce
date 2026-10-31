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
    const R=(el)=>{const r=el.getBoundingClientRect();return [Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.right)];};
    const main=document.querySelector('main'), pe=document.querySelector('.page-enter');
    const wide=[...main.querySelectorAll('*')].map(el=>({el,sw:el.scrollWidth,ow:el.offsetWidth,r:el.getBoundingClientRect()})).filter(x=>x.sw>1700||x.ow>1700).sort((a,b)=>b.sw-a.sw).slice(0,12).map(x=>({tag:x.el.tagName,cls:(x.el.className||'').toString().slice(0,150),sw:x.sw,ow:x.ow,rect:R(x.el)}));
    return {mainSW:main.scrollWidth,mainOW:main.offsetWidth,peSW:pe?.scrollWidth,peOW:pe?.offsetWidth,mainOverflowX:getComputedStyle(main).overflowX,wide};
  });
  console.log(JSON.stringify(info,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
