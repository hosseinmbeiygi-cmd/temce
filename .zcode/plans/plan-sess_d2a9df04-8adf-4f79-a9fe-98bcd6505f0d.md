## بازطراحی صفحه بازار نقره (http://localhost:3000/markets/silver)

### خلاصه
صفحه فعلی نقره ۷۶۹ خط با ۱۰ سکشن شلوغ (hero، قیمتها، کندل، پیشبینی، آتی، ETF، فوتچر، مبدل، API، اخبار) است. بازطراحی با ۲ تب سراسری انجام میشود: **«دادههای واقعی»** و **«پیشبینی»** — طراحی تمیز، دادههای واقعی از API، بدون مطلب ساختگی. ضمناً صفحه پیشبینی جداگانه برای «همه قیمتها» ساخته میشود.

### نکته کشفشده
`/forecast` در روتر اصلی ثبت نیست (فقط در `_FRONTEND_BACKEND_COPY` هست). طلا-افایکس خودش دارد کار میکند چون از صفحه خام با ریکوئست مستقیم استفاده میکند. برای کارکرد این ویژگیها در صفحات جدید، باید روتر را correction کنم: `include_router(forecast_router, prefix="/forecast", tags=["Forecast"], dependencies=_optional_auth)` در `apps/api/router.py` (۲ خط).

---

### تغییرات

**۱. `frontend/src/app/markets/silver/page.tsx` — بازنویسی کامل (نسخه جدید، ~۶۰۰ خط)**
- یک hero خلوت، بدون گرادینت شلوغ: ۴ کارت (XAG/USD، نقره گرمی از آتی، صندوقها، دلار)
- ۲ تب: «قیمت و داده» | «پیشبینی»
- تب ۱ (دادههای واقعی — exact دادههای فعلی API):
  - قیمت لحظهای نقره (grid ساده ۲-۴ ستونی، کارتهای مینیمال)
  - نمودار کندل NAV صندوق (سبک، بدون ابزار hover پیچیده)
  - جدول صندوقهای نقره (نام/نماد/قیمت/NAV/حباب/تغییر)
  - جدول آتی نقره (نماد/سررسید/قیمت/تغییر/حجم)
  - مبدل گرم→دلار→ریال (فقط، حذف بلوک API)
- تب ۲ (پیشبینی XAG/USD):
  - کارت انتخاب افق (۱/۳/۷/۱۴/۳۰/۹۰ روز)
  - نمودار منحنی p50 + بازه ۸۰٪ (SVG ساده، بدون recharts)
  - جدول افق پیشبینی با احتمال رشد
  - دیسکلایمر
- حذف: سکشن News، بلوک API، ساختار آتی bar-chart، تبهای شلوغ
- دادهها: همان ۷ کوئری react-query فعلی، همه real

**۲. صفحه جدید پیشبینی «همه قیمتها» — `frontend/src/app/predictions/page.tsx` (جدید)**
- `"use client"` + `AppLayout`
- فهرست نمادها (واقعی، از `/forecast?symbol=`):
  - `gold_18k` طلای ۱۸ عیار
  - `xau_usd` اونس جهانی طلا
  - `xag_usd` اونس جهانی نقره
  - `usd_irr_free` دلار آزاد
- برای هر کدام: ۶ افق (۱/۳/۷/۱۴/۳۰/۹۰) با `Promise.allSettled`
- کارت هر نماد: قیمت فعلی (از `/brsapi/gold-coin` و `/brsapi/currency`)، تغییر انتظاری، احتمال رشد، نمودار SVG کوچک، جدول قابلگسترش با p50/بازه/احتمال
- `enabled` فقط وقتی قیمت فعلی موجود باشد
- `staleTime: 60s`
- ثبت در `frontend/src/lib/nav-config.tsx` (زیر «تحلیل و سیگنال» → «تحلیل»): «پیشبینی قیمتها» href `/predictions`

**۳. `apps/api/router.py` — ۲ خط**
- `from apps.api.endpoints.forecast import router as forecast_router`
- `router.include_router(forecast_router, prefix="/forecast", tags=["Forecast"], dependencies=_optional_auth)`

(الگوی `gold-fx/page.tsx` برای تب و پیشبینی، الگوی `components/gold/TimeSeriesChart.tsx` و کارتهای `Card`/`GoldKPICard` برای استایل)

### چیزهایی که عمداً حذف میشوند
- نمودار ساختار آتی bar-chart (تکراری با جدول آتی)
- سکشن اخبار (پیشبینیپرایس بیشتر میخواهد، خبر حواسپرتی است)
- بلوک API endpoints (مخاطب نیست)
- تگ «Lorem» — همهچیز فارسی، ساده، واقعی

### تأیید (ارزیابی)
- `cd frontend && npm run build` یا `npx tsc --noEmit` برای TypeScript
- تست دستی: صفحه silver، صفحه predicitions، اتصال `/forecast`