"""Live collectors: Tgju (free USD) + Nobitex (USDT).

Design: per-venue graceful degradation. Any fetch/parse/sanity failure falls
back to the fixture value for that venue only — the snapshot is always
complete. ``official_cbi`` and ``nima`` have no free JSON API, so they always
come from the fixture baseline (update them via CURRENCY_OVERRIDE_JSON).

Tgju ``price_dollar_rl`` = daily OHLC in RIAL ("rl"); we convert to Toman (/10).
Columns of the latest row (data[0]): [open, low, high, close, change, change%,
gregorian, jalali].
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from apps.currency_service.domain.entities import RatePair, RateSnapshot
from apps.currency_service.infra.fixtures import load_fixture_snapshot
from core.logging import get_logger

logger = get_logger(__name__)

TGJU_SUMMARY_URL = "https://api.tgju.org/v1/market/indicator/summary-table-data/{slug}"
NOBITEX_STATS_URL = "https://api.nobitex.ir/market/stats"
HTTP_TIMEOUT = 8.0

# Sanity band (Toman) — outside this, the source is considered broken.
USD_TOMAN_MIN = 50_000
USD_TOMAN_MAX = 5_000_000


def _num(cell: str | float) -> float:
    """'2,272,050' or '<span ...>61450</span>' or 61450 -> float."""
    s = re.sub(r"<[^>]+>", "", str(cell)).replace(",", "").replace("%", "").strip()
    return float(s)


def parse_tgju_row(row: list) -> tuple[float, float, float]:
    """Extract (close_toman, open_toman, change_pct) from a tgju summary row.

    Raises ValueError on malformed/unparsable rows.
    """
    if len(row) < 6:
        raise ValueError("tgju row too short")
    close = _num(row[3]) / 10.0  # RIAL -> Toman
    open_ = _num(row[0]) / 10.0
    chg_pct = _num(row[5])
    if not (USD_TOMAN_MIN < close < USD_TOMAN_MAX):
        raise ValueError(f"tgju close {close} outside sanity band")
    return close, open_, chg_pct


async def fetch_tgju_dollar(client: httpx.AsyncClient) -> RatePair | None:
    """Free-market USD from tgju. buy≈open, sell≈close (daily OHLC proxy)."""
    try:
        r = await client.get(TGJU_SUMMARY_URL.format(slug="price_dollar_rl"))
        r.raise_for_status()
        data = r.json()["data"]
        if not data:
            raise ValueError("empty tgju data")
        close, open_, chg = parse_tgju_row(data[0])
        return RatePair(
            name="دلار بازار آزاد",
            source="tgju (زنده)",
            buy_price=int(min(open_, close)),
            sell_price=int(max(open_, close)),
            daily_change_pct=chg,
        )
    except Exception:
        logger.warning("tgju fetch failed; falling back to fixture", exc_info=True)
        return None


async def fetch_nobitex_usdt(client: httpx.AsyncClient) -> RatePair | None:
    """USDT/IRT from Nobitex public stats (values are Toman strings)."""
    try:
        r = await client.get(NOBITEX_STATS_URL)
        r.raise_for_status()
        pair = r.json()["stats"]["USDT-IRT"]
        buy = int(float(pair["buy"]))
        sell = int(float(pair["sell"]))
        last = float(pair["last"])
        day_open = float(pair.get("dayOpenPrice") or last)
        if not (USD_TOMAN_MIN < last < USD_TOMAN_MAX):
            raise ValueError(f"nobitex last {last} outside sanity band")
        chg = ((last - day_open) / day_open) * 100.0 if day_open else 0.0
        return RatePair(
            name="تتر (USDT)",
            source="nobitex (زنده)",
            buy_price=buy,
            sell_price=sell,
            daily_change_pct=round(chg, 2),
        )
    except Exception:
        logger.warning("nobitex fetch failed; falling back to fixture", exc_info=True)
        return None


class LiveCollector:
    """Tgju + Nobitex with per-venue fixture fallback.

    ``official_cbi``/``nima`` always come from the fixture (no free API).
    """

    async def fetch(self) -> RateSnapshot:
        fixture = load_fixture_snapshot()
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"}
        ) as client:
            free = await fetch_tgju_dollar(client) or fixture.free
            usdt = await fetch_nobitex_usdt(client) or fixture.usdt
        return RateSnapshot(
            timestamp=datetime.now(tz=timezone.utc),
            free=free,
            usdt=usdt,
            nima=fixture.nima,
            official_cbi=fixture.official_cbi,
        )
