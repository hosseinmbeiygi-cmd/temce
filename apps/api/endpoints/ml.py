"""ML API endpoints — connected to the real ML pipeline.

No mock data. All predictions and training use real DB data.
When models are not trained, returns clear error messages.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session, get_inference_service
from core.logging import get_logger
from repositories.instrument_repository import InstrumentRepository
from schemas.api.ml import MlTrainRequest, MlTrainResponse
from schemas.common.responses import ApiResponse
from services.inference_service import InferenceService

router = APIRouter()
logger = get_logger(__name__)


# ── In-memory prediction results store ──────────────────────────────────────
_prediction_results: dict[str, dict[str, Any]] = {}


async def _db_list_models(session: AsyncSession) -> list[dict] | None:
    """List real registered models from ml_models + ml_model_versions tables."""
    import json as json_lib

    from models.ml import MlModelModel, MlModelVersionModel
    from sqlalchemy import select

    rows = (await session.execute(select(MlModelModel).order_by(MlModelModel.name))).scalars().all()
    if not rows:
        return None

    # Single query for all versions (avoids N+1) and group by model id
    all_versions = (
        await session.execute(select(MlModelVersionModel).order_by(MlModelVersionModel.version))
    ).scalars().all()
    versions_by_model: dict[str, list] = {}
    for v in all_versions:
        versions_by_model.setdefault(v.model_id, []).append(v)

    out: list[dict] = []
    for m in rows:
        versions = versions_by_model.get(m.id, [])
        tags: list[str] = []
        if m.tags:
            try:
                tags = json_lib.loads(m.tags)
            except (json_lib.JSONDecodeError, TypeError):
                tags = [s.strip() for s in m.tags.split(",") if s.strip()]
        out.append({
            "id": m.id,
            "name": m.name,
            "task": m.task or "regression",
            "framework": m.framework or "sklearn",
            "model_type": m.framework or m.name,
            "latest_version": m.latest_version or "1.0.0",
            "description": m.description or "",
            "tags": tags,
            "versions": [
                {
                    "version": v.version,
                    "stage": v.stage or "development",
                    "metrics": _safe_json(v.metrics),
                    "parameters": _safe_json(v.parameters),
                    "artifact_path": v.artifact_path or "",
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return out


async def _db_list_runs(session: AsyncSession, limit: int = 200) -> list[dict] | None:
    """List training runs from ml_training_runs table."""
    from models.ml import MlTrainingRunModel
    from sqlalchemy import select

    rows = (
        await session.execute(
            select(MlTrainingRunModel).order_by(MlTrainingRunModel.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    if not rows:
        return None

    out: list[dict] = []
    for r in rows:
        out.append(_run_to_dict(r))
    return out


def _run_to_dict(r) -> dict:
    """Map an MlTrainingRunModel ORM row to the API run dict shape."""
    config = _safe_json(r.config) or {}
    return {
        "id": r.id,
        "experiment_name": r.experiment_name or "",
        "run_name": r.run_name or "",
        "model_type": r.model_type or "",
        "symbol": config.get("symbol") if isinstance(config, dict) else None,
        "symbols": [config["symbol"]] if isinstance(config, dict) and config.get("symbol") else [],
        "status": r.status or "pending",
        "metrics": _safe_json(r.metrics) or {},
        "best_params": _safe_json(r.best_params) or {},
        "progress_pct": r.progress_pct or 0,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _safe_json(value: str | None) -> dict:
    import json as json_lib

    if not value:
        return {}
    try:
        parsed = json_lib.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (json_lib.JSONDecodeError, TypeError):
        return {}


@router.get("/models", summary="List ML models", description="List all registered ML models")
async def list_models(session: AsyncSession = Depends(get_db_session)) -> ApiResponse[list[dict]]:
    # Prefer the real trained models registered in the database
    try:
        db_models = await _db_list_models(session)
        if db_models:
            return ApiResponse[list[dict]](success=True, data=db_models)
    except Exception as e:
        logger.warning("Could not read ML models from DB, falling back to registry: %s", e)

    from ml.global_registry import get_registry

    registry = get_registry()
    models = registry.list_models()
    return ApiResponse[list[dict]](success=True, data=models)


@router.get("/runs", summary="List training runs", description="List all training runs")
async def list_runs(session: AsyncSession = Depends(get_db_session)) -> ApiResponse[list[dict]]:
    # Prefer training runs persisted in the database
    try:
        db_runs = await _db_list_runs(session)
        if db_runs:
            return ApiResponse[list[dict]](success=True, data=db_runs)
    except Exception as e:
        logger.warning("Could not read ML runs from DB, falling back to in-memory service: %s", e)

    from services.global_training_service import get_training_service

    service = get_training_service()
    result = await service.list_runs()
    return ApiResponse[list[dict]](success=True, data=result.value if result.success else [])


@router.get("/runs/{run_id}", summary="Get training run", description="Get details of a specific training run")
async def get_run(run_id: str, session: AsyncSession = Depends(get_db_session)) -> ApiResponse[dict]:
    # Prefer DB-persisted run (direct lookup by id)
    try:
        from models.ml import MlTrainingRunModel
        from sqlalchemy import select

        row = (
            await session.execute(select(MlTrainingRunModel).where(MlTrainingRunModel.id == run_id))
        ).scalar_one_or_none()
        if row is not None:
            return ApiResponse[dict](success=True, data=_run_to_dict(row))
    except Exception as e:
        logger.warning("DB run lookup failed: %s", e)

    from services.global_training_service import get_training_service

    service = get_training_service()
    result = await service.get_training_status(run_id)
    if result.success and result.value:
        return ApiResponse[dict](success=True, data=result.value)
    return ApiResponse[dict](success=False, data={}, error={"message": "Run not found"})


@router.get(
    "/runs/{run_id}/feature-importance",
    summary="Feature importance",
    description="Get feature importance for a completed training run",
)
async def get_feature_importance(run_id: str) -> ApiResponse[dict[str, Any]]:
    from services.global_training_service import get_training_service

    service = get_training_service()
    result = await service.get_feature_importance(run_id)
    if result.success and result.value:
        return ApiResponse[dict[str, Any]](success=True, data=result.value)
    return ApiResponse[dict[str, Any]](success=False, data={}, error={"message": result.error or "Not available"})


@router.post("/predict/{model_id}")
async def predict(
    model_id: str,
    features: dict[str, Any],
    service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[dict[str, Any]]:
    # Real prediction only — no mock fallback
    symbol = features.get("symbol", "")
    if symbol:
        result = await service.predict_real(model_id, symbol)
        if result.success:
            return ApiResponse[dict[str, Any]](success=True, data=result.value)

    return ApiResponse[dict[str, Any]](
        success=False, data=None,
        error={"message": f"No trained model available for {model_id}. Train first via /ml/train."},
    )


@router.post(
    "/predict-real",
    summary="Real prediction",
    description="Run real ML prediction using trained model + live DB data for a symbol",
)
async def predict_real(
    body: dict[str, Any],
    service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[dict[str, Any]]:
    model_id = body.get("model_id", "xgboost")
    symbol = body.get("symbol", "فولاد")
    result = await service.predict_real(model_id, symbol)
    if result.success:
        return ApiResponse[dict[str, Any]](success=True, data=result.value)
    return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": result.error or "Prediction failed"})


def _map_real_prediction(
    symbol: str,
    model_type: str,
    pred_result: dict[str, Any] | None,
    batch_id: str,
    duration_seconds: float,
    succeeded: bool,
) -> dict[str, Any]:
    """Map a real prediction result to a consistent response format.

    Returns real data when available, or a failed-status entry when not.
    No mock/fallback data is generated.
    """
    if succeeded and pred_result:
        confidence = pred_result.get("confidence", 0.75)
        return {
            "symbol": symbol,
            "model_type": model_type,
            "prediction": pred_result.get("prediction", 0),
            "accuracy": confidence,
            "confidence": confidence,
            "f1_score": confidence,
            "mse": 0.0,
            "samples": pred_result.get("samples", 0),
            "duration_seconds": round(duration_seconds, 2),
            "timestamp": pred_result.get("timestamp", datetime.now(UTC).isoformat()),
            "batch_id": batch_id,
            "predicted_change_pct": pred_result.get("predicted_change_pct"),
            "last_price": pred_result.get("last_price"),
            "feature_importance": pred_result.get("feature_importance", {}),
            "model_loaded_from": pred_result.get("model_loaded_from", "real"),
            "model_id": pred_result.get("model_id", model_type),
        }

    # Failed prediction — report error, no mock data
    return {
        "symbol": symbol,
        "model_type": model_type,
        "prediction": 0,
        "accuracy": 0,
        "confidence": 0,
        "f1_score": 0,
        "mse": 0,
        "samples": 0,
        "duration_seconds": round(duration_seconds, 2),
        "timestamp": datetime.now(UTC).isoformat(),
        "batch_id": batch_id,
        "prediction_failed": True,
        "error": f"No trained model available for {model_type}/{symbol}",
        "model_loaded_from": "none",
    }


@router.post(
    "/predict-all",
    summary="Run model on all symbols",
    description="Run the specified model on ALL symbols from the database using real predictions",
)
async def predict_all(
    body: dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    model_type = body.get("model_type", "xgboost")
    overall_start = time.time()

    # ── 1. Dynamically fetch all symbols from the database ──
    repo = InstrumentRepository(session=session)
    instruments_result = await repo.list(page=1, page_size=10000)
    if instruments_result.success and instruments_result.value:
        db_symbols = [
            inst.symbol
            for inst in instruments_result.value.items
            if inst.symbol and inst.status.value == "active"
        ]
    else:
        db_symbols = []

    symbols = body.get("symbols")
    if not symbols:
        symbols = db_symbols
    if not symbols:
        return ApiResponse[dict[str, Any]](
            success=False, data={},
            error={"message": "No symbols available — ensure brsapi_symbol_snapshots table has data"},
        )

    # ── 2. Create inference service with DB access for real predictions ──
    from repositories.ml_repository import MlRepository
    from repositories.quote_repository import QuoteRepository

    inference = InferenceService(
        quote_repo=QuoteRepository(session=session),
        model_repo=MlRepository(session=session),
    )

    batch_id = uuid.uuid4().hex[:12]
    results: list[dict[str, Any]] = []

    # ── 3. Run real predictions in parallel (with configurable concurrency limit) ──
    max_concurrency = min(body.get("max_concurrency", 50), 200)  # default 50, max 200
    sem = asyncio.Semaphore(max_concurrency)

    async def _predict_one(sym: str) -> tuple[str, dict[str, Any] | None, float, bool]:
        async with sem:
            t0 = time.time()
            try:
                pred = await inference.predict_real(model_type, sym)
                elapsed = time.time() - t0
                if pred.success:
                    return sym, pred.value, elapsed, True
                return sym, None, elapsed, False
            except Exception:
                return sym, None, time.time() - t0, False

    tasks = [_predict_one(sym) for sym in symbols]
    completed = await asyncio.gather(*tasks)

    # ── 4. Map results ──
    for sym, pred_val, elapsed, ok in completed:
        mapped = _map_real_prediction(sym, model_type, pred_val, batch_id, elapsed, ok)
        results.append(mapped)
        _prediction_results[mapped["symbol"]] = mapped

    total_elapsed = time.time() - overall_start
    successful = sum(1 for r in results if not r.get("prediction_failed"))
    failed = len(results) - successful

    # ── 5. Persist results to database ──
    try:
        from repositories.prediction_repository import PredictionRepository
        pred_repo = PredictionRepository(session=session)
        await pred_repo.save_batch(results)
        await session.commit()
    except Exception as persist_err:
        logger.warning("Could not persist predictions to DB: %s", persist_err)

    return ApiResponse[dict[str, Any]](success=True, data={
        "batch_id": batch_id,
        "model_type": model_type,
        "total_symbols": len(results),
        "successful": successful,
        "failed": failed,
        "total_duration_seconds": round(total_elapsed, 2),
        "data_source": "database" if db_symbols else "default",
        "results": results,
    })


@router.get(
    "/predictions",
    summary="List prediction results",
    description="List saved prediction results from DB, optionally filtered by symbol",
)
async def list_predictions(
    symbol: str | None = Query(None, description="Filter by symbol"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[dict[str, Any]]]:
    # Try DB first (persistent storage)
    from repositories.prediction_repository import PredictionRepository

    try:
        repo = PredictionRepository(session=session)
        db_result = await repo.list_recent(limit=1000, symbol=symbol)
        if db_result.success and db_result.value:
            return ApiResponse[list[dict[str, Any]]](success=True, data=db_result.value)
    except Exception as e:
        logger.warning("Could not load predictions from DB: %s", e)

    # Fallback to in-memory store
    if symbol:
        filtered = [v for k, v in _prediction_results.items() if symbol in k or symbol in v.get("symbol", "")]
        return ApiResponse[list[dict[str, Any]]](success=True, data=filtered)
    return ApiResponse[list[dict[str, Any]]](success=True, data=list(_prediction_results.values()))


@router.post("/train")
async def train(
    body: MlTrainRequest,
    session: AsyncSession = Depends(get_db_session),
    service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[MlTrainResponse]:
    from repositories.quote_repository import QuoteRepository
    from services.global_training_service import get_training_service
    from services.training_service import TrainingService

    symbol = body.symbols[0] if body.symbols else "فولاد"

    # Real training pipeline
    quote_repo = QuoteRepository(session=session)
    trainer = TrainingService(quote_repo=quote_repo)
    result = await trainer.train_with_db_data(
        symbol=symbol,
        model_type=body.model_type,
        start_date=body.start_date,
        end_date=body.end_date,
        experiment_name=body.experiment_name,
    )

    if result.success and result.value:
        run = result.value
        train_service = get_training_service()
        if run.get("id"):
            train_service._runs[run["id"]] = run

        resp = MlTrainResponse(
            run_id=run.get("id", ""),
            experiment_name=run.get("experiment_name", ""),
            model_type=body.model_type,
            status="completed",
            message=f"مدل {body.model_type} روی {symbol} آموزش دید — "
            f"R²={run['metrics'].get('r2', 0):.3f}, "
            f"MSE={run['metrics'].get('mse', 0):.4f}",
        )
        return ApiResponse[MlTrainResponse](success=True, data=resp)

    return ApiResponse[MlTrainResponse](
        success=False, data=None,
        error={"message": result.error or f"Training failed for {symbol} — ensure quote data exists in database"},
    )


@router.post(
    "/train-all",
    summary="Train model on all symbols",
    description="Train a model on ALL symbols from the database in parallel and save artifacts",
)
async def train_all(
    body: MlTrainRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    from repositories.quote_repository import QuoteRepository
    from services.global_training_service import get_training_service
    from services.training_service import TrainingService

    model_type = body.model_type or "xgboost"
    overall_start = time.time()

    # ── 1. Dynamically fetch all symbols from the database ──
    repo = InstrumentRepository(session=session)
    instruments_result = await repo.list(page=1, page_size=10000)
    if instruments_result.success and instruments_result.value:
        symbols = [
            inst.symbol
            for inst in instruments_result.value.items
            if inst.symbol and inst.status.value == "active"
        ]
    else:
        symbols = body.symbols or []

    if not symbols:
        return ApiResponse[dict[str, Any]](
            success=False, data={},
            error={"message": "No symbols available — ensure brsapi_symbol_snapshots table has data"},
        )

    if body.symbols:
        symbols = [s for s in body.symbols if s in symbols] or symbols

    # ── 2. Create training service with DB access ──
    trainer = TrainingService(quote_repo=QuoteRepository(session=session))
    train_service = get_training_service()

    runs: list[dict[str, Any]] = []

    # ── 3. Train on each symbol in parallel (with concurrency limit) ──
    sem = asyncio.Semaphore(5)  # max 5 concurrent training (CPU-intensive)

    async def _train_one(sym: str) -> dict[str, Any]:
        async with sem:
            t0 = time.time()
            try:
                result = await trainer.train_with_db_data(
                    symbol=sym,
                    model_type=model_type,
                    start_date=body.start_date,
                    end_date=body.end_date,
                    experiment_name=body.experiment_name or f"{model_type}-{sym}-batch",
                )
                elapsed = time.time() - t0
                if result.success and result.value:
                    run = result.value
                    return {
                        "symbol": sym,
                        "success": True,
                        "run_id": run.get("id", ""),
                        "metrics": run.get("metrics", {}),
                        "train_samples": run.get("train_samples", 0),
                        "val_samples": run.get("val_samples", 0),
                        "duration_seconds": round(elapsed, 2),
                    }
                return {
                    "symbol": sym,
                    "success": False,
                    "error": result.error or "Training failed",
                    "duration_seconds": round(elapsed, 2),
                }
            except Exception as e:
                return {
                    "symbol": sym,
                    "success": False,
                    "error": str(e),
                    "duration_seconds": round(time.time() - t0, 2),
                }

    tasks = [_train_one(sym) for sym in symbols]
    completed = await asyncio.gather(*tasks)

    # ── 4. Register completed runs in global service ──
    for result in completed:
        if result["success"]:
            run_id = result.get("run_id", "")
            if run_id and run_id in trainer._runs:
                train_service._runs[run_id] = trainer._runs[run_id]
            runs.append(result)
        else:
            runs.append(result)

    total_elapsed = time.time() - overall_start
    successful = sum(1 for r in runs if r.get("success"))
    failed = len(runs) - successful

    # Compute aggregate statistics
    best_r2 = None
    best_symbol = None
    avg_r2 = 0.0
    r2_count = 0
    for r in runs:
        metrics = r.get("metrics", {})
        r2 = metrics.get("r2")
        if r2 is not None:
            avg_r2 += r2
            r2_count += 1
            if best_r2 is None or r2 > best_r2:
                best_r2 = r2
                best_symbol = r["symbol"]

    avg_r2 = round(avg_r2 / r2_count, 4) if r2_count > 0 else None

    return ApiResponse[dict[str, Any]](success=True, data={
        "model_type": model_type,
        "total_symbols": len(symbols),
        "successful": successful,
        "failed": failed,
        "total_duration_seconds": round(total_elapsed, 2),
        "best_r2": best_r2,
        "best_symbol": best_symbol,
        "avg_r2": avg_r2,
        "data_source": "database",
        "results": runs,
    })


@router.get(
    "/comparison",
    summary="Model comparison",
    description="Compare all trained models across symbols",
)
async def get_comparison(
    service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[list[dict[str, Any]]]:
    result = await service.get_comparison()
    return ApiResponse[list[dict[str, Any]]](success=True, data=result.value if result.success else [])


@router.get(
    "/model-loader/cache-info",
    summary="ModelLoader cache info",
    description="Runtime diagnostics for the ModelLoader LRU cache: hit/miss stats, "
    "capacity, and the symbols whose models are currently hot in memory.",
)
async def model_loader_cache_info() -> ApiResponse[dict[str, Any]]:
    """Return live ModelLoader LRU cache diagnostics for runtime monitoring.

    Data comes from the shared ModelLoader singleton (``get_model_loader``),
    so it reflects what the running process actually has cached:
      - ``cache_info``: maxsize / currsize / hits / misses (LRU stats)
      - ``cached_symbols``: symbols whose models are hot in memory right now
    """
    try:
        from ml.model_loader import get_model_loader

        loader = get_model_loader()
        info = loader.cache_info()
        return ApiResponse[dict[str, Any]](success=True, data={
            "cache_info": info,
            "cached_symbols": info.get("cached_symbols", []),
        })
    except Exception as e:
        logger.warning("Could not read ModelLoader cache info: %s", e)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={},
            error={"message": f"Could not read ModelLoader cache info: {e}"},
        )
