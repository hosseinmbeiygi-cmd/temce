"""سلامت داده (Data Freshness) — آخرین زمان به‌روزرسانی منابع GoldDesk.

هر منبع یک جدول + ستون زمان دارد و یک حداکثر سن مجاز. وضعیت:
  * ``ok``      — داده تازه‌تر از آستانه
  * ``stale``   — داده هست ولی قدیمی‌تر از آستانه
  * ``empty``   — جدول وجود دارد ولی خالی است
  * ``missing`` — جدول/ستون خوانده نشد (خطای DB) یا تاریخ آن قابل تبدیل نبود

هیچ مقداری جعل نمی‌شود: خطای خواندن به‌جای «تازه»، ``missing`` می‌شود.

**تاریخچه‌ها با تاریخ معامله سنجیده می‌شوند، نه تاریخ درج**
----------------------------------------------------------
جدول‌های تاریخچهٔ طلا/سکه/ارز و NAV یک ستون شمسی ``date`` دارند (تاریخ واقعی
بازار) و — در دیتابیس عملیاتی — ستون‌های ``gregorian_date``/``shamsi_date`` که
همان روز اجرای ingestion را نگه می‌دارند (ISSUE-127). سنجش تازگی با
``gregorian_date`` باعث می‌شد یک بک‌فیل امروزی، تاریخچهٔ ۴۲ روز کهنه را «تازه»
نشان دهد و حتی health check را سبز کند. به همین دلیل این منابع
``calendar="jalali"`` دارند و تازگی از ``MAX(date)`` (تبدیل‌شده به میلادی)
محاسبه می‌شود.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.quality import SQL_JALALI_NORMALIZE, jalali_to_gregorian
from core.time import tehran_to_utc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FreshnessSource:
    """یک منبع داده که تازگی‌اش پایش می‌شود.

    ``calendar``:
      * ``"gregorian"`` — ستون یک timestamp/date میلادی است (پیش‌فرض).
      * ``"jalali"``    — ستون یک رشتهٔ تاریخ شمسی ``YYYY-MM-DD``/``YYYY/MM/DD``
        است و باید تبدیل شود؛ ``fetched_at``/``gregorian_date`` این جدول‌ها
        تاریخ درج‌اند و برای تازگی معیار نیستند.
    """

    key: str
    label: str
    table: str
    column: str
    max_age_minutes: int
    calendar: str = "gregorian"
    # توضیح ثابت برای داشبورد: چه چیزی دقیقاً سنجیده می‌شود و چه چیزی نه.
    note: str | None = None


# آستانه‌ها بر اساس فرکانس واقعی نویسندهٔ همان جدول:
#   gold_* → job های GoldDesk؛ قیمت‌ها → sync هر ۵ دقیقه؛ تاریخچه → روزانه.
FRESHNESS_SOURCES: list[FreshnessSource] = [
    FreshnessSource("gold_snapshots", "اسنپ‌شات GoldDesk", "gold_snapshots", "snapshot_at", 30),
    FreshnessSource("gold_score_history", "تاریخچهٔ امتیاز", "gold_score_history", "score_at", 30),
    # `gold_fund_nav.snapshot_at` فقط می‌گوید job امروز اجرا شده؛ مقدار
    # `nav_per_unit` می‌تواند از یک رکورد NAV قدیمی آمده باشد. سن خودِ NAV منبع
    # جداگانه با منبع `brsapi_nav_records` سنجیده می‌شود، پس اینجا صریح گفته می‌شود.
    FreshnessSource(
        "gold_fund_nav",
        "اسنپ‌شات NAV صندوق‌ها (زمان اجرای job)",
        "gold_fund_nav",
        "snapshot_at",
        1440,
        note="زمان نوشتن snapshot؛ سن NAV منبع از منبع brsapi_nav_records خوانده می‌شود",
    ),
    FreshnessSource("gold_portfolio_values", "تاریخچهٔ ارزش پرتفوی", "gold_portfolio_values", "snapshot_at", 1440),
    FreshnessSource("gold_alert_rules", "قوانین هشدار", "gold_alert_rules", "created_at", 525600),
    FreshnessSource("gold_alert_events", "رویدادهای هشدار", "gold_alert_events", "sent_at", 1440),
    FreshnessSource("gold_holdings", "دارایی‌های ثبت‌شده", "gold_holdings", "bought_at", 525600),
    FreshnessSource("gold_trades", "معاملات ثبت‌شده", "gold_trades", "traded_at", 525600),
    FreshnessSource("brsapi_gold_coin_prices", "قیمت طلا/سکه (زنده)", "brsapi_gold_coin_prices", "fetched_at", 120),
    FreshnessSource(
        "brsapi_gold_currency_pro_prices",
        "قیمت ارز/اونس (زنده)",
        "brsapi_gold_currency_pro_prices",
        "fetched_at",
        120,
    ),
    FreshnessSource(
        "brsapi_index_values", "شاخص بورس", "brsapi_index_values", "fetched_at", 120
    ),
    # تاریخچه‌ها: تاریخ **معامله** (شمسی) معیار است. `gregorian_date` این
    # جدول‌ها تاریخ ingestion است و تازگی را جعلی «ok» نشان می‌داد (ISSUE-127).
    FreshnessSource(
        "brsapi_gold_coin_history",
        "تاریخچهٔ روزانهٔ طلا/سکه (تاریخ معامله)",
        "brsapi_gold_coin_history",
        "date",
        2880,
        calendar="jalali",
    ),
    FreshnessSource(
        "brsapi_gold_currency_pro_daily_history",
        "تاریخچهٔ روزانهٔ ارز (تاریخ معامله)",
        "brsapi_gold_currency_pro_daily_history",
        "date",
        2880,
        calendar="jalali",
    ),
    # NAV صندوق‌ها هم تاریخ شمسی انتشار دارد؛ قبلاً هیچ منبعی تازگی آن را
    # نمی‌سنجید و «NAV سه هفته کهنه» در داشبورد دیده نمی‌شد.
    FreshnessSource(
        "brsapi_nav_records",
        "NAV صندوق‌ها (تاریخ انتشار)",
        "brsapi_nav_records",
        "date",
        2880,
        calendar="jalali",
    ),
]


def _as_utc(value: object) -> datetime | None:
    """تبدیل مقدار ستون زمان به UTC.

    ستون‌های naive در این دیتابیس زمان محلی تهران را نگه می‌دارند (اختلاف ۳:۳۰
    با UTC)؛ فرض UTC سن را منفی می‌کرد. ستون‌های تاریخ‌ـی (date) نیز نیمه‌شب تهران
    فرض می‌شوند.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else tehran_to_utc(value)
    if isinstance(value, date):
        return tehran_to_utc(datetime(value.year, value.month, value.day))
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else tehran_to_utc(parsed)
    return None


