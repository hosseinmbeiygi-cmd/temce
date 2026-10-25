"""قرارداد حذف نرم دارایی روی یک دیتابیس تست ایزوله.

اجرا فقط وقتی ``GOLD_TEST_DATABASE_URL`` تنظیم شده باشد. بدون آن، ماژول با پیام
روشن skip می‌شود تا هرگز روی دیتابیس برنامه (my_first_db) نوشته نشود.

پاک‌سازی فقط با نمادهای دقیق همین اجرا انجام می‌شود (setup + teardown)؛ نه الگوی
``LIKE`` و نه assert روی کل جدول.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.gold_desk.models import GoldHoldingModel, GoldTradeModel

pytestmark = pytest.mark.needs_db

_TEST_DB_URL = os.environ.get("GOLD_TEST_DATABASE_URL")

if not _TEST_DB_URL:
    pytest.skip(
        "GOLD_TEST_DATABASE_URL is not set; skipping the soft-delete DB test so the "
        "application database is never touched",
        allow_module_level=True,
    )

_RUN_ID = uuid.uuid4().hex[:8]
SYM_A = f"_TD_A_{_RUN_ID}"
SYM_B = f"_TD_B_{_RUN_ID}"
OWN_SYMBOLS = (SYM_A, SYM_B)


async def _delete_own_rows(session: AsyncSession) -> None:
    """پاک‌سازی دقیق: فقط ردیف‌های همین دو نماد."""
    await session.execute(delete(GoldTradeModel).where(GoldTradeModel.symbol.in_(OWN_SYMBOLS)))
    await session.execute(delete(GoldHoldingModel).where(GoldHoldingModel.symbol.in_(OWN_SYMBOLS)))
    await session.commit()


@pytest.fixture()
async def session():
    engine = create_async_engine(_TEST_DB_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        await _delete_own_rows(s)
        yield s
    # teardown، مستقل از موفقیت تست
    async with factory() as s:
        await _delete_own_rows(s)
    await engine.dispose()


async def _seed(session: AsyncSession) -> tuple[int, int]:
    """دو دارایی (A و B) با معامله‌های متصل به ``holding_id``."""
    now = datetime.now(UTC)
    ids: list[int] = []
    for sym in OWN_SYMBOLS:
        holding = GoldHoldingModel(
            symbol=sym,
            display_name=f"{sym}-soft-delete",
            vehicle="etf",
            quantity=10.0,
            buy_price=10_000.0,
            buy_amount_irt=1_000_000.0,
            bought_at=now,
        )
        session.add(holding)
        await session.flush()
        ids.append(holding.id)
        for _ in range(2):
            session.add(
                GoldTradeModel(
                    symbol=sym,
                    action="buy",
                    quantity=5.0,
                    price=10_000.0,
                    amount_irt=50_000.0,
                    traded_at=now,
                    holding_id=holding.id,
                )
            )
        session.add(
            GoldTradeModel(
                symbol=sym,
                action="sell",
                quantity=2.0,
                price=11_000.0,
                amount_irt=22_000.0,
                traded_at=now,
                holding_id=holding.id,
            )
        )
    await session.commit()
    return ids[0], ids[1]


async def _trade_snapshot(session: AsyncSession) -> dict:
    rows = (
        await session.execute(select(GoldTradeModel).where(GoldTradeModel.symbol.in_(OWN_SYMBOLS)))
    ).scalars()
    return {
        trade.id: (trade.symbol, trade.quantity, trade.amount_irt, trade.holding_id)
        for trade in rows
    }


async def test_soft_delete_keeps_row_and_trades(session: AsyncSession) -> None:
    from src.gold_desk.portfolio import build_tax_summary, load_holdings_and_trades

    holding_a_id, holding_b_id = await _seed(session)
    summary_before = await build_tax_summary(session)
    trades_before = await _trade_snapshot(session)
    assert len(trades_before) == 6

    # حذف نرم فقط روی دارایی A.
    holding_a = await session.get(GoldHoldingModel, holding_a_id)
    assert holding_a is not None
    assert holding_a.deleted_at is None
    holding_a.deleted_at = datetime.now(UTC)
    await session.commit()

    # ۱) نمای پورتفوی: A دیگر نیست، B هست — فقط روی نمادهای خودمان.
    holdings_after, _trades_after = await load_holdings_and_trades(session)
    visible = {h.symbol for h in holdings_after if h.symbol in OWN_SYMBOLS}
    assert SYM_A not in visible
    assert SYM_B in visible

    # ۲) کوئری مستقیم: ردیف A هنوز هست و deleted_at دارد؛ B دست‌نخورده است.
    row_a = (
        await session.execute(select(GoldHoldingModel).where(GoldHoldingModel.id == holding_a_id))
    ).scalar_one()
    row_b = (
        await session.execute(select(GoldHoldingModel).where(GoldHoldingModel.id == holding_b_id))
    ).scalar_one()
    assert row_a.deleted_at is not None
    assert row_b.deleted_at is None

    # ۳) معامله‌های A دست‌نخورده‌اند (همان id/مقدار/holding_id).
    assert await _trade_snapshot(session) == trades_before

    # ۴) گزارش مالیاتی بین قبل و بعد تغییر نمی‌کند.
    summary_after = await build_tax_summary(session)
    assert summary_after["realized_pnl_irt"] == summary_before["realized_pnl_irt"]
    assert summary_after["sold_quantity"] == summary_before["sold_quantity"]


async def test_cleanup_removes_only_own_symbols(session: AsyncSession) -> None:
    """پاک‌سازی با نمادهای دقیق کار می‌کند."""
    await _seed(session)
    before = (
        await session.execute(
            select(GoldHoldingModel).where(GoldHoldingModel.symbol.in_(OWN_SYMBOLS))
        )
    ).scalars().all()
    assert len(before) == 2

    await _delete_own_rows(session)

    after = (
        await session.execute(
            select(GoldHoldingModel).where(GoldHoldingModel.symbol.in_(OWN_SYMBOLS))
        )
    ).scalars().all()
    assert after == []
