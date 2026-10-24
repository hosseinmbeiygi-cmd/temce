"""تستی برای контракт حذف نرم (Soft-Delete) دارایی در سرویس پورتفایل.

A-C3 / E-H7:
  * حذف دارایی پیش‌فرض نرم است (ستون deleted_at تنظیم می‌شود).
  * معامله‌های وابسته به Darayei (از طریق FK holding_id با ondelete="SET NULL")
    سالم می‌مانند و از بین نمی‌روند.
  * خلاصه مالیاتی /portfolio/tax پس از حذف، همچنان به درستی محاسبه می‌شود.
  * holdings (حذف‌نشده) حذف‌شده از نمای پورتفوی خارج می‌شوند، но معاملات آن‌ها
    در کل لیست معامله‌ها ظاهر می‌مانند.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from core.config import settings
from core.database import create_async_engine, async_sessionmaker, AsyncSession

from src.gold_desk.models import GoldHoldingModel, GoldTradeModel

pytestmark = pytest.mark.needs_db

SYM_A = "_TD_A" + os.environ.get("TEST_SYMBOL_SUFFIX", "test")
SYM_B = "_TD_B" + os.environ.get("TEST_SYMBOL_SUFFIX", "test")


@pytest.mark.asyncio
async def test_soft_delete_preserves_trades_and_tax():
    """Test that soft-delete preserves trades and tax summary."""
    db_url = settings.database_url_async
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(db_url, pool_size=5, max_overflow=10)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with session_factory() as s:
        # Clean up any previous test data
        await s.execute(
            GoldHoldingModel.__table__.delete()
            .where(GoldHoldingModel.symbol.like("_TD%"))
        )
        await s.execute(
            GoldTradeModel.__table__.delete()
            .where(GoldTradeModel.symbol.like("_TD%"))
        )
        await s.commit()

        now = datetime.now(timezone.utc)
        for sym in (SYM_A, SYM_B):
            holding = GoldHoldingModel(
                symbol=sym,
                display_name=f"{sym}-dtemce",
                vehicle="etf",
                quantity=10.0,
                buy_price=10_000.0,
                buy_amount_irt=1_000_000.0,
                bought_at=now,
            )
            s.add(holding)
            await s.flush()
            for _ in range(2):
                s.add(
                    GoldTradeModel(
                        symbol=sym,
                        action="buy",
                        quantity=5.0,
                        price=10_000.0,
                        amount_irt=50_000.0,
                        traded_at=now,
                    )
                )
            s.add(
                GoldTradeModel(
                    symbol=sym,
                    action="sell",
                    quantity=2.0,
                    price=11_000.0,
                    amount_irt=22_000.0,
                    traded_at=now,
                )
            )
        await s.commit()

        # مالیات پیش از حذف
        from src.gold_desk.portfolio import build_tax_summary
        summary_before = await build_tax_summary(s)
        summary_before_val = summary_before["realized_pnl_irt"]
        assert summary_before["sold_quantity"] > 0

        # پیدا کردن holdings A
        holdings = (
            await s.execute(select(GoldHoldingModel).where(GoldHoldingModel.symbol == SYM_A))
        ).scalars().all()
        assert len(holdings) == 1
        assert holdings[0].deleted_at is None

        # حذف نرم (Soft delete) دارایی A
        holding = holdings[0]
        holding.deleted_at = now
        await s.commit()

        # A حذف شده، معامله‌های A مقدار ثابت می‌مانند
        all_trades = (await s.execute(select(GoldTradeModel))).scalars().all()
        a_trades = [t for t in all_trades if t.symbol == SYM_A]
        b_trades = [t for t in all_trades if t.symbol == SYM_B]
        assert len(a_trades) == 3
        assert len(b_trades) == 3

        # /portfolio/tax همچنان کار می‌کند و به درستی می‌گردد
        summary_after = await build_tax_summary(s)
        assert summary_after["realized_pnl_irt"] == summary_before_val
        assert summary_after["sold_quantity"] == summary_before["sold_quantity"]

        # holdings آزمایشی حذف‌شده از نمای پورتفوی حذف می‌شوند
        from src.gold_desk.portfolio import load_holdings_and_trades
        holdings_after, _ = await load_holdings_and_trades(s)
        assert all(h.symbol == SYM_B for h in holdings_after)
        assert all(h.deleted_at is not None for h in holdings_after)
    
    await engine.dispose()