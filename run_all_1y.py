# -*- coding: utf-8 -*-
"""گرفتن یک سال داده برای همهٔ نمادهایی که قبلاً دانلود شده‌اند.

منطق:
    ۱) پوشهٔ transactions_data اسکن می‌شود و هر پوشه‌ای که حداقل یک فایل
       .json دارد به‌عنوان «نماد دانلودشده» شناسایی می‌شود.
    ۲) پنجرهٔ تاریخ روی ۱۲ ماه اخیر تنظیم می‌شود (RECENT_MONTHS = 12).
    ۳) همان موتور z.py (سهمیه، کش روزهای معاملاتی، خروجی JSON + SQLite)
       بدون فیلتر fund_rank.json اجرا می‌شود تا فقط همین نمادها دانلود شوند.

استفاده:
    python run_all_1y.py                 # همهٔ نمادهای دانلودشده، ۱۲ ماه
    python run_all_1y.py --months 12     # تعیین دستی طول پنجره
    python run_all_1y.py --list          # فقط نمایش نمادهای پیدا‌شده (بدون دانلود)
    python run_all_1y.py نماد1 نماد2     # محدود کردن به چند نماد مشخص
"""
import os
import sys

import z

# کنسول ویندوز با cp1252 اجرا می‌شود و چاپ فارسی را می‌شکند؛ خروجی را UTF-8 کن
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# طول پنجره بر حسب «ماه» (۱۲ × ۳۰ روز ≈ یک سال)
DEFAULT_MONTHS = 12


def discover_downloaded_symbols():
    """پوشه‌هایی از DATA_DIR که حداقل یک فایل .json دارند."""
    root = z.DATA_DIR
    found = []
    if not os.path.isdir(root):
        return found
    for name in sorted(os.listdir(root)):
        sym_dir = os.path.join(root, name)
        if not os.path.isdir(sym_dir):
            continue
        try:
            has_json = any(
                f.endswith(".json") and os.path.isfile(os.path.join(sym_dir, f))
                for f in os.listdir(sym_dir)
            )
        except OSError:
            continue
        if has_json and z.is_valid_symbol_name(name):
            found.append(name)
    return found


def parse_args(argv):
    months = DEFAULT_MONTHS
    list_only = False
    symbols = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--list":
            list_only = True
        elif arg == "--months":
            i += 1
            try:
                months = int(argv[i])
            except (IndexError, ValueError):
                raise SystemExit("مقدار --months باید یک عدد صحیح باشد.")
        elif arg.startswith("--months="):
            try:
                months = int(arg.split("=", 1)[1])
            except ValueError:
                raise SystemExit("مقدار --months باید یک عدد صحیح باشد.")
        else:
            symbols.append(arg)
        i += 1
    return symbols, months, list_only


def main():
    explicit, months, list_only = parse_args(sys.argv[1:])

    symbols = explicit or discover_downloaded_symbols()
    if not symbols:
        raise SystemExit("هیچ نماد دانلودشده‌ای در پوشهٔ transactions_data پیدا نشد.")

    z.RECENT_MONTHS = months
    # بدون فیلتر fund_rank.json: دقیقاً همین نمادها پردازش شوند
    z.apply_top_funds = lambda syms: [s for s in symbols if s in set(syms)]

    if list_only:
        print(f"{len(symbols)} نماد دانلودشده (پنجره {months} ماه):")
        for s in symbols:
            print("  -", s)
        return

    cached_days = sum(
        1 for s in symbols
        if os.path.exists(os.path.join(z.TRADE_DAYS_DIR, f"{s}_days.json"))
    )
    z.logging.info(
        f"اجرای «یک سال برای همه»: {len(symbols)} نماد | پنجره {months} ماه | "
        f"کش روزهای معاملاتی موجود: {cached_days}/{len(symbols)} | "
        f"باقی‌مانده سهمیه: {z.RateLimiter().remaining()}"
    )
    z.SmartCollector(symbols).run()


if __name__ == "__main__":
    main()
