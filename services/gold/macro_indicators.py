"""محرک‌های کلان طلا — پاریتهٔ درهم، نرخ واقعی و فید مقاوم قیمت.

سه بخش:

  • سیگنال پاریتهٔ درهم دبی:
        Dubai_Implied_USD = AED_Rate * 3.6725
        Spread = (Tehran_USD - Dubai_USD) / Dubai_USD * 100
    وقتی اسپرد از ۱٫۵٪ عبور کند، ریسک بازقیمت‌گذاری طلا در تهران علامت
    می‌خورد. واحد ``aed_rate`` هر چه باشد (ریال یا تومان) نرخ ضمنی هم
    همان واحد را دارد؛ نسبت بدون بُعد است.

  • وضعیت کلان: رابطهٔ معکوس بازده واقعی TIPS ۱۰ ساله با طلا، به‌همراه
    شاخص دلار (DXY) و روند طلا برای جمع‌بندی posture.

  • فید مقاوم: تلاش به ترتیب اولویت ارائه‌دهنده‌ها، با timeout و رد
    دادهٔ کهنه‌تر از ۱۲۰ ثانیه.

همهٔ توابع pure هستند به‌جز ``fetch_resilient_gold_spot`` که فقط از
callableهای تزریق‌شده (mock-friendly) استفاده می‌کند.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime
from typing import Any

# ── پاریتهٔ درهم (پگ رسمی امارات) ─────────────────────────────────
AED_PEG: float = 3.6725
GOLD_REPRICING_SPREAD_THRESHOLD: float = 1.5  # درصد

# ── آستانه‌های کلان ───────────────────────────────────────────────
TIPS_ACCOMMODATIVE_MAX: float = 1.0  # ≤ ۱٪ = محرک صعودی طلا
TIPS_RESTRICTIVE_MIN: float = 2.0  # ≥ ۲٪ = محرک نزولی طلا
# Classic DXY levels are only meaningful for a *true* DXY series.  DTWEXBGS
# (broad dollar index) lives on a different scale, so it uses percentiles of
# its own stored history instead (see ``evaluate_gold_macro_posture``).
DXY_WEAK_MAX: float = 95.0  # ≤ ۹۵ = دلار ضعیف (فقط DXY کلاسیک)
DXY_STRONG_MIN: float = 105.0  # ≥ ۱۰۵ = دلار قوی (فقط DXY کلاسیک)
DXY_CLASSIC_SERIES: frozenset[str] = frozenset({"DXY", "USDX", "DXY_INDEX"})
DEFAULT_DXY_SERIES: str = "DTWEXBGS"
DEFAULT_DXY_PERCENTILE_LOW: float = 20.0
DEFAULT_DXY_PERCENTILE_HIGH: float = 80.0
DEFAULT_DXY_MIN_SAMPLES: int = 30
POSTURE_INSUFFICIENT_HISTORY: str = "insufficient_history"
_GOLD_TRENDS = ("up", "down", "sideways")

# ── فید قیمت ──────────────────────────────────────────────────────
DEFAULT_TIMEOUT_SECONDS: float = 5.0
MAX_STALENESS_SECONDS: float = 120.0

# Provider calls run in a process-wide bounded pool. See the timeout note in
# ``fetch_resilient_gold_spot`` for the hung-thread limitation.
MAX_PROVIDER_WORKERS: int = 4

_provider_executor: ThreadPoolExecutor | None = None
_provider_executor_lock = threading.Lock()


def _get_provider_executor() -> ThreadPoolExecutor:
    """Return the shared bounded executor used for provider calls."""
    global _provider_executor
    if _provider_executor is None:
        with _provider_executor_lock:
            if _provider_executor is None:
                _provider_executor = ThreadPoolExecutor(
                    max_workers=MAX_PROVIDER_WORKERS,
                    thread_name_prefix="gold-feed",
                )
    return _provider_executor


class GoldFeedUnavailableError(RuntimeError):
    """همهٔ ارائه‌دهنده‌ها شکست خوردند، timeout دادند یا دادهٔ کهنه دادند."""

    check_id: str
    checked_at: datetime
    primary: dict[str, Any] | None

    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        self.attempts = attempts
        summary = ", ".join(f"{a['provider']}:{a['status']}" for a in attempts)
        super().__init__(f"All gold price providers failed ({summary})")


class _StaleQuoteError(ValueError):
    def __init__(self, age_seconds: float, max_age: float) -> None:
        self.age_seconds = age_seconds
        super().__init__(
            f"quote is stale: age {age_seconds:.1f}s exceeds {max_age:.1f}s"
        )


def _require_positive(name: str, value: float) -> None:
    if value is None or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number, got {value!r}")


def calculate_aed_implied_usd(aed_rate: float, tehran_usd_rate: float) -> dict[str, Any]:
    """نرخ دلار ضمنی دبی از قیمت درهم و اسپرد آن با دلار آزاد تهران.

    اسپرد مثبت یعنی دلار تهران گران‌تر از دلار ضمنی دبی است؛ عبور از
    آستانهٔ ۱٫۵٪ به‌عنوان ریسک بازقیمت‌گذاری طلا علامت می‌خورد.
    """
    _require_positive("aed_rate", aed_rate)
    _require_positive("tehran_usd_rate", tehran_usd_rate)

    dubai_implied_usd = aed_rate * AED_PEG
    spread_pct = (tehran_usd_rate - dubai_implied_usd) / dubai_implied_usd * 100.0
    is_flagged = spread_pct > GOLD_REPRICING_SPREAD_THRESHOLD

    if is_flagged:
        signal = "TEHRAN_GOLD_REPRICING_RISK"
    elif spread_pct < -GOLD_REPRICING_SPREAD_THRESHOLD:
        signal = "TEHRAN_GOLD_DISCOUNT"
    else:
        signal = "ALIGNED"

    return {
        "aed_rate": float(aed_rate),
        "aed_peg": AED_PEG,
        "dubai_implied_usd": dubai_implied_usd,
        "tehran_usd_rate": float(tehran_usd_rate),
        "spread_pct": spread_pct,
        "threshold_pct": GOLD_REPRICING_SPREAD_THRESHOLD,
        "is_flagged": is_flagged,
        "signal": signal,
    }


def percentile(values: list[float], percentile_value: float) -> float:
    """Linear-interpolated percentile (``percentile_value`` in ``[0, 100]``)."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot take a percentile of an empty sample")
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percentile_value / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def evaluate_gold_macro_posture(
    tips_yield: float,
    dxy_index: float,
    gold_trend: str,
    *,
    dxy_history: Sequence[float] | None = None,
    dxy_series: str = DEFAULT_DXY_SERIES,
    percentile_low: float = DEFAULT_DXY_PERCENTILE_LOW,
    percentile_high: float = DEFAULT_DXY_PERCENTILE_HIGH,
    min_samples: int = DEFAULT_DXY_MIN_SAMPLES,
) -> dict[str, Any]:
    """جمع‌بندی محرک‌های کلان طلا با مدل رابطهٔ معکوس بازده واقعی.

    امتیاز هر محرک: +۱ صعودی، -۱ نزولی، ۰ خنثی. جمع سه محرک
    posture نهایی را می‌سازد. ``divergence`` وقتی روشن می‌شود که
    بازده واقعی و روند طلا خلاف رابطهٔ معکوس حرکت کنند.

    ``dxy_series`` selects the threshold model:

    * a true DXY series (``DXY`` / ``USDX`` / ``DXY_INDEX``) keeps the
      classic 95/105 levels,
    * anything else — notably the FRED broad index ``DTWEXBGS`` — uses the
      ``percentile_low`` / ``percentile_high`` thresholds computed from
      ``dxy_history``.  Fewer than ``min_samples`` observations yields the
      explicit ``insufficient_history`` posture instead of a misleading call.
    """
    if tips_yield is None or not math.isfinite(tips_yield):
        raise ValueError(
            f"tips_yield must be a finite number, got {tips_yield!r}"
        )
    _require_positive("dxy_index", dxy_index)

    trend = str(gold_trend).strip().lower() if gold_trend is not None else ""
    if trend not in _GOLD_TRENDS:
        raise ValueError(
            f"gold_trend must be one of {_GOLD_TRENDS}, got {gold_trend!r}"
        )

    series = str(dxy_series or DEFAULT_DXY_SERIES).strip().upper()
    if not (0.0 <= percentile_low < percentile_high <= 100.0):
        raise ValueError(
            "percentile thresholds must satisfy 0 <= low < high <= 100, "
            f"got {percentile_low!r} and {percentile_high!r}"
        )
    if min_samples < 2:
        raise ValueError(f"min_samples must be >= 2, got {min_samples!r}")

    if tips_yield <= TIPS_ACCOMMODATIVE_MAX:
        real_yield_score, real_yield_signal = 1, "ACCOMMODATIVE"
    elif tips_yield >= TIPS_RESTRICTIVE_MIN:
        real_yield_score, real_yield_signal = -1, "RESTRICTIVE"
    else:
        real_yield_score, real_yield_signal = 0, "NEUTRAL"

    history: list[float] = []
    for raw in dxy_history or ():
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            history.append(number)

    classic = series in DXY_CLASSIC_SERIES
    low_threshold: float | None = None
    high_threshold: float | None = None

    if classic:
        threshold_mode = "classic"
        if dxy_index <= DXY_WEAK_MAX:
            dxy_score, dxy_signal = 1, "WEAK"
        elif dxy_index >= DXY_STRONG_MIN:
            dxy_score, dxy_signal = -1, "STRONG"
        else:
            dxy_score, dxy_signal = 0, "NEUTRAL"
    else:
        threshold_mode = "percentile"
        if len(history) < min_samples:
            return {
                "tips_yield": float(tips_yield),
                "dxy_index": float(dxy_index),
                "dxy_series": series,
                "dxy_threshold_mode": threshold_mode,
                "dxy_percentile_low": None,
                "dxy_percentile_high": None,
                "dxy_history_samples": len(history),
                "gold_trend": trend,
                "real_yield_score": real_yield_score,
                "real_yield_signal": real_yield_signal,
                "dxy_score": 0,
                "dxy_signal": "INSUFFICIENT_HISTORY",
                "trend_score": {"up": 1, "down": -1, "sideways": 0}[trend],
                "composite_score": None,
                "posture": POSTURE_INSUFFICIENT_HISTORY,
                "inverse_correlation_expected": True,
                "divergence": None,
                "reasons": [
                    f"تاریخ کافی برای شاخص دلار گسترده وجود ندارد "
                    f"({len(history)} از حداقل {min_samples} نمونه)؛ "
                    "وضعیت جهت‌دار گزارش نمی‌شود."
                ],
            }
        low_threshold = percentile(history, percentile_low)
        high_threshold = percentile(history, percentile_high)
        if dxy_index <= low_threshold:
            dxy_score, dxy_signal = 1, "WEAK"
        elif dxy_index >= high_threshold:
            dxy_score, dxy_signal = -1, "STRONG"
        else:
            dxy_score, dxy_signal = 0, "NEUTRAL"

    trend_score = {"up": 1, "down": -1, "sideways": 0}[trend]
    composite_score = real_yield_score + dxy_score + trend_score

    if composite_score > 0:
        posture = "BULLISH"
    elif composite_score < 0:
        posture = "BEARISH"
    else:
        posture = "NEUTRAL"

    divergence = (real_yield_score * trend_score) < 0

    reasons: list[str] = []
    if real_yield_signal == "ACCOMMODATIVE":
        reasons.append("بازده واقعی TIPS پایین است؛ محرک صعودی طلا.")
    elif real_yield_signal == "RESTRICTIVE":
        reasons.append("بازده واقعی TIPS بالاست؛ فشار نزولی بر طلا.")
    if dxy_signal == "WEAK":
        reasons.append("شاخص دلار ضعیف است؛ محیط مساعد طلا.")
    elif dxy_signal == "STRONG":
        reasons.append("شاخص دلار قوی است؛ فشار نزولی بر طلا.")
    if divergence:
        reasons.append("روند طلا با رابطهٔ معکوس بازده واقعی هم‌جهت نیست.")
    if not reasons:
        reasons.append("محرک‌های کلان در محدودهٔ خنثی هستند.")

    return {
        "tips_yield": float(tips_yield),
        "dxy_index": float(dxy_index),
        "dxy_series": series,
        "dxy_threshold_mode": threshold_mode,
        "dxy_percentile_low": low_threshold,
        "dxy_percentile_high": high_threshold,
        "dxy_history_samples": len(history),
        "gold_trend": trend,
        "real_yield_score": real_yield_score,
        "real_yield_signal": real_yield_signal,
        "dxy_score": dxy_score,
        "dxy_signal": dxy_signal,
        "trend_score": trend_score,
        "composite_score": composite_score,
        "posture": posture,
        "inverse_correlation_expected": True,
        "divergence": divergence,
        "reasons": reasons,
    }


