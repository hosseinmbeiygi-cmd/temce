from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field

from apps.api.error_handlers import safe_error_message
from schemas.common.responses import ApiResponse

router = APIRouter()


# ── Subscription Models (in-memory) ──────────────────────────────────────


class SubscriptionCreate(BaseModel):
    name: str = Field(default="", description="A friendly name for this subscription")
    channel: str = Field(..., pattern=r"^(email|telegram|both)$", description="Notification channel")
    email: str | None = Field(default=None, description="Email address")
    telegram_id: str | None = Field(default=None, description="Telegram user ID / chat ID")
    min_importance: int = Field(default=3, ge=1, le=3, description="Minimum importance level")
    categories: list[str] = Field(default_factory=list, description="Categories to subscribe to (empty = all)")


class SubscriptionResponse(BaseModel):
    id: str
    name: str
    channel: str
    email: str | None = None
    telegram_id: str | None = None
    min_importance: int
    categories: list[str]
    created_at: str
    enabled: bool = True


# In-memory subscription store (would use DB in production)
_subscriptions: dict[str, dict[str, Any]] = {}


def _subscribe(sub: SubscriptionCreate) -> SubscriptionResponse:
    sid = uuid.uuid4().hex[:12]
    now = datetime.now(UTC).isoformat()
    entry = {
        "id": sid,
        "name": sub.name or f"اشتراک {sid[:4]}",
        "channel": sub.channel,
        "email": sub.email,
        "telegram_id": sub.telegram_id,
        "min_importance": sub.min_importance,
        "categories": sub.categories,
        "created_at": now,
        "enabled": True,
    }
    _subscriptions[sid] = entry
    return SubscriptionResponse(**entry)


# ── Economic events database ──────────────────────────────────────────────

