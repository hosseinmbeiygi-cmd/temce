from __future__ import annotations


def calculate_stock_market_score(
    z_rvol: float,
    z_bpr: float,
    z_net_real_flow: float,
    z_clv: float,
    z_rs: float,
    z_abs: float,
    z_illiq: float,
    w1: float = 0.20,
    w2: float = 0.18,
    w3: float = 0.16,
    w4: float = 0.14,
    w5: float = 0.12,
    w6: float = 0.10,
    w7: float = 0.10,
) -> float:
    return w1 * z_rvol + w2 * z_bpr + w3 * z_net_real_flow + w4 * z_clv + w5 * z_rs + w6 * z_abs - w7 * z_illiq
