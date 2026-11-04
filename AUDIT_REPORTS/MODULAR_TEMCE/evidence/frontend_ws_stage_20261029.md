# مرحلهٔ ۶ — فرانت/WebSocket: شاهد اجرا (۲۹ اکتبر ۲۰۲۶)

دامنه: FE-06 (توکن دسترسی در query string وب‌سوکت) و چهار endpoint بدون timestamp منبع
(`flow-history`, `economic-calendar`, `value-history`, `ownership-history`).

## ۱) FE-06 — بلیت یک‌بارمصرف handshake

**قبل:** `useWebSocket.ts` و `goldApi.ts` توکن دسترسی را در `?token=` می‌گذاشتند؛
`verify_websocket_token` هم همان را می‌خواند. توکن بلندعمر در access log، log پروکسی،
history مرورگر و ابزارهای ضبط URL دیده می‌شد.

**بعد:**
- `core/security/tokens.py::create_ws_ticket` — توکن تصادفی ۳۲ بایتی (`secrets.token_urlsafe`)،
  ذخیره با کلید `auth:ws_ticket:<sha256(ticket)>`، TTL=۶۰s. مقدار خام هرگز در Redis نیست.
- `consume_ws_ticket` با `GETDEL` → دقیقاً یک‌بار قابل استفاده.
- `POST /auth/ws-ticket` (کاربر معتبر، rate-limit `ws_ticket` = ۳۰/دقیقه، `Cache-Control: no-store`).
  اگر Redis در دسترس نباشد **503** (fail-closed): بلیتی که قابل ذخیره نیست قابل تأیید هم نیست.
- `verify_websocket_token` ترتیب: `ticket` (اگر ارائه شد و نامعتبر بود → رد، بدون downgrade)
  → `token` query (deprecated، با warning) → هدر `Authorization: Bearer`.
- فرانت: `lib/wsTicket.ts::fetchWsTicket()` با `apiPost` (پس توکن در هدر HTTP می‌ماند).
  `useWebSocket` و `GoldWSManager` قبل از dial بلیت می‌گیرند؛ بدون توکن (AUTH_DISABLED/مهمان)
  مثل قبل مستقیم وصل می‌شوند؛ خطای بلیت = error + reconnect، هرگز اتصال بدون احراز هویت.
  `seq` شمارنده از dial دیرهنگام پس از teardown/اتصال جدید جلوگیری می‌کند.

**تست‌ها** (`tests/unit/api/test_ws_ticket.py` — ۱۰ passed):
hash شدن و TTL=۶۰، مصرف یک‌باره، replay رد، توکن ناشناخته رد، Redis down → fail-closed،
purpose اشتباه رد، handshake با بلیت تازه، بلیت مصرف‌شده رد، بلیت نامعتبر به مسیر token
downgrade نمی‌کند، AUTH_DISABLED باز می‌ماند.

**فرانت:** `useSymbolPrices.test.ts` (۸) ادعا می‌کند URL فقط `ticket=` دارد و توکن در آن نیست،
همچنین اگر درخواست بلیت ۵۰۳ بدهد هیچ سوکتی باز نمی‌شود؛ `useWebSocketOrdering.test.tsx` (۲)
و `GoldWebSocket.test.tsx` (۱۰) با flush میکروتسک سازگار شدند.

## ۲) چهار endpoint بدون timestamp منبع

| endpoint | منبع | `data_as_of` |
|---|---|---|
| `/market/flow-history` | `brsapi_historical_real_legal` (آخرین روز) | `max(created_at)` ردیف‌های سروشده |
| `/market/value-history` | `brsapi_historical_daily` (N روز) | `max(created_at)` هر گروه، سپس بیشینه |
| `/market/ownership-history` | `brsapi_historical_real_legal` (N روز) | همان |
| `/economic-calendar` | `gold_economic_calendar_events` | `max(fetched_at)` |

- تاریخ بازار در این جدول‌ها **Jalali** است و instant نیست؛ تنها مهر زمانی صادق، زمان
  نوشتن ردیف است (محدودیت: ساعت DB؛ ستون `created_at` naive است).
- هوک‌های فرانت از `getDataAsOf(res)` + `envelopeResult` استفاده می‌کنند؛ تازگی/کهنگی حالا
  واقعی است، نه `isFresh:false` ثابت.

**یافتهٔ ضمنی (مهم):** `/economic-calendar` قبلاً یک **فهرست ثابت درون‌کد** با رویدادهای
تیر ۱۴۰۵ را به‌عنوان داده زنده سرو می‌کرد — نه timestamp داشت و نه منبع. اکنون از جدول
DB می‌خواند؛ جدول خالی ⇒ `events: []` و `data_as_of: null` (خالی صریح، نه داده ساختگی).
فهرست ثابت با کامنت «LEGACY … do not wire back» در فایل ماند (حذف کد بدون تأیید مالک انجام نمی‌شود).
تست `test_static_fixture_is_not_served` این را قفل می‌کند.

**تست‌ها:** `test_market_history_freshness.py` (۴) + `test_economic_calendar_source.py` (۴).

## ۳) اجرای تست

| مجموعه | نتیجه |
|---|---|
| `tests/unit/api/test_ws_ticket.py` | ۱۰ passed |
| `tests/unit/api/test_market_history_freshness.py` | ۴ passed |
| `tests/unit/api/test_economic_calendar_source.py` | ۴ passed |
| `tests/unit/test_auth_rate_limit.py` | ۷ passed (قرارداد `ws_ticket` اضافه شد) |
| `tests/unit/api` (کل) | ۳۶۰ passed، ۶ skipped، ۷ failed |
| فرانت: `useSymbolPrices` + `useWebSocketOrdering` + `GoldWebSocket` | ۲۰ passed |
| فرانت: `useMarketData` + `LiveDataBanner` + `DashboardPage` | ۲۶ passed |
| `tsc --noEmit` | پاک |
| eslint فایل‌های تغییریافته | فقط یک warning قدیمی (`_droppedByContract` در goldApi) |

۷ شکست `tests/unit/api` همان «Cannot connect to PostgreSQL» در `test_gold_derivatives_endpoints.py`
و `test_gold_personal_surface_auth.py` است (TEST-01؛ بدون ربط به این برش). دو تست
`test_market_dashboard_aggregates.py` که به ستون `created_at` نیاز داشتند به‌روز و سبز شدند.

## ۴) محدودیت‌ها و ریسک‌ها

- **مرورگر/E2E اجرا نشد** (بدون سرور زنده)؛ رفتار فقط با jsdom/vitest و fake WS سنجیده شد.
- Redis محلی اعتبارنامهٔ پیکربندی‌شده را رد می‌کند؛ مسیر بلیت با fake cache تست شد، نه Redis واقعی.
- مسیر deprecated `?token=` عمداً یک نسخه باقی مانده تا کلاینت‌های خارجی نشکنند؛ هر استفاده
  warning می‌دهد. حذف نهایی پس از اطمینان از مهاجرت همهٔ مصرف‌کننده‌ها.
- وقتی Redis در دسترس نیست، بلیت صادر نمی‌شود و WS احراز هویت نمی‌شود (fail-closed آگاهانه).
- `goldApi.ts` در working tree تغییرات staged از کار قبلی داشت (mtime قدیم)؛ ویرایش FE-06 در
  همان فایل انجام شد و تست‌های gold سبزند.
