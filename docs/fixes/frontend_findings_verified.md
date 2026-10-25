# گام ۰ — تأیید یافته‌های گزارش فرانت (GoldDesk)

نویسنده: دستیار ۳ (Senior Frontend Engineer + DevOps) — branch: `fix/frontend-infra`
تاریخ: ۲۰۲۶-۱۰-۲۴

این فایل **فقط واقعیتِ خوانده‌شده از کد** را ثبت می‌کند. جایی که گزارش ممیزی با کد
نمی‌خواند، رقم/واقعِ کد آمده و در CHANGELOG با وضعیت مربوطه ثبت می‌شود (قاعده ۶).
`docs/analysis/` فقط‌خواندنی است و در این دستیار تغییر نمی‌کند.

---

## ۱) F1 — تعریف‌نشده بودن متغیرهای تم: **تأیید شد (P0، واقعی‌ترین ایراد این محدوده)**

دستور و خروجی واقعی:

```
$ grep -rn -- "--gd-" frontend/src/app/globals.css        → (خالی، exit 0)
$ grep -rn "var(--gd-" frontend/src/app/gold frontend/src/components/gold | wc -l
170
```

- `--gd-*` در `globals.css` (۲۰۱۴ خط) **هیچ تعریفی ندارد**.
- ۱۷۰ مصرف `var(--gd-*)` در درخت gold وجود دارد، از جمله در جاهای بنیادی:
  - `frontend/src/app/gold/layout.tsx:59` — `style={{ background: "var(--gd-bg)" }}` برای کل صفحه
  - `layout.tsx:61` — `background: var(--gd-bg-2)` و `borderColor: var(--gd-border)` برای هدر
  - `layout.tsx:127`، `layout.tsx:179` — درِ موبایل و نوار پایین
- نتیجهٔ بالینی: `var()` بدون fallback مقدار نامعتبر است، پس این declare‌ها نادیده گرفته
  می‌شوند و پس‌زمینه/حاشیه **شفاف** می‌ماند؛ متن روی `text-zinc-100` در حالت روشن
  عملاً ناخواناست. یعنی تم‌های light/gold نه‌تنها استایل نمی‌گیرند، بلکه کنتراست را می‌شکنند.
- `ThemeProvider.tsx:31` فقط `document.documentElement.setAttribute("data-theme", theme)`
  را ست می‌کند و هیچ متغیری تولید نمی‌کند → تأیید می‌کند که تعریف‌ها **باید** زیر
  `[data-theme="..."]` در CSS بنویسند (نه در JS).

منبع بازیابی: بلاک تم در درخت مرجع وجود دارد و دقیقاً در بازهٔ اعلام‌شده است:

```
.freebuff/worktrees/72c673be-.../_FRONTEND_BACKEND_COPY/frontend/src/app/globals.css:1805-1866
```

شامل هر سه بلوک `:root,[data-theme="dark"]` / `[data-theme="light"]` / `[data-theme="gold"]`
با هر ۱۲ توکن خواسته‌شده (`gd-bg, gd-bg-2, gd-bg-3, gd-border, gd-text, gd-text-2,
gd-text-3, gd-accent, gd-accent-2, gd-success, gd-warn, gd-danger`) + دو قانون کمکی
`html[data-theme="gold"] body` و `[data-theme="gold"] body::before`.

> نکتهٔ واقعی که گزارش نگفته: در تم `gold` مقدار `--gd-bg` یک **gradient** است
> (`linear-gradient(...)`), نه یک رنگ. پس `background: var(--gd-bg)` درست است
> (shorthand) ولی هر جا `color: var(--gd-bg)` یا `borderColor: var(--gd-bg)` استفاده
> شود میشکد. مصرف‌های پرخطر در F1 با تست پوشش داده می‌شوند.

## ۲) F2 — حالت خطای ۵۰۳: **مشکل واقعی است، ولی شکلش با گزارش فرق دارد**

گزارش/C3 فرض می‌کند `/snapshot` و `/score` با ۵۰۳ پاسخ می‌دهند. در کدِ امروز:

