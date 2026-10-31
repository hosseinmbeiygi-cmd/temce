const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
const variants={
  'none':'',
  'hide-after':'.dash-field::after{display:none!important}',
  'inset0':'.dash-field::after{inset:0!important}',
  'inset0-noanim':'.dash-field::after{inset:0!important;animation:none!important}',
  'page-overflow-clip':'.page-enter{overflow-x:clip!important}',
  'page-anim-none':'.page-enter{animation:none!important}',
  'after-anim-none':'.dash-field::after{animation:none!important}',
  'after-clip-path':'.dash-field::after{clip-path:inset(0)!important}',
  'root-overflow-clip':'html,body{overflow-x:clip!important}',
  'dash-overflow-clip':'.dash-field{overflow:clip!important}',
  'page-contain-paint':'.page-enter{contain:paint!important}',
};
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
  await page.waitForTimeout(5000);
  const measure=()=>page.evaluate(()=>{const m=document.querySelector('main');const r=m?.getBoundingClientRect();return {sw:document.documentElement.scrollWidth,iw:innerWidth,mainX:r?Math.round(r.x):null,peSW:document.querySelector('.page-enter')?.scrollWidth};});
  const out={};
  for (const [w,h] of [[1440,900],[1920,1080]]) {
    await page.setViewportSize({width:w,height:h}); await page.waitForTimeout(1200);
    out[w]={};
    for (const [name,css] of Object.entries(variants)) {
      let el=null;
      if(css) el=await page.addStyleTag({content:css});
      await page.waitForTimeout(400);
      out[w][name]=await measure();
      if(el) await el.evaluate(n=>n.remove());
      await page.waitForTimeout(200);
    }
  }
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
