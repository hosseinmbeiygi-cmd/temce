import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(channel="chrome", args=["--no-sandbox"])
        p = await (await b.new_context()).new_page()
        for r in ["/", "/markets", "/admin"]:
            resp = await p.goto("http://localhost:3000" + r,
                                wait_until="domcontentloaded", timeout=30000)
            await p.wait_for_timeout(2000)
            print(r, resp.status, p.url,
                  await p.evaluate("() => document.body.innerText.length"))
        await b.close()

asyncio.run(main())
