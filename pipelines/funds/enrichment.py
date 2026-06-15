from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def enrich_fund_with_holdings(fund: dict[str, Any], holdings: list[dict[str, Any]]) -> dict[str, Any]:
    total_market_value = sum(h.get("market_value", 0) for h in holdings)
    equity_value = sum(h.get("market_value", 0) for h in holdings if h.get("asset_type") == "equity")
    bond_value = sum(h.get("market_value", 0) for h in holdings if h.get("asset_type") == "bond")
    cash_value = sum(h.get("market_value", 0) for h in holdings if h.get("asset_type") == "cash")
    commodity_value = sum(h.get("market_value", 0) for h in holdings if h.get("asset_type") == "commodity")
    other_value = total_market_value - equity_value - bond_value - cash_value - commodity_value

    enriched = dict(fund)
    extra = dict(enriched.get("extra", {}))
    extra["holdings_count"] = len(holdings)
    extra["total_market_value"] = total_market_value
    extra["asset_allocation"] = {
        "equity": round(equity_value / total_market_value * 100, 2) if total_market_value > 0 else 0.0,
        "bond": round(bond_value / total_market_value * 100, 2) if total_market_value > 0 else 0.0,
        "cash": round(cash_value / total_market_value * 100, 2) if total_market_value > 0 else 0.0,
        "commodity": round(commodity_value / total_market_value * 100, 2) if total_market_value > 0 else 0.0,
        "other": round(other_value / total_market_value * 100, 2) if total_market_value > 0 else 0.0,
    }
    top_holdings = sorted(holdings, key=lambda h: h.get("weight_pct", 0), reverse=True)[:5]
    extra["top_holdings"] = [
        {"symbol": h.get("symbol", ""), "weight_pct": h.get("weight_pct", 0), "asset_type": h.get("asset_type", "")}
        for h in top_holdings
    ]
    enriched["extra"] = extra
    return enriched


def calculate_fund_metrics(nav_history: list[dict[str, Any]]) -> dict[str, Any]:
    if not nav_history:
        return {
            "return_pct": 0.0,
            "annualized_return_pct": 0.0,
            "volatility_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
        }

    sorted_nav = sorted(nav_history, key=lambda n: n.get("nav_date", ""))
    returns = [n.get("daily_return_pct", 0.0) for n in sorted_nav]

    total_return = 0.0
    if len(sorted_nav) >= 2:
        first_nav = sorted_nav[0].get("nav", 0)
        last_nav = sorted_nav[-1].get("nav", 0)
        if first_nav > 0:
            total_return = (last_nav - first_nav) / first_nav * 100

    trading_days = len(returns)
    annualized_return = 0.0
    if trading_days > 0 and len(sorted_nav) >= 2:
        annualized_return = total_return * (252 / max(trading_days, 1))

    mean_return = sum(returns) / len(returns) if returns else 0.0
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns) if returns else 0.0
    volatility = variance**0.5 * (252**0.5) if variance > 0 else 0.0

    sharpe = 0.0
    if volatility > 0:
        risk_free_rate = 20.0
        sharpe = (annualized_return - risk_free_rate) / volatility

    max_drawdown = 0.0
    peak = 0.0
    for nav_entry in sorted_nav:
        nav_val = nav_entry.get("nav", 0)
        if nav_val > peak:
            peak = nav_val
        if peak > 0:
            drawdown = (peak - nav_val) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    return {
        "return_pct": round(total_return, 4),
        "annualized_return_pct": round(annualized_return, 4),
        "volatility_pct": round(volatility, 4),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown_pct": round(max_drawdown, 4),
    }
