"""Hard Stops — شرایط بحرانی که امتیاز را نادیده می‌گیرند و RED مطلق می‌دهند.

Hard stop = رویداد بازار که فارغ از تحلیل تکنیکال، خرید ممنوع.

نمونه‌ها:
- سقوط شاخص کل بورس > 5% روزانه (فروش گسترده در همه بازارها)
- جهش دلار جهانی DXY > 3% (شوک ارزی)
- جهش دلار تهران > 5% روزانه (تقاضای سفته‌بازانه)
- (در آینده: جنگ/تحریم از news API)
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import HARDSTOP_DXY_SPIKE_PCT, HARDSTOP_TSE_CRASH_PCT, HARDSTOP_USD_SPIKE_PCT


@dataclass(frozen=True)
class HardStopResult:
    active: bool
    reason: str | None


def check_hard_stops(
    tse_daily_change_pct: float | None = None,
    dxy_daily_change_pct: float | None = None,
    usd_irt_daily_change_pct: float | None = None,
) -> HardStopResult:
    """بررسی hard stopها.

    هر کدام None = داده موجود نیست → نادیده بگیر (نه فعال).
    """
    if tse_daily_change_pct is not None and tse_daily_change_pct <= HARDSTOP_TSE_CRASH_PCT:
        return HardStopResult(
            active=True,
            reason=f"سقوط شاخص کل {tse_daily_change_pct:.1f}٪ (آستانه {HARDSTOP_TSE_CRASH_PCT}٪) — فروش گسترده",
        )
    if dxy_daily_change_pct is not None and dxy_daily_change_pct >= HARDSTOP_DXY_SPIKE_PCT:
        return HardStopResult(
            active=True,
            reason=f"جهش DXY {dxy_daily_change_pct:.1f}٪ — شوک ارزی جهانی",
        )
    if usd_irt_daily_change_pct is not None and usd_irt_daily_change_pct >= HARDSTOP_USD_SPIKE_PCT:
        return HardStopResult(
            active=True,
            reason=f"جهش دلار تهران {usd_irt_daily_change_pct:.1f}٪ — تقاضای سفته‌بازانه",
        )
    return HardStopResult(active=False, reason=None)
