"""Raw probe of BrsApi NAV (l18) for a few symbols - no retries, no DB."""

import asyncio
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from brsapi.client import get_client
from brsapi.config import BrsApiEndpoints

SYMBOLS = ["ابتکار", "ابتکار2", "آرمانی", "آسا2", "ارکیده2", "آتی1", "ارزش2", "فولاد"]


async def main() -> None:
    client = await get_client()
    endpoint = BrsApiEndpoints.NAV
    url = client._base_url + endpoint.path
    for symbol in SYMBOLS:
        params = client._build_params(endpoint, {"l18": symbol})
        resp = await client._client.get(url, params=params)
        body = " ".join(resp.text[:150].split())
        print(f"{symbol!r:>24} -> HTTP {resp.status_code} | {body}", flush=True)
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
