"""Secondary Source — fallback زمانی که BrsApi قطع است.

TGJU.org scraper با درخواست هم‌زمان + پشتیبانی ارقام فارسی.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

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


# Map: tgju slug → (canonical name, factor)
# "ons" در TGJU قیمت اونس به دلار است — مستقیماً XAUUSD
TGJU_SYMBOLS: dict[str, tuple[str, float]] = {
    "geram18": ("IR_GOLD_18K", 1.0),
    "coin-emami": ("IR_COIN_EMAMI", 1.0),
    "coin-bahar": ("IR_COIN_BAHAR", 1.0),
    "coin-half": ("IR_COIN_HALF", 1.0),
    "coin-quarter": ("IR_COIN_QUARTER", 1.0),
    "price_dollar_rl": ("USD", 1.0),
    "price_aed": ("AED", 1.0),
    "ons": ("XAUUSD", 1.0),
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
    # TGJU ریال برمی‌گرداند برای ارز/طلا → اگر > 1e6 ریال ≈ تومان/10
    # اما همه قیمت‌های ریالی TGJU برحسب ریال هستند — تبدیل به تومان با /10 اگر خیلی بزرگ
    # برای سازگاری با BrsApi که تومان است: اگه price > 10_000_000 → فرض ریال و /10
    # (این heuristic فقط وقتی قیمت مشکوک بزرگ است اعمال می‌شود)
    # توجه: "ons" دلار است و نباید تبدیل ریال شود.
    canonical, _ = TGJU_SYMBOLS[slug]
    if canonical != "XAUUSD" and price > 5_000_000:
        # احتمالاً ریال است — به تومان تبدیل کن
        # اما این مبدل را فقط زمانی اعمال می‌کنیم که قیمت غیرمنطقی برای تومان باشد
        # (دلار 800k تومان واقعی، ریال 8M) — اگر XAUUSD نیست
        # نرمال: دلار ≈ 700k-900k تومان → اگر 7M-9M → ریال بوده
        if price > 2_000_000:
            price = price / 10.0
    return TGJUPrice(symbol=canonical, price_irt=price, change_pct=change)


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
