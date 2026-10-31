const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
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
    await page.setViewportSize({width:w,height:h}); await page.waitForTimeout(1200); out[w]={normal:[]};
    for(let i=0;i<3;i++){out[w].normal.push(await m()); await page.waitForTimeout(2500);}
    const el=await page.addStyleTag({content:'.dash-field::after{animation:none!important;transform:translate3d(-2.2%,1.6%,0) scale(1.05)!important}'});
    await page.waitForTimeout(400); out[w].worst=await m(); await el.evaluate(n=>n.remove());
  }
  await page.setViewportSize({width:1920,height:1080}); await page.waitForTimeout(800);
  await page.screenshot({path:'audit_out/_tmp/show_dashboard_fixed3_1920.png',fullPage:false});
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
