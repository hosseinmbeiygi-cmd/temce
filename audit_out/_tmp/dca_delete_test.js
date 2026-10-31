const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const BASE='http://127.0.0.1:3000', API='http://127.0.0.1:8000/api/v1';
const USER='audit_ui_storage_20261031', PASS='AuditStorage-20261031!';
const UID='usr_4f65d5f2daa349a39fc0a9fd';
const NAME='AUD-UI-DCA-DELETE-20261031';
function db(sql){return execFileSync('docker',['exec','tse_timescaledb','psql','-U','quant_dev','-d','tse_quant_verify','-At','-F','|','-c',sql],{encoding:'utf8'}).trim();}
(async()=>{
  const lr=await fetch(API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:USER,password:PASS})});
  const token=(await lr.json()).data.access_token;
  const H={Authorization:'Bearer '+token};
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'});
  const ctx=await browser.newContext({viewport:{width:1680,height:1400},serviceWorkers:'block'});
  for (const p of ['**/api/v1/market/**','**/api/v1/market-dashboard**','**/api/v1/news**','**/api/v1/economic-calendar**','**/api/v1/brsapi/**']) await ctx.route(p,r=>r.abort());
  const page=await ctx.newPage();
  await page.goto(BASE+'/auth/login',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(6000);
  await page.locator('input[placeholder="نام کاربری خود را وارد کنید"]:visible').fill(USER);
  await page.locator('input[placeholder="رمز عبور خود را وارد کنید"]:visible').fill(PASS);
  await page.locator('button[type="submit"]:visible').click();
  await page.waitForURL(u=>!String(u).includes('/auth/login'),{timeout:20000}).catch(()=>{});
  await page.waitForLoadState('networkidle',{timeout:30000}).catch(()=>{});
  await page.goto(BASE+'/gold/portfolio',{waitUntil:'domcontentloaded'}); await page.waitForTimeout(4000);
  await page.getByRole('button',{name:'پلن‌های DCA',exact:true}).click();
  await page.locator('input[placeholder="نام پلن"]:visible').fill(NAME);
  await page.getByRole('button',{name:'ساخت پلن',exact:true}).click();
  let plan=null;
  for(let i=0;i<20;i++){
    const list=await (await fetch(API+'/gold/portfolio/dca',{headers:H})).json();
    plan=(list.data||[]).find(p=>p.name===NAME); if(plan) break; await new Promise(r=>setTimeout(r,500));
  }
  const created={planId:plan?.plan_id??null, uiHasCard:(await page.locator('main').innerText()).includes(NAME), db:db(`select count(*) from gold_dca_plans where user_id='${UID}' and name='${NAME}'`)};
  await page.getByRole('button',{name:`حذف پلن ${NAME}`,exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:'حذف پلن',exact:true}).click();
  let gone=false;
  for(let i=0;i<20;i++){
    const list=await (await fetch(API+'/gold/portfolio/dca',{headers:H})).json();
    gone=!(list.data||[]).some(p=>p.name===NAME); if(gone) break; await new Promise(r=>setTimeout(r,500));
  }
  const after={goneFromApi:gone, uiCardGone:!(await page.locator('main').innerText()).includes(NAME), db:db(`select count(*) from gold_dca_plans where user_id='${UID}' and name='${NAME}'`)};
  console.log(JSON.stringify({created,after},null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
