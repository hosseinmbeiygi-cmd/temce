#!/usr/bin/env python
"""Test Alpha API logic directly against the database."""

from __future__ import annotations

import asyncio
import math
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings


def compute_alpha_metrics(prices: list[float]) -> dict:
    if len(prices) < 2:
        return {"sharpe": 0.0, "returns": 0.0, "volatility": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "trades": 0}

    returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
    total_return = (prices[-1] - prices[0]) / prices[0] * 100

    avg_r = sum(returns) / len(returns)
    variance = sum((r - avg_r) ** 2 for r in returns) / len(returns)
    daily_vol = math.sqrt(variance) if variance > 0 else 0
    annual_vol = daily_vol * math.sqrt(252) * 100 if daily_vol > 0 else 0
    sharpe = (avg_r / daily_vol * math.sqrt(252)) if daily_vol > 0 else 0.0

    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = (peak - p) / peak
        if dd > max_dd:
            max_dd = dd

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


async def main():
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        limit = 20

        # ── Try quotes first ──
        print("=== Phase 1: Fetching symbols from quotes table ===")
        result = await conn.execute(
            text("""
            SELECT symbol, COUNT(DISTINCT date) as cnt
            FROM quotes
            WHERE price_close IS NOT NULL AND price_close > 0
              AND date IS NOT NULL
            GROUP BY symbol
            HAVING COUNT(DISTINCT date) >= 10
            ORDER BY cnt DESC
            LIMIT :limit
        """),
            {"limit": limit},
        )
        symbols = [(row[0], row[1]) for row in result.fetchall()]
        print(f"Found {len(symbols)} symbols in quotes table")
        print(f"Top symbols: {[s[0] for s in symbols[:5]]}")

        if not symbols:
            print("\n=== Phase 2: Fallback to trades table ===")
            result = await conn.execute(
                text("""
                SELECT symbol, COUNT(DISTINCT date) as cnt
                FROM trades
                WHERE price IS NOT NULL AND price > 0
                  AND date IS NOT NULL
                GROUP BY symbol
                HAVING COUNT(DISTINCT date) >= 10
                ORDER BY cnt DESC
                LIMIT :limit
            """),
                {"limit": limit},
            )
            symbols = [(row[0], row[1]) for row in result.fetchall()]
            print(f"Found {len(symbols)} symbols in trades table")
            print(f"Top: {[s[0] for s in symbols[:5]]}")

        print(f"\n=== Computing Alpha Metrics for {len(symbols)} symbols ===")
        strategies = []

        for symbol, cnt in symbols:
            # Try quotes first
            price_result = await conn.execute(
                text("""
                SELECT DISTINCT ON (date) price_close
                FROM quotes
                WHERE symbol = :symbol AND price_close IS NOT NULL AND price_close > 0
                  AND date IS NOT NULL
                ORDER BY date ASC, time DESC NULLS LAST
            """),
                {"symbol": symbol},
            )
            prices = [row[0] for row in price_result.fetchall()]

            # Fallback to trades
            if not prices:
                price_result = await conn.execute(
                    text("""
                    SELECT DISTINCT ON (date) date, price
                    FROM trades
                    WHERE symbol = :symbol AND price IS NOT NULL AND price > 0
                      AND date IS NOT NULL
                    ORDER BY date ASC, time DESC
                """),
                    {"symbol": symbol},
                )
                prices = [row[1] for row in price_result.fetchall()]

            if len(prices) < 2:
                continue

            metrics = compute_alpha_metrics(prices)

            if metrics["sharpe"] >= 1.5:
                status = "active"
            elif metrics["sharpe"] >= 0.5:
                status = "paper"
            else:
                status = "disabled"

            strategies.append(
                {
                    "name": symbol,
                    "days": cnt,
                    "sharpe": metrics["sharpe"],
                    "returns": metrics["returns"],
                    "volatility": metrics["volatility"],
                    "maxDrawdown": metrics["max_drawdown"],
                    "winRate": metrics["win_rate"],
                    "trades": metrics["trades"],
                    "status": status,
                }
            )

        strategies.sort(key=lambda s: s["sharpe"], reverse=True)

        print(f"\n{'=' * 80}")
        print(f"Alpha API Results: {len(strategies)} strategies found")
        print(f"{'=' * 80}")
        print(
            f"{'Symbol':<12} {'Sharpe':>7} {'Return%':>8} {'Vol%':>8} {'DD%':>8} {'Win%':>7} {'Days':>6} {'Status':<10}"
        )
        print(f"{'-' * 12} {'-' * 7} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 7} {'-' * 6} {'-' * 10}")
        for s in strategies:
            print(
                f"{s['name']:<12} {s['sharpe']:>7.2f} {s['returns']:>8.2f} {s['volatility']:>8.2f} {s['maxDrawdown']:>8.2f} {s['winRate']:>7.1f} {s['days']:>6} {s['status']:<10}"
            )

        print(f"\n{'=' * 80}")
        active = [s for s in strategies if s["status"] == "active"]
        paper = [s for s in strategies if s["status"] == "paper"]
        disabled = [s for s in strategies if s["status"] == "disabled"]
        print(f"Active (Sharpe>=1.5): {len(active)}")
        print(f"Paper (Sharpe>=0.5):  {len(paper)}")
        print(f"Disabled (else):      {len(disabled)}")

        if active:
            print("\nBest performers (top 5 active):")
            for s in active[:5]:
                print(f"  {s['name']:<12} Sharpe={s['sharpe']:.2f} Return={s['returns']:.1f}%")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

