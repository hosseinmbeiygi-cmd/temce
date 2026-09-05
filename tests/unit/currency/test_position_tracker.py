"""PositionTracker CRUD + PnL against in-memory SQLite (raw DDL pattern,
same as tests/unit/repositories/conftest.py — avoids ORM/JSONB compile issues).
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.currency_service.services.position_tracker import PositionTracker


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(
            text("""
            CREATE TABLE currency_manual_positions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     VARCHAR(64)  NOT NULL,
                asset_type  VARCHAR(16)  NOT NULL,
                entry_price NUMERIC(18,0) NOT NULL,
                volume      NUMERIC(18,4) NOT NULL,
                entry_date  DATE NOT NULL DEFAULT CURRENT_DATE,
                created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                note        TEXT
            )""")
        )
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


class TestCRUD:
    async def test_create_assigns_id(self, session: AsyncSession) -> None:
        tracker = PositionTracker(session)
        pos = await tracker.create(
            user_id="u1", asset_type="CASH_USD", entry_price=600_000, volume=100
        )
        assert pos.id == 1
        assert pos.asset_type == "CASH_USD"
        assert pos.entry_price == 600_000
        assert pos.entry_date == date.today()

    async def test_list_scoped_to_user(self, session: AsyncSession) -> None:
        tracker = PositionTracker(session)
        await tracker.create(user_id="u1", asset_type="CASH_USD", entry_price=600_000, volume=10)
        await tracker.create(user_id="u2", asset_type="USDT", entry_price=620_000, volume=5)
        mine = await tracker.list_for_user("u1")
        assert len(mine) == 1
        assert mine[0].user_id == "u1"

    async def test_delete(self, session: AsyncSession) -> None:
        tracker = PositionTracker(session)
        pos = await tracker.create(user_id="u1", asset_type="USDT", entry_price=620_000, volume=5)
        assert await tracker.delete(pos.id, "u1") is True
        assert await tracker.delete(pos.id, "u1") is False

    async def test_delete_other_user_denied(self, session: AsyncSession) -> None:
        tracker = PositionTracker(session)
        pos = await tracker.create(user_id="u1", asset_type="USDT", entry_price=620_000, volume=5)
        assert await tracker.delete(pos.id, "attacker") is False


class TestPnL:
    async def test_profit(self, session: AsyncSession) -> None:
        tracker = PositionTracker(session)
        pos = await tracker.create(user_id="u1", asset_type="CASH_USD", entry_price=600_000, volume=100)
        pnl = tracker.pnl_for(pos, current_price=615_000)
        assert pnl.pnl_toman == pytest.approx(1_500_000)
        assert pnl.return_pct == pytest.approx(2.5)

    async def test_loss(self, session: AsyncSession) -> None:
        tracker = PositionTracker(session)
        pos = await tracker.create(user_id="u1", asset_type="CASH_USD", entry_price=600_000, volume=10)
        pnl = tracker.pnl_for(pos, current_price=580_000)
        assert pnl.pnl_toman == pytest.approx(-200_000)
        assert pnl.return_pct == pytest.approx(-3.3333333333)

    def test_price_selection_by_asset(self) -> None:
        from datetime import datetime, timezone

        from apps.currency_service.domain import ManualPosition

        prices = {"free_sell": 615_000, "usdt_sell": 620_000}
        cash = ManualPosition(
            id=1, user_id="u", asset_type="CASH_USD", entry_price=1, volume=1,
            entry_date=date.today(), created_at=datetime.now(tz=timezone.utc),
        )
        usdt = ManualPosition(
            id=2, user_id="u", asset_type="USDT", entry_price=1, volume=1,
            entry_date=date.today(), created_at=datetime.now(tz=timezone.utc),
        )
        assert PositionTracker.price_for(cash, prices) == 615_000
        assert PositionTracker.price_for(usdt, prices) == 620_000
