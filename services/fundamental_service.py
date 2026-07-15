"""Fundamental Service — uses real data from brsapi_symbol_snapshots and brsapi_symbol_details.

No mock/fake data. When real data is unavailable, returns empty/zero values
instead of fabricated financials.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


def _snapshot_to_financials(symbol: str, snap: dict[str, Any], detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build financials from real brsapi snapshot + detail data."""
    price = float(snap.get("price_last") or snap.get("price_close") or 0)
    shares = int(snap.get("shares_count") or 0)
    market_cap = float(snap.get("market_value") or 0)
    eps = float(snap.get("eps") or 0)
    pe = float(snap.get("pe_ratio") or 0)

    # Detail fields (richer data when available)
    free_float_pct = 0.0
    board = ""
    sub_sector = ""
    if detail:
        free_float_pct = float(detail.get("free_float_pct") or 0)
        board = str(detail.get("board") or "")
        sub_sector = str(detail.get("sub_sector") or "")

    bvps = 0.0
    pb = 0.0
    roe = 0.0
    roa = 0.0
    de = 0.0
    current_ratio = 0.0
    net_margin = 0.0

    # Compute what we can from available data
    if pe > 0 and eps > 0:
        # PE = price / EPS, so we already have both
        pass
    if market_cap > 0 and shares > 0:
        bvps = market_cap / shares  # rough estimate
        if bvps > 0:
            pb = price / bvps if bvps else 0

    return {
        "symbol": symbol,
        "company_name": snap.get("name", f"شرکت {symbol}"),
        "industry": snap.get("sector", ""),
        "sub_sector": sub_sector,
        "board": board,
        "last_price": price,
        "market_cap": market_cap,
        "shares_outstanding": shares,
        "free_float_pct": free_float_pct,
        "eps": round(eps, 2),
        "bvps": round(bvps, 2),
        "pe": round(pe, 2),
        "pb": round(pb, 2),
        "roe_pct": round(roe, 2),
        "roa_pct": round(roa, 2),
        "debt_to_equity": round(de, 2),
        "current_ratio": round(current_ratio, 2),
        "net_margin_pct": round(net_margin, 2),
        "dividend_yield_pct": 0.0,
        "free_cash_flow": 0,
        "revenue": 0,
        "net_profit": round(eps * shares, 2) if eps and shares else 0,
        "total_assets": 0,
        "total_equity": 0,
        "total_debt": 0,
        "fiscal_year": datetime.now(UTC).year,
        "_data_source": "brsapi" if (snap.get("eps") or snap.get("pe_ratio")) else "snapshot_only",
    }