- `src/gold_desk/api.py:95-103` (`/snapshot`) و `:109-116` (`/score`) در خطا **HTTP 200**
  با بدنهٔ `{"success": false, "data": null, "error": {"message": str(exc)}}` برمی‌گردانند —
  نه ۵۰۳، نه `snapshot_unavailable`. یعنی C3 هنوز سمت بک‌اند پیاده نشده (دستیار ۲).
- پیام خطای داخلی (`str(exc)`) هم روی سیم بیرون می‌زند، دقیقاً چیزی که C3 ممنوع می‌کند.
- خسارت سمت فرانت: `goldApi.ts:39-42` مقدار `r.data` را برمی‌گرداند؛ وقتی `data` تهی باشد
  `undefined` برمی‌گردد و React Query آن را رد می‌کند («Query data cannot be undefined»).
  پس صفحه یا کرش می‌کند یا «خطای مبهم» — همان چیزی که F2 می‌گوید.
- `isServiceUnavailable` (`goldApi.ts:32-35`) روی regex `\b503\b` در **پیام** می‌نویسد؛
  با پاسخ ۲۰۰ِ امروز هرگز true نمی‌شود.
- `/gold/signals/recent`: `LiveSignalBanner.tsx:55-64` خطا را کاملاً دور می‌ریزد
  (`const { data } = useQuery` بدون `isError`) → کاربر هیچ‌وقت نمی‌فهمد سرویس خوابیده.

جمع‌بندی برای پیاده‌سازی: فرانت باید **هر دو** شکل را بپذیرد (۵۰۳ِ فردا و ۲۰۰ِ با
`success:false`ِ امروز) تا merge سه‌طرفه اتمیک باشد و در فاصلهٔ merge هم اپ نشکند.

## ۳) F3 — `NO_DATA` و پوشش داده: **صددرصد، و بدتر از گزارش**

- `types/gold.ts:4` → `Decision = "GREEN" | "YELLOW" | "RED"`؛ هیچ عضو `NO_DATA` نیست.
- `types/gold.ts:70-76` (`ScoreBlock`) هیچ‌کدام از `raw_total` / `available_weight` /
  `data_coverage_pct` را ندارد (C1).
- سه مسیر رندر decision و دو تا کرش می‌کنند، یکی **بدترین حالت ممکن** را می‌سازد:
  - `components/gold/ScoreGauge.tsx:11-16` → `colorMap[score.decision]` بدون fallback،
    سپس `:22` دسترسی به `c.text` → **TypeError** با مقدار ناشناخته.
  - `app/gold/coins/page.tsx:193-201` (`DecisionBadge`) → همین الگو، `m.cls` → **TypeError**.
  - `app/gold/analytics/page.tsx:119` → ternary سه‌تایی که هر مقدار ناشناخته را به رنگ
    **قرمز** می‌اندازد. یعنی `NO_DATA` دقیقاً مثل «فروش/توقف قرمز» دیده می‌شود —
    همان چیزی که F3 صراحتاً ممنوع می‌کند. این تنها mis-classify بی‌صداست.
  - `app/gold/components/SummarySection.tsx:68` تنها جای امن است (fallback خاکستری)،
    ولی `:71` متن خام enum را چاپ می‌کند.
- هشدار «ابزار تحلیلی، نه توصیهٔ مالی»: در کل `/gold/**` **صفر بار** وجود دارد.
  تنها متن موجود در `lib/gold-silver-spec.ts:601` است و تنها رندر آن
  `components/gold/SpecRulesCard.tsx:294` است که فقط در `/markets/gold` و `/markets/silver`
  استفاده می‌شود (`app/markets/gold/page.tsx:35`)، نه در GoldDesk.

## ۴) C2 (حباب nullable): **تقریباً انجام‌شده؛ دو باگ واقعی باقی است**

- `types/gold.ts:25-26` و `:37` همین حالا `number | null` هستند → خواستهٔ C2 در تایپِ
  فرانت برآورده است (گزارش انگار این را ندیده).
