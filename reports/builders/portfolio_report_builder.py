from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from domain.portfolios.portfolio import Portfolio

logger = get_logger(__name__)


class PortfolioReportBuilder:
    async def build(self, portfolio: Portfolio) -> Result[dict[str, Any]]:
        positions = []
        for position in portfolio.positions:
            positions.append(
                {
                    "symbol": getattr(position, "symbol", ""),
                    "instrument_id": getattr(position, "instrument_id", ""),
                    "quantity": getattr(position, "quantity", 0),
                    "avg_price": getattr(position, "average_price", 0),
                    "current_price": getattr(position, "current_price", 0),
                    "cost_basis": getattr(position, "average_price", 0) * getattr(position, "quantity", 0),
                    "market_value": getattr(position, "current_price", 0) * getattr(position, "quantity", 0),
                    "unrealized_pnl": (getattr(position, "current_price", 0) - getattr(position, "average_price", 0))
                    * getattr(position, "quantity", 0),
                    "weight": 0.0,
                }
            )
        total_value = sum(p.get("market_value", 0) for p in positions)
        if total_value > 0:
            for p in positions:
                p["weight"] = (p["market_value"] / total_value) * 100
        total_cost = sum(p.get("cost_basis", 0) for p in positions)
        data: dict[str, Any] = {
            "title": f"Portfolio Report: {portfolio.name if hasattr(portfolio, 'name') else 'N/A'}",
            "report_type": "portfolio",
            "generated_at": datetime.now(UTC).isoformat(),
            "portfolio_id": portfolio.id,
            "portfolio_name": getattr(portfolio, "name", ""),
            "total_value": total_value,
            "total_cost": total_cost,
            "total_unrealized_pnl": total_value - total_cost,
            "position_count": len(positions),
            "positions": positions,
        }
        return Result.ok(data)
