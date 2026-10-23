/**
 * QA UI crawl (F-UI): drives every Next.js route with Playwright/Chromium and
 * records render status, latency, console errors and a screenshot.
 *
 * Usage:
 *   node qa/ui_crawl.mjs [baseURL] [outDir]
 *
 * Writes:
 *   <outDir>/ui_crawl_results.json   machine-readable per-route metrics
 *   <outDir>/screenshots/<slug>.png  one screenshot per route
 */
import { chromium } from 'playwright';
import { readFileSync, mkdirSync, writeFileSync } from 'fs';
import path from 'path';

const BASE = process.argv[2] || 'http://localhost:3001';
const OUT = process.argv[3] || 'reports';
const SHOTS = path.join(OUT, 'screenshots');
const ROUTES_FILE = process.env.QA_ROUTES || '/tmp/routes.txt';

// Dynamic segments get a concrete sample value so the page actually renders.
const SEGMENT_VALUES = {
  symbol: 'فولاد',
  id: '1',
  sheetId: '1',
  fid: '1',
  assetId: '1',
  alertId: '1',
};

mkdirSync(SHOTS, { recursive: true });

const routes = readFileSync(ROUTES_FILE, 'utf8')
  .split('\n')
  .map((l) => l.trim())
  .filter(Boolean);

const concretise = (r) =>
  r.replace(/\[[^\]]+\]/g, (m) => {
    const key = m.slice(1, -1).split(':').pop().replace(/^\.\.\./, '');
    return SEGMENT_VALUES[key] || '1';
  });

const slug = (r) =>
  r === '/' ? 'root' : r.replace(/^\//, '').replace(/[/?=&]/g, '_').slice(0, 120);

const browser = await chromium.launch();
const results = [];

for (const route of routes) {
  const target = concretise(route);
  const url = BASE + target;
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 400));
  });
  page.on('pageerror', (err) => pageErrors.push(String(err).slice(0, 400)));
  page.on('requestfailed', (req) => {
    const f = req.failure();
    // Backend is intentionally not running during this crawl; record but do not fail.
    failedRequests.push(`${req.url().slice(0, 200)} :: ${f ? f.errorText : 'unknown'}`);
  });

  const rec = { route, target, url };
  const t0 = Date.now();

  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    rec.httpStatus = resp ? resp.status() : null;

    // Give client components time to hydrate and paint.
    await page.waitForTimeout(2500);

    rec.ttfbMs = Date.now() - t0;

    const perf = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] || {};
      const paints = {};
      for (const p of performance.getEntriesByType('paint')) {
        paints[p.name] = Math.round(p.startTime);
      }
      const body = document.body;
      const text = (body ? body.innerText : '').trim();
      return {
        domContentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
        loadEvent: Math.round(nav.loadEventEnd || 0),
        firstPaint: paints['first-paint'] ?? null,
        firstContentfulPaint: paints['first-contentful-paint'] ?? null,
        textLength: text.length,
        // A page that rendered nothing but shell markup is "blank".
        isBlank: text.length < 5,
        hasErrorBoundaryText:
          /Application error|Unhandled Runtime Error|Something went wrong|This page could not be found|500|Internal Server Error/i.test(
            text
          ),
        h1: (document.querySelector('h1')?.innerText || '').slice(0, 120),
      };
    });
    rec.perf = perf;
    rec.latencyMs = Date.now() - t0;

    const file = path.join(SHOTS, `${slug(route)}.png`);
    await page.screenshot({ path: file, fullPage: false });
    rec.screenshot = path.relative(process.cwd(), file);

    if (perf.isBlank) rec.status = 'BLANK';
    else if (perf.hasErrorBoundaryText) rec.status = 'ERROR_BOUNDARY';
    else if (rec.httpStatus && rec.httpStatus >= 500) rec.status = 'HTTP_5XX';
    else if (rec.httpStatus === 404) rec.status = 'NOT_FOUND';
    else rec.status = 'OK';
  } catch (err) {
    rec.status = 'NAV_ERROR';
    rec.error = String(err).slice(0, 300);
    rec.latencyMs = Date.now() - t0;
    try {
      const file = path.join(SHOTS, `${slug(route)}.png`);
      await page.screenshot({ path: file, fullPage: false });
      rec.screenshot = path.relative(process.cwd(), file);
    } catch {}
  }

  rec.consoleErrorCount = consoleErrors.length;
  rec.pageErrorCount = pageErrors.length;
  rec.failedRequestCount = failedRequests.length;
  rec.consoleErrors = consoleErrors.slice(0, 10);
  rec.pageErrors = pageErrors.slice(0, 10);
  rec.failedRequests = failedRequests.slice(0, 10);

  results.push(rec);
  console.log(
    `${rec.status.padEnd(14)} ${String(rec.latencyMs ?? '-').padStart(6)}ms  ` +
      `ce=${rec.consoleErrorCount} pe=${rec.pageErrorCount}  ${route}`
  );

  await context.close();
}

await browser.close();

writeFileSync(path.join(OUT, 'ui_crawl_results.json'), JSON.stringify(results, null, 2));

const by = (s) => results.filter((r) => r.status === s).length;
const lat = results.map((r) => r.latencyMs).filter((n) => typeof n === 'number').sort((a, b) => a - b);
const pct = (p) => (lat.length ? lat[Math.min(lat.length - 1, Math.floor(lat.length * p))] : null);

const summary = {
  base: BASE,
  total: results.length,
  OK: by('OK'),
  BLANK: by('BLANK'),
  ERROR_BOUNDARY: by('ERROR_BOUNDARY'),
  NOT_FOUND: by('NOT_FOUND'),
  HTTP_5XX: by('HTTP_5XX'),
  NAV_ERROR: by('NAV_ERROR'),
  routesWithConsoleErrors: results.filter((r) => r.consoleErrorCount > 0).length,
  routesWithPageErrors: results.filter((r) => r.pageErrorCount > 0).length,
  totalConsoleErrors: results.reduce((a, r) => a + r.consoleErrorCount, 0),
  totalPageErrors: results.reduce((a, r) => a + r.pageErrorCount, 0),
  latencyMs: { p50: pct(0.5), p90: pct(0.9), p95: pct(0.95), max: lat[lat.length - 1] ?? null },
};

writeFileSync(path.join(OUT, 'ui_crawl_summary.json'), JSON.stringify(summary, null, 2));
console.log('\n=== SUMMARY ===');
console.log(JSON.stringify(summary, null, 2));