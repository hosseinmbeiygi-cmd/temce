from __future__ import annotations

import math


def calculate_simple_return(price_t: float, price_t_minus_1: float) -> float:
    return (price_t - price_t_minus_1) / price_t_minus_1


def calculate_log_return(price_t: float, price_t_minus_1: float) -> float:
    return math.log(price_t / price_t_minus_1)


def calculate_daily_range(high_t: float, low_t: float) -> float:
    return high_t - low_t


def calculate_relative_range(high_t: float, low_t: float, close_t_minus_1: float) -> float:
    return (high_t - low_t) / close_t_minus_1


def calculate_clv(close_t: float, high_t: float, low_t: float) -> float:
    if high_t == low_t:
        return 0.0
    return (2 * close_t - high_t - low_t) / (high_t - low_t)


def calculate_recovery_ratio(close_t: float, high_t: float, low_t: float) -> float:
    if high_t == low_t:
        return 0.0
    return (close_t - low_t) / (high_t - low_t)


def calculate_relative_volume(volume_t: float, avg_volume_n: float) -> float:
    return volume_t / avg_volume_n if avg_volume_n else 1.0


def calculate_volume_zscore(volume_t: float, mean_volume: float, std_volume: float) -> float:
    if std_volume == 0:
        return 0.0
    return (volume_t - mean_volume) / std_volume


def calculate_traded_value(price_t: float, volume_t: float) -> float:
    return price_t * volume_t


def calculate_float_turnover(volume_t: float, effective_float_shares: float) -> float:
    return volume_t / effective_float_shares if effective_float_shares else 0.0


def calculate_amihud_illiquidity(return_t: float, traded_value_t: float) -> float | None:
    if traded_value_t == 0:
        return None
    return abs(return_t) / traded_value_t


def calculate_true_range(high_t: float, low_t: float, close_t_minus_1: float) -> float:
    return max(
        high_t - low_t,
        abs(high_t - close_t_minus_1),
        abs(low_t - close_t_minus_1),
    )


def calculate_atr(true_ranges: list[float]) -> float:
    if not true_ranges:
        return 0.0
    return sum(true_ranges) / len(true_ranges)


def calculate_normalized_volatility(atr_t: float, close_t: float) -> float:
    return atr_t / close_t if close_t else 0.0


def calculate_compression_ratio(atr_short: float, atr_long: float) -> float:
    return atr_short / atr_long if atr_long else 1.0


def calculate_bollinger_bandwidth(upper_band: float, lower_band: float, middle_ma: float) -> float:
    return (upper_band - lower_band) / middle_ma if middle_ma else 0.0


def calculate_relative_strength_ratio(asset_price: float, benchmark_price: float) -> float:
    return asset_price / benchmark_price if benchmark_price else 1.0


def calculate_excess_return(asset_return: float, benchmark_return: float) -> float:
    return asset_return - benchmark_return


def calculate_zscore(x_t: float, mean_x: float, std_x: float) -> float:
    if std_x == 0:
        return 0.0
    return (x_t - mean_x) / std_x
