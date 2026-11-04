# مرحلهٔ ۱۱ — امنیت: شاهد اجرا (۲۹ اکتبر ۲۰۲۶)

دامنه: SEC-06/07/08 و sweep کامل IDOR/نقش.
بدون DB/شبکهٔ زنده؛ وضعیت Redis محلی برای بررسی قطعی با fake شبیه‌سازی شد.

## ۱) SEC-06 — هویت rate-limit و آستانه‌های refresh/logout

**قبل:** `_get_client_ip` هر `X-Forwarded-For` را می‌پذیرفت؛ هر تلاش می‌توانست
bucket تازه بسازد و limit لاگین/OTP را دور بزند. `refresh` و `logout` هیچ limit نداشتند.

**بعد:**
- `TRUSTED_PROXIES` (لیست IP/CIDR) در `core/config`؛ XFF فقط وقتی استفاده می‌شود که
  peer سوکت در لیست باشد؛ در غیر این صورت آدرس peer حاکم است.
- `refresh` = ۳۰/دقیقه، `logout` = ۱۰/دقیقه (per IP).

**تست:** `tests/unit/api/test_trusted_proxy_ip.py` (۶) + قرارداد `_AUTH_LIMITS` در
`test_auth_rate_limit.py` به‌روز شد. **باقی‌مانده:** در prod باید `TRUSTED_PROXIES`
مقدار بگیرد وگرنه محدودیت‌ها روی IP پروکسی مشترک اعمال می‌شوند (امن است، ولی per-client نیست).

## ۲) SEC-07 — پایان همهٔ نشست‌ها پس از تغییر رمز

**قبل:** فقط jti همان توکن باطل می‌شد؛ دستگاه‌های دیگر تا ۶۰ دقیقه توکن معتبر داشتند.
همچنین `is_token_revoked` در قطعی Redis fail-open بود.

**بعد:**
- `create_access_token` حالا `iat` می‌گذارد.
- `revoke_user_access_tokens(uid)` یک cutoff در `auth:user_revoked:<uid>` می‌نویسد
  (TTL = عمر access token)؛ `is_user_session_revoked(uid, iat)` هر توکن قدیمی‌تر را رد می‌کند.
- `_reject_if_revoked` و `get_optional_user` هر دو چک می‌کنند؛ پس همهٔ endpointها
  و WebSocket (از مسیر توکن) پوشش می‌گیرند.
- `/auth/change-password` **قبل از تغییر** بررسی می‌کند که store در دسترس است؛ در قطعی
  Redis پاسخ ۵۰۳ می‌دهد (به‌جای تغییر رمز با نشست‌های زنده). `reset_password` هم پس از
  تغییر، توکن‌های کاربر را باطل می‌کند.
- marker خراب/غیرقابل‌تجزیه = «باطل» (fail-closed روی دادهٔ نامفهوم، نه روی transport).

**تست:** `tests/unit/api/test_session_revocation.py` (۸) — cutoff، TTL، بدون marker،
marker خراب، قطعی Redis، حضور `iat`، رد در `_reject_if_revoked`، ۵۰۳ برای change-password.

**باقی‌مانده:** اگر Redis **بعد از** تغییر رمز قطع شود، توکن‌های قدیمی تا انقضای خود
(۶۰ دقیقه) معتبر می‌مانند — همان سیاست fail-open موجود برای revocation؛ حذف کامل آن
نیازمند `token_version` در DB/migration است (گروه C).

## ۳) SEC-08 — bootstrap مالک بدون race

**قبل:** دو ثبت‌نام هم‌زمان هر دو `count=0` می‌دیدند و هر دو admin می‌شدند.

**بعد:** `register` قبل از شمارش، `pg_advisory_xact_lock` می‌گیرد (بدون migration؛ روی
PostgreSQL تراکنش‌ها سریال می‌شوند، روی fake/SQLite بی‌اثر است) و نقش admin فقط وقتی
اعمال می‌شود که جدول خالی باشد **و** `BOOTSTRAP_FIRST_ADMIN` روشن باشد.

**تست:** `tests/unit/services/test_registration_bootstrap.py` (۳) — admin برای اولین،
user برای دوم، خاموش‌کردن dial، و وجود advisory lock در SQL.

## ۴) sweep کامل IDOR/نقش

- ابزار موجود `scripts/check_router_auth.py` (گراف واقعی dependency، نه اسکن متنی) اجرا شد:
  **«Audited 710 router operations and 8 app-level routes — OK»**. این ابزار در CI
  (`ci-pr.yml:140`) هم اجرا می‌شود و تست دودی در `tests/unit/test_api_v6_hardening.py` دارد.
- بازبینی دستی سطوح شخصی که ابزار فقط «authenticated» را می‌سنجد:
  - `portfolios`, `alerts`, `watchlist` — owner scoping (SEC-03/04/05، قبلاً).
  - `paper-trading` — `list_trades/get_dashboard/open/close` با `user_id` و `_get_owned_trade`
    (ردیف‌های NULL-owner قدیمی فقط admin/عمومی)؛ mount با `_require_user`.
  - `pre-buy/sheets/{id}` — `_owned(sheet_id, session, current_user)` → ۴۰۴ برای غیرمالک.
  - `saved_filters` — همهٔ کوئری‌ها با `user_id` از JWT.
  - `writes` روی مرجع داده (`news/symbols/codal/funds`) — `require_roles("admin")` (API-06).

**باقی‌مانده:** نقش‌ها در JWT کش می‌شوند و تغییر نقش تا انقضای توکن اثر نمی‌گذارد؛
مالکیت `saved_filters`/`pre_buy` تست خودکار اختصاصی ندارد (فقط بازبینی کد).

## ۵) اجرای تست

| مجموعه | نتیجه |
|---|---|
| ۴ فایل جدید/به‌روز مرحله | ۲۵ passed |
| `tests/unit/api` + auth/security suites | **۴۴۶ passed، ۶ skipped، ۷ failed** |
| ۷ شکست | `test_gold_derivatives_endpoints` (۲) و `test_gold_personal_surface_auth` (۵) — «Cannot connect to PostgreSQL» (محیط) |
| `scripts/check_router_auth.py` | exit 0 — ۷۱۰ + ۸ مسیر |
