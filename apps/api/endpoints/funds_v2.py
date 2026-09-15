"""📊 Funds V2 API — Enterprise Fund Module Endpoints (بخش ۶).

نسخه‌بندی ماژولار: تمام قابلیت‌های جدید زیر پیشوند ``/funds/v2`` ارائه می‌شوند
تا قرارداد ``/funds`` فعلی (که صفحه فعلی صندوق‌ها استفاده می‌کند) دست‌نخورده
بماند (Zero Breaking Changes).

Endpoints:
  GET  /funds/v2/universe                 — کشف خودکار کل صندوق‌ها (DB-first + JIT)
  GET  /funds/v2/{fund_id}/nav-history    — تاریخچه NAV با Gap-Filling خودکار
  GET  /funds/v2/{fund_id}/holdings       — ریز دارایی (JIT از کدال)
  GET  /funds/v2/{fund_id}/valuation      — NAV لحظه‌ای تخمینی + Coverage
  GET  /funds/v2/{fund_id}/score          — امتیاز کمی کامل (Sharpe/Sortino/…)
  GET  /funds/v2/{fund_id}/backtest       — بک‌تست ۳ استراتژی
  GET  /funds/v2/rankings                 — رتبه‌بندی دوره‌ای همه صندوق‌ها
  GET  /funds/v2/portfolio-diffs          — ورود/خروج پول صندوق به نمادها
  GET  /funds/v2/monitoring               — متریک‌های پایش (P1)

نکته: ``fund_id`` کانونی فرمت ``tse:نماد`` یا ``ime:نماد`` دارد؛ برای
سازگاری، نماد خام هم پذیرفته می‌شود (→ ``tse:نماد``).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from core.logging import get_logger
from services.fund_quant_engine import (
    ScoreWeights,
    run_all_strategies,
    score_fund,
)
from services.fund_read_through import FundReadThroughService

logger = get_logger(__name__)
router = APIRouter()

ENGINE_VERSION = "v2.0.0"


def _get_service(session: AsyncSession = Depends(get_db_session)) -> FundReadThroughService:
    return FundReadThroughService(session=session)


def _canonical_fund_id(raw: str) -> str:
    """``آگاس`` → ``tse:آگاس``؛ ``ime:X`` دست‌نخورده."""
    if ":" in raw:
        return raw
    return f"tse:{raw}"


async def _load_nav_points(
    session: AsyncSession, fund_id: str, limit: int = 500
) -> list[dict[str, Any]]:
    """تاریخچه NAV از DB (جدول جدید + fallback به brsapi_nav_records قدیمی)."""
    rows = (
        await session.execute(
            text(
                """
                SELECT nav_date, COALESCE(nav_statistical, nav_redemption, nav_issue) AS nav
                FROM fund_nav_history
                WHERE fund_id = :fid AND COALESCE(nav_statistical, nav_redemption, nav_issue) IS NOT NULL
                ORDER BY nav_date ASC
                LIMIT :lim
                """
            ),
            {"fid": fund_id, "lim": limit},
        )
    ).fetchall()
    points = [{"date": str(r[0]), "nav": float(r[1])} for r in rows]
    if len(points) >= 30:
        return points
    # fallback: جدول قدیمی NAV (شمسی → میلادی با jdatetime در لایه quant)
    rows_old = (
        await session.execute(
            text(
                """
                SELECT date, COALESCE(nav_redemption, nav_issue) AS nav
                FROM brsapi_nav_records
                WHERE symbol = :sym AND (nav_redemption > 0 OR nav_issue > 0)
                ORDER BY date ASC
                LIMIT :lim
                """
            ),
            {"sym": fund_id.split(":", 1)[-1], "lim": limit},
        )
    ).fetchall()
    if rows_old:
        from services.fund_api_adapter import normalize_date

        for r in rows_old:
            gd = normalize_date(r[0])
            if gd is not None and r[1]:
                points.append({"date": str(gd), "nav": float(r[1])})
    # dedupe + sort
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for p in sorted(points, key=lambda x: x["date"]):
        if p["date"] not in seen:
            seen.add(p["date"])
            deduped.append(p)
    return deduped


async def _load_benchmark(session: AsyncSession, limit: int = 500) -> list[float]:
    """شاخص کل از snapshots — بهترین تلاش؛ در نبودش [] برمی‌گردد."""
    try:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT close_value FROM index_history
                    WHERE name = 'شاخص کل'
                    ORDER BY date ASC LIMIT :lim
                    """
                ),
                {"lim": limit},
            )
        ).fetchall()
        return [float(r[0]) for r in rows if r[0]]
    except Exception:
        return []


