"""سلامت داده (Data Freshness) — آخرین زمان به‌روزرسانی منابع GoldDesk.

هر منبع یک جدول + ستون زمان دارد و یک حداکثر سن مجاز. وضعیت:
  * ``ok``      — داده تازه‌تر از آستانه
  * ``stale``   — داده هست ولی قدیمی‌تر از آستانه
  * ``empty``   — جدول وجود دارد ولی خالی است
  * ``missing`` — جدول/ستون خوانده نشد (خطای DB)

هیچ مقداری جعل نمی‌شود: خطای خواندن به‌جای «تازه»، ``missing`` می‌شود.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import tehran_to_utc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FreshnessSource:
    """یک منبع داده که تازگی‌اش پایش می‌شود."""

    key: str
    label: str
    table: str
    column: str
    max_age_minutes: int


# آستانه‌ها بر اساس فرکانس واقعی نویسندهٔ همان جدول:
#   gold_* → job های GoldDesk؛ قیمت‌ها → sync هر ۵ دقیقه؛ تاریخچه → روزانه.
FRESHNESS_SOURCES: list[FreshnessSource] = [
    FreshnessSource("gold_snapshots", "اسنپ‌شات GoldDesk", "gold_snapshots", "snapshot_at", 30),
    FreshnessSource("gold_score_history", "تاریخچهٔ امتیاز", "gold_score_history", "score_at", 30),
    FreshnessSource("gold_fund_nav", "NAV صندوق‌ها", "gold_fund_nav", "snapshot_at", 1440),
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
    FreshnessSource(
        "brsapi_gold_coin_history",
        "تاریخچهٔ روزانهٔ طلا/سکه",
        "brsapi_gold_coin_history",
        "gregorian_date",
        2880,
    ),
    FreshnessSource(
        "brsapi_gold_currency_pro_daily_history",
        "تاریخچهٔ روزانهٔ ارز",
        "brsapi_gold_currency_pro_daily_history",
        "gregorian_date",
        2880,
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


async def _probe(session: AsyncSession, src: FreshnessSource) -> dict:
    """آخرین مقدار + تعداد ردیف یک منبع (جدول/ستون ناموجود → missing)."""
    try:
        async with session.begin_nested():
            last = (await session.execute(text(f"SELECT MAX({src.column}) FROM {src.table}"))).scalar()
            count = (await session.execute(text(f"SELECT COUNT(*) FROM {src.table}"))).scalar()
    except Exception as exc:  # noqa: BLE001
        logger.warning("freshness probe failed for %s: %s", src.key, exc)
        return {
            "key": src.key,
            "label": src.label,
            "table": src.table,
            "column": src.column,
            "max_age_minutes": src.max_age_minutes,
            "last_at": None,
            "age_minutes": None,
            "rows": None,
            "status": "missing",
            "detail": str(exc)[:200],
        }
    return {
        "key": src.key,
        "label": src.label,
        "table": src.table,
        "column": src.column,
        "max_age_minutes": src.max_age_minutes,
        "last_at": last.isoformat() if hasattr(last, "isoformat") else (str(last) if last else None),
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