def _age_minutes(last_at: object, now: datetime) -> float | None:
    instant = _as_utc(last_at)
    if instant is None:
        return None
    return (now - instant).total_seconds() / 60.0


def _last_value_sql(src: FreshnessSource) -> str:
    """کوئری خواندن آخرین مقدار ستون زمان (برای تاریخ شمسی، نرمال‌شده)."""
    if src.calendar == "jalali":
        # MAX روی رشتهٔ نرمال‌شده تا ردیف‌های `1405/05/01` و `1405-06-23` با هم
        # مقایسه شوند و ارقام فارسی هم به ASCII تبدیل شوند.
        return f"SELECT MAX({SQL_JALALI_NORMALIZE.format(column=src.column)}) FROM {src.table}"
    return f"SELECT MAX({src.column}) FROM {src.table}"


def _last_at(src: FreshnessSource, last: object) -> tuple[str | None, str | None]:
    """مقدار خام ستون → (ISO میلادی, دلیل خطا).

    تاریخ شمسی قابل تبدیل نباشد، ``None`` با دلیل برمی‌گردد تا وضعیت ``missing``
    شود؛ حدس زدن «امروز» دقیقاً همان خطایی است که این تابع باید جلوی آن را بگیرد.
    """
    if last is None:
        return None, None
    if src.calendar == "jalali":
        gregorian = jalali_to_gregorian(last)
        if gregorian is None:
            return None, f"unparsable Jalali {src.column}={last!r}"
        return gregorian.isoformat(), None
    return (last.isoformat() if hasattr(last, "isoformat") else str(last)), None


