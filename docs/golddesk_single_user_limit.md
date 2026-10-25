# محدودیت تک‌کاربره — چک‌لیست «قبل از کاربر دوم» + دیکشنری دادهٔ GoldDesk

نویسنده: دستیار ۳ (`fix/frontend-infra`) — تاریخ: ۲۰۲۶-۱۰-۲۴
مخاطب: صاحب محصول، و هر کسی که روزی بخواهد GoldDesk را چندکاربره کند.

---

## ۱) وضعیت امروز: تک‌کاربره، و این یک تصمیم است نه فراموشی

هیچ‌کدام از ۹ جدول ماژول طلا ستون `user_id` ندارند. یعنی **هر داده‌ای که نوشته
می‌شود، جهانی است**؛ اگر دومین کاربر وارد شود، دارایی، معاملات، پلن‌های DCA،
قواعد هشدار و تاریخچهٔ امتیاز کاربر اول را می‌بیند و روی آن‌ها می‌نویسد.

چیزی که این سند را مهم می‌کند: چون محصول امروز تک‌کاربره است، **هیچ‌کدام از
مسیرهای «جداسازی» آزموده نشده‌اند** — نه در تست، نه در UI. پس عبور به چندکاربره
یک تغییر migration نیست، یک بازآفرینی است.

نکتهٔ مهم و آسان‌گیرنده: احراز هویت *خودِ سرویس* تک‌کاربره نیست. `/gold/*` پشت
`_require_user` است (`apps/api/router.py:297`) و API token ها scope دارند. یعنی
«لاگین» هست، اما «مالکیت داده» نیست. این دو را اشتباه نگیرید.

## ۲) چک‌لیست قبل از کاربر دوم

هر آیتم بدون **تست** انجام‌نشده حساب می‌شود، نه بدون کد.

### ۲.۱ مدل و migration
- [ ] `user_id` (FK → `users.id`, `nullable=False`, `index=True`) به **هر ۹ جدول**:
  `gold_snapshots`, `gold_fund_nav`, `gold_alert_rules`, `gold_alert_events`,
  `gold_score_history`, `gold_holdings`, `gold_dca_plans`, `gold_trades`,
  `gold_portfolio_values`
- [ ] برای ۹ جدول یک migration **افزاینده** (نه rebuild): ستون nullable اضافه شود،
  داده موجود به کاربر تک‌نفرهٔ فعلی backfill شود، بعداً `NOT NULL` گردد.
  هیچ ردیفی در این فرآیند حذف نمی‌شود (سیاست repo: حذف داده ممنوع).
- [ ] یکتایی‌های جدید: `gold_portfolio_values (user_id, as_of)` و
  `gold_fund_nav (user_id, symbol, date)` — امروز اینها بدون کاربر یکتا هستند و
  با کاربر دوم کلیدهایشان معنایش را از دست می‌دهد.
- [ ] قیود `gold_trades.holding_id` / `plan_id` باید **درون‌مالک** بمانند: یک
  معامله نباید بتواند holding کاربر دیگری را نشانه برود (CHECK یا join در سرویس).

### ۲.۲ کوئری‌ها
- [ ] هر تابع خواندن/نوشتن در `src/gold_desk/*` (portfolio.py، alert_engine.py،
  snapshot_service.py، backtest_runner.py، live_signals.py) باید `user_id` بگیرد و
  در `WHERE` بگذارد. امروز هیچ‌کدام نمی‌گیرند.
- [ ] `build_portfolio_returns`, `capture_portfolio_value`, `get_plan_status` و
  همین‌طور `/portfolio/tax` و `/portfolio/export.csv` — اینها پول کاربر را
  محاسبه می‌کنند؛ یک فیلتر جابه‌جا = گزارش مالیاتی غلط.
- [ ] jobهای زمان‌بندی (`brsapi/jobs/gold_desk_jobs.py`, ۶ job) باید **per-user**
  شوند یا به صراحت global بمانند (jobهای دادهٔ بازار global می‌مانند؛ jobهای
  هشدار/ارزش‌گذاری پرتفو global **نمی‌مانند**).

