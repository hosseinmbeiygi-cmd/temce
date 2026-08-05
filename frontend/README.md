# 🖥️ فرانت‌اند — Iran Market Platform (Next.js 16)

> **آخرین به‌روزرسانی:** ۲۰۲۶-۰۸-۰۵

داشبورد کوانت و تحلیل بازار سرمایه ایران — رابط کاربری کامل برای بیش از ۸۰ مسیر (داشبورد، سیگنال، صف، بک‌تست، هوش مصنوعی، صندوق‌ها، اخبار، آپشن، کریپتو و...).

---

## 🏗️ استک فنی

| بخش | تکنولوژی |
|------|-----------|
| فریم‌ورک | **Next.js 16** (App Router، `output: "standalone"`) |
| زبان | **TypeScript 5** (strict) |
| رابط | **React 19** + Tailwind CSS 4 |
| داده کلاینت | **TanStack Query v5** (کش، refetch، polling) |
| نمودار | **lightweight-charts** + **recharts** |
| فرم‌ها/اعلان | **sonner** (toast) + **xlsx** (خروجی اکسل) |
| انیمیشن | **framer-motion** + آیکون‌های **lucide-react** |
| تست | **Vitest 4** + Testing Library (jsdom) — ۱۹ فایل / ۲۷۶ تست |
| پروکسی | Next.js rewrites → بک‌اند FastAPI (`api:8000`) |

---

## 🚀 اجرا

```bash
cd frontend
npm install
npm run dev          # توسعه (پورت 3000 — webpack)
npm run build        # بیلد production (خروجی standalone)
npm start            # اجرای بیلد
npm run lint         # ESLint
npm run test         # Vitest (همه تست‌ها)
npm run test:watch   # حالت watch
```

### محیط (`.env`)
```bash
# پروکسی سمت سرور → بک‌اند (هیچ‌وقت به مرورگر نشت نمی‌کند)
API_URL=http://localhost:8000

# سمت کلاینت (NEXT_PUBLIC_ — در bundle مرورگر قرار می‌گیرد)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# (اختیاری) نام cookie نشست — باید با AUTH_COOKIE_NAME بک‌اند یکی باشد
AUTH_COOKIE_NAME=im_refresh
```

> **نکته امنیتی:** از `API_URL` (بدون پیشوند `NEXT_PUBLIC_`) برای پروکسی استفاده کنید تا آدرس بک‌اند در مرورگر فاش نشود. متغیرهای `NEXT_PUBLIC_*` در bundle کلاینت قرار می‌گیرند.

### Docker
```bash
# از ریشه پروژه
docker compose up frontend
```
Dockerfile مخصوص: `Dockerfile.frontend` (multi-stage با خروجی standalone).

---

## 🗂️ ساختار

```
frontend/src/
├── app/                  # صفحات (App Router) — ۸۵ مسیر
│   ├── page.tsx          # داشبورد اصلی (شاخص، ارز، طلا، خبر، ...)
│   ├── layout.tsx        # ریشه: فونت Vazirmatn + تم + Providers
│   ├── providers.tsx     # AuthProvider + QueryClient + Toaster
│   ├── error.tsx         # Error Boundary عمومی
│   ├── global-error.tsx  # خطای ریشه (بدون layout)
│   ├── admin/            # پنل مدیریت (+ users/، error.tsx)
│   ├── auth/login|register/
│   ├── backtest/         # بک‌تست (engine, cascade, compose, decision, ...)
│   ├── signals/          # سیگنال‌ها (all, dashboard, stocks)
│   ├── symbol/[symbol]/  # صفحه جزئیات نماد
│   ├── funds/            # صندوق‌ها
│   ├── codal/            # کدال (analysis, accounting, audit, import)
│   ├── settings/         # تنظیمات
│   │   └── security/     # MFA (TOTP/ایمیل/تلگرام + QR)
│   ├── ml/               # آموزش/استنتاج مدل
│   ├── smart-money/      # پول هوشمند (+ monitor/، error.tsx)
│   └── ...               # ۸۰+ صفحه دیگر
├── components/           # کامپوننت‌های مشترک
│   ├── layout/           # AppLayout, Sidebar
│   ├── ui/               # Card, Button, Badge...
│   ├── charts/           # TradingViewChart, IndicatorChart
│   └── ...               # RoleGate, SSRSafe, ClientOnly, ErrorBoundary...
├── hooks/                # useWebSocket, useTheme, useClientData, useApiMonitor...
├── lib/                  # api.ts, auth-context.tsx, dates.ts, types.ts...
└── __tests__/            # ۱۹ فایل تست (Vitest + Testing Library)
```

---

## 🔐 احراز هویت (امن از XSS)

معماری دو-توکن با **refresh token فقط در httpOnly cookie**:

| مورد | محل ذخیره | نکته |
|------|-----------|------|
| **refresh token** | httpOnly cookie (`im_refresh` — توسط بک‌اند `Set-Cookie`) | قابل خواندن توسط جاوااسکریپت نیست |
| **access token** | حافظه ماژول (in-memory) در `lib/api.ts` | بعد از reload با `hydrateSession()` از cookie بازیابی می‌شود |
| **user profile** | حافظه ماژول | هیچ‌وقت در `localStorage` نوشته نمی‌شود |

