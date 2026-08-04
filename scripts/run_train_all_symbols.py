"""
Run ML training on ALL symbols in the database.
Uses the fixed TrainingService with HistoricalDailyModel fallback.
"""
import asyncio
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

try:
    from core.config import settings

    DATABASE_URL = settings.database_url_async
except ImportError:
    # No hardcoded credentials — read from env with a credential-free fallback
    DATABASE_URL = os.environ.get("DATABASE_URL_ASYNC", "postgresql+asyncpg://localhost:5432/market")


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # Step 1: Get all symbols from the database
        from sqlalchemy import select

        from models.instrument import InstrumentModel

        stmt = select(InstrumentModel.symbol).where(
            InstrumentModel.status == "active"
        ).order_by(InstrumentModel.symbol)
        result = await session.execute(stmt)
        all_symbols = [row[0] for row in result if row[0]]

        print(f"Found {len(all_symbols)} active symbols in database")
        print(f"First 10: {all_symbols[:10]}")
        print()

        # Step 2: Run training on each symbol
        from repositories.quote_repository import QuoteRepository
        from services.training_service import TrainingService

        quote_repo = QuoteRepository(session=session)
        trainer = TrainingService(quote_repo=quote_repo, session=session)

        start_date = (date.today() - timedelta(days=180)).isoformat()
        end_date = date.today().isoformat()

        results = []
        total = len(all_symbols)
        successful = 0
        failed = 0

        for idx, symbol in enumerate(all_symbols):
            print(f"[{idx+1}/{total}] Training {symbol}...", end=" ", flush=True)
            t0 = time.time()

            try:
                result = await trainer.train_with_db_data(
                    symbol=symbol,
                    model_type="xgboost",
                    start_date=start_date,
                    end_date=end_date,
                    feature_groups=["price", "technical"],
                    task_type="regression",
                    n_cv_splits=3,
                )

                elapsed = time.time() - t0

                if result.success and result.value:
                    run = result.value
                    metrics = run.get("metrics", {})
                    r2 = metrics.get("mean_r2", "N/A")
                    samples = run.get("train_samples", 0)
                    print(f"✅ R²={r2}, samples={samples}, {elapsed:.1f}s")
                    successful += 1
                    results.append({
                        "symbol": symbol,
                        "success": True,
                        "r2": r2,
                        "samples": samples,
                        "elapsed": round(elapsed, 1),
                    })
                else:
                    print(f"❌ {result.error}, {elapsed:.1f}s")
                    failed += 1
                    results.append({
                        "symbol": symbol,
                        "success": False,
                        "error": result.error,
                        "elapsed": round(elapsed, 1),
                    })
            except Exception as e:
                elapsed = time.time() - t0
                print(f"💥 {str(e)[:80]}, {elapsed:.1f}s")
                failed += 1
                results.append({
                    "symbol": symbol,
                    "success": False,
                    "error": str(e)[:200],
                    "elapsed": round(elapsed, 1),
                })

        # Step 3: Print summary
        print("\n" + "=" * 60)
        print(f"TRAINING COMPLETE: {total} symbols")
        print(f"  ✅ Successful: {successful}")
        print(f"  ❌ Failed: {failed}")
        print(f"  ⏱ Total time: {sum(r['elapsed'] for r in results):.1f}s")

        # Best models
        successful_results = [r for r in results if r.get("success") and r.get("r2") != "N/A"]
        if successful_results:
            best = max(successful_results, key=lambda r: r["r2"])
            print(f"\n  🏆 Best model: {best['symbol']} with R²={best['r2']}")
            worst = min(successful_results, key=lambda r: r["r2"])
            print(f"  😞 Worst model: {worst['symbol']} with R²={worst['r2']}")

        # Save results to file
        import json
        with open("train_all_results.json", "w", encoding="utf-8") as f:
            json.dump({
                "total": total,
                "successful": successful,
                "failed": failed,
                "results": results,
            }, f, ensure_ascii=False, indent=2)
        print("\n  📄 Results saved to train_all_results.json")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
