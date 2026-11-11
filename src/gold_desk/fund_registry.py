"""Fund Registry — ماتریس کارمزد صندوق‌های طلای قابل معامله در بورس ایران.

منبع: فیپ‌ایران (fipiran.com) + امیدنامهٔ هر صندوق (نسخهٔ ثابت).
این داده ایستا (static) است و به BrsApi وابسته نیست.

**مقادیر تقریبی و اطلاعاتی هستند.** برای عدد دقیق و به‌روز به امیدنامهٔ
صندوق یا سایت fipiran.com مراجعه کنید.

``MICROSTRUCTURE_DEFERRED = True`` نشان می‌دهد بخش «ریزساختار» (عمق دفتر
سفارشات، اسپرد لحظه‌ای) هنوز پیاده‌سازی نشده چون منبع داده زنده‌ای برای آن
تأیید نشده است (WS6 — microstructure gap).

این ماژول اطلاعاتی است (informational) و به scorer وصل نمی‌شود (C6/E-M10).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# ریزساختار (order book depth / intraday spread) به منبع داده زنده‌ای نیاز
# دارد که هنوز تأیید نشده. این ثابت وجود گپ را مستند می‌کند.
MICROSTRUCTURE_DEFERRED: bool = True


@dataclass(frozen=True)
class FundFeeInfo:
    """اطلاعات کارمزد یک صندوق طلا.

    همهٔ فیلدهای ``*_fee_pct`` درصد هستند (مثال: ``0.5`` یعنی ۰.۵٪).
    """

    symbol: str
    display_name: str
    subscription_fee_pct: float    # کارمزد صدور (٪)
    redemption_fee_pct: float      # کارمزد ابطال (٪)
    annual_mgmt_fee_pct: float     # کارمزد مدیریت سالانه (٪)
    data_source: str               # fipiran | prospectus | estimate

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── ماتریس کارمزد صندوق‌های طلا (تقریبی — منبع: fipiran.com / امیدنامه) ───

FUND_REGISTRY: dict[str, FundFeeInfo] = {
    "طلا": FundFeeInfo(
        symbol="طلا",
        display_name="صندوق سرمایه‌گذاری طلای کیان",
        subscription_fee_pct=0.001,
        redemption_fee_pct=0.001,
        annual_mgmt_fee_pct=2.5,
        data_source="fipiran",
    ),
    "عیار": FundFeeInfo(
        symbol="عیار",
        display_name="صندوق سرمایه‌گذاری عیار مفید",
        subscription_fee_pct=0.001,
        redemption_fee_pct=0.001,
        annual_mgmt_fee_pct=0.5,
        data_source="fipiran",
    ),
    "کهربا": FundFeeInfo(
        symbol="کهربا",
        display_name="صندوق سرمایه‌گذاری کهربا ملت",
        subscription_fee_pct=0.001,
        redemption_fee_pct=0.001,
        annual_mgmt_fee_pct=1.0,
        data_source="fipiran",
    ),
    "گوهر": FundFeeInfo(
        symbol="گوهر",
        display_name="صندوق سرمایه‌گذاری گوهر",
        subscription_fee_pct=0.5,
        redemption_fee_pct=0.5,
        annual_mgmt_fee_pct=1.5,
        data_source="fipiran",
    ),
    "آتیه": FundFeeInfo(
        symbol="آتیه",
        display_name="صندوق آتیه درخشان مس پاسارگاد",
        subscription_fee_pct=0.5,
        redemption_fee_pct=0.5,
        annual_mgmt_fee_pct=1.0,
        data_source="fipiran",
    ),
    "زرین": FundFeeInfo(
        symbol="زرین",
        display_name="صندوق زرین آگاه",
        subscription_fee_pct=0.5,
        redemption_fee_pct=0.5,
        annual_mgmt_fee_pct=1.5,
        data_source="fipiran",
    ),
}


def get_fund_fee(symbol: str) -> FundFeeInfo | None:
    """اطلاعات کارمزد یک صندوق؛ ``None`` اگر شناخته‌شده نباشد."""
    return FUND_REGISTRY.get(symbol)


def list_funds() -> list[FundFeeInfo]:
    """فهرست همهٔ صندوق‌های ثبت‌شده."""
    return list(FUND_REGISTRY.values())
