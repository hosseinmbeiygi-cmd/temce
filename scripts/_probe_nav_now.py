"""Direct probe of Nav.php for known-good symbols — is upstream down right now?"""
import asyncio
import sys

sys.path.insert(0, ".")

from brsapi.client import get_client
from brsapi.config import BrsApiEndpoints
from brsapi.parsers import TsetmcParser


async def main() -> None:
    client = await get_client()
    for s in ["اهرم", "آرام", "آسا", "ابتکار"]:
        r = await client.fetch(BrsApiEndpoints.NAV, params={"l18": s})
        if not r.success:
            print(f"{s}: FAIL {r.error}")
        else:
            resp = r.value
            rec = None if resp.is_empty else TsetmcParser.parse_nav(resp.data)
            print(f"{s}: http={resp.status_code} empty={resp.is_empty} nav={rec and rec.get('nav_issue')}")
        await asyncio.sleep(11)


asyncio.run(main())
