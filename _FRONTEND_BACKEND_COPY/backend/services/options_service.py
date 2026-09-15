"""Options Trading Service - complete strategy engine for Iranian market options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# ── Strategy Definitions ──────────────────────────────────────────────────────


@dataclass
class OptionLeg:
    """A single leg in an options strategy."""

    option_type: str  # "call" or "put"
    side: str  # "buy" or "sell"
    strike: float
    quantity: int = 1
    premium: float = 0.0
    expiry_months: int = 1  # months to expiry


@dataclass
class StrategyResult:
    """Result of analyzing an options strategy."""

    strategy_name: str
    strategy_name_fa: str
    legs: list[dict[str, Any]]
    max_profit: float
    max_loss: float
    break_even: list[float]
    initial_cost: float
    profit_at_expiry: list[dict[str, float]]
    market_condition: str  # bullish, bearish, neutral, volatile
    risk_level: str  # low, medium, high
    description: str
    description_fa: str
    best_for: str
    example: dict[str, Any] | None = None


class OptionsStrategyEngine:
    """Complete options strategy engine covering all 28+ strategies from the book."""

    # Iranian market constants
    CONTRACT_SIZE = 1000  # Each option contract = 1000 shares
    RISK_FREE_RATE = 0.15  # 15% annual (Iran)
    COMMISSION_BUY = 0.00125  # 0.125% buy commission
    COMMISSION_SELL = 0.00625  # 0.625% sell commission (incl 0.5% tax)
    SETTLEMENT_DAYS = 2  # T+2 settlement
    PRICE_LIMIT_PCT = 0.05  # 5% daily price limit for stocks
    OPTION_PRICE_LIMIT_PCT = 0.19  # 19% for options (wider than stocks)
    MIN_CAPITAL_RECOMMEND = 50_000_000  # 50M Toman recommended minimum

    def analyze_covered_call(
        self, stock_price: float, strike: float, premium: float, shares: int = 1000
    ) -> StrategyResult:
        """Covered Call: Own stock + sell call."""
        max_profit = (strike - stock_price) + premium
        max_loss = -stock_price + premium
        be = stock_price - premium
        return StrategyResult(
            strategy_name="covered_call",
            strategy_name_fa="کاورد کال",
            legs=[
                {"type": "stock", "side": "buy", "quantity": shares, "price": stock_price},
                {"type": "call", "side": "sell", "strike": strike, "premium": premium, "quantity": 1},
            ],
            max_profit=max_profit * shares,
            max_loss=max_loss * shares,
            break_even=[be],
            initial_cost=stock_price * shares - premium * shares,
            profit_at_expiry=[
                {"price": p, "profit": (min(p, strike) - stock_price + premium) * shares}
                for p in [stock_price * 0.7, stock_price * 0.85, stock_price, stock_price * 1.1, stock_price * 1.3]
            ],
            market_condition="neutral_bullish",
            risk_level="medium",
            description="Buy stock and sell call option for premium income",
            description_fa="خرید سهم و فروش اختیار خرید برای کسب درآمد از پریمیوم",
            best_for="بازار خنثی یا صعودی ملایم",
            example={"symbol": "ذوب", "stock_price": 444, "strike": 400, "premium": 84, "return_2m": "11%"},
        )

    def analyze_married_put(
        self, stock_price: float, put_strike: float, put_premium: float, shares: int = 1000
    ) -> StrategyResult:
        """Married Put: Own stock + buy put (insurance)."""
        float("inf")
        max_loss = -(stock_price - put_strike + put_premium)
        be = stock_price + put_premium
        return StrategyResult(
            strategy_name="married_put",
            strategy_name_fa="مرید پوت",
            legs=[
                {"type": "stock", "side": "buy", "quantity": shares, "price": stock_price},
                {"type": "put", "side": "buy", "strike": put_strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=float("inf"),
            max_loss=max_loss * shares,
            break_even=[be],
            initial_cost=(stock_price + put_premium) * shares,
            profit_at_expiry=[
                {"price": p, "profit": (p - stock_price - put_premium) * shares}
                for p in [stock_price * 0.7, stock_price * 0.85, stock_price, stock_price * 1.1, stock_price * 1.3]
            ],
            market_condition="bullish",
            risk_level="low",
            description="Own stock + buy put for downside protection",
            description_fa="خرید سهم و خرید اختیار فروش برای محافظت در برابر افت قیمت",
            best_for="بازار صعودی با احتمال اصلاح",
            example={"symbol": "صندوق سلام", "stock_price": 1500, "put_strike": 1500, "premium": 40},
        )

    def analyze_collar(
        self,
        stock_price: float,
        put_strike: float,
        put_premium: float,
        call_strike: float,
        call_premium: float,
        shares: int = 1000,
    ) -> StrategyResult:
        """Collar: Own stock + buy put + sell call."""
        net_premium = call_premium - put_premium
        max_profit = (call_strike - stock_price + net_premium) * shares
        max_loss = -(stock_price - put_strike - net_premium) * shares
        return StrategyResult(
            strategy_name="collar",
            strategy_name_fa="کولار",
            legs=[
                {"type": "stock", "side": "buy", "quantity": shares, "price": stock_price},
                {"type": "put", "side": "buy", "strike": put_strike, "premium": put_premium, "quantity": 1},
                {"type": "call", "side": "sell", "strike": call_strike, "premium": call_premium, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            break_even=[stock_price - net_premium],
            initial_cost=(stock_price + put_premium - call_premium) * shares,
            profit_at_expiry=[],
            market_condition="neutral",
            risk_level="low",
            description="Protect stock with put, fund it by selling call",
            description_fa="محافظت از سهم با خرید Put و تامین هزینه با فروش Call",
            best_for="بازار نوسانی با حفاظت از سود",
        )

    def analyze_long_straddle(
        self, stock_price: float, strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Long Straddle: Buy call + buy put same strike."""
        total_cost = call_premium + put_premium
        return StrategyResult(
            strategy_name="long_straddle",
            strategy_name_fa="استرادل خرید",
            legs=[
                {"type": "call", "side": "buy", "strike": strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=float("inf"),
            max_loss=-total_cost,
            break_even=[strike - total_cost, strike + total_cost],
            initial_cost=total_cost,
            profit_at_expiry=[
                {"price": p, "profit": max(0, p - strike) + max(0, strike - p) - total_cost}
                for p in [stock_price * 0.7, stock_price * 0.85, stock_price, stock_price * 1.15, stock_price * 1.3]
            ],
            market_condition="volatile",
            risk_level="high",
            description="Buy call + put same strike, profit from large moves",
            description_fa="خرید همزمان Call و Put با قیمت اعمال یکسان - سود از نوسان شدید",
            best_for="قبل از اخبار مهم یا رویدادهای سیاسی",
        )

    def analyze_long_strangle(
        self, stock_price: float, call_strike: float, put_strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Long Strangle: Buy OTM call + buy OTM put."""
        total_cost = call_premium + put_premium
        return StrategyResult(
            strategy_name="long_strangle",
            strategy_name_fa="استرانگل خرید",
            legs=[
                {"type": "call", "side": "buy", "strike": call_strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": put_strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=float("inf"),
            max_loss=-total_cost,
            break_even=[put_strike - total_cost, call_strike + total_cost],
            initial_cost=total_cost,
            profit_at_expiry=[
                {"price": p, "profit": max(0, p - call_strike) + max(0, put_strike - p) - total_cost}
                for p in [stock_price * 0.7, stock_price * 0.85, stock_price, stock_price * 1.15, stock_price * 1.3]
            ],
            market_condition="volatile",
            risk_level="high",
            description="Buy OTM call + put, cheaper than straddle",
            description_fa="خرید اختیار خرید و فروش OTM - هزینه کمتر از استرادل",
            best_for="انتظار نوسان شدید قیمت",
        )

    def analyze_short_straddle(
        self, stock_price: float, strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Short Straddle: Sell call + sell put same strike."""
        total_premium = call_premium + put_premium
        return StrategyResult(
            strategy_name="short_straddle",
            strategy_name_fa="استرادل فروش",
            legs=[
                {"type": "call", "side": "sell", "strike": strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "sell", "strike": strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=total_premium,
            max_loss=float("inf"),
            break_even=[strike - total_premium, strike + total_premium],
            initial_cost=-total_premium,
            profit_at_expiry=[],
            market_condition="neutral_low_vol",
            risk_level="very_high",
            description="Sell call + put same strike, profit from low volatility",
            description_fa="فروش همزمان Call و Put با قیمت اعمال یکسان - سود از بازار آرام",
            best_for="بازار آرام و بدون نوسان",
        )

    def analyze_short_strangle(
        self, stock_price: float, call_strike: float, put_strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Short Strangle: Sell OTM call + sell OTM put."""
        total_premium = call_premium + put_premium
        return StrategyResult(
            strategy_name="short_strangle",
            strategy_name_fa="استرانگل فروش",
            legs=[
                {"type": "call", "side": "sell", "strike": call_strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "sell", "strike": put_strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=total_premium,
            max_loss=float("inf"),
            break_even=[put_strike - total_premium, call_strike + total_premium],
            initial_cost=-total_premium,
            profit_at_expiry=[],
            market_condition="neutral_low_vol",
            risk_level="high",
            description="Sell OTM call + put, wider profit zone than short straddle",
            description_fa="فروش اختیار خرید و فروش OTM - منطقه سود گسترده‌تر",
            best_for="بازار خنثی با نوسان کم",
            example={"stock_price": 2200, "call_strike": 2400, "put_strike": 2000, "total_premium": 120},
        )

    def analyze_bull_call_spread(
        self, stock_price: float, lower_strike: float, upper_strike: float, lower_premium: float, upper_premium: float
    ) -> StrategyResult:
        """Bull Call Spread: Buy lower call + sell upper call."""
        net_cost = lower_premium - upper_premium
        max_profit = (upper_strike - lower_strike) - net_cost
        max_loss = -net_cost
        return StrategyResult(
            strategy_name="bull_call_spread",
            strategy_name_fa="بول کال اسپرد",
            legs=[
                {"type": "call", "side": "buy", "strike": lower_strike, "premium": lower_premium, "quantity": 1},
                {"type": "call", "side": "sell", "strike": upper_strike, "premium": upper_premium, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            break_even=[lower_strike + net_cost],
            initial_cost=net_cost,
            profit_at_expiry=[
                {"price": p, "profit": max(0, p - lower_strike) - max(0, p - upper_strike) - net_cost}
                for p in [stock_price * 0.8, stock_price * 0.9, stock_price, stock_price * 1.1, stock_price * 1.2]
            ],
            market_condition="bullish_mild",
            risk_level="medium",
            description="Buy low strike call + sell high strike call",
            description_fa="خرید اختیار خرید پایین‌تر و فروش اختیار خرید بالاتر",
            best_for="بازار صعودی ملایم با ریسک محدود",
            example={
                "symbol": "فملی",
                "lower_strike": 250,
                "upper_strike": 400,
                "lower_premium": 20,
                "upper_premium": 50,
            },
        )

    def analyze_bear_call_spread(
        self, stock_price: float, lower_strike: float, upper_strike: float, lower_premium: float, upper_premium: float
    ) -> StrategyResult:
        """Bear Call Spread: Sell lower call + buy upper call."""
        net_credit = lower_premium - upper_premium
        max_profit = net_credit
        max_loss = -(upper_strike - lower_strike - net_credit)
        return StrategyResult(
            strategy_name="bear_call_spread",
            strategy_name_fa="بیر کال اسپرد",
            legs=[
                {"type": "call", "side": "sell", "strike": lower_strike, "premium": lower_premium, "quantity": 1},
                {"type": "call", "side": "buy", "strike": upper_strike, "premium": upper_premium, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            break_even=[lower_strike + net_credit],
            initial_cost=-net_credit,
            profit_at_expiry=[],
            market_condition="bearish_mild",
            risk_level="medium",
            description="Sell low strike call + buy high strike call",
            description_fa="فروش اختیار خرید پایین‌تر و خرید اختیار خرید بالاتر",
            best_for="بازار نزولی ملایم",
        )

    def analyze_bull_put_spread(
        self, stock_price: float, higher_strike: float, lower_strike: float, higher_premium: float, lower_premium: float
    ) -> StrategyResult:
        """Bull Put Spread: Sell higher put + buy lower put."""
        net_credit = higher_premium - lower_premium
        max_profit = net_credit
        max_loss = -(higher_strike - lower_strike - net_credit)
        return StrategyResult(
            strategy_name="bull_put_spread",
            strategy_name_fa="بول پوت اسپرد",
            legs=[
                {"type": "put", "side": "sell", "strike": higher_strike, "premium": higher_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": lower_strike, "premium": lower_premium, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            break_even=[higher_strike - net_credit],
            initial_cost=-net_credit,
            profit_at_expiry=[],
            market_condition="bullish_mild",
            risk_level="medium",
            description="Sell higher put + buy lower put",
            description_fa="فروش اختیار فروش بالاتر و خرید اختیار فروش پایین‌تر",
            best_for="بازار صعودی یا خنثی",
        )

    def analyze_bear_put_spread(
        self, stock_price: float, higher_strike: float, lower_strike: float, higher_premium: float, lower_premium: float
    ) -> StrategyResult:
        """Bear Put Spread: Buy higher put + sell lower put."""
        net_cost = higher_premium - lower_premium
        max_profit = (higher_strike - lower_strike) - net_cost
        max_loss = -net_cost
        return StrategyResult(
            strategy_name="bear_put_spread",
            strategy_name_fa="بیر پوت اسپرد",
            legs=[
                {"type": "put", "side": "buy", "strike": higher_strike, "premium": higher_premium, "quantity": 1},
                {"type": "put", "side": "sell", "strike": lower_strike, "premium": lower_premium, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            break_even=[higher_strike - net_cost],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="bearish_mild",
            risk_level="medium",
            description="Buy higher put + sell lower put",
            description_fa="خرید اختیار فروش بالاتر و فروش اختیار فروش پایین‌تر",
            best_for="بازار نزولی ملایم",
        )

    def analyze_long_call_butterfly(
        self,
        stock_price: float,
        low_strike: float,
        mid_strike: float,
        high_strike: float,
        low_premium: float,
        mid_premium: float,
        high_premium: float,
    ) -> StrategyResult:
        """Long Call Butterfly: Buy 1 low + sell 2 mid + buy 1 high call."""
        net_cost = low_premium - 2 * mid_premium + high_premium
        max_profit = (mid_strike - low_strike) - net_cost
        max_loss = -net_cost
        return StrategyResult(
            strategy_name="long_call_butterfly",
            strategy_name_fa="پروانه اختیار خرید",
            legs=[
                {"type": "call", "side": "buy", "strike": low_strike, "premium": low_premium, "quantity": 1},
                {"type": "call", "side": "sell", "strike": mid_strike, "premium": mid_premium, "quantity": 2},
                {"type": "call", "side": "buy", "strike": high_strike, "premium": high_premium, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            break_even=[low_strike + net_cost, high_strike - net_cost],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="neutral",
            risk_level="low",
            description="Buy low call + sell 2 mid calls + buy high call",
            description_fa="ترکیب بول و بیر اسپرد - سود از بازار رنج",
            best_for="بازار رنج با نوسان محدود",
            example={"low": 130, "mid": 140, "high": 150, "max_profit": 10},
        )

    def analyze_short_call_butterfly(
        self,
        stock_price: float,
        low_strike: float,
        mid_strike: float,
        high_strike: float,
        low_premium: float,
        mid_premium: float,
        high_premium: float,
    ) -> StrategyResult:
        """Short Call Butterfly: Sell 1 low + buy 2 mid + sell 1 high call."""
        net_credit = -low_premium + 2 * mid_premium - high_premium
        max_loss = -(mid_strike - low_strike) + net_credit
        return StrategyResult(
            strategy_name="short_call_butterfly",
            strategy_name_fa="پروانه فروش اختیار خرید",
            legs=[
                {"type": "call", "side": "sell", "strike": low_strike, "premium": low_premium, "quantity": 1},
                {"type": "call", "side": "buy", "strike": mid_strike, "premium": mid_premium, "quantity": 2},
                {"type": "call", "side": "sell", "strike": high_strike, "premium": high_premium, "quantity": 1},
            ],
            max_profit=net_credit,
            max_loss=max_loss,
            break_even=[low_strike + net_credit, high_strike - net_credit],
            initial_cost=-net_credit,
            profit_at_expiry=[],
            market_condition="volatile",
            risk_level="medium",
            description="Reverse of long call butterfly",
            description_fa="عکس پروانه اختیار خرید - سود از نوسان",
            best_for="بازار با نوسان قیمت",
        )

    def analyze_long_put_butterfly(
        self,
        stock_price: float,
        low_strike: float,
        mid_strike: float,
        high_strike: float,
        low_premium: float,
        mid_premium: float,
        high_premium: float,
    ) -> StrategyResult:
        """Long Put Butterfly: Buy 1 low + sell 2 mid + buy 1 high put."""
        net_cost = low_premium - 2 * mid_premium + high_premium
        max_profit = (high_strike - mid_strike) - net_cost
        max_loss = -net_cost
        return StrategyResult(
            strategy_name="long_put_butterfly",
            strategy_name_fa="پروانه اختیار فروش",
            legs=[
                {"type": "put", "side": "buy", "strike": low_strike, "premium": low_premium, "quantity": 1},
                {"type": "put", "side": "sell", "strike": mid_strike, "premium": mid_premium, "quantity": 2},
                {"type": "put", "side": "buy", "strike": high_strike, "premium": high_premium, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            break_even=[low_strike + net_cost, high_strike - net_cost],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="neutral",
            risk_level="low",
            description="Same as long call butterfly but with puts",
            description_fa="مشابه پروانه اختیار خرید ولی با اختیار فروش",
            best_for="بازار رنج",
        )

    def analyze_short_put_butterfly(
        self,
        stock_price: float,
        low_strike: float,
        mid_strike: float,
        high_strike: float,
        low_premium: float,
        mid_premium: float,
        high_premium: float,
    ) -> StrategyResult:
        """Short Put Butterfly: Sell 1 low + buy 2 mid + sell 1 high put."""
        net_credit = -low_premium + 2 * mid_premium - high_premium
        max_loss = -(high_strike - mid_strike) + net_credit
        return StrategyResult(
            strategy_name="short_put_butterfly",
            strategy_name_fa="پروانه فروش اختیار فروش",
            legs=[
                {"type": "put", "side": "sell", "strike": low_strike, "premium": low_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": mid_strike, "premium": mid_premium, "quantity": 2},
                {"type": "put", "side": "sell", "strike": high_strike, "premium": high_premium, "quantity": 1},
            ],
            max_profit=net_credit,
            max_loss=max_loss,
            break_even=[low_strike + net_credit, high_strike - net_credit],
            initial_cost=-net_credit,
            profit_at_expiry=[],
            market_condition="volatile",
            risk_level="medium",
            description="Reverse of long put butterfly",
            description_fa="عکس پروانه اختیار فروش",
            best_for="بازار با نوسان",
        )

    def analyze_iron_butterfly(
        self,
        stock_price: float,
        center_strike: float,
        outer_call_strike: float,
        outer_put_strike: float,
        center_call_premium: float,
        center_put_premium: float,
        outer_call_premium: float,
        outer_put_premium: float,
    ) -> StrategyResult:
        """Iron Butterfly: Sell ATM call+put + buy OTM call+put."""
        net_credit = center_call_premium + center_put_premium - outer_call_premium - outer_put_premium
        max_profit = net_credit
        max_loss = max(center_strike - outer_put_strike, outer_call_strike - center_strike) - net_credit
        return StrategyResult(
            strategy_name="iron_butterfly",
            strategy_name_fa="پروانه آهنی",
            legs=[
                {
                    "type": "call",
                    "side": "sell",
                    "strike": center_strike,
                    "premium": center_call_premium,
                    "quantity": 1,
                },
                {"type": "put", "side": "sell", "strike": center_strike, "premium": center_put_premium, "quantity": 1},
                {
                    "type": "call",
                    "side": "buy",
                    "strike": outer_call_strike,
                    "premium": outer_call_premium,
                    "quantity": 1,
                },
                {"type": "put", "side": "buy", "strike": outer_put_strike, "premium": outer_put_premium, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=-max_loss,
            break_even=[center_strike - net_credit, center_strike + net_credit],
            initial_cost=-net_credit,
            profit_at_expiry=[],
            market_condition="neutral_low_vol",
            risk_level="high",
            description="Sell ATM call+put + buy OTM wings",
            description_fa="ترکیب استرادل فروش و استرانگل خرید",
            best_for="بازار آرام",
        )

    def analyze_iron_condor(
        self,
        stock_price: float,
        put_high_strike: float,
        put_low_strike: float,
        call_low_strike: float,
        call_high_strike: float,
        put_high_premium: float,
        put_low_premium: float,
        call_low_premium: float,
        call_high_premium: float,
    ) -> StrategyResult:
        """Iron Condor: Bull put spread + bear call spread."""
        net_credit = put_high_premium - put_low_premium + call_low_premium - call_high_premium
        max_profit = net_credit
        max_loss = max(put_high_strike - put_low_strike, call_high_strike - call_low_strike) - net_credit
        return StrategyResult(
            strategy_name="iron_condor",
            strategy_name_fa="کرکس آهنی",
            legs=[
                {"type": "put", "side": "sell", "strike": put_high_strike, "premium": put_high_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": put_low_strike, "premium": put_low_premium, "quantity": 1},
                {"type": "call", "side": "sell", "strike": call_low_strike, "premium": call_low_premium, "quantity": 1},
                {
                    "type": "call",
                    "side": "buy",
                    "strike": call_high_strike,
                    "premium": call_high_premium,
                    "quantity": 1,
                },
            ],
            max_profit=max_profit,
            max_loss=-max_loss,
            break_even=[put_high_strike - net_credit, call_low_strike + net_credit],
            initial_cost=-net_credit,
            profit_at_expiry=[],
            market_condition="neutral",
            risk_level="medium",
            description="Sell narrow put+call spread, limited risk",
            description_fa="ترکیب بول پوت و بیر کال اسپرد - ریسک محدود",
            best_for="بازار خنثی با نوسان کم",
        )

    def analyze_long_call_condor(
        self, stock_price: float, k1: float, k2: float, k3: float, k4: float, p1: float, p2: float, p3: float, p4: float
    ) -> StrategyResult:
        """Long Call Condor: Buy 1 low + sell 1 mid-low + sell 1 mid-high + buy 1 high."""
        net_cost = p1 - p2 - p3 + p4
        max_profit = (k2 - k1) - net_cost
        max_loss = -net_cost
        return StrategyResult(
            strategy_name="long_call_condor",
            strategy_name_fa="کندر خرید با اختیار خرید",
            legs=[
                {"type": "call", "side": "buy", "strike": k1, "premium": p1, "quantity": 1},
                {"type": "call", "side": "sell", "strike": k2, "premium": p2, "quantity": 1},
                {"type": "call", "side": "sell", "strike": k3, "premium": p3, "quantity": 1},
                {"type": "call", "side": "buy", "strike": k4, "premium": p4, "quantity": 1},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            break_even=[k1 + net_cost, k4 - net_cost],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="neutral",
            risk_level="low",
            description="Buy low+high calls, sell two mid calls",
            description_fa="خرید اختیار خرید پایین و بالا، فروش دو اختیار میانی",
            best_for="بازار رنج با محدوده مشخص",
            example={"price": 1000, "k1": 900, "k2": 950, "k3": 1000, "k4": 1050, "net_cost": 40},
        )

    def analyze_strip(
        self, stock_price: float, strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Strip: Buy 1 call + buy 2 puts (bearish bias)."""
        total_cost = call_premium + 2 * put_premium
        return StrategyResult(
            strategy_name="strip",
            strategy_name_fa="استریپ",
            legs=[
                {"type": "call", "side": "buy", "strike": strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": strike, "premium": put_premium, "quantity": 2},
            ],
            max_profit=float("inf"),
            max_loss=-total_cost,
            break_even=[],
            initial_cost=total_cost,
            profit_at_expiry=[],
            market_condition="volatile_bearish",
            risk_level="high",
            description="Buy 1 call + 2 puts, bearish volatile",
            description_fa="خرید ۱ اختیار خرید و ۲ اختیار فروش - وزن نزولی",
            best_for="انتظار نوسان با احتمال بیشتر نزول",
        )

    def analyze_strap(
        self, stock_price: float, strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Strap: Buy 2 calls + buy 1 put (bullish bias)."""
        total_cost = 2 * call_premium + put_premium
        return StrategyResult(
            strategy_name="strap",
            strategy_name_fa="استرپ",
            legs=[
                {"type": "call", "side": "buy", "strike": strike, "premium": call_premium, "quantity": 2},
                {"type": "put", "side": "buy", "strike": strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=float("inf"),
            max_loss=-total_cost,
            break_even=[],
            initial_cost=total_cost,
            profit_at_expiry=[],
            market_condition="volatile_bullish",
            risk_level="high",
            description="Buy 2 calls + 1 put, bullish volatile",
            description_fa="خرید ۲ اختیار خرید و ۱ اختیار فروش - وزن صعودی",
            best_for="انتظار نوسان با احتمال بیشتر صعود",
        )

    def analyze_long_gut(
        self, stock_price: float, call_strike: float, put_strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Long Gut: Buy ITM call + buy ITM put (opposite of strangle)."""
        total_cost = call_premium + put_premium
        return StrategyResult(
            strategy_name="long_gut",
            strategy_name_fa="گات خرید",
            legs=[
                {"type": "call", "side": "buy", "strike": call_strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": put_strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=float("inf"),
            max_loss=-total_cost,
            break_even=[put_strike - total_cost, call_strike + total_cost],
            initial_cost=total_cost,
            profit_at_expiry=[],
            market_condition="volatile",
            risk_level="high",
            description="Buy ITM call + ITM put",
            description_fa="خرید اختیار خرید و فروش ITM - برعکس استرانگل",
            best_for="نوسان شدید قیمت",
        )

    def analyze_calendar_spread(
        self, stock_price: float, strike: float, near_premium: float, far_premium: float, option_type: str = "call"
    ) -> StrategyResult:
        """Calendar Spread: Buy far expiry + sell near expiry."""
        net_cost = far_premium - near_premium
        return StrategyResult(
            strategy_name="calendar_spread",
            strategy_name_fa="اسپرد تقویمی",
            legs=[
                {
                    "type": option_type,
                    "side": "sell",
                    "strike": strike,
                    "premium": near_premium,
                    "quantity": 1,
                    "expiry": "near",
                },
                {
                    "type": option_type,
                    "side": "buy",
                    "strike": strike,
                    "premium": far_premium,
                    "quantity": 1,
                    "expiry": "far",
                },
            ],
            max_profit=float("inf"),
            max_loss=-net_cost,
            break_even=[],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="neutral",
            risk_level="medium",
            description="Sell near expiry + buy far expiry, same strike",
            description_fa="فروش سررسید نزدیک و خرید سررسید دور - بهره‌برداری از زمان",
            best_for="بازار کوتاه‌مدت آرام، بلندمدت پرنوسان",
        )

    def analyze_ratio_spread(
        self,
        stock_price: float,
        buy_strike: float,
        sell_strike: float,
        buy_premium: float,
        sell_premium: float,
        sell_qty: int = 2,
        option_type: str = "call",
    ) -> StrategyResult:
        """Ratio Spread: Buy 1 + sell N options."""
        net_cost = buy_premium - sell_qty * sell_premium
        return StrategyResult(
            strategy_name="ratio_spread",
            strategy_name_fa="اسپرد نسبتی",
            legs=[
                {"type": option_type, "side": "buy", "strike": buy_strike, "premium": buy_premium, "quantity": 1},
                {
                    "type": option_type,
                    "side": "sell",
                    "strike": sell_strike,
                    "premium": sell_premium,
                    "quantity": sell_qty,
                },
            ],
            max_profit=float("inf") if option_type == "call" else (sell_strike - buy_strike - net_cost),
            max_loss=float("inf") if sell_qty > 1 else -net_cost,
            break_even=[],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="directional",
            risk_level="high",
            description=f"Buy 1 + sell {sell_qty} options",
            description_fa=f"خرید ۱ و فروش {sell_qty} قرارداد اختیار",
            best_for="پیش‌بینی حرکت معین قیمت",
        )

    def analyze_call_back_spread(
        self, stock_price: float, itm_strike: float, otm_strike: float, itm_premium: float, otm_premium: float
    ) -> StrategyResult:
        """Call Back Spread: Sell 1 ITM call + buy 2 OTM calls."""
        net_cost = -itm_premium + 2 * otm_premium
        return StrategyResult(
            strategy_name="call_back_spread",
            strategy_name_fa="اسپرد بازگشتی اختیار خرید",
            legs=[
                {"type": "call", "side": "sell", "strike": itm_strike, "premium": itm_premium, "quantity": 1},
                {"type": "call", "side": "buy", "strike": otm_strike, "premium": otm_premium, "quantity": 2},
            ],
            max_profit=float("inf"),
            max_loss=-net_cost if net_cost > 0 else -(itm_strike - otm_strike + net_cost),
            break_even=[],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="volatile_bullish",
            risk_level="high",
            description="Sell 1 ITM call + buy 2 OTM calls",
            description_fa="فروش ۱ اختیار خرید ITM و خرید ۲ اختیار OTM",
            best_for="صعود شدید قیمت",
        )

    def analyze_put_back_spread(
        self, stock_price: float, itm_strike: float, otm_strike: float, itm_premium: float, otm_premium: float
    ) -> StrategyResult:
        """Put Back Spread: Sell 1 ITM put + buy 2 OTM puts."""
        net_cost = -itm_premium + 2 * otm_premium
        return StrategyResult(
            strategy_name="put_back_spread",
            strategy_name_fa="اسپرد بازگشتی اختیار فروش",
            legs=[
                {"type": "put", "side": "sell", "strike": itm_strike, "premium": itm_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": otm_strike, "premium": otm_premium, "quantity": 2},
            ],
            max_profit=float("inf"),
            max_loss=-net_cost if net_cost > 0 else -(itm_strike - otm_strike + net_cost),
            break_even=[],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="volatile_bearish",
            risk_level="high",
            description="Sell 1 ITM put + buy 2 OTM puts",
            description_fa="فروش ۱ اختیار فروش ITM و خرید ۲ اختیار OTM",
            best_for="نزول شدید قیمت",
        )

    def analyze_conversion(
        self, stock_price: float, strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Conversion: Buy call + sell put (synthetic long)."""
        net_cost = call_premium - put_premium
        return StrategyResult(
            strategy_name="conversion",
            strategy_name_fa="کانورژن",
            legs=[
                {"type": "call", "side": "buy", "strike": strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "sell", "strike": strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=float("inf"),
            max_loss=float("inf"),
            break_even=[strike + net_cost],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="bullish",
            risk_level="medium",
            description="Buy call + sell put = synthetic long stock",
            description_fa="خرید اختیار خرید و فروش اختیار فروش = سهام مصنوعی",
            best_for="آربیتراژ و سود بدون ریسک",
        )

    def analyze_synthetic_long(
        self, stock_price: float, strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Synthetic Long: Buy call + sell put (same strike)."""
        net_cost = call_premium - put_premium
        return StrategyResult(
            strategy_name="synthetic_long",
            strategy_name_fa="سهام مصنوعی صعودی",
            legs=[
                {"type": "call", "side": "buy", "strike": strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "sell", "strike": strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=float("inf"),
            max_loss=float("inf"),
            break_even=[strike + net_cost],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="bullish",
            risk_level="medium",
            description="Buy call + sell put at same strike = synthetic long stock",
            description_fa="خرید اختیار خرید + فروش اختیار فروش = سهام مصنوعی صعودی (بدون نیاز به خرید سهم)",
            best_for="بجای خرید مستقیم سهم با سرمایه کمتر",
        )

    def analyze_synthetic_short(
        self, stock_price: float, strike: float, call_premium: float, put_premium: float
    ) -> StrategyResult:
        """Synthetic Short: Sell call + buy put (same strike)."""
        net_credit = put_premium - call_premium
        return StrategyResult(
            strategy_name="synthetic_short",
            strategy_name_fa="سهام مصنوعی نزولی",
            legs=[
                {"type": "call", "side": "sell", "strike": strike, "premium": call_premium, "quantity": 1},
                {"type": "put", "side": "buy", "strike": strike, "premium": put_premium, "quantity": 1},
            ],
            max_profit=float("inf"),
            max_loss=float("inf"),
            break_even=[strike - net_credit],
            initial_cost=-net_credit,
            profit_at_expiry=[],
            market_condition="bearish",
            risk_level="high",
            description="Sell call + buy put at same strike = synthetic short stock",
            description_fa="فروش اختیار خرید + خرید اختیار فروش = سهام مصنوعی نزولی (فروش فزاینده بدون سهم)",
            best_for="بجای فروش استقراضی سهم (ممنوع در ایران)",
        )

    def analyze_diagonal_call_spread(
        self,
        stock_price: float,
        long_call_strike: float,
        short_call_strike: float,
        long_call_premium: float,
        short_call_premium: float,
        long_call_expiry: str = "6m",
        short_call_expiry: str = "1m",
    ) -> StrategyResult:
        """Diagonal Call Spread: Buy far expiry + sell near expiry (different strikes)."""
        net_cost = long_call_premium - short_call_premium
        return StrategyResult(
            strategy_name="diagonal_call_spread",
            strategy_name_fa="اسپرد مورب اختیار خرید",
            legs=[
                {
                    "type": "call",
                    "side": "buy",
                    "strike": long_call_strike,
                    "premium": long_call_premium,
                    "quantity": 1,
                    "expiry": long_call_expiry,
                },
                {
                    "type": "call",
                    "side": "sell",
                    "strike": short_call_strike,
                    "premium": short_call_premium,
                    "quantity": 1,
                    "expiry": short_call_expiry,
                },
            ],
            max_profit=float("inf"),
            max_loss=-net_cost,
            break_even=[],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="bullish_mild",
            risk_level="medium",
            description="Buy far expiry call + sell near expiry call (different strikes)",
            description_fa="خرید اختیار خرید سررسید دورتر + فروش اختیار خرید سررسید نزدیک‌تر با اعمال متفاوت",
            best_for="صعود ملایم با بهره‌برداری از تفاوت زمانی",
        )

    def analyze_diagonal_put_spread(
        self,
        stock_price: float,
        long_put_strike: float,
        short_put_strike: float,
        long_put_premium: float,
        short_put_premium: float,
        long_put_expiry: str = "6m",
        short_put_expiry: str = "1m",
    ) -> StrategyResult:
        """Diagonal Put Spread: Buy far expiry + sell near expiry (different strikes)."""
        net_cost = long_put_premium - short_put_premium
        return StrategyResult(
            strategy_name="diagonal_put_spread",
            strategy_name_fa="اسپرد مورب اختیار فروش",
            legs=[
                {
                    "type": "put",
                    "side": "buy",
                    "strike": long_put_strike,
                    "premium": long_put_premium,
                    "quantity": 1,
                    "expiry": long_put_expiry,
                },
                {
                    "type": "put",
                    "side": "sell",
                    "strike": short_put_strike,
                    "premium": short_put_premium,
                    "quantity": 1,
                    "expiry": short_put_expiry,
                },
            ],
            max_profit=float("inf"),
            max_loss=-net_cost,
            break_even=[],
            initial_cost=net_cost,
            profit_at_expiry=[],
            market_condition="bearish_mild",
            risk_level="medium",
            description="Buy far expiry put + sell near expiry put (different strikes)",
            description_fa="خرید اختیار فروش سررسید دورتر + فروش اختیار فروش سررسید نزدیک‌تر با اعمال متفاوت",
            best_for="نزول ملایم با بهره‌برداری از تفاوت زمانی",
        )

    # ── Professional Tools ──────────────────────────────────────────────────────

    def calculate_realistic_costs(
        self, entry_price: float, exit_price: float, quantity: int, is_option: bool = True, is_short: bool = False
    ) -> dict[str, Any]:
        """Calculate realistic P&L with Iranian market costs."""
        if is_option:
            # Options: 0.125% buy + 0.625% sell
            buy_cost = entry_price * quantity * self.COMMISSION_BUY
            sell_cost = exit_price * quantity * self.COMMISSION_SELL
            total_commission = buy_cost + sell_cost
        else:
            # Stocks: 0.125% buy + 0.88% sell (incl tax)
            buy_cost = entry_price * quantity * 0.00125
            sell_cost = exit_price * quantity * 0.0088
            total_commission = buy_cost + sell_cost

        gross_pnl = (exit_price - entry_price) * quantity
        net_pnl = gross_pnl - total_commission
        net_pnl_pct = (net_pnl / (entry_price * quantity)) * 100

        return {
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "gross_pnl": round(gross_pnl, 0),
            "commission": round(total_commission, 0),
            "tax_included": is_option and not is_short,
            "net_pnl": round(net_pnl, 0),
            "net_pnl_pct": round(net_pnl_pct, 2),
            "breakeven": round(entry_price + total_commission / quantity, 2),
        }

    def calculate_position_size(
        self, capital: float, risk_per_trade_pct: float, max_loss_per_contract: float, option_type: str = "buy"
    ) -> dict[str, Any]:
        """Professional position sizing for options."""
        risk_amount = capital * (risk_per_trade_pct / 100)

        if option_type == "buy":
            # For long options: max loss = premium paid
            max_contracts = int(risk_amount / (max_loss_per_contract * self.CONTRACT_SIZE))
            cost_per_contract = max_loss_per_contract * self.CONTRACT_SIZE
            total_cost = max_contracts * cost_per_contract
        else:
            # For short options: max loss is theoretically unlimited
            # Use margin requirement instead
            margin_per_contract = max_loss_per_contract * self.CONTRACT_SIZE * 0.15
            max_contracts = int(risk_amount / margin_per_contract)
            total_cost = max_contracts * margin_per_contract

        return {
            "capital": capital,
            "risk_per_trade": risk_amount,
            "max_contracts": max_contracts,
            "total_cost": round(total_cost, 0),
            "cost_per_contract": round(cost_per_contract if option_type == "buy" else margin_per_contract, 0),
            "pct_of_capital": round((total_cost / capital) * 100, 1),
        }

    def calculate_iv_rank(self, current_iv: float, iv_52w_high: float, iv_52w_low: float) -> dict[str, Any]:
        """Calculate IV Rank and Percentile."""
        iv_range = iv_52w_high - iv_52w_low
        iv_rank = ((current_iv - iv_52w_low) / iv_range * 100) if iv_range > 0 else 50

        # Interpretation
        if iv_rank > 80:
            interpretation = "IV بسیار بالا - مناسب فروش پریمیوم (Short strategies)"
            interpretation_fa = "نوسان ضمنی بسیار بالا - اختیارها گران هستند. فروش پریمیوم مناسب‌تر است."
            suggestion = "short_straddle, short_strangle, iron_condor, covered_call"
        elif iv_rank > 60:
            interpretation = "IV بالا - مناسب فروش پریمیوم"
            interpretation_fa = "نوسان ضمنی بالا - اختیارها نسبتاً گران هستند."
            suggestion = "short_strangle, iron_condor, covered_call"
        elif iv_rank > 40:
            interpretation = "IV متوسط - استراتژی‌های متعادل"
            interpretation_fa = "نوسان ضمنی در محدوده متوسط."
            suggestion = "spread strategies, collar"
        elif iv_rank > 20:
            interpretation = "IV پایین - مناسب خرید پریمیوم"
            interpretation_fa = "نوسان ضمنی پایین - اختیارها ارزان هستند. خرید اختیار مناسب‌تر است."
            suggestion = "long_straddle, long_strangle, long_call, long_put"
        else:
            interpretation = "IV بسیار پایین - فرصت نادر خرید ارزان"
            interpretation_fa = "نوسان ضمنی بسیار پایین - فرصت نادر برای خرید اختیار."
            suggestion = "long_straddle, long_strangle, buy calls/puts"

        return {
            "current_iv": round(current_iv * 100, 1),
            "iv_52w_high": round(iv_52w_high * 100, 1),
            "iv_52w_low": round(iv_52w_low * 100, 1),
            "iv_rank": round(iv_rank, 1),
            "interpretation": interpretation,
            "interpretation_fa": interpretation_fa,
            "suggestion": suggestion,
        }

    def analyze_options_chain(self, options_chain: list[dict[str, Any]], stock_price: float) -> dict[str, Any]:
        """Analyze full options chain for trading signals."""
        calls = [o for o in options_chain if o.get("type") == "call"]
        puts = [o for o in options_chain if o.get("type") == "put"]

        # Find ATM
        atm_call = min(calls, key=lambda x: abs(x.get("strike", 0) - stock_price), default=None)
        min(puts, key=lambda x: abs(x.get("strike", 0) - stock_price), default=None)

        # Put-Call Ratio
        total_call_vol = sum(o.get("volume", 0) for o in calls)
        total_put_vol = sum(o.get("volume", 0) for o in puts)
        pcr = total_put_vol / total_call_vol if total_call_vol > 0 else 1.0

        # Max Pain (strike with most open interest)
        all_oi = {}
        for o in options_chain:
            s = o.get("strike", 0)
            all_oi[s] = all_oi.get(s, 0) + o.get("open_interest", 0)
        max_pain = max(all_oi, key=all_oi.get) if all_oi else stock_price

        # Support/Resistance from options
        call_oi_strikes = sorted(
            [(o.get("strike", 0), o.get("open_interest", 0)) for o in calls], key=lambda x: x[1], reverse=True
        )
        put_oi_strikes = sorted(
            [(o.get("strike", 0), o.get("open_interest", 0)) for o in puts], key=lambda x: x[1], reverse=True
        )

        return {
            "stock_price": stock_price,
            "atm_strike": atm_call.get("strike") if atm_call else None,
            "put_call_ratio": round(pcr, 2),
            "pcr_interpretation": ("bearish" if pcr > 1.2 else "bullish" if pcr < 0.8 else "neutral"),
            "max_pain": max_pain,
            "resistance_levels": [s for s, _ in call_oi_strikes[:3]],
            "support_levels": [s for s, _ in put_oi_strikes[:3]],
            "total_call_volume": total_call_vol,
            "total_put_volume": total_put_vol,
            "total_call_oi": sum(o.get("open_interest", 0) for o in calls),
            "total_put_oi": sum(o.get("open_interest", 0) for o in puts),
        }

    def generate_trade_checklist(self, strategy: str, stock_price: float, strike: float) -> list[dict[str, Any]]:
        """Pre-trade checklist for Iranian options market."""
        checklist = [
            {"item": "تحلیل تکنیکال انجام شده", "done": False, "priority": "high"},
            {"item": "تحلیل بنیادی بررسی شده", "done": False, "priority": "medium"},
            {"item": "حد ضرر مشخص شده", "done": False, "priority": "high"},
            {"item": "حد سود مشخص شده", "done": False, "priority": "high"},
            {"item": "اندازه موقعیت محاسبه شده (حداکثر ۲۰٪ سرمایه)", "done": False, "priority": "high"},
            {"item": "نقدشوندگی نماد بررسی شده (حجم معاملات)", "done": False, "priority": "high"},
            {"item": "هزینه‌ها محاسبه شده (کارمزد + مالیات)", "done": False, "priority": "medium"},
            {"item": "تاریخ سررسید بررسی شده", "done": False, "priority": "medium"},
            {"item": "نوسان ضمنی (IV) بررسی شده", "done": False, "priority": "medium"},
            {"item": "رویدادهای مهم (مجمع، اخبار) بررسی شده", "done": False, "priority": "low"},
            {"item": "وجه تضمین کافی موجود است", "done": False, "priority": "high"},
            {"item": "سناریوهای مختلف (صعود/نزول/خنثی) بررسی شده", "done": False, "priority": "medium"},
        ]

        # Strategy-specific checks
        if strategy in ("short_straddle", "short_strangle", "iron_butterfly", "iron_condor"):
            checklist.append({"item": "مجوز فروش از کارگزاری دریافت شده", "done": False, "priority": "high"})
            checklist.append(
                {"item": "وجه تضمین اضافی برای مدیریت ریسک کنار گذاشته شده", "done": False, "priority": "high"}
            )

        if strategy in ("covered_call", "married_put", "collar"):
            checklist.append({"item": "سهم پایه در پرتفوی موجود است", "done": False, "priority": "high"})

        if strategy in ("long_straddle", "long_strangle", "long_gut"):
            checklist.append(
                {"item": "رویداد محرک (اخبار، مجمع) در آینده نزدیک وجود دارد", "done": False, "priority": "medium"}
            )

        # Price proximity check
        pct_from_strike = abs(stock_price - strike) / stock_price * 100
        if pct_from_strike > 20:
            checklist.append(
                {
                    "item": f"فاصله قیمت سهم تا اعمال: {pct_from_strike:.1f}% - بررسی کنید",
                    "done": False,
                    "priority": "medium",
                }
            )

        return checklist

    def get_all_strategies(self) -> list[dict[str, Any]]:
        """Return list of all available strategies with metadata."""
        return [
            {
                "id": "covered_call",
                "name": "Covered Call",
                "name_fa": "کاورد کال",
                "category": "income",
                "market": "neutral_bullish",
                "risk": "medium",
                "legs": 2,
            },
            {
                "id": "married_put",
                "name": "Married Put",
                "name_fa": "مرید پوت",
                "category": "protection",
                "market": "bullish",
                "risk": "low",
                "legs": 2,
            },
            {
                "id": "collar",
                "name": "Collar",
                "name_fa": "کولار",
                "category": "protection",
                "market": "neutral",
                "risk": "low",
                "legs": 3,
            },
            {
                "id": "long_straddle",
                "name": "Long Straddle",
                "name_fa": "استرادل خرید",
                "category": "volatility",
                "market": "volatile",
                "risk": "high",
                "legs": 2,
            },
            {
                "id": "short_straddle",
                "name": "Short Straddle",
                "name_fa": "استرادل فروش",
                "category": "income",
                "market": "neutral_low_vol",
                "risk": "very_high",
                "legs": 2,
            },
            {
                "id": "long_strangle",
                "name": "Long Strangle",
                "name_fa": "استرانگل خرید",
                "category": "volatility",
                "market": "volatile",
                "risk": "high",
                "legs": 2,
            },
            {
                "id": "short_strangle",
                "name": "Short Strangle",
                "name_fa": "استرانگل فروش",
                "category": "income",
                "market": "neutral_low_vol",
                "risk": "high",
                "legs": 2,
            },
            {
                "id": "bull_call_spread",
                "name": "Bull Call Spread",
                "name_fa": "بول کال اسپرد",
                "category": "directional",
                "market": "bullish_mild",
                "risk": "medium",
                "legs": 2,
            },
            {
                "id": "bear_call_spread",
                "name": "Bear Call Spread",
                "name_fa": "بیر کال اسپرد",
                "category": "directional",
                "market": "bearish_mild",
                "risk": "medium",
                "legs": 2,
            },
            {
                "id": "bull_put_spread",
                "name": "Bull Put Spread",
                "name_fa": "بول پوت اسپرد",
                "category": "directional",
                "market": "bullish_mild",
                "risk": "medium",
                "legs": 2,
            },
            {
                "id": "bear_put_spread",
                "name": "Bear Put Spread",
                "name_fa": "بیر پوت اسپرد",
                "category": "directional",
                "market": "bearish_mild",
                "risk": "medium",
                "legs": 2,
            },
            {
                "id": "long_call_butterfly",
                "name": "Long Call Butterfly",
                "name_fa": "پروانه اختیار خرید",
                "category": "neutral",
                "market": "neutral",
                "risk": "low",
                "legs": 3,
            },
            {
                "id": "short_call_butterfly",
                "name": "Short Call Butterfly",
                "name_fa": "پروانه فروش اختیار خرید",
                "category": "volatility",
                "market": "volatile",
                "risk": "medium",
                "legs": 3,
            },
            {
                "id": "long_put_butterfly",
                "name": "Long Put Butterfly",
                "name_fa": "پروانه اختیار فروش",
                "category": "neutral",
                "market": "neutral",
                "risk": "low",
                "legs": 3,
            },
            {
                "id": "short_put_butterfly",
                "name": "Short Put Butterfly",
                "name_fa": "پروانه فروش اختیار فروش",
                "category": "volatility",
                "market": "volatile",
                "risk": "medium",
                "legs": 3,
            },
            {
                "id": "iron_butterfly",
                "name": "Iron Butterfly",
                "name_fa": "پروانه آهنی",
                "category": "income",
                "market": "neutral_low_vol",
                "risk": "high",
                "legs": 4,
            },
            {
                "id": "iron_condor",
                "name": "Iron Condor",
                "name_fa": "کرکس آهنی",
                "category": "income",
                "market": "neutral",
                "risk": "medium",
                "legs": 4,
            },
            {
                "id": "long_call_condor",
                "name": "Long Call Condor",
                "name_fa": "کندر خرید با اختیار خرید",
                "category": "neutral",
                "market": "neutral",
                "risk": "low",
                "legs": 4,
            },
            {
                "id": "strip",
                "name": "Strip",
                "name_fa": "استریپ",
                "category": "volatility",
                "market": "volatile_bearish",
                "risk": "high",
                "legs": 3,
            },
            {
                "id": "strap",
                "name": "Strap",
                "name_fa": "استرپ",
                "category": "volatility",
                "market": "volatile_bullish",
                "risk": "high",
                "legs": 3,
            },
            {
                "id": "long_gut",
                "name": "Long Gut",
                "name_fa": "گات خرید",
                "category": "volatility",
                "market": "volatile",
                "risk": "high",
                "legs": 2,
            },
            {
                "id": "calendar_spread",
                "name": "Calendar Spread",
                "name_fa": "اسپرد تقویمی",
                "category": "time",
                "market": "neutral",
                "risk": "medium",
                "legs": 2,
            },
            {
                "id": "ratio_spread",
                "name": "Ratio Spread",
                "name_fa": "اسپرد نسبتی",
                "category": "directional",
                "market": "directional",
                "risk": "high",
                "legs": 2,
            },
            {
                "id": "call_back_spread",
                "name": "Call Back Spread",
                "name_fa": "اسپرد بازگشتی اختیار خرید",
                "category": "volatility",
                "market": "volatile_bullish",
                "risk": "high",
                "legs": 2,
            },
            {
                "id": "put_back_spread",
                "name": "Put Back Spread",
                "name_fa": "اسپرد بازگشتی اختیار فروش",
                "category": "volatility",
                "market": "volatile_bearish",
                "risk": "high",
                "legs": 2,
            },
            {
                "id": "conversion",
                "name": "Conversion",
                "name_fa": "کانورژن",
                "category": "arbitrage",
                "market": "any",
                "risk": "low",
                "legs": 2,
            },
            {
                "id": "synthetic_long",
                "name": "Synthetic Long",
                "name_fa": "سهام مصنوعی صعودی",
                "category": "directional",
                "market": "bullish",
                "risk": "medium",
                "legs": 2,
            },
            {
                "id": "synthetic_short",
                "name": "Synthetic Short",
                "name_fa": "سهام مصنوعی نزولی",
                "category": "directional",
                "market": "bearish",
                "risk": "high",
                "legs": 2,
            },
            {
                "id": "diagonal_call_spread",
                "name": "Diagonal Call Spread",
                "name_fa": "اسپرد مورب اختیار خرید",
                "category": "time",
                "market": "bullish_mild",
                "risk": "medium",
                "legs": 2,
            },
            {
                "id": "diagonal_put_spread",
                "name": "Diagonal Put Spread",
                "name_fa": "اسپرد مورب اختیار فروش",
                "category": "time",
                "market": "bearish_mild",
                "risk": "medium",
                "legs": 2,
            },
        ]

    def recommend(self, market_condition: str, risk_tolerance: float = 0.5) -> list[dict[str, Any]]:
        """Recommend strategies based on market condition and risk tolerance."""
        all_strategies = self.get_all_strategies()
        recommended = []

        for s in all_strategies:
            score = 0
            market_match = s["market"]

            if market_condition == "bullish":
                if market_match in ("bullish", "bullish_mild", "volatile_bullish", "any"):
                    score += 3
                elif market_match in ("neutral", "directional"):
                    score += 1
            elif market_condition == "bearish":
                if market_match in ("bearish", "bearish_mild", "volatile_bearish", "any"):
                    score += 3
                elif market_match in ("neutral", "directional"):
                    score += 1
            elif market_condition == "neutral":
                if market_match in ("neutral", "neutral_low_vol", "any"):
                    score += 3
            elif market_condition == "volatile":
                if market_match in ("volatile", "volatile_bullish", "volatile_bearish", "any"):
                    score += 3

            # Risk matching
            risk_map = {"low": 1, "medium": 2, "high": 3, "very_high": 4}
            s_risk = risk_map.get(s["risk"], 2)
            if risk_tolerance < 0.3 and s_risk <= 2:
                score += 2
            elif risk_tolerance < 0.7 and s_risk <= 3 or risk_tolerance >= 0.7:
                score += 1

            if score > 0:
                recommended.append({**s, "score": score})

        recommended.sort(key=lambda x: x["score"], reverse=True)
        return recommended[:8]


# Singleton
_options_engine: OptionsStrategyEngine | None = None


def get_options_engine(instance: OptionsStrategyEngine | None = None) -> OptionsStrategyEngine:
    """Get or create the OptionsStrategyEngine.

    Args:
        instance: optional pre-built instance to use instead of the singleton.
    """
    if instance is not None:
        return instance
    global _options_engine
    if _options_engine is None:
        _options_engine = OptionsStrategyEngine()
    return _options_engine