- ولی دو جای خطرناک:
  - `app/gold/analytics/page.tsx:175` → `value: p.bubble_pct ?? 0` و سپس `:189`
    `.value.toFixed(2)` → «دادهٔ گم‌شده» به شکل **«۰٫۰۰٪»** نمایش داده می‌شود؛ صفرِ جعلی
    در نمودار حباب. این دقیقاً همان «صامت‌صفر» است که C2 می‌خواهد جلوگیری کند.
  - `components/gold/CoinBubbleTable.tsx:53` → `c.implied_usd ? … : "—"` مقدار **۰ واقعی**
    را «گم‌شده» می‌شمارد (truthiness به‌جای null-check).
  - تایپ `goldApi.ts:489-509` (`postCoinBubble`) هنوز `bubble_pct: number` غیرnullable دارد.

## ۵) F4 — پاکت‌ها و `current_score`: **سه‌قطع واقعیت**

- `POST /dca/plan`: `api.py:199` با `response_model=DCAResponse` پاسخ **برهنه** می‌دهد
  (بدون `success`/`data`). فرانت در `goldApi.ts:340-342` `r.data` را می‌خواند → همیشه
  `undefined`. یعنی ماشین‌حساب DCA امروز عملاً از این مسیر خراب است. C5 هنوز پیاده نشده.
- `POST /telegram/test`: `api.py:378` امضاش `chat_id: str | None = None` است → FastAPI آن را
  **query** می‌خواند، نه body. فرانت (`goldApi.ts:124`) chat_id را در **body** می‌فرستد.
  نتیجه: chat_id فرستاده‌شده نادیده گرفته می‌شود و تست همیشه به چت‌پیش‌فرض می‌رود.
  خواستهٔ C5 («از بدنه هم بپذیرد») سمت بک‌اند است — دستیار ۲.
- `current_score`: `schemas.py:116` → `current_score: int = Field(..., ge=0, le=100)`
  **اجباری** است. اگر فرانت همان‌طور که C4 می‌گوید ارسالش را حذف کند، امروز 422 می‌گیریم.
  پس حذف از فرانت فقط هم‌زمان با optional‌کردن سمت بک‌اند قابل ادغام است (در CHANGELOG
  و handoff صریح ذکر می‌شود). فرستنده‌های امروزی: `goldApi.ts:337`،
  `components/gold/DCACalculator.tsx:20`، `app/gold/portfolio/page.tsx:40,67,419`.

## ۶) F5 — حذف دارایی: **گزارش را نمی‌خواند؛ واقعیت کد این است**

- در فرانت **هیچ حذف دارایی (holding) وجود ندارد**. جدول هولدینگ‌ها
  (`app/gold/portfolio/page.tsx:182-195`) فقط‌خواندنی است و `AddHoldingTab` تنها POST
  می‌کند (`:367`). تنها `apiDelete` این صفحه برای **پلن DCA** است:
  `portfolio/page.tsx:432-436` → `if (!confirm("حذف شود؟")) return;` — تأیید بومی مرورگر،
  بدون نام پلن، بدون هیچ اشاره‌ای به معامله‌ها.
- سمت بک‌اند برعکس، **همین حالا C7 را پیاده کرده است**: `api.py:963-989`
  `DELETE /portfolio/holdings/{holding_id}` با پیش‌فرض soft-delete (`deleted_at`) و
  `?force=true` برای حذف سخت، و مستند می‌کند که FK با `ondelete="SET NULL"`
  (`models.py:186`) گزارش مالیاتی را نمی‌شکند.
- پس کاری که اینجا انجام می‌شود: ساخت affordance حذف دارایی روی همان endpoint موجود +
  دیالوگ تأیید صریح با متن اثر روی معامله‌ها، و نه ساختن چیزی که وجود ندارد.
- `pnl_pct`: رابط `portfolio/page.tsx:17,25` آن را **غیرnullable** اعلام می‌کند و
  `:156`/`:192` مستقیم `.toFixed()` می‌گیرند → با nullِ واقعی (C7) TypeError.

## ۷) F6 / C10 — WebSocket: **گزارش بدترین بخش را جا انداخته**

