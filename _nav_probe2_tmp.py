"""Probe NAV endpoint for base vs digit-suffixed fund symbols (raw, 1 req / 11s)."""

import asyncio
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

from brsapi.client import get_client
from brsapi.config import BrsApiEndpoints

SYMBOLS = [
    "ابتکار",
    "ابتکار2",
    "آسا",
    "آسا2",
    "آرمانی",
    "آتیه ملت",
    "آتیه ملت4",
    "آتی",
    "آتی1",
]


async def main() -> None:
    client = await get_client()
    endpoint = BrsApiEndpoints.NAV
    url = client._base_url + endpoint.path
    for symbol in SYMBOLS:
        try:
            params = client._build_params(endpoint, {"l18": symbol})
            resp = await client._client.get(url, params=params)
            body = " ".join(resp.text[:200].split())
            print(f"{symbol} -> HTTP {resp.status_code} | {body}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"{symbol} -> ERROR {type(exc).__name__}: {exc}", flush=True)
        await asyncio.sleep(11)


if __name__ == "__main__":
    asyncio.run(main())
