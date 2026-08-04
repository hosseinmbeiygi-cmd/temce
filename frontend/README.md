# 🖥️ فرانت‌اند — Iran Market Platform (Next.js 16)

> **آخرین به‌روزرسانی:** ۲۰۲۶-۰۸-۰۲ — فاز ۱۱

داشبورد کوانت و تحلیل بازار سرمایه ایران — رابط کاربری کامل برای بیش از ۴۰ بخش (داشبورد، سیگنال، صف، بک‌تست، هوش مصنوعی، صندوق‌ها، اخبار و...).

---

## 🏗️ استک فنی

| بخش | تکنولوژی |
|------|-----------|
| فریم‌ورک | **Next.js 16** (App Router + Server Actions) |
| زبان | **TypeScript 5** (strict) |
| رابط | **React 19** + Tailwind CSS 4 |
| داده کلاینت | **TanStack Query v5** (کش، refetch، polling) |
| نمودار | **lightweight-charts** + **recharts** |
| تست | **Vitest 4** + Testing Library (jsdom) |
| پروکسی | Next.js rewrites → بک‌اند FastAPI (`api:8000`) |

---

## 🚀 اجرا

```bash
cd frontend
npm install
npm run dev          # توسعه (پورت 3000)
npm run build        # بیلد production (خروجی standalone)
npm start            # اجرای بیلد
npm run lint         # ESLint
npm run test         # Vitest (واحد)
npm run test:watch   # حالت watch
```

### محیط (`.env`)
```bash
# پروکسی سمت سرور → بک‌اند (هیچ‌وقت به مرورگر نشت نمی‌کند)
API_URL=http://localhost:8000
API_PREFIX=/api/v1

# سمت کلاینت (NEXT_PUBLIC_ — فقط اگر مستقیم به بک‌اند وصل می‌شوید)
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws
```

> **نکته امنیتی:** از `API_URL` (بدون پیشوند `NEXT_PUBLIC_`) برای پروکسی استفاده کنید تا آدرس بک‌اند در مرورگر فاش نشود. متغیرهای `NEXT_PUBLIC_*` در bundle کلاینت قرار می‌گیرند.

---

## 🗂️ ساختار

```
frontend/src/
├── app/                  # صفحات (App Router) — ۴۰+ مسیر
│   ├── page.tsx          # داشبورد اصلی (شاخص، نرخ ارز، طلا، خبر، ...
│   ├── layout.tsx        # ریشه: فونت Vazirmatn + تم + Providers
│   ├── signals/          # سیگنال‌ها
│   ├── symbol/[symbol]/  # صفحه جزئیات نماد
│   ├── backtest/         # بک‌تست
│   ├── funds/            # صندوق‌ها
│   └── ...               # ۴۰+ صفحه دیگر
├── components/           # کامپوننت‌های مشترک
│   ├── layout/           # AppLayout, Sidebar
│   ├── ui/               # Card, Button, Badge...
│   ├── charts/           # TradingViewChart, IndicatorChart
│   └── ...               # ۳۰+ کامپوننت (Modal, Sparkline, Skeleton...)
├── hooks/                # useWebSocket, useClientData, useTheme, useAuth...
├── lib/                  # api.ts, auth-context.tsx, dates.ts, types.ts...
└── __tests__/            # تست‌های واحد (Vitest + Testing Library)
```

---

## 🔑 احراز هویت (auth-context.tsx + lib/api.ts)

- **`AuthProvider`** — مدیریت state احراز هویت با hydration از `localStorage` در mount (الگوی مستند React برای ذخیره‌سازی خارجی).
- **`useAuth()`** — دسترسی به `user`, `login`, `logout`, `refreshAccessToken`, `hasRole/hasAnyRole` (سلسله‌مراتب: admin > analyst > user > viewer).
- **توکن‌ها** در localStorage با کلید `auth` ذخیره می‌شوند.
- **Silent refresh** — همه متدهای `apiGet/apiPost/apiPut/apiDelete` در 401 ابتدا refresh توکن را امتحان می‌کنند (با **deduplication** درخواست‌های هم‌زمان) و در صورت شکست به صفحه ورود هدایت می‌کنند. اینترفیس‌های `/auth/*` هرگز refresh نمی‌شوند.
- **timeout** — درخواست عادی ۶۰ ثانیه، عملیات سنگین (sync) ۱۰ دقیقه (`AbortController`).

