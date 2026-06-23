from __future__ import annotations

from typing import Any

import httpx

from core.result import Result


class TsetmcClient:
    """
    Lightweight async client for TSETMC public endpoints.
    """

    BASE_URL = "https://cdn.tsetmc.com/api"

    async def get_closing_price_info(self, ins_code: str) -> Result[dict[str, Any]]:
        """
        Get latest closing price info by instrument code, also known as insCode.
        """
        url = f"{self.BASE_URL}/ClosingPrice/GetClosingPriceInfo/{ins_code}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)

            if response.status_code != 200:
                return Result.fail(f"TSETMC error {response.status_code}: {response.text}")

            data = response.json()

            if not data:
                return Result.fail("Empty response from TSETMC")

            return Result.ok(data)

        except httpx.TimeoutException:
            return Result.fail("TSETMC request timeout")

        except httpx.HTTPError as exc:
            return Result.fail(f"TSETMC HTTP error: {exc}")

        except Exception as exc:
            return Result.fail(f"TSETMC unexpected error: {exc}")
