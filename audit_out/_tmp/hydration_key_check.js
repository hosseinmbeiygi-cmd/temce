const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/Iran/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe' });
  const page = await (await browser.newContext({viewport:{width:1400,height:1000}})).newPage();
  await page.goto('http://127.0.0.1:3000/auth/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  const res = await page.evaluate(() => {
    const btn = document.querySelector('button[type="submit"]');
    const inputs = [...document.querySelectorAll('input')];
    return {
      submitKeys: btn ? Reflect.ownKeys(btn).map(String).filter(k => /react|fib/i.test(k)) : null,
      inputKeys: inputs.map(i => Reflect.ownKeys(i).map(String).filter(k => /react|fib/i.test(k))),
      readyState: document.readyState,
      dcl: performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart,
      loadEnd: performance.timing.loadEventEnd ? performance.timing.loadEventEnd - performance.timing.navigationStart : null,
      buttons: document.querySelectorAll('button').length,
    };
  });
  console.log(JSON.stringify(res, null, 2));
  await browser.close();
})();
