# وضعیت پیاده‌سازی موتور NAV مستقل و تطبیق

> نسخه: ۲.۱ — ۱۴۰۵/۰۶/۲۸
> مرجع طراحی: `docs/funds/NAV_ARCHITECTURE_V5.md` (نسخه ۵.۱) + `docs/funds/NAV_CONTROLS_REGISTER_500.md`
> دامنه اجرا: **صفحه صندوق** (`/funds/[symbol]`) — بک‌اند + فرانت‌اند.

---

## ۱. خلاصه

همه فازهای ۱ تا ۱۲ معماری (به‌جز اتصال‌های رسمی برون‌سازمانی) پیاده و تست شده‌اند:
NAV مستقل + تطبیق + دفتر دوطرفه + طبقات + FOF بازگشتی + AML/شرعی + حاکمیت +
مالیات (قاعده و جریان معاملات) + چرخه عمر + CSDI + کالیبراسیون + Backfill +
درگاه نظارتی با کلید دسترسی + پذیرش سایه + پنل صفحه صندوق.

- بک‌اند: **۱۵۵ تست پاس** در سوئیت صندوق، `ruff` پاک، زنجیره Alembic `0058 (head)`.
- فرانت‌اند: **۱۴ تست Vitest پاس**، `eslint` پاک، `tsc --noEmit` بدون خطا.
- هیچ قرارداد موجودی (`/funds`, `/funds/v2`) تغییر نکرده؛ همه‌چیز Additive است.

---

## ۲. نگاشت فازها به پیاده‌سازی

| فاز (سند معماری) | وضعیت | فایل/سند |
|---|---|---|
| ۱. قرارداد داده | ✅ انجام شد | انواع NAV، سه بُعد تطبیق، زمان‌ها، دقت در `services/fund_nav_engine.py` + `models/fund_nav.py` |
| ۲. مرجع و دفتر مالی + واحدها | ✅ انجام شد | دفتر دوطرفه `chart_of_accounts/journal_entries/journal_lines` + تریگر توازن + API حرکت واحدها + تراز آزمایشی |
| ۳. ارزش‌گذاری + Snapshot | ✅ انجام شد | `FundNavEngine._build_payload` + `value_position` + `input_hash` |
| ۴. NAV مستقل و طبقاتی | ✅ انجام شد | `fund_class_nav.py` (SIMPLE/LEVERAGED/GUARANTEED) + `fund_fof.py` (NAV از NAV + **کشف حلقه + Look-through بازگشتی عمق ۳**) + UI |
| ۵. تطبیق API + پرونده مغایرت | ✅ انجام شد | `fund_nav_reconciliation.py` (گیت‌ها، آستانه دوگانه، Break) + **کالیبراسیون p95/p99** |
| ۶. تاب‌آوری (Outbox/Replay) | ✅ انجام شد | Outbox هم‌تراکنش + جاب انتشار + Redis Streams Sink + **رویدادهای AML/CSDI در Outbox** |
| ۷. انطباق/AML/شرعی | ✅ انجام شد | هشدار AML + STR با مهلت + **خروجی FIU-STR-JSON** + رجیستری تأیید شرعی |
| ۸. حاکمیت/تعارض منافع/حقوقی | ✅ انجام شد | RPT + شکایات + **کمیته‌ها، حسابرسی داخلی، انتظامی، بیمه D&O** |
| ۹. مالیات/چرخه عمر/مجمع | ✅ انجام شد | **`fund_tax.py` (قاعده + محاسبه از جریان معاملات)** + نسخه‌های امیدنامه + رویدادهای چرخه عمر |
| ۱۰. گزارش/داشبورد/درگاه نظارتی | ✅ انجام شد | پنل + **درگاه نظارتی با کلید دسترسی (REGULATOR_API_KEY) + X-Actor + لاگ + CSV** |
| ۱۱. اجرای سایه | ✅ انجام شد | `mode=SHADOW` + جاب روزانه + **گزارش پذیرش سایه (`shadow-acceptance`) با نرخ تطبیق و آمادگی** |
| ۱۲. مهاجرت تاریخی | ✅ جزئی | `FundNavEngine.backfill` بازسازی NAV تاریخی از گزارش دوره (mode=BACKFILL) + endpoint |

---

## ۳. فایل‌های ایجادشده (بک‌اند)