# ── Universe ─────────────────────────────────────────────────────────────────


@router.get("/universe", summary="کشف خودکار کل Universe صندوق‌ها (Zero-Config)")
async def get_universe(
    service: FundReadThroughService = Depends(_get_service),
    type: str | None = Query(default=None, description="فیلتر نوع صندوق"),
    market: str | None = Query(default=None, description="tse|ime"),
    search: str | None = Query(default=None, max_length=60),
) -> dict[str, Any]:
    result = await service.get_fund_universe()
    funds = result.data if isinstance(result.data, list) else []
    if type:
        funds = [f for f in funds if f.get("fund_type_hint") == type]
    if market:
        funds = [f for f in funds if f.get("market") == market]
    if search:
        q = search.lower()
        funds = [
            f
            for f in funds
            if q in (f.get("symbol") or "").lower()
            or q in (f.get("name") or "").lower()
            or q in (f.get("isin") or "").lower()
        ]
    return {
        "success": True,
        "data": {
            "funds": funds,
            "total": len(funds),
            "freshness": result.freshness,
            "fetched_from": result.fetched_from,
        },
    }


# ── NAV History ──────────────────────────────────────────────────────────────


@router.get("/{fund_id}/nav-history", summary="تاریخچه NAV با Gap-Filling خودکار")
async def get_nav_history(
    fund_id: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    service: FundReadThroughService = Depends(_get_service),
) -> dict[str, Any]:
    result = await service.get_fund_nav_history(
        _canonical_fund_id(fund_id), start_date, end_date
    )
    return {
        "success": True,
        "data": {
            "fund_id": _canonical_fund_id(fund_id),
            "points": result.data,
            "count": len(result.data) if isinstance(result.data, list) else 0,
            "freshness": result.freshness,
            "fetched_from": result.fetched_from,
        },
    }


# ── Holdings ─────────────────────────────────────────────────────────────────


