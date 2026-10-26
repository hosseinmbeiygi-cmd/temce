"""Secondary Source — fallback زمانی که BrsApi قطع است.

TGJU.org scraper با درخواست هم‌زمان + پشتیبانی ارقام فارسی.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TGJU_URL = "https://www.tgju.org"

# Persian/Arabic → English digits
_PERSIAN_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _fa2en(s: str) -> str:
    return s.translate(_PERSIAN_MAP)


def _to_float(raw: str) -> float | None:
    """تبدیل متن قیمت/درصد به float با حذف کاما، درصد، ارقام فارسی."""
    try:
        cleaned = _fa2en(raw.strip().replace(",", "").replace("٬", "").replace("%", "").replace("٪", ""))
        # keep only digits, dot, minus
        cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
        if not cleaned or cleaned in (".", "-", "-."):
            return None
        return float(cleaned)
    except Exception:
        return None


@dataclass(frozen=True)
class TGJUPrice:
    symbol: str
    price_irt: float
    change_pct: float | None
    source: str = "tgju"
    unit: str = "toman"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# Map: tgju slug → (canonical name, factor to Toman, source unit)
# TGJU gold/coin pages are quoted in Toman; the currency pages whose slug ends
# in ``_rl`` are quoted in Rial. The old blanket "price > 2,000,000 → /10"
# divided 18k gold and full coins by 10 as well, corrupting every gold fallback.
TGJU_SYMBOLS: dict[str, tuple[str, float, str]] = {
    "geram18": ("IR_GOLD_18K", 1.0, "toman"),
    "coin-emami": ("IR_COIN_EMAMI", 1.0, "toman"),
    "coin-bahar": ("IR_COIN_BAHAR", 1.0, "toman"),
    "coin-half": ("IR_COIN_HALF", 1.0, "toman"),
    "coin-quarter": ("IR_COIN_QUARTER", 1.0, "toman"),
    "price_dollar_rl": ("USD", 0.1, "rial"),
    "price_aed": ("AED", 0.1, "rial"),
    "ons": ("XAUUSD", 1.0, "usd"),
}


async def fetch_tgju_page(slug: str, client: httpx.AsyncClient) -> str | None:
    """HTML صفحه TGJU برای یک symbol با client مشترک."""
    url = f"{TGJU_URL}/{slug}"
    try:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Temce GoldDesk)"})
        r.raise_for_status()
        return r.text
    except Exception as exc:
        logger.warning("TGJU fetch failed for %s: %s", slug, exc)
        return None


def _parse_price(html: str) -> tuple[float, float | None] | None:
    """استخراج قیمت و درصد تغییر از HTML."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        price_el = soup.select_one('[data-col="info.last_trade.PDrCotVal"]')
        if not price_el:
            # fallback: try generic price class
            price_el = soup.select_one(".info-price span")
            if not price_el:
                return None
        price = _to_float(price_el.get_text(strip=True))
        if price is None:
            return None
        change_el = soup.select_one('[data-col="info.last_trade.PDChCotVal"]')
        change: float | None = None
        if change_el:
            change = _to_float(change_el.get_text(strip=True))
        return (price, change)
    except Exception as exc:
        logger.debug("TGJU parse failed: %s", exc)
        return None


async def _fetch_one(slug: str, client: httpx.AsyncClient) -> TGJUPrice | None:
    if slug not in TGJU_SYMBOLS:
        return None
    html = await fetch_tgju_page(slug, client)
    if not html:
        return None
    parsed = _parse_price(html)
    if not parsed:
        return None
    price, change = parsed
    canonical, factor, source_unit = TGJU_SYMBOLS[slug]
    # واحد هر slug صریح است (بالا)؛ هیچ heuristic بزرگی/کوچکی روی قیمت نیست.
    # قیمت نهایی قرارداد بازار ایران تومان است (BrsApi هم تومان می‌دهد).
    price = price * factor
    return TGJUPrice(
        symbol=canonical,
        price_irt=price,
        change_pct=change,
        unit="usd" if source_unit == "usd" else "toman",
    )


async def fetch_prices(symbols: list[str] | None = None) -> list[TGJUPrice]:
    """دریافت قیمت از TGJU برای چند symbol — هم‌زمان."""

    targets = symbols or list(TGJU_SYMBOLS.keys())
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        tasks = [_fetch_one(slug, client) for slug in targets if slug in TGJU_SYMBOLS]
        results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def is_available() -> bool:
    """آیا TGJU در دسترسه؟"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(TGJU_URL, follow_redirects=True)
            return r.status_code == 200
    except Exception:
        return False
