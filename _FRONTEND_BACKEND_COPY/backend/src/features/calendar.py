from __future__ import annotations

import datetime as dt

# تقویم بازار ایران — بدون وابستگی سنگین (jdatetime اختیاری)
IRAN_HOLIDAYS_MD = {(1, 1), (1, 2), (1, 3), (1, 4), (3, 14), (3, 15)}  # نمونه نوروز


def calendar_features(ts_utc: dt.datetime) -> dict:
    # Asia/Tehran = UTC+3:30
    tehran = ts_utc + dt.timedelta(hours=3, minutes=30)
    wd = tehran.weekday()  # 0=Mon
    return {
        "weekday": wd,
        "is_weekend_ir": wd in (3, 4),  # پنج‌شنبه/جمعه
        "month": tehran.month,
        "is_holiday": (tehran.month, tehran.day) in IRAN_HOLIDAYS_MD,
        "days_to_month_end": (
            dt.date(tehran.year, tehran.month + 1, 1) - dt.date(tehran.year, tehran.month, tehran.day)
        ).days
        if tehran.month < 12
        else (dt.date(tehran.year + 1, 1, 1) - dt.date(tehran.year, tehran.month, tehran.day)).days,
    }


def to_jalali_str(g_date: str | dt.date | dt.datetime) -> str:
    """تبدیل تاریخ میلادی/شمسی به رشته شمسی استاندارد YYYY-MM-DD با ارقام فارسی اختیاری."""
    try:
        import jdatetime

        if isinstance(g_date, str):
            # اگر ورودی قبلا شمسی با / یا - است، فقط نرمال کن
            if "/" in g_date:
                g_date = g_date.replace("/", "-")
            # سعی کن به عنوان شمسی parse کنی (اگر سال > 1300 یعنی شمسی)
            parts = g_date.split("-")
            if len(parts) >= 3 and int(parts[0]) > 1300:
                return g_date  # قبلا شمسی
            # در غیر این صورت میلادی فرض کن
            dt_obj = dt.date.fromisoformat(g_date.split("T")[0])
            j = jdatetime.date.fromgregorian(date=dt_obj)
            return j.strftime("%Y-%m-%d")
        if isinstance(g_date, dt.datetime):
            j = jdatetime.date.fromgregorian(date=g_date.date())
            return j.strftime("%Y-%m-%d")
        if isinstance(g_date, dt.date):
            j = jdatetime.date.fromgregorian(date=g_date)
            return j.strftime("%Y-%m-%d")
    except Exception:
        pass
    return str(g_date)


def to_jalali_persian_digits(jalali_str: str) -> str:
    """تبدیل ارقام انگلیسی تاریخ شمسی به فارسی."""
    trans = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return jalali_str.translate(trans)
