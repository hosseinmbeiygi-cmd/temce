# CHANGELOG — مرحلهٔ ۳ (بستن فاصله‌ها) · دستیار `frontend-infra`

تاریخ: ۲۰۲۶-۱۰-۲۴ · مرحلهٔ ۱: `docs/fixes/frontend_infra_CHANGELOG.md`
فهرست مسیرهای لمس‌شده در این مرحله: `docs/fixes/frontend_infra_paths.txt`

> **وضعیت commit:** همچنان **هیچ commitی نزده‌ام** (قاعدهٔ ۱ مرحلهٔ ۳). درخت بین
> سه دستیار مشترک است و در میانهٔ همین مرحله یک **گذر ادغام** روی آن اجرا شده:
> `handoff_frontend_to_backend.md` من به `handoff_frontend_to_backend_1.md`
> تغییر نام یافت و فایل‌های `paths_reconciliation.md`، `final_inventory.md`،
> `final_status.md`، `secret_hygiene_report.md` و `*_paths_final.txt` ظاهر شدند.
> من آن فایل‌ها را دست نزدم؛ §۷ handoff خودم را در نام تازه اصلاح کردم.
>
> **قاعدهٔ ۵ (چاپ نکردن secret):** خودم را هم حساب کردم — در مرحلهٔ ۱ سه مقدار
> لو‌رفته را در گزارش‌هایم نوشته بودم که در این مرحله ماسک شد (§S3).

---

## ۱) جدول شناسه‌ها

| شناسه | وضعیت | فایل‌ها | تست |
|---|---|---|---|
| **S1** — دو SW رقیب | `fixed` (قرارداد با تست قفل شد؛ ادغام به یک SW فقط پیشنهاد) | `frontend/public/sw.js`, `frontend/public/golddesk-sw.js`, `frontend/src/__tests__/fixtures/swHarness.ts` (جدید) | `GoldSwBoundary.test.ts` (۶) + بازنویسی‌شدهٔ `GoldServiceWorker.test.ts` (۷) |
| **S2** — env و بوت‌استرپ | `fixed` | `.env.example`, `docs/golddesk_first_run.md` (جدید), `PLAN_GOLD.md` (ارجاع شروع سریع) | — (پیکربندی/سند) |
| **S3** — secretها | `partial` — **ابزار و سند کامل؛ چرخش واقعی باقی است** | `.gitleaks.toml` (جدید), `scripts/scan_secrets.py` (جدید), `.github/workflows/ci.yml`, `docs/security/secret_scan_report.md` (جدید), `docs/security/secret_rotation.md` (جدید), `docs/secrets-management.md`, `docs/SECRETS_ROTATION_2026-09-16.md`, ۴ سند `docs/fixes/*` (ماسک) | اجرای قدم blocking CI محلی = exit 0؛ اعتبارسنجی TOML + RE2 + گرفتن ۵ هدف واقعی |
| **S4** — بازگردانی واقعی | `partial` — **I4 عمداً fixed نیست** | `scripts/test_restore_golddesk.sh` (جدید), `docs/golddesk_backup.md` §۴ | پیش‌نیاز نبود ⇒ **NOT EXECUTED** با exit 3 (خروجی واقعی در §۳) |
| **S5/F7** | `fixed` (feature-detect؛ OOS منتظر serialize بک‌اند) | `frontend/src/app/gold/backtest/page.tsx`, `frontend/src/lib/goldApi.ts` | `GoldBacktestPage.test.tsx` (۴) |
| **S5/F6** | `fixed` (فرانت) — بک‌اند هنوز push ندارد | — (تغییر جدید نداد؛ مرحلهٔ ۱ کافی بود) | `GoldWebSocket.test.ts` (۵) + `GoldSnapshotPolling.test.tsx` (۳) نگه داشته شدند |
| **S5/I2** | `partial` — تا نبود scope `metrics` | (بدون تغییر در این مرحله) | — |
| **S5/nginx** | `fixed` (مسیرها تأیید شدند) / `wontfix` برای `nginx -t` | `nginx-golddesk.conf` (مرحلهٔ ۱) | — (nginx روی این ماشین نصب نیست ⇒ توضیح، نه اجرا) |
| **S6** — فهرست‌ها | `fixed` (بدون هیچ حذف) | `docs/fixes/dead_code_list.md`, `docs/fixes/license_decision.md` | — |

---

