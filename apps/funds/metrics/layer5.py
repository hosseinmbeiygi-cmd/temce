"""لایه ۵: شاخص‌های اختصاصی بازار ایران (۱۸ شاخص)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .helpers import beta_to_market, correlation, percentile_rank


def compute_layer5(
    *,
    nav_returns: Sequence[float] | None,
    fx_nima_returns: Sequence[float] | None,
    fx_azad_returns: Sequence[float] | None,
    cpi_returns: Sequence[float] | None,
    interbank_rate_changes: Sequence[float] | None,
    duration_years: float | None,
    gold_world_returns: Sequence[float] | None,
    silver_world_returns: Sequence[float] | None,
    saffron_returns: Sequence[float] | None,
    peer_returns: Sequence[float] | None,
    peer_bubbles: Sequence[float] | None,
    self_bubble: float | None,
    volume_to_aum: float | None,
    order_book_depth: float | None,
    esfand_monthly_returns: Sequence[float] | None,
    khordad_monthly_returns: Sequence[float] | None,
    ramadan_monthly_returns: Sequence[float] | None,
    geopolitical_event_returns: Sequence[float] | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "fx_beta_nima": None,
        "fx_beta_azad": None,
        "inflation_beta": None,
        "real_return": None,
        "geopolitical_sensitivity": None,
        "calendar_esfand": None,
        "calendar_khordad": None,
        "calendar_ramadan": None,
        "interbank_rate_beta": None,
        "duration_years": duration_years,
        "gold_world_corr": None,
        "silver_world_corr": None,
        "saffron_corr": None,
        "peer_correlation": None,
        "pnav_peer_percentile": None,
        "liquidity_score": None,
        "order_book_depth": order_book_depth,
    }

    if nav_returns and fx_nima_returns:
        out["fx_beta_nima"] = beta_to_market(nav_returns, fx_nima_returns)
    if nav_returns and fx_azad_returns:
        out["fx_beta_azad"] = beta_to_market(nav_returns, fx_azad_returns)
    if nav_returns and cpi_returns:
        out["inflation_beta"] = beta_to_market(nav_returns, cpi_returns)
        if len(nav_returns) == len(cpi_returns):
            real = [(1 + n) / (1 + c) - 1 for n, c in zip(nav_returns, cpi_returns, strict=False)]
            out["real_return"] = sum(real) / len(real)

    if nav_returns and interbank_rate_changes and len(nav_returns) == len(interbank_rate_changes):
        out["interbank_rate_beta"] = beta_to_market(nav_returns, interbank_rate_changes)

    if nav_returns and gold_world_returns:
        out["gold_world_corr"] = correlation(nav_returns, gold_world_returns)
    if nav_returns and silver_world_returns:
        out["silver_world_corr"] = correlation(nav_returns, silver_world_returns)
    if nav_returns and saffron_returns:
        out["saffron_corr"] = correlation(nav_returns, saffron_returns)

    if nav_returns and peer_returns:
        out["peer_correlation"] = correlation(nav_returns, peer_returns)

    if peer_bubbles and self_bubble is not None:
        out["pnav_peer_percentile"] = percentile_rank(self_bubble, peer_bubbles)

    if volume_to_aum is not None:
        out["liquidity_score"] = min(1.0, volume_to_aum / 0.05)

    if esfand_monthly_returns:
        out["calendar_esfand"] = sum(esfand_monthly_returns) / len(esfand_monthly_returns)
    if khordad_monthly_returns:
        out["calendar_khordad"] = sum(khordad_monthly_returns) / len(khordad_monthly_returns)
    if ramadan_monthly_returns:
        out["calendar_ramadan"] = sum(ramadan_monthly_returns) / len(ramadan_monthly_returns)

    if geopolitical_event_returns:
        out["geopolitical_sensitivity"] = sum(geopolitical_event_returns) / len(geopolitical_event_returns)

    return out