async def _probe(session: AsyncSession, src: FreshnessSource) -> dict:
    """آخرین مقدار + تعداد ردیف یک منبع (جدول/ستون ناموجود → missing)."""
    try:
        async with session.begin_nested():
            last = (await session.execute(text(_last_value_sql(src)))).scalar()
            count = (await session.execute(text(f"SELECT COUNT(*) FROM {src.table}"))).scalar()
    except Exception as exc:  # noqa: BLE001
        logger.warning("freshness probe failed for %s: %s", src.key, exc)
        return {
            "key": src.key,
            "label": src.label,
            "table": src.table,
            "column": src.column,
            "calendar": src.calendar,
            "note": src.note,
            "max_age_minutes": src.max_age_minutes,
            "last_at": None,
            "age_minutes": None,
            "rows": None,
            "status": "missing",
            "detail": str(exc)[:200],
        }

    last_at, parse_error = _last_at(src, last)
    if parse_error is not None:
        logger.warning("freshness probe for %s: %s", src.key, parse_error)
        return {
            "key": src.key,
            "label": src.label,
            "table": src.table,
            "column": src.column,
            "calendar": src.calendar,
            "note": src.note,
            "max_age_minutes": src.max_age_minutes,
            "last_at": None,
            "age_minutes": None,
            "rows": int(count or 0),
            "status": "missing",
            "detail": parse_error,
        }

    return {
        "key": src.key,
        "label": src.label,
        "table": src.table,
        "column": src.column,
        "calendar": src.calendar,
        "note": src.note,
        "max_age_minutes": src.max_age_minutes,
        "last_at": last_at,
        "age_minutes": None,  # در build پر می‌شود
        "rows": int(count or 0),
        "status": "empty",
        "detail": None,
    }


async def build_freshness_report(
    session: AsyncSession, *, sources: list[FreshnessSource] | None = None
) -> dict:
    """وضعیت تازگی همهٔ منابع + خلاصهٔ کلی ``ok``/``stale``/``empty``/``missing``."""
    now = datetime.now(UTC)
    items: list[dict] = []
    for src in sources if sources is not None else FRESHNESS_SOURCES:
        row = await _probe(session, src)
        if row["status"] == "missing":
            items.append(row)
            continue
        age = _age_minutes(row["last_at"], now)
        row["age_minutes"] = round(age, 1) if age is not None else None
        if row["rows"] == 0 or age is None:
            row["status"] = "empty"
        elif age <= src.max_age_minutes:
            row["status"] = "ok"
        else:
            row["status"] = "stale"
        items.append(row)

    statuses = {i["status"] for i in items}
    if "missing" in statuses:
        overall = "missing"
    elif "empty" in statuses:
        overall = "empty"
    elif "stale" in statuses:
        overall = "stale"
    else:
        overall = "ok"

    return {
        "generated_at": now.isoformat(),
        "overall": overall,
        "counts": {
            "ok": sum(1 for i in items if i["status"] == "ok"),
            "stale": sum(1 for i in items if i["status"] == "stale"),
            "empty": sum(1 for i in items if i["status"] == "empty"),
            "missing": sum(1 for i in items if i["status"] == "missing"),
        },
        "sources": items,
    }


__all__ = ["FRESHNESS_SOURCES", "FreshnessSource", "build_freshness_report"]
