"""Strategy engine extensions for the Tehran options platform.

Spec reference: ``تکمیل-بخش-موتور-استراتژی.md`` (§7.2-7.8) and
``تکمیل-نهایی-موتور-استراتژی.md`` (§7.9-7.12).

Components
----------
- ``StrategyTemplateLibrary`` — parametric strategy templates with
  delta-targeted strike selection (§7.9).
- ``ChainLookup`` / ``InMemoryChainLookup`` — adapter over an option
  chain snapshot used by the templates.
- ``GreeksAggregator`` — per-strategy current value + greeks, stocks
  included (§7.2 GreeksAggregator).
- ``dual_payoff_curve`` — expiry payoff + current-value curve for the
  Strategy Builder live chart (§7.2 نمودار Payoff دوگانه).
- ``StrategyValidator`` — pre-trade validation (§7.10).
- ``AdjustmentEngine`` — roll / defend / delta-hedge suggestions (§7.6).
- ``StrategyLifecycleTracker`` — PROPOSED → CLOSED state machine (§7.7).
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Sequence

from domain.options.payoff import OptionLeg
from domain.options.pricing import black_scholes_price


# ── Chain lookup (§7.9 ChainLookup) ─────────────────────────────────────


@dataclass(frozen=True)
class ChainQuote:
    option_type: str  # "call" | "put"
    strike: float
    expiry: str  # ISO date string
    premium: float
    delta: float = 0.0
    open_interest: int = 0
    bid: float | None = None
    ask: float | None = None


class ChainLookup:
    """Interface the templates rely on; adapt any chain snapshot to this."""

    def quotes(self) -> Sequence[ChainQuote]:
        raise NotImplementedError

    def nearest_strike(self, target: float, option_type: str, expiry: str) -> float:
        raise NotImplementedError

    def nearest_expiry(self, target_dte: int) -> str:
        raise NotImplementedError

    def premium_of(self, strike: float, option_type: str, expiry: str) -> float:
        raise NotImplementedError

    def strike_for_delta(self, target_delta: float, option_type: str, expiry: str) -> float:
        raise NotImplementedError


class InMemoryChainLookup(ChainLookup):
    """Simple sorted-snapshot implementation of :class:`ChainLookup`."""

    def __init__(self, quotes: Iterable[ChainQuote], spot: float, trading_days: int = 252):
        self._quotes = sorted(quotes, key=lambda q: (q.expiry, q.option_type, q.strike))
        self.spot = spot
        self._trading_days = trading_days

    def quotes(self) -> Sequence[ChainQuote]:
        return self._quotes

    def _filtered(self, option_type: str, expiry: str) -> list[ChainQuote]:
        rows = [q for q in self._quotes if q.option_type == option_type and q.expiry == expiry]
        if not rows:
            raise ValueError(f"زنجیره برای {option_type} @ {expiry} خالی است")
        return rows

    def nearest_strike(self, target: float, option_type: str, expiry: str) -> float:
        rows = self._filtered(option_type, expiry)
        return min(rows, key=lambda q: abs(q.strike - target)).strike

    def nearest_expiry(self, target_dte: int) -> str:
        if not self._quotes:
            raise ValueError("زنجیره خالی است")
        expiries = sorted({q.expiry for q in self._quotes})
        if not expiries:
            raise ValueError("سررسیدی در زنجیره نیست")
        # Approximate DTE from ISO dates when possible.
        from datetime import date

        today = date.today()
        def _dte(iso: str) -> float:
            try:
                return abs((date.fromisoformat(iso) - today).days - target_dte)
            except ValueError:
                return abs(float(iso[:8]) - target_dte)  # fallback
        return min(expiries, key=_dte)

    def premium_of(self, strike: float, option_type: str, expiry: str) -> float:
        rows = self._filtered(option_type, expiry)
        return min(rows, key=lambda q: abs(q.strike - strike)).premium

    def strike_for_delta(self, target_delta: float, option_type: str, expiry: str) -> float:
        """Closest listed strike whose |delta| matches the target.

        ``target_delta`` sign is normalized by option type: calls use
        positive deltas, puts negative ones (conventional quoting).
        """
        rows = self._filtered(option_type, expiry)
        if option_type == "put":
            target = -abs(target_delta)
        else:
            target = abs(target_delta)

        def _distance(q: ChainQuote) -> float:
            delta = q.delta if q.delta else 0.0
            if option_type == "put" and delta > 0:
                delta = -delta
            if option_type == "call" and delta < 0:
                delta = -delta
            return abs(delta - target)

        best = min(rows, key=_distance)
        if not any(q.delta for q in rows):
            # No delta data in the chain — approximate from moneyness via BS.
            approx = self._approx_delta(best.strike, option_type, expiry)
            if abs(approx - target) > 0.25:
                raise ValueError("دلتای زنجیره برای انتخاب strike کافی نیست")
        return best.strike

    def _approx_delta(self, strike: float, option_type: str, expiry: str) -> float:
        try:
            from datetime import date

            dte = max((date.fromisoformat(expiry) - date.today()).days, 1)
        except ValueError:
            dte = 30
        sigma = 0.35  # conservative fallback vol
        price = black_scholes_price(self.spot, strike, dte / 365.0, 0.0, sigma, option_type)
        return price.delta


# ── Strategy templates (§7.1, §7.9) ─────────────────────────────────────


@dataclass
class TemplateLeg:
    """Raw leg before conversion to ``payoff.OptionLeg``."""

    option_type: str  # "call" | "put" | "stock"
    action: str  # "buy" | "sell"
    strike: float | None
    premium: float
    quantity: float = 1.0
    expiry: str | None = None


@dataclass
class BuiltStrategy:
    name: str
    legs: list[TemplateLeg]
    payoff_legs: list[OptionLeg]
    meta: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "meta": self.meta,
            "legs": [
                {
                    "option_type": leg.option_type,
                    "action": leg.action,
                    "strike": leg.strike,
                    "premium": leg.premium,
                    "quantity": leg.quantity,
                    "expiry": leg.expiry,
                }
                for leg in self.legs
            ],
        }


class StrategyTemplateLibrary:
    """One-click strategy construction from a live chain (§7.9)."""

    def __init__(self, chain: ChainLookup):
        self.chain = chain
        self._templates: dict[str, Callable[..., BuiltStrategy]] = {
            "COVERED_CALL": self.covered_call,
            "PROTECTIVE_PUT": self.protective_put,
            "COLLAR": self.collar,
            "BULL_CALL_SPREAD": self.bull_call_spread,
            "BEAR_PUT_SPREAD": self.bear_put_spread,
            "IRON_CONDOR": self.iron_condor,
            "IRON_BUTTERFLY": self.iron_butterfly,
            "CALENDAR_SPREAD": self.calendar_spread,
            "LONG_STRADDLE": self.long_straddle,
            "SHORT_STRANGLE": self.short_strangle,
            "JADE_LIZARD": self.jade_lizard,
        }

    def available(self) -> list[str]:
        return sorted(self._templates)

    def build(self, name: str, **params: Any) -> BuiltStrategy:
        key = name.upper()
        if key not in self._templates:
            raise ValueError(f"الگوی ناشناخته: {name}")
        return self._templates[key](**params)

    # -- helpers ---------------------------------------------------------

    def _expiry(self, dte_target: int) -> str:
        return self.chain.nearest_expiry(dte_target)

    def _leg(self, option_type: str, action: str, strike: float | None, expiry: str, quantity: float = 1.0) -> TemplateLeg:
        premium = self.chain.premium_of(strike, option_type, expiry) if option_type != "stock" else strike or 0.0
        return TemplateLeg(option_type, action, strike, premium, quantity, expiry)

    def _payoff(self, legs: Iterable[TemplateLeg]) -> list[OptionLeg]:
        return [
            OptionLeg(
                type=leg.option_type,  # type: ignore[arg-type]
                action=leg.action,  # type: ignore[arg-type]
                strike=leg.strike or 0.0,
                premium=leg.premium,
                quantity=leg.quantity,
            )
            for leg in legs
        ]

    def _assemble(self, name: str, legs: list[TemplateLeg], **meta: Any) -> BuiltStrategy:
        return BuiltStrategy(name=name, legs=legs, payoff_legs=self._payoff(legs), meta=meta)

    # -- single-underlying templates --------------------------------------

    def covered_call(self, dte_target: int = 30, call_delta_target: float = 0.30) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        k = self.chain.strike_for_delta(call_delta_target, "call", expiry)
        k = self.chain.nearest_strike(k, "call", expiry)
        legs = [
            TemplateLeg("stock", "buy", None, self.chain.spot, 1000.0, expiry),
            self._leg("call", "sell", k, expiry, 1.0),
        ]
        return self._assemble("COVERED_CALL", legs, expiry=expiry, short_delta=call_delta_target)

    def protective_put(self, dte_target: int = 30, put_delta_target: float = -0.30) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        k = self.chain.strike_for_delta(put_delta_target, "put", expiry)
        legs = [
            TemplateLeg("stock", "buy", None, self.chain.spot, 1000.0, expiry),
            self._leg("put", "buy", k, expiry, 1.0),
        ]
        return self._assemble("PROTECTIVE_PUT", legs, expiry=expiry, put_delta=put_delta_target)

    def collar(self, dte_target: int = 30, put_offset_pct: float = 5, call_offset_pct: float = 5) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        s = self.chain.spot
        put_k = self.chain.nearest_strike(s * (1 - put_offset_pct / 100), "put", expiry)
        call_k = self.chain.nearest_strike(s * (1 + call_offset_pct / 100), "call", expiry)
        legs = [
            TemplateLeg("stock", "buy", None, s, 1000.0, expiry),
            self._leg("put", "buy", put_k, expiry, 1.0),
            self._leg("call", "sell", call_k, expiry, 1.0),
        ]
        return self._assemble("COLLAR", legs, expiry=expiry, put_strike=put_k, call_strike=call_k)

    # -- verticals ---------------------------------------------------------

    def bull_call_spread(self, dte_target: int = 30, long_delta: float = 0.40, wing_pct: float = 5) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        long_k = self.chain.strike_for_delta(long_delta, "call", expiry)
        short_k = self.chain.nearest_strike(long_k * (1 + wing_pct / 100), "call", expiry)
        legs = [
            self._leg("call", "buy", long_k, expiry),
            self._leg("call", "sell", short_k, expiry),
        ]
        return self._assemble("BULL_CALL_SPREAD", legs, expiry=expiry, long_strike=long_k, short_strike=short_k)

    def bear_put_spread(self, dte_target: int = 30, long_delta: float = -0.40, wing_pct: float = 5) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        long_k = self.chain.strike_for_delta(long_delta, "put", expiry)
        short_k = self.chain.nearest_strike(long_k * (1 - wing_pct / 100), "put", expiry)
        legs = [
            self._leg("put", "buy", long_k, expiry),
            self._leg("put", "sell", short_k, expiry),
        ]
        return self._assemble("BEAR_PUT_SPREAD", legs, expiry=expiry, long_strike=long_k, short_strike=short_k)

    # -- volatility templates ----------------------------------------------

    def iron_condor(self, dte_target: int = 30, short_delta: float = 0.20, wing_pct: float = 5) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        put_k = self.chain.strike_for_delta(-short_delta, "put", expiry)
        call_k = self.chain.strike_for_delta(short_delta, "call", expiry)
        long_put_k = self.chain.nearest_strike(put_k * (1 - wing_pct / 100), "put", expiry)
        long_call_k = self.chain.nearest_strike(call_k * (1 + wing_pct / 100), "call", expiry)
        legs = [
            self._leg("put", "sell", put_k, expiry),
            self._leg("put", "buy", long_put_k, expiry),
            self._leg("call", "sell", call_k, expiry),
            self._leg("call", "buy", long_call_k, expiry),
        ]
        return self._assemble(
            "IRON_CONDOR",
            legs,
            expiry=expiry,
            short_put=put_k,
            short_call=call_k,
            long_put=long_put_k,
            long_call=long_call_k,
        )

    def iron_butterfly(self, dte_target: int = 30, wing_pct: float = 5) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        s = self.chain.spot
        atm = self.chain.nearest_strike(s, "call", expiry)
        long_put_k = self.chain.nearest_strike(atm * (1 - wing_pct / 100), "put", expiry)
        long_call_k = self.chain.nearest_strike(atm * (1 + wing_pct / 100), "call", expiry)
        legs = [
            self._leg("put", "sell", atm, expiry),
            self._leg("put", "buy", long_put_k, expiry),
            self._leg("call", "sell", atm, expiry),
            self._leg("call", "buy", long_call_k, expiry),
        ]
        return self._assemble("IRON_BUTTERFLY", legs, expiry=expiry, atm=atm)

    def calendar_spread(self, near_dte: int = 15, far_dte: int = 45, offset_pct: float = 0) -> BuiltStrategy:
        near = self.chain.nearest_expiry(near_dte)
        far = self.chain.nearest_expiry(far_dte)
        strike = self.chain.nearest_strike(self.chain.spot * (1 + offset_pct / 100), "call", near)
        legs = [
            self._leg("call", "sell", strike, near),
            self._leg("call", "buy", strike, far),
        ]
        return self._assemble("CALENDAR_SPREAD", legs, near_expiry=near, far_expiry=far, strike=strike)

    def long_straddle(self, dte_target: int = 30) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        atm = self.chain.nearest_strike(self.chain.spot, "call", expiry)
        legs = [
            self._leg("call", "buy", atm, expiry),
            self._leg("put", "buy", atm, expiry),
        ]
        return self._assemble("LONG_STRADDLE", legs, expiry=expiry, atm=atm)

    def short_strangle(self, dte_target: int = 30, short_delta: float = 0.20) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        put_k = self.chain.strike_for_delta(-short_delta, "put", expiry)
        call_k = self.chain.strike_for_delta(short_delta, "call", expiry)
        legs = [
            self._leg("put", "sell", put_k, expiry),
            self._leg("call", "sell", call_k, expiry),
        ]
        return self._assemble("SHORT_STRANGLE", legs, expiry=expiry, short_put=put_k, short_call=call_k)

    def jade_lizard(self, dte_target: int = 30, put_delta: float = -0.20, call_delta: float = 0.16) -> BuiltStrategy:
        expiry = self._expiry(dte_target)
        short_put_k = self.chain.strike_for_delta(put_delta, "put", expiry)
        short_call_k = self.chain.strike_for_delta(call_delta, "call", expiry)
        long_call_k = self.chain.nearest_strike(short_call_k * 1.05, "call", expiry)
        legs = [
            self._leg("put", "sell", short_put_k, expiry),
            self._leg("call", "sell", short_call_k, expiry),
            self._leg("call", "buy", long_call_k, expiry),
        ]
        return self._assemble("JADE_LIZARD", legs, expiry=expiry)


# ── Greeks aggregation + dual payoff (§7.2) ─────────────────────────────


class GreeksAggregator:
    """Current strategy value + greeks, mixing stock legs with options."""

    def __init__(self, risk_free_rate: float = 0.0):
        self.risk_free_rate = risk_free_rate

    def portfolio_value_and_greeks(
        self,
        legs: Sequence[TemplateLeg],
        spot: float,
        days_to_expiry: int,
        sigma_by_leg: dict[int, float] | None = None,
    ) -> tuple[float, dict[str, float]]:
        sigma_by_leg = sigma_by_leg or {}
        total_value = 0.0
        total_greeks = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}

        t_years = max(days_to_expiry, 0) / 365.0
        for index, leg in enumerate(legs):
            sign = 1.0 if leg.action == "buy" else -1.0
            qty = sign * leg.quantity

            if leg.option_type == "stock":
                total_value += qty * spot
                total_greeks["delta"] += qty
                continue

            sigma = sigma_by_leg.get(index, 0.3)
            strike = leg.strike or spot
            priced = black_scholes_price(spot, strike, t_years, self.risk_free_rate, sigma, leg.option_type)
            total_value += qty * priced.price
            for greek in total_greeks:
                total_greeks[greek] += qty * getattr(priced, greek)

        return total_value, total_greeks

    def dual_payoff_curve(
        self,
        legs: Sequence[TemplateLeg],
        spot: float,
        days_to_expiry: int,
        price_min: float,
        price_max: float,
        step: float,
        sigma_by_leg: dict[int, float] | None = None,
    ) -> list[dict[str, float]]:
        """Expiry payoff (broken line) + current value (smooth curve)."""
        from domain.options.payoff import calculate_payoff_at_price

        payoff_legs = [
            OptionLeg(
                type=leg.option_type,  # type: ignore[arg-type]
                action=leg.action,  # type: ignore[arg-type]
                strike=leg.strike or 0.0,
                premium=leg.premium,
                quantity=leg.quantity,
            )
            for leg in legs
        ]
        current, _ = self.portfolio_value_and_greeks(legs, spot, days_to_expiry, sigma_by_leg)
        curve: list[dict[str, float]] = []
        price = price_min
        while price < price_max:
            curve.append(
                {
                    "price": round(price, 6),
                    "payoff": round(calculate_payoff_at_price(payoff_legs, price), 6),
                    "current_value": round(current, 6),
                }
            )
            price += step
        curve.append(
            {
                "price": round(price_max, 6),
                "payoff": round(calculate_payoff_at_price(payoff_legs, price_max), 6),
                "current_value": round(current, 6),
            }
        )
        return curve


# ── Pre-trade validation (§7.10) ─────────────────────────────────────────


class StrategyValidator:
    """Runs before any strategy reaches the order coordinator (§7.10)."""

    MIN_OPEN_INTEREST = 10

    def validate(
        self,
        legs: Sequence[TemplateLeg],
        chain: ChainLookup | None = None,
        portfolio_state: dict[str, Any] | None = None,
        user_limits: dict[str, Any] | None = None,
        estimated_margin: float | None = None,
    ) -> list[str]:
        errors: list[str] = []
        portfolio_state = portfolio_state or {}
        user_limits = user_limits or {}

        if not legs:
            errors.append("استراتژی بدون پایه قابل ثبت نیست")
            return errors

        option_legs = [leg for leg in legs if leg.option_type != "stock"]
        expiries = {leg.expiry for leg in option_legs if leg.expiry}
        if len(expiries) > 1 and not any(leg.strike != (option_legs[0].strike) for leg in option_legs):
            # Multi-expiry with identical strikes is calendar/diagonal — allowed.
            pass

        if chain is not None:
            for leg in option_legs:
                if leg.strike is None:
                    continue
                try:
                    quote = next(
                        q
                        for q in chain.quotes()
                        if q.option_type == leg.option_type
                        and q.expiry == leg.expiry
                        and abs(q.strike - leg.strike) < 1e-9
                    )
                except StopIteration:
                    errors.append(f"پایه {leg.option_type} @{leg.strike} در زنجیره یافت نشد")
                    continue
                if quote.open_interest < self.MIN_OPEN_INTEREST:
                    errors.append(
                        f"پایه با Strike {leg.strike} نقدشوندگی بسیار پایینی دارد (OI<{self.MIN_OPEN_INTEREST})"
                    )

        available_cash = portfolio_state.get("available_cash")
        if estimated_margin is not None and available_cash is not None and estimated_margin > available_cash:
            errors.append("وجه تضمین تخمینی از موجودی قابل‌استفاده بیشتر است")

        max_concentration = user_limits.get("max_concentration_pct")
        if max_concentration is not None:
            projected = portfolio_state.get("current_concentration", 0.0) + portfolio_state.get(
                "new_concentration", 0.0
            )
            if projected > max_concentration:
                errors.append("این معامله از سقف تمرکز مجاز روی این نماد/سررسید عبور می‌کند")

        return errors


# ── Adjustment engine (§7.6) ──────────────────────────────────────────────


class AdjustmentEngine:
    """Suggests rolls / defense / hedges; execution stays user-approved."""

    def evaluate(self, strategy_state: dict[str, Any], market_state: dict[str, Any]) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []

        dte = strategy_state.get("days_to_expiry", 999)
        pnl = strategy_state.get("unrealized_pnl_pct", 0.0)
        if dte <= 5 and pnl > 0:
            suggestions.append({"action": "ROLL_FORWARD", "reason": "نزدیکی سررسید با سود جزئی"})

        threatened = strategy_state.get("threatened_leg")
        distance = strategy_state.get("distance_to_threatened_strike_pct")
        if threatened is not None and distance is not None and distance < 2:
            suggestions.append(
                {
                    "action": "DEFEND_SIDE",
                    "leg": threatened,
                    "reason": "قیمت سهم پایه به Strike تهدیدشده نزدیک شده",
                }
            )

        portfolio_delta = strategy_state.get("portfolio_delta", 0.0)
        delta_limit = strategy_state.get("user_delta_limit")
        if delta_limit is not None and abs(portfolio_delta) > delta_limit:
            suggestions.append({"action": "DELTA_HEDGE", "reason": "عبور از حد مجاز Delta تجمیعی"})

        return suggestions


# ── Lifecycle (§7.7) ──────────────────────────────────────────────────────


class StrategyStatus(str, Enum):
    PROPOSED = "PROPOSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PENDING_EXECUTION = "PENDING_EXECUTION"
    ACTIVE = "ACTIVE"
    ADJUSTED = "ADJUSTED"
    CLOSED = "CLOSED"


_ALLOWED_TRANSITIONS: dict[StrategyStatus, set[StrategyStatus]] = {
    StrategyStatus.PROPOSED: {StrategyStatus.PENDING_APPROVAL, StrategyStatus.CLOSED},
    StrategyStatus.PENDING_APPROVAL: {StrategyStatus.PENDING_EXECUTION, StrategyStatus.CLOSED},
    StrategyStatus.PENDING_EXECUTION: {StrategyStatus.ACTIVE, StrategyStatus.CLOSED},
    StrategyStatus.ACTIVE: {StrategyStatus.ADJUSTED, StrategyStatus.CLOSED},
    StrategyStatus.ADJUSTED: {StrategyStatus.ACTIVE, StrategyStatus.CLOSED},
    StrategyStatus.CLOSED: set(),
}


class StrategyLifecycleTracker:
    """Tiny auditable state machine for multi-leg strategies."""

    def __init__(self) -> None:
        self._state: dict[str, StrategyStatus] = {}

    def status(self, strategy_id: str) -> StrategyStatus | None:
        return self._state.get(strategy_id)

    def create(self, strategy_id: str) -> StrategyStatus:
        self._state[strategy_id] = StrategyStatus.PROPOSED
        return StrategyStatus.PROPOSED

    def transition(self, strategy_id: str, to_status: StrategyStatus) -> StrategyStatus:
        current = self._state.get(strategy_id)
        if current is None:
            raise KeyError(f"استراتژی {strategy_id} ثبت نشده است")
        if to_status not in _ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"گذار نامعتبر: {current.value} → {to_status.value}")
        self._state[strategy_id] = to_status
        return to_status