EVENTS: list[dict[str, Any]] = [
    # ── Central Bank ──
    {
        "id": "ev-001",
        "date": "2026-07-08",
        "time": "13:30",
        "title": "نرخ بهره بانک مرکزی",
        "country": "🇮🇷 ایران",
        "category": "بانک مرکزی",
        "importance": 3,
        "forecast": "23.0%",
        "previous": "23.0%",
        "analysis": "افزایش نرخ بهره معمولاً منجر به خروج پول از بورس به سمت سپرده‌های بانکی می‌شود. کاهش نرخ بهره می‌تواند سیگنال مثبتی برای بازار سهام باشد. ثبات نرخ بهره نشان‌دهنده تداوم سیاست فعلی بانک مرکزی است.",
    },
    {
        "id": "ev-002",
        "date": "2026-07-31",
        "time": "15:00",
        "title": "نرخ بهره فدرال رزرو",
        "country": "🇺🇸 آمریکا",
        "category": "بانک مرکزی",
        "importance": 3,
        "forecast": "5.25%",
        "previous": "5.50%",
        "analysis": "کاهش نرخ بهره آمریکا دلار را تضعیف می‌کند و می‌تواند باعث افزایش قیمت طلا و کاهش ارزش دلار در بازار ایران شود. افزایش نرخ بهره آمریکا معمولاً فشار بر بازارهای نوظهور از جمله ایران افزایش می‌دهد.",
    },
    {
        "id": "ev-003",
        "date": "2026-07-18",
        "time": "13:15",
        "title": "نرخ بهره بانک مرکزی اروپا",
        "country": "🇪🇺 اروپا",
        "category": "بانک مرکزی",
        "importance": 3,
        "forecast": "4.00%",
        "previous": "4.25%",
        "analysis": "نرخ بهره ECB بر ارزش یورو در برابر دلار تأثیر مستقیم دارد. تغییرات آن بر بازارهای کالایی و قیمت نفت تأثیر می‌گذارد و به‌صورت غیرمستقیم بر بازار ایران اثرگذار است.",
    },
    {
        "id": "ev-004",
        "date": "2026-07-15",
        "time": "15:30",
        "title": "صورتجلسه فدرال رزرو",
        "country": "🇺🇸 آمریکا",
        "category": "بانک مرکزی",
        "importance": 2,
        "forecast": "",
        "previous": "",
        "analysis": "صورتجلسه نشان‌دهنده جهت‌گیری آینده نرخ بهره است. لحن اعضا (hawkish/dovish) می‌تواند جهت دلار و بازارهای جهانی را تا جلسه بعد تعیین کند.",
    },
    # ── تورم ──
    {
        "id": "ev-010",
        "date": "2026-07-25",
        "time": "12:00",
        "title": "شاخص قیمت مصرف‌کننده (CPI) ایران",
        "country": "🇮🇷 ایران",
        "category": "تورم",
        "importance": 3,
        "forecast": "30.5%",
        "previous": "31.2%",
        "analysis": "کاهش نرخ تورم سیگنال مثبتی برای بازار سرمایه است زیرا انتظار کاهش نرخ بهره را ایجاد می‌کند. افزایش تورم فشار بر هزینه‌های شرکتها و حاشیه سود آنها وارد می‌کند.",
    },
    {
        "id": "ev-011",
        "date": "2026-07-12",
        "time": "16:30",
        "title": "CPI آمریکا",
        "country": "🇺🇸 آمریکا",
        "category": "تورم",
        "importance": 3,
        "forecast": "3.3%",
        "previous": "3.4%",
        "analysis": "CPI بالاتر از پیش‌بینی به معنی تداوم سیاست انقباضی فدرال رزرو است که برای بازارهای سهام جهانی منفی است. CPI پایین‌تر احتمال کاهش نرخ بهره را افزایش می‌دهد.",
    },
    {
        "id": "ev-012",
        "date": "2026-07-31",
        "time": "16:30",
        "title": "PCE قیمت‌های مصرفی آمریکا",
        "country": "🇺🇸 آمریکا",
        "category": "تورم",
        "importance": 2,
        "forecast": "2.7%",
        "previous": "2.8%",
        "analysis": "PCE شاخص تورم مورد علاقه فدرال رزرو است. کاهش آن سیگنال قوی‌تری برای کاهش نرخ بهره نسبت به CPI دارد.",
    },
    {
        "id": "ev-013",
        "date": "2026-07-04",
        "time": "11:30",
        "title": "CPI اتحادیه اروپا",
        "country": "🇪🇺 اروپا",
        "category": "تورم",
        "importance": 2,
        "forecast": "2.5%",
        "previous": "2.6%",
        "analysis": "تورم اروپا بر سیاست‌های ECB و ارزش یورو تأثیر می‌گذارد. کاهش تورم در اروپا می‌تواند به افزایش قیمت کامودیتی‌ها به دلیل ضعف دلار منجر شود.",
    },
    # ── اشتغال ──
    {
        "id": "ev-020",
        "date": "2026-07-05",
        "time": "16:30",
        "title": "گزارش اشتغال آمریکا (NFP)",
        "country": "🇺🇸 آمریکا",
        "category": "اشتغال",
        "importance": 3,
        "forecast": "185K",
        "previous": "272K",
        "analysis": "NFP پایین‌تر از پیش‌بینی می‌تواند منجر به تضعیف دلار و افزایش قیمت طلا شود. NFP بالاتر نشان‌دهنده قدرت اقتصاد آمریکا و احتمال تداوم نرخ‌های بالای بهره است.",
    },
    {
        "id": "ev-021",
        "date": "2026-07-05",
        "time": "16:30",
        "title": "نرخ بیکاری آمریکا",
        "country": "🇺🇸 آمریکا",
        "category": "اشتغال",
        "importance": 3,
        "forecast": "4.0%",
        "previous": "4.0%",
        "analysis": "نرخ بیکاری پایین نشان‌دهنده اقتصاد قوی اما فشار تورمی بیشتر است. افزایش بیکاری می‌تواند فدرال رزرو را به سمت سیاست انبساطی سوق دهد که برای بازارهای نوظهور مثبت است.",
    },
    {
        "id": "ev-022",
        "date": "2026-07-23",
        "time": "12:00",
        "title": "نرخ بیکاری ایران",
        "country": "🇮🇷 ایران",
        "category": "اشتغال",
        "importance": 2,
        "forecast": "8.7%",
        "previous": "8.9%",
        "analysis": "کاهش نرخ بیکاری نشان‌دهنده بهبود فعالیت‌های اقتصادی است که می‌تواند بر تقاضای داخلی و درآمد شرکت‌های بورسی تأثیر مثبت بگذارد.",
    },
    {
        "id": "ev-023",
        "date": "2026-07-10",
        "time": "16:30",
        "title": "ادعاهای بیکاری آمریکا",
        "country": "🇺🇸 آمریکا",
        "category": "اشتغال",
        "importance": 2,
        "forecast": "235K",
        "previous": "238K",
        "analysis": "کاهش ادعاهای بیکاری نشانه قدرت بازار کار است. افزایش آن می‌تواند نشانه اولیه ضعف اقتصادی باشد که بر احساسات بازار تأثیر می‌گذارد.",
    },
    # ── GDP ──
    {
        "id": "ev-030",
        "date": "2026-07-25",
        "time": "16:30",
        "title": "GDP آمریکا (Q2 اولیه)",
        "country": "🇺🇸 آمریکا",
        "category": "GDP",
        "importance": 3,
        "forecast": "2.1%",
        "previous": "1.6%",
        "analysis": "GDP قوی‌تر از انتظار نشان‌دهنده سلامت اقتصاد آمریکا و احتمال تداوم نرخ‌های بهره بالاست. GDP ضعیف‌تر انتظارات کاهش نرخ بهره را تقویت می‌کند.",
    },
    {
        "id": "ev-031",
        "date": "2026-07-15",
        "time": "15:00",
        "title": "GDP چین (Q2)",
        "country": "🇨🇳 چین",
        "category": "GDP",
        "importance": 2,
        "forecast": "5.1%",
        "previous": "5.3%",
        "analysis": "GDP چین بر قیمت کامودیتی‌ها (نفت، مس، فولاد) تأثیر مستقیم دارد. رشد قوی چین به معنی افزایش تقاضا برای مواد اولیه است که برای صادرات ایران مفید است.",
    },
    {
        "id": "ev-032",
        "date": "2026-07-30",
        "time": "15:30",
        "title": "GDP آلمان (Q2)",
        "country": "🇩🇪 آلمان",
        "category": "GDP",
        "importance": 2,
        "forecast": "0.1%",
        "previous": "-0.2%",
        "analysis": "آلمان بزرگترین اقتصاد اروپا است. رکود یا رشد آن بر کل اقتصاد اروپا و تقاضای کالاهای صنعتی تأثیر می‌گذارد.",
    },
    # ── نفت و انرژی ──
    {
        "id": "ev-040",
        "date": "2026-07-03",
        "time": "—",
        "title": "نشست اوپک پلاس",
        "country": "🌍 جهانی",
        "category": "انرژی",
        "importance": 3,
        "forecast": "",
        "previous": "",
        "analysis": "تصمیمات اوپک پلاس درباره سقف تولید مستقیماً بر قیمت نفت تأثیر می‌گذارد. کاهش تولید = افزایش قیمت نفت که برای ایران و شرکت‌های پتروشیمی بورس مثبت است.",
    },
    {
        "id": "ev-041",
        "date": "2026-07-16",
        "time": "18:00",
        "title": "گزارش هفتگی ذخایر نفت آمریکا (EIA)",
        "country": "🇺🇸 آمریکا",
        "category": "انرژی",
        "importance": 2,
        "forecast": "-2.1M",
        "previous": "-1.5M",
        "analysis": "کاهش ذخایر نفت آمریکا نشانه تقاضای بالا و عاملی برای افزایش قیمت نفت است. افزایش ذخایر فشار نزولی بر قیمت نفت وارد می‌کند.",
    },
    {
        "id": "ev-042",
        "date": "2026-07-09",
        "time": "18:00",
        "title": "ذخایر نفت خام آمریکا",
        "country": "🇺🇸 آمریکا",
        "category": "انرژی",
        "importance": 2,
        "forecast": "",
        "previous": "-1.2M",
        "analysis": "تغییرات هفتگی ذخایر نفت تأثیر کوتاه‌مدت بر قیمت نفت دارد. روند کاهشی ذخایر نشانه تعادل عرضه و تقاضاست.",
    },
    # ── بازار بورس ایران ──
    {
        "id": "ev-050",
        "date": "2026-07-06",
        "time": "08:30",
        "title": "بازار بورس بازگشایی شد",
        "country": "🇮🇷 ایران",
        "category": "بورس ایران",
        "importance": 1,
        "forecast": "",
        "previous": "",
        "analysis": "بازگشایی بازار پس از تعطیلات آخر هفته. معمولاً روزهای شنبه بازار با نوساناتی همراه است زیرا سرمایه‌گذاران به رویدادهای آخر هفته واکنش نشان می‌دهند.",
    },
    {
        "id": "ev-051",
        "date": "2026-07-15",
        "time": "12:00",
        "title": "مهلت ارائه گزارش‌های فصلی (کدال)",
        "country": "🇮🇷 ایران",
        "category": "بورس ایران",
        "importance": 2,
        "forecast": "",
        "previous": "",
        "analysis": "شرکت‌ها موظف به ارائه گزارش عملکرد فصلی خود هستند. گزارش‌های خوب می‌توانند منجر به رشد قیمت سهم و گزارش‌های ضعیف باعث اصلاح قیمت شوند.",
    },
    {
        "id": "ev-052",
        "date": "2026-07-22",
        "time": "—",
        "title": "تعطیلی بازار به مناسبت تاسوعا و عاشورا",
        "country": "🇮🇷 ایران",
        "category": "بورس ایران",
        "importance": 2,
        "forecast": "",
        "previous": "",
        "analysis": "بازار سرمایه در ایام تعطیلات رسمی تعطیل است. معمولاً روزهای قبل و بعد از تعطیلات طولانی حجم معاملات کاهش می‌یابد.",
    },
    {
        "id": "ev-053",
        "date": "2026-07-23",
        "time": "—",
        "title": "تعطیلی بازار به مناسبت تاسوعا و عاشورا",
        "country": "🇮🇷 ایران",
        "category": "بورس ایران",
        "importance": 2,
        "forecast": "",
        "previous": "",
        "analysis": "دومین روز تعطیلی. در این گونه تعطیلات دو روزه، معمولاً بازار روز بازگشایی با نوسانات بیشتری همراه است.",
    },
    # ── داده‌های صنعتی ──
    {
        "id": "ev-060",
        "date": "2026-07-01",
        "time": "10:30",
        "title": "PMI تولیدی ایران",
        "country": "🇮🇷 ایران",
        "category": "صنعت",
        "importance": 2,
        "forecast": "52.5",
        "previous": "53.1",
        "analysis": "PMI بالای ۵۰ نشان‌دهنده رشد بخش تولید است. کاهش PMI از ۵۳ به ۵۲.۵ نشانه کاهش سرعت رشد است که می‌تواند بر سهام شرکت‌های تولیدی تأثیر منفی بگذارد.",
    },
    {
        "id": "ev-061",
        "date": "2026-07-01",
        "time": "16:45",
        "title": "PMI تولیدی آمریکا (ISM)",
        "country": "🇺🇸 آمریکا",
        "category": "صنعت",
        "importance": 2,
        "forecast": "48.7",
        "previous": "48.7",
        "analysis": "PMI زیر ۵۰ نشانه رکود در بخش تولید است. PMI ضعیف آمریکا احتمال کاهش نرخ بهره را افزایش می‌دهد که برای بازارهای نوظهور مثبت است.",
    },
    {
        "id": "ev-062",
        "date": "2026-07-03",
        "time": "16:45",
        "title": "PMI خدمات آمریکا (ISM)",
        "country": "🇺🇸 آمریکا",
        "category": "صنعت",
        "importance": 2,
        "forecast": "53.2",
        "previous": "53.8",
        "analysis": "بخش خدمات بزرگترین بخش اقتصاد آمریکاست. PMI خدمات بالای ۵۰ نشان‌دهنده رشد است. کاهش آن می‌تواند نشانه کاهش کلی فعالیت اقتصادی باشد.",
    },
    {
        "id": "ev-063",
        "date": "2026-07-08",
        "time": "18:00",
        "title": "شاخص تولید صنعتی آلمان",
        "country": "🇩🇪 آلمان",
        "category": "صنعت",
        "importance": 1,
        "forecast": "0.3%",
        "previous": "-0.1%",
        "analysis": "تولید صنعتی آلمان شاخص مهمی برای سلامت اقتصاد اروپاست. رشد آن به معنی افزایش تقاضا برای کالاهای صنعتی است.",
    },
    # ── داده‌های خارجی ──
    {
        "id": "ev-070",
        "date": "2026-07-11",
        "time": "08:00",
        "title": "حجم معاملات خرده فروشی ایران",
        "country": "🇮🇷 ایران",
        "category": "مصرف",
        "importance": 1,
        "forecast": "",
        "previous": "",
        "analysis": "افزایش فروش خرده‌فروشی نشان‌دهنده رونق تقاضای مصرفی است که برای شرکت‌های مصرفی و خرده‌فروشی بورس مثبت است.",
    },
    {
        "id": "ev-071",
        "date": "2026-07-16",
        "time": "16:30",
        "title": "فروش خرده فروشی آمریکا",
        "country": "🇺🇸 آمریکا",
        "category": "مصرف",
        "importance": 2,
        "forecast": "0.3%",
        "previous": "0.1%",
        "analysis": "مخارج مصرفی ۷۰٪ اقتصاد آمریکا را تشکیل می‌دهد. افزایش فروش خرده‌فروشی نشانه قدرت اقتصادی است اما می‌تواند تورم را افزایش دهد.",
    },
    {
        "id": "ev-072",
        "date": "2026-07-18",
        "time": "16:30",
        "title": "ادعاهای بیکاری آمریکا",
        "country": "🇺🇸 آمریکا",
        "category": "اشتغال",
        "importance": 1,
        "forecast": "240K",
        "previous": "235K",
        "analysis": "افزایش هفتگی ادعاهای بیکاری می‌تواند نشانه سرد شدن بازار کار باشد که برای سیاست پولی انبساطی محرک است.",
    },
    # ── طلا و ارز ──
    {
        "id": "ev-080",
        "date": "2026-07-28",
        "time": "—",
        "title": "حراج سکه طلا (مرکز مبادله)",
        "country": "🇮🇷 ایران",
        "category": "طلا و ارز",
        "importance": 2,
        "forecast": "",
        "previous": "",
        "analysis": "حراج سکه مرکز مبادله بر قیمت سکه و طلا در بازار داخلی تأثیر می‌گذارد. عرضه بیشتر سکه می‌تواند قیمت‌ها را متعادل کند.",
    },
    {
        "id": "ev-081",
        "date": "2026-07-04",
        "time": "12:00",
        "title": "نرخ ارز توافقی (نیما)",
        "country": "🇮🇷 ایران",
        "category": "طلا و ارز",
        "importance": 2,
        "forecast": "",
        "previous": "",
        "analysis": "نرخ نیما به عنوان قیمت پایه ارز برای واردات و صادرات استفاده می‌شود. افزایش آن می‌تواند به نفع شرکت‌های صادراتی و به ضرر شرکت‌های وارداتی باشد.",
    },
    # ── بین‌الملل ──
    {
        "id": "ev-090",
        "date": "2026-07-09",
        "time": "—",
        "title": "نشست G20",
        "country": "🌍 جهانی",
        "category": "سیاسی",
        "importance": 2,
        "forecast": "",
        "previous": "",
        "analysis": "نشست G20 بر سیاست‌های تجاری و اقتصادی جهانی تأثیر می‌گذارد. هرگونه توافق یا تنش تجاری بر بازارهای نوظهور تأثیر مستقیم دارد.",
    },
    {
        "id": "ev-091",
        "date": "2026-07-16",
        "time": "14:00",
        "title": "شاخص ZEWsentiment آلمان",
        "country": "🇩🇪 آلمان",
        "category": "اقتصاد",
        "importance": 1,
        "forecast": "18.5",
        "previous": "17.5",
        "analysis": "شاخص ZEW احساسات سرمایه‌گذاران نسبت به اقتصاد آلمان را اندازه‌گیری می‌کند. افزایش آن نشانه خوش‌بینی به آینده اقتصادی اروپاست.",
    },
    {
        "id": "ev-092",
        "date": "2026-07-24",
        "time": "16:30",
        "title": "سفارشات کالاهای بادوام آمریکا",
        "country": "🇺🇸 آمریکا",
        "category": "صنعت",
        "importance": 2,
        "forecast": "0.5%",
        "previous": "0.1%",
        "analysis": "افزایش سفارشات کالاهای بادوام نشانه رشد سرمایه‌گذاری صنعتی است. این شاخص بر قیمت فلزات صنعتی و کامودیتی‌ها تأثیر می‌گذارد.",
    },
    {
        "id": "ev-093",
        "date": "2026-07-30",
        "time": "16:30",
        "title": "GDP آمریکا (Q2 تجدید نظر)",
        "country": "🇺🇸 آمریکا",
        "category": "GDP",
        "importance": 2,
        "forecast": "",
        "previous": "2.1%",
        "analysis": "تجدید نظر در GDP اولیه می‌تواند انتظارات بازار را تغییر دهد. revisions بالاتر از انتظار نشانه قوی‌تر بودن اقتصاد از برآورد اولیه است.",
    },
]


