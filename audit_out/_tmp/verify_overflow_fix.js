const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1920,height:1080},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill('audit_ui_layout_20261031');
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill('AuditLayout-20261031!');
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:25000}).catch(()=>{});
  await page.waitForTimeout(5000);
  const measure=()=>page.evaluate(()=>{const m=document.querySelector('main');const r=m?.getBoundingClientRect();return {sw:document.documentElement.scrollWidth,iw:innerWidth,mainX:r?Math.round(r.x):null,mainW:r?Math.round(r.width):null,peSW:document.querySelector('.page-enter')?.scrollWidth};});
  const out={};
  out['1920']=await measure();
  await page.screenshot({path:'audit_out/_tmp/show_dashboard_fixed_1920.png',fullPage:false});
  await page.setViewportSize({width:1440,height:900}); await page.waitForTimeout(1500);
  out['1440']=await measure();
  console.log(JSON.stringify(out,null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
