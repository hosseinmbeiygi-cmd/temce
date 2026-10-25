"""Live UI crawl: 148 routes, status+console+blank heuristics+screenshots."""
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.async_api import async_playwright

BASE = "http://localhost:3000"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "test-screenshots")
os.makedirs(OUT, exist_ok=True)

def slug(r):
    s = re.sub(r"[^a-z0-9]+", "-", r.strip("/").lower()) or "root"
    return s[:60]

async def main():
    cat = json.load(open("qa/route_catalog.json", encoding="utf-8"))
    routes = cat["routes"]
    s0 = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    s1 = int(sys.argv[2]) if len(sys.argv) > 2 else len(routes)
    routes = routes[s0:s1]
    off = s0
    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="chrome", args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1366, "height": 768})
        page = await ctx.new_page()
        for i, r in enumerate(routes):
            url = BASE + (r.replace(":param", "test"))
            errs, failed = [], []
            def _con(m):
                if m.type == "error":
                    errs.append(m.text[:150])
            def _rf(q):
                failed.append(f"{q.url[:90]}:{q.failure}")
            page.on("console", _con)
            page.on("requestfailed", _rf)
            rec = {"route": r, "url": url}
            try:
                resp = await page.goto(url, wait_until="commit", timeout=120000)
                await page.wait_for_timeout(4000)
                rec["status"] = resp.status if resp else -1
                rec["final_url"] = page.url
                rec["redirected_to_login"] = "/auth/login" in page.url
                n = await page.evaluate(
                    "() => document.querySelectorAll('body :not(script):not(style)').length")
                txt = await page.evaluate(
                    "() => (document.body.innerText || '').length")
                rec["dom_nodes"] = n
                rec["text_len"] = txt
                bad = await page.evaluate(
                    "() => { const t = document.body.innerText || ''; "
                    "const m = t.match(/NaN%?|undefined|null|\\[object Object\\]|01\\/01\\/1970/g); "
                    "return m ? [...new Set(m)] : []; }")
                rec["corrupt_tokens"] = bad
                if rec["redirected_to_login"]:
                    rec["verdict"] = "REDIRECT-login(expected-protected-or-auth)"
                elif n < 5 or txt < 20:
                    rec["verdict"] = "BLANK?"
                elif bad:
                    rec["verdict"] = "CORRUPT-DATA?"
                else:
                    rec["verdict"] = "OK"
                shot = os.path.join(OUT, f"{i:03d}_{slug(r)}.png")
                await page.screenshot(path=shot, full_page=False)
                rec["shot"] = os.path.basename(shot)
            except Exception as e:
                rec["status"] = -1
                rec["verdict"] = f"LOAD-FAIL: {str(e)[:120]}"
            rec["console_errors"] = len(errs)
            rec["req_failed"] = len(failed)
            results.append(rec)
            print(f"[{i+1}/{len(routes)}] {r} -> {rec['verdict']} s={rec.get('status')}", flush=True)
            # detach listeners
            page.remove_listener("console", _con)
            page.remove_listener("requestfailed", _rf)
        await browser.close()
    json.dump(results, open("qa/crawl_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ok = sum(1 for r in results if r["verdict"] == "OK")
    red = sum(1 for r in results if str(r["verdict"]).startswith("REDIRECT"))
    bad = [r for r in results if r["verdict"] not in ("OK",) and not str(r["verdict"]).startswith("REDIRECT")]
    print(f"DONE ok={ok} redirect={red} attention={len(bad)}")

asyncio.run(main())
