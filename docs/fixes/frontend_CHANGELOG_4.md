# Frontend CHANGELOG 4 — پورتفوی گروهی، as_of، OOS، null-safety و تب صندوق‌ها

شاخه: `integration/golddesk-fixes` — HEAD زمان شروع: `c18b616b`
بک‌اند مرجع (فقط‌خواندنی): commit `731de301`

## خلاصهٔ وضعیت

| کار | وضعیت | فایل‌ها | تست |
|---|---|---|---|
| ۱) حذف دارایی گروه‌شده (holding_ids) | fixed | `app/gold/portfolio/page.tsx` | `__tests__/GoldPortfolioSafety.test.tsx` (۴ تست حذف) |
| ۲) ثبت معامله با holding_id تازه | fixed | `app/gold/portfolio/page.tsx` | `__tests__/GoldPortfolioSafety.test.tsx` (۴ تست فروش) |
| ۳) کهنگی از `as_of` (hot ۲۰s / snapshot ۶۰۰s) | fixed | `lib/goldApi.ts`، `hooks/useGoldWS.ts` | `__tests__/GoldWebSocket.test.tsx` (۵ تست as_of) |
| ۴) جدول OOS کنار کل دوره | fixed | `app/gold/backtest/page.tsx` | `__tests__/GoldBacktestPage.test.tsx`، `GoldApiLayer.test.ts` |
| ۵) null-safety اعداد پورتفو | fixed | `app/gold/portfolio/page.tsx` | `__tests__/GoldPortfolioSafety.test.tsx` (۲ تست) |
| اضافه: تب مستقل «صندوق‌های طلا» | fixed | `app/gold/funds/page.tsx`، `app/gold/layout.tsx` | `__tests__/GoldFundsPage.test.tsx` + به‌روزرسانی تست layout |

## ۱) حذف دارایی گروه‌شده

`Holding` حالا `id` (فقط گروه تک‌ردیفی) و `holding_ids` (همیشه) را می‌خواند.
- دکمهٔ حذف برای گروه چندردیفی هم دیده می‌شود (قبلاً فقط `h.id` چک می‌شد).
- دیالوگ برای گروه می‌گوید: «این نماد N ردیف دارد؛ همه حذف نرم می‌شوند و معاملات حفظ می‌شوند.»
- هر id **پشت‌سرهم** `DELETE /gold/portfolio/holdings/{id}` می‌شود؛ `force` هرگز از UI نمی‌آید.
- 409 → «قبلاً حذف شده» و ادامهٔ بقیهٔ idها؛ 404 → «دارایی پیدا نشد…»؛ خطای شبکه →
  «ارتباط با سرور برقرار نشد…». در همهٔ حالت‌ها پورتفو refetch می‌شود.

## ۲) ثبت معامله (فرم فروش)

هیچ فرم ثبت معامله‌ای در فرانت نبود؛ یک فرم کوچک «فروش» برای ردیف‌های تک‌id اضافه شد.
- `holding_id` فقط از همان ردیفِ پاسخ فعلی `/portfolio` گرفته می‌شود و **قبل از ارسال**
  دوباره در `holding_ids` پاسخ تازه جست‌وجو می‌شود؛ اگر id عوض شده باشد، درخواستی ارسال
  نمی‌شود و پیام «لیست پورتفو تغییر کرده است» می‌آید.
- ارسال به `POST /gold/portfolio/trades` با `action: "sell"`، `quantity`، `price`،
  `amount_irt` و `holding_id`؛ `force` در بدنه نیست.
- 404/409 پیام خوانا + refetch پورتفو؛ خطای شبکه پیام روشن.
- بعد از موفقیت، پورتفو/پلن‌ها/تاریخچه refetch می‌شوند.

## ۳) کهنگی بر پایهٔ `as_of`

`goldApi.ts`:
- `parseAsOf()` فقط ISO 8601 واقعی را می‌پذیرد (رشته‌های مبهم مثل `"12"` رد می‌شوند).
- `GoldWSInfo` سه فیلد تازه دارد: `lastAsOfAt`، `lastHotAsOfAt`، `lastSnapshotAsOfAt`.
- در هر فریم، زمان داده = `as_of` معتبر، وگرنه زمان رسیدن (fallback). مقدارها با
  `Math.max` نگه داشته می‌شوند تا فریم قدیمی کهنگی را عقب نبرد.

