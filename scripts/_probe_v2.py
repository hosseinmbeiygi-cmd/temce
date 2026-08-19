"""Probe Nav.php for a version-2 symbol (ابتکار2) — show raw response shape."""
import asyncio
import sys

sys.path.insert(0, ".")

from brsapi.client import get_client
from brsapi.config import BrsApiEndpoints


async def main() -> None:
    client = await get_client()
    for s in ["ابتکار2", "اتکاسا3", "آتی1"]:
        r = await client.fetch(BrsApiEndpoints.NAV, params={"l18": s})
        if not r.success:
            print(f"{s}: fetch FAIL → {r.error}")
        else:
            resp = r.value
            print(f"{s}: http={resp.status_code} is_empty={resp.is_empty}")
            print(f"   data={str(resp.data)[:250]}")
        await asyncio.sleep(11)


asyncio.run(main())