### ۲.۳ کش و Realtime
- [ ] کلیدهای Redis امروز کاربر-ندارند → پیشوند `{user_id}:` می‌خواهند
  (دیکشنری کلیدها در `docs/analysis/02_backend_infra.md §۳`).
- [ ] `ws_hub` یک hub مشترک است و آخرین snapshot را برای «همهٔ client ها»
  broadcast می‌کند (`ws_hub.py:40-50`) → در چندکاربره یا per-user فیلتر شود یا
  مستند بماند که فقط دادهٔ عمومی بازار است.
- [ ] PWA service worker کش API را در **دستگاه** نگه می‌دارد؛ اگر دو کاربر با یک
  مرورگر کار کنند، کش مشترک است. TTL پنج‌دقیقه (F9) جلوی کهنگی را می‌گیرد نه
  جلوی نشتی؛ باید logout کش را پاک کند.

### ۲.۴ سطح API
- [ ] scope های واقعی token (`read|write|admin`) به مالکیت گره بخورند؛ امروز scope
  فقط «نوع عملیات» را می‌گوید نه «دادهٔ چه کسی».
- [ ] rate limit per-user (امروز بودجه‌ها سراسری‌اند، مثل `BRSAPI_GLOBAL_*_LIMIT`).
- [ ] `response_model` روی همهٔ route ها: امروز `/snapshot` با
  `response_model=None` است و بعضی route ها dict خام برمی‌گردانند → بدون schema،
  نشت فیلد در چندکاربره قابل کشف نیست.
- [ ] C3 (۵۰۳ + بدون متن خطای داخلی) و C4 (`current_score` سمت سرور) باید قبل از
  چندکاربره تمام شده باشند، وگرنه دادهٔ یک کاربر در پیام خطای کاربر دیگر ظاهر می‌شود.

### ۲.۵ بار و استقرار
- [ ] load test واقعی (`tests/load/locustfile.py`) با N کاربر هم‌زمان؛ اعداد SLO در
  `PLAN_GOLD.md` **فقط هدف** هستند و هنوز اندازه‌گیری نشده‌اند.
- [ ] پشتیبان‌گیری per-user یا حداقل یک آزمون بازگردانی روی دادهٔ چندکاربره
  (`docs/golddesk_backup.md`).

## ۳) دیکشنری داده (خلاصه از `src/gold_desk/models.py`)

۹ جدول، همه بدون `user_id`. «null» در ستون‌های زیر یعنی **داده وجود ندارد**، که
با «صفر» فرق دارد — این تمایز را UI هم باید نگه دارد (C2/C7).

### ۳.۱ دادهٔ بازار (global — با چندکاربره هم global می‌ماند)

**`gold_snapshots`** (۱۶ ستون) — قیمت لحظه‌ای هر سمبل + مرجع‌های ارزی
| ستون | نوع | نکته |
|---|---|---|
| `symbol`, `display_name`, `asset_type` | str | `gold` / `coin` / `fx` / `fund` |
| `market_price` | float | قیمت بازار |
| `fair_value`, `bubble_abs`, `bubble_pct`, `implied_usd` | float nullable | حباب؛ null ≠ صفر |
| `xau_usd`, `usd_irt`, `aed_irt`, `aed_parity_usd`, `aed_gap_pct` | float nullable | بلوک مرجع |
| `quality_flag` | str | `clean` / `fallback` / … |
| `snapshot_at` | datetime | مبنای زمانی؛ **hypertable نیست** |

**`gold_fund_nav`** (۱۳ ستون) — NAV/قیمت/BPR صندوق‌ها
`symbol`, `fund_name`, `date`, `nav_per_unit`, `market_price`, `bubble_abs`,
`bubble_pct`, `units_traded`, `real_buy_value`, `real_sell_value`, `bpr`,
`snapshot_at` — در این جدول `bubble_pct` **غیرnullable** است؛ خلاف
`gold_snapshots`. مصرف‌کنندهٔ UI نباید فرض کند هر دو یکی‌اند.

