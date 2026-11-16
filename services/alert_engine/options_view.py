"""Related options as an *analytical input* to the underlying (pure — no I/O).

Scope: descriptive only. Nothing here recommends buying or selling a contract, and public
volume / open interest are never read as participant direction, dealer inventory or
"dealer gamma". Four states are kept apart:

* ``none``        — the source lists no contract on this underlying identifier
* ``unavailable`` — the options feed could not be read
* ``stale``       — contracts exist but the latest fetch is too old to analyse
* ``available``   — fresh chain; per-contract values may still be individually unreliable
"""

from __future__ import annotations

from typing import Any

from domain.options.pricing import black_scholes_price, implied_volatility
from domain.trading.iran_costs import OPTION_BUY_PCT
from services.alert_engine.analytics import _num

MAX_IV_SPREAD_PCT = 20.0  # a quote wider than this is not a price; no IV is solved from it
MODEL_NOTE = (
    "Black–Scholes (European exercise, no dividends), T = days_remaining/365, flat assumed rate. "
    "Exercise style and settlement terms are not provided by the data source and are not verified."
)


def _contract(row: dict[str, Any], spot: float, rate: float) -> dict[str, Any]:
    kind = "put" if str(row.get("option_type") or "").lower().startswith("p") else "call"
    strike = _num(row.get("strike_price"))
    days = _num(row.get("days_remaining"))
    bid, ask = _num(row.get("bid_price_1")), _num(row.get("ask_price_1"))
    out: dict[str, Any] = {
        "symbol": row.get("symbol"), "type": kind, "strike": strike, "days_remaining": days,
        "expiry_jalali": row.get("date_end"), "contract_size": _num(row.get("contract_size")),
        "bid": bid if bid and bid > 0 else None, "ask": ask if ask and ask > 0 else None,
        "last": _num(row.get("price_last")), "volume": _num(row.get("trade_volume")) or 0.0,
        "open_interest": _num(row.get("open_interest")),
        "iv": None, "iv_reason": None, "greeks": None,
    }
    if not strike or strike <= 0 or spot <= 0:
        out["iv_reason"] = "strike or underlying price missing"
        return out
    out["moneyness"] = spot / strike
    intrinsic = max(spot - strike, 0.0) if kind == "call" else max(strike - spot, 0.0)
    out["intrinsic"] = intrinsic
    if not out["bid"] or not out["ask"]:
        out["iv_reason"] = "no two-sided quote"
        return out
    if out["ask"] < out["bid"]:
        out["iv_reason"] = "crossed quote"
        return out
    mid = (out["bid"] + out["ask"]) / 2
    out["mid"] = mid
    out["spread_pct"] = (out["ask"] - out["bid"]) / mid * 100
    out["time_value"] = mid - intrinsic
    fee = mid * OPTION_BUY_PCT
    out["breakeven_cost_adjusted"] = strike + mid + fee if kind == "call" else strike - mid - fee
    if out["spread_pct"] > MAX_IV_SPREAD_PCT:
        out["iv_reason"] = f"spread {out['spread_pct']:.0f}% too wide to treat mid as a price"
        return out
    if not days or days < 1:
        out["iv_reason"] = "at or past expiry"
        return out
    if mid <= intrinsic:
        out["iv_reason"] = "mid below intrinsic value (stale or non-arbitrage-free quote)"
        return out
    t = days / 365
    iv = implied_volatility(mid, spot, strike, t, rate, kind)
    if iv is None:
        out["iv_reason"] = "solver did not converge inside the no-arbitrage band"
        return out
    out["iv"] = iv
    px = black_scholes_price(spot, strike, t, rate, iv, kind)
    out["greeks"] = {"delta": px.delta, "gamma": px.gamma, "theta": px.theta, "vega": px.vega, "rho": px.rho}
    return out


def summarize(rows: list[dict[str, Any]] | None, *, spot: float | None, rate: float,
              feed_state: str, fetched_at: str | None = None, max_contracts: int = 40) -> dict[str, Any]:
    """``rows`` = latest row per contract for one underlying id; ``feed_state`` from coverage."""
    base = {"scope": "analytical input only — no options-trading recommendation",
            "fetched_at": fetched_at, "assumptions": {"risk_free_rate": rate, "model": MODEL_NOTE}}
    if feed_state == "unavailable" or rows is None:
        return {**base, "state": "unavailable", "summary": None, "contracts": []}
    if not rows:
        return {**base, "state": "none", "summary": None, "contracts": []}
    if feed_state == "stale":
        return {**base, "state": "stale", "summary": {"contracts_listed": len(rows)}, "contracts": []}
    if not spot or spot <= 0:
        return {**base, "state": "unavailable", "summary": {"contracts_listed": len(rows)},
                "contracts": [], "reason": "underlying price unavailable"}

    contracts = [_contract(r, spot, rate) for r in rows]
    calls = [c for c in contracts if c["type"] == "call"]
    puts = [c for c in contracts if c["type"] == "put"]

    def total(items: list[dict[str, Any]], key: str) -> float:
        return sum(c[key] or 0.0 for c in items)

    call_vol, put_vol = total(calls, "volume"), total(puts, "volume")
    call_oi, put_oi = total(calls, "open_interest"), total(puts, "open_interest")
    term: dict[Any, dict[str, Any]] = {}
    for c in contracts:
        if c["iv"] is None or c["days_remaining"] is None:
            continue
        best = term.get(c["days_remaining"])
        if best is None or abs(c["moneyness"] - 1) < abs(best["moneyness"] - 1):
            term[c["days_remaining"]] = c
    active = sorted((c for c in contracts if c["volume"] > 0 or (c["open_interest"] or 0) > 0),
                    key=lambda c: (c["days_remaining"] or 0, c["strike"] or 0))
    expiries = sorted({c["days_remaining"] for c in contracts if c["days_remaining"] is not None})
    return {
        **base, "state": "available",
        "summary": {
            "contracts_listed": len(contracts), "calls": len(calls), "puts": len(puts),
            "contracts_active": len(active), "contracts_with_reliable_iv": sum(c["iv"] is not None for c in contracts),
            "nearest_expiry_days": expiries[0] if expiries else None, "expiries_days": expiries[:12],
            "call_volume": call_vol, "put_volume": put_vol, "call_open_interest": call_oi, "put_open_interest": put_oi,
            "put_call_volume_ratio": put_vol / call_vol if call_vol > 0 else None,
            "put_call_oi_ratio": put_oi / call_oi if call_oi > 0 else None,
            "ratio_note": "descriptive only — volume and open interest do not reveal who is long or short",
            "atm_iv_term_structure": [{"days": d, "iv": term[d]["iv"], "strike": term[d]["strike"], "contract": term[d]["symbol"]}
                                      for d in sorted(term)],
        },
        "contracts": active[:max_contracts],
        "contracts_truncated": max(0, len(active) - max_contracts),
    }
