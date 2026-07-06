from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()


def _compute_alpha_metrics(prices: list[float]) -> dict[str, Any]:
    """Compute alpha metrics from a list of closing prices."""
    if len(prices) < 2:
        return {"sharpe": 0.0, "returns": 0.0, "volatility": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "trades": 0}

    # Daily returns
    returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]

    # Total return
    total_return = (prices[-1] - prices[0]) / prices[0] * 100

    # Volatility (annualized)
    avg_r = sum(returns) / len(returns)
    variance = sum((r - avg_r) ** 2 for r in returns) / len(returns)
    daily_vol = math.sqrt(variance)
    annual_vol = daily_vol * math.sqrt(252) * 100

    # Sharpe ratio (risk-free = 0)
    sharpe = (avg_r / daily_vol * math.sqrt(252)) if daily_vol > 0 else 0.0

    # Max drawdown
    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = (peak - p) / peak
        if dd > max_dd:
            max_dd = dd

    # Win rate
    wins = sum(1 for r in returns if r > 0)
    win_rate = wins / len(returns) * 100 if returns else 0

    return {
        "sharpe": round(sharpe, 2),
        "returns": round(total_return, 2),
        "volatility": round(annual_vol, 2),
        "max_drawdown": round(-max_dd * 100, 2),
        "win_rate": round(win_rate, 1),
        "trades": len(returns),
    }


@router.get("", summary="Alpha strategies from real data", description="Compute alpha metrics from actual historical prices")
async def list_alphas(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    # Get symbols with historical data, ordered by most data
    result = await session.execute(text("""
        SELECT symbol, COUNT(*) as cnt
        FROM brsapi_historical_daily
        WHERE price_close IS NOT NULL AND price_close > 0
        GROUP BY symbol
        HAVING COUNT(*) >= 30
        ORDER BY cnt DESC
        LIMIT :limit
    """), {"limit": limit})
    symbols = [(row[0], row[1]) for row in result.fetchall()]

    strategies = []
    for symbol, cnt in symbols:
        # Get closing prices ordered by date
        price_result = await session.execute(text("""
            SELECT price_close FROM brsapi_historical_daily
            WHERE symbol = :symbol AND price_close IS NOT NULL AND price_close > 0
            ORDER BY date ASC
        """), {"symbol": symbol})
        prices = [row[0] for row in price_result.fetchall()]

        metrics = _compute_alpha_metrics(prices)

        # Determine status based on sharpe
        if metrics["sharpe"] >= 1.5:
            status = "active"
        elif metrics["sharpe"] >= 0.5:
            status = "paper"
        else:
            status = "disabled"

        strategies.append({
            "id": f"alpha-{symbol}",
            "name": symbol,
            "version": f"v1 ({cnt} days)",
            "sharpe": metrics["sharpe"],
            "returns": metrics["returns"],
            "volatility": metrics["volatility"],
            "maxDrawdown": metrics["max_drawdown"],
            "winRate": metrics["win_rate"],
            "trades": metrics["trades"],
            "status": status,
            "description": f"تحلیل بازده {symbol} بر اساس {cnt} روز داده تاریخی",
        })

    # Sort by sharpe descending
    strategies.sort(key=lambda s: s["sharpe"], reverse=True)

    return ApiResponse[dict[str, Any]](
        success=True,
        data={"items": strategies, "total": len(strategies)},
    )
