"""
Direct test of TrainingService with HistoricalDailyModel fallback.
Bypasses the API server to test the core logic.
"""

import asyncio
import os
import sys

# Force UTF-8 for Persian characters
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from datetime import date, timedelta

import _db
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = _db.database_url_async()


async def test_historical_daily():
    """Step 1: Verify HistoricalDailyModel has data."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        from brsapi.models import HistoricalDailyModel

        stmt = select(func.count()).select_from(HistoricalDailyModel).where(HistoricalDailyModel.symbol == "فولاد")
        result = await session.execute(stmt)
        count = result.scalar()
        print(f"HistoricalDailyModel count for فولاد: {count}")

        if count and count > 0:
            stmt2 = (
                select(HistoricalDailyModel)
                .where(HistoricalDailyModel.symbol == "فولاد")
                .order_by(HistoricalDailyModel.date.desc())
                .limit(5)
            )
            result2 = await session.execute(stmt2)
            rows = result2.scalars().all()
            for r in rows:
                print(
                    f"  date={r.date}, first={r.price_first}, max={r.price_max}, min={r.price_min}, close={r.price_close}, vol={r.trade_volume}"
                )

    await engine.dispose()
    return count


async def run_training():
    """Step 2: Run actual training using the fixed TrainingService."""
    from repositories.quote_repository import QuoteRepository
    from services.training_service import TrainingService

    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        quote_repo = QuoteRepository(session=session)
        trainer = TrainingService(quote_repo=quote_repo, session=session)

        symbol = "فولاد"
        start_date = (date.today() - timedelta(days=180)).isoformat()
        end_date = date.today().isoformat()

        print(f"\nStarting training for {symbol}...")
        print(f"  Date range: {start_date} to {end_date}")

        result = await trainer.train_with_db_data(
            symbol=symbol,
            model_type="xgboost",
            start_date=start_date,
            end_date=end_date,
            feature_groups=["price", "technical"],
            task_type="regression",
            n_cv_splits=3,
        )

        if result.success and result.value:
            run = result.value
            metrics = run.get("metrics", {})
            print(f"\n✅ Training SUCCESS for {symbol}!")
            print(f"  Run ID: {run.get('id', '')}")
            print(f"  Train samples: {run.get('train_samples', 0)}")
            print(f"  Features: {run.get('feature_count', 0)}")
            print(f"  Metrics: R2={metrics.get('mean_r2', 'N/A')}, MAE={metrics.get('mean_mae', 'N/A')}")
            print(f"  Feature groups: {run.get('feature_groups', [])}")
        else:
            print(f"\n❌ Training FAILED for {symbol}")
            print(f"  Error: {result.error}")

    await engine.dispose()


async def main():
    print("=" * 60)
    print("TEST 1: HistoricalDailyModel Data Check")
    print("=" * 60)
    count = await test_historical_daily()

    if count and count >= 30:
        print(f"\n✅ Sufficient data ({count} rows). Proceeding to training...\n")
        print("=" * 60)
        print("TEST 2: Training with HistoricalDailyModel fallback")
        print("=" * 60)
        await run_training()
    else:
        print(f"\n❌ Insufficient data ({count} rows). Cannot train.")


if __name__ == "__main__":
    asyncio.run(main())

