"""Cached service layer for the Iran physical-market analytics endpoints.

Data sources are the BrsApi tables already populated by the scheduler
(``brsapi_commodity_prices``, ``brsapi_currency_prices``,
``brsapi_gold_coin_prices``, ``brsapi_ime_certificates``) plus
``gold_snapshots`` for rolling history.  No number is fabricated: a missing
quote produces ``available: false`` with the missing symbols/reason.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.commodity import (
    CommodityPriceModel,
    CurrencyPriceModel,
    GoldCoinPriceModel,
)
from brsapi.models.ime import ImeCertificateModel
from core.cache import get_cache
from core.config.ime_engine import load_ime_config
from core.logging import get_logger
from services.gold.physical_market import (
    aed_hawala_spread,
    calculate_coin_bubbles_with_history,
    calculate_ime_certificate_spread,
    evaluate_aed_hawala_alert,
    validate_ime_position_limit,
)
from src.gold_desk.models import GoldSnapshotModel

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 30
COIN_HISTORY_LIMIT = 200
AED_HISTORY_LIMIT = 200

XAU_SYMBOL = "XAUUSD"
USD_SYMBOL = "USD"
AED_SYMBOL = "AED"
MELTED_GRAM18_SYMBOL = "IR_GOLD_18K"
COIN_PRICE_SYMBOLS: tuple[str, ...] = (
    "IR_COIN_EMAMI",
    "IR_COIN_BAHAR",
    "IR_COIN_HALF",
    "IR_COIN_QUARTER",
    "IR_COIN_1G",
)

COINS_CACHE_KEY = "gold:analytics:coins:{history_limit}"
ARBITRAGE_CACHE_KEY = (
    "gold:analytics:arbitrage:{quantity_grams}:{holding_days}:{storage}:{delivery}"
)
AED_HISTORY_CACHE_KEY = "gold:analytics:aed-history:{limit}"

_GRAM_UNITS = {"g", "gram", "grams", "گرم"}
_KILOGRAM_UNITS = {"kg", "kilogram", "kilograms", "کیلوگرم"}


def _grams_per_contract(size: Any, unit: Any) -> float | None:
    """Convert an IME contract size to grams, or return ``None`` if unknown."""
    try:
        numeric_size = float(size)
    except (TypeError, ValueError):
        return None
    if numeric_size <= 0:
        return None

    normalized = str(unit or "").strip().lower()
    if normalized in _GRAM_UNITS:
        return numeric_size
    if normalized in _KILOGRAM_UNITS:
        return numeric_size * 1_000.0
    return None


async def _latest_commodity_price(session: AsyncSession, symbol: str) -> float | None:
    stmt = (
        select(CommodityPriceModel.price)
        .where(
            CommodityPriceModel.symbol == symbol,
            CommodityPriceModel.price.isnot(None),
        )
        .order_by(desc(CommodityPriceModel.id))
        .limit(1)
    )
    value = (await session.execute(stmt)).scalar()
    return float(value) if value is not None and value > 0 else None


async def _latest_currency_prices(
    session: AsyncSession, symbols: tuple[str, ...]
) -> dict[str, float]:
    stmt = (
        select(CurrencyPriceModel)
        .where(
            CurrencyPriceModel.symbol.in_(symbols),
            CurrencyPriceModel.price.isnot(None),
        )
        .order_by(desc(CurrencyPriceModel.id))
    )
    rows = (await session.execute(stmt)).scalars().all()
    prices: dict[str, float] = {}
    for row in rows:
        if row.symbol in prices:
            continue
        if row.price is not None and row.price > 0:
            prices[row.symbol] = float(row.price)
    return prices


async def _latest_coin_prices(
    session: AsyncSession, symbols: tuple[str, ...]
) -> dict[str, float]:
    stmt = (
        select(GoldCoinPriceModel)
        .where(
            GoldCoinPriceModel.symbol.in_(symbols),
            GoldCoinPriceModel.price.isnot(None),
        )
        .order_by(desc(GoldCoinPriceModel.id))
    )
    rows = (await session.execute(stmt)).scalars().all()
    prices: dict[str, float] = {}
    for row in rows:
        if row.symbol in prices:
            continue
        if row.price is not None and row.price > 0:
            prices[row.symbol] = float(row.price)
    return prices


async def _load_coin_market_state(session: AsyncSession) -> dict[str, Any]:
    xau = await _latest_commodity_price(session, XAU_SYMBOL)
    currencies = await _latest_currency_prices(session, (USD_SYMBOL,))
    usd = currencies.get(USD_SYMBOL)

    missing: list[str] = []
    if xau is None:
        missing.append(XAU_SYMBOL)
    if usd is None:
        missing.append(USD_SYMBOL)
    if missing:
        return {
            "available": False,
            "reason": "missing reference price(s): " + ", ".join(missing),
            "missing_symbols": missing,
        }

    coin_prices = await _latest_coin_prices(session, COIN_PRICE_SYMBOLS)
    missing_coins = [symbol for symbol in COIN_PRICE_SYMBOLS if symbol not in coin_prices]
    if not coin_prices:
        return {
            "available": False,
            "reason": "no coin prices available",
            "missing_symbols": missing_coins,
        }

    return {
        "available": True,
        "xau_usd": xau,
        "usd_irr": usd,
        "coin_prices": coin_prices,
        "missing_symbols": missing_coins,
    }


async def _load_bubble_history(
    session: AsyncSession, symbols: list[str], limit: int
) -> dict[str, list[float]]:
    history: dict[str, list[float]] = {}
    for symbol in symbols:
        stmt = (
            select(GoldSnapshotModel.bubble_pct)
            .where(
                GoldSnapshotModel.symbol == symbol,
                GoldSnapshotModel.bubble_pct.isnot(None),
            )
            .order_by(desc(GoldSnapshotModel.snapshot_at))
            .limit(limit)
        )
        values = [
            float(value)
            for value in (await session.execute(stmt)).scalars().all()
            if value is not None
        ]
        history[symbol] = list(reversed(values))
    return history


async def _load_arbitrage_state(session: AsyncSession) -> dict[str, Any]:
    coin_prices = await _latest_coin_prices(session, (MELTED_GRAM18_SYMBOL,))
    melted = coin_prices.get(MELTED_GRAM18_SYMBOL)
    if melted is None:
        return {
            "available": False,
            "reason": f"{MELTED_GRAM18_SYMBOL} melted price unavailable",
            "missing_symbols": [MELTED_GRAM18_SYMBOL],
        }

    stmt = (
        select(ImeCertificateModel)
        .where(
            ImeCertificateModel.price_last.isnot(None),
            ImeCertificateModel.contract_size.isnot(None),
            ImeCertificateModel.contract_size > 0,
        )
        .order_by(desc(ImeCertificateModel.id))
        .limit(50)
    )
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        grams = _grams_per_contract(row.contract_size, row.contract_size_unit)
        if grams is None or row.price_last is None or row.price_last <= 0:
            continue
        return {
            "available": True,
            "cert_price_per_gram_irr": float(row.price_last) / grams,
            "cert_price_last_irr": float(row.price_last),
            "cert_contract_code": row.contract_code,
            "cert_contract_size": row.contract_size,
            "cert_contract_size_unit": row.contract_size_unit,
            "melted_gram18_price_irr": melted,
            "source": "brsapi_ime_certificates+brsapi_gold_coin_prices",
        }

    return {
        "available": False,
        "reason": "IME certificate contract size unit is not gram-compatible",
        "missing_symbols": ["IME_CERTIFICATE"],
    }


async def _load_aed_history(session: AsyncSession, limit: int) -> list[dict[str, Any]]:
    stmt = (
        select(
            GoldSnapshotModel.snapshot_at,
            GoldSnapshotModel.usd_irt,
            GoldSnapshotModel.aed_irt,
        )
        .where(
            GoldSnapshotModel.usd_irt.isnot(None),
            GoldSnapshotModel.aed_irt.isnot(None),
        )
        .order_by(desc(GoldSnapshotModel.snapshot_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()

    points: list[dict[str, Any]] = []
    for snapshot_at, usd_irt, aed_irt in reversed(rows):
        if usd_irt is None or aed_irt is None or usd_irt <= 0 or aed_irt <= 0:
            continue
        points.append(
            {
                "snapshot_at": (
                    snapshot_at.isoformat()
                    if hasattr(snapshot_at, "isoformat")
                    else str(snapshot_at)
                ),
                "usd_irt": float(usd_irt),
                "aed_irt": float(aed_irt),
            }
        )
    return points


async def get_coin_bubble_report(
    session: AsyncSession, *, history_limit: int = COIN_HISTORY_LIMIT
) -> dict[str, Any]:
    """All available coin bubbles with nominal/percent bubble and history stats."""
    key = COINS_CACHE_KEY.format(history_limit=history_limit)
    cache = get_cache()
    cached = await cache.get(key)
    if cached is not None:
        return cached

    state = await _load_coin_market_state(session)
    if not state.get("available"):
        result: dict[str, Any] = {
            "available": False,
            "reason": state.get("reason"),
            "coins": {},
            "missing_symbols": state.get("missing_symbols", []),
            "history_limit": history_limit,
        }
    else:
        history = await _load_bubble_history(
            session, list(state["coin_prices"]), history_limit
        )
        coins = calculate_coin_bubbles_with_history(
            state["xau_usd"],
            state["usd_irr"],
            state["coin_prices"],
            history_by_coin=history,
        )
        result = {
            "available": True,
            "ounce_usd": state["xau_usd"],
            "usd_irr": state["usd_irr"],
            "coins": coins,
            "missing_symbols": state.get("missing_symbols", []),
            "history_limit": history_limit,
            "source": "brsapi_gold_coin_prices+brsapi_commodity_prices+gold_snapshots",
        }

    await cache.set(key, result, ttl=CACHE_TTL_SECONDS)
    return result


async def get_ime_arbitrage_report(
    session: AsyncSession,
    *,
    quantity_grams: float = 1.0,
    holding_days: int = 0,
    storage_irr_per_gram_per_day: float | None = None,
    delivery_irr_per_gram: float | None = None,
) -> dict[str, Any]:
    """IME certificate vs Tehran melted spread with config-driven limits."""
    config = load_ime_config().get("physical_market", {}) or {}
    storage = (
        storage_irr_per_gram_per_day
        if storage_irr_per_gram_per_day is not None
        else config.get("storage_irr_per_gram_per_day") or 0.0
    )
    delivery = (
        delivery_irr_per_gram
        if delivery_irr_per_gram is not None
        else config.get("delivery_irr_per_gram") or 0.0
    )
    if holding_days is None:
        holding_days = int(config.get("holding_days") or 0)

    key = ARBITRAGE_CACHE_KEY.format(
        quantity_grams=quantity_grams,
        holding_days=holding_days,
        storage=storage,
        delivery=delivery,
    )
    cache = get_cache()
    cached = await cache.get(key)
    if cached is not None:
        return cached

    state = await _load_arbitrage_state(session)
    if not state.get("available"):
        result: dict[str, Any] = {
            "available": False,
            "reason": state.get("reason"),
            "missing_symbols": state.get("missing_symbols", []),
        }
    else:
        spread = calculate_ime_certificate_spread(
            state["cert_price_per_gram_irr"],
            state["melted_gram18_price_irr"],
            quantity_grams=quantity_grams,
            storage_irr_per_gram_per_day=storage,
            holding_days=holding_days,
            delivery_irr_per_gram=delivery,
        )
        limit_check = validate_ime_position_limit(
            quantity_grams,
            position_limit_grams=config.get("ime_certificate_position_limit_grams"),
            ownership_limit_grams=config.get("ime_certificate_ownership_limit_grams"),
        )
        result = {
            "available": True,
            "source": state["source"],
            "cert_contract_code": state["cert_contract_code"],
            "cert_contract_size": state["cert_contract_size"],
            "cert_contract_size_unit": state["cert_contract_size_unit"],
            "cert_price_per_gram_irr": state["cert_price_per_gram_irr"],
            "cert_price_last_irr": state["cert_price_last_irr"],
            "melted_gram18_price_irr": state["melted_gram18_price_irr"],
            **spread,
            "limit_check": limit_check,
        }

    await cache.set(key, result, ttl=CACHE_TTL_SECONDS)
    return result


async def get_aed_history_report(
    session: AsyncSession, *, limit: int = AED_HISTORY_LIMIT
) -> dict[str, Any]:
    """AED hawala spread history with per-point z-score and alert flag."""
    key = AED_HISTORY_CACHE_KEY.format(limit=limit)
    cache = get_cache()
    cached = await cache.get(key)
    if cached is not None:
        return cached

    config = load_ime_config().get("physical_market", {}) or {}
    alert_zscore = config.get("aed_hawala_alert_zscore")
    rows = await _load_aed_history(session, limit)

    if not rows:
        result: dict[str, Any] = {
            "available": False,
            "reason": "no gold snapshot history with USD and AED prices",
            "series": [],
            "current": None,
            "alert_zscore": alert_zscore,
        }
    else:
        series: list[dict[str, Any]] = []
        history_pct: list[float] = []
        for row in rows:
            point = aed_hawala_spread(row["usd_irt"], row["aed_irt"])
            stats = evaluate_aed_hawala_alert(
                history_pct, point["spread_pct"], alert_zscore=alert_zscore
            )
            series.append(
                {
                    **row,
                    **point,
                    "z_score": stats["z_score"],
                    "percentile": stats["percentile"],
                    "alert": stats["alert"],
                }
            )
            history_pct.append(point["spread_pct"])

        current = {**series[-1], "alert_zscore": alert_zscore}
        result = {
            "available": True,
            "series": series,
            "current": current,
            "alert_zscore": alert_zscore,
            "sample_size": len(series),
        }

    await cache.set(key, result, ttl=CACHE_TTL_SECONDS)
    return result


__all__ = [
    "AED_HISTORY_CACHE_KEY",
    "AED_HISTORY_LIMIT",
    "ARBITRAGE_CACHE_KEY",
    "CACHE_TTL_SECONDS",
    "COINS_CACHE_KEY",
    "COIN_HISTORY_LIMIT",
    "get_aed_history_report",
    "get_coin_bubble_report",
    "get_ime_arbitrage_report",
]
