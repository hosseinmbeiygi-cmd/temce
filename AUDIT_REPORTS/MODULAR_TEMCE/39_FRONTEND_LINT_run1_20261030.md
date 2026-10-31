# ۳۹ — AUD-FE-01: کاهش هشدارهای ESLint — run1، ۳۰ اکتبر ۲۰۲۶

**AUD-FE-01:** **PARTIAL** — هشدارها از ۱۶۹ به **۱۳۷** کاهش یافت (۰ خطا)؛
۲۹ هشدار `exhaustive-deps` عمداً ساکت نشد و ۱۰۰ متغیر بی‌استفادهٔ واقعی باقی است.
تغییرات commit نشده‌اند.

---

## ۱) تغییر config

در `frontend/eslint.config.mjs` برای `@typescript-eslint/no-unused-vars` الگوهای
زیر فعال شد:

```
argsIgnorePattern: "^_"
varsIgnorePattern: "^_"
caughtErrorsIgnorePattern: "^_"
destructuredArrayIgnorePattern: "^_"
ignoreRestSiblings: true
```

این کار پارامترهای mock عمداً بی‌استفاده (`_url`, `_token`, `_signal`) را از هشدار خارج
می‌کند بدون خاموش‌کردن قاعده برای متغیرهای واقعی.

## ۲) `eslint --fix`

`npx eslint src --fix` فقط ۲۳ دایرکتیو `eslint-disable` بی‌استفاده را از **۱۶ فایل**
حذف کرد (کامنت‌محور، بدون تغییر رفتار). فایل‌ها: `swHarness.ts`، `backtest/page.tsx`،
`brsapi/history/[symbol]/page.tsx`، `indicators/page.tsx`، `multi-market-signals/page.tsx`،
`news/page.tsx`، `settings/security/page.tsx`، `DecisionSubmitter.tsx`،
`SymbolQueueModal.tsx`، و ۷ هوک (`useApiMonitor`, `useBackgroundBackfill`, `useClientData`,
`useMounted`, `useNotificationSound`, `useSyncSettings`, `useTheme`).

> ⚠️ شفافیت درخت مشترک: `indicators/page.tsx` در بازهٔ جلسه توسط ویرایشگر هم‌زمان هم
> تغییر کرده بود؛ تغییر ما فقط حذف یک کامنت `eslint-disable` بی‌استفاده است.

## ۳) نتیجه

| شاخص | قبل | بعد |
|---|---|---|
| کل هشدارها | ۱۶۹ | **۱۳۷** |
| خطا | ۰ | **۰** |
| `no-unused-vars` | ۱۰۹ | ۱۰۰ |
| دایرکتیو disable بی‌استفاده | ۲۳ | **۰** |
| `react-hooks/exhaustive-deps` | ۲۹ | ۲۹ (عمداً دست‌نخورده) |
| `@next/next/no-img-element` | ۸ | ۸ (تصمیم طراحی) |

بیشترین هشدارهای باقی‌مانده: `admin/page.tsx` (۹)، `news/page.tsx` (۶)،
`multi-market-signals/page.tsx` (۵)، `recommendations/page.tsx` (۵).

## ۴) تست‌ها

| اجرا | نتیجه |
|---|---|
| `npx tsc --noEmit` | exit 0 |
| `npx vitest run` | **۶۷ فایل / ۵۸۶ تست پاس**، exit 0 (۱۶۲ ثانیه) |

## ۵) چرا exhaustive-deps ساکت نشد

۲۹ هشدار `react-hooks/exhaustive-deps` می‌توانند نشانهٔ dependency ناقص در effect و
stale-closure باشند؛ خاموش‌کردنشان آدیت را ضعیف می‌کند. نیازمند بررسی موردی است
(اسلایس جدا).

## ۶) وضعیت

| مورد | وضعیت |
|---|---|
| هشدارها | **PARTIAL** (۱۶۹ → ۱۳۷) |
| خطای ESLint | **PASS** (۰) |
| tsc / vitest | **PASS** |
| commit | **BLOCKED** (درخت مشترک) |