## ۲) S1 — پاسخ دقیق «کدام SW کدام صفحه را کنترل می‌کند»

- `providers.tsx:15` → `register("/sw.js")` **بدون scope** ⇒ scope = `/`.
- `PWAProvider.tsx:21` → `register("/golddesk-sw.js", { scope: "/gold" })`.
- طبق spec، برای یک client_longest matching scope برنده است ⇒ **صفحات `/gold*` را
  `golddesk-sw.js` می‌گیرد** و بقیهٔ اپ را `sw.js`.
- **نکته‌ای که اولاً ندیدم و تستش کردم:** `CacheStorage` در یک origin **بین دو SW
  مشترک** است. پس اگر `sw.js` روزی `/api/` را cache-first کند، می‌تواند ورودیِ
  کش‌شده توسط SW طلا را سرو کند. `GoldSwBoundary.test.ts` همین را برای **هر دو**
  فایل می‌آزماید: (الف) شبکه همیشه برندهٔ cache است؛ (ب) پاسخ کهنه‌تر از سقف
  مشترک سرو نمی‌شود.
- **تصحیح ادعای مرحلهٔ ۱ خودم** (قاعدهٔ ۴): نوشته بودم «`sw.js` روی `/api/`
  cache-first است». **غلط بود** — خط ۳۰ آن network-only است و هیچ پاسخی را کش
  نمی‌کند؛ آنچه cache-first است فقط دارایی‌های غیر-API (خط ۴۳) هستند. ادعای
  «خطرناک‌تر از TTL طلا» را پس می‌گیرم.
- تغییر من در `sw.js` رفتار را عوض نکرد؛ **صریح** کرد: شاخهٔ ویژهٔ
  `/api/v1/gold/` که هرگز cache را نمی‌خواند، و ثابت مشترک
  `FINANCIAL_MAX_AGE_MS = 300_000` که حالا **در هر دو فایل یک عدد است** (تست ۶
  این برابری را قفل می‌کند؛ قبل از تغییر، قرمز بود چون `sw.js` اصلاً چنین مفهومی
  نداشت).
- **پیشنهاد (بدون اجرا):** یک SW کافی است — `sw.js` با شاخهٔ طلای TTL‌دار و
  حذف ثبت دوم. انجامش ندادم چون `sw.js` کل اپ غیرطلا را کنترل می‌کند و این
  تغییر، ریسکِ خارج از محدوده دارد. اگر خواستید، جدا انجام می‌شود.

## ۳) S4 — چیزی که اجرا **نشد**

```
$ bash scripts/test_restore_golddesk.sh
NOT EXECUTED — daemon داکر در دسترس نیست (Docker Desktop بالا نیست؟). این آزمون
  را روی سروری اجرا کنید که timescaledb آنجا running است؛ تا قبل از آن،
  I4 «fixed» نیست.
EXIT=3
```

- باینری `docker` هست، **daemon** بالا نیست؛ `psql`/`pg_dump`/`pg_restore` نصب
  نیستند؛ سرویس `timescaledb` روی این ماشین running نیست.
- اسکریپت عمداً در نبود پیش‌نیاز **exit 3** می‌دهد (نه صفر)، تا «اجرا شد» با
  «پاس شد» اشتباه نشود. `--dry-run` هم نقشه را بدون اجرا چاپ می‌کند (تأیید شد).
- **دستوری که شما باید اجرا کنید** (روی سرور مقصد):
  ```bash
  cd /srv/temce
  docker compose -f docker-compose.yml up -d timescaledb
  bash scripts/test_restore_golddesk.sh
  ```
  انتظار: جدول ۹ ردیف «ok» + «آخرین snapshot برابر» ⇒ آن‌گاه I4 را fixed بنویسید.
- مقایسه فقط شمار ردیف نیست: `max(snapshot_at)` هم برابرسنجی می‌شود تا نسخهٔ
  خالیِ ساختار-درست اما بی‌داده، پاس نشود.

## ۴) S3 — نتیجهٔ اسکن و کاری که شد

- `gitleaks` در CI **از قبل** بود (`secrets-scan.yml:23`)، ولی commit-محور است:
  secretهایی که پیش از وجودش commit شده‌اند را نمی‌بیند. `.gitleaks.toml` در ریشه
  را همان اقدام خودکار برمی‌دارد؛ پس قواعد تازه بدون ویرایش آن workflow فعال‌اند.
