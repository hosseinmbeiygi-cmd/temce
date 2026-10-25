"""دانلود فوری چند نماد مشخص (کل تاریخ موجود) با استفاده از موتور z.py

استفاده:
    python run_symbols.py              # لیست پیش‌فرض DEFAULT_SYMBOLS
    python run_symbols.py نماد1 نماد2  # لیست دلخواه از خط فرمان

این اسکریپت همان سهمیه روزانه، همان کش روزهای معاملاتی و همان خروجی‌های z.py
را به کار می‌گیرد؛ فقط لیست نمادها و پنجره تاریخ را محدود/باز می‌کند.
"""
import sys

import z

DEFAULT_SYMBOLS = ["متال", "استیل", "آذرین"]

# پنجره تاریخ برای این اجرا: عدد بزرگ = کل تاریخ موجود هر نماد
FULL_HISTORY_MONTHS = 60


def main():
    symbols = sys.argv[1:] or DEFAULT_SYMBOLS
    z.RECENT_MONTHS = FULL_HISTORY_MONTHS
    # بدون فیلتر fund_rank.json: دقیقاً همین نمادهای درخواستی دانلود شوند
    z.apply_top_funds = lambda syms: [s for s in symbols if s in set(syms)]
    z.logging.info(f"اجرای هدفمند: {len(symbols)} نماد | پنجره {z.RECENT_MONTHS} ماه | باقی‌مانده سهمیه: {z.RateLimiter().remaining()}")
    collector = z.SmartCollector(symbols)
    collector.run()


if __name__ == "__main__":
    main()
