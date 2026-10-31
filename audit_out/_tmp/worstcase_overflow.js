const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
const base='.dash-field::after{clip-path:none!important;animation:none!important;transform:translate3d(-2.2%,1.6%,0) scale(1.05)!important}';
const variants={
  'worst-base':base,
  'worst-page-clip':base+'.page-enter{overflow-x:clip!important}',
  'worst-root-clip':base+'html,body{overflow-x:clip!important}',
  'worst-after-overflow-clip':base+'.dash-field::after{overflow:clip!important}',
  'worst-after-clip-path':base+'.dash-field::after{clip-path:inset(0)!important}',
  'worst-willchange-auto':base+'.dash-field::after{will-change:auto!important}',
  'worst-contain-paint':base+'.dash-field::after{contain:paint!important}',
};
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1920,height:1080},serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_layout3_20261031');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditLayout-20261031!');
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:25000}).catch(()=>{});
  await page.waitForTimeout(5000);
  const m=()=>page.evaluate(()=>({sw:document.documentElement.scrollWidth,iw:innerWidth,peSW:document.querySelector('.page-enter')?.scrollWidth}));
  const out={};
  for(const [w,h] of [[1440,900],[1920,1080]]){
    await page.setViewportSize({width:w,height:h}); await page.waitForTimeout(800); out[w]={};
    for(const [name,css] of Object.entries(variants)){
      const el=await page.addStyleTag({content:css}); await page.waitForTimeout(400); out[w][name]=await m(); await el.evaluate(n=>n.remove()); await page.waitForTimeout(150);
    }
  }
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
