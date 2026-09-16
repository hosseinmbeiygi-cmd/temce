"""Macro & News AI — داده‌های کلان اقتصادی + تحلیل تأثیر بر بازار طلا.

منابع:
- CBI (بانک مرکزی): نرخ بهره، M2، ارز
- MarkazAmar (مرکز آمار): CPI، تورم
- World Gold Council: گزارش‌های ماهانه تقاضا

هر event شامل:
- impact_score: -3 (بسیار منفی) تا +3 (بسیار مثبت) بر طلا
- confidence: 0-1
- explanation
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

import httpx

from core.time import utc_now_naive

logger = logging.getLogger(__name__)

REDIS_KEY_MACRO = "golddesk:macro:events"
REDIS_KEY_MACRO_CACHE_DAYS = 7  # cache events for 7 days


@dataclass(frozen=True)
class MacroEvent:
    title: str
    source: str  # cbi | markaz_amar | wgc | news
    category: str  # rate | inflation | fx | demand | geopolitics
    impact_score: int  # -3..+3
    confidence: float  # 0..1
    explanation: str
    published_at: datetime

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat()
        return d


# ── Heuristic impact estimation ────────────────────────────


def _score_rate_event(title: str) -> int:
    """نرخ بهره: افزایش = منفی برای طلا، کاهش = مثبت."""
    t = title.lower()
    if "افزایش" in t or "rise" in t or "increase" in t or "+" in title:
        return -2
    if "کاهش" in t or "cut" in t or "decrease" in t or "−" in title or "-" in title:
        return +2
    return 0


def _score_inflation_event(title: str) -> int:
    """تورم بالا = مثبت برای طلا (hedge)."""
    t = title.lower()
    if "افزایش" in t or "بالا" in t or "سالانه" in t or "نقطه" in t:
        return +2
    if "کاهش" in t or "پایین" in t:
        return -1
    return 0


def _score_fx_event(title: str) -> int:
    """دلار قوی = منفی، دلار ضعیف = مثبت."""
    t = title.lower()
    if "تقویت" in t or "افزایش" in t or "صعود" in t:
        return -2
    if "ضعیف" in t or "کاهش" in t or "سقوط" in t:
        return +2
    return 0


def _score_demand_event(title: str) -> int:
    """تقاضای بالا = مثبت."""
    t = title.lower()
    if "افزایش" in t or "بالا" in t or "خرید" in t:
        return +2
    if "کاهش" in t or "فروش" in t:
        return -1
    return 0


def estimate_impact(title: str, category: str) -> tuple[int, float]:
    """تخمین impact و confidence از عنوان رویداد."""
    if category == "rate":
        score = _score_rate_event(title)
    elif category == "inflation":
        score = _score_inflation_event(title)
    elif category == "fx":
        score = _score_fx_event(title)
    elif category == "demand":
        score = _score_demand_event(title)
    else:
        score = 0
    return score, 0.6  # confidence پایه


# ── نمونه events (manual seed) ────────────────────────────


def get_sample_events() -> list[MacroEvent]:
    """نمونه رویدادهای کلان برای شروع. در آینده با scraper جایگزین می‌شود."""
    now = utc_now_naive()
    return [
        MacroEvent(
            title="نرخ تورم نقطه‌به‌نقطه مرداد: ۳۱.۲٪",
            source="markaz_amar",
            category="inflation",
            impact_score=+2,
            confidence=0.85,
            explanation="تورم بالا → تقاضا برای طلا به‌عنوان hedge افزایش می‌یابد",
            published_at=now - timedelta(days=2),
        ),
        MacroEvent(
            title="افزایش نقدینگی M2 در تیر ۱۴۰۵: +۴.۸٪ ماهانه",
            source="cbi",
            category="fx",
            impact_score=+2,
            confidence=0.75,
            explanation="رشد نقدینگی → فشار تورمی → تضعیف دلار داخلی → افزایش قیمت طلا",
            published_at=now - timedelta(days=5),
        ),
        MacroEvent(
            title="تقاضای طلای بانک‌های مرکزی در Q2: +۲۱۵ تن (WGC)",
            source="wgc",
            category="demand",
            impact_score=+2,
            confidence=0.9,
            explanation="خرید قوی بانک‌های مرکزی (چین، لهستان، ترکیه) → سیگنال مثبت بلندمدت",
            published_at=now - timedelta(days=10),
        ),
        MacroEvent(
            title="کاهش قیمت اونس جهانی به دلیل تقویت دلار آمریکا",
            source="news",
            category="fx",
            impact_score=-1,
            confidence=0.7,
            explanation="تقویت DXY → فشار منفی بر قیمت طلای جهانی",
            published_at=now - timedelta(days=1),
        ),
    ]


# ── Macro impact analyzer (بهبود امتیاز) ────────────────────


def compute_macro_multiplier(events: list[MacroEvent]) -> float:
    """محاسبه ضریب تأثیر کلان برای اصلاح score نهایی.

    returns: -1 (بسیار منفی) تا +1 (بسیار مثبت)
    """
    if not events:
        return 0.0

    # فقط رویدادهای ۳۰ روز اخیر
    recent = [e for e in events if (utc_now_naive() - e.published_at).days <= 30]
    if not recent:
        return 0.0

    # weighted average از impact × confidence
    total_weight = 0.0
    weighted_score = 0.0
    for e in recent:
        # weight = confidence × decay
        days_old = (utc_now_naive() - e.published_at).days
        decay = 1.0 / (1 + days_old * 0.1)
        w = e.confidence * decay
        total_weight += w
        weighted_score += e.impact_score * w

    if total_weight == 0:
        return 0.0

    # نرمال‌سازی: impact_score بین -3..+3
    avg = weighted_score / total_weight
    return max(-1.0, min(1.0, avg / 3.0))


async def fetch_macro_events() -> list[MacroEvent]:
    """بارگذاری events از cache یا seed."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        raw = await cache.get(REDIS_KEY_MACRO)
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            events = [
                MacroEvent(
                    title=e["title"],
                    source=e["source"],
                    category=e["category"],
                    impact_score=e["impact_score"],
                    confidence=e["confidence"],
                    explanation=e["explanation"],
                    published_at=datetime.fromisoformat(e["published_at"]),
                )
                for e in data
            ]
            return events
    except Exception as exc:
        logger.debug("macro cache fetch failed: %s", exc)

    # seed
    events = get_sample_events()
    with contextlib.suppress(Exception):
        from core.cache import get_cache

        cache = get_cache()
        await cache.set(
            REDIS_KEY_MACRO,
            json.dumps([e.to_dict() for e in events], default=str),
            ttl=86400 * REDIS_KEY_MACRO_CACHE_DAYS,
        )
    return events


# ── News scraper (RSS / CBI / MarkazAmar) ────────────────────


async def scrape_cbi_news() -> list[MacroEvent]:
    """scrape سرصفحه اخبار CBI."""
    events: list[MacroEvent] = []
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(
                "https://www.cbi.ir/",
                headers={"User-Agent": "Temce GoldDesk/1.0"},
            )
            if r.status_code == 200:
                # regex ساده برای پیدا کردن عناوین
                titles = re.findall(r"<h\d[^>]*>(.*?)</h\d>", r.text, re.DOTALL)
                for t in titles[:10]:
                    clean = re.sub(r"<[^>]+>", "", t).strip()
                    if 10 < len(clean) < 200:
                        score, conf = estimate_impact(clean, "rate")
                        events.append(
                            MacroEvent(
                                title=clean,
                                source="cbi",
                                category="rate",
                                impact_score=score,
                                confidence=conf,
                                explanation="استخراج خودکار از cbi.ir",
                                published_at=utc_now_naive(),
                            )
                        )
    except Exception as exc:
        logger.debug("CBI scrape failed: %s", exc)
    return events