CATEGORIES = sorted({e["category"] for e in EVENTS})


# ── Subscription Endpoints ────────────────────────────────────────────────────


@router.post(
    "/subscribe",
    summary="Subscribe to event notifications",
    description="Subscribe to receive notifications for important economic events",
)
async def create_subscription(sub: SubscriptionCreate = Body(...)) -> ApiResponse[SubscriptionResponse]:
    """Create a new subscription for event notifications."""
    try:
        result = _subscribe(sub)
        return ApiResponse[SubscriptionResponse](success=True, data=result)
    except Exception as exc:
        return ApiResponse[SubscriptionResponse](success=False, error={"message": safe_error_message(exc)})


@router.get(
    "/subscriptions", summary="List subscriptions", description="Get all active event notification subscriptions"
)
async def list_subscriptions() -> ApiResponse[list[SubscriptionResponse]]:
    """List all active subscriptions."""
    subs = [SubscriptionResponse(**s) for s in _subscriptions.values() if s.get("enabled", True)]
    return ApiResponse[list[SubscriptionResponse]](success=True, data=subs)


@router.delete(
    "/subscriptions/{sub_id}", summary="Delete subscription", description="Remove an event notification subscription"
)
async def delete_subscription(sub_id: str) -> ApiResponse[dict[str, Any]]:
    """Delete a subscription by ID."""
    try:
        if sub_id not in _subscriptions:
            return ApiResponse[dict[str, Any]](success=False, error={"message": "Subscription not found"})
        del _subscriptions[sub_id]
        return ApiResponse[dict[str, Any]](success=True, data={"deleted": sub_id})
    except Exception as exc:
        return ApiResponse[dict[str, Any]](success=False, error={"message": safe_error_message(exc)})


