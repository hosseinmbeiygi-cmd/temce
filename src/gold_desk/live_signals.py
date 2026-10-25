"""Live Trading Signals — تشخیص real-time سیگنال با مقایسه snapshot قبل/فعلی.

این ماژول در هر snapshot job (هر ۵ دقیقه):
1. snapshot قبلی را از Redis می‌خواند
2. اختلاف قیمت (Δ) و درصد تغییر را محاسبه می‌کند
3. اگه threshold رد شود → signal ثبت می‌شود
4. سیگنال‌های جدید از طریق WebSocketHub broadcast می‌شوند
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass

from .constants import (
    LIVE_AED_SPIKE_PCT,
    LIVE_BUBBLE_EXTREME_PCT,
    LIVE_PREV_SNAPSHOT_TTL_SEC,
    LIVE_PRICE_SPIKE_CRITICAL_PCT,
    LIVE_PRICE_SPIKE_PCT,
    LIVE_SCORE_DELTA,
    LIVE_SIGNAL_COOLDOWN_SEC,
    LIVE_USD_SPIKE_PCT,
)

logger = logging.getLogger(__name__)

REDIS_KEY_PREV_SNAP = "golddesk:snapshot:prev"
REDIS_KEY_RECENT_SIGNALS = "golddesk:signals:recent"
# نام قدیمی برای سازگاری با مصرف‌کنندگان بیرونی؛ مقدار از constants می‌آید (E-M6).
SIGNAL_COOLDOWN_SEC = LIVE_SIGNAL_COOLDOWN_SEC


def _unwrap_prev_snapshot(payload, now: float | None = None) -> dict | None:
    """snapshot قبلی را از پیلود Redis بیرون می‌کشد و پیلود **کهنه** را رد می‌کند.

    پیلود جدید شکل ``{"ts": <epoch>, "snapshot": {...}}`` دارد تا بتوان سن آن را
    سنجید؛ پیش‌تر TTL یک روزه بود و پس از ری‌استارت یا بین دو روز، «تغییر ۵
    دقیقه‌ای» با snapshot دیروز مقایسه می‌شد و سیگنال کاذب می‌ساخت (E-M7).
    پیلود بدون wrapper (شکل قدیمی) برای سازگاری عقب‌رو پذیرفته می‌شود.
    """
    if not payload:
        return None
    data = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    if not isinstance(data, dict):
        return None
    if "snapshot" in data and "ts" in data:
        age = (now if now is not None else time.time()) - float(data.get("ts") or 0)
        if age > LIVE_PREV_SNAPSHOT_TTL_SEC:
            logger.info("prev snapshot is stale (%.0fs) — comparison skipped", age)
            return None
        snapshot = data.get("snapshot")
        return snapshot if isinstance(snapshot, dict) else None
    return data


@dataclass(frozen=True)
class Signal:
    """یک سیگنال live."""

    symbol: str
    signal_type: str  # spike_up | spike_down | break_resistance | bubble_extreme | score_change
    severity: str  # info | warn | critical
    title: str
    description: str
    current_value: float
    threshold: float
    change_pct: float | None = None
    ts: float = 0.0

    def to_dict(self) -> dict:
        return {**asdict(self), "ts": self.ts or time.time()}


def detect_spike(prev: float, curr: float, threshold: float = 1.0) -> str | None:
    """تشخیص spike: تغییر > threshold% در یک snapshot."""
    if prev <= 0 or curr <= 0:
        return None
    pct = (curr - prev) / prev * 100.0
    if abs(pct) >= threshold:
        return "spike_up" if pct > 0 else "spike_down"
    return None


def detect_signals(prev_snap: dict | None, curr_snap: dict) -> list[Signal]:
    """مقایسه snapshot قبل و فعلی، ساخت لیست signal."""
    signals: list[Signal] = []
    now = time.time()

    if not prev_snap:
        return signals

    prev_coins = prev_snap.get("coins", {})
    curr_coins = curr_snap.get("coins", {})
    # score گم‌شده یعنی «مقایسه ناممکن»، نه صفر: پیش‌تر دلتا برابر امتیاز فعلی
    # می‌شد و یک سیگنال کاذب «تغییر امتیاز» می‌ساخت (E-M8).
    prev_score = prev_snap.get("score", {}).get("total")
    curr_score = curr_snap.get("score", {}).get("total")
    prev_refs = prev_snap.get("references", {})
    curr_refs = curr_snap.get("references", {})

    # ── 1. Spike قیمت سکه/طلا (threshold 1.5%) ─────────────
    for k, c in curr_coins.items():
        prev_c = prev_coins.get(k, {})
        prev_p = prev_c.get("market_price", 0)
        curr_p = c.get("market_price", 0)
        sig_type = detect_spike(prev_p, curr_p, threshold=LIVE_PRICE_SPIKE_PCT)
        if sig_type:
            change = ((curr_p - prev_p) / prev_p * 100) if prev_p else 0
            signals.append(
                Signal(
                    symbol=c.get("symbol", k),
                    signal_type=sig_type,
                    severity="critical" if abs(change) >= LIVE_PRICE_SPIKE_CRITICAL_PCT else "warn",
                    title=f"تغییر ناگهانی {c.get('display_name', k)}",
                    description=f"قیمت در ۵ دقیقه {change:+.2f}٪ تغییر کرد",
                    current_value=curr_p,
                    threshold=LIVE_PRICE_SPIKE_PCT,
                    change_pct=change,
                    ts=now,
                )
            )

    # ── 2. تغییر امتیاز کلی (threshold از constants) ─────────
    if prev_score is None or curr_score is None:
        score_delta = None
    else:
        score_delta = curr_score - prev_score
    if score_delta is not None and abs(score_delta) >= LIVE_SCORE_DELTA:
        signals.append(
            Signal(
                symbol="GLOBAL",
                signal_type="score_change",
                severity="info",
                title="تغییر امتیاز کلی",
                description=f"امتیاز از {prev_score} به {curr_score} ({score_delta:+d})",
                current_value=curr_score,
                threshold=LIVE_SCORE_DELTA,
                change_pct=score_delta,
                ts=now,
            )
        )

    # ── 3. تغییر دلار (threshold 2%) ─────────────────────────
    for fx, threshold in [("USD", LIVE_USD_SPIKE_PCT), ("AED", LIVE_AED_SPIKE_PCT)]:
        prev_fx = prev_refs.get(fx.lower() + "_irt", 0)
        curr_fx = curr_refs.get(fx.lower() + "_irt", 0)
        if not prev_fx or not curr_fx:
            continue
        change = (curr_fx - prev_fx) / prev_fx * 100
        if abs(change) >= threshold:
            signals.append(
                Signal(
                    symbol=fx,
                    signal_type="spike_up" if change > 0 else "spike_down",
                    severity="warn",
                    title=f"تغییر {fx}",
                    description=f"{change:+.2f}٪ در ۵ دقیقه",
                    current_value=curr_fx,
                    threshold=threshold,
                    change_pct=change,
                    ts=now,
                )
            )

    # ── 4. حباب شدید ──────────────────────────────────────
    for k, c in curr_coins.items():
        bpct = c.get("bubble_pct", 0)
        if bpct and abs(bpct) >= LIVE_BUBBLE_EXTREME_PCT:
            signals.append(
                Signal(
                    symbol=c.get("symbol", k),
                    signal_type="bubble_extreme",
                    severity="critical",
                    title=f"حباب شدید {c.get('display_name', k)}",
                    description=(
                        f"حباب {bpct:.1f}٪ — قدرمطلق بالای {LIVE_BUBBLE_EXTREME_PCT:.0f}٪ (اشباع)"
                    ),
                    current_value=bpct,
                    threshold=LIVE_BUBBLE_EXTREME_PCT,
                    change_pct=None,
                    ts=now,
                )
            )

    return signals


async def detect_and_broadcast(curr_snap: dict) -> list[Signal]:
    """مقایسه با snapshot قبلی، broadcast signals، ذخیره prev."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        prev_raw = await cache.get(REDIS_KEY_PREV_SNAP)
        prev_snap = _unwrap_prev_snapshot(prev_raw)

        signals = detect_signals(prev_snap, curr_snap)

        # ذخیره snapshot فعلی همراه با زمان ساخت؛ TTL کوتاه‌تر از یک بازهٔ کامل
        # شبانه تا مقایسه هرگز روی دادهٔ دیروز انجام نشود (E-M7).
        payload = {"ts": time.time(), "snapshot": curr_snap}
        await cache.set(
            REDIS_KEY_PREV_SNAP,
            json.dumps(payload, default=str),
            ttl=LIVE_PREV_SNAPSHOT_TTL_SEC,
        )

        # Cooldown: signal تکراری در ۱۰ دقیقه skip
        recent_raw = await cache.get(REDIS_KEY_RECENT_SIGNALS) or []
        recent: list[dict] = json.loads(recent_raw) if isinstance(recent_raw, str) else recent_raw
        now = time.time()
        recent = [s for s in recent if now - s.get("ts", 0) < SIGNAL_COOLDOWN_SEC]

        unique: list[Signal] = []
        for s in signals:
            key = f"{s.symbol}:{s.signal_type}"
            if any(r.get("key") == key and now - r.get("ts", 0) < SIGNAL_COOLDOWN_SEC for r in recent):
                continue
            unique.append(s)
            recent.append({"key": key, "ts": now, "signal": s.to_dict()})

        await cache.set(REDIS_KEY_RECENT_SIGNALS, json.dumps(recent, default=str), ttl=3600)

        # publish در Redis؛ process API آن را به کلاینت‌های WebSocket می‌رساند
        # (این process کلاینتی ندارد و broadcast محلی بی‌اثر بود).
        if unique:
            try:
                from .ws_hub import publish_ws_event

                for s in unique:
                    await publish_ws_event({"type": "signal", "data": s.to_dict()})
            except Exception as exc:
                logger.debug("signal publish failed: %s", exc)

        return unique
    except Exception as exc:
        logger.warning("detect_and_broadcast failed: %s", exc)
        return []
