"""Decision Engine API — Serve architecture data & decision results from PostgreSQL.

Endpoints:
  GET    /decision-engine/architecture       — Full architecture blueprint
  GET    /decision-engine/features           — 110 features in 8 blocks
  GET    /decision-engine/services           — 22 services
  GET    /decision-engine/database           — Database tables
  GET    /decision-engine/api                — API endpoints
  GET    /decision-engine/overview           — All data combined (for dashboard)
  POST   /decision-engine/seed              — Load JSON data into DB (admin)
  GET    /decision-engine/decisions         — List saved decisions (filterable)
  POST   /decision-engine/decisions         — Save a new decision result
  GET    /decision-engine/decisions/buy-candidates   — Latest BUY decisions
  GET    /decision-engine/decisions/watchlist         — Latest WATCHLIST decisions
  GET    /decision-engine/decisions/rejected           — Latest REJECT decisions
  GET    /decision-engine/decisions/runs             — List unique run IDs
  GET    /decision-engine/decisions/{symbol}          — Latest decision for a symbol
  GET    /decision-engine/decisions/{symbol}/history  — Decision history for a symbol
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from core.logging import get_logger
from models.decision_engine import DecisionArchitecture, DecisionResult
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()


def _safe_error_message(exc: BaseException, *, default_message: str = "Internal error") -> str:
    """Return a non-leaking message string for a caught exception.

    Preserves the historical ``{"message": <str>}`` response shape. In
    production ``str(exc)`` is suppressed and a generic message is returned
    (the full exception is still logged). In development ``str(exc)`` is
    included for debugging.
    """
    from core.config import settings

    is_dev = settings.environment == "development"
    if is_dev:
        return str(exc) or default_message
    return default_message


# ── Pydantic Schema ──


class DecisionResultCreate(BaseModel):
    """Schema for saving a new decision result."""

    symbol: str = Field(..., min_length=1, max_length=20, description="نماد بورسی")
    run_id: str = Field(..., min_length=1, max_length=50, description="شناسه اجرا")
    model_version: str = Field("Enterprise-Final-1.0", max_length=50, description="نسخه مدل")
    rulebook_version: str = Field("RB-1.0", max_length=50, description="نسخه Rulebook")
    # 8 sub-scores
    score_fundamental: float | None = Field(None, ge=0, le=100)
    score_valuation: float | None = Field(None, ge=0, le=100)
    score_technical: float | None = Field(None, ge=0, le=100)
    score_liquidity: float | None = Field(None, ge=0, le=100)
    score_orderflow: float | None = Field(None, ge=0, le=100)
    score_micro: float | None = Field(None, ge=0, le=100)
    score_macro: float | None = Field(None, ge=0, le=100)
    score_event: float | None = Field(None, ge=0, le=100)
    # Aggregated
    base_score: float | None = Field(None, ge=0, le=100)
    micro_adjustment: float | None = Field(None, ge=-20, le=20)
    penalty: float | None = Field(None, ge=0, le=0.35)
    # Final
    final_score: float | None = Field(None, ge=0, le=100)
    decision: str = Field(..., pattern="^(BUY|WATCHLIST|HOLD|REDUCE|REJECT|NEUTRAL)$", description="تصمیم نهایی")
    confidence: float | None = Field(None, ge=0, le=1)
    neg_events_count: int | None = Field(None, ge=0)
    details: dict[str, Any] | None = Field(None, description="جزئیات کامل (دلایل، reason_codes، report)")


def _result_to_dict(r: DecisionResult) -> dict[str, Any]:
    """Convert a DecisionResult ORM object to a response dict."""
    return {
        "id": r.id,
        "symbol": r.symbol,
        "run_id": r.run_id,
        "model_version": r.model_version,
        "rulebook_version": r.rulebook_version,
        "score_fundamental": r.score_fundamental,
        "score_valuation": r.score_valuation,
        "score_technical": r.score_technical,
        "score_liquidity": r.score_liquidity,
        "score_orderflow": r.score_orderflow,
        "score_micro": r.score_micro,
        "score_macro": r.score_macro,
        "score_event": r.score_event,
        "base_score": r.base_score,
        "micro_adjustment": r.micro_adjustment,
        "penalty": r.penalty,
        "final_score": r.final_score,
        "decision": r.decision,
        "confidence": r.confidence,
        "neg_events_count": r.neg_events_count,
        "details": r.details,
        "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
    }


# ── Cache ──
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 300  # 5 minutes for static architecture data


def _cache_get(key: str) -> Any | None:
    if key in _CACHE:
        ts, val = _CACHE[key]
        if time.time() - ts < _CACHE_TTL:
            return val
        del _CACHE[key]
    return None


def _cache_set(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)
    if len(_CACHE) > 20:
        oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
        del _CACHE[oldest]


# ── JSON fallback paths ──
_JSON_DIR = Path("json")


def _load_json(filename: str) -> dict | None:
    """Fallback: load JSON file directly if DB not available."""
    path = _JSON_DIR / filename
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


async def _auto_seed(session: AsyncSession) -> None:
    """Auto-seed architecture data from JSON if DB is empty (merges all 5 files)."""
    result = await session.execute(select(DecisionArchitecture).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    arch = _load_json("architecture.json")
    if arch is None:
        return
    # Merge all data files
    for key, fname in [
        ("features", "features.json"),
        ("services", "services.json"),
        ("database", "database.json"),
        ("api", "api.json"),
    ]:
        data = _load_json(fname)
        if data:
            arch[key] = data
    version = arch.get("system", {}).get("version", "unknown")
    record = DecisionArchitecture(
        version=version,
        title=arch.get("system", {}).get("name", "DSS"),
        data=arch,
        is_active=True,
    )
    session.add(record)
    await session.commit()
    logger.info("Auto-seeded architecture v%s from JSON (merged)", version)


# ── Helper: get architecture from DB or JSON fallback ──


async def _get_data_from_db(session: AsyncSession) -> dict | None:
    """Get active architecture record from PostgreSQL."""
    try:
        result = await session.execute(
            select(DecisionArchitecture)
            .where(
                DecisionArchitecture.is_active == True  # noqa: E712
            )
            .order_by(DecisionArchitecture.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row.data
    except Exception:
        logger.warning("DB query failed, falling back to JSON")
    return None


async def _get_architecture(session: AsyncSession) -> dict | None:
    """Get architecture: cache -> DB -> JSON fallback -> auto-seed."""
    cached = _cache_get("architecture:active")
    if cached:
        return cached

    arch = await _get_data_from_db(session)

    if arch is None:
        arch = _load_json("architecture.json")
        if arch is not None:
            # Auto-seed: load JSON into DB for next time
            with contextlib.suppress(Exception):
                await _auto_seed(session)

    if arch is not None:
        _cache_set("architecture:active", arch)
    return arch


async def _get_data(key: str, filename: str, session: AsyncSession) -> dict | None:
    """Generic fetcher: cache -> DB (nested in architecture.data) -> JSON fallback."""
    cached = _cache_get(key)
    if cached:
        return cached

    data: dict | None = None
    arch = await _get_data_from_db(session)
    if arch is not None and key in arch:
        data = arch[key]

    if data is None:
        data = _load_json(filename)

    if data is not None:
        _cache_set(key, data)
    return data


# ── Endpoints ──


@router.get(
    "/architecture",
    summary="Architecture Blueprint",
    description="Get the full 12-layer architecture blueprint from database with JSON fallback",
)
async def get_architecture(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get the full architecture blueprint."""
    try:
        arch = await _get_architecture(session)
        if arch is None:
            return ApiResponse(success=False, data={}, error={"message": "Architecture data not available"})
        return ApiResponse(success=True, data=arch)
    except Exception as exc:
        logger.exception("Failed to get architecture: %s", exc)
        return ApiResponse(success=False, data={}, error={"message": _safe_error_message(exc)})


