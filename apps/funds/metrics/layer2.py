"""لایه ۲: ریسک-بازده کلاسیک (۸ شاخص)."""

from __future__ import annotations

from .helpers import (
    beta_to_market,
    calmar_ratio,
    max_drawdown,
    safe_mean,
    safe_std,
    sharpe_ratio,
    sortino_ratio,
)


def daily_returns(nav_series: list[float]) -> list[float]:
    if len(nav_series) < 2:
        return []
    out: list[float] = []
    for i in range(1, len(nav_series)):
        prev = nav_series[i - 1]
        if prev > 0:
            out.append(nav_series[i] / prev - 1)
    return out


def compute_layer2(
    *,
    nav_series: list[float],
    market_returns: list[float] | None,
    risk_free: float = 0.0,
) -> dict[str, float | int | None]:
    rets = daily_returns(nav_series)
    out: dict[str, float | int | None] = {
        "sharpe": sharpe_ratio(rets, risk_free),
        "sortino": sortino_ratio(rets, risk_free),
        "calmar": None,
        "max_drawdown": None,
        "recovery_days": None,
        "beta": None,
        "std_dev": safe_std(rets),
        "info_ratio": None,
        "upside_capture": None,
        "downside_capture": None,
    }

    mdd, rec = max_drawdown(nav_series)
    out["max_drawdown"] = mdd
    out["recovery_days"] = rec

    if len(nav_series) >= 252:
        cagr = (nav_series[-1] / nav_series[0]) ** (252 / (len(nav_series) - 1)) - 1
        out["calmar"] = calmar_ratio(cagr, mdd)

    if market_returns and len(market_returns) == len(rets):
        out["beta"] = beta_to_market(rets, market_returns)
        m_sd = safe_std(market_returns)
        f_sd = out["std_dev"]
        if m_sd and f_sd and m_sd > 0:
            out["info_ratio"] = (safe_mean(rets) - safe_mean(market_returns)) / m_sd if m_sd > 0 else None

        up_f, up_m, dn_f, dn_m = [], [], [], []
        for f, m in zip(rets, market_returns, strict=False):
            if m > 0:
                up_f.append(f)
                up_m.append(m)
            elif m < 0:
                dn_f.append(f)
                dn_m.append(m)
        if up_m:
            out["upside_capture"] = safe_mean(up_f) / safe_mean(up_m) if safe_mean(up_m) else None
        if dn_m:
            out["downside_capture"] = safe_mean(dn_f) / safe_mean(dn_m) if safe_mean(dn_m) else None

    return out