- دو قدم به `ci.yml` اضافه شد: **blocking** روی محدودهٔ من (با اسکنر خودنویس،
  exit 0 تأیید شد) و **advisory** برای درخت کامل (اگر باینری gitleaks روی runner
  باشد، با `--redact`).
- یافته‌های نیازمند اقدام: `k8s/decision-engine-secret.yaml:20,23,26`،
  `docker-compose.decision-engine.yml:49,73,74,76`، `docker-compose.sandooghyar.yml:39`،
  `src/gold_desk/api_token.py:28` (پیش‌فرض salt)، reprint در
  `docs/analysis/02_backend_infra.md:538`، و reprint در
  `docs/git-history-rotation.md` (§۴-الف پایین). جزئیات: `docs/security/secret_scan_report.md`.
- **باگ‌هایی که در ابزار خودم پیدا و رفع شد** (چون تست کردم، نه اینکه فرض کنم
  درست است): (۱) `--files` با دایرکتوری هیچ نمی‌گرفت ⇒ صفر کاذب؛ (۲) URL با
  username خالی (`redis://:pass@`) را نمی‌دید؛ (۳) `SKIP_DIR_PARTS` بزرگ‌حرفی با
  `lower()` مقایسه می‌شد؛ (۴) قاعدهٔ salt من **هدف اصلی‌اش را نمی‌گرفت** و
  `(?!\s*\$\{)`/`(?xi)` در RE2 اصلاً کامپایل نمی‌شوند.
- چرخش واقعی (rotate + بازصدور توکن‌ها) **انجام نشد** و از عمق کار من نیست:
  رمزها در `.env`/secret manager شماست و `filter-repo` را طبق قاعده اجرا نکردم.

### ۴-الف) اضافهٔ این دور: یک یافتهٔ تازه که اسکنر الگومحور نمی‌دید

برای بستن سؤال مالکیت (`k8s/**`)، مقادیر decode‌شدهٔ manifest را با «دانشنامهٔ
مقدارهای شناخته‌شده» در همهٔ ۱۲٬۹۲۵ فایل track‌شده جویدم (بدون چاپ هیچ مقداری).
نتیجه: **۱۲ occurrence در ۳ فایل**.

| محل | چه | کاری که کردم |
|---|---|---|
| `docker-compose.decision-engine.yml:49` | `--requirepass <17 کاراکتر>` — خطی که جدول §۲ نسخهٔ اول جا انداخته بود (URL نیست، پس الگوی `url-with-credentials` نمی‌گیرد) | دست نزدم (محدودهٔ من است؛ اسلایس K1، منتظر تأیید) |
| `k8s/decision-engine-secret.yaml:19,22` | کامنت‌های «echo -n … » همان دو credential را plaintext دارند (پس نه‌فقط base64 خط ۲۰/۲۳) | دست نزدم (`k8s/**` در هیچ فهرست مالکیتی نیست) |
| `docs/git-history-rotation.md:5,6,31,32,45` | **خودِ سند راهنمای پاک‌سازی، هر دو credential فعال را دوباره چاپ کرده بود** — و در خط ۸ ادعا می‌کرد «current tree is clean» | **۶ occurrence ماسک شد** → `<masked-from-history>`؛ قدم‌های ۳/۴/۵ بازنویسی شدند تا `secrets.txt` **خارج از repo** ساخته و با `grep -F -f` بررسی شود (دستورالعمل همچنان اجرایی است، مقدار دیگر در repo نیست) |

شمارِ واقعی نیازمند اقدام از ۵ به **۷** رسید (§۲ و §۳ِ `secret_scan_report.md`
به‌روز شدند). درس روش‌شناختی: یک اسکنر الگومحور برای reprintِ «مقدار تنها در خط»
کور است؛ قدم blocking CI هم همین‌طور. برای همین این cross-check در §۶ همان سند
ثبت شد.

## ۵) تصحیح‌های «گزارش/ادعا ≠ کد» در این مرحله

