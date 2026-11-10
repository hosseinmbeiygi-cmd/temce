"""GoldAPI.io client — international XAU/USD price.

GoldAPI.io provides real-time international gold prices in USD.
API key is read from the ``GOLDAPI_KEY`` env var.

Endpoint: GET https://www.goldapi.io/api/XAU/USD
Header:   x-access-token: <key>

This module is intentionally thin — no DB, no cache, no side effects.
Integration into the snapshot service overlay is in snapshot_service.py.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

GOLDAPI_BASE = "https://www.goldapi.io/api"
GOLDAPI_TIMEOUT_SECONDS: float = 8.0


async def fetch_xau_usd(
    key: str,
    client: httpx.AsyncClient | None = None,
) -> float | None:
    """قیمت بین‌المللی XAU/USD از goldapi.io.

    Args:
        key: کلید API goldapi.io.
        client: کلاینت httpx — اگر None باشد یک کلاینت موقت می‌سازد.

    Returns:
        float قیمت XAU/USD در دلار، یا None در صورت هر نوع خطا.
    """
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=GOLDAPI_TIMEOUT_SECONDS)
    try:
        resp = await client.get(
            f"{GOLDAPI_BASE}/XAU/USD",
            headers={"x-access-token": key, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        price = data.get("price")
        if price is None or float(price) <= 0:
            logger.warning("goldapi.io returned invalid price: %r", price)
            return None
        return float(price)
    except Exception as exc:  # noqa: BLE001
        logger.warning("goldapi.io fetch failed: %s", exc)
        return None
    finally:
        if close_client:
            await client.aclose()


def get_goldapi_key() -> str | None:
    """GOLDAPI_KEY از محیط — None اگر تنظیم نشده یا خالی."""
    return os.getenv("GOLDAPI_KEY") or None


async def get_goldapi_xau_usd() -> float | None:
    """XAU/USD از goldapi.io با کلید از env.

    Returns None بدون هیچ درخواست شبکه‌ای اگر GOLDAPI_KEY تنظیم نشده باشد.
    """
    key = get_goldapi_key()
    if not key:
        return None
    return await fetch_xau_usd(key)