@router.get(
    "/features",
    summary="110 Features",
    description="Get all 110 features in 8 expert blocks from database with JSON fallback",
)
async def get_features(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get all 110 features in 8 blocks."""
    data = await _get_data("features", "features.json", session)
    if data is None:
        return ApiResponse(success=False, data={}, error={"message": "Features data not available"})
    return ApiResponse(success=True, data=data)


@router.get(
    "/services",
    summary="22 Services",
    description="Get list of all 22 services from database with JSON fallback",
)
async def get_services(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get all 22 services."""
    data = await _get_data("services", "services.json", session)
    if data is None:
        return ApiResponse(success=False, data={}, error={"message": "Services data not available"})
    return ApiResponse(success=True, data=data)


@router.get(
    "/database",
    summary="Database Tables",
    description="Get database table structure from database with JSON fallback",
)
async def get_database(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get all database tables."""
    data = await _get_data("database", "database.json", session)
    if data is None:
        return ApiResponse(success=False, data={}, error={"message": "Database data not available"})
    return ApiResponse(success=True, data=data)


@router.get(
    "/api",
    summary="API Endpoints",
    description="Get list of internal and external API endpoints from database with JSON fallback",
)
async def get_api(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get all API endpoints."""
    data = await _get_data("api", "api.json", session)
    if data is None:
        return ApiResponse(success=False, data={}, error={"message": "API data not available"})
    return ApiResponse(success=True, data=data)


@router.get(
    "/overview",
    summary="Overview",
    description="Get all architecture data combined for the frontend dashboard",
)
async def get_overview(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get all architecture data combined."""
    arch = await _get_architecture(session)
    features = await _get_data("features", "features.json", session)
    services = await _get_data("services", "services.json", session)
    database = await _get_data("database", "database.json", session)
    api_data = await _get_data("api", "api.json", session)

    overview = {
        "system": arch.get("system") if arch else {},
        "layers": arch.get("layers") if arch else [],
        "features": features,
        "services": services,
        "database": database,
        "api": api_data,
    }
    return ApiResponse(success=True, data=overview)


# ════════════════════════════════════════════════════════════════════════════
# 📊 DECISION RESULTS CRUD — ذخیره و بازیابی تصمیمات واقعی
# ════════════════════════════════════════════════════════════════════════════


@router.post(
    "/decisions",
    summary="Save Decision Result",
    description="Save a new decision result (BUY / WATCHLIST / HOLD / REDUCE / REJECT / NEUTRAL) to the database.",
)
async def save_decision(
    body: DecisionResultCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Save a new decision result for a symbol."""
    try:
        record = DecisionResult(
            symbol=body.symbol,
            run_id=body.run_id,
            model_version=body.model_version,
            rulebook_version=body.rulebook_version,
            score_fundamental=body.score_fundamental,
            score_valuation=body.score_valuation,
            score_technical=body.score_technical,
            score_liquidity=body.score_liquidity,
            score_orderflow=body.score_orderflow,
            score_micro=body.score_micro,
            score_macro=body.score_macro,
            score_event=body.score_event,
            base_score=body.base_score,
            micro_adjustment=body.micro_adjustment,
            penalty=body.penalty,
            final_score=body.final_score,
            decision=body.decision,
            confidence=body.confidence,
            neg_events_count=body.neg_events_count,
            details=body.details,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)

        return ApiResponse(
            success=True,
            data=_result_to_dict(record),
            message=f"تصمیم {body.decision} برای {body.symbol} ذخیره شد",
        )
    except Exception as exc:
        logger.exception("Failed to save decision for %s: %s", body.symbol, exc)
        return ApiResponse(success=False, data={}, error={"message": _safe_error_message(exc)})


@router.get(
    "/decisions",
    summary="List Decisions",
    description="List decision results with optional filters (symbol, decision type, pagination).",
)
async def list_decisions(
    symbol: str | None = Query(None, description="فیلتر بر اساس نماد"),
    decision: str | None = Query(
        None, description="فیلتر بر اساس نوع تصمیم (BUY/WATCHLIST/HOLD/REDUCE/REJECT/NEUTRAL)"
    ),
    run_id: str | None = Query(None, description="فیلتر بر اساس شناسه اجرا"),
    limit: int = Query(50, ge=1, le=200, description="تعداد نتایج"),
    offset: int = Query(0, ge=0, description="شروع از"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """List decision results with optional filters."""
    try:
        stmt = select(DecisionResult).order_by(desc(DecisionResult.evaluated_at))

        if symbol:
            stmt = stmt.where(DecisionResult.symbol == symbol.upper())
        if decision:
            stmt = stmt.where(DecisionResult.decision == decision.upper())
        if run_id:
            stmt = stmt.where(DecisionResult.run_id == run_id)

        # Get total count
        count_stmt = stmt.with_only_columns(DecisionResult.id).limit(10000)
        count_result = await session.execute(count_stmt)
        total = len(count_result.scalars().all())

        # Get paginated results
        stmt = stmt.offset(offset).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        items = [_result_to_dict(r) for r in rows]

        return ApiResponse(
            success=True,
            data={
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )
    except Exception as exc:
        logger.exception("Failed to list decisions: %s", exc)
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": _safe_error_message(exc)})


@router.get(
    "/decisions/buy-candidates",
    summary="Buy Candidates",
    description="Get the most recent BUY decision for each symbol (for the dashboard buy list).",
)
async def buy_candidates(
    limit: int = Query(50, ge=1, le=200),
    min_score: float = Query(0.0, ge=0, le=100, description="حداقل امتیاز نهایی"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get latest BUY decisions, one per symbol."""
    try:
        stmt = (
            select(DecisionResult)
            .where(
                DecisionResult.decision == "BUY",
                DecisionResult.final_score >= min_score,
            )
            .order_by(DecisionResult.symbol, desc(DecisionResult.evaluated_at))
            .distinct(DecisionResult.symbol)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        items = [_result_to_dict(r) for r in rows]
        return ApiResponse(success=True, data={"items": items, "total": len(items)})
    except Exception as exc:
        logger.exception("Failed to get buy candidates: %s", exc)
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": _safe_error_message(exc)})


@router.get(
    "/decisions/watchlist",
    summary="Watchlist",
    description="Get the most recent WATCHLIST decision for each symbol.",
)
async def watchlist_decisions(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get latest WATCHLIST decisions, one per symbol."""
    try:
        stmt = (
            select(DecisionResult)
            .where(DecisionResult.decision == "WATCHLIST")
            .order_by(DecisionResult.symbol, desc(DecisionResult.evaluated_at))
            .distinct(DecisionResult.symbol)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        items = [_result_to_dict(r) for r in rows]
        return ApiResponse(success=True, data={"items": items, "total": len(items)})
    except Exception as exc:
        logger.exception("Failed to get watchlist: %s", exc)
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": _safe_error_message(exc)})


@router.get(
    "/decisions/rejected",
    summary="Rejected Symbols",
    description="Get the most recent REJECT decision for each symbol.",
)
async def rejected_decisions(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get latest REJECT decisions, one per symbol."""
    try:
        stmt = (
            select(DecisionResult)
            .where(DecisionResult.decision == "REJECT")
            .order_by(DecisionResult.symbol, desc(DecisionResult.evaluated_at))
            .distinct(DecisionResult.symbol)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        items = [_result_to_dict(r) for r in rows]
        return ApiResponse(success=True, data={"items": items, "total": len(items)})
    except Exception as exc:
        logger.exception("Failed to get rejected: %s", exc)
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": _safe_error_message(exc)})


@router.get(
    "/decisions/runs",
    summary="List Unique Run IDs",
    description="Get all unique run_id values with metadata (count, date range) to let users browse decisions by execution batch.",
)
async def list_runs(
    limit: int = Query(20, ge=1, le=100, description="تعداد run_idها"),
    offset: int = Query(0, ge=0, description="شروع از"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """List unique run IDs with statistics."""
    try:
        from sqlalchemy import func

        # Get unique run_ids with counts and date range
        stmt = (
            select(
                DecisionResult.run_id,
                func.count(DecisionResult.id).label("decision_count"),
                func.min(DecisionResult.evaluated_at).label("first_seen"),
                func.max(DecisionResult.evaluated_at).label("last_seen"),
                func.max(DecisionResult.model_version).label("model_version"),
            )
            .group_by(DecisionResult.run_id)
            .order_by(desc(func.max(DecisionResult.evaluated_at)))
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

        # Get total unique run count
        count_stmt = select(func.count(func.distinct(DecisionResult.run_id))).select_from(DecisionResult)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        items = []
        for row in rows:
            items.append(
                {
                    "run_id": row.run_id,
                    "decision_count": row.decision_count,
                    "first_seen": row.first_seen.isoformat() if row.first_seen else None,
                    "last_seen": row.last_seen.isoformat() if row.last_seen else None,
                    "model_version": row.model_version,
                }
            )

        return ApiResponse(
            success=True,
            data={
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )
    except Exception as exc:
        logger.exception("Failed to list runs: %s", exc)
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": _safe_error_message(exc)})


@router.get(
    "/decisions/stats",
    summary="Decision Statistics",
    description="Get aggregate statistics for all decisions: counts by type, average scores, and summary metrics.",
)
async def get_decision_stats(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get aggregate statistics for all decisions in the database."""
    try:
        from sqlalchemy import func

        # ── Count by decision type ──
        count_stmt = select(DecisionResult.decision, func.count(DecisionResult.id).label("cnt")).group_by(
            DecisionResult.decision
        )
        count_result = await session.execute(count_stmt)
        decision_counts: dict[str, int] = {}
        for row in count_result.all():
            decision_counts[row.decision] = row.cnt

        total = sum(decision_counts.values())

        # ── Average scores ──
        avg_stmt = select(
            func.avg(DecisionResult.final_score).label("avg_final_score"),
            func.avg(DecisionResult.confidence).label("avg_confidence"),
            func.avg(DecisionResult.base_score).label("avg_base_score"),
            func.avg(DecisionResult.penalty).label("avg_penalty"),
            func.avg(DecisionResult.micro_adjustment).label("avg_micro_adjustment"),
            func.avg(DecisionResult.score_fundamental).label("avg_score_fundamental"),
            func.avg(DecisionResult.score_valuation).label("avg_score_valuation"),
            func.avg(DecisionResult.score_technical).label("avg_score_technical"),
            func.avg(DecisionResult.score_liquidity).label("avg_score_liquidity"),
            func.avg(DecisionResult.score_orderflow).label("avg_score_orderflow"),
            func.avg(DecisionResult.score_micro).label("avg_score_micro"),
            func.avg(DecisionResult.score_macro).label("avg_score_macro"),
            func.avg(DecisionResult.score_event).label("avg_score_event"),
        )
        avg_result = await session.execute(avg_stmt)
        avg_row = avg_result.one()

        # ── Latest evaluation timestamp ──
        latest_stmt = select(func.max(DecisionResult.evaluated_at)).select_from(DecisionResult)
        latest_result = await session.execute(latest_stmt)
        latest_eval = latest_result.scalar()

        # ── Unique symbols ──
        symbols_stmt = select(func.count(func.distinct(DecisionResult.symbol))).select_from(DecisionResult)
        symbols_result = await session.execute(symbols_stmt)
        unique_symbols = symbols_result.scalar() or 0

        # ── Unique runs ──
        runs_stmt = select(func.count(func.distinct(DecisionResult.run_id))).select_from(DecisionResult)
        runs_result = await session.execute(runs_stmt)
        unique_runs = runs_result.scalar() or 0

        # ── Build response ──
        def _to_float_or_none(val: Any) -> float | None:
            return round(float(val), 2) if val is not None else None

        stats = {
            "total_decisions": total,
            "unique_symbols": unique_symbols,
            "unique_runs": unique_runs,
            "latest_evaluation": latest_eval.isoformat() if latest_eval else None,
            "decision_counts": {
                "BUY": decision_counts.get("BUY", 0),
                "WATCHLIST": decision_counts.get("WATCHLIST", 0),
                "HOLD": decision_counts.get("HOLD", 0),
                "REDUCE": decision_counts.get("REDUCE", 0),
                "REJECT": decision_counts.get("REJECT", 0),
                "NEUTRAL": decision_counts.get("NEUTRAL", 0),
            },
            "avg_scores": {
                "final_score": _to_float_or_none(avg_row.avg_final_score),
                "confidence": _to_float_or_none(avg_row.avg_confidence),
                "base_score": _to_float_or_none(avg_row.avg_base_score),
                "penalty": _to_float_or_none(avg_row.avg_penalty),
                "micro_adjustment": _to_float_or_none(avg_row.avg_micro_adjustment),
            },
            "avg_sub_scores": {
                "score_fundamental": _to_float_or_none(avg_row.avg_score_fundamental),
                "score_valuation": _to_float_or_none(avg_row.avg_score_valuation),
                "score_technical": _to_float_or_none(avg_row.avg_score_technical),
                "score_liquidity": _to_float_or_none(avg_row.avg_score_liquidity),
                "score_orderflow": _to_float_or_none(avg_row.avg_score_orderflow),
                "score_micro": _to_float_or_none(avg_row.avg_score_micro),
                "score_macro": _to_float_or_none(avg_row.avg_score_macro),
                "score_event": _to_float_or_none(avg_row.avg_score_event),
            },
        }

        return ApiResponse(success=True, data=stats)

    except Exception as exc:
        logger.exception("Failed to get decision stats: %s", exc)
        return ApiResponse(
            success=False,
            data={},
            error={"message": _safe_error_message(exc)},
        )


@router.get(
    "/decisions/{symbol}",
    summary="Latest Decision for Symbol",
    description="Get the most recent decision result for a specific symbol.",
)
async def get_symbol_decision(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get latest decision for a symbol."""
    try:
        stmt = (
            select(DecisionResult)
            .where(DecisionResult.symbol == symbol.upper())
            .order_by(desc(DecisionResult.evaluated_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            return ApiResponse(
                success=False,
                data={},
                error={"message": f"هیچ تصمیمی برای {symbol} یافت نشد"},
            )
        return ApiResponse(success=True, data=_result_to_dict(row))
    except Exception as exc:
        logger.exception("Failed to get decision for %s: %s", symbol, exc)
        return ApiResponse(success=False, data={}, error={"message": _safe_error_message(exc)})


@router.get(
    "/decisions/{symbol}/history",
    summary="Decision History",
    description="Get the full decision history for a specific symbol.",
)
async def get_symbol_decision_history(
    symbol: str,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get decision history for a symbol."""
    try:
        stmt = (
            select(DecisionResult)
            .where(DecisionResult.symbol == symbol.upper())
            .order_by(desc(DecisionResult.evaluated_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        items = [_result_to_dict(r) for r in rows]
        return ApiResponse(
            success=True,
            data={
                "symbol": symbol.upper(),
                "items": items,
                "total": len(items),
            },
        )
    except Exception as exc:
        logger.exception("Failed to get decision history for %s: %s", symbol, exc)
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": _safe_error_message(exc)})


@router.get(
    "/migration-status",
    summary="Migration & Table Status",
    description="Get Alembic migration revision, table row counts, and schema status for all decision engine tables.",
)
async def get_migration_status(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get migration history and table status for decision-engine tables."""
    try:
        from sqlalchemy import text

        # ── Alembic migration revision ──
        alembic_revision = None
        try:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            row = result.one_or_none()
            alembic_revision = row[0] if row else None
        except Exception:
            alembic_revision = None

        # ── Table row counts ──
        table_status = []
        for table_name in ["decision_architectures", "decision_results", "alembic_version"]:
            try:
                count_result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                row_count = count_result.scalar() or 0

                # Get last updated timestamp
                ts_col = (
                    "evaluated_at"
                    if table_name == "decision_results"
                    else "created_at"
                    if table_name == "decision_architectures"
                    else None
                )
                last_updated = None
                if ts_col:
                    with contextlib.suppress(Exception):
                        ts_result = await session.execute(text(f"SELECT MAX({ts_col}) FROM {table_name}"))
                        ts_val = ts_result.scalar()
                        last_updated = ts_val.isoformat() if ts_val else None

                table_status.append(
                    {
                        "table_name": table_name,
                        "row_count": row_count,
                        "last_updated": last_updated,
                        "status": "ok",
                    }
                )
            except Exception as exc:
                table_status.append(
                    {
                        "table_name": table_name,
                        "row_count": 0,
                        "last_updated": None,
                        "status": "missing",
                        "error": _safe_error_message(exc)[:100],
                    }
                )

        # ── Architecture version info ──
        arch_info = None
        with contextlib.suppress(Exception):
            arch_result = await session.execute(
                select(DecisionArchitecture)
                .where(
                    DecisionArchitecture.is_active == True  # noqa: E712
                )
                .order_by(DecisionArchitecture.id.desc())
                .limit(1)
            )
            arch_row = arch_result.scalar_one_or_none()
            if arch_row:
                arch_info = {
                    "version": arch_row.version,
                    "title": arch_row.title,
                    "is_active": arch_row.is_active,
                    "created_at": arch_row.created_at.isoformat() if arch_row.created_at else None,
                    "updated_at": arch_row.updated_at.isoformat() if arch_row.updated_at else None,
                }

        # ── Build response ──
        status_data = {
            "alembic_revision": alembic_revision,
            "tables": table_status,
            "architecture": arch_info,
            "total_decision_engine_tables": 2,
            "migration_applied": alembic_revision is not None,
        }

        return ApiResponse(success=True, data=status_data)

    except Exception as exc:
        logger.exception("Failed to get migration status: %s", exc)
        return ApiResponse(success=False, data={}, error={"message": _safe_error_message(exc)})


@router.post(
    "/seed",
    summary="Seed Architecture Data",
    description="Load all JSON architecture data into PostgreSQL (merges all 5 JSON files into one record)",
)
async def seed_architecture(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Load all JSON architecture data into PostgreSQL — merges 5 files into one record."""
    try:
        # Load ALL JSON files and merge into one record
        arch = _load_json("architecture.json")
        if arch is None:
            return ApiResponse(success=False, data={}, error={"message": "architecture.json not found"})

        # Merge all data files into the architecture record
        features = _load_json("features.json")
        services = _load_json("services.json")
        database = _load_json("database.json")
        api_data = _load_json("api.json")

        if features:
            arch["features"] = features
        if services:
            arch["services"] = services
        if database:
            arch["database"] = database
        if api_data:
            arch["api"] = api_data

        # Check if this version already exists
        version = arch.get("system", {}).get("version", "unknown")
        result = await session.execute(select(DecisionArchitecture).where(DecisionArchitecture.version == version))
        existing = result.scalar_one_or_none()

        if existing:
            existing.data = arch
            existing.is_active = True
            existing.title = arch.get("system", {}).get("name", "DSS")
        else:
            arch_record = DecisionArchitecture(
                version=version,
                title=arch.get("system", {}).get("name", "DSS"),
                data=arch,
                is_active=True,
            )
            session.add(arch_record)

        await session.commit()

        # Clear all cache
        for key in list(_CACHE.keys()):
            _CACHE.pop(key, None)

        return ApiResponse(
            success=True,
            data={
                "message": f"All architecture data (version {version}) saved to database",
                "version": version,
            },
        )
    except Exception as exc:
        logger.exception("Failed to seed architecture: %s", exc)
        return ApiResponse(success=False, data={}, error={"message": _safe_error_message(exc)})
