"""Options Analytics - arbitrage detection, volatility analysis, portfolio Greeks."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from domain.options.pricing import black_scholes_price, implied_volatility

logger = get_logger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity."""
    strategy: str
    description: str
    description_fa: str
    profit_potential: float
    risk_level: str
    legs: list[dict[str, Any]]
    conditions: str


class ArbitrageDetector:
    """Detects arbitrage opportunities in options market."""

    def __init__(self, risk_free_rate: float = 0.15):
        self.risk_free_rate = risk_free_rate

    def check_put_call_parity(
        self, call_price: float, put_price: float,
        stock_price: float, strike: float, time_to_expiry: float
    ) -> dict[str, Any]:
        """Check Put-Call Parity: C + Ke^(-rT) = P + S"""
        pv_strike = strike * math.exp(-self.risk_free_rate * time_to_expiry)
        left = call_price + pv_strike
        right = put_price + stock_price
        diff = left - right

        has_arbitrage = abs(diff) > 1  # > 1 Toman threshold

        result = {
            "parity_violated": has_arbitrage,
            "left_side": round(left, 2),
            "right_side": round(right, 2),
            "difference": round(diff, 2),
            "theoretical_call": round(right - pv_strike, 2),
            "theoretical_put": round(left - stock_price, 2),
        }

        if has_arbitrage:
            if diff > 0:
                result["action"] = "conversion"
                result["action_fa"] = "کانورژن: خرید سهام + خرید Put + فروش Call"
                result["profit"] = round(abs(diff), 2)
            else:
                result["action"] = "reverse_conversion"
                result["action_fa"] = "reverse_conversion: فروش سهام + خرید Call + فروش Put"
                result["profit"] = round(abs(diff), 2)

        return result

    def detect_opportunities(
        self, options_chain: list[dict[str, Any]], stock_price: float
    ) -> list[ArbitrageOpportunity]:
        """Scan options chain for arbitrage opportunities."""
        opportunities = []

        # Group by expiry
        by_expiry: dict[str, list] = {}
        for opt in options_chain:
            exp = opt.get("expiry", "")
            by_expiry.setdefault(exp, []).append(opt)

        for _expiry, opts in by_expiry.items():
            calls = [o for o in opts if o.get("type") == "call"]
            puts = [o for o in opts if o.get("type") == "put"]

            # Check put-call parity for each strike
            for call in calls:
                strike = call.get("strike", 0)
                matching_put = next((p for p in puts if p.get("strike") == strike), None)
                if matching_put and call.get("price", 0) > 0 and matching_put.get("price", 0) > 0:
                    T = call.get("time_to_expiry", 0.25)
                    result = self.check_put_call_parity(
                        call["price"], matching_put["price"],
                        stock_price, strike, T
                    )
                    if result["parity_violated"]:
                        opportunities.append(ArbitrageOpportunity(
                            strategy="put_call_parity",
                            description=f"Put-Call Parity violation at strike {strike}",
                            description_fa=f"نقض برابری پوت-کال در قیمت اعمال {strike}",
                            profit_potential=result.get("profit", 0),
                            risk_level="low",
                            legs=[
                                {"action": "buy", "type": "stock", "price": stock_price},
                                {"action": "buy", "type": "put", "strike": strike, "price": matching_put["price"]},
                                {"action": "sell", "type": "call", "strike": strike, "price": call["price"]},
                            ],
                            conditions="اختلاف بیش از ۱ تومان",
                        ))

            # Check box spread (risk-free profit)
            if len(calls) >= 2:
                sorted_calls = sorted(calls, key=lambda x: x.get("strike", 0))
                for i in range(len(sorted_calls) - 1):
                    c1 = sorted_calls[i]
                    c2 = sorted_calls[i + 1]
                    if c1.get("price", 0) > 0 and c2.get("price", 0) > 0:
                        k1 = c1.get("strike", 0)
                        k2 = c2.get("strike", 0)
                        if k2 > k1:
                            box = (c2["price"] - c1["price"]) - (k2 - k1)
                            if abs(box) > 1:
                                opportunities.append(ArbitrageOpportunity(
                                    strategy="box_spread",
                                    description=f"Box spread profit: {abs(box):.0f} Toman",
                                    description_fa=f"سود باکس اسپرد: {abs(box):.0f} تومان",
                                    profit_potential=abs(box),
                                    risk_level="very_low",
                                    legs=[],
                                    conditions="خرید Call اعمال پایین + فروش Call اعمال بالا + معکوس با Put",
                                ))

        return opportunities


