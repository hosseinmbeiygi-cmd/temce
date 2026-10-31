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
  const m=()=>page.evaluate(()=>{const main=document.querySelector('main');const hi=document.querySelector('header')?.firstElementChild;const r=main.getBoundingClientRect(),h=hi?.getBoundingClientRect();return {sw:document.documentElement.scrollWidth,iw:innerWidth,mainX:Math.round(r.x),mainW:Math.round(r.width),mainRight:Math.round(r.right),headerInnerX:h?Math.round(h.x):null,headerInnerW:h?Math.round(h.width):null};});
  const out={}; out['1920']=await m();
  await page.setViewportSize({width:1440,height:900}); await page.waitForTimeout(1200); out['1440']=await m();
  await page.setViewportSize({width:1920,height:1080}); await page.waitForTimeout(800);
  await page.screenshot({path:'audit_out/_tmp/show_dashboard_w602_fixed_1920.png',fullPage:false});
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
