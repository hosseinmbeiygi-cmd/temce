import sys, asyncio, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from httpx import AsyncClient, ASGITransport
from apps.api.app import app

async def t():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Test 404 format
        r = await c.get("/api/v1/codal/XXX/profile")
        print("404:", json.dumps(r.json(), ensure_ascii=False))

        # Test sentiment
        r = await c.get("/api/v1/analysis/sentiment")
        print("sentiment keys:", list(r.json().get("data", {}).keys()))

        # Test trends
        r = await c.get("/api/v1/analysis/trends")
        d = r.json().get("data")
        print("trends type:", type(d).__name__)
        if isinstance(d, list) and len(d) > 0:
            print("trends[0] keys:", list(d[0].keys()))
        elif isinstance(d, dict):
            print("trends keys:", list(d.keys()))

        # Test recommendations
        r = await c.get("/api/v1/analysis/recommendations")
        print("rec keys:", list(r.json().get("data", [{}])[0].keys()))

        # Test elliot
        r = await c.get("/api/v1/analysis/elliot-waves/XXX")
        print("elliot keys:", list(r.json().get("data", {}).keys()))

        # Test liquidity
        r = await c.get("/api/v1/analysis/liquidity")
        print("liq keys:", list(r.json().get("data", {}).keys()))

        # Test interest rates
        r = await c.get("/api/v1/analysis/interest-rates")
        print("int keys:", list(r.json().get("data", {}).keys()))

        # Test profit prediction
        r = await c.get("/api/v1/analysis/profit-prediction/XXX")
        print("profit keys:", list(r.json().get("data", {}).keys()))

asyncio.run(t())