class VolatilityAnalyzer:
    """Analyze and compare implied vs historical volatility."""

    def analyze(
        self, options_chain: list[dict[str, Any]], stock_price: float,
        historical_vol: float = 0.35
    ) -> dict[str, Any]:
        """Analyze volatility surface and compare IV vs HV."""
        iv_data = []

        for opt in options_chain:
            if opt.get("price", 0) > 0 and opt.get("strike", 0) > 0:
                T = opt.get("time_to_expiry", 0.25)
                iv = implied_volatility(
                    opt["price"], stock_price, opt["strike"],
                    T, 0.15, opt.get("type", "call")
                )
                iv_data.append({
                    "strike": opt["strike"],
                    "type": opt.get("type", "call"),
                    "iv": round(iv * 100, 1),
                    "moneyness": round(stock_price / opt["strike"], 3),
                })

        # Sort by strike
        iv_data.sort(key=lambda x: x["strike"])

        # Calculate average IV
        avg_iv = sum(d["iv"] for d in iv_data) / len(iv_data) if iv_data else 0

        # Volatility smile detection
        has_smile = False
        if len(iv_data) >= 3:
            mid_idx = len(iv_data) // 2
            mid_iv = iv_data[mid_idx]["iv"]
            wing_ivs = [d["iv"] for d in iv_data if abs(d["moneyness"] - 1.0) > 0.1]
            if wing_ivs and max(wing_ivs) > mid_iv * 1.1:
                has_smile = True

        return {
            "average_iv": round(avg_iv, 1),
            "historical_vol": round(historical_vol * 100, 1),
            "iv_hv_spread": round(avg_iv - historical_vol * 100, 1),
            "iv_higher": avg_iv > historical_vol * 100,
            "has_smile": has_smile,
            "iv_surface": iv_data,
            "interpretation": self._interpret(avg_iv, historical_vol * 100, has_smile),
        }

    def _interpret(self, avg_iv: float, hv: float, has_smile: bool) -> str:
        parts = []
        if avg_iv > hv * 1.2:
            parts.append("نوسان ضمنی بالاتر از تاریخی - اختیارها گران هستند (فروش مناسب‌تر)")
        elif avg_iv < hv * 0.8:
            parts.append("نوسان ضمنی پایین‌تر از تاریخی - اختیارها ارزان هستند (خرید مناسب‌تر)")
        else:
            parts.append("نوسان ضمنی نزدیک به تاریخی - قیمت‌گذاری منطقی")

        if has_smile:
            parts.append("لبخند نوسان مشاهده شده - اختیارهای OTM گران‌ترند")

        return " | ".join(parts)


class OptionsPortfolioAnalyzer:
    """Analyze a portfolio of options positions."""

    def analyze_portfolio(
        self, positions: list[dict[str, Any]], stock_price: float
    ) -> dict[str, Any]:
        """Calculate portfolio-level Greeks and risk metrics."""
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        total_rho = 0
        total_cost = 0

        for pos in positions:
            opt_type = pos.get("type", "call")
            side = pos.get("side", "buy")
            qty = pos.get("quantity", 1)
            strike = pos.get("strike", stock_price)
            premium = pos.get("premium", 0)
            T = pos.get("time_to_expiry", 0.25)

            result = black_scholes_price(stock_price, strike, T, 0.15, 0.35, opt_type)
            multiplier = qty if side == "buy" else -qty

            total_delta += result.delta * multiplier
            total_gamma += result.gamma * multiplier
            total_theta += result.theta * multiplier
            total_vega += result.vega * multiplier
            total_rho += result.rho * multiplier
            total_cost += premium * abs(multiplier) * (1 if side == "buy" else -1)

        return {
            "portfolio_delta": round(total_delta, 4),
            "portfolio_gamma": round(total_gamma, 6),
            "portfolio_theta": round(total_theta, 4),
            "portfolio_vega": round(total_vega, 4),
            "portfolio_rho": round(total_rho, 4),
            "net_cost": round(total_cost, 2),
            "delta_explanation": self._explain_delta(total_delta),
            "hedging_suggestion": self._suggest_hedge(total_delta, stock_price),
        }

    def _explain_delta(self, delta: float) -> str:
        if abs(delta) < 0.1:
            return "پورتفوی تقریباً خنثی نسبت به تغییرات قیمت"
        elif delta > 0:
            return f"پورتفوی {delta:.2f} واحد صعودی است (هر ۱٪ رشد سهم ≈ {delta:.2f}% سود)"
        else:
            return f"پورتفوی {abs(delta):.2f} واحد نزولی است (هر ۱٪ افت سهم ≈ {abs(delta):.2f}% سود)"

    def _suggest_hedge(self, delta: float, stock_price: float) -> str:
        if abs(delta) < 0.5:
            return "نیازی به هج نیست"
        shares_to_hedge = round(abs(delta) * 1000)
        direction = "فروش" if delta > 0 else "خرید"
        return f"برای خنثی‌سازی: {direction} {shares_to_hedge} سهم یا معادل آن اختیار"


# Singletons
_arb_detector: ArbitrageDetector | None = None
_vol_analyzer: VolatilityAnalyzer | None = None
_portfolio_analyzer: OptionsPortfolioAnalyzer | None = None


def get_arbitrage_detector() -> ArbitrageDetector:
    global _arb_detector
    if _arb_detector is None:
        _arb_detector = ArbitrageDetector()
    return _arb_detector


def get_volatility_analyzer() -> VolatilityAnalyzer:
    global _vol_analyzer
    if _vol_analyzer is None:
        _vol_analyzer = VolatilityAnalyzer()
    return _vol_analyzer


def get_portfolio_analyzer() -> OptionsPortfolioAnalyzer:
    global _portfolio_analyzer
    if _portfolio_analyzer is None:
        _portfolio_analyzer = OptionsPortfolioAnalyzer()
    return _portfolio_analyzer
