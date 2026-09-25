"""API endpoints for options trading strategies."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from schemas.api.options import PayoffCalculatorRequest
from schemas.common.responses import ApiResponse
from services.options_analytics import get_arbitrage_detector, get_portfolio_analyzer, get_volatility_analyzer
from services.options_reference import (
    COMMON_MISTAKES,
    COURSE_SYLLABUS,
    GLOSSARY,
    IRAN_MARKET_RULES,
    IRAN_OPTIONS_STATS,
    IRANIAN_EXAMPLES,
    KEY_FORMULAS,
    REFERENCES,
    STRATEGY_SELECTION_GUIDE,
)
from services.options_service import get_options_engine

router = APIRouter()


class AnalyzeRequest(BaseModel):
    strategy: str
    stock_price: float = 1000
    strike: float = 1000
    call_premium: float = 50
    put_premium: float = 30
    call_strike: float = 1100
    put_strike: float = 900
    shares: int = 1000


class RecommendRequest(BaseModel):
    market_condition: str = "neutral"
    risk_tolerance: float = 0.5


@router.get("/strategies", summary="List all options strategies")
async def list_strategies() -> ApiResponse[list[dict[str, Any]]]:
    engine = get_options_engine()
    return ApiResponse(success=True, data=engine.get_all_strategies())


@router.post("/analyze", summary="Analyze an options strategy")
async def analyze_strategy(body: AnalyzeRequest) -> ApiResponse[dict[str, Any]]:
    engine = get_options_engine()
    try:
        method_name = f"analyze_{body.strategy}"
        method = getattr(engine, method_name, None)
        if not method:
            return ApiResponse(success=False, error={"message": f"Strategy '{body.strategy}' not found"})

        # Build kwargs based on strategy
        kwargs: dict[str, Any] = {"stock_price": body.stock_price}
        if body.strategy in ("covered_call", "married_put"):
            kwargs.update({"shares": body.shares})
        if "call" in body.strategy or body.strategy in ("straddle", "strangle", "long_gut", "conversion", "strip", "strap", "collar", "calendar_spread", "ratio_spread", "call_back_spread"):
            kwargs["call_premium"] = body.call_premium
        if "put" in body.strategy or body.strategy in ("straddle", "strangle", "long_gut", "conversion", "strip", "strap", "collar", "calendar_spread", "ratio_spread", "put_back_spread"):
            kwargs["put_premium"] = body.put_premium

        if body.strategy == "covered_call":
            kwargs.update({"strike": body.strike, "premium": body.call_premium})
        elif body.strategy == "married_put":
            kwargs.update({"put_strike": body.put_strike, "put_premium": body.put_premium})
        elif body.strategy == "collar":
            kwargs.update({"put_strike": body.put_strike, "put_premium": body.put_premium,
                           "call_strike": body.call_strike, "call_premium": body.call_premium})
        elif body.strategy == "long_straddle" or body.strategy == "short_straddle":
            kwargs.update({"strike": body.strike})
        elif body.strategy == "long_strangle" or body.strategy == "short_strangle":
            kwargs.update({"call_strike": body.call_strike, "put_strike": body.put_strike})
        elif body.strategy == "bull_call_spread" or body.strategy == "bear_call_spread":
            kwargs.update({"lower_strike": body.strike, "upper_strike": body.call_strike,
                           "lower_premium": body.call_premium, "upper_premium": body.put_premium})
        elif body.strategy == "bull_put_spread" or body.strategy == "bear_put_spread":
            kwargs.update({"higher_strike": body.strike, "lower_strike": body.put_strike,
                           "higher_premium": body.put_premium, "lower_premium": body.call_premium})
        elif body.strategy == "strip" or body.strategy == "strap":
            kwargs.update({"strike": body.strike})
        elif body.strategy == "long_gut":
            kwargs.update({"call_strike": body.strike, "put_strike": body.put_strike})

        result = method(**kwargs)
        data = {
            "strategy_name": result.strategy_name,
            "strategy_name_fa": result.strategy_name_fa,
            "legs": result.legs,
            "max_profit": result.max_profit,
            "max_loss": result.max_loss,
            "break_even": result.break_even,
            "initial_cost": result.initial_cost,
            "profit_at_expiry": result.profit_at_expiry,
            "market_condition": result.market_condition,
            "risk_level": result.risk_level,
            "description": result.description,
            "description_fa": result.description_fa,
            "best_for": result.best_for,
            "example": result.example,
        }
        return ApiResponse(success=True, data=data)
    except Exception as e:
        return ApiResponse(success=False, error={"message": str(e)})


@router.post("/recommend", summary="Recommend strategies based on market condition")
async def recommend_strategies(body: RecommendRequest) -> ApiResponse[list[dict[str, Any]]]:
    engine = get_options_engine()
    results = engine.recommend(body.market_condition, body.risk_tolerance)
    return ApiResponse(success=True, data=results)


def _missing_inputs(S: float, K: float, T: float, r: float | None, sigma: float | None) -> list[str]:
    """Which Black-Scholes inputs the caller did not supply.

    ``r`` and ``sigma`` used to default to ۱۵٪ and ۳۵٪, so a price came back for anybody who
    asked with no idea of the rate or the implied volatility. An invented volatility is the
    whole option price, so the calculator now refuses instead of guessing.
    """

    out: list[str] = []
    if not S or S <= 0:
        out.append("قیمت underlying (S)")
    if not K or K <= 0:
        out.append("قیمت اعمال (K)")
    if T is None or T <= 0:
        out.append("زمان تا سررسید بر حسب سال (T)")
    if r is None:
        out.append("نرخ بدون ریسک (r)")
    if sigma is None:
        out.append("نوسان ضمنی (sigma)")
    return out


def _need_inputs(missing: list[str]) -> str:
    return "بدون این ورودی‌ها عددی محاسبه نمی‌شود: " + "، ".join(missing)


@router.get("/greeks", summary="Calculate Greeks for an option")
async def calculate_greeks(
    S: float, K: float, T: float, r: float | None = None, sigma: float | None = None,
    option_type: str = "call"
) -> ApiResponse[dict[str, Any]]:
    missing = _missing_inputs(S, K, T, r, sigma)
    if missing:
        return ApiResponse[dict[str, Any]](success=False, error={"message": _need_inputs(missing)})
    from domain.options.pricing import black_scholes_price
    result = black_scholes_price(S, K, T, float(r), float(sigma), option_type)
    return ApiResponse(success=True, data={
        "price": result.price,
        "delta": result.delta,
        "gamma": result.gamma,
        "theta": result.theta,
        "vega": result.vega,
        "rho": result.rho,
        "intrinsic_value": result.intrinsic_value,
        "time_value": result.time_value,
        "inputs": {"S": S, "K": K, "T": T, "r": r, "sigma": sigma, "type": option_type},
    })


@router.get("/pricing", summary="Black-Scholes pricing for call and put")
async def pricing(
    S: float, K: float, T: float, r: float | None = None, sigma: float | None = None
) -> ApiResponse[dict[str, Any]]:
    missing = _missing_inputs(S, K, T, r, sigma)
    if missing:
        return ApiResponse[dict[str, Any]](success=False, error={"message": _need_inputs(missing)})
    from domain.options.pricing import black_scholes_call, black_scholes_put
    call_price = black_scholes_call(S, K, T, float(r), float(sigma))
    put_price = black_scholes_put(S, K, T, float(r), float(sigma))
    return ApiResponse(success=True, data={
        "call_price": round(call_price, 2),
        "put_price": round(put_price, 2),
        "parameters": {"S": S, "K": K, "T": T, "r": r, "sigma": sigma},
    })


# ── Payoff engine endpoints ─────────────────────────────────────────────────────

@router.post("/payoff-calculator", summary="Payoff curve, break-even points and max profit/loss")
async def payoff_calculator(body: PayoffCalculatorRequest) -> ApiResponse[dict[str, Any]]:
    from domain.options.payoff import (
        OptionLeg,
        build_payoff_curve,
        find_break_even_points,
        find_max_profit_loss,
    )

    try:
        legs = [
            OptionLeg(
                type=leg.type,
                action=leg.action,
                strike=leg.strike,
                premium=leg.premium,
                quantity=leg.quantity,
            )
            for leg in body.legs
        ]
        price_min = body.price_range.min
        price_max = body.price_range.max
        price_step = body.price_range.step
        curve = build_payoff_curve(legs, price_min, price_max, price_step, body.contract_size)
        break_evens = find_break_even_points(legs, price_min, price_max, price_step, body.contract_size)
        extremes = find_max_profit_loss(legs, price_min, price_max, body.contract_size)
    except ValueError as exc:
        return ApiResponse(success=False, error={"message": str(exc)})

    return ApiResponse(success=True, data={
        "payoffCurve": curve,
        "breakEvenPoints": [round(point, 6) for point in break_evens],
        "maxProfit": extremes["max_profit"],
        "maxLoss": extremes["max_loss"],
        "maxProfitUnbounded": extremes["max_profit_unbounded"],
        "maxLossUnbounded": extremes["max_loss_unbounded"],
    })


# ── Reference / Knowledge Base endpoints ────────────────────────────────────────

@router.get("/reference/selection-guide", summary="Strategy selection guide")
async def selection_guide() -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(success=True, data=STRATEGY_SELECTION_GUIDE)


@router.get("/reference/mistakes", summary="Common mistakes and solutions")
async def common_mistakes() -> ApiResponse[list[dict[str, str]]]:
    return ApiResponse(success=True, data=COMMON_MISTAKES)


@router.get("/reference/glossary", summary="Options glossary (Persian-English)")
async def glossary() -> ApiResponse[list[dict[str, str]]]:
    return ApiResponse(success=True, data=GLOSSARY)


@router.get("/reference/references", summary="Books and resources")
async def references() -> ApiResponse[dict[str, list[str]]]:
    return ApiResponse(success=True, data=REFERENCES)


@router.get("/reference/examples", summary="Real examples from Iranian market")
async def iranian_examples() -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(success=True, data=IRANIAN_EXAMPLES)


@router.get("/reference/syllabus", summary="Course syllabus")
async def course_syllabus() -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(success=True, data=COURSE_SYLLABUS)


@router.get("/reference/iran-rules", summary="Iranian market rules for options")
async def iran_rules() -> ApiResponse[dict[str, Any]]:
    return ApiResponse(success=True, data=IRAN_MARKET_RULES)


@router.get("/reference/stats", summary="Iranian options market statistics")
async def iran_stats() -> ApiResponse[dict[str, Any]]:
    return ApiResponse(success=True, data=IRAN_OPTIONS_STATS)


@router.get("/reference/formulas", summary="Key formulas reference")
async def key_formulas() -> ApiResponse[dict[str, str]]:
    return ApiResponse(success=True, data=KEY_FORMULAS)


# ── Analytics endpoints ─────────────────────────────────────────────────────────

@router.get("/analytics/arbitrage/parity", summary="Check Put-Call Parity")
async def check_parity(
    call_price: float, put_price: float, stock_price: float,
    strike: float, time_to_expiry: float = 0.25
) -> ApiResponse[dict[str, Any]]:
    detector = get_arbitrage_detector()
    result = detector.check_put_call_parity(call_price, put_price, stock_price, strike, time_to_expiry)
    return ApiResponse(success=True, data=result)


@router.post("/analytics/arbitrage/scan", summary="Scan for arbitrage opportunities")
async def scan_arbitrage(
    options_chain: list[dict[str, Any]], stock_price: float
) -> ApiResponse[list[dict[str, Any]]]:
    detector = get_arbitrage_detector()
    opportunities = detector.detect_opportunities(options_chain, stock_price)
    return ApiResponse(success=True, data=[
        {
            "strategy": o.strategy,
            "description_fa": o.description_fa,
            "profit_potential": o.profit_potential,
            "risk_level": o.risk_level,
            "legs": o.legs,
        }
        for o in opportunities
    ])


@router.post("/analytics/volatility", summary="Analyze volatility surface")
async def analyze_volatility(
    options_chain: list[dict[str, Any]], stock_price: float,
    historical_vol: float = 0.35
) -> ApiResponse[dict[str, Any]]:
    analyzer = get_volatility_analyzer()
    result = analyzer.analyze(options_chain, stock_price, historical_vol)
    return ApiResponse(success=True, data=result)


@router.post("/analytics/portfolio", summary="Analyze options portfolio Greeks")
async def analyze_portfolio(
    positions: list[dict[str, Any]], stock_price: float
) -> ApiResponse[dict[str, Any]]:
    analyzer = get_portfolio_analyzer()
    result = analyzer.analyze_portfolio(positions, stock_price)
    return ApiResponse(success=True, data=result)


# ── Professional Tools endpoints ────────────────────────────────────────────────

class CostCalcRequest(BaseModel):
    entry_price: float
    exit_price: float
    quantity: int
    is_option: bool = True
    is_short: bool = False


class PositionSizingRequest(BaseModel):
    capital: float
    risk_per_trade_pct: float = 2.0
    max_loss_per_contract: float = 100
    option_type: str = "buy"


class IVRankRequest(BaseModel):
    current_iv: float
    iv_52w_high: float
    iv_52w_low: float


class ChainAnalysisRequest(BaseModel):
    options_chain: list[dict[str, Any]]
    stock_price: float


class ChecklistRequest(BaseModel):
    strategy: str
    stock_price: float
    strike: float


@router.post("/professional/costs", summary="Calculate realistic P&L with Iranian market costs")
async def calculate_costs(body: CostCalcRequest) -> ApiResponse[dict[str, Any]]:
    engine = get_options_engine()
    result = engine.calculate_realistic_costs(
        body.entry_price, body.exit_price, body.quantity,
        body.is_option, body.is_short
    )
    return ApiResponse(success=True, data=result)


@router.post("/professional/position-sizing", summary="Calculate position size")
async def position_sizing(body: PositionSizingRequest) -> ApiResponse[dict[str, Any]]:
    engine = get_options_engine()
    result = engine.calculate_position_size(
        body.capital, body.risk_per_trade_pct,
        body.max_loss_per_contract, body.option_type
    )
    return ApiResponse(success=True, data=result)


@router.post("/professional/iv-rank", summary="Calculate IV Rank")
async def iv_rank(body: IVRankRequest) -> ApiResponse[dict[str, Any]]:
    engine = get_options_engine()
    result = engine.calculate_iv_rank(body.current_iv, body.iv_52w_high, body.iv_52w_low)
    return ApiResponse(success=True, data=result)


@router.post("/professional/chain-analysis", summary="Analyze options chain")
async def chain_analysis(body: ChainAnalysisRequest) -> ApiResponse[dict[str, Any]]:
    engine = get_options_engine()
    result = engine.analyze_options_chain(body.options_chain, body.stock_price)
    return ApiResponse(success=True, data=result)


@router.post("/professional/checklist", summary="Pre-trade checklist")
async def trade_checklist(body: ChecklistRequest) -> ApiResponse[list[dict[str, Any]]]:
    engine = get_options_engine()
    result = engine.generate_trade_checklist(body.strategy, body.stock_price, body.strike)
    return ApiResponse(success=True, data=result)


@router.get("/live/chain/{underlying}", summary="Live options chain from database")
async def live_options_chain(underlying: str, limit: int = 50) -> ApiResponse[dict[str, Any]]:
    """Get live options chain data from brsapi_option_snapshots."""
    from sqlalchemy import text

    from core.database import async_session_factory

    if async_session_factory is None:
        return ApiResponse(success=False, error={"message": "Database not connected"})

    async with async_session_factory() as session:
        r = await session.execute(text("""
            SELECT symbol, name, option_type, strike_price, price_last,
                   trade_volume, open_interest, days_remaining,
                   underlying_price_last, price_first, price_max, price_min,
                   bid_price_1, ask_price_1, trade_count, trade_value
            FROM brsapi_option_snapshots
            WHERE underlying_symbol = :underlying
              AND trade_volume > 0 AND price_last > 0
            ORDER BY trade_volume DESC
            LIMIT :limit
        """), {"underlying": underlying, "limit": limit})
        rows = r.fetchall()

    calls = []
    puts = []
    underlying_price = 0

    for row in rows:
        opt = {
            "symbol": row[0], "name": row[1], "type": row[2],
            "strike": row[3], "price": row[4], "volume": row[5],
            "oi": row[6], "days_to_expiry": row[7],
            "underlying_price": row[8], "open": row[9],
            "high": row[10], "low": row[11],
            "bid": row[12], "ask": row[13],
            "trades": row[14], "value": row[15],
        }
        if not underlying_price and row[8]:
            underlying_price = row[8]
        if row[2] == "call":
            calls.append(opt)
        else:
            puts.append(opt)

    # Sort by strike
    calls.sort(key=lambda x: x["strike"])
    puts.sort(key=lambda x: x["strike"], reverse=True)

    # Chain analysis
    engine_svc = get_options_engine()
    chain_data = [{"type": c["type"], "strike": c["strike"], "price": c["price"],
                   "volume": c["volume"], "open_interest": c["oi"]} for c in calls + puts]
    analysis = engine_svc.analyze_options_chain(chain_data, underlying_price) if underlying_price else {}

    return ApiResponse(success=True, data={
        "underlying": underlying,
        "underlying_price": underlying_price,
        "calls": calls,
        "puts": puts,
        "total_contracts": len(calls) + len(puts),
        "analysis": analysis,
    })


@router.get("/live/symbols", summary="List symbols with active options")
async def live_symbols() -> ApiResponse[list[dict[str, Any]]]:
    """Get list of underlying symbols that have active options."""
    from sqlalchemy import text

    from core.database import async_session_factory

    if async_session_factory is None:
        return ApiResponse(success=False, error={"message": "Database not connected"})

    async with async_session_factory() as session:
        r = await session.execute(text("""
            SELECT underlying_symbol,
                   count(*) as contract_count,
                   SUM(trade_volume) as total_volume,
                   MAX(underlying_price_last) as underlying_price
            FROM brsapi_option_snapshots
            WHERE trade_volume > 0 AND price_last > 0
            GROUP BY underlying_symbol
            ORDER BY SUM(trade_volume) DESC
        """))
        rows = r.fetchall()

    symbols = []
    for row in rows:
        symbols.append({
            "symbol": row[0],
            "contracts": row[1],
            "volume": row[2],
            "price": row[3],
        })

    return ApiResponse(success=True, data=symbols)


# ── IME commodity options (gold / saffron) with Black-76 ─────────────────────

#: Known IME commodity codes (contract_category_commodity). Saffron trades
#: under "ZR" on the IME options board; unknown codes are still queryable.
IME_COMMODITIES = ("GoldBar", "ZR", "SilverBar", "KA", "DG", "CU", "JZ", "NQ", "LG ETC")


@router.get("/live/commodities", summary="List IME commodities with options")
async def live_commodities() -> ApiResponse[list[dict[str, Any]]]:
    """Distinct ``contract_category_commodity`` values with contract counts."""
    from sqlalchemy import text

    from core.database import async_session_factory

    if async_session_factory is None:
        return ApiResponse(success=False, error={"message": "Database not connected"})

    async with async_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT contract_category_commodity, COUNT(*) "
                    "FROM brsapi_ime_options "
                    "WHERE contract_category_commodity IS NOT NULL "
                    "GROUP BY 1 ORDER BY 2 DESC"
                )
            )
        ).fetchall()

    return ApiResponse(success=True, data=[
        {"commodity": r[0], "contracts": r[1]} for r in rows
    ])


@router.get("/live/commodity-chain", summary="IME commodity options chain (Black-76)")
async def live_commodity_chain(
    commodity: str = "GoldBar",
    forward_price: float | None = None,
    iv: float = 0.30,
    rate: float = 0.25,
    limit: int = 50,
) -> ApiResponse[dict[str, Any]]:
    """Options chain for an IME commodity (gold, saffron/ZR, …) from ``brsapi_ime_options``.

    Each leg carries the market quote plus the Black-76 theoretical price
    and delta. ``forward_price`` defaults to the ATM proxy (median strike)
    when no futures forward is supplied — reported via ``forward_source``.
    """
    from sqlalchemy import text

    from core.database import async_session_factory

    if async_session_factory is None:
        return ApiResponse(success=False, error={"message": "Database not connected"})

    async with async_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT strike_price, call_contract_code, call_price_last, "
                    "call_trade_volume, call_open_interest, call_days_remaining, "
                    "call_bid_price_1, call_ask_price_1, "
                    "put_contract_code, put_price_last, put_trade_volume, "
                    "put_open_interest, put_days_remaining, "
                    "put_bid_price_1, put_ask_price_1 "
                    "FROM brsapi_ime_options "
                    "WHERE contract_category_commodity = :c "
                    "AND strike_price IS NOT NULL AND strike_price > 0 "
                    "ORDER BY fetched_at DESC, strike_price ASC "
                    "LIMIT :n"
                ),
                {"c": commodity, "n": limit * 2},
            )
        ).fetchall()

    # Latest snapshot per strike (one row per strike).
    by_strike: dict[float, Any] = {}
    for r in rows:
        k = float(r[0])
        by_strike.setdefault(k, r)
    strikes = sorted(by_strike)[:limit]

    from src.gold_desk.black76 import black76_greeks, black76_price

    if forward_price and forward_price > 0:
        forward, forward_source = float(forward_price), "query"
    elif strikes:
        forward = strikes[len(strikes) // 2]
        forward_source = "atm_proxy"
    else:
        return ApiResponse(success=True, data={
            "commodity": commodity, "forward": 0.0, "forward_source": "none",
            "calls": [], "puts": [], "total_contracts": 0, "model": "black76",
        })

    def _leg(row: Any, side: str) -> dict[str, Any]:
        # Row layout: 0 strike, 1-7 call fields, 8-14 put fields.
        base = 8 if side == "put" else 1
        days = row[base + 4] or row[5] or 30
        t = max(float(days) / 365.0, 1e-6)
        k = float(row[0])
        try:
            call_px, put_px, _, _ = black76_price(forward, k, t, iv, rate)
            g = black76_greeks(forward, k, t, iv, rate)
            theo = call_px if side == "call" else put_px
            delta = float(g.delta) if side == "call" else float(g.delta - 1.0)
        except Exception:
            theo, delta = 0.0, 0.0
        return {
            "symbol": row[base], "type": side, "strike": k,
            "price": row[base + 1], "volume": row[base + 2], "oi": row[base + 3],
            "days_to_expiry": days, "bid": row[base + 5], "ask": row[base + 6],
            "theoretical": round(theo, 1), "delta": round(delta, 4),
        }

    calls = [_leg(by_strike[k], "call") for k in strikes]
    puts = sorted(
        (_leg(by_strike[k], "put") for k in strikes),
        key=lambda x: x["strike"], reverse=True,
    )
    return ApiResponse(success=True, data={
        "commodity": commodity, "forward": forward,
        "forward_source": forward_source, "model": "black76",
        "iv": iv, "rate": rate,
        "calls": calls, "puts": puts,
        "total_contracts": len(calls) + len(puts),
    })


@router.get("/professional/iran-costs", summary="Iranian market cost breakdown")
async def iran_costs() -> ApiResponse[dict[str, Any]]:
    engine = get_options_engine()
    return ApiResponse(success=True, data={
        "contract_size": engine.CONTRACT_SIZE,
        "commission_buy": f"{engine.COMMISSION_BUY * 100:.3f}%",
        "commission_sell": f"{engine.COMMISSION_SELL * 100:.4f}%",
        "commission_sell_note": "شامل ۰.۵٪ مالیات فروش + کارمزد کارگزاری",
        "settlement": f"T+{engine.SETTLEMENT_DAYS} (تسویه {engine.SETTLEMENT_DAYS} روز کاری)",
        "price_limit": f"±{engine.PRICE_LIMIT_PCT*100:.0f}% (سهام) / ±{engine.OPTION_PRICE_LIMIT_PCT*100:.0f}% (اختیار)",
        "option_style": "اروپایی (فقط در تاریخ سررسید قابل اعمال)",
        "min_capital": f"{engine.MIN_CAPITAL_RECOMMEND:,} تومان (توصیه شده)",
        "example_trade_cost": {
            "buy_option_500_toman": f"کارمزد خرید: {500 * 1000 * engine.COMMISSION_BUY:,.0f} تومان",
            "sell_option_800_toman": f"کارمزد فروش: {800 * 1000 * engine.COMMISSION_SELL:,.0f} تومان",
            "total_round_trip": f"هزینه رفت و برگشت: {(500 * engine.COMMISSION_BUY + 800 * engine.COMMISSION_SELL) * 1000:,.0f} تومان",
        },
    })
