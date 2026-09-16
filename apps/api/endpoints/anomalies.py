from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.error_handlers import safe_error_message
from core.database import get_session
from core.db_utils import safe_row_str
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()


def _detect_anomalies(
    symbol: str,
    closes: list[float],
    volumes: list[int | float],
    dates: list[str],
    price_threshold: float = 2.5,
    volume_threshold: float = 2.0,
) -> list[dict[str, Any]]:
    """Detect price and volume anomalies using Z-score analysis."""
    if len(closes) < 20:
        return []

    anomalies: list[dict[str, Any]] = []

    # ── Price anomalies ──
    mean_p = statistics.mean(closes)
    stdev_p = statistics.stdev(closes) if len(closes) > 1 else 0.0

    if stdev_p > 0:
        for _i, (price, vol, dt) in enumerate(zip(closes, volumes, dates, strict=False)):
            z_price = (price - mean_p) / stdev_p

            # Price spike
            if abs(z_price) > price_threshold:
                anomaly_type = "price_spike_up" if z_price > 0 else "price_spike_down"
                severity = "high" if abs(z_price) > price_threshold * 1.5 else "medium"
                anomalies.append(
                    {
                        "symbol": symbol,
                        "type": anomaly_type,
                        "severity": severity,
                        "date": dt,
                        "value": price,
                        "expected": round(mean_p, 2),
                        "z_score": round(z_price, 2),
                        "volume": int(vol) if vol else 0,
                        "description": f"قیمت {int(price):,} — {abs(z_price):.1f}σ انحراف از میانگین {int(mean_p):,}",
                    }
                )

    # ── Volume anomalies ──
    if len(volumes) >= 20 and any(v > 0 for v in volumes):
        positive_vols = [float(v) for v in volumes if v and v > 0]
        if len(positive_vols) >= 10:
            mean_v = statistics.mean(positive_vols)
            stdev_v = statistics.stdev(positive_vols) if len(positive_vols) > 1 else 0.0
            if stdev_v > 0:
                for _i, (price, vol, dt) in enumerate(zip(closes, volumes, dates, strict=False)):
                    if not vol or vol <= 0:
                        continue
                    z_vol = (float(vol) - mean_v) / stdev_v
                    if z_vol > volume_threshold:
                        anomalies.append(
                            {
                                "symbol": symbol,
                                "type": "volume_spike",
                                "severity": "high" if z_vol > volume_threshold * 1.5 else "medium",
                                "date": dt,
                                "value": float(vol),
                                "expected": round(mean_v, 0),
                                "z_score": round(z_vol, 2),
                                "price": price,
                                "description": f"حجم {int(vol):,} — {z_vol:.1f}σ بالاتر از میانگین {int(mean_v):,}",
                            }
                        )

    return anomalies


@router.get("", summary="Anomaly Detection", description="Detect price and volume anomalies from the quotes table")
async def get_anomalies(
    limit: int = Query(30, ge=5, le=200, description="Days of lookback"),
    price_threshold: float = Query(2.5, ge=1.0, le=5.0, description="Z-score threshold for price anomalies"),
    volume_threshold: float = Query(2.0, ge=1.0, le=5.0, description="Z-score threshold for volume anomalies"),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    try:
        # Get symbols with enough data
        end_dt = date.today()
        start_dt = end_dt - timedelta(days=limit * 2)

        result = await session.execute(
            text("""
            SELECT symbol, COUNT(*) as cnt
            FROM quotes
            WHERE date >= :start AND price_close IS NOT NULL AND price_close > 0
            GROUP BY symbol
            HAVING COUNT(*) >= 20
            ORDER BY cnt DESC
            LIMIT 50
        """),
            {"start": start_dt.isoformat()},
        )
        symbols = [row[0] for row in result.fetchall()]

        all_anomalies: list[dict[str, Any]] = []
        total_symbols = len(symbols)
        symbols_with_data = 0
        symbols_with_anomalies = 0

        for symbol in symbols:
            try:
                rows_result = await session.execute(
                    text("""
                    SELECT price_close, volume, date
                    FROM quotes
                    WHERE symbol = :sym AND date >= :start AND price_close IS NOT NULL AND price_close > 0
                    ORDER BY date ASC
                """),
                    {"sym": symbol, "start": start_dt.isoformat()},
                )
                rows = rows_result.fetchall()

                if not rows:
                    continue
                symbols_with_data += 1

                closes = [float(row[0]) for row in rows]
                volumes = [int(row[1] or 0) for row in rows]
                dates = [safe_row_str(row, idx=2) for row in rows]

                anomalies = _detect_anomalies(
                    symbol=symbol,
                    closes=closes,
                    volumes=volumes,
                    dates=dates,
                    price_threshold=price_threshold,
                    volume_threshold=volume_threshold,
                )

                if anomalies:
                    symbols_with_anomalies += 1
                    all_anomalies.extend(anomalies)
            except Exception:
                logger.warning("Failed to process anomalies for %s", symbol, exc_info=True)
                continue

        # Sort by severity (high first), then by z-score magnitude
        severity_order = {"high": 0, "medium": 1, "low": 2}
        all_anomalies.sort(key=lambda a: (severity_order.get(a["severity"], 9), -abs(a["z_score"])))

        high_count = sum(1 for a in all_anomalies if a["severity"] == "high")
        medium_count = sum(1 for a in all_anomalies if a["severity"] == "medium")
        price_count = sum(1 for a in all_anomalies if a["type"] == "price_spike_up" or a["type"] == "price_spike_down")
        volume_count = sum(1 for a in all_anomalies if a["type"] == "volume_spike")

        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "items": all_anomalies,
                "total": len(all_anomalies),
                "summary": {
                    "total_symbols_scanned": total_symbols,
                    "symbols_with_data": symbols_with_data,
                    "symbols_with_anomalies": symbols_with_anomalies,
                    "high_severity": high_count,
                    "medium_severity": medium_count,
                    "price_anomalies": price_count,
                    "volume_anomalies": volume_count,
                },
                "config": {
                    "price_threshold": price_threshold,
                    "volume_threshold": volume_threshold,
                    "lookback_days": limit,
                },
            },
        )
    except Exception as exc:
        logger.exception("Anomaly detection failed")
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"items": [], "total": 0, "summary": {}},
            error={"message": safe_error_message(exc)},
        )
