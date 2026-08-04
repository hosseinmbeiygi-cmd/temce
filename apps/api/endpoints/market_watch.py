"""Market Watch — Comprehensive market dashboard endpoint."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_brsapi_query_service
from core.db_utils import safe_float, safe_int
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()

@router.get("", summary="Market watch dashboard data")
async def market_watch(
    market: str = Query("all", description="Market filter: all, bourse, farabourse, top30, top50"),
    sector: str | None = Query(None, description="Sector name filter"),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[dict[str, Any]]:
    """Comprehensive market dashboard with indices, stats, money flow, and charts."""

    try:
        # Use simple snapshots (high limit to cover entire market)
        snapshots = await brsapi.get_latest_snapshots(limit=3000)
        if not snapshots:
            return ApiResponse[dict[str, Any]](success=True, data=_empty_response(market))

        # Filter by market
        filtered = _filter_by_market(snapshots, market)

        # Filter by sector if provided
        if sector:
            filtered = [s for s in filtered if s.get("sector") == sector]

        if not filtered:
            return ApiResponse[dict[str, Any]](success=True, data=_empty_response(market))

        # Get index data
        indices = await brsapi.get_latest_indices()

        # Build response
        result = {
            "date": _get_persian_date(),
            "market": market,
            "sector_filter": sector,
            "summary": _build_summary(filtered, indices),
            "symbol_stats": _build_symbol_stats(filtered),
            "sector_money_flow": _build_sector_money_flow(filtered),
            "stock_money_flow": _build_stock_money_flow(filtered),
            "sector_trade_values": _build_sector_trade_values(filtered),
            "sectors": _get_unique_sectors(snapshots),
        }

        return ApiResponse[dict[str, Any]](success=True, data=result)

    except Exception as exc:
        logger.exception("Market watch failed")
        return ApiResponse[dict[str, Any]](
            success=False,
            data=_empty_response(market),
            error={"message": str(exc)},
        )


def _filter_by_market(snapshots: list[dict], market: str) -> list[dict]:
    """Filter snapshots by market segment."""
    if market == "all":
        return snapshots

    if market == "bourse":
        return [s for s in snapshots if _is_bourse(s)]

    if market == "farabourse":
        return [s for s in snapshots if _is_farabourse(s)]

    if market == "top30":
        sorted_by_mv = sorted(snapshots, key=lambda x: safe_float(x.get("market_value")), reverse=True)
        return sorted_by_mv[:30]

    if market == "top50":
        sorted_by_tv = sorted(snapshots, key=lambda x: safe_float(x.get("trade_value")), reverse=True)
        return sorted_by_tv[:50]

    return snapshots


def _is_bourse(s: dict) -> bool:
    """Check if symbol belongs to TSE (بورس)."""
    # Use ISIN prefix: IRO = TSE, IROF = FaraBourse
    isin = (s.get("isin") or "").upper()
    if isin.startswith("IROF"):
        return False
    if isin.startswith("IRO"):
        return True
    # Fallback: check market field if available
    market = (s.get("market") or "").lower()
    board = (s.get("board") or "").lower()
    if "فرابورس" in market or "فرابورس" in board:
        return False
    if "بورس" in market:
        return True
    # Default: assume Bourse (most symbols are TSE)
    return True


def _is_farabourse(s: dict) -> bool:
    """Check if symbol belongs to FaraBourse (فرابورس)."""
    isin = (s.get("isin") or "").upper()
    if isin.startswith("IROF"):
        return True
    market = (s.get("market") or "").lower()
    board = (s.get("board") or "").lower()
    return "فرابورس" in market or "فرابورس" in board


def _build_summary(snapshots: list[dict], indices: list[dict]) -> dict[str, Any]:
    """Build market summary statistics."""
    total_trade_value = sum(safe_float(s.get("trade_value")) for s in snapshots)
    total_volume = sum(safe_int(s.get("trade_volume")) for s in snapshots)

    # Find TSE index - first match wins (latest data)
    tse_index = {}
    equal_weight_index = {}
    for idx in indices:
        name = (idx.get("name") or "").strip()
        if not name:
            continue
        if "شاخص کل" in name and "هم وزن" not in name and not tse_index:
            tse_index = idx
        elif "شاخص کل" in name and "هم وزن" in name and not equal_weight_index:
            equal_weight_index = idx

    # Money flow: (buy_real_volume - sell_real_volume) * price_last
    net_real_flow = 0
    for s in snapshots:
        buy_real = safe_int(s.get("buy_real_volume"))
        sell_real = safe_int(s.get("sell_real_volume"))
        price = safe_float(s.get("price_last"))
        net_real_flow += (buy_real - sell_real) * price

    # Convert to billion rials
    net_real_flow_billion = net_real_flow / 1_000_000_000

    # Queue values (orderbook level 1) — use model fields directly
    buy_queue_value = 0
    sell_queue_value = 0
    for s in snapshots:
        bid_vol = safe_int(s.get("bid_volume_1"))
        bid_price = safe_float(s.get("bid_price_1"))
        ask_vol = safe_int(s.get("ask_volume_1"))
        ask_price = safe_float(s.get("ask_price_1"))
        buy_queue_value += bid_vol * bid_price / 1_000_000_000
        sell_queue_value += ask_vol * ask_price / 1_000_000_000

    # Fund data
    equity_fund_value = 0
    equity_fund_net = 0
    fixed_income_fund_value = 0
    fixed_income_fund_net = 0

    for s in snapshots:
        sector = (s.get("sector") or "").lower()
        name = (s.get("name") or "").lower()
        trade_value = safe_float(s.get("trade_value"))
        buy_real = safe_int(s.get("buy_real_volume"))
        sell_real = safe_int(s.get("sell_real_volume"))
        price = safe_float(s.get("price_last"))
        net = (buy_real - sell_real) * price / 1_000_000_000

        if "صندوق" in sector or "صندوق" in name:
            if "سهام" in name or "سهامی" in name:
                equity_fund_value += trade_value / 1_000_000_000
                equity_fund_net += net
            elif "درآمد" in name or "ثابت" in name:
                fixed_income_fund_value += trade_value / 1_000_000_000
                fixed_income_fund_net += net

    return {
        "index_value": safe_float(tse_index.get("index_value")),
        "index_change": safe_float(tse_index.get("index_change")),
        "index_change_pct": safe_float(tse_index.get("index_change_pct")),
        "index_equal_weight": safe_float(equal_weight_index.get("index_equal_weight")),
        "index_equal_weight_change": safe_float(equal_weight_index.get("index_equal_weight_change")),
        "index_equal_weight_change_pct": safe_float(equal_weight_index.get("index_equal_weight_change_pct")),
        "total_trade_value": round(total_trade_value / 1_000_000_000),
        "total_volume": total_volume,
        "net_real_money_flow": round(net_real_flow_billion),
        "buy_queue_value": round(buy_queue_value),
        "sell_queue_value": round(sell_queue_value),
        "equity_fund_value": round(equity_fund_value),
        "equity_fund_net": round(equity_fund_net),
        "fixed_income_fund_value": round(fixed_income_fund_value),
        "fixed_income_fund_net": round(fixed_income_fund_net),
    }


def _build_symbol_stats(snapshots: list[dict]) -> dict[str, Any]:
    """Build symbol count statistics."""
    positive = 0
    negative = 0
    unchanged = 0
    above_close = 0
    below_close = 0
    buy_queue = 0
    sell_queue = 0

    for s in snapshots:
        change_pct = safe_float(s.get("price_last_change_pct"))
        price_last = safe_float(s.get("price_last"))
        price_close = safe_float(s.get("price_close"))

        if change_pct > 0:
            positive += 1
        elif change_pct < 0:
            negative += 1
        else:
            unchanged += 1

        if price_last > price_close:
            above_close += 1
        elif price_last < price_close:
            below_close += 1

        # Check for queue ( صف )
        if change_pct >= 4.9:
            buy_queue += 1
        elif change_pct <= -4.9:
            sell_queue += 1

    return {
        "total": len(snapshots),
        "positive": positive,
        "negative": negative,
        "unchanged": unchanged,
        "above_closing": above_close,
        "below_closing": below_close,
        "buy_queue": buy_queue,
        "sell_queue": sell_queue,
    }


def _build_sector_money_flow(snapshots: list[dict]) -> dict[str, list[dict[str, Any]]]:
    """Build sector-level money flow (inflow/outflow)."""
    sector_flow: dict[str, float] = defaultdict(float)

    for s in snapshots:
        sector = s.get("sector") or "سایر"
        buy_real = safe_int(s.get("buy_real_volume"))
        sell_real = safe_int(s.get("sell_real_volume"))
        price = safe_float(s.get("price_last"))
        net = (buy_real - sell_real) * price / 1_000_000_000
        sector_flow[sector] += net

    # Separate inflow and outflow
    inflow = []
    outflow = []
    for sector, value in sorted(sector_flow.items(), key=lambda x: x[1], reverse=True):
        if value > 0:
            inflow.append({"name": sector, "value": round(value)})
        else:
            outflow.append({"name": sector, "value": round(abs(value))})

    return {
        "inflow": inflow[:15],
        "outflow": outflow[:15],
    }


def _build_stock_money_flow(snapshots: list[dict]) -> dict[str, list[dict[str, Any]]]:
    """Build stock-level money flow (inflow/outflow)."""
    stock_flow: list[dict[str, Any]] = []

    for s in snapshots:
        symbol = s.get("symbol") or ""
        if not symbol:
            continue
        buy_real = safe_int(s.get("buy_real_volume"))
        sell_real = safe_int(s.get("sell_real_volume"))
        price = safe_float(s.get("price_last"))
        net = (buy_real - sell_real) * price / 1_000_000_000

        stock_flow.append({
            "symbol": symbol,
            "name": s.get("name") or symbol,
            "value": round(net),
        })

    # Sort by value
    stock_flow.sort(key=lambda x: x["value"], reverse=True)

    inflow = [s for s in stock_flow if s["value"] > 0][:15]
    outflow = [{"symbol": s["symbol"], "name": s["name"], "value": abs(s["value"])} for s in stock_flow if s["value"] < 0][:15]

    return {
        "inflow": inflow,
        "outflow": outflow,
    }


def _build_sector_trade_values(snapshots: list[dict]) -> list[dict[str, Any]]:
    """Build sector trade value ranking."""
    sector_values: dict[str, float] = defaultdict(float)

    for s in snapshots:
        sector = s.get("sector") or "سایر"
        trade_value = safe_float(s.get("trade_value"))
        sector_values[sector] += trade_value / 1_000_000_000

    sorted_sectors = sorted(sector_values.items(), key=lambda x: x[1], reverse=True)
    return [{"name": name, "value": round(value)} for name, value in sorted_sectors[:20]]


def _get_unique_sectors(snapshots: list[dict]) -> list[str]:
    """Get unique sector names for filter dropdown."""
    sectors = set()
    for s in snapshots:
        sector = s.get("sector")
        if sector:
            sectors.add(sector)
    return sorted(sectors)


def _get_persian_date() -> str:
    """Get current date in Persian format."""
    from datetime import datetime, timedelta, timezone
    try:
        iran_tz = timezone(timedelta(hours=3, minutes=30))
        now = datetime.now(iran_tz)
        # Simple conversion (approximate)
        return f"{now.year}/{now.month:02d}/{now.day:02d}"
    except Exception as exc:
        logger.debug("Persian date conversion failed: %s", exc)
        return ""


def _empty_response(market: str) -> dict[str, Any]:
    """Return empty response structure."""
    return {
        "date": "",
        "market": market,
        "sector_filter": None,
        "summary": {
            "index_value": 0, "index_change": 0, "index_change_pct": 0,
            "index_equal_weight": 0, "index_equal_weight_change": 0, "index_equal_weight_change_pct": 0,
            "total_trade_value": 0, "total_volume": 0,
            "net_real_money_flow": 0, "buy_queue_value": 0, "sell_queue_value": 0,
            "equity_fund_value": 0, "equity_fund_net": 0,
            "fixed_income_fund_value": 0, "fixed_income_fund_net": 0,
        },
        "symbol_stats": {
            "total": 0, "positive": 0, "negative": 0, "unchanged": 0,
            "above_closing": 0, "below_closing": 0, "buy_queue": 0, "sell_queue": 0,
        },
        "sector_money_flow": {"inflow": [], "outflow": []},
        "stock_money_flow": {"inflow": [], "outflow": []},
        "sector_trade_values": [],
        "sectors": [],
    }
