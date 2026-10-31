const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1920,height:1080},serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_layout_20261031');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditLayout-20261031!');
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:25000}).catch(()=>{});
  await page.waitForTimeout(6000);
  const m=()=>page.evaluate(()=>{const el=document.querySelector('main');const r=el.getBoundingClientRect();const pe=document.querySelector('.page-enter');return {sw:document.documentElement.scrollWidth,iw:innerWidth,scrollX:window.scrollX,mainX:Math.round(r.x),mainW:Math.round(r.width),mainOffsetLeft:el.offsetLeft,mainTransform:getComputedStyle(el).transform,peTransform:pe?getComputedStyle(pe).transform:null,peSW:pe?.scrollWidth};});
  const out={}; out['1920']=await m();
  await page.setViewportSize({width:1440,height:900}); await page.waitForTimeout(1500); out['1440']=await m();
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
