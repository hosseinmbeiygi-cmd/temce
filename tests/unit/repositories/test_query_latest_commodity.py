"""Append-only gold/currency/crypto tables must return one row per symbol.

`sync_gold_currency` writes a new row per symbol on every cycle (the old
TRUNCATE was removed to stop deleting data). Without a latest-per-symbol
read, the API returns one row per historical cycle for the same symbol.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from brsapi.models.commodity import CurrencyPriceModel, GoldCoinPriceModel
from brsapi.models.crypto import CryptoPriceModel
from brsapi.services.query_service import BrsApiQueryService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for model in (GoldCoinPriceModel, CurrencyPriceModel, CryptoPriceModel):
            await conn.run_sync(model.__table__.create)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_gold_prices_return_latest_per_symbol(session: AsyncSession) -> None:
    session.add_all(
        [
            GoldCoinPriceModel(id=1, symbol="X", price=100.0, fetched_at="2026-10-28T09:00:00.000Z"),
            GoldCoinPriceModel(id=2, symbol="X", price=110.0, fetched_at="2026-10-28T09:05:00.000Z"),
            # Late backfill: inserted last, but its source time is older.
            GoldCoinPriceModel(id=3, symbol="X", price=90.0, fetched_at="2026-10-28T08:00:00.000Z"),
            GoldCoinPriceModel(id=4, symbol="Y", price=200.0, fetched_at="2026-10-28T09:00:00.000Z"),
        ]
    )
    await session.commit()

    rows = await BrsApiQueryService(session).get_gold_coin_prices()

    by_symbol = {row["symbol"]: row for row in rows}
    assert len(rows) == 2
    assert by_symbol["X"]["price"] == 110.0
    assert by_symbol["X"]["id"] == 2
    assert by_symbol["Y"]["price"] == 200.0


async def test_currency_prices_return_latest_per_symbol(session: AsyncSession) -> None:
    session.add_all(
        [
            CurrencyPriceModel(id=1, symbol="USD", price=60000.0, fetched_at="2026-10-28T09:00:00.000Z"),
            CurrencyPriceModel(id=2, symbol="USD", price=61000.0, fetched_at="2026-10-28T09:05:00.000Z"),
            CurrencyPriceModel(id=3, symbol="USD", price=59000.0, fetched_at="2026-10-28T08:00:00.000Z"),
        ]
    )
    await session.commit()

    rows = await BrsApiQueryService(session).get_currency_prices()

    assert len(rows) == 1
    assert rows[0]["price"] == 61000.0


async def test_crypto_prices_are_deduped_then_sorted(session: AsyncSession) -> None:
    session.add_all(
        [
            CryptoPriceModel(id=1, name="Bitcoin", symbol="BTC", rank=2, price_usd=100.0, fetched_at="2026-10-28T09:00:00.000Z"),
            CryptoPriceModel(id=2, name="Bitcoin", symbol="BTC", rank=2, price_usd=110.0, fetched_at="2026-10-28T09:05:00.000Z"),
            CryptoPriceModel(id=3, name="Ethereum", symbol="ETH", rank=1, price_usd=50.0, fetched_at="2026-10-28T09:00:00.000Z"),
            # Late backfill for BTC must not win.
            CryptoPriceModel(id=4, name="Bitcoin", symbol="BTC", rank=2, price_usd=90.0, fetched_at="2026-10-28T08:00:00.000Z"),
        ]
    )
    await session.commit()

    rows = await BrsApiQueryService(session).get_crypto_prices(limit=50)

    assert [row["symbol"] for row in rows] == ["ETH", "BTC"]
    btc = next(row for row in rows if row["symbol"] == "BTC")
    assert btc["price_usd"] == 110.0
    assert btc["id"] == 2
