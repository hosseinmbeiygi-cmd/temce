from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


def _mock_financials(symbol: str) -> dict[str, Any]:
    base_revenue = random.randint(100_000, 500_000) * 1_000_000
    net_profit = int(base_revenue * random.uniform(0.08, 0.25))
    equity = int(base_revenue * random.uniform(0.4, 0.7))
    total_assets = int(equity * random.uniform(1.5, 3.0))
    current_assets = int(total_assets * random.uniform(0.3, 0.6))
    current_liabilities = int(current_assets * random.uniform(0.4, 0.8))
    operating_cf = int(net_profit * random.uniform(0.7, 1.3))
    total_debt = int(equity * random.uniform(0.2, 0.8))
    shares = random.randint(5_000, 50_000) * 1_000_000
    price = random.randint(5_000, 50_000)
    market_cap = price * shares

    eps = net_profit / shares
    bvps = equity / shares
    pe = market_cap / net_profit if net_profit > 0 else 0
    pb = market_cap / equity if equity > 0 else 0
    roe = (net_profit / equity * 100) if equity > 0 else 0
    roa = (net_profit / total_assets * 100) if total_assets > 0 else 0
    de = total_debt / equity if equity > 0 else 0
    current_ratio = current_assets / current_liabilities if current_liabilities > 0 else 0
    net_margin = (net_profit / base_revenue * 100) if base_revenue > 0 else 0
    dividend_yield = random.uniform(0, 0.25)
    free_cash_flow = int(operating_cf - total_assets * random.uniform(0.05, 0.15))

    return {
        "symbol": symbol,
        "company_name": f"شرکت {symbol}",
        "industry": random.choice(["فلزات اساسی", "فرآورده‌های نفتی", "بانک", "خودرو", "پتروشیمی", "سیمان", "دارویی"]),
        "last_price": price,
        "market_cap": market_cap,
        "shares_outstanding": shares,
        "eps": round(eps, 2),
        "bvps": round(bvps, 2),
        "pe": round(pe, 2),
        "pb": round(pb, 2),
        "roe_pct": round(roe, 2),
        "roa_pct": round(roa, 2),
        "debt_to_equity": round(de, 2),
        "current_ratio": round(current_ratio, 2),
        "net_margin_pct": round(net_margin, 2),
        "dividend_yield_pct": round(dividend_yield * 100, 2),
        "free_cash_flow": free_cash_flow,
        "revenue": base_revenue,
        "net_profit": net_profit,
        "total_assets": total_assets,
        "total_equity": equity,
        "total_debt": int(total_debt),
        "fiscal_year": datetime.now(UTC).year,
    }


