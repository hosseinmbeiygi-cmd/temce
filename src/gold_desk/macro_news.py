"""Macro & News AI — داده‌های کلان اقتصادی + تحلیل تأثیر بر بازار طلا.

منابع:
- CBI (بانک مرکزی): نرخ بهره، M2، ارز
- MarkazAmar (مرکز آمار): CPI، تورم
- World Gold Council: گزارش‌های ماهانه تقاضا

هر event شامل:
- impact_score: -3 (بسیار منفی) تا +3 (بسیار مثبت) بر طلا
- confidence: 0-1
- explanation

**این ماژول اطلاعاتی است (informational) و به امتیاز ۰-۱۰۰ وصل نمی‌شود.** طبق
قرارداد C6، هیچ مسیر محاسبهٔ score از خروجی کلان استفاده نمی‌کند؛
``compute_macro_multiplier`` فقط برای نمایش/مقایسه است و در ``scorer`` وارد
نمی‌شود (E-M10). امتیاز تصمیم‌گیری فقط از ``scorer.compute_score`` می‌آید.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta

import httpx
import jdatetime

from core.time import utc_now_naive

logger = logging.getLogger(__name__)

REDIS_KEY_MACRO = "golddesk:macro:events"
REDIS_KEY_MACRO_CACHE_DAYS = 7  # cache events for 7 days

# ── آستانه‌های heuristic (نام‌دار، با واحد) ─────────────────────────
# تفسیر عدد با علامت نقش اصلی دارد؛ کلمه‌های «افزایش/کاهش» نقش پشتیبان.
MACRO_CONFIDENCE_BASE: float = 0.5  # اطمینان پایه وقتی یک جهت تشخیص داده شود
MACRO_CONFIDENCE_PER_CUE: float = 0.1  # هر شاهد اضافه (عدد یا کلمهٔ کلیدی)
MACRO_CONFIDENCE_MAX: float = 0.9  # سقف اطمینان heuristic
import logging

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
        d["dedupe_key"] = self.dedupe_key()
        return d

    def dedupe_key(self) -> str:
        """کلید یکتای پایدار برای جلوگیری از ثبت چندبارهٔ یک خبر (E-M11).

        بر پایهٔ منبع + عنوانِ نرمال‌شده است تا اسکرپ مجدد همان تیتر، رویداد تازه
        نسازد.
        """
        normalized = re.sub(r"\s+", " ", self.title.strip().lower())
        digest = hashlib.sha1(f"{self.source}:{normalized}".encode()).hexdigest()[:16]
        return f"golddesk:macro:{digest}"


def _dedupe(events: list[MacroEvent]) -> list[MacroEvent]:
    """حذف رویدادهای تکراری با حفظ ترتیب ورود."""
    seen: set[str] = set()
    out: list[MacroEvent] = []
    for event in events:
        key = event.dedupe_key()
        if key in seen:
            continue
        seen.add(key)
        out.append(event)
    return out


# الگوی عدد علامت‌دار (فارسی/عربی/لاتین) — ورودی تشخیص جهت.
_SIGNED_NUMBER_RE = re.compile(
    r"(?P<pre_sign>[+\-−＋])\s*(?P<pre_num>[\d۰-۹])"
    r"|(?P<post_num>[\d۰-۹])\s*(?P<post_sign>[+\-−＋])"
)

# تاریخ‌های قابل تشخیص در متن خبر: ``1405/05/12`` یا ``2026-08-03``.
_NEWS_DATE_RE = re.compile(r"(?P<y>\d{4})[/\-](?P<m>\d{1,2})[/\-](?P<d>\d{1,2})")


def _extract_published_at(text: str, fallback: datetime) -> datetime:
    """تاریخ انتشار واقعی خبر از متن؛ در نبودِ تاریخ، ``fallback`` (زمان واکشی).

    تاریخ‌های با سال ۱۳۰۰–۱۵۰۰ شمسی تلقی و به میلادی تبدیل می‌شوند، بقیه میلادی.
    پیش‌تر همهٔ اخبار «همین حالا» ثبت می‌شدند و decay بی‌معنا بود (E-M11).
    """
    match = _NEWS_DATE_RE.search(text)
    if not match:
        return fallback
    year, month, day = int(match.group("y")), int(match.group("m")), int(match.group("d"))
    try:
        if 1300 <= year <= 1500:
            return datetime.combine(jdatetime.date(year, month, day).togregorian(), time.min)
        return datetime(year, month, day)
    except ValueError:
        logger.warning("unparsable news date in %r", text[:80])
        return fallback


# ── Heuristic impact estimation ────────────────────────────


def _numeric_direction(title: str) -> int:
    """جهت تغییر از **عددِ علامت‌دار** عنوان: +1، -1 یا 0.

    پیش‌تر وجود هر ``+`` یا ``-`` در عنوان (حتی خط تیرهٔ «گزارش-تیر») یک جهت
    جعلی می‌ساخت. حالا فقط عدد با علامت (یا درصد) شمرده می‌شود (E-M9).
    """
    match = _SIGNED_NUMBER_RE.search(title)
    if not match:
        return 0
    # علامت ممکن است پیش از عدد («+۲») یا پس از آن («۲+») بیاید.
    sign = match.group("pre_sign") or match.group("post_sign")
    return 1 if sign in {"+", "＋"} else -1


def _judge(
    title: str,
    up_words: tuple[str, ...],
    down_words: tuple[str, ...],
    up_score: int,
    down_score: int,
) -> tuple[int, float]:
    """امتیاز جهت‌دار + اطمینان بر اساس تعداد شواهد (عدد علامت‌دار، کلمهٔ کلیدی)."""
    text = title.lower()
    numeric = _numeric_direction(title)
    word_up = any(w in text for w in up_words)
    word_down = any(w in text for w in down_words)

    cues = (1 if numeric else 0) + (1 if (word_up or word_down) else 0)
    direction = numeric or (1 if word_up else (-1 if word_down else 0))
    if direction == 0:
        return 0, 0.0
    if word_up and word_down:
        # نشانه‌های متناقض ⇒ اطمینان پایین‌تر، ولی جهت عددی/اولی معتبر است
        cues = max(1, cues - 1)
    score = up_score if direction > 0 else down_score
    confidence = min(MACRO_CONFIDENCE_MAX, MACRO_CONFIDENCE_BASE + MACRO_CONFIDENCE_PER_CUE * cues)
    return score, confidence


_RATE_UP = ("افزایش", "بالا", "rise", "increase")
_RATE_DOWN = ("کاهش", "پایین", "cut", "decrease")
_INFLATION_UP = ("افزایش", "بالا", "سالانه", "نقطه")
_INFLATION_DOWN = ("کاهش", "پایین")
_FX_UP = ("تقویت", "افزایش", "صعود")  # تقویت دلار
_FX_DOWN = ("ضعیف", "کاهش", "سقوط")
_DEMAND_UP = ("افزایش", "بالا", "خرید")
_DEMAND_DOWN = ("کاهش", "فروش")


def _score_rate_event(title: str) -> int:
    """نرخ بهره: افزایش = منفی برای طلا، کاهش = مثبت."""
    return _judge(title, _RATE_UP, _RATE_DOWN, -2, +2)[0]


def _score_inflation_event(title: str) -> int:
    """تورم بالا = مثبت برای طلا (hedge)."""
    return _judge(title, _INFLATION_UP, _INFLATION_DOWN, +2, -1)[0]


def _score_fx_event(title: str) -> int:
    """دلار قوی = منفی، دلار ضعیف = مثبت."""
    return _judge(title, _FX_UP, _FX_DOWN, -2, +2)[0]


def _score_demand_event(title: str) -> int:
    """تقاضای بالا = مثبت."""
    return _judge(title, _DEMAND_UP, _DEMAND_DOWN, +2, -1)[0]


_CATEGORY_RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...], int, int]] = {
    "rate": (_RATE_UP, _RATE_DOWN, -2, +2),
    "inflation": (_INFLATION_UP, _INFLATION_DOWN, +2, -1),
    "fx": (_FX_UP, _FX_DOWN, -2, +2),
    "demand": (_DEMAND_UP, _DEMAND_DOWN, +2, -1),
}


def estimate_impact(title: str, category: str) -> tuple[int, float]:
    """تخمین impact و confidence از عنوان رویداد.

    confidence دیگر ثابت ۰.۶ نیست: پایه + یک پله به‌ازای هر شاهد (عدد علامت‌دار،
    کلمهٔ کلیدی) با سقف نام‌دار (E-M9). نبودِ نشانه ⇒ (0, 0.0)، نه ادعای خنثی.
    """
    rule = _CATEGORY_RULES.get(category)
    if rule is None:
        return 0, 0.0
    return _judge(title, *rule)


# ── نمونه events (manual seed) ────────────────────────────


def get_sample_events() -> list[MacroEvent]:
    """دادهٔ نمایشی (demo) — هرگز خروجی واقعی نه.

    این رویدادها دست‌نویس‌اند: نرخ تورم، نقدینگی M2 و خرید بانک‌های مرکزی با منبع
    «markaz_amar»/«cbi»/«wgc» و تاریخِ محاسبه‌شده از «الان». به‌همین دلیل از مسیر
    ``fetch_macro_events`` صدا زده نمی‌شود؛ مصرف‌کنندهٔ تست و دمو باید خودش بداند که این‌ها
    عدد واقعی نیستند. راهاست که نبودِ داده اعلام شود، نه پر کردنش با یک روایت باورپذیر.
    """
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
    """ضریب **اطلاعاتی** تأثیر کلان (فقط نمایش/مقایسه، نه ورودی امتیاز).

    مطابق C6 و E-M10، این عدد به ``scorer.compute_score`` وصل نمی‌شود؛ نام قبلی
    «برای اصلاح score نهایی» ادعای نادرستی بود. خروجی در بازهٔ -1 تا +1 است.
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

    # No cache: an empty list, not the demo seed. The scraper below is what fills this;
    # until it runs, the product has to say «داده‌ای نیست» instead of inventing a CPI print.
    logger.info("macro events cache empty — reporting no data instead of the demo seed")
    return []


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
                fetched_at = utc_now_naive()
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
                                # تاریخ خبر اگر در متن باشد؛ وگرنه زمان واکشی (E-M11).
                                published_at=_extract_published_at(clean, fetched_at),
                            )
                        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("CBI scrape failed: %s", exc, exc_info=True)
    # تیترهای تکراری یک صفحه نباید چند رویداد بسازند (E-M11).
    return _dedupe(events)