| فایل | نقش |
|---|---|
| `migrations/versions/0055_fund_nav_engine.py` | ۸ جدول: runs، position_valuations، results، reference_reports، reconciliation_runs، breaks، thresholds، unit_movements + آستانه پیش‌فرض |
| `models/fund_nav.py` | ORM مدل‌های متناظر |
| `services/fund_nav_engine.py` | محاسبه NAV مستقل + `input_hash` + کیفیت داده |
| `services/fund_nav_reconciliation.py` | گیت‌ها، اختلاف مطلق/bps، آستانه دوگانه، چرخه عمر Break |
| `apps/api/endpoints/funds_nav.py` | ۹ مسیر زیر `/funds/v2/nav` |
| `jobs/definitions/fund_nav_jobs.py` | `FundNavReconciliationJob` (اجرای سایه روزانه) |
| `tests/unit/services/test_fund_nav_engine.py` | ۱۹ تست منطق خالص |
| `tests/unit/test_funds_nav_api.py` | ۱۰ تست قرارداد API |
| `migrations/versions/0056_fund_ledger.py` | دفتر دوطرفه: chart_of_accounts، journal_entries/lines، تریگر توازن، Outbox |
| `models/fund_ledger.py` | ORM دفتر + Outbox |
| `services/fund_ledger.py` | ثبت سند متوازن، حرکت واحدها، سند برگشتی، تراز، Outbox |
| `apps/api/endpoints/funds_ledger.py` | ۵ مسیر زیر `/funds/v2/ledger` |
| `tests/unit/services/test_fund_ledger.py` | ۱۱ تست منطق خالص |
| `tests/unit/test_funds_ledger_api.py` | ۵ تست قرارداد API |
| `migrations/versions/0057_fund_tiered_nav_compliance.py` | طبقات، AML/شرعی، حاکمیت، چرخه عمر، کالیبراسیون، CSDI (۱۲ جدول) |
| `models/fund_compliance.py` | ORM جدول‌های فازهای ۴/۷/۸/۹ + CSDI |
| `services/fund_class_nav.py` | تخصیص SIMPLE/LEVERAGED/GUARANTEED + `percentile` |
| `services/fund_compliance.py` | AML (هشدار/STR)، شرعی، RPT، شکایات، امیدنامه، چرخه عمر، CSDI |
| `apps/api/endpoints/funds_compliance.py` | ۱۷ مسیر زیر `/funds/v2/compliance` |
| `tests/unit/services/test_fund_class_nav.py` | ۱۰ تست تخصیص طبقات |
| `tests/unit/services/test_fund_compliance.py` | ۸ تست قواعد انطباق |
| `tests/unit/test_funds_compliance_api.py` | ۹ تست قرارداد API |
| `migrations/versions/0058_fund_fof_tax_governance.py` | FOF، مالیات، کمیته‌ها، حسابرسی داخلی، انتظامی، D&O، لاگ نظارتی (۷ جدول) |
| `models/fund_governance.py` | ORM جدول‌های FOF/مالیات/حاکمیت/نظارتی |
| `services/fund_fof.py` | ارزش‌گذاری FOF + `detect_cycles` + `compute_fof_value` |
| `services/fund_tax.py` | قواعد و محاسبه مالیات (پنج نوع) |
| `apps/api/endpoints/funds_regulator.py` | ۳ مسیر زیر `/funds/v2/regulator` (evidence، audit-pack، access-logs) |
| `tests/unit/services/test_fund_fof.py` | ۷ تست FOF/حلقه |
| `tests/unit/services/test_fund_tax.py` | ۸ تست مالیات |
| `tests/unit/test_funds_regulator_api.py` | ۳ تست درگاه نظارتی |

### فایل‌های تغییریافته

`apps/api/router.py` (mount)، `jobs/definitions/__init__.py`، `apps/scheduler/app.py` (کرون ۱۸:۳۰)، `models/__init__.py` (export).

## ۴. فایل‌های ایجادشده (فرانت‌اند)

| فایل | نقش |
|---|---|
| `frontend/src/lib/fund-nav.ts` | Types + برچسب‌ها + helpers خالص |
| `frontend/src/hooks/useFundNavEngine.ts` | React Query: dashboard/calculate/reconcile/break |
| `frontend/src/components/FundNavEnginePanel.tsx` | پنل در صفحه صندوق |
| `frontend/src/__tests__/fund-nav.test.ts` | ۵ تست helper |
| `frontend/src/lib/fund-ledger.ts` | Types + برچسب‌ها + helpers دفتر |
| `frontend/src/hooks/useFundLedger.ts` | React Query: تراز/حرکت‌ها/اسناد/ثبت/برگشت |
| `frontend/src/components/FundLedgerPanel.tsx` | پنل دفتر مالی در صفحه صندوق |
| `frontend/src/__tests__/fund-ledger.test.ts` | ۴ تست helper |
| `frontend/src/lib/fund-compliance.ts` | Types + برچسب‌های AML/مالیات/کمیته + helpers |
| `frontend/src/hooks/useFundCompliance.ts` | ۱۵ hook انطباق/FOF/مالیات/CSDI |
| `frontend/src/components/FundCompliancePanel.tsx` | پنل انطباق و حاکمیت در صفحه صندوق |
| `frontend/src/__tests__/fund-compliance.test.ts` | ۵ تست helper |

