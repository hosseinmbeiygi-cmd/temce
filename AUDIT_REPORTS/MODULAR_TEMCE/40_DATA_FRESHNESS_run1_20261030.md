# ۴۰ — AUD-DATA-01: کهنگی داده‌های محلی — run1، ۳۰ اکتبر ۲۰۲۶

**AUD-DATA-01:** **PARTIAL + DECIDED** — داده‌ها snapshot آفلاین‌اند و به‌عنوان
«LEGACY / not live» مستند شدند؛ runtime تحت تأثیر نیست. بازتولید/تازه‌سازی داده انجام نشد
(نیازمند provider و مجاز نبودن داده‌سازی).

---

## ۱) واقعیت داده

| مسیر | وضعیت |
|---|---|
| `crypto_data/*.csv` | کندل‌ها تا **2026-08-26**؛ فایل‌ها نوشته‌شده 2026-09-16؛ `all_data_180d.csv` دارای **۳۹۳** خانهٔ خالی در ۱۸۴ ردیف؛ btc/eth هرکدام ۱۸۱ ردیف بدون null |
| `data/top50_funds_intraday/summary.csv` | یک جلسهٔ معاملاتی: `last_trade_date=1405-05-18` (شمسی)، ۵۰ نماد صندوق، بزرگ‌ترین نماد ۶۷۶٫۱۱۷ تیک |

## ۲) مصرف‌کننده‌ها (بدون runtime)

- `crypto_data/` توسط هیچ ماژول runtime خوانده نمی‌شود؛ فقط ورودی پژوهش آفلاین است.
- `data/top50_funds_intraday/` فقط توسط گزارش‌سازهای آفلاین مصرف می‌شود:
  `build_symbol_reports.py`، `new_reports/etl.py`، `new_reports/build_pages.py`،
  `new_reports/build_dashboard.py`، `scripts/analyze_top50_funds.py`.

هیچ مسیر API/سرویس در زمان اجرا این فایل‌ها را نمی‌خواند؛ دادهٔ زنده از PostgreSQL/BrsApi
می‌آید.

## ۳) اقدام

- `crypto_data/README.md` (جدید): snapshot ثابت، تاریخ پایان، هشدار «live نیست».
- `data/top50_funds_intraday/README.md` (جدید): snapshot یک‌جلسه‌ای، مصرف‌کننده‌ها،
  هشدار تازه‌سازی پیش از تولید گزارش.

هیچ فایلی حذف یا بازنویسی نشد.

## ۴) شرط بازبینی (revisit)

اگر گزارش‌سازهای آفلاین به دادهٔ جاری نیاز پیدا کنند، باید یک اسکریپت refresh با
timestamp و منبع مشخص اضافه شود؛ تا آن زمان این پوشه‌ها «LEGACY» هستند.

## ۵) وضعیت

| مورد | وضعیت |
|---|---|
| AUD-DATA-01 | **PARTIAL** (DECIDED: legacy annotation) |
| Runtime impact | **PASS** (بدون مصرف runtime) |
| تازه‌سازی داده | **BLOCKED** (provider/عدم مجاز بودن داده‌سازی) |
| commit | **BLOCKED** (درخت مشترک) |
