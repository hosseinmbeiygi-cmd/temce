"""Hot Path — آماده‌سازی snapshot سریع برای معاملات لحظه‌ای.

این ماژول یک endpoint سبک فراهم می‌کنه که:
- فقط فیلدهای ضروری را برمی‌گرداند (نه همه assetها)
- از cache در Redis استفاده می‌کنه
- quick signal (خرید/صبر/فروش) بر اساس bubble ارائه می‌دهد
- latency < 50ms
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from .constants import BUBBLE_GREEN_MAX, BUBBLE_ORANGE_MAX, BUBBLE_YELLOW_MAX, REDIS_KEY_SNAPSHOT

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuickSignal:
    """سیگنال سریع برای معامله‌گر."""

    action: str  # "buy" | "hold" | "sell" | "wait"
    confidence: float  # 0-1
    bubble_pct: float
    reason: str


def compute_quick_signal(bubble_pct: float | None) -> QuickSignal:
    """سیگنال سریع فقط بر اساس bubble.

    - < 5% → buy (high confidence)
    - 5-12% → buy light
    - 12-22% → hold
    - > 22% → sell
    """
    if bubble_pct is None:
        return QuickSignal("wait", 0.0, 0.0, "data unavailable")

    if bubble_pct < 0:
        return QuickSignal("buy", 0.9, bubble_pct, f"حباب منفی {bubble_pct:.1f}٪ — فرصت طلایی")
    if bubble_pct < 5:
        return QuickSignal("buy", 0.85, bubble_pct, f"حباب {bubble_pct:.1f}٪ — خرید قوی")
    if bubble_pct < BUBBLE_GREEN_MAX:
        return QuickSignal("buy", 0.65, bubble_pct, f"حباب {bubble_pct:.1f}٪ — خرید با احتیاط")
    if bubble_pct < BUBBLE_YELLOW_MAX:
        return QuickSignal("hold", 0.55, bubble_pct, f"حباب {bubble_pct:.1f}٪ — صبر")
    if bubble_pct < BUBBLE_ORANGE_MAX:
        return QuickSignal("hold", 0.7, bubble_pct, f"حباب {bubble_pct:.1f}٪ — احتیاط جدی")
    return QuickSignal("sell", 0.9, bubble_pct, f"حباب {bubble_pct:.1f}٪ — اشباع خرید")


async def get_hot_snapshot() -> dict | None:
    """snapshot سریع از Redis cache.

    Returns None اگه cache خالیه.
    """
    try:
        from core.cache import get_cache

        cache = get_cache()
        raw = await cache.get(REDIS_KEY_SNAPSHOT)
        if not raw:
            return None
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as exc:
        logger.debug("hot snapshot fetch failed: %s", exc)
        return None


def build_hotpath_response(snap: dict | None) -> dict:
    """ساخت response کم‌حجم برای polling سریع.

    فقط: refs + score + سیگنال coin_emami + ۳ صندوق برتر.
    """
    if not snap:
        return {
            "success": True,
            "data": {
                "status": "no_data",
                "message": "snapshot هنوز آماده نیست",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

    refs = snap.get("references", {})
    score = snap.get("score", {})
    coins = snap.get("coins", {})
    funds = snap.get("funds", [])

    emami = coins.get("coin_emami", {})
    bubble_pct = emami.get("bubble_pct")
    signal = compute_quick_signal(bubble_pct)

    # ۳ صندوق برتر بر اساس BPR
    top_funds = sorted(funds, key=lambda f: f.get("bpr", 0), reverse=True)[:3]

    return {
        "success": True,
        "data": {
            "status": "ok",
            "timestamp": snap.get("snapshot_at", datetime.now(UTC).isoformat()),
            "refs": {
                "xau_usd": refs.get("xau_usd"),
                "usd_irt": refs.get("usd_irt"),
                "aed_gap_pct": refs.get("aed_gap_pct"),
            },
            "score": {
                "total": score.get("total"),
                "decision": score.get("decision"),
            },
            "signal": {
                "action": signal.action,
                "confidence": signal.confidence,
                "reason": signal.reason,
            },
            "coin_emami": {
                "market": emami.get("market_price"),
                "fair": emami.get("fair_value"),
                "bubble_pct": bubble_pct,
                "implied_usd": emami.get("implied_usd"),
            },
            "top_funds": [
                {
                    "symbol": f.get("symbol"),
                    "name": f.get("fund_name"),
                    "nav": f.get("nav_per_unit"),
                    "bubble_pct": f.get("bubble_pct"),
                    "bpr": f.get("bpr"),
                }
                for f in top_funds
            ],
        },
    }