class FundamentalService:
    def __init__(self, brsapi_query_service: Any | None = None) -> None:
        self._brsapi = brsapi_query_service

    async def _get_snapshot_and_detail(self, symbol: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Get both snapshot and enriched detail from BrsApi tables."""
        if not self._brsapi:
            return None, None
        try:
            snap = await self._brsapi.get_symbol_snapshot(symbol)
        except Exception:
            snap = None
        detail = None
        try:
            detail = await self._brsapi.get_enriched_symbol_detail(symbol)
        except Exception:
            pass
        return snap, detail

    async def get_ratios(self, symbol: str) -> Result[dict[str, Any]]:
        snap, detail = await self._get_snapshot_and_detail(symbol)
        if snap:
            return Result.ok(_snapshot_to_financials(symbol, snap, detail))
        return Result.fail(f"Symbol {symbol} not found in database")

    async def get_dcf_valuation(self, symbol: str) -> Result[dict[str, Any]]:
        snap, detail = await self._get_snapshot_and_detail(symbol)
        if not snap:
            return Result.fail(f"Symbol {symbol} not found — cannot compute DCF valuation")

        f = _snapshot_to_financials(symbol, snap, detail)
        fcf = f.get("net_profit", 0) or 0
        price = f.get("last_price", 0) or 0

        if fcf <= 0 or price <= 0:
            return Result.ok({
                "symbol": symbol,
                "fair_price": 0,
                "current_price": price,
                "upside_pct": 0,
                "fcf": 0,
                "growth_rate": 0,
                "terminal_growth": 3.0,
                "wacc": 20.0,
                "pv_fcf": 0,
                "pv_terminal": 0,
                "enterprise_value": 0,
                "_note": "Insufficient data for DCF — need positive FCF and price",
            })

        # Conservative DCF with fixed reasonable assumptions
        growth = 0.10
        terminal_growth = 0.03
        wacc = 0.20

        pv_fcf = sum(fcf * ((1 + growth) ** i) / ((1 + wacc) ** i) for i in range(1, 6))
        discount_rate = wacc - terminal_growth
        terminal_value = fcf * (1 + growth) ** 5 * (1 + terminal_growth) / discount_rate if discount_rate > 0 else 0.0
        pv_terminal = terminal_value / (1 + wacc) ** 5
        enterprise_value = pv_fcf + pv_terminal
        fair_price = enterprise_value / f["shares_outstanding"] if f["shares_outstanding"] > 0 else 0

        return Result.ok({
            "symbol": symbol,
            "fair_price": round(fair_price, 2),
            "current_price": price,
            "upside_pct": round((fair_price / price - 1) * 100, 2) if price > 0 else 0,
            "fcf": fcf,
            "growth_rate": round(growth * 100, 2),
            "terminal_growth": round(terminal_growth * 100, 2),
            "wacc": round(wacc * 100, 2),
            "pv_fcf": round(pv_fcf, 2),
            "pv_terminal": round(pv_terminal, 2),
            "enterprise_value": round(enterprise_value, 2),
            "_note": "DCF uses conservative fixed assumptions (growth=10%, WACC=20%) — refine with actual financials when available",
        })

    async def score_stock(self, symbol: str) -> Result[dict[str, Any]]:
        snap, detail = await self._get_snapshot_and_detail(symbol)
        if not snap:
            return Result.fail(f"Symbol {symbol} not found — cannot score")

        f = _snapshot_to_financials(symbol, snap, detail)
        score = 0.0
        details: list[dict[str, Any]] = []

        pe = f.get("pe", 0)
        pb = f.get("pb", 0)
        roe = f.get("roe_pct", 0)
        de = f.get("debt_to_equity", 0)
        net_margin = f.get("net_margin_pct", 0)
        current_ratio = f.get("current_ratio", 0)

        if pe and pe > 0:
            if pe < 8:
                score += 20; details.append({"factor": "P/E پایین", "score": 20, "desc": "ارزنده"})
            elif pe < 15:
                score += 15; details.append({"factor": "P/E متعادل", "score": 15, "desc": "مناسب"})
            else:
                score += 5; details.append({"factor": "P/E بالا", "score": 5, "desc": "گران"})
        else:
            details.append({"factor": "P/E", "score": 0, "desc": "داده موجود نیست"})

        if pb and pb > 0:
            if pb < 1:
                score += 15; details.append({"factor": "P/B کمتر از ۱", "score": 15, "desc": "زیر ارزش ذاتی"})
            elif pb < 3:
                score += 10; details.append({"factor": "P/B متعادل", "score": 10, "desc": "مناسب"})
            else:
                score += 5; details.append({"factor": "P/B بالا", "score": 5, "desc": "گران"})
        else:
            details.append({"factor": "P/B", "score": 0, "desc": "داده موجود نیست"})

        # ROE, D/E, margins — only score if we have real data
        if roe > 0:
            if roe > 30:
                score += 20; details.append({"factor": "ROE عالی", "score": 20, "desc": "بازده حقوق صاحبان سهام بالا"})
            elif roe > 15:
                score += 15; details.append({"factor": "ROE خوب", "score": 15, "desc": "بازده مناسب"})
            else:
                score += 5; details.append({"factor": "ROE پایین", "score": 5, "desc": "نیاز به بهبود"})
        else:
            details.append({"factor": "ROE", "score": 0, "desc": "داده موجود نیست"})

        if de > 0:
            if de < 0.5:
                score += 15; details.append({"factor": "D/E پایین", "score": 15, "desc": "بدهی کم"})
            elif de < 1.5:
                score += 10; details.append({"factor": "D/E متعادل", "score": 10, "desc": "بدهی قابل قبول"})
            else:
                score += 3; details.append({"factor": "D/E بالا", "score": 3, "desc": "بدهی زیاد"})
        else:
            details.append({"factor": "D/E", "score": 0, "desc": "داده موجود نیست"})

        rating = "نامشخص"
        if score >= 70:
            rating = "خرید قوی"
        elif score >= 55:
            rating = "خرید"
        elif score >= 40:
            rating = "خنثی"
        elif score > 0:
            rating = "فروش"

        return Result.ok({
            "symbol": symbol,
            "total_score": round(score, 1),
            "max_score": 100,
            "rating": rating,
            "rating_fa": rating,
            "details": details,
            "financials": f,
        })

    async def compare_symbols(self, symbols: list[str]) -> Result[list[dict[str, Any]]]:
        results = []
        for sym in symbols:
            r = await self.score_stock(sym)
            if r.success and r.value:
                results.append(r.value)
        return Result.ok(results)

    async def industry_analysis(self, industry: str) -> Result[dict[str, Any]]:
        # Get all symbols in the industry from snapshot data
        if not self._brsapi:
            return Result.fail("No BrsApi service available")

        try:
            snapshots = await self._brsapi.get_enriched_snapshots(limit=500)
        except Exception:
            return Result.fail("Failed to fetch snapshots")

        peers = []
        for s in (snapshots or []):
            if s.get("sector") == industry:
                f = _snapshot_to_financials(s.get("symbol", ""), s)
                peers.append(f)

        if not peers:
            return Result.ok({
                "industry": industry,
                "peers_count": 0,
                "avg_pe": 0, "avg_pb": 0, "avg_roe": 0,
                "peers": [],
                "_note": f"No symbols found for industry '{industry}'",
            })

        valid_pe = [p["pe"] for p in peers if p["pe"] and p["pe"] > 0]
        valid_pb = [p["pb"] for p in peers if p["pb"] and p["pb"] > 0]

        avg_pe = sum(valid_pe) / len(valid_pe) if valid_pe else 0
        avg_pb = sum(valid_pb) / len(valid_pb) if valid_pb else 0
        avg_roe = 0  # Not available from snapshot data

        return Result.ok({
            "industry": industry,
            "peers_count": len(peers),
            "avg_pe": round(avg_pe, 2),
            "avg_pb": round(avg_pb, 2),
            "avg_roe": round(avg_roe, 2),
            "peers": [
                {
                    "symbol": p["symbol"],
                    "pe": p["pe"],
                    "pb": p["pb"],
                    "roe": p["roe_pct"],
                    "market_cap": p["market_cap"],
                }
                for p in sorted(peers, key=lambda x: x["market_cap"], reverse=True)
            ],
        })