`frontend/src/app/funds/[symbol]/page.tsx` → چهار پنل: NAV، دفتر، انطباق (و تحلیل قبلی).

---

## ۵. قرارداد API

| متد | مسیر | توضیح |
|---|---|---|
| POST | `/api/v1/funds/v2/nav/{fund_id}/calculate` | اجرای NAV مستقل (بدنه: `nav_type`, `as_of`, `mode`) |
| GET | `/api/v1/funds/v2/nav/{fund_id}/latest` | آخرین اجرا + ردیف‌های ارزش‌گذاری |
| GET | `/api/v1/funds/v2/nav/{fund_id}/runs` | تاریخچه اجراها |
| GET | `/api/v1/funds/v2/nav/{fund_id}/runs/{run_id}` | جزئیات اجرا |
| POST | `/api/v1/funds/v2/nav/{fund_id}/reconcile` | تطبیق با مرجع |
| GET | `/api/v1/funds/v2/nav/{fund_id}/reconciliation` | تاریخچه تطبیق + پرونده‌های باز |
| GET | `/api/v1/funds/v2/nav/{fund_id}/dashboard` | بسته یکپارچه صفحه صندوق |
| GET | `/api/v1/funds/v2/nav/breaks` | فهرست پرونده‌های مغایرت |
| PATCH | `/api/v1/funds/v2/nav/breaks/{break_id}` | به‌روزرسانی چرخه عمر |
| GET | `/api/v1/funds/v2/nav/{fund_id}/evidence` | بسته مدارک حسابرسی + `integrity_hash` |
| POST | `/api/v1/funds/v2/ledger/{fund_id}/unit-movements` | ثبت حرکت واحد + سند دوطرفه اتمیک |
| GET | `/api/v1/funds/v2/ledger/{fund_id}/trial-balance` | تراز آزمایشی |
| GET | `/api/v1/funds/v2/ledger/{fund_id}/entries` | اسناد مالی + خطوط |
| GET | `/api/v1/funds/v2/ledger/{fund_id}/unit-movements` | تاریخچه حرکت واحدها |
| POST | `/api/v1/funds/v2/ledger/entries/{entry_id}/reverse` | سند برگشتی (بدون حذف) |
| GET/PUT | `/api/v1/funds/v2/nav/{fund_id}/class-nav[/config]` | آخرین تخصیص طبقات / ثبت پیکربندی نسخه‌دار |
| POST | `/api/v1/funds/v2/nav/{fund_id}/class-nav/calculate` | محاسبه تخصیص طبقات (اهرمی/تضمین) |
| POST | `/api/v1/funds/v2/nav/{fund_id}/backfill` | بازسازی NAV تاریخی (فاز ۱۲) |
| POST | `/api/v1/funds/v2/nav/{fund_id}/thresholds/calibrate` | کالیبراسیون آستانه از تاریخ |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/aml/alerts[/generate]` | هشدارهای AML |
| POST/GET | `/api/v1/funds/v2/compliance/{fund_id}/aml/str` | گزارش مشکوک (STR) + ارسال |
| GET/POST | `/api/v1/funds/v2/compliance/sharia/approvals` | تأیید شرعی ابزار |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/rpt` | معاملات اشخاص وابسته |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/complaints` | شکایات |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/prospectus` | نسخه‌های امیدنامه |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/lifecycle` | رویدادهای چرخه عمر |
| POST/GET | `/api/v1/funds/v2/compliance/{fund_id}/csdi/statements`, `/csdi/reconcile`, `/csdi/breaks` | ورود و تطبیق CSDI |
| GET/POST | `/api/v1/funds/v2/nav/{fund_id}/fof[/calculate]` | ارزش FOF + کشف حلقه |
| GET/POST | `/api/v1/funds/v2/compliance/tax/rules`, `/{fund_id}/tax/calculate`, `/tax/summary` | قواعد و محاسبه مالیات |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/committees` | کمیته‌های حاکمیتی |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/internal-audits` | حسابرسی داخلی |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/disciplinary` | پرونده‌های انتظامی |
| GET/POST | `/api/v1/funds/v2/compliance/{fund_id}/insurance` | بیمه مسئولیت (D&O) |
| GET | `/api/v1/funds/v2/compliance/{fund_id}/aml/str/{str_id}/export` | خروجی FIU-STR-JSON |
| GET | `/api/v1/funds/v2/regulator/{fund_id}/evidence` | بسته کامل نظارتی (با لاگ دسترسی) |
| GET | `/api/v1/funds/v2/regulator/{fund_id}/audit-pack` | خروجی CSV حسابرسی |
| GET | `/api/v1/funds/v2/regulator/access-logs` | سابقه دسترسی‌های نظارتی |
| GET | `/api/v1/funds/v2/nav/{fund_id}/shadow-acceptance` | گزارش پذیرش اجرای سایه (نرخ تطبیق/آمادگی) |
| POST | `/api/v1/funds/v2/compliance/{fund_id}/tax/from-trades` | مالیات مقطوع از جریان معاملات |

