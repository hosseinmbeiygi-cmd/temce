"""Gold ETF/ Mutual fund P/NAV analytics — pure engine.

Single source of truth for fund-level premium/discount, historical percentile,
real-vs-legal net flow, abnormal-discount flag, and halted / price-band handling.

All public functions are pure (no DB, no I/O) so the service layer can back them
with provider data and the regression suite can test them deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.gold.calculator import calculate_nav_premium

# Gold funds that trade on Iran's exchanges normally have a parsed price band
# (no-arbitrage corridor) published by the exchange. We mirror that concept here
# as an explicit struct so the engine can reject out-of-band prices instead of
# silently treating stale quotes as live.
FUND_BAND_TOLERANCE_BPS: int = 50  # 0.50% corridor around band edges
FUND_BAND_STALE_AGE_DAYS: int = 5  # band older than this => treat as missing

DISCOUNT_ABNORMAL_BPS: int = 300  # 3.00% below NAV => abnormal flag

# ── Data model for one fund snapshot ───────────────────────────────────────────

FUND_PROVIDER_FIELDS: dict[str, str] = {
    "symbol": " fund unique symbol (e.g. TSE:atm / CCE:...). "
    "Supplied by BrsApi / DB snapshot.",
    "fund_name": "display name of the fund.",
    "nav_per_unit": "Net asset value per unit (IRR). "
    "From brsapi_nav_records.nav_issue / nav_redemption (GS-01 fix).",
    "market_price": "Last traded price (IRR). "
    "From price band, BrsApi quote, or gold_snapshots market_price. "
    "None when halted / missing.",
    "price_band_low": "Lower bound of exchange price band (IRR). "
    "None when band not provided or stale.",
    "price_band_high": "Upper bound of exchange price band (IRR). "
    "None when band not provided or stale.",
    "band_stale_since": "Date the band was last refreshed, or None when fresh.",
    "halted": "bool — fund trading is halted by the exchange.",
    "real_buy_volume": "Real (الحقیقی) buy value (IRR) in latest reporting period.",
    "real_sell_volume": "Real sell value (IRR) in latest reporting period.",
    "legal_buy_volume": "Legal (قانونی) buy value (IRR)."
    " Used for real-vs-legal net flow; None when unavailable.",
    "legal_sell_volume": "Legal sell value (IRR)."
    " None when unavailable.",
    "nav_history": "list of dicts {date, nav} for percentile computation."
    " Sorted oldest-to-newest.",
}

# ── Data feasibility note ──────────────────────────────────────────────────────
# The DB/BrsApi surfaces we can currently reach:
#   - nav:  brsapi_nav_records.nav_issue, nav_redemption (pick non-null).
#   - real/legal buy-sell volumes: brsapi_tse_legal_stats / historical_real_legal
#     (real_buy_value, sell_real_value). Legal side may be None for some funds.
#   - halt status / price band: NOT currently available via any provider or DB
#     table in this codebase. We model the field with a mock-backed interface and
#   mark it BLOCKED BY DATA below.
#
#   If nav is missing for a fund, the engine treats the fund as BLOCKED for
#   P/NAV (no synthetic NAV). If market_price is missing (halt / no quote),
#   premium/discount is reported as None and abnormal-discount stays False.
# ──────────────────────────────────────────────────────────────────────────────


# ── Pure value objects ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class FundPremiumResult:
    symbol: str
    fund_name: str
    nav_per_unit: float
    market_price: float | None
    premium_pct: float | None
    signal: str  # BUY | SELL | NEUTRAL | N/A
    reason: str


@dataclass(frozen=True)
class FundPercentileResult:
    symbol: str
    nav: float
    percentile: float  # 0..100 current nav vs hist nav
    hist_min: float
    hist_max: float
    hist_median: float
    hist_count: int


@dataclass(frozen=True)
class FundFlowResult:
    symbol: str
    real_buy_volume: float
    real_sell_volume: float
    real_net_flow: float
    legal_buy_volume: float | None
    legal_sell_volume: float | None
    legal_net_flow: float | None
    flow_call: str  # INFLOW | OUTFLOW | NEUTRAL | UNKNOWN


@dataclass(frozen=True)
class FundHealthFlags:
    halted: bool
    band_missing: bool
    price_out_of_band: bool
    abnormal_discount: bool
    notes: list[str]


@dataclass(frozen=True)
class FundAnalyticsRow:
    """One row returned by the ranking endpoint."""

    symbol: str
    fund_name: str
    nav_per_unit: float
    market_price: float | None
    premium_pct: float | None
    signal: str
    percentile: float | None
    real_net_flow: float | None
    flow_call: str
    health: FundHealthFlags
    halted: bool
    band_missing: bool


# ── Pure math functions ────────────────────────────────────────────────────────


def fund_premium(
    symbol: str,
    fund_name: str,
    nav_per_unit: float,
    market_price: float | None,
) -> FundPremiumResult:
    """Premium/discount of one fund vs its NAV.

    Pure. Rejects non-positive NAV; tolerates missing market price (returns N/A).
    """
    if nav_per_unit <= 0:
        raise ValueError(f"{symbol}: nav_per_unit must be > 0, got {nav_per_unit}")

    if market_price is None or market_price <= 0:
        return FundPremiumResult(
            symbol=symbol,
            fund_name=fund_name,
            nav_per_unit=nav_per_unit,
            market_price=market_price,
            premium_pct=None,
            signal="N/A",
            reason="market price unavailable (halt / no quote)",
        )

    prem = calculate_nav_premium(market_price, nav_per_unit)
    return FundPremiumResult(
        symbol=symbol,
        fund_name=fund_name,
        nav_per_unit=nav_per_unit,
        market_price=market_price,
        premium_pct=prem.premium_pct,
        signal=prem.signal,
        reason=prem.reason,
    )


def fund_percentile(nav: float, nav_history: list[dict[str, Any]]) -> FundPercentileResult:
    """Current NAV percentile against a historical NAV series.

    Pure. Requires at least one historical point. Empty history => zero-count row.
    """
    if nav <= 0:
        raise ValueError(f"nav must be > 0, got {nav}")
    if not nav_history:
        return FundPercentileResult(
            symbol="", nav=nav, percentile=0.0,
            hist_min=nav, hist_max=nav, hist_median=nav, hist_count=0,
        )

    series = [float(h["nav"]) for h in nav_history if h and h.get("nav") is not None]
    if not series:
        return FundPercentileResult(
            symbol="", nav=nav, percentile=0.0,
            hist_min=nav, hist_max=nav, hist_median=nav, hist_count=0,
        )

    sorted_series = sorted(series)
    below = sum(1 for v in sorted_series if v <= nav)
    percentile = (below / len(sorted_series)) * 100.0
    n = len(sorted_series)
    mid = n // 2
    hist_median = sorted_series[mid] if n % 2 == 1 else (
        (sorted_series[mid - 1] + sorted_series[mid]) / 2.0
    )
    return FundPercentileResult(
        symbol="",
        nav=nav,
        percentile=round(percentile, 2),
        hist_min=min(sorted_series),
        hist_max=max(sorted_series),
        hist_median=hist_median,
        hist_count=n,
    )


def fund_net_flow(
    symbol: str,
    real_buy_volume: float,
    real_sell_volume: float,
    legal_buy_volume: float | None = None,
    legal_sell_volume: float | None = None,
) -> FundFlowResult:
    """Real-vs-legal net flow for one fund.

    Pure. Prefers real volumes when available; falls back to legal when real is
    absent. Unknown flow when both legs missing.
    """
    real_net = real_buy_volume - real_sell_volume
    if real_buy_volume or real_sell_volume:
        flow_call = "INFLOW" if real_net > 0 else ("OUTFLOW" if real_net < 0 else "NEUTRAL")
    elif legal_buy_volume is not None or legal_sell_volume is not None:
        legal_net = (legal_buy_volume or 0) - (legal_sell_volume or 0)
        real_buy_volume = legal_buy_volume or 0.0
        real_sell_volume = legal_sell_volume or 0.0
        real_net = legal_net
        flow_call = "INFLOW" if legal_net > 0 else ("OUTFLOW" if legal_net < 0 else "NEUTRAL")
    else:
        flow_call = "UNKNOWN"

    return FundFlowResult(
        symbol=symbol,
        real_buy_volume=float(real_buy_volume or 0),
        real_sell_volume=float(real_sell_volume or 0),
        real_net_flow=float(real_net),
        legal_buy_volume=legal_buy_volume,
        legal_sell_volume=legal_sell_volume,
        legal_net_flow=(legal_buy_volume or 0) - (legal_sell_volume or 0)
        if legal_buy_volume is not None or legal_sell_volume is not None
        else None,
        flow_call=flow_call,
    )


def fund_health_flags(
    symbol: str,
    halted: bool,
    market_price: float | None,
    nav_per_unit: float,
    price_band_low: float | None,
    price_band_high: float | None,
    band_stale_since: Any = None,
) -> FundHealthFlags:
    """Health / data-quality flags for a fund row.

    Pure. Detects halted, missing/stale band, price outside band, and abnormal
    discount vs NAV. Reports notes for downstream alerting.
    """
    notes: list[str] = []
    band_missing = price_band_low is None or price_band_high is None
    band_stale = band_stale_since is not None
    if band_missing:
        notes.append(f"{symbol}: price band not available")
    if band_stale:
        notes.append(f"{symbol}: price band stale since {band_stale_since}")
    price_out_of_band = False
    if market_price and not band_missing:
        low, high = float(price_band_low), float(price_band_high)
        if market_price < low or market_price > high:
            price_out_of_band = True
            notes.append(
                f"{symbol}: price {market_price:.2f} outside band "
                f"[{low:.2f}, {high:.2f}]"
            )
    abnormal_discount = False
    if market_price and nav_per_unit > 0 and market_price < nav_per_unit:
        discount_bps = (nav_per_unit - market_price) / nav_per_unit * 10000.0
        if discount_bps >= DISCOUNT_ABNORMAL_BPS:
            abnormal_discount = True
            notes.append(f"{symbol}: discount {discount_bps/100:.2f}% >= 3.00% threshold")
    return FundHealthFlags(
        halted=halted,
        band_missing=band_missing or band_stale,
        price_out_of_band=price_out_of_band,
        abnormal_discount=abnormal_discount,
        notes=notes,
    )


def build_fund_row(
    symbol: str,
    fund_name: str,
    nav_per_unit: float,
    market_price: float | None,
    nav_history: list[dict[str, Any]],
    real_buy_volume: float,
    real_sell_volume: float,
    legal_buy_volume: float | None = None,
    legal_sell_volume: float | None = None,
    halted: bool = False,
    price_band_low: float | None = None,
    price_band_high: float | None = None,
    band_stale_since: Any = None,
) -> FundAnalyticsRow:
    """Combine premium, percentile, flow and health into one ranking row.

    Pure. This is the unit of work the ranking endpoint sorts.
    """
    prem = fund_premium(symbol, fund_name, nav_per_unit, market_price)
    percentile = None
    if nav_history:
        pct = fund_percentile(nav_per_unit, nav_history)
        percentile = pct.percentile
    flow = fund_net_flow(symbol, real_buy_volume, real_sell_volume,
                         legal_buy_volume, legal_sell_volume)
    health = fund_health_flags(
        symbol, halted, market_price, nav_per_unit,
        price_band_low, price_band_high, band_stale_since,
    )
    return FundAnalyticsRow(
        symbol=symbol,
        fund_name=fund_name,
        nav_per_unit=nav_per_unit,
        market_price=market_price,
        premium_pct=prem.premium_pct,
        signal=prem.signal,
        percentile=percentile,
        real_net_flow=flow.real_net_flow if flow.flow_call != "UNKNOWN" else None,
        flow_call=flow.flow_call,
        health=health,
        halted=health.halted,
        band_missing=health.band_missing,
    )


# ── Ranking / ordering helpers ────────────────────────────────────────────────


def discount_sort_key(row: FundAnalyticsRow) -> float:
    """Sort key for ranking by discount ascending (deepest discount first).

    Rows without a price have discount = +inf (shown last).
    """
    if row.premium_pct is None:
        return float("inf")
    return -row.premium_pct  # negative of premium = discount


def abnormal_discount_filter(rows: list[FundAnalyticsRow]) -> list[FundAnalyticsRow]:
    """Keep only rows flagged with abnormal discount (for alert generation)."""
    return [r for r in rows if r.health.abnormal_discount]


def halted_filter(rows: list[FundAnalyticsRow]) -> list[FundAnalyticsRow]:
    """Keep only halted rows (for monitoring)."""
    return [r for r in rows if r.halted]
