# موج اول آزمون دستی — Auth و Gold

- تاریخ: 2026-10-31T02:03:06
- شاخه: `backup/db02-baseline-20261030`
- HEAD: `54c6a6eb`
- محیط: `tse_quant_verify` روی 15432 (۲۰۳ جدول، ۰ کاربر اولیه)، Redis 16379
- مهاجرت 0120 روی DB تستی اعمال شد (`0119 → 0120`).
- سرور تستی: `scripts/ui_test_server.py` بدون startup sync/scheduler/BrsApi/news.
- داده آزمایشی: کاربر `audit_ui_20261030` (admin) و holding با note `AUD-UI-20261030`؛ هر دو پس از آزمون حذف شدند.
- بررسی کامل UI همهٔ ۲۲ صفحهٔ Gold انجام نشد؛ دلیل: timeout مرورگر در `/gold` و reload `/gold/portfolio`.

## نتایج تأییدشده

| شناسه | جریان | نتیجه UI | نتیجه API | Persistence | وضعیت |
|---|---|---|---|---|---|
| AUTH-01 | ورود صحیح | موفق؛ انتقال به `/` | POST `/auth/login` 200 | refresh 200 پس از reload | PASS |
| AUTH-02 | رمز اشتباه | پیام «Login failed: missing access token» | POST 200 با `success:false` | ورودی‌ها حفظ شد | FAIL |
| AUTH-03 | Logout | انتقال به `/auth/login` | POST logout | session پاک شد | PASS |
| AUTH-04 | مسیر محافظت‌شده بدون session | redirect به `/auth/login?redirect=/gold/portfolio` | — | — | PASS |
| AUTH-05 | Register UI | صفحه پس از ~۹۰s لود شد؛ فرم submit نشد | — | — | NOT RUN |
| GOLD-01 | Portfolio load | ۱۸ تب و empty state | `/gold/portfolio` 200 | — | PASS |
| GOLD-02 | افزودن holding | فرم reset شد؛ بدون toast | POST holdings 200 | id=1، qty=2، ۱۰۰٬۰۰۰٬۰۰۰ ریال، fee=0.5٪، user_id ثبت شد | PASS |
| GOLD-03 | حذف holding | از طریق API | DELETE force 200 | ردیف حذف شد | PASS |
| GOLD-04 | live-prices | — | 200 با `gold_oz_usd:0.0` و ... | — | FAIL |
| GOLD-05 | portfolio P&L | P&L کل +۰ | `total_pnl=0` ولی `returns.nominal_pnl_irt=-100000000` و `-100%` | — | FAIL |
| GOLD-06 | Reload/New page Gold | timeout مرورگر | SSR `/gold` 200 سریع | — | BLOCKED |

## یافته‌ها

### F1 — High — رمز اشتباه پیام گمراه‌کننده می‌دهد
- `frontend/src/lib/auth-context.tsx` بعد از login فقط `res.ok` را چک می‌کند و `success:false` را نمی‌بیند؛ سپس `missing access token` پرتاب می‌کند.
- بک‌اند `apps/api/endpoints/auth.py` خطای اعتبارنامه را با HTTP 200 و `success:false` برمی‌گرداند.
- شاهد: Network `POST /api/v1/auth/login [200]` و UI: `Login failed: missing access token`.
- اثر: کاربر پیام «رمز اشتباه» نمی‌بیند؛ پشتیبانی گمراه می‌شود.

### F2 — High — live-prices در نبود داده صفر برمی‌گرداند
- `GET /api/v1/gold/live-prices` در DB خالی: `gold_oz_usd:0.0`, `gold_18k_irr:0.0`, `coin_bahar_irr:0.0`, `usd_irr:0.0`.
- اثر: صفر به‌جای NO_DATA/`—` می‌تواند به‌عنوان قیمت واقعی رندر شود.

### F3 — High — ناسازگاری P&L برای holding بدون قیمت
- `GET /api/v1/gold/portfolio` پس از افزودن holding بدون قیمت بازار:
  - `total_pnl=0`, `total_pnl_pct=0`, `unpriced_holdings=1`
  - `returns.nominal_pnl_irt=-100000000`, `nominal_pnl_pct=-100`
- UI P&L کل `+۰` نشان می‌دهد؛ holding P&L `—`؛ هشدار unpriced نمایش داده می‌شود.
- اثر: دو معیار متناقض برای یک پرتفوی؛ مصرف‌کننده API ممکن است -100% را واقعی بداند.

### F4 — Medium — دو فرم ورود در DOM (یکی مخفی/صفراندازه)
- در `/auth/login` سه فرم وجود داشت: search، login visible، login hidden با rect صفر.
- کلیک accessibility روی uid ممکن است فرم مخفی را هدف بگیرد و submit نشود؛ با DOM click روی فرم visible کار کرد.
- نیازمند بررسی علت duplicate (احتمالاً render دوباره/کامپوننت مخفی).

### F5 — Medium — افزودن holding بازخورد موفقیت ندارد
- بعد از submit، فرم reset شد و holding فقط پس از تغییر تب دیده شد؛ toast/پیام موفقیت در snapshot نبود.
- persistence واقعی بود، ولی کاربر ممکن است فکر کند ثبت نشده.

### F6 — Blocked — مرورگر روی Gold/reload قفل می‌شود
- `/gold` در browser-use تایم‌اوت شد؛ `/gold/portfolio` در chrome-devtools بعد از تعامل، reload/new page را تایم‌اوت کرد؛ SSR با curl 200 و سریع بود.
- این مورد **اثبات نقص محصول نیست**؛ نیاز به پروفایل client-side (WS/polling/render) دارد.

### F7 — Low — Register page اولین بار ~۹۰s
- `GET /auth/register` اول 000 و بعد 200 در ~۹۰s؛ احتمالاً compile Next dev، نه لزوماً production.

## خطاهای API/DB مشاهده‌شده
- `GET /gold/portfolio` قبل از اعمال 0120: 500 (ستون‌های user_id نبودند). بعد از migration: 200.
- `GET /gold/snapshot` در محیط بدون داده/BrsApi: 503 `snapshot_unavailable` (رفتار صادقانه).
- در log بک‌اند: `asyncpg InFailedSQLTransactionError` روی query مربوط به `brsapi_symbol_snapshots` هنگام بارگذاری داشبورد؛ نیاز به بررسی session/transaction.

## تغییرات
- فایل تستی جدید: `scripts/ui_test_server.py` (فقط harness).
- DB تستی: مهاجرت 0120 اعمال شد.
- داده تستی: کاربر admin و holding ایجاد و سپس حذف شدند.
- کد محصول تغییر نکرد.

## محدودیت‌ها
- ۲۲ صفحهٔ Gold و کنترل‌های آن‌ها کامل اجرا نشد؛ فقط Portfolio.
- Register UI submit و mobile viewport اجرا نشد.
- بازار داده واقعی/BrsApi در محیط تستی نبود؛ empty/error بررسی شد، نه داده زنده.
- مرورگر پس از تعامل با Gold پاسخ‌گو نشد.

## اقدامات بعدی
1. رفع F1 (بررسی `success:false` در login + پیام دقیق) با تست.
2. رفع F2 (null/NO_DATA به‌جای 0 در live-prices) و F3 (یکدست‌سازی P&L unpriced).
3. بررسی F4/F6 با پروفایل شبکه/کنسول و لاگ‌های client.
4. ادامهٔ Gold با محیط مرورگر سالم/ری‌استارت‌شده و داده fixture کنترل‌شده.
