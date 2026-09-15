from __future__ import annotations

import logging

from sqlalchemy import BigInteger, DateTime, Float, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core.config import INFRA
from core.exceptions import ForecastingError

logger = logging.getLogger("brsapi.query_service")


class Base(DeclarativeBase):
    pass


class PriceRecord(Base):
    __tablename__ = "price_records"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    price: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ForecastRecord(Base):
    __tablename__ = "forecast_records"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    fair_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_price: Mapped[float] = mapped_column(Float)
    bubble: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecasted_bubble: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecasted_price: Mapped[float] = mapped_column(Float)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


_engine = create_async_engine(INFRA.database_url, echo=False)
SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def init_db() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_latest_market_prices(session: AsyncSession, symbols: list[str] | None = None) -> dict[str, float]:
    try:
        subq = select(func.max(PriceRecord.id)).group_by(PriceRecord.symbol)
        if symbols:
            subq = subq.where(PriceRecord.symbol.in_(symbols))
        subq = subq.scalar_subquery()
        stmt = select(PriceRecord).where(PriceRecord.id.in_(subq))
        result = await session.execute(stmt)
        records = result.scalars().all()
        return {r.symbol: r.price for r in records}
    except Exception as exc:
        logger.error("Database error in get_latest_market_prices: %s", exc)
        raise ForecastingError("خطای داخلی در خواندن آخرین قیمت‌ها از پایگاه داده.") from exc


async def record_price(session: AsyncSession, symbol: str, price: float) -> None:
    session.add(PriceRecord(symbol=symbol, price=price))
    await session.commit()


async def record_forecast(session: AsyncSession, forecast: dict) -> None:
    session.add(
        ForecastRecord(
            symbol=forecast["symbol"],
            fair_value=forecast.get("fair_value"),
            market_price=forecast["current_market_price"],
            bubble=forecast.get("current_bubble"),
            forecasted_bubble=forecast.get("forecasted_bubble"),
            forecasted_price=forecast["forecasted_price"],
        )
    )
    await session.commit()
