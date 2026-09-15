"""Codal audit summary endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session

router = APIRouter()

_TABLE = "codal_audit_summary"
_ALLOWED_SORT = {
    "symbol",
    "health_score",
    "roe",
    "roa",
    "net_margin",
    "gross_margin",
    "current_ratio",
    "debt_to_equity",
    "revenue",
    "net_profit",
    "total_assets",
    "revenue_growth",
}


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            row[k] = v.isoformat()
    return row


@router.get("/summary")
async def get_audit_summary(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str = Query(""),
    health: str = Query(""),
    sort_by: str = Query("health_score"),
    sort_dir: str = Query("desc"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    wheres: list[str] = []
    params: dict[str, Any] = {}

    if search:
        wheres.append("symbol ILIKE :search")
        params["search"] = f"%{search}%"

    if health:
        wheres.append("health_classification = :health")
        params["health"] = health

    wsql = (" WHERE " + " AND ".join(wheres)) if wheres else ""
    sort_col = sort_by if sort_by in _ALLOWED_SORT else "health_score"
    sdir = "ASC" if sort_dir.lower() == "asc" else "DESC"

    count_result = await session.execute(text(f"SELECT COUNT(*) as cnt FROM {_TABLE}{wsql}"), params)
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    data_result = await session.execute(
        text(f"SELECT * FROM {_TABLE}{wsql} ORDER BY {sort_col} {sdir} NULLS LAST LIMIT :limit OFFSET :offset"),
        {**params, "limit": page_size, "offset": offset},
    )
    rows = [_serialize(dict(row._mapping)) for row in data_result.fetchall()]

    return {
        "data": {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    }


@router.get("/stats")
async def get_audit_stats(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    hdist_result = await session.execute(
        text(
            "SELECT health_classification, COUNT(*) as cnt, AVG(health_score) as avg_score "
            "FROM codal_audit_summary GROUP BY health_classification ORDER BY cnt DESC"
        )
    )
    hdist = [dict(row._mapping) for row in hdist_result.fetchall()]

    top_roe_result = await session.execute(
        text(
            "SELECT symbol, health_score, health_classification, roe, roa, net_margin, "
            "current_ratio, debt_to_equity FROM codal_audit_summary "
            "WHERE roe IS NOT NULL ORDER BY roe DESC LIMIT 10"
        )
    )
    top_roe = [dict(row._mapping) for row in top_roe_result.fetchall()]

    worst_roe_result = await session.execute(
        text(
            "SELECT symbol, health_score, health_classification, roe, roa, net_margin, "
            "current_ratio, debt_to_equity FROM codal_audit_summary "
            "WHERE roe IS NOT NULL ORDER BY roe ASC LIMIT 10"
        )
    )
    worst_roe = [dict(row._mapping) for row in worst_roe_result.fetchall()]

    fd_result = await session.execute(
        text(
            "SELECT forensic_risk, COUNT(*) as cnt FROM codal_audit_summary "
            "WHERE forensic_risk IS NOT NULL GROUP BY forensic_risk ORDER BY cnt DESC"
        )
    )
    fd = [dict(row._mapping) for row in fd_result.fetchall()]

    total_result = await session.execute(text("SELECT COUNT(*) as t FROM codal_audit_summary"))
    total = total_result.scalar() or 0

    return {
        "data": {
            "total": total,
            "health_distribution": hdist,
            "top_roe": top_roe,
            "worst_roe": worst_roe,
            "forensic_distribution": fd,
        }
    }


@router.get("/symbol/{symbol}")
async def get_symbol_audit(
    symbol: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(
        text("SELECT * FROM codal_audit_summary WHERE symbol = :symbol"),
        {"symbol": symbol},
    )
    row = result.mappings().first()
    if not row:
        return {"data": None, "error": "Not found"}

    return {"data": _serialize(dict(row))}
