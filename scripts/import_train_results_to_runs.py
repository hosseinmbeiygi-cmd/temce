"""Import train_all_models_results.json into ml_training_runs.

``scripts/train_all_models.py`` saves evaluation results to
``ml_symbol_results`` + the JSON file, but the ML page's training-runs tab
reads ``ml_training_runs`` — so the results never appeared there. This script
bridges the gap: every (symbol, model) record becomes one run row.

Idempotent: run IDs are deterministic (``tam_<md5(symbol|model)[:12]>``) and
inserted with ``ON CONFLICT (id) DO UPDATE``, so re-running never duplicates.

Usage::

    python scripts/import_train_results_to_runs.py [path/to/results.json]
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# --- auto PYTHONPATH ---
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

from sqlalchemy import text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from core.config import settings  # noqa: E402
from models.ml import MlTrainingRunModel  # noqa: E402


def _run_id(symbol: str, model: str) -> str:
    digest = hashlib.md5(f"{symbol}|{model}".encode()).hexdigest()[:12]
    return f"tam_{digest}"


def _load_results(path: Path) -> tuple[list[dict], dict]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return payload["results"], payload.get("summary", {})


def _row(r: dict, run_time: datetime) -> dict:
    symbol = r.get("symbol", "")
    model = r.get("model", "")
    ok = bool(r.get("ok"))
    return {
        "id": _run_id(symbol, model),
        "experiment_name": "train_all_models",
        "run_name": f"{model}-{symbol}",
        "status": "completed" if ok else "failed",
        "model_type": model,
        "config": json.dumps(
            {
                "symbol": symbol,
                "data_type": "historical_daily",
                "train_samples": r.get("train_samples"),
                "val_samples": r.get("val_samples"),
            },
            ensure_ascii=False,
        ),
        "metrics": json.dumps(
            {"r2": r.get("r2", 0), "mae": r.get("mae", 0)}, ensure_ascii=False
        ),
        "best_params": "{}",
        "progress_pct": 100.0 if ok else 0.0,
        # Columns are TIMESTAMP WITHOUT TIME ZONE — strip tzinfo so asyncpg
        # does not raise "can't subtract offset-naive and offset-aware".
        "started_at": run_time.replace(tzinfo=None),
        "finished_at": run_time.replace(tzinfo=None),
        "duration_seconds": r.get("time", 0),
        "error": (r.get("error") or "")[:500] if not ok else None,
    }


async def main(path: Path) -> None:
    results, summary = _load_results(path)
    run_time = datetime.now(UTC)

    engine = create_async_engine(settings.database_url, pool_size=2)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    rows = [_row(r, run_time) for r in results]
    # asyncpg caps a single statement at 32767 bound params — 13 cols/row means
    # ~500 rows per batch is safe.
    BATCH = 500
    async with factory() as session:
        for i in range(0, len(rows), BATCH):
            chunk = rows[i : i + BATCH]
            stmt = pg_insert(MlTrainingRunModel).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[MlTrainingRunModel.id],
                set_={
                    "status": stmt.excluded.status,
                    "metrics": stmt.excluded.metrics,
                    "duration_seconds": stmt.excluded.duration_seconds,
                    "error": stmt.excluded.error,
                    "progress_pct": stmt.excluded.progress_pct,
                    "finished_at": stmt.excluded.finished_at,
                },
            )
            await session.execute(stmt)
            print(f"  chunk {i // BATCH + 1}: {len(chunk)} rows")
        await session.commit()

        total = await session.execute(text("SELECT COUNT(*) FROM ml_training_runs"))
        print(
            f"Imported {len(rows)} runs from {path.name} "
            f"(summary: {summary.get('total')} total, "
            f"{summary.get('success')} ok, {summary.get('failed')} failed). "
            f"ml_training_runs now has {total.scalar()} rows."
        )
    await engine.dispose()


if __name__ == "__main__":
    import asyncio

    p = Path(sys.argv[1]) if len(sys.argv) > 1 else _project_root / "train_all_models_results.json"
    asyncio.run(main(p))
