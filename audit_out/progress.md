# progress — وضعیت بخش‌های A تا J

آخرین به‌روزرسانی: پایان ممیزی. همهٔ بخش‌ها نوشته شدند.

| بخش | وضعیت | یادداشت |
|---|---|---|
| A | ✅ تمام | `part_A.md` — بازتولید کامل A–D؛ باگ سایز فروش، MDD=قیمت، ناسازگاری سه موتور، لغزش سقف‌خورده |
| B | ✅ تمام | `part_B.md` — random/detrend/foresight/shift + تست گارد پیشنهادی (`_proposed_tests/`) |
| C | ✅ تمام | `part_C.md` — ۱۰ یافته؛ دو باگ HIDDEN_ERRORS رفع‌شده |
| D | ✅ تمام | `part_D.md` — اعداد کهنه؛ #1 Fail-open؛ #11 ناسازگار؛ #5 نرخ ۰.۰۰۳ |
| E | ✅ تمام | `part_E.md` — سه‌گروه‌بندی؛ بازاجرای زنده (Postgres+Redis) |
| F | ✅ تمام | `part_F.md` — ۳۵۹ مدل؛ مسیر آرتیفکت غلط؛ آزمایش Ridge؛ label shuffle + canary |
| G | ✅ تمام | `part_G.md` — `gregorian_date` = زمان سینک؛ ADV؛ bitemporal نیست |
| H | ✅ تمام | `part_H.md` — بدون کلید ثابت در کد؛ `.env` خارج از گیت؛ ToS نامشخص |
| I | ✅ تمام | `part_I.md` — هم‌پوشانی‌ها؛ PR/issue بررسی نشد |
| J | ✅ تمام | `part_J.md` — حکم غیرقابل‌اتکا؛ ۱۵ اصلاح اولویت‌دار؛ فهرست «انجام نشد» |

## خروجی‌ها
- `audit_out/part_A.md` … `part_J.md`
- `audit_out/MISSING_ITEMS_REPORT.md` (ادغام A–J)
- `audit_out/findings_new.csv` (۵۰ یافته)
- شواهد خام: `equity_A..D.csv`, `fills_B.csv`, `_tmp/*.json`, `_logs/partB.log`, `_proposed_tests/`

## بندهای «انجام‌نشده» (تفصیل در `part_J.md` §J4)
C6 فهرست اسمی نمادهای حذف‌شده؛ C5 knowledge_time بنیادی؛ C8 فیت کامل رژیم/ensemble/calibrator؛ E بازاجرای کل suite؛ F1 تاریخچهٔ کامل git؛ H1 اسکن رمز در تاریخچه؛ I2 ۱۵ PR باز؛ A5 اجرای واقعی SignalBacktestEngine؛ G3 نمونهٔ همهٔ جدول‌ها.

## محدودیت‌ها
- DB زنده فقط SELECT شد (هیچ نوشتنی).
- مقادیر رمز/توکن هرگز چاپ نشد (فقط نام/مسیر).
- timeout در `grep -r` روی کل مخزن ⇒ بخشی از «استفاده می‌شود؟» در بخش I با برچسب [حدس از نام].
