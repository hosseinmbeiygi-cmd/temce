# تحلیل تطبیقی سند معماری با وضعیت فعلی — سامانۀ آپشن و بازار کالا
> مبتنی بر سند: `documentاخخخ.pdf` (۳ شهریور ۱۴۰۵) — معماری ۴ لایه نیمه‌خودکار

## چکیده تصمیم معماری سند
- **اصل:** BrsApi فقط **منبع داده** است، نه مجری سفارش. اجرای واقعی باید از **Adapter Broker مستقل** پس از کنترل ریسک انجام شود.
- **معماری ۴ لایه:** Data Plane (دریافت + کیفیت‌سنجی) / Research Plane (قیمت‌گذاری + بک‌تست) / Trading Plane (سیگنال + سفارش پیشنهادی) / Control Plane (هویت، پیکربندی، ممیزی، kill switch)
- **سطح اتوماسیون:** نیمه‌خودکار — سامانه فرصت + هزینه + ریسک را می‌سازد، **کاربر مجاز** تأیید می‌کند. هیچ مدل/استراتژی نباید ریسک را دور بزند.
- **منابع داده تأییدشده سند:** آمار معاملات فیزیکی، صندوق‌های کالایی، گواهی سپرده، آپشن و آتی IME (سرویس‌های BrsApi با JSON + API Key + پارامتر بازار)

---

## ۱. وضعیت موجود (آنچه دارید) — دارایی‌های قابل حفظ

| لایه سند | دارایی فعلی در کد | وضعیت |
|----------|-------------------|--------|
| Data Plane | `brsapi/models/tsetmc.py` + `ime.py` (snapshots جفتی call/put، فیزیکی/گواهی/صندوق/آتی)، `parsers/tsetmc.py`, `parsers/ime.py`، `services/sync_service.py` (هر ۵دقیقه ساعات بازار)، نگهداری `raw_json` + `fetched_at` + `time` بازار | **۷۰٪ منطبق** — snapshot نگهداری می‌شود ولی نسخه immutable + checksum + لاگ HTTP هنوز کامل نیست |
| Research Plane | `services/options_service.py` (۳۰ استراتژی)، `domain/options/pricing.py` (BS + IV)، `greeks/higher_order`, `tree_pricing`, `heston`, `commodity_pricing`, `margin_engine`, `var_calculator`, `backtesting/strategies/options` (۶ استراتژی)، `tests/unit/options` (۴۱ تست) | **۸۰٪ منطبق** — کتابخانه‌ها versioned نیستند، ورودی‌های مؤثر (r/q/تقویم) ثبت نسخه نمی‌شوند |
| Trading Plane | `services/quant_signal_orchestrator.py` (۶ مرحله + voting + confidence + decision ۱۰گانه)، `frontend/src/app/options/page.tsx` (۴ تب، زنجیره زنده، Payoff SVG)، `quickBuy` فعلی mock با `alert` | **۵۰٪ منطبق** — Engine سیگنال وجود دارد ولی `Proposal Order` + `Gateway Approval` وجود ندارد، اجرای واقعی mock است |
| Control Plane | `apps/api/middleware.py` (sanitization, timing)، `core/security/tokens.py` (JWT + httpOnly refresh)، `brsapi/jobs/registry.py` (cron)، `Audit` جزئی | **۴۰٪ منطبق** — RBAC، audit trail تغییرناپذیر، kill switch، health check، داشبورد عملیاتی ناقص |

تصمیم‌های درست موجود که سند تأیید می‌کند و باید حفظ شود: نگهداری پاسخ خام، ثبت جداگانه `time` بازار و `fetched_at`، تفکیک `contracts` از `snapshots`، نگاشت بین بازارها.

---

## ۲. شکاف‌های کلیدی نسبت به سند