- `src/gold_desk/ws_hub.py:71-87`: `ws_endpoint` بعد از accept فقط یک `while True:
  receive_text()` می‌چرخد و به `ping` پاسخ `pong` می‌دهد. **هیچ حلقهٔ push ندارد.**
  تنها پیام‌هایی که client می‌گیرد: (الف) یک `{"type":"snapshot"}` در `register` از
  کش (`ws_hub.py:31-33`) و (ب) `{"type":"signal"}` از `live_signals.py:188`.
- docstring‌ها (`ws_hub.py:3` و `api.py:693`) می‌گویند «هر ۵ ثانیه push» — ولی آن کد وجود ندارد.
  یعنی C10 (hot هر ۱۰ ثانیه / snapshot هر ۳۰۰ ثانیه) نه‌تنها پیاده نشده، ادعای ۵ ثانیه هم
  با واقعیت نمی‌خواند. زمان‌بندی، وظیفهٔ دستیار ۲ (`src/`).
- فرانت امروز: `goldApi.ts:204-214` تنها `type === "snapshot"` را می‌فهمد؛ `hot` و
  `signal` دور ریخته می‌شوند.
- `layout.tsx:42` → `setTimeout(() => setWsActive(false), 3000)` **بدون توجه به وضعیت
  واقعی سوکت**، نشانگر «Live» را سه ثانیه بعد خاموش می‌کند. با توجه به (ب) این تصادفاً
  نزدیک واقعیت است، ولی منطق غلط است: نشانگر باید از خودِ سوکت و از تازگی پیام بیاید.
- polling: **هیچ** `refetchInterval`ی در درخت gold با وضعیت WS گیت نشده (۲۰+ مورد،
  از `futures/page.tsx:65` با ۵۰۰۰ms تا `gold/page.tsx:19` با ۶۰۰۰۰ms). خواستهٔ F6
  («polling فقط وقتی WS قطع است») امروز برقرار نیست.
- `subscribeGoldWS` مصرف‌کنندهٔ واقعی ندارد برای داده: `LiveSignalBanner.tsx:72-79`
  هر دو callback را خالی گذاشته، `coins/page.tsx:220-225` فقط refetch می‌زند.

## ۸) F8 — تکرار و تب‌ها

- `components/gold/CoinBubbleTable.tsx` **توسط هیچ فایلی import نمی‌شود** (grep کامل).
  نسخهٔ فعال: `app/gold/components/CoinBubbleTable.tsx` که `app/gold/page.tsx:6` آن را
  می‌آورد. امضاهای props دوتا یکی نیست (`data` در برابر `coins`) → واگرایی واقعی.
- تنهاییِ بیشتر: `ScoreGauge`، `ScoreBreakdown`، `FundNAVTable`، `ParityBadge`،
  `BubbleGauge`، `DCACalculator`، `GoldKPICard`، `TimeSeriesChart`، `RSIIndicator`
  هیچ‌کدام از هیچ‌جای `src/` import نمی‌شوند (کد مردهٔ compose‌شده).
- `ParityBadge.tsx:18` → `label = "کمی偏离"` — دو کاراکتر چینی (`偏离`) وسط متن فارسی.
- **تعداد تب: ۱۵، نه ۱۳** (`layout.tsx:14-30`، خطوط ۱۵ تا ۲۹). نوار پایین موبایل
  (`layout.tsx:180-196`) هر ۱۵ را در `grid-cols-5` می‌ریزد → ۳ سطر ~۱۳۰px ارتفاع،
  همان‌طور که کامنت `layout.tsx:170-172` خودش اعتراف می‌کند و با `pb-[130px]`
  و `pb-24` **هم‌زمان** جبران شده (`:173` — دو padding در یک class، آخری برنده است).
- `tokens/page.tsx:16,22,31` → `fetch` خام بدون import از `@/lib/api`. مسیرها prefix
  `/api/v1` ندارند (`api.ts:1`)، هدر Authorization نمی‌رود و مسیر refresh/۴۰۱ دور زده
  می‌شود → عملاً در production نمی‌توانند کار کنند.

