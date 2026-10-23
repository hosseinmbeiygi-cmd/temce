/* Headless dashboard inspection (authenticated in-page): login from inside the
 * page context (same-origin fetch → httpOnly refresh cookie), then capture
 * console errors, failed API calls, per-widget render state and a screenshot. */
const { chromium } = require("playwright-core");

const BASE = "http://localhost:3000";
const USER = { username: "dashview_tmp", password: "Dash#View2026!" };
const WIDGETS = [
  "NewsStrip", "QuoteCards", "GlobalMarkets", "TrendChart",
  "TripleChartsGroup", "MarketMap", "MarketOverview", "OwnershipChange",
  "IndexImpacts", "EventCalendar", "LiquidityBlocks", "AssetAllocationPie",
];

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1050 } });
  const page = await ctx.newPage();

  const consoleErrors = [];
  const pageErrors = [];
  const badResponses = [];
  const okApi = new Set();

  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 180)); });
  page.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 200)));
  page.on("response", (r) => {
    const u = r.url();
    if (!u.includes("/api/") || u.includes("/auth/")) return;
    if (r.status() >= 400) badResponses.push(`${r.status()} ${u.slice(u.indexOf("/api/"), u.indexOf("/api/") + 70)}`);
    else okApi.add(u.slice(u.indexOf("/api/")).split("?")[0]);
  });

  await page.goto(BASE + "/auth/login", { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForTimeout(2500);
  const loginRes = await page.evaluate(async (u) => {
    const r = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(u),
      credentials: "include",
    });
    return r.status;
  }, USER);
  console.log("in-page LOGIN:", loginRes);
  if (loginRes !== 200) process.exit(2);

  const t0 = Date.now();
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 90000 });
  // Dev server / HMR can re-navigate; poll until the widget set is stable.
  // Also scroll to the bottom so contentIndex widgets mount fully.
  let last = -1, stable = 0, waited = 0;
  while (waited < 60000 && stable < 2) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight)).catch(() => {});
    await page.waitForTimeout(4000); waited += 4000;
    const st = await page.evaluate(() => document.querySelectorAll("[data-widget]").length).catch(() => -1);
    if (st === last && st > 0) stable++; else stable = 0;
    last = st;
  }
  await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {});
  const loadMs = Date.now() - t0;
  const finalUrl = page.url();

  const widgetReport = [];
  for (const w of WIDGETS) {
    const el = page.locator(`[data-widget="${w}"]`).first();
    let found = false;
    let info = null;
    // locator.count() can race with HMR re-renders; retry a few times
    for (let attempt = 0; attempt < 3; attempt++) {
      found = (await el.count().catch(() => 0)) > 0;
      if (found) break;
      await page.waitForTimeout(1500);
    }
    if (!found) { widgetReport.push({ widget: w, found: false }); continue; }
    try {
    info = await el.evaluate((node) => {
      const text = (node.innerText || "").trim();
      const banners = [...node.querySelectorAll("[role='status']")].filter((n) =>
        /ارتباط با سرور برقرار نشد|داده زنده‌ای از سرور دریافت نشد/.test(n.textContent || "")
      );
      const degText = [...node.querySelectorAll("*")]
        .map((n) => (n.childElementCount === 0 ? n.textContent || "" : ""))
        .filter((t) => /در دسترس نیست|موجود نیست/.test(t || ""))
        .slice(0, 2);
      return {
        textLen: text.length,
        preview: text.replace(/\s+/g, " ").slice(0, 95),
        degradedBanner: banners.length,
        svgCount: node.querySelectorAll("svg").length,
        degText,
      };
    });
    } catch (e) {
      // HMR/navigation race — retry once after letting things settle
      await page.waitForTimeout(4000);
      try {
        found = (await el.count()) > 0;
        if (!found) throw new Error("still missing after retry");
        info = await el.evaluate((node) => {
          const text = (node.innerText || "").trim();
          const banners = [...node.querySelectorAll("[role='status']")].filter((n) =>
            /ارتباط با سرور برقرار نشد|داده زنده‌ای از سرور دریافت نشد/.test(n.textContent || "")
          );
          return {
            textLen: text.length,
            degradedBanner: banners.length,
            svgCount: node.querySelectorAll("svg").length,
          };
        });
      } catch (e2) {
        widgetReport.push({ widget: w, found: false, evalError: String(e2).slice(0, 80) });
        continue;
      }
    }
    widgetReport.push({ widget: w, found, ...info });
  }

  await page.screenshot({ path: "dashboard_live.png", fullPage: true });

  console.log(JSON.stringify({
    loadMs,
    finalUrl,
    okApiCount: okApi.size,
    widgetReport,
    badResponses: badResponses.slice(0, 25),
    pageErrors: pageErrors.slice(0, 8),
    consoleErrors: consoleErrors.slice(0, 10),
  }, null, 1));

  await browser.close();
})().catch((e) => { console.error("FATAL:", e && e.message); process.exit(1); });
