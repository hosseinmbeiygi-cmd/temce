"""Test the actual screener API endpoint."""
import asyncio
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv()

from httpx import ASGITransport, AsyncClient

from apps.api.app import app


async def test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test GET /screener
        print("=== GET /screener ===")
        resp = await client.get(
            "/screener",
            params={"sort_by": "smc_score", "sort_order": "desc", "limit": 10},
        )
        data = resp.json()
        if data.get("success"):
            items = data["data"]["items"]
            print(f"  Total: {data['data']['total']}, items returned: {len(items)}")
            for item in items[:5]:
                print(
                    f"  {item['symbol']}: smc={item['smc_score']:.4f}, phase={item['phase']}, "
                    f"volume={item['volume']}, reason={item['reason']}"
                )
        else:
            print(f"  FAILED: {data.get('error')}")


asyncio.run(test())
