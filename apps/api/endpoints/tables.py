from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()

TABLE_ORDER = [
    "instruments", "quotes", "trades", "signals", "recommendations",
    "indicators", "news_articles", "codal_reports", "markets",
    "macro_indicators", "alerts", "alert_history", "orderbooks",
    "backtest_runs", "backtest_trades", "portfolios", "portfolio_positions",
    "ml_models", "ml_model_versions", "ml_training_runs",
    "users", "job_runs", "audit_logs", "provider_health", "provider_health_history",
]


def _serialize(val: Any) -> Any:
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, bytes):
        return f"<{len(val)} bytes>"
    return val


@router.get("", summary="List tables", description="List all database tables with row counts")
async def list_tables(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    result = await session.execute(
        text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
    )
    all_tables = [row[0] for row in result.fetchall()]

    tables = []
    for t in all_tables:
        try:
            count_result = await session.execute(text(f'SELECT COUNT(*) FROM "{t}"'))
            count = count_result.scalar() or 0
        except Exception:
            count = -1
        tables.append({"name": t, "row_count": count})

    order_map = {name: i for i, name in enumerate(TABLE_ORDER)}
    tables.sort(key=lambda t: (order_map.get(t["name"], 999), t["name"]))

    return ApiResponse[dict[str, Any]](success=True, data={"tables": tables})


@router.get("/{table_name}", summary="Get table data", description="Get paginated data from any table")
async def get_table_data(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str | None = Query(None, description="Search in text columns"),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    check = await session.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :name
            )
        """),
        {"name": table_name},
    )
    if not check.scalar():
        return ApiResponse[dict[str, Any]](
            success=False, error={"message": f"Table '{table_name}' not found"}
        )

    cols_result = await session.execute(
        text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :name
            ORDER BY ordinal_position
        """),
        {"name": table_name},
    )
    columns = [{"name": row[0], "type": row[1]} for row in cols_result.fetchall()]

    count_result = await session.execute(
        text(f'SELECT COUNT(*) FROM "{table_name}"')
    )
    total = count_result.scalar() or 0

    where_clause = ""
    params: dict[str, Any] = {}
    if search:
        text_cols = [c["name"] for c in columns if c["type"] in ("text", "character varying", "varchar")]
        if text_cols:
            conditions = " OR ".join([f'"{c}"::text ILIKE :search' for c in text_cols])
            where_clause = f"WHERE {conditions}"
            params["search"] = f"%{search}%"

    offset = (page - 1) * page_size
    data_result = await session.execute(
        text(f'SELECT * FROM "{table_name}" {where_clause} ORDER BY 1 LIMIT :limit OFFSET :offset'),
        {**params, "limit": page_size, "offset": offset},
    )
    rows = [dict(row._mapping) for row in data_result.fetchall()]

    for row in rows:
        for k, v in row.items():
            row[k] = _serialize(v)

    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "table": table_name,
            "columns": columns,
            "rows": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, -(-total // page_size)),
        },
    )