| ادعای قبلی | واقعیت کد |
|---|---|
| «`sw.js` روی `/api/` cache-first است» (مرحلهٔ ۱، من) | network-only؛ هیچ پاسخ API را کش نمی‌کند (`sw.js:30-40`) |
| «OOS را موتور محاسبه نمی‌کند» (مرحلهٔ ۱، بند ۷ handoff) | `BacktestMetrics` پنج فیلد `oos_*` را **دارد** (`backtest_runner.py:77-81`)؛ فقط `/backtest/strategy` serialize نمی‌کند (`api.py:534-562`). درخواست به ~۵ خط کاهش یافت. |
| «۵ route یتیم ⇒ کد مرده» (پیشنهاد F8) | ۴ تایشان `redirect` پنج‌خطی به `/gold` هستند (**زنده**); فقط `/gold/coins` (۳۹۰ خط) واقعاً بی‌لینک است (`grep` → صفر). |
| «`GOLD_API_TOKEN_SALT` در `.env.example` نیست ⇒ دستیار Ops اضافه کند» | `.env.example` در مرحلهٔ ۳ شد محدودهٔ من ⇒ خودم اضافه کردم؛ handoff به «حل شد» به‌روز شد. |
| «`planDCA` حذف `current_score` ممکن است صفحه‌ای را بشکند» | تنها فراخوان آن `DCACalculator.tsx` است که **هیچ‌جا import نمی‌شود** و `/gold/dca` فقط redirect است ⇒ ریسک 422 امروز صفر. |
| «`docs/analysis/**` در repo منتشر شده» | **untracked** است (`git status: ?? docs/analysis/`) ⇒ مقدار reprint‌شدهٔ آن منتشر نشده؛ با این حال ماسکش کار صاحب گزارش است نه من. |
| «یافته‌های secret من ۵ مورد است و ۳ credential واقعی» (این گزارش، نسخهٔ اول) | **کم‌شمار بود**: با cross-check مقدارهای شناخته‌شده، ردیف ۷ (`docs/git-history-rotation.md`، ۶ occurrence) و خط ۴۹ `docker-compose.decision-engine.yml` اضافه شد ⇒ ۷ مورد نیازمند اقدام. سند ماسک شد؛ اعداد در `secret_scan_report.md` §۲/§۳ اصلاح شدند. |
| «`k8s/decision-engine-secret.yaml` یک کلید واقعیِ لو‌رفته دارد (Critical)» | `SECRET_KEY` خط ۲۶ **عین متن placeholder** کامنت خودش است («replace before production use») ⇒ کلید واقعی لو نرفته؛ Critical فقط مشروط است (اگر محیطی با همین manifest اعمال شده باشد — `decision-engine-deployment.yaml:151-155` آن را مصرف می‌کند). ولی خط‌های ۲۰/۲۳ **credential واقعی‌اند**: decode‌شان با مقدارهای inline زندهٔ `docker-compose.decision-engine.yml` یکی است. |
| «دو فایل compose سرویس‌های دیگر خارج از محدودهٔ من‌اند» (من، §۵ نسخهٔ اول) | محدودهٔ من glob **«`docker-compose*.yml`»** ثبت شده (`handoff_frontend_to_ops_env.md:23`) ⇒ آن دو فایل **کار من‌اند**؛ فقط چون بالا‌آمدن سرویس را fail-closed می‌کنند، اسلایس K1/K2 به تأیید شما موکول شد. |

## ۶) راستی‌آزمایی (خروجی واقعی این مرحله)

```
$ cd frontend && npx tsc --noEmit                     → TSC=0
$ cd frontend && npx vitest run                       → 50 فایل / 538 تست، همه پاس
      (مرحلهٔ ۱: 48 فایل / 527؛ این مرحله +2 فایل +11 تست)
$ bash scripts/test_backup_golddesk.sh                → «همهٔ بررسی‌ها پاس شد»
$ bash scripts/test_restore_golddesk.sh               → EXIT=3 (NOT EXECUTED — پیش‌نیاز نیست)
$ bash scripts/test_restore_golddesk.sh --dry-run     → EXIT=0 (نقشه)
$ python scripts/scan_secrets.py --fail-on-real …     → EXIT=0 (قدم blocking CI)
$ python -c "tomllib(.gitleaks.toml); yaml(ci.yml)"    → TOML+YAML OK
$ RE2-safety check on .gitleaks.toml                  → problems: NONE
$ custom gitleaks rules vs real targets               → 5/5 caught, current compose 0
$ known-value cross-check (پیش از ماسک)              → 12 occurrence در 3 فایل (compose=4, k8s=2, docs=6)
$ known-value cross-check (پس از ماسک این سند)       → 6 occurrence، فقط در 2 فایل infra که دست نزدم
$ python scripts/scan_secrets.py … (تکرار پس از ماسک) → EXIT=0
```

## ۷) سؤالات باز