### Data Plane — تثبیت قرارداد داده (فاز صفر سند)
- ❌ مخزن خام immutable با `id_source, status HTTP, مدت پاسخ, checksum, نسخۀ schema` جداگانه وجود ندارد — فقط `raw_json` در جدول snapshot.
- ❌ لایه **Normalizer** به مدل مشترک (`instruments, contracts, market_snapshots, orderbook_levels, trades, instrument_mapping`) وجود ندارد — هر منبع جدول جدا دارد.
- ❌ جداول مرجع `corporate_actions, trades/orderbook_levels/instruments` هنوز جدا از BrsApi نیستند.
- ❌ نرخ بدون ریسک، سود نقدی، تقویم معاملاتی، اقدامات شرکتی، لغزش، محدودیت موقعیت، شرایط اعمال به‌صورت **نسخه‌دار** ثبت نمی‌شوند.
- ❌ اعتبارسنجی schema + هشدار تغییر schema بدون تست سازگاری (سند: SLA و versioning تضمین نیست)
- ✅ فیکس اخیر: `dedup` بر اساس `params` + `bulk_insert rowcount` + `checksum` در `raw_json` — گام اول به سمت سند

### Research Plane — تحلیل قابل اعتماد (فاز یک)
- ❌ هر خروجی فاقد `version_calculation, ورودی‌های مؤثر, timestamp` است.
- ❌ انتخاب قیمت برای IV سلیقه‌ای است (Mid/Ask/Bid/Last بدون flag کیفیت/کهنگی).
- ❌ بک‌تست کارمزد/spread/latency/slippage/limit/نقدشوندگی و عدم آینده‌نگری را مدل نمی‌کند — `backtesting/*` ساده است.
- ❌ تست‌های CI فعلی ۴۱ مورد BS/parity را پوشش می‌دهند ولی فاقد تست `Greeks`, داده ناقص, `limit price` هستند.
- ✅ اصلاحات انجام‌شده: `pricing.py` گارد `gamma=inf`, `tree_pricing` عبارات مرده، `var_calculator` گارد `nan` — مطابق الزام «ثبت ورودی مؤثر»

### Trading Plane — پیشنهاد تا تأیید (فاز دو)
- ❌ **Proposal Order** تعریف نشده — خروجی فعلی `EnrichedSignal` است نه سفارش با `legs, قیمت پیشنهادی, هزینه, ریسک, سناریو زیان, TTL`.
- ❌ **Approval Gateway** وجود ندارد — `options/page.tsx:141` هنوز `alert` و سپس باید `Gateway Approval` با خلاصه ریسک و امکان تأیید/رد باشد.
- ❌ **Portfolio Greeks + Risk Engine مستقل** وجود ندارد — ریسک داخل خود `quant_signal_orchestrator` ادغام است و قابل دور زدن است.
- ❌ شبیه‌سازی paper trading با دفتر داخلی و audit کامل سفارش (accepted/partial/filled/cancelled + idempotency) وجود ندارد.
- ✅ موتور سیگنال، زنجیره زنده و مارجین موجود است — پایه برای فاز دو آماده است.

### Control Plane
- ❌ `RBAC` روی ابزارهای IME/آپشن ناقص (سند: `only approver` باید تأیید کند)
- ❌ `audit trail` تغییرناپذیر (append-only) + `kill switch` + `circuit breaker` وجود ندارد.
- ❌ نگهداری امن کلیدها (`secret management`) پراکنده در `.env` است.
- ❌ داشبورد عملیاتی + هشدار خطای داده (Data Quality) وجود ندارد.

---

## ۳. معماری هدف پیشنهادی (نگاشت سند به کد شما)

```
[ BrsApi / TSETMC / IME ] ─┬─► Raw Store (immutable, checksum, schema version)
                            │         │
                            ▼         ▼
                      Adapter per source ─► Normalizer ─► Reference DB
                      (ImePhysical/Fund/Cert/Option/Future)   (instruments, contracts,
                                                               market_snapshots, trades,
                                                               orderbook_levels, corporate_actions,
                                                               risk_free, dividend, calendar)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              Research Plane    Trading Plane     Control Plane
              (versioned libs) (Signal→Risk→Proposal) (RBAC, Audit, Kill Switch)
                    │                 │                 │
                    └────────► Approval Gateway ◄───────┘
                                   │
                              Broker Adapter (مستقل، idempotent)
                                   │
                              Paper → Allowlist → Live (مرحله‌ای)
```