---

## 🔌 ارتباط با بک‌اند

```
مرورگر → /api/v1/* (Next.js) → rewrites → FastAPI (api:8000)
```

- `next.config.ts` — `rewrites()` همه درخواست‌های `/api/v1/:path*` را به بک‌اند پروکسی می‌کند.
- `output: "standalone"` — آماده Docker multi-stage.
- **WebSocket** — `useWebSocket` با reconnect خودکار (تا ۱۰ بار، هر ۳ ثانیه)، ping/keep-alive هر ۳۰ ثانیه، و ref نگه‌داشتن handlerها بدون بازسازی اتصال.

---

## 🧪 تست‌ها (۲۰۵ تست)

| فایل | تعداد | پوشش |
|------|-------|------|
| `silent-refresh.test.ts` | ۱۶ | refresh توکن، dedup، 401، SSR |
| `auth-context.test.tsx` | ۱۰ | hydration، login/logout، نقش‌ها، refresh |
| `fund-analysis.test.ts` | ۶۲ | تحلیل صندوق، NAV، مقایسه |
| `compareReport.test.ts` | — | مقایسه ریپورت بک‌تست |
| `MiniSparkline.test.tsx` | — | رندر نمودار کوچک |
| `SSRSafe.test.tsx` | — | کامپوننت‌های امن برای SSR |
| `useApiMonitor/useClientData/useDebugLogs/useTheme` | — | هوک‌ها |

```bash
npm run test        # اجرای همه تست‌ها
npx vitest run src/__tests__/auth-context.test.tsx   # تست خاص
```

---

## 🐛 اشکالات رفع‌شده در فاز ۱۱

| # | مشکل | مکان | راه‌حل |
|---|-------|------|--------|
| ۱ | **۵× `no-explicit-any`** | `silent-refresh.test.ts` | تایپ `(call: string[])` به‌جای `any[]` در فیلترهای refresh |
| ۲ | **`set-state-in-effect`** | `auth-context.tsx` | مستندسازی + disable با دلیل (الگوی hydration مجاز است) |
| ۳ | **`set-state-in-effect`** | `news/page.tsx` | disable با دلیل — ریست صفحه‌بندی رویدادمحور است نه state مشتق‌شده |
| ۴ | **`set-state-in-effect`** | `profile/page.tsx` | **ارتقا به الگوی React 19 توصیه‌شده**: همگام‌سازی فیلدها هنگام render (guarded توسط `syncedProfileId`) به‌جای useEffect — حذف effect و import بلااستفاده |
| ۵ | **disable بلااستفاده** | `SymbolQueueModal.tsx` | حذف دستور disable دوم (قانون فقط اولین setState را گزارش می‌دهد) |

---

## ⚠️ نکات و هشدارهای باقی‌مانده (۹۴ warning)

- **Missing dependencies** در `useEffect`ها: `TradingViewChart` (`cleanupSubChart`), `useClientData` (`generator`), `useWebSocket` (`ws`), `auth-context` (`ROLE_HIERARCHY`) — عمدتاً الگوهای intentional هستند که با ref نگه داشته می‌شوند؛ در صورت تمایل می‌توان `eslint-disable` مستند اضافه کرد.
- **متغیرهای استفاده‌نشده:** `LiveMarketWidget` (import useEffect), `fund-analysis.ts` (`PRIORITY_PENALTY`, `criticalCount`) — پاک‌سازی پیشنهاد می‌شود.
- **`total_pages` و داده mock** — برخی صفحات (داشبورد) در نبود بک‌اند به داده‌های نمونه برمی‌گردند (قصدی، برای نمایش).

---

## 🎨 طراحی

- **RTL کامل** (`dir="rtl"`) با فونت **Vazirmatn** (نسخه web با `next/font`).
- **تم تاریک/روشن** — اسکریپت hydration قبل از رندر برای جلوگیری از FOUC + `useTheme` (ذخیره در localStorage).
- **سیستم رنگی `surface`/`accent`** — انسجام بصری در همه صفحات.
- **کامپوننت‌های SSR-Safe** (`SSRSafe`, `ClientOnly`, `useClientData`) برای جلوگیری از hydration mismatch.