@router.get(
    "",
    summary="Economic calendar",
    description="Upcoming economic events with importance, forecast, and previous values",
)
async def get_economic_calendar(
    start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    category: str | None = Query(None, description="Filter by category"),
    min_importance: int = Query(1, ge=1, le=3, description="Minimum importance (1=low, 2=medium, 3=high)"),
) -> ApiResponse[dict[str, Any]]:
    today = date.today()

    if start:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            start_date = today
    else:
        start_date = today

    if end:
        try:
            end_date = date.fromisoformat(end)
        except ValueError:
            end_date = today + timedelta(days=30)
    else:
        end_date = today + timedelta(days=30)

    # Filter events
    filtered = []
    for ev in EVENTS:
        try:
            ev_date = date.fromisoformat(ev["date"])
        except (ValueError, KeyError):
            continue

        if ev_date < start_date or ev_date > end_date:
            continue
        if category and ev["category"] != category:
            continue
        if ev["importance"] < min_importance:
            continue

        filtered.append(ev)

    # Sort by date then time
    def _sort_key(ev: dict[str, Any]) -> tuple:
        t = ev.get("time", "—")
        time_sort = 0 if t == "—" else 1
        return (ev["date"], time_sort, t)

    filtered.sort(key=_sort_key)

    # Group by date
    grouped: dict[str, list[dict[str, Any]]] = {}
    date_counts: dict[str, int] = {}
    for ev in filtered:
        d = ev["date"]
        if d not in grouped:
            grouped[d] = []
            date_counts[d] = 0
        grouped[d].append(ev)
        date_counts[d] += 1

    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "events": filtered,
            "grouped": grouped,
            "date_counts": date_counts,
            "total": len(filtered),
            "categories": CATEGORIES,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
        },
    )
