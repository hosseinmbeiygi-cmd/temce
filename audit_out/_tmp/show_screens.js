const { chromium } = require('playwright');
const BASE='http://127.0.0.1:3000';
const U='audit_ui_demo_20261031', P='AuditDemo-20261031!';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'});
  for(const p of ['**/api/v1/market/enriched-heatmap**','**/api/v1/market-dashboard**','**/api/v1/news**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  const shot=async(name)=>{await page.screenshot({path:'audit_out/_tmp/'+name,fullPage:false}); console.log('shot',name,page.url());};
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded',timeout:90000});
  for(let i=0;i<20;i++){const ok=await page.evaluate(()=>{const x=document.querySelector('input[placeholder="نام کاربری خود را وارد کنید"]');return x?Reflect.ownKeys(x).map(String).some(k=>/reactProps/.test(k)):false;}).catch(()=>false); if(ok)break; await page.waitForTimeout(1000);}
  await page.waitForTimeout(1000);
  await shot('show_login.png');
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(U);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(P);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(x=>!String(x).includes('/auth/login'),{timeout:25000}).catch(()=>{});
  await page.waitForTimeout(5000);
  await shot('show_dashboard.png');
  try{
    await page.goto(BASE+'/gold/portfolio',{waitUntil:'domcontentloaded',timeout:90000});
    await page.waitForTimeout(12000);
    await shot('show_portfolio.png');
  }catch(e){console.log('portfolio failed',String(e).slice(0,100));}
  try{
    await page.goto(BASE+'/backtest',{waitUntil:'domcontentloaded',timeout:90000});
    await page.waitForTimeout(6000);
    await shot('show_backtest.png');
  }catch(e){console.log('backtest failed',String(e).slice(0,100));}
  console.log('done');
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