- **`useAuth()`** — دسترسی به `user`, `login`, `register`, `logout`, `refreshAccessToken`, `hasRole/hasAnyRole` (سلسله‌مراتب: admin > analyst > user > viewer).
- **Silent refresh** — همه متدهای `apiGet/apiPost/apiPut/apiDelete` در 401 ابتدا `POST /auth/refresh` (با deduplication درخواست‌های هم‌زمان) را امتحان می‌کنند؛ در شکست → ریدایرکت به `/auth/login?redirect=...`.
- **MFA** — صفحه `/settings/security`: انتخاب روش (TOTP با QR / ایمیل / تلگرام)، جریان enable → confirm → disable.
- **route-guard (middleware)** — مسیرهای `/admin`, `/settings/security`, `/profile`, `/watchlist` بدون cookie به لاگین ریدایرکت می‌شوند (307 با حفظ مسیر و کوئری). مرز امنیتی واقعی بک‌اند است؛ middleware فقط لایه UX + defense-in-depth است.
- **timeout** — درخواست عادی ۶۰ ثانیه، عملیات سنگین (sync) ۱۰ دقیقه (`AbortController`).

---

## 🛡️ Middleware (`src/middleware.ts`)

- **هدرهای امنیتی روی همه پاسخ‌ها:** `X-Frame-Options: SAMEORIGIN`، `X-Content-Type-Options: nosniff`، `Referrer-Policy`، `X-DNS-Prefetch-Control`.
- **Route guard:** تشخیص نشست با حضور cookie بازخوانی (نام از `AUTH_COOKIE_NAME`، پیش‌فرض `im_refresh`).
- **Matcher:** استاتیک‌های Next و assetهای عمومی از پردازش مستثنا هستند؛ بقیه مسیرها هدر می‌گیرند.

---

## 🔌 ارتباط با بک‌اند

```
مرورگر → /api/v1/* (Next.js) → rewrites → FastAPI (api:8000)
```

- `next.config.ts` — `rewrites()` همه درخواست‌های `/api/v1/:path*` را به بک‌اند پروکسی می‌کند.
- `output: "standalone"` — آماده Docker multi-stage.
- **WebSocket** — `useWebSocket` با reconnect خودکار، ping/keep-alive و ref نگه‌داشتن handlerها بدون بازسازی اتصال.
- **پاسخ‌های API** — `extractArray()` / `extractItems()` / `extractTotal()` پاسخ‌های متنوع بک‌اند (list/data/items/...) را نرمال می‌کنند.

---

## 🧪 تست‌ها (۱۹ فایل — ۲۷۶ تست)

| فایل | پوشش |
|------|-------|
| `middleware.test.ts` | route-guard (۱۵ تست)، هدرهای امنیتی، ریدایرکت‌ها |
| `silent-refresh.test.ts` | refresh توکن (cookie-only)، dedup، 401، بدون ذخیره در حافظه |
| `auth-context.test.tsx` | hydration، login/logout، نقش‌ها، refresh |
| `fund-analysis.test.ts` | تحلیل صندوق، NAV، مقایسه |
| `compareReport.test.ts` | مقایسه ریپورت بک‌تست (با escape مقادیر) |
| `BacktestComponents.test.tsx` / `DashboardPage.test.tsx` | رندر صفحات کلیدی |
| `MarketIndices`, `MultiEquityChart`, `SyncStatus`, `MiniSparkline` | کامپوننت‌های UI |
| `useApiMonitor`, `useClientData`, `useDebugLogs`, `useSymbolPrices`, `useTheme` | هوک‌ها |
| `SSRSafe`, `AppLayout` | لایه‌های عمومی |

```bash
npm run test        # اجرای همه تست‌ها
npx vitest run src/__tests__/middleware.test.ts   # تست خاص
npx tsc --noEmit    # تایپ‌چک
```

پیکربندی: `vitest.config.ts` (jsdom + globals + alias `@` → `src`) و `src/__tests__/setup.ts`.

---

## 🎨 طراحی

- **RTL کامل** (`dir="rtl"`) با فونت **Vazirmatn** (نسخه web با `next/font`).
- **تم تاریک/روشن** — اسکریپت hydration قبل از رندر برای جلوگیری از FOUC + `useTheme` (ذخیره در localStorage — فقط تنظیم تم، نه داده حساس).
- **سیستم رنگی `surface`/`accent`** — انسجام بصری در همه صفحات.
- **کامپوننت‌های SSR-Safe** (`SSRSafe`, `ClientOnly`, `useClientData`) برای جلوگیری از hydration mismatch.
- **PWA** — `public/manifest.json` + `public/sw.js` + آیکون‌ها.
- **Error Boundaries** — `error.tsx` در مسیرهای اصلی (admin, backtest, codal, ml, options, smart-money) + `global-error.tsx`.

---

## 📜 نکات توسعه

- تمام درخواست‌ها باید از `lib/api.ts` (با `credentials: "include"`) عبور کنند؛ `fetch` خام فقط برای auth (login/register/refresh) در auth-context مجاز است.
- از `any` پرهیز کنید؛ پاسخ‌های API را با interface در `lib/types.ts` تایپ کنید.
- برای داده‌های سمت سرور از TanStack Query استفاده کنید (نه useEffect).
- کامپوننت‌های سنگین (نمودارها) را با `next/dynamic` lazy-load کنید.
