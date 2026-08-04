"""
apps/api/app.py
ماژول API اپلیکیشن – شامل منطق بررسی cron alerts.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

# =============================================================================
# تنظیمات و ثابت‌ها
# =============================================================================
COOLDOWN_SECONDS = 3600  # ۱ ساعت – مدت زمان خنک‌سازی برای جلوگیری از هشدارهای تکراری

# =============================================================================
# وضعیت‌های داخلی (State)
# =============================================================================
_alert_state: dict[str, float] = {
    "consecutive_failures": 0.0,      # زمان آخرین هشدار شکست متوالی
    "accuracy_drop": 0.0,             # زمان آخرین هشدار کاهش دقت
    "was_in_failure_streak": 0.0,     # زمان شروع آخرین دورهٔ شکست (برای تشخیص بازیابی)
    "was_accuracy_below_50": 0.0,     # زمان شروع آخرین دورهٔ دقت پایین (برای تشخیص بازیابی)
}

_cron_state: dict[str, deque[dict[str, Any]]] = {
    "history": deque(maxlen=100)      # تاریخچهٔ آخرین اجراها (حداکثر ۱۰۰ مورد)
}

# =============================================================================
# ارسال هشدار (قابل جای‌گزینی با سرویس واقعی)
# =============================================================================
async def _send_cron_alert(title: str, message: str, icon: str = "") -> None:
    """
    ارسال هشدار به کانال موردنظر (در اینجا فقط چاپ می‌شود).
    در محیط واقعی می‌توان به تلگرام، ایمیل، یا Slack متصل کرد.
    """
    print(f"{icon} {title}\n{message}\n{'-' * 40}")

# =============================================================================
# بازنشانی وضعیت هشدارها (مورد استفاده در تست‌ها)
# =============================================================================
def _reset_alert_state() -> None:
    """بازنشانی تمام وضعیت‌های هشدار به مقادیر اولیه (برای تست‌ها)."""
    _alert_state.update(
        {
            "consecutive_failures": 0.0,
            "accuracy_drop": 0.0,
            "was_in_failure_streak": 0.0,
            "was_accuracy_below_50": 0.0,
        }
    )

# =============================================================================
# تابع اصلی بررسی هشدارها
# =============================================================================
async def _check_cron_alerts() -> None:
    """
    بررسی آخرین سه ورودی تاریخچه و در صورت لزوم ارسال هشدارهای مناسب.
    سناریوهای پوشش‌داده‌شده:
      ۱) سه شکست متوالی → هشدار قرمز
      ۲) بازیابی پس از شکست‌های متوالی → هشدار سبز بازیابی
      ۳) دقت کمتر از ۵۰٪ → هشدار قرمز کاهش دقت
      ۴) بازگشت دقت به بالای ۵۰٪ → هشدار سبز بازیابی دقت
      ۵) خنک‌سازی (cooldown) برای جلوگیری از هشدارهای تکراری
    """
    history = _cron_state["history"]
    if len(history) < 3:
        return  # دادهٔ کافی برای تحلیل وجود ندارد

    # سه ورودی آخر
    last_three = list(history)[-3:]
    latest = last_three[-1]

    # ------------------------------------------------------------------------
    # ۱) تشخیص شکست متوالی
    # ------------------------------------------------------------------------
    all_failed = all(not entry.get("success", False) for entry in last_three)
    now = time.time()

    if all_failed:
        # اگر دورهٔ شکست قبلاً ثبت شده و خنک‌سازی تمام نشده، هشدار تکرار نمی‌شود
        if _alert_state["consecutive_failures"] == 0.0 or \
           (now - _alert_state["consecutive_failures"] > COOLDOWN_SECONDS):
            # ارسال هشدار بحرانی
            error_messages = "\n".join(
                f"  - اجرای {e.get('run', '?')}: {e.get('error', 'خطای ناشناخته')}"
                for e in last_three
            )
            await _send_cron_alert(
                title="⚠️ ۳ شکست متوالی در Cron",
                message=f"سه اجرای اخیر همگی با شکست مواجه شده‌اند:\n{error_messages}",
                icon="🔴"
            )
            # به‌روزرسانی زمان‌ها
            _alert_state["consecutive_failures"] = now
            _alert_state["was_in_failure_streak"] = now
    else:
        # --------------------------------------------------------------------
        # ۲) بازیابی از شکست متوالی
        # --------------------------------------------------------------------
        # اگر قبلاً در وضعیت شکست بودیم و آخرین اجرا موفق است → بازیابی
        if _alert_state["was_in_failure_streak"] > 0.0 and latest.get("success", False):
            await _send_cron_alert(
                title="✅ بازیابی از شکست متوالی",
                message=f"اجرای شمارهٔ {latest.get('run', '?')} با موفقیت انجام شد.",
                icon="🟢"
            )
            # بازنشانی پرچم‌ها
            _alert_state["was_in_failure_streak"] = 0.0
            _alert_state["consecutive_failures"] = 0.0

    # ------------------------------------------------------------------------
    # ۳) تشخیص کاهش دقت (زیر ۵۰٪)
    # ------------------------------------------------------------------------
    any_low_accuracy = any(
        entry.get("accuracy", 100.0) < 50.0 for entry in last_three
    )

    if any_low_accuracy:
        if _alert_state["accuracy_drop"] == 0.0 or \
           (now - _alert_state["accuracy_drop"] > COOLDOWN_SECONDS):
            # پیدا کردن کمترین دقت برای گزارش
            min_acc = min(entry.get("accuracy", 100.0) for entry in last_three)
            await _send_cron_alert(
                title="⚠️ کاهش شدید دقت (زیر ۵۰٪)",
                message=f"دقت در یکی از اجراهای اخیر به {min_acc:.1f}٪ رسیده است.",
                icon="🔴"
            )
            _alert_state["accuracy_drop"] = now
            _alert_state["was_accuracy_below_50"] = now
    else:
        # --------------------------------------------------------------------
        # ۴) بازیابی دقت
        # --------------------------------------------------------------------
        if _alert_state["was_accuracy_below_50"] > 0.0 and \
           latest.get("accuracy", 100.0) >= 50.0:
            await _send_cron_alert(
                title="✅ بازگشت دقت به محدودهٔ قابل‌قبول",
                message=f"دقت اجرای شمارهٔ {latest.get('run', '?')} به {latest.get('accuracy', 0):.1f}٪ بازگشت.",
                icon="🟢"
            )
            _alert_state["was_accuracy_below_50"] = 0.0
            _alert_state["accuracy_drop"] = 0.0

    # در صورت سالم بودن همه‌چیز، هیچ هشداری ارسال نمی‌شود.
