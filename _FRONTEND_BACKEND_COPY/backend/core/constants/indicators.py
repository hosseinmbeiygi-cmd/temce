from __future__ import annotations

from enum import StrEnum


class IndicatorType(StrEnum):
    SMA = "sma"
    EMA = "ema"
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER = "bollinger"
    ATR = "atr"
    STOCHASTIC = "stochastic"
    VOLUME = "volume"
    OBV = "obv"
    VWAP = "vwap"
    ROC = "roc"
    MOMENTUM = "momentum"
    HALF_TREND = "half_trend"
    SQUEEZE_MOMENTUM = "squeeze_momentum"
    SUPPORT_RESISTANCE = "support_resistance"


DEFAULT_INDICATOR_PARAMS: dict[str, dict[str, int | float]] = {
    "sma": {"period": 20},
    "ema": {"span": 12},
    "rsi": {"period": 14},
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "bollinger": {"period": 20, "std": 2.0},
    "atr": {"period": 14},
    "stochastic": {"k_period": 14, "d_period": 3},
    "volume_sma": {"period": 20},
    "obv": {},
    "vwap": {},
    "roc": {"period": 12},
    "momentum": {"period": 10},
    "half_trend": {"amplitude": 2, "channel_deviation": 2.0},
    "squeeze_momentum": {"bb_period": 20, "bb_std": 2.0, "kc_period": 20, "kc_mult": 1.5},
    "support_resistance": {"lookback": 20, "vol_threshold": 1.5},
}

INDICATOR_MIN_PERIODS: dict[str, int] = {
    "sma": 1,
    "ema": 1,
    "rsi": 14,
    "macd": 26,
    "bollinger": 20,
    "atr": 14,
    "stochastic": 14,
    "volume_sma": 1,
    "roc": 1,
    "momentum": 1,
    "half_trend": 2,
    "squeeze_momentum": 20,
    "support_resistance": 20,
}