## ۹) F9 / I1 / I2 / I3 — زیرساخت

- `frontend/public/golddesk-sw.js`: `networkFirst` هر پاسخ OK روی `/api/` را **بدون TTL**
  در `RUNTIME_CACHE` می‌گذارد و در قطعی شبکه همان کش را بی‌قیدوشرط برمی‌گرداند →
  دادهٔ مالی کهنه سرو می‌شود (مخالف F9). `CACHE_NAME` (خط ۲) تعریف و هرگز استفاده نمی‌شود.
  `skipWaiting`/`clients.claim` از قبل هست (خطوط ۲۶، ۴۰) — برخلاف فرض گزارش.
  استراتژی روی `/api/` عمومی است نه `/api/v1/gold/*`.
- `nginx-golddesk.conf`: مسیرها `/api/gold/` و `/api/gold/ws` هستند، درحالی‌که پایهٔ واقعی
  API `/api/v1/gold` است → این location‌ها با آدرس واقعی اپ **مچ نمی‌کنند**.
  هیچ `log_format`/`access_log` تعریف‌شده‌ای نیست → لاگ پیش‌فرض کل request-line را
  می‌نویسد، یعنی `?token=<JWT>` در log دیسک می‌نشیند (I1). `X-Forwarded-Proto` روی
  `/gold/` نیست؛ روی `/api/gold/` هم `proxy_http_version 1.1` برای upgrade ندارد.
- `docker-compose.yml` / `monitoring/golddesk-prometheus.yml` / healthcheck: بررسی در
  بخش I انجام و در CHANGELOG ثبت می‌شود.

## ۱۰) وضعیت تست فرانت

- زیرساخت تست سالم است: `vitest 4.1.9` + `@testing-library/react 16.3.2` + `jsdom 29`،
  `frontend/vitest.config.ts` با environment jsdom و setup.
- `frontend/src/__tests__/` **۳۹ فایل** دارد (نه ۳)؛ ولی ادعای «۳ فایل» احتمالاً مخصوصِ
  تست‌های GoldDesk است. الگوی قابل‌استفادهٔ موجود: `GoldCommandCenter.test.tsx`
  (partial mock `@/lib/goldApi` + QueryClientProvider).
- خط مبنای اجرا (قبل از هر تغییر من):
  `npx vitest run src/__tests__/GoldCommandCenter.test.tsx` → **۸/۸ pass**.

---

## نتیجهٔ گام ۰

| شناسه | تأیید؟ | تفاوت اصلی با گزارش |
|---|---|---|
| F1 | ✅ واقعی و بحرانی | گرادیان بودن `--gd-bg` در تم gold؛ شکستن کنتراست نه فقط «بی‌رنگی» |
| F2 | ✅ واقعی | امروز ۵۰۳ نمی‌آید؛ پاسخ ۲۰۰ با `success:false` و نشت پیام خطای داخلی |
| F3 | ✅ واقعی | `analytics/page.tsx:119` مقدار ناشناخته را **قرمز** می‌کند؛ دو رندر با مقدار ناشناخته کرش می‌کنند |
| F4 | ✅ واقعی | `/dca/plan` پاکت ندارد → `undefined`؛ `current_score` اجباری است (schema:116) |
| F5 | ⚠️ نمی‌خواند | حذف holding در فرانت وجود ندارد؛ بک‌اند C7 را از قبل پیاده کرده |
| F6 | ✅ واقعی‌تر از گزارش | `ws_hub` هیچ حلقهٔ push ندارد؛ ادعای «هر ۵ ثانیه» در docstring توخالی است |
| F8 | ✅ | تب‌ها ۱۵ هستند نه ۱۳؛ ۹ کامپوننتِ gold کد مرده‌اند |
| F9 | ✅ | `skipWaiting`/`claim` از قبل هست؛ نبود TTL مشکل اصلی است |
| I1 | ✅ | مسیر nginx با `/api/v1/gold` مچ نمی‌کند (فراتر از ماسک لاگ) |
