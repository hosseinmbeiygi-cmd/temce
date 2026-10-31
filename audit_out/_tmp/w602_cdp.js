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
  const geo=await page.evaluate(()=>{
    const main=document.querySelector('main'), p=main.parentElement, h=document.querySelector('header'), hi=h?.firstElementChild;
    const g=(el)=>{const cs=getComputedStyle(el);return {offsetWidth:el.offsetWidth,clientWidth:el.clientWidth,borderLeft:cs.borderLeftWidth,borderRight:cs.borderRightWidth,paddingLeft:cs.paddingLeft,paddingRight:cs.paddingRight,marginLeft:cs.marginLeft,marginRight:cs.marginRight,marginInlineStart:cs.marginInlineStart,marginInlineEnd:cs.marginInlineEnd,direction:cs.direction,boxSizing:cs.boxSizing,rect:el.getBoundingClientRect().toJSON()};};
    return {main:g(main),parent:g(p),header:g(h),headerInner:hi?g(hi):null};
  });
  const cdp=await ctx.newCDPSession(page); await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
  const {root}=await cdp.send('DOM.getDocument',{depth:-1});
  const {nodeId}=await cdp.send('DOM.querySelector',{nodeId:root.nodeId,selector:'main'});
  const matched=await cdp.send('CSS.getMatchedStylesForNode',{nodeId});
  const rules=[];
  for(const m of matched.matchedCSSRules||[]){
    const sel=m.rule.selectorList.text; const props=(m.rule.style.cssProperties||[]).filter(p=>/margin|width|max-width/i.test(p.name)).map(p=>`${p.name}:${p.value}`);
    if(props.length) rules.push({sel,props,origin:m.rule.origin,parent:m.rule.parentRule?.selectorList?.text||null});
  }
  console.log(JSON.stringify({geo,rules},null,2));
  await browser.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