@router.get("/{fund_id}/holdings", summary="ریز دارایی صندوق (JIT از کدال)")
async def get_holdings(
    fund_id: str,
    period_date: date | None = Query(default=None),
    service: FundReadThroughService = Depends(_get_service),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    result = await service.get_fund_holdings(fid, period_date)
    diffs = await _portfolio_diffs_for(service, fid)
    return {
        "success": True,
        "data": {
            "fund_id": fid,
            "holdings": result.data,
            "count": len(result.data) if isinstance(result.data, list) else 0,
            "freshness": result.freshness,
            "diffs": diffs,
        },
    }


async def _portfolio_diffs_for(
    service: FundReadThroughService, fund_id: str
) -> list[dict[str, Any]]:
    rows = (
        await service.session.execute(
            text(
                """
                SELECT instrument_symbol, current_period_date, previous_period_date,
                       prev_weight_pct, curr_weight_pct, weight_change_pct,
                       prev_market_value, curr_market_value, flow_direction
                FROM fund_portfolio_diffs
                WHERE fund_id = :fid
                ORDER BY ABS(COALESCE(weight_change_pct, 0)) DESC
                LIMIT 50
                """
            ),
            {"fid": fund_id},
        )
    ).fetchall()
    return [
        {
            "symbol": r[0],
            "current_period": str(r[1]) if r[1] else None,
            "previous_period": str(r[2]) if r[2] else None,
            "prev_weight_pct": r[3],
            "curr_weight_pct": r[4],
            "weight_change_pct": r[5],
            "prev_market_value": r[6],
            "curr_market_value": r[7],
            "flow_direction": r[8],
        }
        for r in rows
    ]


# ── Live Valuation ───────────────────────────────────────────────────────────


@router.get("/{fund_id}/valuation", summary="NAV لحظه‌ای تخمینی با درصد پوشش")
async def get_live_valuation(
    fund_id: str,
    service: FundReadThroughService = Depends(_get_service),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    result = await service.get_live_valuation(fid)
    return {
        "success": True,
        "data": {**result.data, "freshness": result.freshness, "fund_id": fid},
    }


# ── Quant Score ──────────────────────────────────────────────────────────────


@router.get("/{fund_id}/score", summary="امتیاز کمی + متریک‌های ریسک/بازده")
async def get_fund_score(
    fund_id: str,
    service: FundReadThroughService = Depends(_get_service),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    points = await _load_nav_points(service.session, fid)
    if len(points) < 30:
        return {
            "success": False,
            "error": "تاریخچه NAV کافی موجود نیست (حداقل ۳۰ نقطه)",
            "data": {"fund_id": fid, "points_available": len(points)},
        }
    benchmark = await _load_benchmark(service.session)
    avg_daily_value = await _avg_daily_value(service.session, fid)
    score = score_fund(
        [p["nav"] for p in points],
        benchmark_series=benchmark or None,
        avg_daily_trade_value=avg_daily_value,
        weights=ScoreWeights(),
    )
    payload = score.to_dict()
    payload["fund_id"] = fid
    payload["engine_version"] = ENGINE_VERSION
    payload["points_used"] = len(points)
    # ذخیره تاریخچه امتیاز (idempotent روزانه)
    await _persist_score(service.session, fid, score)
    return {"success": True, "data": payload}


async def _avg_daily_value(session: AsyncSession, fund_id: str) -> float | None:
    try:
        row = (
            await session.execute(
                text(
                    """
                    SELECT AVG(trade_value) FROM (
                        SELECT trade_value FROM brsapi_symbol_snapshots
                        WHERE symbol = :sym AND trade_value > 0
                        ORDER BY id DESC LIMIT 30
                    ) t
                    """
                ),
                {"sym": fund_id.split(":", 1)[-1]},
            )
        ).first()
        return float(row[0]) if row and row[0] else None
    except Exception:
        return None


async def _persist_score(session: AsyncSession, fund_id: str, score: Any) -> None:
    import json as _json

    try:
        m = score.metrics
        await session.execute(
            text(
                """
                INSERT INTO fund_scores_history
                    (fund_id, score_date, total_score, return_score, risk_score,
                     liquidity_score, stability_score, sharpe, sortino, max_drawdown,
                     calmar, alpha, beta, engine_version, payload_json)
                VALUES (:fid, CURRENT_DATE, :total, :ret, :risk, :liq, :stab,
                        :sharpe, :sortino, :mdd, :calmar, :alpha, :beta, :ver, :payload)
                ON CONFLICT (fund_id, score_date) DO UPDATE SET
                    total_score = EXCLUDED.total_score,
                    sharpe = EXCLUDED.sharpe,
                    payload_json = EXCLUDED.payload_json
                """
            ),
            {
                "fid": fund_id,
                "total": score.total,
                "ret": score.return_component,
                "risk": score.risk_component,
                "liq": score.liquidity_component,
                "stab": score.stability_component,
                "sharpe": m.get("sharpe"),
                "sortino": m.get("sortino"),
                "mdd": m.get("max_drawdown_pct"),
                "calmar": m.get("calmar"),
                "alpha": m.get("alpha_annual_pct"),
                "beta": m.get("beta"),
                "ver": ENGINE_VERSION,
                "payload": _json.dumps(score.to_dict(), ensure_ascii=False, default=str),
            },
        )
        await session.commit()
    except Exception:
        logger.exception("Score persistence failed for %s", fund_id)


# ── Backtest ─────────────────────────────────────────────────────────────────


@router.get("/{fund_id}/backtest", summary="بک‌تست ۳ استراتژی (بدون آینده‌نگری)")
async def get_backtest(
    fund_id: str,
    initial_amount: float = Query(default=100_000_000.0, gt=0),
    monthly_amount: float = Query(default=10_000_000.0, gt=0),
    service: FundReadThroughService = Depends(_get_service),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    points = await _load_nav_points(service.session, fid)
    result = run_all_strategies(
        points, initial_amount=initial_amount, monthly_amount=monthly_amount
    )
    return {
        "success": True,
        "data": {
            "fund_id": fid,
            "points_used": len(points),
            **result,
        },
    }


# ── Rankings ─────────────────────────────────────────────────────────────────


@router.get("/rankings", summary="رتبه‌بندی دوره‌ای صندوق‌ها")
async def get_rankings(
    limit: int = Query(default=50, ge=1, le=200),
    service: FundReadThroughService = Depends(_get_service),
) -> dict[str, Any]:
    rows = (
        await service.session.execute(
            text(
                """
                SELECT h.fund_id, h.score_date, h.total_score, h.sharpe, h.max_drawdown,
                       h.rank_overall, f.symbol, f.name, f.fund_type
                FROM fund_scores_history h
                LEFT JOIN funds f ON f.id = h.fund_id
                WHERE h.score_date = (
                    SELECT MAX(score_date) FROM fund_scores_history WHERE fund_id = h.fund_id
                )
                ORDER BY h.total_score DESC NULLS LAST
                LIMIT :lim
                """
            ),
            {"lim": limit},
        )
    ).fetchall()
    return {
        "success": True,
        "data": {
            "rankings": [
                {
                    "rank": i + 1,
                    "fund_id": r[0],
                    "score_date": str(r[1]) if r[1] else None,
                    "total_score": r[2],
                    "sharpe": r[3],
                    "max_drawdown": r[4],
                    "symbol": r[6],
                    "name": r[7],
                    "fund_type": r[8],
                }
                for i, r in enumerate(rows)
            ]
        },
    }


# ── Portfolio Diffs (ورود/خروج پول) ─────────────────────────────────────────


@router.get("/portfolio-diffs", summary="تغییرات وزنی پرتفوی همه صندوق‌ها")
async def get_portfolio_diffs(
    fund_id: str | None = Query(default=None),
    flow: str | None = Query(default=None, description="in|out|new|exited"),
    limit: int = Query(default=100, ge=1, le=500),
    service: FundReadThroughService = Depends(_get_service),
) -> dict[str, Any]:
    sql = """
        SELECT d.fund_id, f.symbol, d.instrument_symbol, d.current_period_date,
               d.weight_change_pct, d.flow_direction
        FROM fund_portfolio_diffs d
        LEFT JOIN funds f ON f.id = d.fund_id
        WHERE 1=1
    """
    params: dict[str, Any] = {"lim": limit}
    if fund_id:
        sql += " AND d.fund_id = :fid"
        params["fid"] = _canonical_fund_id(fund_id)
    if flow:
        sql += " AND d.flow_direction = :flow"
        params["flow"] = flow
    sql += " ORDER BY ABS(COALESCE(d.weight_change_pct, 0)) DESC LIMIT :lim"
    rows = (await service.session.execute(text(sql), params)).fetchall()
    return {
        "success": True,
        "data": {
            "diffs": [
                {
                    "fund_id": r[0],
                    "fund_symbol": r[1],
                    "instrument_symbol": r[2],
                    "period": str(r[3]) if r[3] else None,
                    "weight_change_pct": r[4],
                    "flow_direction": r[5],
                }
                for r in rows
            ]
        },
    }


# ── Monitoring (P1) ──────────────────────────────────────────────────────────


@router.get("/monitoring", summary="متریک‌های پایش ماژول صندوق‌ها")
async def get_monitoring(
    service: FundReadThroughService = Depends(_get_service),
) -> dict[str, Any]:
    s = service.session
    quarantine_count = (
        await s.execute(text("SELECT COUNT(*) FROM fund_ingestion_quarantine WHERE reviewed = FALSE"))
    ).scalar() or 0
    universe_count = (await s.execute(text("SELECT COUNT(*) FROM funds WHERE is_etf = TRUE"))).scalar() or 0
    nav_rows = (await s.execute(text("SELECT COUNT(*) FROM fund_nav_history"))).scalar() or 0
    holdings_rows = (await s.execute(text("SELECT COUNT(*) FROM fund_holdings"))).scalar() or 0
    scores_rows = (await s.execute(text("SELECT COUNT(*) FROM fund_scores_history"))).scalar() or 0
    quote_stale = (
        await s.execute(
            text(
                """
                SELECT COUNT(*) FROM fund_market_quotes_cache
                WHERE quoted_at < now() - INTERVAL '5 minutes'
                """
            )
        )
    ).scalar() or 0
    return {
        "success": True,
        "data": {
            "universe_count": universe_count,
            "nav_history_rows": nav_rows,
            "holdings_rows": holdings_rows,
            "scores_rows": scores_rows,
            "quarantine_unreviewed": quarantine_count,
            "stale_quotes": quote_stale,
            "engine_version": ENGINE_VERSION,
        },
    }
