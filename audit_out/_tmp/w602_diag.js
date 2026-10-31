const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1920,height:1080},serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_w602_20261031');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditW602-20261031!');
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:25000}).catch(()=>{});
  await page.waitForTimeout(6000);
  const info=await page.evaluate(()=>{
    const R=(el)=>{const r=el.getBoundingClientRect();return [Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height),Math.round(r.right)];};
    const C=(el)=>({tag:el.tagName,cls:(el.className||'').toString().slice(0,140),rect:R(el),offsetLeft:el.offsetLeft,offsetParent:el.offsetParent?.className?.toString().slice(0,80)||null,display:getComputedStyle(el).display,position:getComputedStyle(el).position,float:getComputedStyle(el).float,width:getComputedStyle(el).width,maxWidth:getComputedStyle(el).maxWidth,minWidth:getComputedStyle(el).minWidth,margin:getComputedStyle(el).margin,marginInlineStart:getComputedStyle(el).marginInlineStart,marginInlineEnd:getComputedStyle(el).marginInlineEnd,marginLeft:getComputedStyle(el).marginLeft,marginRight:getComputedStyle(el).marginRight,padding:getComputedStyle(el).padding,paddingInlineStart:getComputedStyle(el).paddingInlineStart,paddingInlineEnd:getComputedStyle(el).paddingInlineEnd,direction:getComputedStyle(el).direction,boxSizing:getComputedStyle(el).boxSizing});
    const main=document.querySelector('main'), parent=main.parentElement;
    const siblings=[...parent.children].map(C);
    const header=document.querySelector('header');
    const headerKids=header?[...header.querySelectorAll(':scope > *, :scope > * > *')].slice(0,12).map(C):[];
    const leftBand=[...document.querySelectorAll('body *')].map(el=>({el,r:el.getBoundingClientRect()})).filter(x=>x.r.width>100&&x.r.height>200&&x.r.x<320&&x.r.right>0).slice(0,15).map(x=>({...C(x.el),rect:R(x.el)}));
    return {main:C(main),parent:C(parent),siblings,header:C(header),headerKids,leftBand,scrollWidth:document.documentElement.scrollWidth,innerWidth:innerWidth};
  });
  console.log(JSON.stringify(info,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
