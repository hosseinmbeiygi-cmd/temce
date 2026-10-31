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
  await page.waitForTimeout(6000);
  const info=await page.evaluate(()=>{
    const rect=(el)=>{if(!el)return null;const r=el.getBoundingClientRect();return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height),right:Math.round(r.right)};};
    const q=(s)=>document.querySelector(s);
    const cs=(el)=>el?{ml:getComputedStyle(el).marginLeft,mr:getComputedStyle(el).marginRight,pl:getComputedStyle(el).paddingLeft,pr:getComputedStyle(el).paddingRight,display:getComputedStyle(el).display,pos:getComputedStyle(el).position,dir:getComputedStyle(el).direction}:null;
    const overflow=[...document.querySelectorAll('body *')].map(el=>({el,r:el.getBoundingClientRect()})).filter(x=>x.r.right>window.innerWidth+2||x.r.left<-2).slice(0,8).map(x=>({tag:x.el.tagName,cls:(x.el.className||'').toString().slice(0,100),rect:[Math.round(x.r.x),Math.round(x.r.y),Math.round(x.r.width)],right:Math.round(x.r.right)}));
    return {
      dir:document.documentElement.dir, bodyDir:getComputedStyle(document.body).direction,
      scrollWidth:document.documentElement.scrollWidth, innerWidth:window.innerWidth,
      html:rect(document.documentElement), body:rect(document.body),
      main:rect(q('main')), mainStyle:cs(q('main')),
      aside:rect(q('aside')), asideStyle:cs(q('aside')),
      header:rect(q('header')), nav:rect(q('nav')),
      mainCls:(q('main')?.className||'').toString().slice(0,200),
      asideCls:(q('aside')?.className||'').toString().slice(0,200),
      overflow,
    };
  });
  console.log(JSON.stringify(info,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
