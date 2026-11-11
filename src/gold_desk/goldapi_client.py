"""International XAU/USD price — goldapi.io (key) + Binance PAXG (free).

Sources (priority order):
  1. goldapi.io  — if ``GOLDAPI_KEY`` env var is set (paid, spot price).
  2. Binance PAXG/USDT — free, no key, real-time (1 PAXG = 1 troy oz gold).

Both sources are thin async functions: no DB, no cache, no side effects.
Integration into the snapshot service is in snapshot_service.py.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

GOLDAPI_BASE = "https://www.goldapi.io/api"
GOLDAPI_TIMEOUT_SECONDS: float = 8.0

OKX_PAXG_URL = "https://www.okx.com/api/v5/market/ticker?instId=PAXG-USDT"
OKX_TIMEOUT_SECONDS: float = 6.0


# ─── goldapi.io (key-based) ───────────────────────────────────────────────────

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


# ─── Binance PAXG/USDT (free, no key) ────────────────────────────────────────

async def fetch_paxg_binance(
    client: httpx.AsyncClient | None = None,
) -> float | None:
    """قیمت XAU/USD از OKX PAXG/USDT — رایگان، بدون کلید API.

    PAX Gold (PAXG) هر توکن برابر ۱ انس تروی طلای فیزیکی است.
    از OKX استفاده می‌شود — Binance از ایران block است (HTTP 451).

    Returns:
        float قیمت در دلار، یا None در صورت هر نوع خطا.
    """
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=OKX_TIMEOUT_SECONDS)
    try:
        resp = await client.get(OKX_PAXG_URL)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") or []
        if not items:
            logger.warning("OKX PAXG returned empty data")
            return None
        price = items[0].get("last")
        if price is None or float(price) <= 0:
            logger.warning("OKX PAXG returned invalid price: %r", price)
            return None
        return float(price)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OKX PAXG fetch failed: %s", exc)
        return None
    finally:
        if close_client:
            await client.aclose()


# ─── combined: best available international price ────────────────────────────

async def get_international_xau_usd() -> float | None:
    """بهترین قیمت موجود XAU/USD از منابع بین‌المللی.

    اولویت:
      1. goldapi.io اگر GOLDAPI_KEY تنظیم باشد (قیمت اسپات دقیق‌تر).
      2. Binance PAXG/USDT (رایگان، real-time، بدون کلید).

    Returns None فقط اگر هر دو منبع شکست بخورند.
    """
    # 1. goldapi.io
    key = get_goldapi_key()
    if key:
        price = await fetch_xau_usd(key)
        if price:
            return price
        logger.warning("goldapi.io failed; falling back to Binance PAXG")

    # 2. Binance PAXG
    return await fetch_paxg_binance()

