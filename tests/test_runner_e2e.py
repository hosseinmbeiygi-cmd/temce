import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from httpx import ASGITransport, AsyncClient

from apps.api.app import app


async def t():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/v1/tests/run")
        print("POST /tests/run status:", r.status_code)
        if r.status_code == 200:
            j = r.json()
            print("success:", j.get("success"))
            if j.get("data"):
                d = j["data"]
                print(f"total: {d['total']}, passed: {d['passed']}, failed: {d['failed']}, duration: {d['duration']}s")
                for res in d.get("results", []):
                    if res["status"] == "failed":
                        print(f"  FAILED: {res['name']}: {res['message'][:100]}")
            else:
                print("error:", j.get("error"))


asyncio.run(t())