# ── فید مقاوم قیمت طلا ────────────────────────────────────────────


def _provider_name(provider: Any, index: int) -> str:
    name = (
        provider.get("name")
        if isinstance(provider, Mapping)
        else getattr(provider, "name", None)
    )
    return str(name) if name else f"provider_{index}"


def _provider_fetch(provider: Any) -> Any:
    fetch = (
        provider.get("fetch")
        if isinstance(provider, Mapping)
        else getattr(provider, "fetch", None)
    )
    if not callable(fetch):
        raise ValueError("provider must expose a callable 'fetch'")
    return fetch


def _quote_timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return float(value)


def _normalize_quote(
    raw: Any, now: float, max_age_seconds: float
) -> tuple[float, float, float]:
    """اعتبارسنجی پاسخ ارائه‌دهنده؛ برمی‌گرداند (price, timestamp, age)."""
    if not isinstance(raw, Mapping):
        raise ValueError("provider returned a non-mapping quote")

    price = raw.get("price")
    if price is None:
        raise ValueError("provider quote missing price")
    price = float(price)
    if not math.isfinite(price) or price <= 0:
        raise ValueError(f"price must be a finite positive number, got {price!r}")

    if raw.get("timestamp") is None:
        raise ValueError("provider quote missing timestamp")
    timestamp = _quote_timestamp(raw["timestamp"])
    if not math.isfinite(timestamp):
        raise ValueError(f"timestamp must be finite, got {timestamp!r}")

    age_seconds = now - timestamp
    if age_seconds > max_age_seconds:
        raise _StaleQuoteError(age_seconds, max_age_seconds)

    return price, timestamp, age_seconds


