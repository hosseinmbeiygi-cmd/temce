"""Event Calendar — تقویم رویدادهای اقتصادی پیش‌رو مرتبط با بازار طلا.

رویدادهای برنامه‌ریزی‌شده (تصمیم نرخ بهره، انتشار CPI، ...) که ممکن است
بر قیمت طلا تأثیر بگذارند.

این ماژول اطلاعاتی است (informational) و به scorer وصل نمی‌شود — همانند
macro_news.py طبق قرارداد C6/E-M10. داده از یک seed دستی است تا زمانی که
منبع زنده فراهم شود.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from core.time import utc_now_naive

logger = logging.getLogger(__name__)

REDIS_KEY_CALENDAR = "golddesk:calendar:events"
REDIS_KEY_CALENDAR_CACHE_DAYS = 1

VALID_CATEGORIES = frozenset(
    {"rate", "inflation", "fx", "demand", "geopolitics", "other"}
)


@dataclass(frozen=True)
class ScheduledEvent:
    event_name: str
    scheduled_at: datetime
    category: str  # see VALID_CATEGORIES
    importance: int  # 1 (low) | 2 (medium) | 3 (high)
    source: str  # cbi | markaz_amar | fed | ecb | wgc | other

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["scheduled_at"] = self.scheduled_at.isoformat()
        d["is_past"] = self.scheduled_at < utc_now_naive()
        return d


def get_seed_events() -> list[ScheduledEvent]:
    """دادهٔ اولیهٔ دستی — رویدادهای اقتصادی برنامه‌ریزی‌شدهٔ مرتبط با طلا.

    این لیست به‌صورت دستی نگه‌داری می‌شود. تا زمانی که منبع خودکار فراهم
    نشود، مالک باید رویدادهای آیندهٔ واقعی را در این‌جا ثبت کند.

    تاریخ‌ها نسبی (timedelta) هستند چون seed داینامیک نیست و بایست از نزدیک
    با رویدادهای واقعی هماهنگ شود.
    """
    now = utc_now_naive()
    return [
        ScheduledEvent(
            event_name="تصمیم نرخ بهره بانک مرکزی ایران — جلسهٔ فصل پاییز ۱۴۰۵",
            scheduled_at=now + timedelta(days=14),
            category="rate",
            importance=3,
            source="cbi",
        ),
        ScheduledEvent(
            event_name="انتشار نرخ تورم نقطه‌به‌نقطه (مرکز آمار) — آبان ۱۴۰۵",
            scheduled_at=now + timedelta(days=21),
            category="inflation",
            importance=3,
            source="markaz_amar",
        ),
        ScheduledEvent(
            event_name="جلسهٔ FOMC فدرال رزرو — نوامبر ۲۰۲۶",
            scheduled_at=now + timedelta(days=35),
            category="rate",
            importance=3,
            source="fed",
        ),
        ScheduledEvent(
            event_name="گزارش تقاضای جهانی طلا — Q4 2026 (WGC)",
            scheduled_at=now + timedelta(days=60),
            category="demand",
            importance=2,
            source="wgc",
        ),
        ScheduledEvent(
            event_name="انتشار آمار M2 بانک مرکزی — مهر ۱۴۰۵",
            scheduled_at=now - timedelta(days=5),
            category="fx",
            importance=2,
            source="cbi",
        ),
    ]


def get_calendar_events(days_ahead: int = 30) -> list[ScheduledEvent]:
    """فیلتر رویدادها از seed بر اساس بازهٔ زمانی.

    days_ahead=0: فقط رویدادهای گذشته یا امروز.
    days_ahead=30: رویدادهای ۳۰ روز آینده + همهٔ گذشته.
    نتیجه بر اساس scheduled_at از قدیم به جدید مرتب است.
    """
    horizon = utc_now_naive() + timedelta(days=days_ahead)
    events = [ev for ev in get_seed_events() if ev.scheduled_at <= horizon]
    return sorted(events, key=lambda e: e.scheduled_at)


async def refresh_calendar_cache(
    events_provider=get_seed_events,
    cache=None,
) -> list[ScheduledEvent]:
    """ذخیرهٔ رویدادها در cache.

    events_provider injectable است تا در تست بتوان provider دلخواه تزریق کرد
    (همان الگوی WS3 در refresh_macro_events_cache).
    """
    from core.cache import get_cache

    events = events_provider()
    if not events:
        return []

    _cache = cache if cache is not None else get_cache()
    try:
        payload = json.dumps([e.to_dict() for e in events], ensure_ascii=False)
        await _cache.set(
            REDIS_KEY_CALENDAR,
            payload,
            ttl=REDIS_KEY_CALENDAR_CACHE_DAYS * 86400,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("calendar cache write failed: %s", exc)

    return events
