"""NAV Checker — P/NAV صندوق‌های طلا.

از brsapi_ime_funds + brsapi_nav_records می‌خواند. P/NAV + BPR + Inflow + 7d NAV change.

این تابع pure نیست — DB session لازم دارد.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import utc_now_naive


@dataclass(frozen=True)
class FundNAVStatus:
    symbol: str
    fund_name: str
    nav_per_unit: float
    # None means "no traded price was found", which is not the same as a 0% bubble: the
    # scorer gives its best NAV mark to a zero, so substituting NAV here used to turn a
    # missing price into «تخفیف/نزدیک».
    market_price: float | None
    bubble_abs: float | None
    bubble_pct: float | None
    bpr: float
    real_buy_value: int
    real_sell_value: int
    net_inflow: int
    nav_7d_pct: float | None


async def _latest_nav(session: AsyncSession, symbol: str) -> float | None:
    """آخرین NAV ثبت‌شده برای یک صندوق."""
    try:
        from brsapi.models import NavRecordModel

        stmt = (
            select(NavRecordModel.nav)
            .where(NavRecordModel.symbol == symbol)
            .order_by(desc(NavRecordModel.date))
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        return float(row[0]) if row and row[0] else None
    except Exception:
        return None


async def _nav_7d_ago(session: AsyncSession, symbol: str) -> float | None:
    """NAV ۷ روز قبل."""
    try:
        from brsapi.models import NavRecordModel

        cutoff = utc_now_naive() - timedelta(days=7)
        stmt = (
            select(NavRecordModel.nav)
            .where(NavRecordModel.symbol == symbol, NavRecordModel.date <= cutoff)
            .order_by(desc(NavRecordModel.date))
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        return float(row[0]) if row and row[0] else None
    except Exception:
        return None


async def _fund_market_data(session: AsyncSession, symbol: str) -> dict[str, Any] | None:
    """آخرین اطلاعات بازار صندوق (real/legal volume)."""
    try:
        from brsapi.models.tsetmc import HistoricalRealLegalModel

        # استفاده از آخرین ردیف historical_real_legal
        stmt = (
            select(HistoricalRealLegalModel)
            .where(HistoricalRealLegalModel.symbol == symbol)
            .order_by(desc(HistoricalRealLegalModel.date))
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        buy_val = int(row.buy_real_value or 0)
        sell_val = int(row.sell_real_value or 0)
        bpr = (buy_val / sell_val) if sell_val > 0 else 0
        return {
            "buy_value": buy_val,
            "sell_value": sell_val,
            "bpr": bpr,
            "net_inflow": buy_val - sell_val,
        }
    except Exception:
        return None


async def get_fund_status(
    session: AsyncSession,
    symbol: str,
    market_price_override: float | None = None,
) -> FundNAVStatus | None:
    """وضعیت کامل یک صندوق.

    market_price_override: اگر قیمت بازار از BrsApi snapshot موجود باشد مستقیماً
        استفاده می‌شود؛ اگر هیچ‌کدام از منابع قیمت آن را ندهند، market_price None می‌ماند
        و حباب محاسبه نمی‌شود.
    """
    nav = await _latest_nav(session, symbol)
    if nav is None:
        return None

    if market_price_override is not None and market_price_override > 0:
        market_price = float(market_price_override)
    else:
        # تلاش برای خواندن قیمت بازار صندوق از BrsApi QueryService
        market_price = None
        with contextlib.suppress(Exception):
            from brsapi.services.query_service import BrsApiQueryService

            svc = BrsApiQueryService(session=session)
            # سعی 1: get_fund_prices اگر وجود دارد
            if hasattr(svc, "get_fund_prices"):
                rows = await svc.get_fund_prices()  # type: ignore
                for row in rows or []:
                    if row.get("symbol") == symbol and row.get("price"):
                        market_price = float(row["price"])
                        break
            # سعی 2: جدول مستقیم nav_records price?
            if market_price is None:
                # آخرین قیمت صندوق از GoldSnapshotModel اگر موجود باشد
                from sqlalchemy import desc, select

                from .models import GoldSnapshotModel

                stmt = (
                    select(GoldSnapshotModel.market_price)
                    .where(GoldSnapshotModel.symbol == symbol)
                    .order_by(desc(GoldSnapshotModel.snapshot_at))
                    .limit(1)
                )
                res = await session.execute(stmt)
                val = res.scalar()
                if val and float(val) > 0:
                    market_price = float(val)
        if market_price is not None and market_price <= 0:
            market_price = None

    market_data = await _fund_market_data(session, symbol) or {}
    bpr = float(market_data.get("bpr", 0))
    buy_val = int(market_data.get("buy_value", 0))
    sell_val = int(market_data.get("sell_value", 0))
    net = int(market_data.get("net_inflow", 0))

    # NAV 7d
    nav_7d = await _nav_7d_ago(session, symbol)
    nav_7d_pct: float | None = None
    if nav_7d and nav_7d > 0:
        nav_7d_pct = ((nav - nav_7d) / nav_7d) * 100.0

    bubble_abs = None if market_price is None else market_price - nav
    bubble_pct = (
        None
        if bubble_abs is None or nav <= 0
        else bubble_abs / nav * 100.0
    )

    return FundNAVStatus(
        symbol=symbol,
        fund_name=symbol,
        nav_per_unit=nav,
        market_price=market_price,
        bubble_abs=bubble_abs,
        bubble_pct=bubble_pct,
        bpr=bpr,
        real_buy_value=buy_val,
        real_sell_value=sell_val,
        net_inflow=net,
        nav_7d_pct=nav_7d_pct,
    )


async def get_all_funds_status(
    session: AsyncSession,
    symbols: list[str],
    market_prices: dict[str, float] | None = None,
) -> list[FundNAVStatus]:
    """وضعیت همه صندوق‌های مورد نظر.

    market_prices: دیکشنری symbol→market_price از snapshot BrsApi (اختیاری).
    """
    out: list[FundNAVStatus] = []
    for sym in symbols:
        override = (market_prices or {}).get(sym)
        st = await get_fund_status(session, sym, market_price_override=override)
        if st:
            out.append(st)
    return out