**اصول اجرایی از سند:**
- هر سرویس data یک **Adapter مستقل** با ثبت خام کامل + `Normalizer` مشترک.
- تمام خروجی‌های محاسباتی **نسخه‌دار** (ورودی‌ها + `version_calculation` + زمان).
- **Risk Engine مستقل** — هیچ مسیر مستقیم از Signal به Broker بدون گذر از Risk.
- **سفارش فقط Proposal** تا تأیید انسانی؛ پس از تأیید با `idempotency key` ارسال و وضعیت‌ها ثبت شود.

---

## ۴. نقشه راه و معیار پذیرش (اقتباس سند)

### فاز ۰ — تثبیت قرارداد داده (۲–۳ هفته)
- [ ] مخزن خام immutable + اسکیماهای مشترک + `instrument master` + `instrument_mapping`
- [ ] ثبت `r, q, تقویم, اقدامات شرکتی, هزینه, slippage` به‌صورت نسخه‌دار
- [ ] Data Quality Rules + تست سازگاری schema در CI
- **معیار خروج:** هر رکورد تا `raw + source + fetched_at + schema version` قابل ردیابی؛ تغییر schema بدون هشدار وارد تحلیل نمی‌شود.

### فاز ۱ — تحلیل قابل اعتماد (۳–۴ هفته)
- [ ] داشبورد یکپارچه آپشن/گواهی/صندوق/آتی + ذخیره `Greeks/IV/PCR/max_pain/carry/spread` با نسخه
- [ ] بک‌تست با کارمزد/spread/latency/slippage + تست parity/Greeks/داده ناقص
- [ ] تست سازگاری Adapter با قرارداد HTTP/JSON/Key/بازار
- **معیار خروج:** گزارش بک‌تست با هزینه/لغزش + CI سبز برای parity و داده ناقص

### فاز ۲ — سفارش پیشنهادی + Paper Trading (۳–۴ هفته)
- [ ] `Proposal Order` + `Risk Engine` مستقل + `Approval Gateway` (خلاصه ریسک + TTL)
- [ ] شبیه‌سازی چرخه سفارش + دفتر داخلی + audit کامل + `idempotency`
- [ ] اجرای پایدار چند هفته‌ای با صفر bypass ریسک
- **معیار خروج:** انطباق موقعیت با دفتر داخلی + ثبت کامل تصمیم کاربر

### فاز ۳ — اجرای محدود (وابسته به Broker Adapter)
- [ ] Allowlist نماد + سقف سرمایه/زیان + سفارش قابل لغو + kill switch + بازیابی
- [ ] هر بازار پس از تأیید کتبی مالک ریسک + تست دسترسی + تأیید Adapter
- **نکته سند:** اجرای واقعی نباید از لایه داده استنباط شود — Broker یک پروژه مستقل حقوقی/فنی است؛ مدل‌های ML پیچیده تا اندازه‌گیری کیفیت تاریخچه و paper به تأخیر افتد.

---

## ۵. ارتباط با فیکس‌های اخیر پروژه
فیکس‌های این هفته مستقیماً فاز ۰/۱ سند را پوشش می‌دهد:
- `quant_signal_orchestrator _stage_time` → پایداری Trading Plane
- `pricing/var/tree/margin` → نسخه‌پذیری و دقت Research Plane
- `feature_engine float` + `indicators period` → کیفیت داده و امتیاز سیگنال
- `next.config` + `api AbortError` + `dedup/rowcount` → قرارداد داده و کیفیت‌سنجی Data Plane

**گام بعدی پیشنهادی:** پیاده‌سازی `Raw Store` + `Normalizer` + `Proposal Order` به‌عنوان PR فاز صفر (همان اولویت سند).

## ۶. منابع
1. محتوای معماری و الزامات سامانه آپشن و بازار کالا (فایل متنی سند، خطوط ۱۱–۵۶۲)
2. مستندات API بورس TSETMC و دامنه بازارها (خطوط ۶۱–۱۲۰)
3. وب‌سرویس‌های بورس کالا (IME) — صفحه دسته‌بندی BrsApi (۲۳ اوت ۲۰۲۶)
