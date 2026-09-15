"""Signal Decision Engine — evaluates enriched signals through a 10-gate pipeline.

Each signal must pass (or receive managed warnings) through all gates before
being released. The engine is config-driven so thresholds can be tuned per
market without code changes.

Gates (in order):
  1. Data Quality Gate     — is the input data complete and valid?
  2. Model Gate            — are the ML models healthy and predictions available?
  3. Probability Gate      — does the calibrated probability exceed the effective threshold?
  4. Regime Gate           — does the current regime support this signal?
  5. Consensus Gate        — do ensemble models agree on the direction?
  6. Liquidity Gate        — can this signal be filled without excessive slippage?
  7. Risk/Reward Gate      — is the reward/risk ratio above minimum?
  8. Expectancy Gate       — is the net expected value positive after costs?
  9. Portfolio Gate        — does this signal respect portfolio risk limits?
  10. Execution Gate       — can the signal be executed in the current market?

Output: a Decision object with per-gate results and a final verdict
  (release / watchlist / reject).

Market-specific overrides: load a YAML/JSON config with per-market sections.
  Each gate reads settings via get_gate_config(gate_name, market) which
  deep-merges global defaults + market-specific overrides.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from core.logging import get_logger
from services.decision_gate import GateOverride, SmartDecisionGate

# ── Cross-market regime cache ───────────────────────────────────────────────
# Populated lazily by _detect_regime() when real data is available
# from CrossMarketCorrelator via DB query.
_cached_regime_data: dict[str, dict[str, Any]] = {}

logger = get_logger(__name__)


# ── Enums & Data Structures ──────────────────────────────────────────────────


class GateVerdict(Enum):
    PASS = "pass"
    WARN = "warn"  # passes but with caution
    BLOCK = "block"  # signal cannot proceed


class FinalVerdict(Enum):
    RELEASE = "release"
    WATCHLIST = "watchlist"
    REJECT = "reject"


@dataclass
class GateResult:
    """Result of a single gate evaluation."""

    gate_name: str
    verdict: GateVerdict
    score: float = 0.0  # 0-1 score for the gate
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate_name,
            "verdict": self.verdict.value,
            "score": round(self.score, 3),
            "reason": self.reason,
            "details": self.details,
        }


@dataclass
class Decision:
    """Final decision for one signal candidate."""

    signal_id: str
    symbol: str
    market: str
    direction: str

    verdict: FinalVerdict
    calibrated_probability: float
    effective_threshold: float
    gate_results: list[GateResult] = field(default_factory=list)

    # Derived fields
    net_expectancy_r: float = 0.0
    risk_reward_ratio: float = 0.0
    fill_probability: float = 0.0

    # Evaluated at
    evaluated_at: str = ""

    def is_releasable(self) -> bool:
        return self.verdict == FinalVerdict.RELEASE

    def is_watchlisted(self) -> bool:
        return self.verdict == FinalVerdict.WATCHLIST

    def all_gates_pass(self) -> bool:
        return all(g.verdict != GateVerdict.BLOCK for g in self.gate_results)

    def warning_count(self) -> int:
        return sum(1 for g in self.gate_results if g.verdict == GateVerdict.WARN)

    def blocked_gates(self) -> list[str]:
        return [g.gate_name for g in self.gate_results if g.verdict == GateVerdict.BLOCK]

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "market": self.market,
            "direction": self.direction,
            "verdict": self.verdict.value,
            "calibrated_probability": round(self.calibrated_probability, 3),
            "effective_threshold": round(self.effective_threshold, 3),
            "net_expectancy_r": round(self.net_expectancy_r, 3),
            "risk_reward_ratio": round(self.risk_reward_ratio, 3),
            "fill_probability": round(self.fill_probability, 3),
            "warning_count": self.warning_count(),
            "blocked_gates": self.blocked_gates(),
            "gate_results": [g.to_dict() for g in self.gate_results],
            "evaluated_at": self.evaluated_at,
        }


# ── SignalCandidate ──────────────────────────────────────────────────────────


@dataclass
class SignalCandidate:
    """A signal before the decision engine evaluates it."""

    signal_id: str
    symbol: str
    name: str
    market: str
    direction: str
    timeframe: str

    # Core scores
    raw_score: float  # 0-1 from rule/technical analysis
    ml_score: float  # 0-1 from ML ensemble
    calibrated_probability: float  # from ProbabilityCalibrator
    boosted_score: float  # 0-100 combined

    # Model info
    active_models: int = 0
    agreeing_models: int = 0
    model_disagreement: float = 0.0  # 0 = full agreement, 1 = total conflict
    models_used: list[str] = field(default_factory=list)

    # Data quality
    data_quality_score: float = 1.0  # 0-1, 1 = perfect
    missing_data_count: int = 0

    # Liquidity
    liquidity_score: float = 0.7
    avg_daily_volume: float = 0.0
    spread_pct: float = 0.0
    fill_probability: float = 0.7

    # Risk
    risk_reward: float = 0.0  # reward / risk
    stop_loss_pct: float = 0.0
    target_pct: float = 0.0
    position_size_pct: float = 0.0  # % of portfolio
    volatility_regime: float = 0.5  # 0 = low, 1 = high

    # Portfolio context
    open_risk_pct: float = 0.0  # current open risk % of portfolio
    correlated_exposure_pct: float = 0.0
    portfolio_risk_approved: bool = True

    # Feature drift
    feature_drift: float = 0.0  # 0 = no drift, 1 = severe
    prediction_drift: float = 0.0

    # Price
    price: float = 0.0
    entry_zone: str = ""
    stop_loss: str = ""
    targets: str = ""

    # Extra
    signal_type: str = "rule"  # rule / ml / hybrid
    best_class_probability: float = 0.0
    second_class_probability: float = 0.0
    source: str = ""


# ── Policy / Config ──────────────────────────────────────────────────────────


class SignalPolicy:
    """Config-driven signal policy with versioned thresholds and gate parameters.

    Supports market-specific overrides via config/signal_policy.yaml.
    Each gate reads settings via `get_gate_config(gate_name, market)` which
    deep-merges the global defaults with any market-specific overrides.

    Example YAML structure::

        data:
          min_data_quality: 0.80
        stock:
          data:
            min_data_quality: 0.85     # overrides for stock market
        crypto:
          probability:
            base_threshold: 0.60       # overrides for crypto
    """

    def __init__(self, json_path: str | None = None) -> None:
        self._policy_data: dict[str, Any] = self._load_defaults()
        if json_path:
            try:
                with open(json_path, encoding="utf-8") as f:
                    if json_path.endswith((".yaml", ".yml")):
                        import yaml

                        overrides = yaml.safe_load(f)
                    else:
                        overrides = json.load(f)
                if overrides is None:
                    overrides = {}
                self._deep_merge(self._policy_data, overrides)
                logger.info("Loaded signal policy from %s (version=%s)", json_path, self.version)
            except Exception as e:
                logger.warning("Failed to load policy from %s: %s — using defaults", json_path, e)

    def _load_defaults(self) -> dict[str, Any]:
        return {
            "policy_version": "1.0.0",
            "policy_name": "default_conservative",
            "data": {
                "min_data_quality": 0.80,
                "max_missing_fields": 3,
            },
            "model": {
                "min_models_available": 1,
                "max_disagreement": 0.60,
            },
            "probability": {
                "base_threshold": 0.55,
                "margin": {
                    "minimum": 0.10,
                    "watchlist": 0.05,
                },
                "volatility_penalty": 0.05,
                "liquidity_penalty": 0.03,
                "drift_penalty": 0.04,
            },
            "regime": {
                "blocked_regimes": ["CRISIS"],
                "warn_regimes": ["HIGH_VOLATILITY", "UNKNOWN"],
            },
            "ensemble": {
                "minimum_active_models": 1,
                "minimum_agreeing_models": 1,
                "conflict_block": True,
            },
            "liquidity": {
                "minimum_score": 0.50,
                "minimum_fill_probability": 0.50,
                "minimum_avg_volume": 0,
            },
            "risk_reward": {
                "minimum_trade": 1.0,
                "minimum_watchlist": 0.5,
            },
            "expectancy": {
                "minimum_net_expectancy_r": 0.05,
                "costs_pct": 0.003,
            },
            "portfolio": {
                "max_open_risk_pct": 0.25,
                "max_correlated_exposure_pct": 0.40,
            },
            "execution": {
                "min_spread_pct": 0.0,
                "require_market_open": True,
            },
            "grades": {
                "a_plus": {"min_probability": 0.70, "min_rr": 2.0, "min_expectancy": 0.20, "all_pass_required": True},
                "a": {"min_probability": 0.65, "min_rr": 1.5, "min_expectancy": 0.12, "max_warnings": 1},
                "b": {"min_probability": 0.60, "min_rr": 1.0, "min_expectancy": 0.05, "max_warnings": 2},
                "watchlist": {"min_probability": 0.55, "min_rr": 0.0, "min_expectancy": 0.0},
            },
        }

    @property
    def version(self) -> str:
        return str(self._policy_data.get("policy_version", "0.0.0"))

    @property
    def name(self) -> str:
        return str(self._policy_data.get("policy_name", "default"))

    def to_dict(self) -> dict[str, Any]:
        return dict(self._policy_data)

    # ── Market-Aware Config Access ──────────────────────────────────────────

    def get_gate_config(self, gate_name: str, market: str) -> dict[str, Any]:
        """Get gate config with market-specific overrides merged in.

        Returns a *deep copy* of the global config dict for *gate_name*,
        overridden by any market-specific config under ``policy_data[market][gate_name]``.
        Uses deep copy so that market-specific overrides never mutate the global defaults.

        Example::

            get_gate_config("probability", "crypto")
            # → global probability dict, overridden by crypto.probability
        """
        base = self._policy_data.get(gate_name, {})
        mkt = self._policy_data.get(market)
        if isinstance(mkt, dict):
            override = mkt.get(gate_name)
            if isinstance(override, dict):
                merged: dict[str, Any] = copy.deepcopy(base)
                SignalPolicy._deep_merge(merged, override)
                return merged
        return dict(copy.deepcopy(base))

    def get_grades_config(self, market: str) -> dict[str, Any]:
        """Get grades config with market-specific overrides."""
        return self.get_gate_config("grades", market)

    def get_effective_threshold(
        self,
        volatility: float = 0.5,
        liquidity: float = 0.7,
        drift: float = 0.0,
        market: str = "",
    ) -> float:
        """Compute the dynamic effective threshold for a signal.

        Uses market-specific probability config when *market* is given.
        Base threshold + penalties for unfavorable conditions.
        """
        prob = self.get_gate_config("probability", market)
        base = float(prob.get("base_threshold", 0.55))

        penalty = 0.0
        if volatility > 0.7:
            penalty += float(prob.get("volatility_penalty", 0.05))
        if liquidity < 0.5:
            penalty += float(prob.get("liquidity_penalty", 0.03))
        if drift > 0.3:
            penalty += float(prob.get("drift_penalty", 0.04))

        return round(min(0.80, base + penalty), 3)

    def get_expectancy_for_market(self, market: str) -> dict[str, Any]:
        """Get expectancy config with market-specific overrides."""
        return self.get_gate_config("expectancy", market)

    # ── Internal ────────────────────────────────────────────────────────────

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                SignalPolicy._deep_merge(base[key], value)
            else:
                base[key] = value


# ── Signal Decision Engine ───────────────────────────────────────────────────


class SignalDecisionEngine:
    """10-gate signal decision engine.

    Usage:
        engine = SignalDecisionEngine(policy=my_policy)
        decision = await engine.evaluate(candidate)
        if decision.is_releasable():
            # release signal
        elif decision.is_watchlisted():
            # add to watchlist

    Each gate reads its config from ``self._policy.get_gate_config(gate, market)``,
    so market-specific thresholds from ``config/signal_policy.yaml`` are applied
    automatically.
    """

    def __init__(
        self,
        policy: SignalPolicy | None = None,
        session: Any = None,
        decision_gate: SmartDecisionGate | None = None,
    ) -> None:
        self._policy = policy or SignalPolicy()
        self._session = session
        self._decision_gate = decision_gate or SmartDecisionGate(session=session)

    @property
    def policy(self) -> SignalPolicy:
        return self._policy

    async def evaluate(self, candidate: SignalCandidate) -> Decision:
        """Run all 10 gates on the candidate and return the decision."""
        gate_results: list[GateResult] = []

        market = candidate.market

        # Compute the effective threshold (dynamic, market-aware)
        effective_threshold = self._policy.get_effective_threshold(
            volatility=candidate.volatility_regime,
            liquidity=candidate.liquidity_score,
            drift=candidate.feature_drift,
            market=market,
        )

        # ── Gate 1: Data Quality ────────────────────────────────────────────
        gate_results.append(await self._gate_data_quality(candidate, market))

        # ── Smart override (market-condition aware) ───────────────────────
        override = await self._resolve_gate_override(candidate, market)

        # ── Gate 2: Model (with SmartOverride) ──────────────────────────────
        gate_results.append(await self._gate_model(candidate, market, override))

        # ── Gate 3: Probability ─────────────────────────────────────────────
        gate_results.append(await self._gate_probability(candidate, effective_threshold, market))

        # ── Gate 4: Regime (with SmartOverride) ─────────────────────────────
        gate_results.append(await self._gate_regime(candidate, market, override))

        # ── Gate 5: Consensus ───────────────────────────────────────────────
        gate_results.append(await self._gate_consensus(candidate, market))

        # ── Gate 6: Liquidity ───────────────────────────────────────────────
        gate_results.append(await self._gate_liquidity(candidate, market))

        # ── Gate 7: Risk/Reward ─────────────────────────────────────────────
        gate_results.append(await self._gate_risk_reward(candidate, market))

        # ── Gate 8: Expectancy ──────────────────────────────────────────────
        gate_results.append(await self._gate_expectancy(candidate, market))

        # ── Gate 9: Portfolio ───────────────────────────────────────────────
        gate_results.append(await self._gate_portfolio(candidate, market))

        # ── Gate 10: Execution ──────────────────────────────────────────────
        gate_results.append(await self._gate_execution(candidate, market))

        # ── Final Verdict ───────────────────────────────────────────────────
        blocked = [g for g in gate_results if g.verdict == GateVerdict.BLOCK]
        warnings = [g for g in gate_results if g.verdict == GateVerdict.WARN]

        if blocked:
            verdict = FinalVerdict.REJECT
        elif len(warnings) > 2:
            verdict = FinalVerdict.WATCHLIST
        else:
            verdict = FinalVerdict.RELEASE

        # Compute net expectancy (market-aware)
        net_expectancy = self._compute_net_expectancy(candidate, market)

        return Decision(
            signal_id=candidate.signal_id,
            symbol=candidate.symbol,
            market=market,
            direction=candidate.direction,
            verdict=verdict,
            calibrated_probability=candidate.calibrated_probability,
            effective_threshold=effective_threshold,
            gate_results=gate_results,
            net_expectancy_r=net_expectancy,
            risk_reward_ratio=candidate.risk_reward,
            fill_probability=candidate.fill_probability,
            evaluated_at=datetime.now(UTC).isoformat(),
        )

    # ── Individual Gates ────────────────────────────────────────────────────

    async def _gate_data_quality(self, candidate: SignalCandidate, market: str) -> GateResult:
        """Gate 1: Data Quality — is the input data complete and valid?"""
        cfg = self._policy.get_gate_config("data", market)
        min_quality = cfg.get("min_data_quality", 0.80)
        max_missing = cfg.get("max_missing_fields", 3)

        score = candidate.data_quality_score
        missing = candidate.missing_data_count

        if score < min_quality:
            return GateResult(
                gate_name="data_quality",
                verdict=GateVerdict.BLOCK,
                score=score,
                reason=f"کیفیت داده پایین: {score:.2f} (حداقل {min_quality})",
                details={"score": score, "missing_fields": missing, "threshold": min_quality},
            )

        if missing > max_missing:
            return GateResult(
                gate_name="data_quality",
                verdict=GateVerdict.WARN,
                score=score,
                reason=f"{missing} فیلد داده از دست رفته است",
                details={"score": score, "missing_fields": missing, "max_allowed": max_missing},
            )

        return GateResult(
            gate_name="data_quality",
            verdict=GateVerdict.PASS,
            score=score,
            reason="داده ورودی کامل و معتبر است",
            details={"score": score, "missing_fields": missing},
        )

    async def _gate_model(
        self,
        candidate: SignalCandidate,
        market: str,
        override: GateOverride | None = None,
    ) -> GateResult:
        """Gate 2: Model — are ML models healthy and predictions available?

        Market-condition override (via SmartDecisionGate):
        - Stagnant market (vol < 2%): ignore ML, force rule-only.
        - Volume surge (3× avg): boost ML weight by 50%.
        """
        cfg = self._policy.get_gate_config("model", market)
        min_models = cfg.get("min_models_available", 1)
        max_disagreement = cfg.get("max_disagreement", 0.60)

        # ── Apply SmartDecisionGate override ───────────────────────────────
        use_override = override is not None

        if use_override and override.ignore_ml:
            # Stagnant market: force rule-only — mean reversion takes over
            return GateResult(
                gate_name="model",
                verdict=GateVerdict.PASS,
                score=1.0,
                reason=(f"SmartOverride: {override.reason} ML نادیده گرفته شد — سیگنال Mean-Reversion جایگزین شد"),
                details={
                    "signal_type": "rule_override",
                    "override_reason": override.reason,
                    "smart_override": True,
                },
            )

        if candidate.signal_type == "rule":
            return GateResult(
                gate_name="model",
                verdict=GateVerdict.PASS,
                score=1.0,
                reason="سیگنال مبتنی بر قانون — نیاز به مدل ندارد",
                details={"signal_type": "rule"},
            )

        if candidate.active_models < min_models:
            return GateResult(
                gate_name="model",
                verdict=GateVerdict.BLOCK,
                score=0.0,
                reason=f"مدل‌های فعال کافی نیست: {candidate.active_models}/{min_models}",
                details={"active_models": candidate.active_models, "min_required": min_models},
            )

        if candidate.model_disagreement > max_disagreement:
            return GateResult(
                gate_name="model",
                verdict=GateVerdict.WARN,
                score=1.0 - candidate.model_disagreement,
                reason=f"اختلاف نظر مدل‌ها: {candidate.model_disagreement:.2f}",
                details={
                    "disagreement": candidate.model_disagreement,
                    "models": candidate.models_used,
                    "threshold": max_disagreement,
                },
            )

        # Volume surge boost (from SmartDecisionGate)
        ml_score = candidate.ml_score
        if use_override and override.ml_boost_multiplier > 1.0:
            ml_score = min(1.0, ml_score * override.ml_boost_multiplier)

        return GateResult(
            gate_name="model",
            verdict=GateVerdict.PASS,
            score=ml_score,
            reason=(
                f"{candidate.active_models} مدل فعال — پیش‌بینی در دسترس"
                + (
                    f" (ضریب ML: {override.ml_boost_multiplier:.1f}×)"
                    if use_override and override.ml_boost_multiplier > 1.0
                    else ""
                )
            ),
            details={
                "active_models": candidate.active_models,
                "agreeing": candidate.agreeing_models,
                "models": candidate.models_used,
                "ml_boost": override.ml_boost_multiplier
                if use_override and override.ml_boost_multiplier > 1.0
                else 1.0,
                "smart_override": use_override,
            },
        )

    async def _gate_probability(
        self,
        candidate: SignalCandidate,
        effective_threshold: float,
        market: str,
    ) -> GateResult:
        """Gate 3: Probability — does calibrated probability exceed the threshold?"""
        prob = candidate.calibrated_probability
        prob_cfg = self._policy.get_gate_config("probability", market)
        margin_policy = prob_cfg.get("margin", {})
        min_margin = margin_policy.get("minimum", 0.10)

        if prob < effective_threshold:
            return GateResult(
                gate_name="probability",
                verdict=GateVerdict.BLOCK,
                score=prob,
                reason=f"احتمال کالیبره‌شده {prob:.2f} کمتر از آستانه {effective_threshold:.2f}",
                details={
                    "calibrated_probability": prob,
                    "effective_threshold": effective_threshold,
                    "margin": prob - effective_threshold,
                },
            )

        margin = candidate.best_class_probability - candidate.second_class_probability
        if margin < min_margin:
            return GateResult(
                gate_name="probability",
                verdict=GateVerdict.WARN,
                score=prob,
                reason=f"حاشیه احتمال کم: {margin:.3f} (حداقل {min_margin})",
                details={
                    "margin": margin,
                    "best_class_prob": candidate.best_class_probability,
                    "second_class_prob": candidate.second_class_probability,
                    "threshold": effective_threshold,
                },
            )

        return GateResult(
            gate_name="probability",
            verdict=GateVerdict.PASS,
            score=prob,
            reason=f"احتمال {prob:.2f} بالاتر از آستانه {effective_threshold:.2f}",
            details={
                "calibrated_probability": prob,
                "effective_threshold": effective_threshold,
                "margin": margin,
            },
        )

    async def _gate_regime(
        self,
        candidate: SignalCandidate,
        market: str,
        override: GateOverride | None = None,
    ) -> GateResult:
        """Gate 4: Regime — does the current regime support this signal?

        Market-condition override (via SmartDecisionGate):
        Uses the real index data from ``brsapi_index_values`` (fetched
        by SmartDecisionGate) rather than the single-snapshot heuristic.
        """
        cfg = self._policy.get_gate_config("regime", market)
        blocked = cfg.get("blocked_regimes", ["CRISIS"])
        warned = cfg.get("warn_regimes", ["HIGH_VOLATILITY", "UNKNOWN"])

        # Use SmartDecisionGate's regime if available (more accurate).
        if override is not None and override.regime_label != "UNKNOWN":
            regime = override.regime_label
            candidate.volatility_regime = override.volatility_regime
        else:
            regime = await self._detect_regime(candidate)

        if regime in blocked:
            return GateResult(
                gate_name="regime",
                verdict=GateVerdict.BLOCK,
                score=0.0,
                reason=f"رژیم {regime} — انتشار سیگنال مجاز نیست",
                details={"regime": regime, "blocked": True},
            )

        if regime in warned:
            return GateResult(
                gate_name="regime",
                verdict=GateVerdict.WARN,
                score=0.5,
                reason=f"رژیم {regime} — سیگنال با احتیاط منتشر شود",
                details={"regime": regime, "warned": True},
            )

        return GateResult(
            gate_name="regime",
            verdict=GateVerdict.PASS,
            score=1.0,
            reason=f"رژیم {regime} — شرایط مناسب",
            details={
                "regime": regime,
                "volatility_regime": candidate.volatility_regime,
                "smart_override": override is not None and override.regime_label != "UNKNOWN",
                "override_reason": override.reason if override else "",
            },
        )

    async def _gate_consensus(self, candidate: SignalCandidate, market: str) -> GateResult:
        """Gate 5: Consensus — do ensemble models agree on direction?"""
        cfg = self._policy.get_gate_config("ensemble", market)
        min_active = cfg.get("minimum_active_models", 1)
        min_agree = cfg.get("minimum_agreeing_models", 1)
        conflict_block = cfg.get("conflict_block", True)

        if candidate.signal_type == "rule":
            return GateResult(
                gate_name="consensus",
                verdict=GateVerdict.PASS,
                score=1.0,
                reason="سیگنال قانون — نیازی به اجماع مدل ندارد",
                details={"signal_type": "rule"},
            )

        if candidate.active_models < min_active:
            return GateResult(
                gate_name="consensus",
                verdict=GateVerdict.BLOCK if conflict_block else GateVerdict.WARN,
                score=candidate.active_models / max(min_active, 1),
                reason=f"مدل‌های کافی برای اجماع: {candidate.active_models}/{min_active}",
                details={"active_models": candidate.active_models, "min_required": min_active},
            )

        if candidate.agreeing_models < min_agree:
            return GateResult(
                gate_name="consensus",
                verdict=GateVerdict.BLOCK if conflict_block else GateVerdict.WARN,
                score=candidate.agreeing_models / max(min_agree, 1),
                reason=f"توافق ناکافی مدل‌ها: {candidate.agreeing_models}/{min_agree}",
                details={
                    "agreeing": candidate.agreeing_models,
                    "min_required": min_agree,
                    "total_models": candidate.active_models,
                },
            )

        agreement_ratio = candidate.agreeing_models / max(candidate.active_models, 1)

        return GateResult(
            gate_name="consensus",
            verdict=GateVerdict.PASS,
            score=agreement_ratio,
            reason=f"{candidate.agreeing_models}/{candidate.active_models} مدل موافق",
            details={
                "agreeing": candidate.agreeing_models,
                "total": candidate.active_models,
                "agreement_ratio": round(agreement_ratio, 3),
            },
        )

    async def _gate_liquidity(self, candidate: SignalCandidate, market: str) -> GateResult:
        """Gate 6: Liquidity — can this position be filled without excess slippage?"""
        cfg = self._policy.get_gate_config("liquidity", market)
        min_score = cfg.get("minimum_score", 0.50)
        min_fill = cfg.get("minimum_fill_probability", 0.50)

        if candidate.liquidity_score < min_score:
            return GateResult(
                gate_name="liquidity",
                verdict=GateVerdict.BLOCK,
                score=candidate.liquidity_score,
                reason=f"نقدشوندگی پایین: {candidate.liquidity_score:.2f} (حداقل {min_score})",
                details={"liquidity_score": candidate.liquidity_score, "threshold": min_score},
            )

        if candidate.fill_probability < min_fill:
            return GateResult(
                gate_name="liquidity",
                verdict=GateVerdict.WARN,
                score=candidate.fill_probability,
                reason=f"احتمال پر شدن پایین: {candidate.fill_probability:.2f}",
                details={
                    "fill_probability": candidate.fill_probability,
                    "avg_volume": candidate.avg_daily_volume,
                    "spread_pct": candidate.spread_pct,
                },
            )

        return GateResult(
            gate_name="liquidity",
            verdict=GateVerdict.PASS,
            score=candidate.liquidity_score,
            reason=f"نقدشوندگی مناسب: {candidate.liquidity_score:.2f}",
            details={
                "liquidity_score": candidate.liquidity_score,
                "fill_probability": candidate.fill_probability,
                "avg_volume": candidate.avg_daily_volume,
            },
        )

    async def _gate_risk_reward(self, candidate: SignalCandidate, market: str) -> GateResult:
        """Gate 7: Risk/Reward — is the reward/risk ratio acceptable?"""
        cfg = self._policy.get_gate_config("risk_reward", market)
        min_trade = cfg.get("minimum_trade", 1.0)
        min_watchlist = cfg.get("minimum_watchlist", 0.5)

        rr = candidate.risk_reward

        if rr < min_watchlist:
            return GateResult(
                gate_name="risk_reward",
                verdict=GateVerdict.BLOCK,
                score=rr,
                reason=f"نسبت ریسک/پاداش ضعیف: {rr:.2f} (حداقل {min_watchlist})",
                details={
                    "risk_reward": rr,
                    "stop_loss_pct": candidate.stop_loss_pct,
                    "target_pct": candidate.target_pct,
                },
            )

        if rr < min_trade:
            return GateResult(
                gate_name="risk_reward",
                verdict=GateVerdict.WARN,
                score=rr,
                reason=f"نسبت ریسک/پاداش متوسط: {rr:.2f} (حداقل معامله {min_trade})",
                details={
                    "risk_reward": rr,
                    "stop_loss_pct": candidate.stop_loss_pct,
                    "target_pct": candidate.target_pct,
                },
            )

        return GateResult(
            gate_name="risk_reward",
            verdict=GateVerdict.PASS,
            score=min(1.0, rr / 3.0),
            reason=f"نسبت ریسک/پاداش مطلوب: {rr:.2f}",
            details={"risk_reward": rr},
        )

    async def _gate_expectancy(self, candidate: SignalCandidate, market: str) -> GateResult:
        """Gate 8: Expectancy — is the net expected value positive in R-multiples?"""
        cfg = self._policy.get_gate_config("expectancy", market)
        min_expectancy = cfg.get("minimum_net_expectancy_r", 0.05)

        net_expectancy = self._compute_net_expectancy(candidate, market)

        if net_expectancy < min_expectancy:
            return GateResult(
                gate_name="expectancy",
                verdict=GateVerdict.BLOCK if net_expectancy < 0 else GateVerdict.WARN,
                score=max(0.0, net_expectancy / max(min_expectancy, 0.001)),
                reason=f"امید ریاضی خالص {net_expectancy:.3f}R (حداقل {min_expectancy})",
                details={
                    "net_expectancy_r": round(net_expectancy, 4),
                    "win_rate": round(candidate.calibrated_probability, 3),
                    "risk_reward": candidate.risk_reward,
                },
            )

        return GateResult(
            gate_name="expectancy",
            verdict=GateVerdict.PASS,
            score=min(1.0, net_expectancy / 0.20),
            reason=f"امید ریاضی خالص {net_expectancy:.3f}R",
            details={
                "net_expectancy_r": round(net_expectancy, 4),
                "win_rate": round(candidate.calibrated_probability, 3),
            },
        )

    async def _gate_portfolio(self, candidate: SignalCandidate, market: str) -> GateResult:
        """Gate 9: Portfolio — does this signal respect portfolio risk limits?"""
        cfg = self._policy.get_gate_config("portfolio", market)
        max_open_risk = cfg.get("max_open_risk_pct", 0.25)
        max_correlated = cfg.get("max_correlated_exposure_pct", 0.40)

        if not candidate.portfolio_risk_approved:
            return GateResult(
                gate_name="portfolio",
                verdict=GateVerdict.BLOCK,
                score=0.0,
                reason="ریسک پرتفوی تأیید نشده است",
                details={"portfolio_risk_approved": False},
            )

        if candidate.open_risk_pct > max_open_risk:
            return GateResult(
                gate_name="portfolio",
                verdict=GateVerdict.BLOCK,
                score=1.0 - (candidate.open_risk_pct / max_open_risk),
                reason=f"ریسک باز {candidate.open_risk_pct:.1%} بیش از حد مجاز {max_open_risk:.0%}",
                details={"open_risk_pct": candidate.open_risk_pct, "max_allowed": max_open_risk},
            )

        if candidate.correlated_exposure_pct > max_correlated:
            return GateResult(
                gate_name="portfolio",
                verdict=GateVerdict.WARN,
                score=1.0 - (candidate.correlated_exposure_pct / max_correlated),
                reason=f"مواجهه همبسته {candidate.correlated_exposure_pct:.1%} بیش از {max_correlated:.0%}",
                details={
                    "correlated_exposure_pct": candidate.correlated_exposure_pct,
                    "max_allowed": max_correlated,
                },
            )

        return GateResult(
            gate_name="portfolio",
            verdict=GateVerdict.PASS,
            score=1.0,
            reason="ریسک پرتفوی در محدوده مجاز",
            details={
                "open_risk_pct": candidate.open_risk_pct,
                "correlated_exposure_pct": candidate.correlated_exposure_pct,
            },
        )

    async def _gate_execution(self, candidate: SignalCandidate, market: str) -> GateResult:
        """Gate 10: Execution — can the signal be executed in the current market?"""
        cfg = self._policy.get_gate_config("execution", market)
        min_spread = cfg.get("min_spread_pct", 0.0)

        if candidate.spread_pct > min_spread > 0:
            return GateResult(
                gate_name="execution",
                verdict=GateVerdict.WARN,
                score=1.0 - (candidate.spread_pct / max(min_spread, 0.001)),
                reason=f"اسپرد بالا: {candidate.spread_pct:.3f}% (حداکثر {min_spread:.3f}%)",
                details={"spread_pct": candidate.spread_pct, "max_spread": min_spread},
            )

        return GateResult(
            gate_name="execution",
            verdict=GateVerdict.PASS,
            score=1.0,
            reason="شرایط اجرا مناسب",
            details={
                "price": candidate.price,
                "spread_pct": candidate.spread_pct,
                "entry_zone": candidate.entry_zone,
            },
        )

    # ── Smart Override Resolution ───────────────────────────────────────────

    async def _resolve_gate_override(
        self,
        candidate: SignalCandidate,
        market: str,
    ) -> GateOverride:
        """Evaluate market conditions and return a GateOverride.

        Delegates to ``SmartDecisionGate`` which reads:
          - ``brsapi_index_values`` for 3-day volatility.
          - ``brsapi_symbol_snapshots`` / ``brsapi_historical_daily`` for
            volume surge detection.
        """
        try:
            return await self._decision_gate.evaluate(
                symbol=candidate.symbol,
                market=market,
            )
        except Exception as e:
            logger.debug("SmartDecisionGate failed for %s: %s — no override", candidate.symbol, e)
            return GateOverride()

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _detect_regime(self, candidate: SignalCandidate) -> str:
        """Detect market regime from signal features + cross-market real data.

        Returns one of: TREND, RANGE, HIGH_VOLATILITY, CRISIS, UNKNOWN

        Priority:
          1. Cross-market real data (from CrossMarketCorrelator) — most accurate
          2. Volatility heuristic fallback — when no real data available
        """
        # ── Try to get real cross-market regime from DB ──
        import time

        cached = _cached_regime_data.get(candidate.market, {})
        if cached and time.time() - cached.get("fetched_at", 0) < 300:
            regime = cached.get("regime")
            if isinstance(regime, str):
                return regime

        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is not None:
                async with async_session_factory() as session:
                    r = await session.execute(
                        text("""
                        SELECT index_change_pct
                        FROM brsapi_index_values
                        WHERE name = 'شاخص کل'
                          AND index_change_pct IS NOT NULL
                        ORDER BY date DESC, fetched_at DESC
                        LIMIT 1
                    """)
                    )
                    row = r.fetchone()
                    if row:
                        change = float(row[0])
                        if abs(change) >= 1.5:
                            cross_regime = "TREND" if change > 0 else "CRISIS"
                        elif abs(change) >= 0.8:
                            cross_regime = "TREND" if change > 0 else "HIGH_VOLATILITY"
                        else:
                            cross_regime = "RANGE"

                        _cached_regime_data[candidate.market] = {
                            "fetched_at": time.time(),
                            "regime": cross_regime,
                        }
                        return cross_regime
        except Exception as e:
            logger.debug("Cross-market regime detection failed: %s — using fallback", e)

        # ── Fallback: volatility + trend strength heuristic ──
        vol = candidate.volatility_regime
        trend_strength = abs(candidate.raw_score - 0.5) * 2  # 0-1

        if vol > 0.80:
            return "CRISIS"
        if vol > 0.65:
            return "HIGH_VOLATILITY"
        if trend_strength > 0.60:
            return "TREND"
        if trend_strength < 0.30:
            return "RANGE"

        return "UNKNOWN"

    def _compute_net_expectancy(self, candidate: SignalCandidate, market: str) -> float:
        """Compute net expectancy in R-multiples after costs (market-aware)."""
        cfg = self._policy.get_gate_config("expectancy", market)
        costs_pct = float(cfg.get("costs_pct", 0.003))
        win_rate = candidate.calibrated_probability
        loss_rate = 1.0 - win_rate
        rr = candidate.risk_reward

        gross = win_rate * rr - loss_rate * 1.0
        cost_r = costs_pct / abs(candidate.stop_loss_pct) if abs(candidate.stop_loss_pct) > 0.001 else costs_pct

        return round(gross - cost_r, 4)

    def signal_grade(self, decision: Decision) -> str:
        """Assign a grade (A+ / A / B / WATCHLIST / REJECT) with market-aware thresholds."""
        grades = self._policy.get_grades_config(decision.market)

        prob = decision.calibrated_probability
        rr = decision.risk_reward_ratio
        net_exp = decision.net_expectancy_r
        warnings = decision.warning_count()

        # A+
        a_plus = grades.get("a_plus", {})
        gates_ok = not a_plus.get("all_pass_required", True) or decision.all_gates_pass()
        if (
            prob >= a_plus.get("min_probability", 0.70)
            and rr >= a_plus.get("min_rr", 2.0)
            and net_exp >= a_plus.get("min_expectancy", 0.20)
            and gates_ok
            and decision.is_releasable()
        ):
            return "A+"

        # A
        a_grade = grades.get("a", {})
        if (
            prob >= a_grade.get("min_probability", 0.65)
            and rr >= a_grade.get("min_rr", 1.5)
            and net_exp >= a_grade.get("min_expectancy", 0.12)
            and warnings <= a_grade.get("max_warnings", 1)
        ):
            return "A"

        # B
        b_grade = grades.get("b", {})
        if (
            prob >= b_grade.get("min_probability", 0.60)
            and rr >= b_grade.get("min_rr", 1.0)
            and net_exp >= b_grade.get("min_expectancy", 0.05)
            and warnings <= b_grade.get("max_warnings", 2)
        ):
            return "B"

        # Watchlist / Reject
        if decision.is_watchlisted():
            return "WATCHLIST"
        return "REJECT"


# ── Singleton ────────────────────────────────────────────────────────────────

_decision_engine: SignalDecisionEngine | None = None


def get_decision_engine(
    policy_path: str | None = None,
    session: Any = None,
    instance: SignalDecisionEngine | None = None,
) -> SignalDecisionEngine:
    """Get or create the SignalDecisionEngine.

    Args:
        policy_path: optional path to a YAML/JSON policy config.
        session: optional database session for market-condition queries.
        instance: optional pre-built instance to use instead of the singleton.
                  When provided, the singleton is bypassed entirely — use this
                  in tests or when a fresh engine with different config is needed.

    The first call without *instance* caches the engine. Subsequent calls
    with different policy_path/session return the cached instance.
    """
    if instance is not None:
        return instance
    global _decision_engine
    if _decision_engine is None:
        policy = SignalPolicy(json_path=policy_path) if policy_path else SignalPolicy()
        decision_gate = SmartDecisionGate(session=session)
        _decision_engine = SignalDecisionEngine(
            policy=policy,
            session=session,
            decision_gate=decision_gate,
        )
    return _decision_engine
