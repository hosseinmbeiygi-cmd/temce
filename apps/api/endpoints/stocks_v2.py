"""📈 Stocks V2 API — قرارداد ۹ تب فرانت‌اند (بخش ۴).

نسخه‌بندی مستقل زیر ``/stocks/v2`` — endpointهای فعلی دست‌نخورده.

تب‌↔Endpoint:
  ۱ Live Tape        → GET /stocks/v2/{symbol}/tape
  ۲ Technical Radar  → GET /stocks/v2/{symbol}/indicators
  ۳ Peers Matrix     → GET /stocks/v2/{symbol}/peers
  ۴ Dossier          → GET /stocks/v2/{symbol}/dossier
  ۵ Codal            → GET /stocks/v2/{symbol}/codal
  ۶ News/Sentiment   → GET /stocks/v2/{symbol}/news
  ۷ History+CSV      → GET /stocks/v2/{symbol}/history  |  /history/export.csv
  ۸ Ticks/VolumeProfile → GET /stocks/v2/{symbol}/volume-profile
  ۹ Market Pulse     → GET /stocks/v2/market-pulse
  کارت سیگنال        → GET /stocks/v2/{symbol}/signal
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from core.logging import get_logger
from services.stock_read_through import StockReadThroughService

logger = get_logger(__name__)
router = APIRouter()


def _svc(session: AsyncSession = Depends(get_db_session)) -> StockReadThroughService:
    return StockReadThroughService(session=session)


# ── تب ۱: Tape + ماتریس تابلوخوانی ──


@router.get("/{symbol}/tape", summary="تابلوی زنده + ماتریس تابلوخوانی (تب ۱)")
async def get_tape(symbol: str, svc: StockReadThroughService = Depends(_svc)) -> dict[str, Any]:
    tape = await svc.get_live_tape(symbol)
    matrix = await svc.get_tape_reading_matrix(symbol)
    return {
        "success": True,
        "data": {
            "tape": tape,
            "matrix": matrix,
            "freshness": tape.get("freshness", "stale"),
        },
    }


# ── تب ۲: Indicators ──


@router.get("/{symbol}/indicators", summary="رادار تکنیکال خودکار (تب ۲)")
async def get_indicators(symbol: str, svc: StockReadThroughService = Depends(_svc)) -> dict[str, Any]:
    data = await svc.get_indicators(symbol)
    return {"success": True, "data": data}


# ── کارت سیگنال ──


@router.get("/{symbol}/signal", summary="کارت تصمیم‌گیری کوانت (۵ لایه + مدیریت ریسک)")
async def get_signal(symbol: str, svc: StockReadThroughService = Depends(_svc)) -> dict[str, Any]:
    data = await svc.get_full_signal(symbol)
    # Persist (idempotent روزانه)
    try:
        await _persist_signal(svc.session, symbol, data)
    except Exception:
        logger.exception("Signal persist failed for %s", symbol)
    return {"success": True, "data": data}


async def _persist_signal(session: AsyncSession, symbol: str, data: dict[str, Any]) -> None:
    from sqlalchemy import text as _text

    targets = data.get("targets") or [None, None, None]
    await session.execute(
        _text(
            """
            INSERT INTO stock_quant_signals (
                symbol, signal_date, action, composite_score,
                tape_score, tech_score, fund_score, peer_score, macro_score,
                entry_low, entry_high, stop_loss, target_1, target_2, target_3,
                risk_reward, kelly_fraction, position_size_pct, market_regime,
                reasons_pro, reasons_con, engine_version, payload_json)
            VALUES (:symbol, CURRENT_DATE, :action, :composite,
                    :tape, :tech, :fund, :peer, :macro,
                    :entry_low, :entry_high, :stop, :t1, :t2, :t3,
                    :rr, :kelly, :pos, :regime, :pro, :con, :ver, :payload)
            ON CONFLICT (symbol, signal_date) DO UPDATE SET
                action = EXCLUDED.action,
                composite_score = EXCLUDED.composite_score,
                payload_json = EXCLUDED.payload_json
            """
        ),
        {
            "symbol": symbol,
            "action": data.get("action"),
            "composite": data.get("composite_score"),
            "tape": data["layer_scores"].get("tape"),
            "tech": data["layer_scores"].get("tech"),
            "fund": data["layer_scores"].get("fund"),
            "peer": data["layer_scores"].get("peer"),
            "macro": data["layer_scores"].get("macro"),
            "entry_low": data.get("entry", [None, None])[0],
            "entry_high": data.get("entry", [None, None])[1],
            "stop": data.get("stop_loss"),
            "t1": targets[0],
            "t2": targets[1],
            "t3": targets[2],
            "rr": data.get("risk_reward"),
            "kelly": data.get("kelly_fraction"),
            "pos": data.get("position_size_pct"),
            "regime": data.get("market_regime"),
            "pro": "; ".join(data.get("reasons_pro") or []),
            "con": "; ".join(data.get("reasons_con") or []),
            "ver": data.get("engine_version"),
            "payload": json.dumps(data, ensure_ascii=False, default=str),
        },
    )
    await session.commit()


# ── تب ۳: Peers ──


@router.get("/{symbol}/peers", summary="ماتریس صنعت و هم‌گروهی‌ها (تب ۳)")
async def get_peers(
    symbol: str,
    limit: int = Query(default=30, ge=1, le=100),
    svc: StockReadThroughService = Depends(_svc),
) -> dict[str, Any]:
    industry_row = (
        await svc.session.execute(
            text("SELECT industry_name FROM symbols WHERE code = :sym LIMIT 1"),
            {"sym": symbol},
        )
    ).first()
    industry = industry_row[0] if industry_row and industry_row[0] else None
    if industry is None:
        return {"success": True, "data": {"industry": None, "peers": []}}

    rows = (
        await svc.session.execute(
            text(
                """
                SELECT s.code, s.name, t.last_price, t.close_price, t.close_change_pct,
                       t.trade_value, t.trade_count, t.buy_real_count, t.sell_real_count,
                       t.buy_real_value, t.sell_real_value, t.trade_volume, t.base_volume
                FROM symbols s
                LEFT JOIN stock_live_tape t ON t.symbol = s.code
                WHERE s.industry_name = :ind
                ORDER BY t.trade_value DESC NULLS LAST
                LIMIT :lim
                """
            ),
            {"ind": industry, "lim": limit},
        )
    ).fetchall()

    peers = []
    for r in rows:
        power = None
        if r[7] and r[8] and r[9] and r[10]:
            avg_buy = r[9] / r[7]
            avg_sell = r[10] / r[8]
            if avg_sell > 0:
                power = round(avg_buy / avg_sell, 2)
        peers.append(
            {
                "symbol": r[0],
                "name": r[1],
                "last_price": r[2],
                "close_price": r[3],
                "change_pct": r[4],
                "trade_value": r[5],
                "percapita_buy_mnt": (r[9] / (r[7] * 10**7)) if (r[9] and r[7]) else None,
                "buyer_power": power,
                "base_volume_ratio": (r[11] / r[12]) if (r[11] and r[12]) else None,
            }
        )
    return {"success": True, "data": {"industry": industry, "peers": peers}}


# ── تب ۴: Dossier ──


@router.get("/{symbol}/dossier", summary="شناسنامه جامع سهم (تب ۴)")
async def get_dossier(symbol: str, svc: StockReadThroughService = Depends(_svc)) -> dict[str, Any]:
    s = svc.session
    identity = (
        await s.execute(
            text(
                """
                SELECT code, name, isin, industry_name, market_segment, trading_state,
                       base_volume, free_float_pct
                FROM symbols WHERE code = :sym LIMIT 1
                """
            ),
            {"sym": symbol},
        )
    ).first()
    shareholders = (
        await s.execute(
            text(
                """
                SELECT shareholder_name, percent, change
                FROM brsapi_shareholder_records
                WHERE symbol = :sym
                ORDER BY percent DESC NULLS LAST LIMIT 15
                """
            ),
            {"sym": symbol},
        )
    ).fetchall()
    monthly = (
        await s.execute(
            text(
                """
                SELECT jalali_year, jalali_month, SUM(sales_amount) AS amount
                FROM stock_monthly_sales_production
                WHERE symbol = :sym
                GROUP BY jalali_year, jalali_month
                ORDER BY jalali_year DESC, jalali_month DESC LIMIT 12
                """
            ),
            {"sym": symbol},
        )
    ).fetchall()
    return {
        "success": True,
        "data": {
            "identity": dict(zip(
                ("symbol", "name", "isin", "industry", "market_segment", "trading_state",
                 "base_volume", "free_float_pct"),
                identity or [],
                strict=False,
            )) if identity else None,
            "major_shareholders": [
                {"name": r[0], "percent": r[1], "change": r[2]} for r in shareholders
            ],
            "monthly_sales": [
                {"period": f"{r[0]}/{r[1]:02d}", "amount": r[2]} for r in monthly
            ],
        },
    }


# ── تب ۵: Codal ──


@router.get("/{symbol}/codal", summary="اطلاعیه‌ها و فروش ماهانه کدال (تب ۵)")
async def get_codal(
    symbol: str,
    category: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    svc: StockReadThroughService = Depends(_svc),
) -> dict[str, Any]:
    s = svc.session
    try:
        rows = (
            await s.execute(
                text(
                    """
                    SELECT title, publish_date, letter_id FROM brsapi_codal_announcements
                    WHERE symbol = :sym
                    ORDER BY publish_date DESC LIMIT :lim
                    """
                ),
                {"sym": symbol, "lim": limit},
            )
        ).fetchall()
    except Exception:
        rows = []
    monthly = (
        await s.execute(
            text(
                """
                SELECT jalali_year, jalali_month, product_name, sales_amount,
                       sales_volume, unit_price, sales_mom_pct, sales_yoy_pct, is_all_time_high
                FROM stock_monthly_sales_production
                WHERE symbol = :sym
                ORDER BY jalali_year DESC, jalali_month DESC LIMIT 24
                """
            ),
            {"sym": symbol},
        )
    ).fetchall()
    return {
        "success": True,
        "data": {
            "announcements": [
                {"title": r[0], "date": str(r[1]) if r[1] else None, "letter_id": r[2]}
                for r in rows
            ],
            "monthly_sales": [
                {
                    "period": f"{r[0]}/{r[1]:02d}",
                    "product": r[2],
                    "sales_amount": r[3],
                    "sales_volume": r[4],
                    "unit_price": r[5],
                    "mom_pct": r[6],
                    "yoy_pct": r[7],
                    "all_time_high": r[8],
                }
                for r in monthly
            ],
        },
    }


# ── تب ۶: News + Sentiment ──


@router.get("/{symbol}/news", summary="اخبار و سنتیمنت (تب ۶)")
async def get_news(
    symbol: str,
    limit: int = Query(default=30, ge=1, le=100),
    svc: StockReadThroughService = Depends(_svc),
) -> dict[str, Any]:
    rows = (
        await svc.session.execute(
            text(
                """
                SELECT title, source, published_at, sentiment, sentiment_score, impact_tag
                FROM stock_news_sentiment
                WHERE symbol = :sym OR industry = (
                    SELECT industry_name FROM symbols WHERE code = :sym LIMIT 1
                )
                ORDER BY published_at DESC NULLS LAST LIMIT :lim
                """
            ),
            {"sym": symbol, "lim": limit},
        )
    ).fetchall()
    return {
        "success": True,
        "data": {
            "news": [
                {
                    "title": r[0],
                    "source": r[1],
                    "published_at": str(r[2]) if r[2] else None,
                    "sentiment": r[3],
                    "sentiment_score": r[4],
                    "impact_tag": r[5],
                }
                for r in rows
            ]
        },
    }


# ── تب ۷: History + CSV export ──


@router.get("/{symbol}/history", summary="تاریخچه قیمت روزانه (تب ۷)")
async def get_history(
    symbol: str,
    adjusted: bool = Query(default=False, description="تعدیل‌شده"),
    limit: int = Query(default=250, ge=1, le=2500),
    svc: StockReadThroughService = Depends(_svc),
) -> dict[str, Any]:
    candles = await svc._load_daily_candles(symbol, limit)
    return {"success": True, "data": {"adjusted": adjusted, "candles": candles}}


@router.get("/{symbol}/history/export.csv", summary="خروجی CSV تاریخچه (تب ۷)")
async def export_history_csv(
    symbol: str,
    svc: StockReadThroughService = Depends(_svc),
) -> StreamingResponse:
    candles = await svc._load_daily_candles(symbol, 2500)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "open", "high", "low", "close", "volume", "value"])
    for c in candles:
        writer.writerow([c["date"], c["open"], c["high"], c["low"], c["close"], c["volume"], c["value"]])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={symbol}_history.csv"},
    )


# ── تب ۸: Volume Profile ──


@router.get("/{symbol}/volume-profile", summary="پروفایل حجم درون‌روزی + POC (تب ۸)")
async def get_volume_profile(
    symbol: str,
    bins: int = Query(default=20, ge=5, le=60),
    svc: StockReadThroughService = Depends(_svc),
) -> dict[str, Any]:
    rows = (
        await svc.session.execute(
            text(
                """
                SELECT price, volume FROM brsapi_intraday_trades
                WHERE symbol = :sym AND trade_date = CURRENT_DATE
                  AND price > 0 AND volume > 0
                """
            ),
            {"sym": symbol},
        )
    ).fetchall()
    if not rows:
        return {"success": True, "data": {"available": False, "profile": []}}
    prices = [float(r[0]) for r in rows]
    volumes = [float(r[1]) for r in rows]
    lo, hi = min(prices), max(prices)
    if hi <= lo:
        return {"success": True, "data": {"available": False, "profile": []}}
    width = (hi - lo) / bins
    buckets = [0.0] * bins
    for p, v in zip(prices, volumes, strict=False):
        idx = min(int((p - lo) / width), bins - 1)
        buckets[idx] += v
    poc_idx = max(range(bins), key=lambda i: buckets[i])
    return {
        "success": True,
        "data": {
            "available": True,
            "poc_price": round(lo + (poc_idx + 0.5) * width, 0),
            "profile": [
                {"price_low": round(lo + i * width, 0), "price_high": round(lo + (i + 1) * width, 0), "volume": buckets[i]}
                for i in range(bins)
            ],
        },
    }


# ── تب ۹: Market Pulse ──


@router.get("/market-pulse", summary="نبض کلان بازار (تب ۹)")
async def get_market_pulse(svc: StockReadThroughService = Depends(_svc)) -> dict[str, Any]:
    s = svc.session
    macro = (
        await s.execute(
            text(
                """
                SELECT indicator_date, total_retail_value, queue_buy_value,
                       queue_sell_value, market_regime, usd_nima, usd_free
                FROM market_macro_indicators
                ORDER BY indicator_date DESC LIMIT 1
                """
            )
        )
    ).first()
    indices = (
        await s.execute(
            text(
                """
                SELECT name, close_value FROM indices LIMIT 5
                """
            )
        )
    ).fetchall()
    heatmap = (
        await s.execute(
            text(
                """
                SELECT s.industry_name, SUM(t.trade_value) AS total_value,
                       AVG(t.close_change_pct) AS avg_change
                FROM stock_live_tape t
                JOIN symbols s ON s.code = t.symbol
                WHERE s.industry_name IS NOT NULL
                GROUP BY s.industry_name
                ORDER BY total_value DESC NULLS LAST LIMIT 12
                """
            )
        )
    ).fetchall()
    return {
        "success": True,
        "data": {
            "macro": dict(zip(
                ("date", "retail_value", "queue_buy", "queue_sell", "regime", "usd_nima", "usd_free"),
                macro or [],
                strict=False,
            )) if macro else None,
            "indices": [{"name": r[0], "value": r[1]} for r in indices],
            "industry_heatmap": [
                {"industry": r[0], "value": r[1], "avg_change_pct": r[2]}
                for r in heatmap
            ],
        },
    }


# ── Monitoring ──


@router.get("/monitoring", summary="سلامت ماژول سهام (P1)")
async def stocks_monitoring(svc: StockReadThroughService = Depends(_svc)) -> dict[str, Any]:
    s = svc.session
    try:
        tape_fresh = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM stock_live_tape WHERE quoted_at > now() - INTERVAL '10 seconds'"
                )
            )
        ).scalar() or 0
        signals_today = (
            await s.execute(
                text("SELECT COUNT(*) FROM stock_quant_signals WHERE signal_date = CURRENT_DATE")
            )
        ).scalar() or 0
        return {"success": True, "data": {"fresh_tapes": tape_fresh, "signals_today": signals_today}}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="monitoring unavailable") from exc