`useGoldWS.ts`:
- `ageSeconds` از `lastAsOfAt ?? lastMessageAt` محاسبه می‌شود، نه فقط زمان رسیدن.
- اگر hot داریم: آستانه `2 × 10s = 20s`؛ اگر فقط snapshot: `2 × 300s = 600s`.
- `as_of` نامعتبر/غایب کرش نمی‌کند و به زمان رسیدن برمی‌گردد.

## ۴) بک‌تست OOS

- حضور پنج فیلد با `!== undefined` تشخیص داده می‌شود (حاضر و null ≠ غایب).
- جدول دو ستونه «کل دوره» / «OOS» برای بازده DCA، Buy & Hold، آلفا و Max Drawdown؛
  `oos_start` هم در سربرگ/ردیف نشان داده می‌شود.
- مقدار null/NaN → «نامشخص»، نه صفر.
- نبود کامل فیلدها → همان پیام صادقانهٔ قبلی (بدون ادعای عدد).
- مسیر endpoint در `goldApi.ts` همان `/gold/backtest/strategy` است و با تست
  `GoldApiLayer.test.ts` (query شامل days/bubble_trigger/initial_capital) قفل شد.

## ۵) null-safety

- `pnl_pct`، `current_value`، `pnl_irt` و `priced_cost` خالی «—» رندر می‌شوند.
- `priced_cost === null` در کارت P&L به «سرمایهٔ قیمت‌دار: —» تبدیل می‌شود.
- جمع‌ها از سرور می‌آیند و دوباره‌شماری سمت کلاینت وجود ندارد؛ تست با یک دارایی
  بی‌قیمت نشان می‌دهد total سرور (۲۰٬۰۰۰٬۰۰۰) حفظ می‌شود و NaN/صفر جعلی نمی‌آید.

## اضافه) تب «صندوق‌های طلا»

- بررسی Postgres: جدول `gold_fund_nav` موجود است؛ **۱۰ ردیف / ۱۰ نماد** برابر با
  `FUND_SYMBOLS` (`عیار، طلا، کهربا، زر، زرفام، گوهر، تابش، نفیس، آلتون، ناب`)؛
  آخرین تاریخ ذخیره `2026-10-14`.
- `/gold/funds` از redirect به یک صفحهٔ واقعی تبدیل شد و **همهٔ** `snapshot.funds`
  را با جدول مشترک `FundNAVTable` نشان می‌دهد (نه top-N).
- تب «صندوق‌های طلا» به نوار دسکتاپ/دراور اضافه شد (نوار پایین موبایل همان ۵ مقصد
  اصلی می‌ماند). تست layout از ۱۵ به ۱۶ لینک دسکتاپ به‌روز شد.

## قرمزی قبل از رفع (ثبت‌شده)

پیش از پیاده‌سازی، تست‌های جدید اجرا شدند:

```text
Test Files  3 failed | 1 passed (4)
     Tests  16 failed | 18 passed (34)
```

نمونهٔ واقعی شکست (پیش از افزودن `lastAsOfAt`):

```text
FAIL GoldWebSocket.test.tsx > useGoldWS staleness from as_of >
  exposes the parsed as_of on the manager's info
AssertionError: expected undefined to be 1792940846525
```

تست‌های حذف گروهی/فروش هم fail شدند چون دکمه/فرم مربوطه در UI وجود نداشت، و
تست جدول OOS چون صفحه هنوز جدولی رندر نمی‌کرد.

## تأیید نهایی (عیناً)

```text
$ cd frontend && npx tsc --noEmit
(بدون خروجی — بدون خطا)

$ npx vitest run
Test Files  52 passed (52)
     Tests  558 passed (558)
```

- حداقل ۵۳۸ تست خواسته‌شده برآورده شد (۵۵۸).
- هیچ وابستگی جدیدی اضافه نشد؛ `package.json` تغییر نکرد.

## سؤالات باز

1. `gold_fund_nav` آخرین ردیفش `2026-10-14` است؛ اگر job شبانه اجرا نشود، صفحهٔ
   صندوق‌ها همان snapshot قدیمی را نشان می‌دهد. آیا endpoint تاریخچه/آخرین ردیف DB
   لازم است؟ (نیازمند تغییر بک‌اند.)
2. `/gold/etf` و `/gold/funds` هم‌پوشانی دارند؛ فعلاً هر دو حفظ شدند.
3. علامت `oos_max_drawdown_pct` در قرارداد صریح نیست؛ UI مثل کل دوره با `-` نمایش
   می‌دهد. اگر بک‌اند مقدار منفی بدهد، دوباره منفی می‌شود.
4. تب صندوق‌ها فقط در نوار دسکتاپ/دراور است؛ نوار پایین موبایل عمداً ۵ مقصد دارد.