def fetch_resilient_gold_spot(
    providers: list[Any],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_staleness_seconds: float = MAX_STALENESS_SECONDS,
    now: float | None = None,
) -> dict[str, Any]:
    """دریافت قیمت لحظه‌ای طلا با failover به ترتیب اولویت.

    هر ارائه‌دهنده یکی از این دو شکل است::

        {"name": "brsapi", "fetch": callable}
        object with ``.name`` and ``.fetch()``

    ``fetch`` باید mapping با ``price`` (عدد مثبت) و ``timestamp``
    (epoch ثانیه یا ``datetime``) برگرداند. خطا، timeout یا دادهٔ
    کهنه‌تر از ``max_staleness_seconds`` باعث رفتن به ارائه‌دهندهٔ بعدی
    می‌شود و همهٔ تلاش‌ها در ``attempts`` گزارش می‌شوند.

    نکته: برای تحمیل timeout از thread استفاده می‌شود؛ thread واقعاً
    kill نمی‌شود، بنابراین ارائه‌دهندهٔ کاملاً قفل‌شده تا پایان فرایند
    زنده می‌ماند (محدودیت شناخته‌شدهٔ API همگام روی ویندوز).
    """
    if not providers:
        raise ValueError("providers must not be empty")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError(
            f"timeout_seconds must be a finite positive number, got {timeout_seconds!r}"
        )
    if not math.isfinite(max_staleness_seconds) or max_staleness_seconds < 0:
        raise ValueError(
            f"max_staleness_seconds must be a finite non-negative number, "
            f"got {max_staleness_seconds!r}"
        )
    if now is not None and not math.isfinite(now):
        raise ValueError(f"now must be a finite timestamp, got {now!r}")

    clock = time.time() if now is None else float(now)
    attempts: list[dict[str, Any]] = []

    # Timeout note: provider calls run in one process-wide bounded executor.
    # Python cannot kill a running thread, so a timed-out call keeps its worker
    # busy until the provider returns. The bound limits thread growth, but a
    # permanently hung provider can exhaust the pool and make later checks time
    # out immediately. HTTP providers therefore also set their own timeout.
    executor = _get_provider_executor()

    for index, provider in enumerate(providers):
        name = _provider_name(provider, index)
        started = time.perf_counter()

        try:
            fetch = _provider_fetch(provider)
        except ValueError as exc:
            attempts.append(
                {
                    "provider": name,
                    "status": "error",
                    "error": str(exc),
                    "latency_ms": 0.0,
                }
            )
            continue

        future = executor.submit(fetch)
        try:
            raw = future.result(timeout=timeout_seconds)
        except FuturesTimeout:
            future.cancel()
            latency_ms = (time.perf_counter() - started) * 1000.0
            attempts.append(
                {
                    "provider": name,
                    "status": "timeout",
                    "error": f"timed out after {timeout_seconds}s",
                    "latency_ms": latency_ms,
                }
            )
            continue
        except Exception as exc:  # هر خطای ارائه‌دهنده یعنی failover
            latency_ms = (time.perf_counter() - started) * 1000.0
            attempts.append(
                {
                    "provider": name,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": latency_ms,
                }
            )
            continue

        latency_ms = (time.perf_counter() - started) * 1000.0

        try:
            price, timestamp, age_seconds = _normalize_quote(
                raw, clock, max_staleness_seconds
            )
        except _StaleQuoteError as exc:
            attempts.append(
                {
                    "provider": name,
                    "status": "stale",
                    "error": str(exc),
                    "age_seconds": exc.age_seconds,
                    "latency_ms": latency_ms,
                }
            )
            continue
        except (TypeError, ValueError) as exc:
            attempts.append(
                {
                    "provider": name,
                    "status": "error",
                    "error": str(exc),
                    "latency_ms": latency_ms,
                }
            )
            continue

        attempts.append(
            {
                "provider": name,
                "status": "ok",
                "age_seconds": age_seconds,
                "latency_ms": latency_ms,
            }
        )
        return {
            "price": price,
            "timestamp": timestamp,
            "provider": name,
            "age_seconds": age_seconds,
            "fallback_used": index > 0,
            "sources_tried": index + 1,
            "attempts": attempts,
        }

    raise GoldFeedUnavailableError(attempts)