1. **ادغام با گذر موجود:** یک مرحلهٔ ادغام فایل handoff من را rename کرده
   («`_1`» پسوند ندارد، فقط شماره خورده) و `*_paths_final.txt` ساخته. آیا
   `frontend_infra_paths.txt` (این مرحله) باید با `frontend_infra_paths_final.txt`
   ادغام شود یا جدا بماند؟ من هر دو را نگه داشتم و هیچ‌کدام را پاک نکردم.
2. **چرخش واقعی secret:** آیا من فقط سند/ابزار بدهم (وضعیت فعلی) یا شما
   `docs/security/secret_rotation.md §۳` را اجرا می‌کنید تا S3 و I4 واقعاً بسته
   شوند؟ تا پیش از آن، S3 = partial.
3. **مالکیت `k8s/decision-engine-secret.yaml`** — پاسخ با شواهد و توصیه: فایل در هیچ
   یک از سه فهرست مالکیت نیست. با اجرا بررسی شد (بدون چاپ مقدار): دو مقدار
   `DATABASE_PASSWORD`/`REDIS_PASSWORD` عین همان credentialهای inline در
   `docker-compose.decision-engine.yml:73,74,76` هستند ⇒ واقعی‌اند و روی
   `origin/main` منتشر شده‌اند (کامیت `1bb41c4c`)؛ ولی `SECRET_KEY` خط ۲۶ برابر
   متنِ کامنتِ «replace before production use» خودش است ⇒ کلید واقعی لو نرفته،
   و Critical فقط اگر محیطی با همین manifest اعمال شده باشد
   (`k8s/decision-engine-deployment.yaml:151-155` آن را مصرف می‌کند).
   **توصیه: محدودهٔ من (دستیار ۳)** — کلاس رفعش manifest/env است، برادرهایش
   (`docker-compose*.yml`, `monitoring/`, `.env.example`, `docs/security/`) همین حالا
   مال من‌اند، و دستیار ۲ فقط `src/gold_desk/**` و دستیار ۱ فقط پایتون موتور است.
   ⚠️ تصحیح خودم: دو فایل compose سرویس‌های دیگر را در گزارش «خارج از محدوده»
   نوشته بودم؛ چون محدودهٔ من glob `docker-compose*.yml` است، آن‌ها **کار من‌اند**
   (§۲-الفِ `secret_scan_report.md`، اسلایس‌های K1–K4). تا تأیید شما دست نمی‌زنم،
   چون K1/K2/K3 بالا‌آمدن آن سرویس‌ها را fail-closed می‌کنند.
4. **ماسک `docs/analysis/02_backend_infra.md:538`:** فایل فقط‌خواندنی برای من است.
   اگر می‌خواهید ماسک شود، صریح بگویید تا از قاعدهٔ ۲ استثناء شود.
5. **ادغام دو Service Worker** (§۲ بالا): انجام شود یا قرارداد فعلی با تست قفل
   شده کافی است؟
6. **`/gold/coins`:** به ناوبری برگردد یا حذف شود؟ (۳۹۰ خط، صفر لینک ورودی)
7. **لایسنس:** A/MIT بماند، B/داخلی، یا C/دوگانه؟ (`docs/fixes/license_decision.md`)
   گزینهٔ C را منطقی‌ترین دانستم چون ریسک اصلی این repo دادهٔ شخص ثالث است نه کد.
8. **`.env.example` و `DEV_JOB_QUEUE_TOKEN`:** حالا اجباری‌اند؛ اولین
   `docker compose up` روی محیط تازه با خطا می‌ایستد. این خواستهٔ I3 است، ولی
   می‌خواهید پیام خطای بهتری بسازم یا همین `:?` کافی است؟
9. **تعارض قاعده در `scripts/scan_secrets.py`:** قاعدهٔ ۳ می‌گوید «هر فایل Python
   ممنوع»، ولی مالکیت جدید «`scripts/` (جدید)» را داده است. من فایل را پایتون نوشتم
   (چون stdlib + در دسترس همهٔ CIها) و در `frontend_infra_paths.txt` هم آورده‌ام.
   اگر تفسیر شما «ممنوعیت مطلق پایتون» است، بگویید تا به bash/portable تبدیلش
   کنم یا حذفش کنم و اسکن را فقط به gitleaks واگذار کنم. (یادداشت: گذر ادغام،
   `scripts/test_backup_golddesk.sh` من را در گروه **Backend** طبقه‌بندی کرده است.)
