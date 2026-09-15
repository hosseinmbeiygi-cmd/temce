from __future__ import annotations


def calculate_avg_real_buy_per_capita(real_buy_value: float, real_buy_count: float) -> float:
    return real_buy_value / real_buy_count if real_buy_count else 0.0


def calculate_avg_real_sell_per_capita(real_sell_value: float, real_sell_count: float) -> float:
    return real_sell_value / real_sell_count if real_sell_count else 0.0


def calculate_buyer_power_ratio(
    real_buy_value: float,
    real_buy_count: float,
    real_sell_value: float,
    real_sell_count: float,
) -> float:
    buy_cap = real_buy_value / real_buy_count if real_buy_count else 0.0
    sell_cap = real_sell_value / real_sell_count if real_sell_count else 0.0
    if sell_cap == 0:
        return float("inf")
    return buy_cap / sell_cap


def calculate_net_real_money_flow(real_buy_value: float, real_sell_value: float) -> float:
    return real_buy_value - real_sell_value


def calculate_normalized_real_flow(net_real_flow: float, free_float_market_cap: float) -> float:
    return net_real_flow / free_float_market_cap if free_float_market_cap else 0.0


def calculate_ownership_change(ownership_t: float, ownership_t_minus_1: float) -> float:
    return ownership_t - ownership_t_minus_1


def calculate_ownership_hhi(ownership_shares_list: list[float]) -> float:
    return sum(s**2 for s in ownership_shares_list)


def calculate_supply_absorption_score(sell_pressure: float, return_t: float, epsilon: float = 1e-10) -> float:
    denom = abs(return_t) + epsilon
    return sell_pressure / denom if denom else 0.0


def calculate_supply_dryness(volume_t: float, avg_volume_20: float) -> float:
    return 1.0 - (volume_t / avg_volume_20) if avg_volume_20 else 0.0


def calculate_correction_dryness_ratio(mean_volume_down_days: float, mean_volume_up_days: float) -> float:
    return mean_volume_down_days / mean_volume_up_days if mean_volume_up_days else float("inf")


def calculate_distance_to_resistance(resistance_level: float, close_t: float) -> float:
    return (resistance_level - close_t) / resistance_level if resistance_level else 0.0


def calculate_resistance_touches(high_series: list[float], resistance_level: float, delta: float = 0.03) -> int:
    return sum(1 for h in high_series if abs(h - resistance_level) / resistance_level < delta)


def calculate_breakout_quality(
    z_rvol: float,
    z_clv: float,
    z_rs: float,
    z_dist_res: float,
    w1: float = 0.35,
    w2: float = 0.25,
    w3: float = 0.25,
    w4: float = 0.15,
) -> float:
    return w1 * z_rvol + w2 * z_clv + w3 * z_rs - w4 * z_dist_res


def calculate_breakout_acceptance(future_close_series: list[float], resistance_level: float) -> float:
    if not future_close_series:
        return 0.0
    above = sum(1 for c in future_close_series if c > resistance_level)
    return above / len(future_close_series)
