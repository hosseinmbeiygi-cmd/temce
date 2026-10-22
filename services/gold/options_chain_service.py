"""Cached options-chain service backed by the existing BrsApi IME tables.

Current contracts come from ``brsapi_ime_options`` and forwards come from
``brsapi_ime_futures``.  Both tables are populated by the existing BrsApi
sync jobs.  The service never calls a network provider.

Historical IV observations are persisted per contract in
``gold_option_iv_history`` (STEP 5-FIX-2): the daily
``GoldOptionIvSnapshotJob`` writes one row per ``(symbol, as_of, strike)``
and :meth:`ImeOptionsChainProvider.load_iv_history` reads the series back.
When the table holds no observation for a contract the report exposes
``iv_history_source = "unavailable"`` with the reason; nothing is inferred.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.ime import ImeFutureModel, ImeOptionModel
from core.cache import get_cache
from core.logging import get_logger
from models.gold_options import GoldOptionIvHistoryModel
from services.gold.options_chain import (
    DEFAULT_IV_HISTORY_LIMIT,
    OptionsChainProvider,
    build_options_chain_report,
)

logger = get_logger(__name__)

OPTIONS_CHAIN_CACHE_TTL_SECONDS = 30
OPTIONS_CHAIN_CACHE_KEY = "gold:analytics:options:chain:{commodity}:{limit}:{forward}:{rate}:{thresholds}"
# Minimum stored days before iv_rank / iv_percentile are reported.  The
# configured value lives at derivatives.options.iv_history_min_days.
DEFAULT_IV_HISTORY_MIN_DAYS = 30


def _matches_commodity(row: ImeOptionModel, commodity: str | None) -> bool:
    if not commodity:
        return True
    needle = commodity.strip().lower()
    if not needle:
        return True
    fields = (
        row.contract_category_commodity,
        row.contract_category,
        row.contract_category_sub,
        row.call_contract_description,
        row.put_contract_description,
    )
    return any(
        needle in str(value).strip().lower()
        for value in fields
        if value is not None and str(value).strip()
    )


def _previous_oi(current: int | None, change: int | None) -> int | None:
    if current is None or change is None:
        return None
    return current - change


class ImeOptionsChainProvider(OptionsChainProvider):
    """Read current IME option/future rows from the existing database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_contracts(
        self, *, commodity: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        scan_limit = max(limit * 4, 200)
        statement = (
            select(ImeOptionModel)
            .order_by(desc(ImeOptionModel.id))
            .limit(scan_limit)
        )
        rows = (await self.session.execute(statement)).scalars().all()

        contracts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            if not _matches_commodity(row, commodity):
                continue
            strike = row.strike_price
            if strike is None or strike <= 0:
                continue

            for option_type in ("call", "put"):
                code = getattr(row, f"{option_type}_contract_code")
                price = getattr(row, f"{option_type}_price_last")
                if not code or price is None or price <= 0:
                    continue
                if code in seen:
                    continue
                seen.add(code)
                current_oi = getattr(row, f"{option_type}_open_interest")
                oi_change = getattr(row, f"{option_type}_open_interest_change")
                contracts.append(
                    {
                        "contract_key": str(code),
                        "symbol": str(code),
                        "option_type": option_type,
                        "strike": float(strike),
                        "market_price": float(price),
                        "open_interest": current_oi,
                        "previous_open_interest": _previous_oi(
                            current_oi, oi_change
                        ),
                        "volume": getattr(row, f"{option_type}_trade_volume"),
                        "days_to_expiry": getattr(
                            row, f"{option_type}_days_remaining"
                        ),
                        "expiry": getattr(row, f"{option_type}_date_end"),
                        "bid": getattr(row, f"{option_type}_bid_price_1"),
                        "ask": getattr(row, f"{option_type}_ask_price_1"),
                        "contract_size": getattr(
                            row, f"{option_type}_contract_size"
                        ),
                        "contract_size_unit": getattr(
                            row, f"{option_type}_contract_size_unit"
                        ),
                        "margin_initial": getattr(
                            row, f"{option_type}_margin_initial"
                        ),
                        "margin_required": getattr(
                            row, f"{option_type}_margin_required"
                        ),
                        "date_update": row.date_update,
                        "time_update": row.time_update,
                        "fetched_at": row.fetched_at,
                    }
                )
                if len(contracts) >= limit:
                    return contracts
        return contracts

    async def load_forward_price(
        self, *, commodity: str | None, expiry: str | None
    ) -> float | None:
        if not expiry:
            return None
        statement = (
            select(ImeFutureModel)
            .where(ImeFutureModel.date_end == expiry)
            .order_by(desc(ImeFutureModel.id))
            .limit(20)
        )
        rows = (await self.session.execute(statement)).scalars().all()
        for row in rows:
            if commodity:
                description = " ".join(
                    str(value or "")
                    for value in (row.contract_description, row.contract_code)
                ).lower()
                if commodity.strip().lower() not in description:
                    continue
            price = row.price_last or row.price_last_settlement
            if price is not None and price > 0:
                return float(price)
        return None

    async def load_iv_history(
        self, contract_key: str, *, limit: int = DEFAULT_IV_HISTORY_LIMIT
    ) -> list[float]:
        # STEP 5-FIX-2: read the dedicated daily series written by
        # GoldOptionIvSnapshotJob (newest first).  An empty table means no
        # history — never infer IV from unrelated prices.
        statement = (
            select(GoldOptionIvHistoryModel.iv)
            .where(GoldOptionIvHistoryModel.symbol == contract_key)
            .order_by(desc(GoldOptionIvHistoryModel.as_of))
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).scalars().all()
        return [float(value) for value in rows]

    async def load_previous_open_interest(
        self, contract_key: str
    ) -> float | None:
        statement = (
            select(ImeOptionModel)
            .where(
                or_(
                    ImeOptionModel.call_contract_code == contract_key,
                    ImeOptionModel.put_contract_code == contract_key,
                )
            )
            .order_by(desc(ImeOptionModel.id))
            .limit(2)
        )
        rows = (await self.session.execute(statement)).scalars().all()
        if len(rows) < 2:
            return None
        previous = rows[1]
        if previous.call_contract_code == contract_key:
            value = previous.call_open_interest
        else:
            value = previous.put_open_interest
        return float(value) if value is not None else None


def _ime_config() -> dict[str, Any]:
    """Load the IME engine config (``derivatives.options`` section lives here)."""
    try:
        from core.config.ime_engine import load_ime_config

        return load_ime_config()
    except Exception:  # pragma: no cover - config failure must not break reads
        return {}


def _iv_history_min_days() -> int:
    """N: minimum stored days before iv_rank/iv_percentile are reported."""
    try:
        value = (
            _ime_config()
            .get("derivatives", {})
            .get("options", {})
            .get("iv_history_min_days")
        )
        if value is None:
            return DEFAULT_IV_HISTORY_MIN_DAYS
        return max(1, int(value))
    except (AttributeError, TypeError, ValueError):  # pragma: no cover
        return DEFAULT_IV_HISTORY_MIN_DAYS


async def get_options_chain_report(
    session: AsyncSession,
    *,
    commodity: str | None = None,
    limit: int = 500,
    forward_price: float | None = None,
    risk_free_rate: float = 0.0,
    liquidity_thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Return a cached live IME options-chain report."""
    threshold_key = repr(sorted((liquidity_thresholds or {}).items()))
    cache_key = OPTIONS_CHAIN_CACHE_KEY.format(
        commodity=commodity or "all",
        limit=limit,
        forward=forward_price if forward_price is not None else "auto",
        rate=risk_free_rate,
        thresholds=threshold_key,
    )
    cache = get_cache()
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    provider = ImeOptionsChainProvider(session)
    min_days = _iv_history_min_days()
    try:
        report = await build_options_chain_report(
            provider,
            commodity=commodity,
            limit=limit,
            forward_price=forward_price,
            risk_free_rate=risk_free_rate,
            liquidity_thresholds=liquidity_thresholds,
            min_history_days=min_days,
            iv_history_limit=max(DEFAULT_IV_HISTORY_LIMIT, min_days),
        )
    except Exception as exc:  # pragma: no cover - DB/schema failure path
        logger.exception("IME options-chain query failed")
        report = {
            "available": False,
            "reason": str(exc),
            "contracts": [],
            "contracts_count": 0,
            "skew_by_expiry": [],
            "iv_term_structure": [],
            "iv_available": False,
            "iv_history_available": False,
        }

    report["source"] = "brsapi_ime_options+brsapi_ime_futures"
    report["commodity"] = commodity
    report["limit"] = limit
    if report.get("iv_history_source") != "provider":
        report["iv_history_source"] = "unavailable"
        report["iv_history_reason"] = (
            "no historical IV observations in gold_option_iv_history yet "
            "(GoldOptionIvSnapshotJob has not backfilled a full history)"
        )

    await cache.set(cache_key, report, ttl=OPTIONS_CHAIN_CACHE_TTL_SECONDS)
    return report


async def snapshot_option_iv(
    session: AsyncSession,
    *,
    as_of: date | None = None,
    provider: OptionsChainProvider | None = None,
) -> dict[str, int]:
    """Store today's per-contract IV observation (STEP 5-FIX-2).

    Runs the normal chain build (contracts + per-expiry forwards + Black-76
    IV inversion) and upserts one row per ``(symbol, as_of, strike)`` so the
    daily job is idempotent.  Contracts without a computable IV are counted
    in ``missing_iv`` — never stored with a fabricated value.
    """
    day = as_of or date.today()
    chain_provider = provider or ImeOptionsChainProvider(session)
    report = await build_options_chain_report(chain_provider)

    counts = {
        "scanned": 0,
        "stored": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "missing_iv": 0,
    }
    for row in report.get("contracts", []):
        counts["scanned"] += 1
        iv = row.get("iv")
        symbol = row.get("contract_key")
        strike = row.get("strike")
        if iv is None or symbol is None or strike is None:
            counts["missing_iv"] += 1
            continue

        expiry = row.get("expiry")
        forward = row.get("forward_price")
        existing = (
            await session.execute(
                select(GoldOptionIvHistoryModel).where(
                    GoldOptionIvHistoryModel.symbol == str(symbol),
                    GoldOptionIvHistoryModel.as_of == day,
                    GoldOptionIvHistoryModel.strike == float(strike),
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            session.add(
                GoldOptionIvHistoryModel(
                    symbol=str(symbol),
                    expiry=str(expiry) if expiry is not None else None,
                    strike=float(strike),
                    iv=float(iv),
                    forward=float(forward) if forward is not None else None,
                    as_of=day,
                )
            )
            counts["inserted"] += 1
            counts["stored"] += 1
            continue

        new_iv = float(iv)
        new_forward = float(forward) if forward is not None else None
        new_expiry = str(expiry) if expiry is not None else None
        if (
            existing.iv != new_iv
            or existing.forward != new_forward
            or existing.expiry != new_expiry
        ):
            existing.iv = new_iv
            existing.forward = new_forward
            existing.expiry = new_expiry
            counts["updated"] += 1
        else:
            counts["skipped"] += 1
        counts["stored"] += 1

    await session.commit()
    return counts


__all__ = [
    "DEFAULT_IV_HISTORY_MIN_DAYS",
    "ImeOptionsChainProvider",
    "OPTIONS_CHAIN_CACHE_KEY",
    "OPTIONS_CHAIN_CACHE_TTL_SECONDS",
    "get_options_chain_report",
    "snapshot_option_iv",
]
