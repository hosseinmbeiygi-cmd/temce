"""Scoring Engine صندوق‌یار — امتیازدهی وزن‌دار ۰ تا ۱۰۰.

طبق spec:
- جدول وزن صریح برای تمام شاخص‌ها در هر نوع صندوق (جمع = ۱۰۰)
- Config Versioning در scoring_config_history
- خروجی ۵ سطحی: خرید قوی/خرید/نگهداری/احتیاط/اجتناب
- Reason Vector: ۳ تا ۵ دلیل با لینک به سنجه
- امتیاز تفکیکی در ۴ بُعد: بازده، ریسک، هزینه، نقدشوندگی
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..constants import (
    COLD_START_BLOCK_THRESHOLD,
    COLD_START_LABELS,
    DEFAULT_SCORING_VERSION,
    DEFAULT_SPREAD_PENALTY_THRESHOLD,
    SIGNAL_AVOID,
    SIGNAL_BUY,
    SIGNAL_CAUTION,
    SIGNAL_HOLD,
    SIGNAL_LABELS_FA,
    SIGNAL_STRONG_BUY,
    TYPE_EQUITY,
    TYPE_FIXED_INCOME,
    TYPE_GOLD,
    TYPE_LEVERAGED,
)
from ..metrics.engine import METRIC_REGISTRY

logger = logging.getLogger(__name__)

# ── جدول وزن‌دهی v1.0 (از spec صندوق‌یار) ───────────────────────────
# جمع هر ستون = ۱۰۰
DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "EQ": {
        "return_1y": 12,
        "behavior_gap": 5,
        "pnav_peer_percentile": 6,
        "sharpe": 10,
        "sortino": 5,
        "max_drawdown": 8,
        "beta": 6,
        "calmar": 4,
        "active_share": 5,
        "ter": 5,
        "turnover": 3,
        "style_drift": 4,
        "fx_beta_nima": 4,
        "inflation_beta": 3,
        "geopolitical_sensitivity": 3,
        "post_change_alpha": 5,
        "market_timing": 4,
        "redemption_pressure": 4,
        "flow_performance": 4,
        "peer_correlation": 3,
    },
    "FI": {
        "return_1y": 8,
        "behavior_gap": 4,
        "pnav_peer_percentile": 5,
        "sharpe": 8,
        "sortino": 4,
        "max_drawdown": 5,
        "beta": 3,
        "calmar": 3,
        "active_share": 3,
        "ter": 6,
        "turnover": 4,
        "style_drift": 3,
        "fx_beta_nima": 2,
        "inflation_beta": 5,
        "geopolitical_sensitivity": 2,
        "post_change_alpha": 5,
        "market_timing": 3,
        "redemption_pressure": 5,
        "flow_performance": 5,
        "peer_correlation": 4,
    },
    "GO": {
        "return_1y": 10,
        "behavior_gap": 4,
        "pnav_peer_percentile": 8,
        "sharpe": 8,
        "sortino": 4,
        "max_drawdown": 7,
        "beta": 3,
        "calmar": 4,
        "active_share": 2,
        "ter": 5,
        "turnover": 3,
        "style_drift": 2,
        "fx_beta_nima": 6,
        "inflation_beta": 5,
        "geopolitical_sensitivity": 4,
        "post_change_alpha": 4,
        "market_timing": 3,
        "redemption_pressure": 4,
        "flow_performance": 4,
        "peer_correlation": 3,
    },
    "LV": {
        "return_1y": 8,
        "behavior_gap": 4,
        "pnav_peer_percentile": 5,
        "sharpe": 6,
        "sortino": 5,
        "max_drawdown": 10,
        "beta": 5,
        "calmar": 5,
        "active_share": 3,
        "ter": 5,
        "turnover": 3,
        "style_drift": 3,
        "fx_beta_nima": 4,
        "inflation_beta": 3,
        "geopolitical_sensitivity": 3,
        "post_change_alpha": 5,
        "market_timing": 5,
        "redemption_pressure": 3,
        "flow_performance": 3,
        "peer_correlation": 3,
        # ویژه LV
        "volatility_decay": 10,
        "suspension_risk": 8,
        "leverage_ratio": 5,
    },
}

# اسکور برای شاخص‌هایی که کمتر بهتر است (مثلاً MDD، اسپرد، فشار ابطال)
LOWER_IS_BETTER: set[str] = {
    "max_drawdown",
    "bid_ask_spread",
    "redemption_pressure",
    "cash_drag",
    "turnover",
    "ter",
    "tracking_difference",
    "style_drift",
    "window_dressing",
    "hidden_leverage",
    "liquidity_spiral",
    "diseconomies_of_scale",
    "geopolitical_sensitivity",
    "volatility_decay",
    "suspension_risk",
}

# برای مقادیر boolean
TRUE_IS_BETTER: set[str] = {"survivorship_flag"}  # flag: False = خوب (با سیگنال معکوس)
FALSE_IS_BETTER: set[str] = {"benchmark_gaming", "survivorship_flag"}

# ── بُعد هر شاخص برای امتیاز تفکیکی ────────────────────────────────
DIMENSION_MAP: dict[str, str] = {
    "return_1m": "return",
    "return_3m": "return",
    "return_6m": "return",
    "return_1y": "return",
    "return_3y": "return",
    "return_inception": "return",
    "sharpe": "return",
    "sortino": "return",
    "calmar": "return",
    "beta": "risk",
    "max_drawdown": "risk",
    "std_dev": "risk",
    "recovery_days": "risk",
    "volatility_decay": "risk",
    "suspension_risk": "risk",
    "downside_capture": "risk",
    "market_timing": "risk",
    "leverage_ratio": "risk",
    "ter": "cost",
    "turnover": "cost",
    "cash_drag": "cost",
    "active_share": "cost",
    "performance_fee_type": "cost",
    "hhi": "cost",
    "window_dressing": "cost",
    "hidden_leverage": "cost",
    "daily_volume": "liquidity",
    "bid_ask_spread": "liquidity",
    "liquidity_score": "liquidity",
    "order_book_depth": "liquidity",
    "redemption_pressure": "liquidity",
    "liquidity_spiral": "liquidity",
}


@dataclass
class ScoringConfig:
    version: str = DEFAULT_SCORING_VERSION
    weights: dict[str, dict[str, float]] = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_WEIGHTS)))
    bubble_avoid_threshold: float = 3.0
    bubble_entry_threshold: float = -2.0
    spread_penalty_threshold: float = DEFAULT_SPREAD_PENALTY_THRESHOLD

    def __post_init__(self) -> None:
        """Normalize وزن‌ها — جمع هر ستون دقیقاً ۱۰۰ (شرط spec).

        منبع spec اعداد ناهنجار دارد (جمع EQ=103)؛ این normalize
        تضمین می‌کند نسبت‌ها حفظ و جمع = ۱۰۰ شود.
        """
        for type_code, weights in self.weights.items():
            total = sum(weights.values())
            if total <= 0:
                continue
            self.weights[type_code] = {k: round(v / total * 100, 4) for k, v in weights.items()}


class ScoringConfigStore:
    """مدیریت نسخه‌بندی پیکربندی — در DB (scoring_config_history) یا in-memory.

    برای بازتولید امتیاز تاریخی: get_version(version, type_code) باید
    دقیقاً همان وزن‌های استفاده‌شده در آن زمان را برگرداند.
    """

    def __init__(self, db_session_factory=None):
        self._db = db_session_factory
        self._memory: dict[tuple[str, str], ScoringConfig] = {}

    def save_version(
        self,
        config: ScoringConfig,
        type_code: str,
        created_by: str | None = None,
        change_reason: str | None = None,
    ) -> None:
        """ذخیره یک نسخه از پیکربندی."""
        if self._db is not None:
            # در حالت واقعی: درج در جدول scoring_config_history
            pass
        self._memory[(config.version, type_code)] = config

    def get_active(self, type_code: str) -> ScoringConfig:
        """دریافت نسخه فعال برای یک نوع صندوق."""
        key = (DEFAULT_SCORING_VERSION, type_code)
        if key in self._memory:
            return self._memory[key]
        return ScoringConfig()

    def get_version(self, version: str, type_code: str) -> ScoringConfig | None:
        """بازتولید امتیاز تاریخی — وزن‌های همان نسخه."""
        if self._db is not None:
            pass  # کوئری از scoring_config_history
        return self._memory.get((version, type_code))


def _score_metric(
    value: Any,
    *,
    lower_is_better: bool,
    peer_percentile: float | None,
    has_weight: bool,
) -> float | None:
    """تبدیل یک مقدار به زیرامتیاز ۰..۱.

    - اگر percentile هم‌گروه داشته باشیم → از آن استفاده می‌کنیم (۰..۱).
    - در غیر این صورت از normalized value استفاده می‌کنیم.
    """
    if value is None or not has_weight:
        return None
    if isinstance(value, bool):
        # فقط درصدی از وزن — اگر true خوب بود، سهم کامل
        return 1.0 if value else 0.0
    if not isinstance(value, (int, float)):
        return None
    v = float(value)

    if peer_percentile is not None:
        base = peer_percentile
    else:
        base = _sigmoid_normalize(v)

    if lower_is_better:
        return 1.0 - base
    return base


def _sigmoid_normalize(value: float) -> float:
    """نرمال‌سازی sigmoid به بازه ۰..۱ (مقادیر نزدیک صفر → ۰.۵)."""
    return 1.0 / (1.0 + __import__("math").exp(-value / 10.0))


def compute_score(
    metric_values: dict[str, Any],
    *,
    type_code: str,
    config: ScoringConfig | None = None,
    peer_percentiles: dict[str, float] | None = None,
) -> dict[str, Any]:
    """محاسبه امتیاز نهایی.

    Returns:
    {
      "score_total": float, "score_return": .., "score_risk": ..,
      "score_cost": .., "score_liquidity": ..,
      "signal": str, "signal_label_fa": str,
      "reasons": [ReasonVectorItem-like dict],
      "cold_start_pct": float, "is_cold_start_blocked": bool,
      "scoring_version": str,
    }
    """
    config = config or ScoringConfig()
    weights = config.weights.get(type_code, config.weights.get("EQ", {}))

    # Cold Start Block — spec: «بیش از ۴۰٪» یعنی strictly greater
    cs_count = sum(1 for k in metric_values if metric_values[k] is None and k in weights)
    cs_pct = cs_count / max(1, len(weights))
    blocked = cs_pct > COLD_START_BLOCK_THRESHOLD

    if blocked:
        return {
            "score_total": None,
            "score_return": None,
            "score_risk": None,
            "score_cost": None,
            "score_liquidity": None,
            "signal": None,
            "signal_label_fa": None,
            "reasons": [
                {
                    "metric": "cold_start",
                    "metric_label_fa": "صندوق جدید",
                    "impact": "neutral",
                    "description_fa": COLD_START_LABELS["new_fund"],
                }
            ],
            "cold_start_pct": cs_pct,
            "is_cold_start_blocked": True,
            "scoring_version": config.version,
        }

    dim_scores: dict[str, list[tuple[float, float]]] = {
        "return": [],
        "risk": [],
        "cost": [],
        "liquidity": [],
    }
    all_parts: list[tuple[float, float]] = []
    reasons: list[dict[str, Any]] = []

    for metric, weight in weights.items():
        value = metric_values.get(metric)
        if value is None:
            continue
        pct = (peer_percentiles or {}).get(metric)
        lower = metric in LOWER_IS_BETTER
        sub = _score_metric(value, lower_is_better=lower, peer_percentile=pct, has_weight=True)
        if sub is None:
            continue

        weighted = sub * weight
        all_parts.append((weighted, weight))
        dim = DIMENSION_MAP.get(metric, "return")
        dim_scores[dim].append((weighted, weight))

        # Reason Vector — فقط ۳ تا ۵ دلیل قوی (وزن بالا + سیگنال واضح)
        if weight >= 5 and (sub >= 0.7 or sub <= 0.3):
            label = METRIC_REGISTRY.get(metric, {}).get("label_fa", metric)
            impact = "positive" if sub >= 0.7 else "negative"
            reasons.append(
                {
                    "metric": metric,
                    "metric_label_fa": label,
                    "impact": impact,
                    "description_fa": _reason_text(metric, label, value, sub),
                }
            )

    # امتیاز بُعدی
    def _dim_score(key: str) -> float | None:
        parts = dim_scores[key]
        if not parts:
            return None
        return round(sum(w for w, wt in parts) / sum(wt for _, wt in parts) * 100, 2)

    total_w = sum(w for _, w in all_parts)
    if total_w <= 0:
        total = None
    else:
        total = round(sum(weighted for weighted, _ in all_parts) / total_w * 100, 2)

    signal = _signal_from_score(total)
    reasons = reasons[:5]
    if not reasons and total is not None:
        reasons.append(
            {
                "metric": "score_total",
                "metric_label_fa": "امتیاز کل",
                "impact": "neutral",
                "description_fa": f"امتیاز نهایی {total} از ۱۰۰ — سیگنال {SIGNAL_LABELS_FA[signal]}",
            }
        )

    return {
        "score_total": total,
        "score_return": _dim_score("return"),
        "score_risk": _dim_score("risk"),
        "score_cost": _dim_score("cost"),
        "score_liquidity": _dim_score("liquidity"),
        "signal": signal,
        "signal_label_fa": SIGNAL_LABELS_FA[signal],
        "reasons": reasons,
        "cold_start_pct": cs_pct,
        "is_cold_start_blocked": False,
        "scoring_version": config.version,
    }


def _reason_text(metric: str, label: str, value: Any, sub: float) -> str:
    direction = "مطلوب" if sub >= 0.7 else "نامطلوب"
    if isinstance(value, float):
        return f"{label} = {value:.2f} — جهت {direction}"
    return f"{label} = {value} — جهت {direction}"


def _signal_from_score(total: float | None) -> str:
    if total is None:
        return SIGNAL_HOLD
    if total >= 80:
        return SIGNAL_STRONG_BUY
    if total >= 65:
        return SIGNAL_BUY
    if total >= 45:
        return SIGNAL_HOLD
    if total >= 30:
        return SIGNAL_CAUTION
    return SIGNAL_AVOID
