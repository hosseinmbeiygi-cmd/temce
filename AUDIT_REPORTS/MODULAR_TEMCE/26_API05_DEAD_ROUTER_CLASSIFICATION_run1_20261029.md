# ۲۶ — API-05 (ادامه): طبقه‌بندی routerهای mount‌نشده — کد مردهٔ خودبسنده در برابر قابلیت یکتا

**تاریخ:** 2026-10-29
**دامنه:** ۷ router mount‌نشده + کد پشتیبان آن‌ها + معادل‌های mount‌شده
**وضعیت:** DONE (تحلیل + طبقه‌بندی؛ تصمیم mount/حذف محصولی و باز)
**نسخه:** run1 — گزارش‌های قبلی بازنویسی نشدند.

---

## ۱. Git

| فیلد | مقدار |
|---|---|
| HEAD | 4a239d84 |

## ۲. روش

برای هر router mount‌نشده:
1. مسیرها و نام handlerها (AST).
2. ماژول/سرویسی که به آن وابسته است.
3. آیا آن سرویس/پکیج در جای دیگری (router دیگر، job، script) مصرف می‌شود؟ → تصمیم «فقط router مرده» در برابر «کل زیرسیستم مرده».

## ۳. جدول طبقه‌بندی

| ماژول (mount‌نشده) | مسیرها | کد پشتیبان | مصرف پشتیبان در جای دیگر | حکم |
|---|---|---|---|---|
| symbol_alerts | GET/POST /, DELETE /{id}, GET /{symbol}/decision-hub | app.alert_hub.* | فقط همین‌جا | زیرسیستم کامل مرده؛ معادل زنده و hardening-شده alerts (با مالکیت SEC-04) mount است → نامزد حذف |
| proposals | POST/GET "", POST /{id}/approve, POST /{id}/reject | services.proposal_service | فقط همین‌جا | زیرسیستم کامل مرده → نامزد حذف |
| sentiment | POST /analyze, /batch, /train, GET /stats | services.persian_sentiment_service | فقط همین‌جا | زیرسیستم کامل مرده؛ تب «تحلیل احساسات» UI از /analysis/overview تغذیه می‌شود → نامزد حذف |
| monitoring | GET /metrics, GET /data-quality | apps.api.metrics.get_prometheus_exporter | بله (middleware فعال) | فقط router مرده؛ هیچ scrape ای برای /metrics پیکربندی نشده → نامزد mount |
| scanner | POST /scan, GET /scan/status, /scan/results, POST /scan/extract-relations | services.mass_scanner_service | بله (backtests.py mount‌شده، backtesting/runner.py) | فقط router مرده؛ سرویس زنده → نامزد mount یا حذف router |
| ime | GET /dashboard, /futures, /options, /certificates, /funds, /physical-trades | brsapi.services.query_service | بله (مشترک) | فقط router مرده؛ /ime/futures با /gold/ime/futures (mount‌شده) هم‌پوشانی دارد؛ بقیه یکتا → نامزد mount |
| comprehensive_analysis | GET /{symbol}/comprehensive-analysis | brsapi_query_service (مشترک) | بله | فقط router مرده؛ هم‌پوشانی با /analysis/overview → نامزد حذف |

## ۴. نتیجه‌گیری شواهدمحور

- هیچ‌کدام از ۷ path در frontend/src مصرف نمی‌شود (rg بدون نتیجه برای /sentiment, /proposals, /scanner, decision-hub, comprehensive-analysis, /monitoring/metrics, /data-quality) → خطای زندهٔ کاربر وجود ندارد.
- ۳ مورد (symbol_alerts, proposals, sentiment) کل زیرسیستم پشتیبان‌شان فقط از طریق همین router mount‌نشده قابل دسترسی است → کل زیرسیستم مرده است (نامزد تمیز حذف).
- ۴ مورد (monitoring, scanner, ime, comprehensive_analysis) سرویس مشترک و زنده دارند؛ فقط سطح HTTP آن‌ها mount نشده.
- نکتهٔ عملیاتی: monitoring//metrics تنها منبع exposition است و هیچ scrape ای به آن وصل نیست → متریک‌ها جمع می‌شوند ولی خوانده نمی‌شوند.

## ۵. توصیهٔ اقدام (نیازمند تصمیم محصول)

| اولویت | اقدام |
|---|---|
| ۱ | mount کردن monitoring (فقط /metrics با include_in_schema=False) + افزودن scrape به compose — کم‌ریسک و پر‌ارزش |
| ۲ | تصمیم دربارهٔ symbol_alerts/proposals/sentiment: حذف (کد مرده) یا احیا با مالکیت/نقش |
| ۳ | mount یا حذف scanner/ime/comprehensive_analysis |

به‌دلیل قاعدهٔ «تصمیم mount/حذف بدون تأیید محصول»، این مرحله هیچ router را mount یا حذف نکرد؛ فقط طبقه‌بندی مستند شد.

## ۶. معیارهای پذیرش

| معیار | نتیجه |
|---|---|
| طبقه‌بندی ۷ ماژول با شاهد کد | PASS |
| تأیید نبود مصرف‌کنندهٔ فرانت‌اند | PASS |
| تعیین «کل‌زیرسیستم مرده» در برابر «فقط router مرده» | PASS (۳ در برابر ۴) |
| تصمیم mount/حذف یک‌طرفه گرفته نشد | PASS |

## ۷. باقی‌مانده

- تصمیم محصولی برای ۷ ماژول بالا.
- دسته‌های B/C/D/E طرح مادر.