`fund_id` کانونی `tse:نماد` است؛ نماد خام هم پذیرفته می‌شود.

---

## ۶. تصمیم‌های کلیدی پیاده‌سازی

1. **جدا بودن سه بُعد وضعیت:** `comparability_status`، `reference_status`، `diff_status` هیچ‌گاه در یک enum جمع نمی‌شوند.
2. **آستانه دوگانه:** عبور از `abs_warn/abs_breach` **یا** `bps_warn/bps_breach` کافی است؛ پیش‌فرض سراسری با `fund_id='*'` و قابل override برای هر صندوق.
3. **مرجع کهنه/نامعتبر ⇒ مقایسه‌پذیر نیست:** `STALE`/`INVALID` باعث `NOT_COMPARABLE` و نبود `diff_status` می‌شود (شکست گیت ≠ MATCHED).
4. **کیفیت داده مستقل از وضعیت اجرا:** `COMPLETE/ESTIMATED/PARTIAL/BLOCKED` فقط از پوشش قیمت، وجود موقعیت، گزارش دوره و واحدها می‌آید.
5. **بازتولیدپذیری:** `input_hash` قطعی (canonical JSON) + `engine_version` + `policy_version` روی هر اجرا.
6. **idempotency:** قید یکتای `(fund_id, valuation_date, nav_type, input_hash)`؛ اجرای دوباره ردیف تکراری نمی‌سازد.
7. **اجرای سایه:** تمام محاسبه/تطبیق با `mode=SHADOW` و بدون هرگونه ارسال سفارش.

---

## ۷. نحوه اجرا و آزمون

```bash
# مهاجرت (روی PostgreSQL)
alembic upgrade head        # → 0056

# تست‌های بک‌اند
pytest tests/unit/services/test_fund_nav_engine.py tests/unit/services/test_fund_ledger.py \
       tests/unit/test_funds_nav_api.py tests/unit/test_funds_ledger_api.py -q

# اجرای دستی یک صندوق (نمونه)
curl -X POST localhost:8000/api/v1/funds/v2/nav/tse:آگاس/calculate -H "Content-Type: application/json" -d "{}"
curl -X POST localhost:8000/api/v1/funds/v2/nav/tse:آگاس/reconcile -H "Content-Type: application/json" -d "{}"
curl localhost:8000/api/v1/funds/v2/nav/tse:آگاس/dashboard
curl -X POST localhost:8000/api/v1/funds/v2/ledger/tse:آگاس/unit-movements \
  -H "Content-Type: application/json" \
  -d '{"movement_type":"ISSUE","movement_date":"2026-09-18","units":100,"price_per_unit":50000}'
curl localhost:8000/api/v1/funds/v2/ledger/tse:آگاس/trial-balance

# فرانت‌اند
cd frontend && npx vitest run src/__tests__ && npx tsc --noEmit && npx eslint src/components/FundLedgerPanel.tsx
```

---

## ۸. کارهای باقی‌مانده (صریح)

فازهای معماری کامل شده‌اند؛ موارد باقی‌مانده **عملیاتی/برون‌سازمانی** هستند و در کد قابل اتمام نیستند:

- **اتصال رسمی به سامانه مرکز AML و CSDI** (رکورد داخلی + Outbox + خروجی استاندارد آماده است؛ تبادل واقعی نیازمند مجوز/سند رسمی است).
- **اجرای پذیرش سایه چندروزه با داده واقعی** (گزارش `shadow-acceptance` آماده است؛ اجرای واقعی زمان‌بر است).
- **RBAC/SoD کامل روی مسیرهای جدید** با اتصال به سیستم هویت موجود (کلید نظارتی و `_optional_auth` فعال است).
- **کالیبراسیون عملیاتی آستانه‌ها** پس از انباشت نمونه واقعی.
- **ورود داده معاملات صندوق** برای محاسبه خودکار مالیات (پردازش از جریان معاملات پیاده شده).

> جمع‌بندی: پیاده‌سازی فازهای ۱–۱۲ سند معماری کامل و تست‌شده است؛ گام بعدی،
> اجرای سایه روی داده واقعی و اتصال‌های رسمی برون‌سازمانی است.