**`gold_score_history`** (۷ ستون) — `total_score`, `components_json`, `decision`,
`hard_stop_active`, `hard_stop_reason`, `score_at`. با قرارداد C1 مقدار
`decision` حالا می‌تواند `NO_DATA` باشد؛ این ستون str است نه enum، پس مقدار تازه
بدون migration می‌آید — ولی کوئری‌های `WHERE decision = ...` باید بازبینی شوند.

### ۳.۲ دادهٔ شخصی کاربر (حساس — محل اصلی خطر چندکاربره)

**`gold_holdings`** (۱۱ ستون) — هر ردیف یک خرید است
`symbol`, `display_name`, `vehicle`, `quantity`, `buy_price`, `buy_amount_irt`,
`buy_fee_pct`, `bought_at`, `note`, **`deleted_at`** (soft-delete، C7 — migration
`0043_gold_holding_soft_delete`).

**`gold_trades`** (۱۲ ستون) — `holding_id` (nullable, `ON DELETE SET NULL`)،
`plan_id` (nullable)، `symbol`, `action` (buy/sell), `quantity`, `price`,
`amount_irt`, `fee_irt`, `pnl_irt`, `note`, `traded_at`.
⟵ این جدول **سابقهٔ مالیاتی** است؛ به همین دلیل حذف holding پیش‌فرض نرم است.

**`gold_dca_plans`** (۱۲ ستون) — `name`, `total_capital_irt`, `risk_profile`,
`vehicle`, `ladder_json`, `executed_tranches`, `current_score`, `stop_loss_pct`,
`take_profit_pct`, `created_at`, `updated_at`.
⟶ با C4، `current_score` باید از snapshot سرور خوانده شود، نه از بدنهٔ کاربر؛
ستون فعلاً در جدول می‌ماند (تاریخچهٔ پلن‌های قدیمی).

**`gold_portfolio_values`** (۷ ستون) — `as_of` (date), `total_value_irt`,
`total_cost_irt`, `net_flow_irt`, `unpriced_holdings`, `snapshot_at`. سری زمانی
ارزش پرتفو؛ مبنای محاسبهٔ TWR.

### ۳.۳ هشدارها (قاعدهٔ کاربر + رویداد)

**`gold_alert_rules`** (۱۱ ستون) — `name`, `rule_type`, `symbol`, `threshold`,
`channel`, `telegram_chat_id`, `enabled`, `cooldown_minutes`, `last_fired_at`,
`created_at`. ⚠️ `telegram_chat_id` در این جدول **صریح** ذخیره می‌شود؛ در
چندکاربره نباید در پاسخ API بدون scope بنشیند.

**`gold_alert_events`** (۱۰ ستون) — `rule_id`, `rule_name`, `symbol`,
`trigger_value`, `threshold`, `message`, `channel`, `sent_at`, `read_at`.

## ۴) دو مشاهده که در محدودهٔ من نیستند ولی دیدم

1. `docs/analysis/02_backend_infra.md` §۲.۱ «۵ جدول از 0041 + ۳ جدول از 0042» =
   ۸ جدول می‌گوید، درحالی‌که `models.py` ۹ جدول دارد (`gold_portfolio_values`
   جا افتاده). سند فقط‌خواندنی است، پس تصحیحش نکردم.
2. در خودِ فایل‌های `docs/analysis/` چند کاراکتر CJK/Korean وسط متن فارسی مانده
   (مثلاً «کد實際»، «مشخصات 기타»، «تست‌های ن anhydro»). همان الگویی که F8 در
   `ParityBadge.tsx:18` پیدا کرد؛ اینجا چون فایل‌ها only-read اند، فقط ثبت شد.

## ۵) خلاصهٔ تصمیم

تا وقتی بخش ۲ کامل نشده، **افزودن کاربر دوم ممنوع** است. راه‌میانهٔ کم‌خطرتر:
GoldDesk را تک‌کاربره نگه دارید و دسترسی دیگران را فقط-خواندنی (token با scope
`read`) بدهید — آن‌وقت هیچ‌کدام از ۹ جدول و ۲.۱ تا ۲.۵ لازم نیست.
