"""
Strategy Registry — single source of truth for all available backtesting strategies.

Provides a StrategyRegistry that stores strategy classes by name, and a
register_all_strategies() function that auto-discovers every strategy from
the rule_based and ml_based modules.  Analogous to ml/models/registry.py + __init__.py.
"""

from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from core.logging import get_logger

logger = get_logger(__name__)

# ── Strategy descriptions (Persian) ─────────────────────────────────────────
STRATEGY_DESCRIPTIONS: dict[str, str] = {
    "moving_average_cross": (
        "از تقاطع میانگین‌های متحرک کوتاه (مثلاً ۵) و بلندمدت (مثلاً ۲۰) "
        "برای شناسایی تغییر روند استفاده می‌کند. وقتی میانگین کوتاه از بلندمدت "
        "بالا می‌رود سیگنال خرید و وقتی پایین می‌آید سیگنال فروش صادر می‌شود. "
        "مناسب برای بازارهای رونددار (Trending)."
    ),
    "momentum": (
        "مقدار حرکت قیمت را در یک بازه زمانی مشخص (lookback) اندازه‌گیری می‌کند. "
        "اگر رشد قیمت از آستانه تعیین‌شده بیشتر باشد، سیگنال خرید صادر می‌شود. "
        "اگر افت قیمت از آستانه منفی کمتر باشد، سیگنال فروش صادر می‌شود. "
        "مناسب برای بازارهای با روند قوی."
    ),
    "mean_reversion": (
        "بر اساس فرض بازگشت قیمت به میانگین بلندمدت کار می‌کند. "
        "با محاسبه Z-Score، نقاط دور از میانگین را پیدا کرده و در آن نقاط "
        "خرید یا فروش می‌کند. "
        "مناسب برای بازارهای ساید (Range) و نوسانی."
    ),
    "breakout": (
        "به دنبال شکست قیمت از سقف یا کف محدوده نوسانی یک بازه مشخص (lookback) "
        "می‌گردد. وقتی قیمت از بالاترین سطح عبور کند سیگنال خرید و وقتی از "
        "پایین‌ترین سطح عبور کند سیگنال فروش صادر می‌شود. "
        "مناسب برای شروع روندهای جدید."
    ),
    "rsi_reversion": (
        "از اندیکاتور RSI برای تشخیص نقاط اشباع خرید (بالای ۷۰) و اشباع فروش "
        "(زیر ۳۰) استفاده می‌کند. در اشباع فروش خرید کرده و در اشباع خرید "
        "می‌فروشد. "
        "مناسب برای بازارهای نوسانی و ساید."
    ),
    "volatility_breakout": (
        "با محاسبه ATR (میانگین محدوده واقعی)، نوسانات بازار را اندازه‌گیری کرده "
        "و وقتی قیمت از یک باند حول قیمت بسته شدن قبلی (بر اساس ضریبی از ATR) "
        "شکست می‌کند، وارد معامله می‌شود. "
        "مناسب برای بازارهای با نوسان بالا."
    ),
    "half_trend": (
        "از اندیکاتور Half Trend برای تشخیص روند صعودی و نزولی استفاده می‌کند. "
        "این اندیکاتور با استفاده از میانگین‌گیری و انحراف، خط روندی هموار ایجاد "
        "می‌کند و تغییر جهت آن سیگنال خرید/فروش صادر می‌کند. "
        "مناسب برای روندهای پایدار."
    ),
    "squeeze_momentum": (
        "بر اساس اندیکاتور Squeeze Momentum عمل می‌کند که فشردگی قیمت بین "
        "باندهای بولینگر و کانال کِلتنر را تشخیص می‌دهد. وقتی فشردگی تمام شود "
        "و مومنتوم مثبت باشد، جهش صعودی پیش‌بینی می‌شود. "
        "مناسب برای شناسایی شروع روندهای قوی پس از تثبیت."
    ),
    "support_resistance": (
        "سطوح حمایت و مقاومت را با استفاده از تحلیل قله‌ها و دره‌های قیمتی "
        "همراه با تأیید حجم معاملات شناسایی می‌کند. شکست این سطوح همراه با حجم بالا "
        "سیگنال معتبرتری محسوب می‌شود. "
        "مناسب برای معاملات مبتنی بر تحلیل تکنیکال کلاسیک."
    ),
}