class FundamentalService:
    def __init__(self) -> None:
        pass

    async def get_ratios(self, symbol: str) -> Result[dict[str, Any]]:
        return Result.ok(_mock_financials(symbol))

    async def get_dcf_valuation(self, symbol: str) -> Result[dict[str, Any]]:
        f = _mock_financials(symbol)
        fcf = f["free_cash_flow"]
        growth = random.uniform(0.05, 0.20)
        terminal_growth = 0.03
        wacc = random.uniform(0.15, 0.25)

        pv_fcf = sum(fcf * ((1 + growth) ** i) / ((1 + wacc) ** i) for i in range(1, 6))
        terminal_value = fcf * (1 + growth) ** 5 * (1 + terminal_growth) / (wacc - terminal_growth)
        pv_terminal = terminal_value / (1 + wacc) ** 5
        enterprise_value = pv_fcf + pv_terminal
        fair_price = enterprise_value / f["shares_outstanding"] if f["shares_outstanding"] > 0 else 0

        return Result.ok({
            "symbol": symbol,
            "fair_price": round(fair_price, 2),
            "current_price": f["last_price"],
            "upside_pct": round((fair_price / f["last_price"] - 1) * 100, 2) if f["last_price"] > 0 else 0,
            "fcf": fcf,
            "growth_rate": round(growth * 100, 2),
            "terminal_growth": round(terminal_growth * 100, 2),
            "wacc": round(wacc * 100, 2),
            "pv_fcf": round(pv_fcf, 2),
            "pv_terminal": round(pv_terminal, 2),
            "enterprise_value": round(enterprise_value, 2),
        })

    async def score_stock(self, symbol: str) -> Result[dict[str, Any]]:
        f = _mock_financials(symbol)
        score = 0.0
        details: list[dict[str, Any]] = []

        if f["pe"] < 8:
            score += 20; details.append({"factor": "P/E پایین", "score": 20, "desc": "ارزنده"})
        elif f["pe"] < 15:
            score += 15; details.append({"factor": "P/E متعادل", "score": 15, "desc": "مناسب"})
        else:
            score += 5; details.append({"factor": "P/E بالا", "score": 5, "desc": "گران"})

        if f["pb"] < 1:
            score += 15; details.append({"factor": "P/B کمتر از ۱", "score": 15, "desc": "زیر ارزش ذاتی"})
        elif f["pb"] < 3:
            score += 10; details.append({"factor": "P/B متعادل", "score": 10, "desc": "مناسب"})
        else:
            score += 5; details.append({"factor": "P/B بالا", "score": 5, "desc": "گران"})

        if f["roe_pct"] > 30:
            score += 20; details.append({"factor": "ROE عالی", "score": 20, "desc": "بازده حقوق صاحبان سهام بالا"})
        elif f["roe_pct"] > 15:
            score += 15; details.append({"factor": "ROE خوب", "score": 15, "desc": "بازده مناسب"})
        else:
            score += 5; details.append({"factor": "ROE پایین", "score": 5, "desc": "نیاز به بهبود"})

        if f["debt_to_equity"] < 0.5:
            score += 15; details.append({"factor": "D/E پایین", "score": 15, "desc": "بدهی کم"})
        elif f["debt_to_equity"] < 1.5:
            score += 10; details.append({"factor": "D/E متعادل", "score": 10, "desc": "بدهی قابل قبول"})
        else:
            score += 3; details.append({"factor": "D/E بالا", "score": 3, "desc": "بدهی زیاد"})

        if f["net_margin_pct"] > 20:
            score += 15; details.append({"factor": "حاشیه سود عالی", "score": 15, "desc": "سودآوری بالا"})
        elif f["net_margin_pct"] > 10:
            score += 10; details.append({"factor": "حاشیه سود خوب", "score": 10, "desc": "سودآوری مناسب"})
        else:
            score += 5; details.append({"factor": "حاشیه سود پایین", "score": 5, "desc": "سودآوری کم"})

        if f["current_ratio"] > 2:
            score += 10; details.append({"factor": "نقدینگی عالی", "score": 10, "desc": "توان پرداخت بالا"})
        elif f["current_ratio"] > 1:
            score += 7; details.append({"factor": "نقدینگی مناسب", "score": 7, "desc": "توان پرداخت قابل قبول"})
        else:
            score += 3; details.append({"factor": "نقدینگی کم", "score": 3, "desc": "ریسک نقدینگی"})

        if f["dividend_yield_pct"] > 5:
            score += 5; details.append({"factor": "سود نقدی خوب", "score": 5, "desc": "توزیع سود مناسب"})
        else:
            score += 2; details.append({"factor": "سود نقدی کم", "score": 2, "desc": "توزیع سود پایین"})

        rating = "خرید قوی"
        if score < 40:
            rating = "فروش"
        elif score < 55:
            rating = "خنثی"
        elif score < 70:
            rating = "خرید"
        elif score < 85:
            rating = "خرید خوب"

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
        symbols = ["فولاد", "فملی", "شپنا", "وبانک", "خودرو", "ذوب", "رمپنا", "اخابر", "کگل", "چادر"]
        peers = []
        for sym in symbols:
            f = _mock_financials(sym)
            f["industry"] = industry
            peers.append(f)

        avg_pe = sum(p["pe"] for p in peers) / len(peers) if peers else 0
        avg_pb = sum(p["pb"] for p in peers) / len(peers) if peers else 0
        avg_roe = sum(p["roe_pct"] for p in peers) / len(peers) if peers else 0

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
