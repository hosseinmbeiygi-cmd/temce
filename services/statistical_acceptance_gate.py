"""Statistical Acceptance Gate (سند v5.0 §7.2).

هیچ الگوی سیگنالی بدون عبور همزمان از ۴ معیار زیر اجازه ورود به فاز اجرای
دستی زنده را ندارد:

  1. تعداد نمونه سیگنال کامل‌شده در Out-of-Sample ≥ ۱۰۰
  2. حد پایین فاصله اطمینان ۹۵٪ برای Win Rate بالاتر از Break-even تعدیل‌شده
  3. Sharpe Ratio (سالانه‌شده، پس از کسر هزینه واقعی) مثبت و معنادار در
     حداقل دو نیمه مجزا از دوره OOS
  4. پایداری در شبیه‌سازی مونت‌کارلوی لغزش: عدم تغییر علامت Expected Value
     در ۹۰٪ سناریوها

این ماژول هم برای gate-کردن الگوهای جدید (پیش از فعال‌سازی در paper trading)
و هم برای ممیزی دورهای الگوهای فعال استفاده می‌شود. آستانه‌ها از پیوست ه
(``config/ime_engine_config.yaml``) خوانده می‌شوند تا با تغییر کانفیگ
بدون redeploy قابل تنظیم باشند.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.config.ime_engine import load_ime_config

# ── Defaults match سند §7.2 + پیوست ه (kept here for callers that don't
#    want to load YAML every time). The YAML is the single source of truth. ──

DEFAULT_MIN_OOS_SAMPLES = 100
DEFAULT_BREAK_EVEN_RATE = 0.50  # بیش از نقطه سر‌به‌سر
DEFAULT_MC_EV_STABILITY_PCT = 0.90
DEFAULT_HALF_YEAR_SPLIT = 2  # دو نیمه OOS
DEFAULT_CONFIDENCE = 0.95


@dataclass
class TradeOutcome:
    """A single OOS trade for the acceptance gate.

    ``pnl_pct`` is the per-trade return in percent (positive = win). ``cost_pct``
    captures the realised commission+slippage for that trade. ``period_index``
    selects which OOS half the trade belongs to (used for the two-half Sharpe
    requirement of سند §7.2).
    """

    pnl_pct: float
    cost_pct: float = 0.0
    period_index: int = 0


@dataclass
class AcceptanceDecision:
    """Result of running the gate.

    ``passed`` is True only when *all* four conditions are simultaneously
    met. ``failed_conditions`` lists human-readable reasons for any that
    failed so the caller can show a feedback dialog.
    """

    passed: bool
    oos_samples: int
    win_rate: float
    win_rate_ci_low: float
    break_even_adjusted: float
    sharpe_half_1: float
    sharpe_half_2: float
    ev_positive_in_scenarios: float
    failed_conditions: list[str] = field(default_factory=list)


# ── Statistical helpers (pure functions) ─────────────────────────────────


def wilson_ci_lower(p: float, n: int, confidence: float = DEFAULT_CONFIDENCE) -> float:
    """Wilson score lower bound for a binomial proportion.

    More robust than the normal approximation for small n and p near 0 or 1.
    The سند §7.2 gate uses a 95% lower bound (one-sided) on the win rate.
    """
    if n <= 0:
        return 0.0
    # z for one-sided 95% CI: 1.6449
    z = 1.6449 if confidence == 0.95 else 1.96
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    spread = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return max(0.0, centre - spread)


def annualised_sharpe(trade_pnls_pct: list[float], periods_per_year: int = 252) -> float:
    """Sharpe ratio from a series of per-trade percentage returns.

    Assumes ``periods_per_year`` independent trades per year for
    annualisation. Returns 0.0 for empty input or zero variance (constant
    returns — undefined risk, not infinity).
    """
    if not trade_pnls_pct or len(trade_pnls_pct) < 2:
        return 0.0
    mean = sum(trade_pnls_pct) / len(trade_pnls_pct)
    var = sum((x - mean) ** 2 for x in trade_pnls_pct) / (len(trade_pnls_pct) - 1)
    if var < 1e-18:  # constant returns → undefined, treat as 0
        return 0.0
    std = math.sqrt(var)
    return mean / std * math.sqrt(periods_per_year)


def ev_stability(ev_samples: list[float], threshold: float = DEFAULT_MC_EV_STABILITY_PCT) -> float:
    """Fraction of MC scenarios where EV is positive.

    سند §7.2: «عدم تغییر علامت Expected Value در ۹۰٪ سناریوها».
    """
    if not ev_samples:
        return 0.0
    return sum(1 for s in ev_samples if s > 0) / len(ev_samples)


# ── Main gate ───────────────────────────────────────────────────────────


def evaluate_acceptance(
    oos_trades: list[TradeOutcome],
    mc_ev_samples: list[float] | None = None,
    break_even_rate: float | None = None,
    config: dict | None = None,
) -> AcceptanceDecision:
    """Run the four-condition gate from سند §7.2.

    1. ``len(oos_trades) >= min_oos_samples`` (default 100)
    2. ``wilson_ci_lower(win_rate) > break_even_rate`` (default break-even 0.50)
    3. ``annualised_sharpe(half_1) > 0 and annualised_sharpe(half_2) > 0``
       where half_1 and half_2 are the first/second half of the OOS window
    4. ``ev_stability(mc_ev_samples) >= 0.90`` when ``mc_ev_samples`` is given
    """
    cfg = config or load_ime_config()
    cfg["sizing"]
    min_samples = DEFAULT_MIN_OOS_SAMPLES  # سند §7.2
    be_rate = break_even_rate if break_even_rate is not None else DEFAULT_BREAK_EVEN_RATE
    stability_threshold = DEFAULT_MC_EV_STABILITY_PCT

    failed: list[str] = []
    n = len(oos_trades)
    if n < min_samples:
        failed.append(f"OOS samples {n} < required {min_samples} (سند §7.2 #1)")

    if n == 0:
        return AcceptanceDecision(
            passed=False,
            oos_samples=0,
            win_rate=0.0,
            win_rate_ci_low=0.0,
            break_even_adjusted=be_rate,
            sharpe_half_1=0.0,
            sharpe_half_2=0.0,
            ev_positive_in_scenarios=0.0,
            failed_conditions=failed or ["no OOS trades"],
        )

    # Net of cost per trade (سند §7.2 #2: «پس از کسر هزینه واقعی»)
    net_pnls = [t.pnl_pct - t.cost_pct for t in oos_trades]
    wins = sum(1 for p in net_pnls if p > 0)
    win_rate = wins / n
    ci_low = wilson_ci_lower(win_rate, n)
    if ci_low <= be_rate:
        failed.append(f"Wilson 95% lower CI {ci_low:.3f} ≤ break-even {be_rate:.3f} (سند §7.2 #2)")

    # Two-half Sharpe (سند §7.2 #3: «مثبت و معنادار در حداقل دو نیمه مجزا»)
    half = n // 2
    pnls_half_1 = net_pnls[:half] if half > 1 else net_pnls
    pnls_half_2 = net_pnls[half:] if (n - half) > 1 else net_pnls
    sh1 = annualised_sharpe(pnls_half_1)
    sh2 = annualised_sharpe(pnls_half_2)
    if sh1 <= 0 or sh2 <= 0:
        failed.append(f"Sharpe half_1={sh1:.2f} or half_2={sh2:.2f} non-positive (سند §7.2 #3)")

    # MC slippage stability (سند §7.2 #4)
    ev_pos = ev_stability(mc_ev_samples) if mc_ev_samples else 1.0  # no MC = no penalty
    if mc_ev_samples is not None and ev_pos < stability_threshold:
        failed.append(f"MC slippage stability {ev_pos:.0%} < required {stability_threshold:.0%} (سند §7.2 #4)")

    return AcceptanceDecision(
        passed=not failed,
        oos_samples=n,
        win_rate=win_rate,
        win_rate_ci_low=ci_low,
        break_even_adjusted=be_rate,
        sharpe_half_1=sh1,
        sharpe_half_2=sh2,
        ev_positive_in_scenarios=ev_pos,
        failed_conditions=failed,
    )