class StrategyRegistry:
    """Registry that maps strategy names to their classes."""

    def __init__(self) -> None:
        self._builders: dict[str, type[BaseStrategy]] = {}

    def register(self, name: str, strategy_cls: type[BaseStrategy]) -> None:
        self._builders[name] = strategy_cls

    def get(self, name: str) -> type[BaseStrategy] | None:
        return self._builders.get(name)

    def get_description(self, name: str) -> str:
        return STRATEGY_DESCRIPTIONS.get(name, "")

    def list_strategies(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "type": _derive_strategy_type(cls),
                "class_name": cls.__name__,
                "params": _inspect_strategy_params(cls),
                "description": STRATEGY_DESCRIPTIONS.get(name, ""),
            }
            for name, cls in self._builders.items()
        ]

    def list_names(self) -> list[str]:
        return list(self._builders.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._builders


def _derive_strategy_type(strategy_cls: type[BaseStrategy]) -> str:
    """Derive a human-readable category from the class's module path."""
    module = getattr(strategy_cls, "__module__", "") or ""
    parts = module.split(".")
    if "rule_based" in parts:
        return "rule_based"
    if "ml_based" in parts:
        return "ml_based"
    if "factor_based" in parts:
        return "factor_based"
    if "options" in parts:
        return "options"
    if "portfolios" in parts:
        return "portfolios"
    if "ml_based" in parts:
        return "ml_based"
    return "other"


def _inspect_strategy_params(strategy_cls: type[BaseStrategy]) -> list[dict[str, Any]]:
    """Introspect __init__ signature to expose configurable parameters."""
    import inspect

    sig = inspect.signature(strategy_cls.__init__)
    params: list[dict[str, Any]] = []
    for p_name, p_param in sig.parameters.items():
        if p_name == "self":
            continue
        default = None if p_param.default is inspect.Parameter.empty else p_param.default
        p_type = "string"
        if isinstance(default, bool):
            p_type = "boolean"
        elif isinstance(default, (int, float)):
            p_type = "number"
        params.append({"name": p_name, "type": p_type, "default": default})
    return params


# ── Global singleton strategy registry ──────────────────────────────────────
_strategy_registry = StrategyRegistry()


def get_strategy_registry() -> StrategyRegistry:
    return _strategy_registry


def register_all_strategies() -> None:
    """Discover and register every strategy from rule_based and portfolios modules."""
    # ML-based strategies
    from backtesting.strategies.ml_based.ml_signal_strategy import MlSignalStrategy
    from backtesting.strategies.rule_based.breakout_strategy import BreakoutStrategy
    from backtesting.strategies.rule_based.half_trend_strategy import HalfTrendStrategy
    from backtesting.strategies.rule_based.mean_reversion_strategy import MeanReversionStrategy
    from backtesting.strategies.rule_based.momentum_strategy import MomentumStrategy
    from backtesting.strategies.rule_based.moving_average_cross import MovingAverageCrossStrategy
    from backtesting.strategies.rule_based.rsi_reversion import RSIMeanReversionStrategy
    from backtesting.strategies.rule_based.squeeze_momentum_strategy import SqueezeMomentumStrategy
    from backtesting.strategies.rule_based.support_resistance_strategy import SupportResistanceStrategy
    from backtesting.strategies.rule_based.volatility_breakout import VolatilityBreakoutStrategy

    # Portfolio strategies
    try:
        from backtesting.strategies.portfolios.equal_weight_strategy import EqualWeightStrategy
        from backtesting.strategies.portfolios.max_sharpe_strategy import MaxSharpeStrategy
        from backtesting.strategies.portfolios.minimum_variance_strategy import MinimumVarianceStrategy
        from backtesting.strategies.portfolios.risk_parity_strategy import RiskParityStrategy
        from backtesting.strategies.portfolios.tactical_allocation_strategy import TacticalAllocationStrategy
        portfolio_strategies = [
            ("equal_weight", EqualWeightStrategy),
            ("max_sharpe", MaxSharpeStrategy),
            ("minimum_variance", MinimumVarianceStrategy),
            ("risk_parity", RiskParityStrategy),
            ("tactical_allocation", TacticalAllocationStrategy),
        ]
    except ImportError:
        portfolio_strategies = []

    for name, cls in [
        ("moving_average_cross", MovingAverageCrossStrategy),
        ("momentum", MomentumStrategy),
        ("mean_reversion", MeanReversionStrategy),
        ("breakout", BreakoutStrategy),
        ("rsi_reversion", RSIMeanReversionStrategy),
        ("volatility_breakout", VolatilityBreakoutStrategy),
        ("half_trend", HalfTrendStrategy),
        ("squeeze_momentum", SqueezeMomentumStrategy),
        ("support_resistance", SupportResistanceStrategy),
        ("ml_signal", MlSignalStrategy),
    ] + portfolio_strategies:
        _strategy_registry.register(name, cls)

    # Add descriptions for portfolio strategies
    STRATEGY_DESCRIPTIONS.update({
        "equal_weight": "توزیع مساوی سرمایه بین تمام دارایی‌ها. ساده‌ترین روش مدیریت پرتفوی.",
        "max_sharpe": "بهینه‌سازی پرتفوی برای حداکثر نسبت شارپ (بازده به ریسک).",
        "minimum_variance": "انتخاب وزن‌هایی که واریانس پرتفوی را به حداقل می‌رساند.",
        "risk_parity": "توزیع ریسک مساوی بین تمام دارایی‌ها بر اساس نوسانات.",
        "tactical_allocation": "تخصیص تاکتیکی بر اساس روند بازار و شرایط اقتصادی.",
        "ml_signal": (
            "از پیش‌بینی‌های یادگیری ماشین برای تصمیم‌گیری خرید/فروش استفاده می‌کند. "
            "مدل XGBoost/RandomForest روی داده‌های تاریخی آموزش دیده و برای هر کندل، "
            "درصد تغییر قیمت پیش‌بینی شده را محاسبه می‌کند. اگر پیش‌بینی صعود > آستانه باشد "
            "خرید می‌کند و اگر پیش‌بینی نزول < آستانه باشد می‌فروشد. "
            "مناسب برای ترکیب قدرت یادگیری ماشین با بک‌تست."
        ),
    })

    logger.debug("Registered %d strategies", len(_strategy_registry._builders))
