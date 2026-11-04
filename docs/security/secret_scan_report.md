# گزارش اسکن secret — repo temce (S3)

تاریخ: ۲۰۲۶-۱۰-۲۴ · مجری: دستیار ۳ (`fix/frontend-infra`)
ابزار: `scripts/scan_secrets.py` (اسکنر الگوی خودنویس، چون `gitleaks` روی این
ماشین نصب نیست) + قواعد repo-محور در `.gitleaks.toml` برای CI.

> ⚠️ در این سند **هیچ مقداری چاپ نمی‌شود** (قاعدهٔ ۵). هر یافته فقط
> `فایل:خط` + نوع + طول مقدار است. برای دیدن خود مقدار، به آن خط در فایل یا در
> تاریخچهٔ git بروید.

## ۱) روش و دامنه

```bash
python scripts/scan_secrets.py                 # فقط فایل‌های track‌شده، بدون vendor
python scripts/scan_secrets.py --include-vendor --include-placeholders
# همان چیزی که در CI بلاک می‌کند (قدم «Secret scan — owned scope»):
python scripts/scan_secrets.py --fail-on-real --exclude '(^|/)docs/analysis/' \
  --files frontend/src frontend/public monitoring scripts docs .github/workflows \
          .gitleaks.toml docker-compose.yml nginx-golddesk.conf .env.example PLAN_GOLD.md
```

دامنه: خروجی `git ls-files` (۱۲٬۹۱۷ فایل). حذف‌شده‌ها: `node_modules`،
`.git`، `*.min.js`، قفل‌های پکیج (`package-lock.json` و … چون digest دارند نه
credential)، و محتوای vendor (`.agents/`, `_FRONTEND_BACKEND_COPY/`,
`_audit_base/`, `.freebuff/`). با `--include-vendor` دوباره قابل مشاهده‌اند.

کالیبراسیون: نسخهٔ نخست اسکنر **۱٬۰۰۳** یافته می‌داد که اکثرش false positive بود
(`password=hashed_password`، urlهای `localhost`، digest قفل‌ها، و مسیر
`_FRONTEND_BACKEND_COPY` به‌خاطر مقایسهٔ حساس به بزرگی/کوچکی حروف). چهار اصلاح
عدد را به **۱۰** رساند:
1. در کد فقط literal نقل‌قول‌شده؛
2. رد کردن host لوکال/placeholder؛
3. کوچک‌کردن entries حذف + رد کردن lockfileها؛
4. **و یک نقص واقعی در خود اسکنر**: `--files` با *دایرکتوری* هیچ فایلی را
   اسکن نمی‌کرد (`is_file()` ردشان می‌کرد) ⇒ صفر کاذب. رفع شد (حالا `rglob`
   می‌کند) و با یک آزمون مثبت ثابت شد: `--files core/security` آن الگو را
   پیدا می‌کند. همچنین `url-with-credentials` ابتدا
   `[^\s:@/]{1,64}` داشت و `redis://:pass@host` (username خالی) را **نمی‌گرفت**؛
   به `{0,64}` تغییر کرد — همان چیزی که `docs/analysis/02_backend_infra.md:538`
   را آشکار کرد (ردیف ۶ جدول §۲).

## ۲) یافته‌های نیازمند اقدام (مرتب بر اساس ریسک)

| # | محل | نوع | چرا | ریسک |
|---|---|---|---|---|
| ۱ | `k8s/decision-engine-secret.yaml:20,23,26` | سه مقدار base64 in-manifest (`DATABASE_PASSWORD`, `REDIS_PASSWORD`, `SECRET_KEY`) | دو واقعیت که با اجرا بررسی شدند (مقدار چاپ نمی‌شود): (الف) `DATABASE_PASSWORD` و `REDIS_PASSWORD` **عین همان رشته‌هایی‌اند که inline در `docker-compose.decision-engine.yml:73,74,76` هستند** ⇒ placeholder بی‌خطر نیستند، credential واقعی‌اند. (ب) `SECRET_KEY` (طول decode=41) برابر متنِ کامنتِ «replace before production use» خودش است ⇒ کلید واقعی لو نرفته، ولی `k8s/decision-engine-deployment.yaml:151-155` آن را با `secretKeyRef` مصرف می‌کند؛ یعنی اگر یک محیط با همین manifest بالا آمده باشد، کلید امضای JWT/CSRF عمومی است و token ساختنی. | **High** (دو credential واقعی، منتشرشده روی `origin/main` — کامیت `1bb41c4c` مورخ ۲۰۲۶-۰۸-۰۵، با `git merge-base --is-ancestor` تأیید شد) + **Critical مشروط** برای `SECRET_KEY` |
| ۲ | `docker-compose.decision-engine.yml:49,73,74,76` | `url-with-credentials` (len=17) + یک `--requirepass` | رمز DB inline در سه `DATABASE_URL*` **و** رمز Redis در فرمان `redis-server` (خط ۴۹ را نسخهٔ اول این جدول جا انداخت؛ با cross-check_known-values پیدا شد) | High |
| ۳ | `docker-compose.sandooghyar.yml:39` | `url-with-credentials` (len=15) | رمز DB inline برای سرویس sandooghyar | Medium (نام `…_dev` نشان می‌دهد dev است، ولی در repo عمومی dev/prod فرقی نمی‌کند) |
| ۴ | `src/gold_desk/api_token.py:28` | `getenv` با پیش‌فرض literal | اگر `GOLD_API_TOKEN_SALT` ست نشود، هش همهٔ توکن‌ها با salt معلوم محاسبه می‌شود | **Critical برای prod** — رفعش در `handoff_frontend_to_backend.md §۵` (فایل Python، محدودهٔ من نیست). ⚠️ این مورد را `scan_secrets.py` **نمی‌گیرد** (نام متغیر، نه literal)؛ قاعدهٔ `env-getenv-hardcoded-default` در `.gitleaks.toml` آن را می‌گیرد — تأییدشده با اجرا |
| ۵ | `docs/SECRETS_ROTATION_2026-09-16.md:13-15` | reprint شش مقدار قدیمی | سند «چرخش» قبلی، خودِ مقادیر لو‌رفته را دوباره چاپ کرده بود | **ماسک شد** (۹ occurrence → `<masked-from-history>`)؛ حالا در این فایل چیزی نیست |
| ۶ | `docs/analysis/02_backend_infra.md:538` | `url-with-credentials` (len=16) | گزارش ممیزی دستیار دیگر، مقدار رمز Redis را در جدول چاپ کرده | **فقط‌خواندنی برای من** ⇒ دست نزدم. از صاحب گزارش می‌خواهم ماسک کند. فعلاً با `--exclude '(^|/)docs/analysis/'` از قدم blocking بیرون است و **اسکریپت هر فایل ردشده را چاپ می‌کند** تا exclude راه پنهان‌کاری نشود. نکتهٔ تسکین‌دهنده: کل `docs/analysis/` **untracked** است (`git status: ?? docs/analysis/`) ⇒ در repo منتشر نشده |
| ۷ | `docs/git-history-rotation.md:5,6,31,32,45` (نسخهٔ پیش از این رفع) | reprint دو credential ردیف ۲ در **فایل track‌شده** | سند راهنمای پاک‌سازی تاریخچه، خودش همان دو مقدار را plaintext چاپ کرده بود (خط‌های ۵/۶ در Context و ۳۱/۳۲ در بلوک `secrets.txt` و ۴۵ داخل فرمان `grep -E`). ⚠️ `scan_secrets.py` **نگرفتش**: خط ۳۱/۳۲ مقدار تنها در خط است — نه `key=` نه URL ⇒ هیچ الگویی تطبیق نمی‌دهد. کشف با روش «دانشنامهٔ مقدارهای شناخته‌شده»: decode از manifest + جست‌جوی همان رشته در همهٔ ۱۲٬۹۲۵ فایل track‌شده | **High** — **ماسک شد** (۶ occurrence → `<masked-from-history>`)؛ قدم‌های ۳/۴/۵ سند به `secrets.txt` **خارج از repo** تغییر کرد تا دستورالعمل اجرایی بماند و دوباره مقدار چاپ نکند |

جمع‌بندی عددی: **۱۰ یافته از اسکنر الگومحور در درخت track‌شده** (۵ نیازمند اقدام:
ردیف‌های ۱، ۲، ۳، ۴، ۶ + ۵ بی‌خطر: §۳) — **و دو مکان بیشتر که اسکنر الگومحور ندید**
(ردیف ۷ = reprint در `docs/git-history-rotation.md`، و خط ۴۹ همان فایل compose ردیف ۲).
پس شمارِ واقعی نیازمند اقدام **۷** است، نه ۵. این دو با روش «دانشنامهٔ مقدارهای
شناخته‌شده» پیدا شدند (§۶)؛ اعداد قدیمیِ «۱۰ یافته / ۵ اقدام» که در نسخهٔ اول این
سند و در CHANGELOG نوشته بودم، کمتر از واقعیت بود.

### ۲-الف) مالکیت سه فایل بالا — تصحیح ادعای قبلی خودم

در نسخهٔ اول، ردیف‌های ۲ و ۳ را «خارج از محدوده» نوشته بودم. **اشتباه بود.**
محدودهٔ من در مرحلهٔ ۱ این‌طور ثبت شد (`docs/fixes/handoff_frontend_to_ops_env.md:23`):
«`docker-compose*.yml`, `monitoring/`, `tests/load/`» — و `docker-compose*` یک glob است
که `docker-compose.decision-engine.yml` و `docker-compose.sandooghyar.yml` را هم می‌گیرد.
پس رفع آن دو فایل **کار من است**، نه handoff. چون تغییرشان یک اثر بیرونی دارد
(هر کس این composeها را بالا بیاورد تا مقدار env ست نشود می‌ایستد) انجامش را به
تأیید شما موکول کردم؛ اسلایس‌ها:

| اسلایس | فایل | تغییر | پیامد |
|---|---|---|---|
| K1 | `docker-compose.decision-engine.yml:73,74,76` | inline → `${DECISION_ENGINE_DB_PASSWORD:?…}` | `docker compose -f docker-compose.decision-engine.yml up` تا `.env` ست نشده خطا می‌دهد (عمدی، fail-closed) |
| K2 | `docker-compose.sandooghyar.yml:39` | همین الگو | همان |
| K3 | `k8s/decision-engine-secret.yaml` | حذف سه مقدار، یا تبدیل به `stringData` با placeholder و کامنت «از secret manager/kubeseal بیاید» | `kubectl apply -f` تنها دیگر کافی نیست؛ manifest باید با Sealed Secrets/External Secrets جایگزین شود (`docs/security/secret_rotation.md §۲`) |
| K4 | `.env.example` | افزودن نام سه کلید جدید (K1/K2) با مقدار خالی | بدون مقدار واقعی |

`k8s/**` در هیچ‌یک از سه فهرست مالکیت نیست ⇒ **توصیهٔ من: به من (دستیار ۳) داده شود**،
چون (الف) کلاس رفعش manifest/env است نه کد اپ، (ب) برادرهایش (`docker-compose*.yml`،
`monitoring/`، `.env.example`، `docs/security/`) همین حالا محدودهٔ من‌اند، (ج) دستیار ۲
محدوده‌اش `src/gold_desk/**` است و دستیار ۱ فقط پایتون موتور. اگر ترجیح می‌دهید
جداسازی سرویس را حفظ کنیم (decision-engine سرویسی غیر از gold است)، آنگاه باید
چهارمین محدودهٔ «deploy/ops» تعریف شود؛ تا آن لحظه دست نمی‌زنم.

## ۳) یافته‌های class‌شده به‌عنوان بی‌خطر (با دلیل)

| محل | نوع | چرا بی‌خطر |
|---|---|---|
| `core/security/secrets.py:28` | high-entropy (len=62) | الفبت تولید رمز، نه credential |
| `codal_data/*.json` (×۳) | high-entropy (len=46) | بخشی از URL سرویس Codal (cache-key base64 در path) — credential ما نیست |
| `reports/runs/2026-09-26_run_funds-all-code.txt:1658` | assignment | لاگ، **متن سورس** را echo کرده است (سطری که مقدار env را با fallback به `secrets.token_hex(32)` می‌خواند). نشت نیست؛ ولی دو نکته دارد که در §۷ آمده |

جمع‌بندی: **۷ مورد نیازمند اقدام** (ردیف‌های ۱–۴، ۶ و ۷؛ ردیف ۵ و ۷ ماسک شدند) و
**۵ مورد بی‌خطر**.

> در نسخهٔ اول این گزارش «۲۸ یافته / ۵ بی‌خطر» نوشته بودم؛ بعد از چهار اصلاح
> اسکنر (از جمله رفع باگ صفر‌کاذب `--files` با دایرکتوری) اعداد بالا جایگزین شد.
> یافته‌های `tests/` و `frontend/src/__tests__/` که در §۳ نسخهٔ قبل بودند، حالا
> در خودِ اسکنر به‌عنوان fixture طبقه‌بندی می‌شوند (با `--include-placeholders`
> دیده می‌شوند: ۱۱۶ مورد).

## ۴) دو نشتی که در این رفع حذف شدند و هنوز در تاریخچه‌اند

این مهم‌ترین بخش گزارش است.

| | |
|---|---|
| محل اولیه | `docker-compose.yml` — پیش‌فرض `DEV_REDIS_PASSWORD` (۱۶ کاراکتر) و پیش‌فرض `DEV_JOB_QUEUE_TOKEN` (۱۶ کاراکتر) |
| وضعیت درخت کار | **حذف شده** — هر دو به `${VAR:?…}` تبدیل شدند. اسکنر روی `docker-compose.yml` فعلی هیچ نمی‌گیرد (تأییدشده). |
| وضعیت در HEAD repo | هنوز در `HEAD:docker-compose.yml` هستند (تأییدشده با `git show`) |
| کامیت‌های حاوی مقدار رمز Redis | **۲** کامیت: `f71d527d` و `3c6103b1` |
| کامیت‌های حاوی مقدار توکن صف | **۱** کامیت: `3c6103b1` |
| آیا منتشر شده؟ | بله. `3c6103b1` روی `origin/main` و چند branch دیگر است؛ `f71d527d` روی `origin/feature/gold-platform`. remote = `github.com/hosseinmbeiygi-cmd/temce` |
| ⚠️ نکتهٔ تکان‌دهنده | کامیت `3c6103b1` پیامش `chore(security): rotate leaked dev credentials …` است. یعنی **چرخش قبلی با commit کردن مقدار تازه انجام شده** — که دقیقاً همان اشتباه است: مقدار تازه هم لحظهٔ push لو می‌رود. و بعد از آن چرخش، رمز Redis **دوباره** در `f71d527d` برگشته. این سومین تکرار همین الگو است. |

**پس:** پاک‌کردن تاریخچه به‌تنهایی چیزی را امن نمی‌کند. اول **چون‌بَدِل** (rotate)،
بعد در صورت نیاز پاک‌سازی تاریخچه. راهنمای قدم‌به‌قدم:
`docs/security/secret_rotation.md`.

## ۵) کاری که من در این رفع کردم / نکردم

انجام‌شده (در محدودهٔ مالکیت من):
- حذف دو پیش‌فرض secret از `docker-compose.yml` و `:?` اجباری (I3، مرحلهٔ ۱).
  **تأییدشده با اجرا**: اسکنر روی `docker-compose.yml` فعلی صفر می‌گیرد، روی
  `HEAD:docker-compose.yml` همان الگو را ۵ بار می‌گیرد.
- `.env.example`: افزودن `GOLD_API_TOKEN_SALT`، `DEV_JOB_QUEUE_TOKEN`،
  `GOLD_BACKUP_DIR`، `GOLD_BACKUP_RETENTION_DAYS` بدون هیچ مقدار واقعی (S2).
- `.gitleaks.toml` با ۶ قانون repo-محور + allowlist فقط برای placeholder/fixture.
  همهٔ regexها **RE2-safe** بررسی شدند (بدون lookahead/lookbehind و بدون flag `x`
  که Go پشتیبانی نمی‌کند) — و همین بررسی، دو باگ خودم را گرفت: نسخهٔ اول
  `(?!\s*\$\{)` و `(?xi)` داشت که در gitleaks کامپایل نمی‌شود.
- `.github/workflows/ci.yml`: دو قدم اضافه شد — «Secret scan — owned scope
  (blocking)» با `scan_secrets.py` و «Secret scan — full tree (advisory)» که اگر
  باینری gitleaks روی runner بود، درخت کامل را `--redact` می‌زند.
  **قدم blocking محلی اجرا و پاس شد** (exit 0).
- `docs/SECRETS_ROTATION_2026-09-16.md`: ۹ reprint مقدار لو‌رفته ماسک شد.
- `docs/secrets-management.md:27-29`: مثال‌های `real-password` → `change-me-…`
  (هم placeholder شدن، هم دیگر اسکنر را فعال نمی‌کنند).
- `.gitleaks.toml` در ریشهٔ repo، همان فایلی است که `secrets-scan.yml` (اقدام
  موجود gitleaks) به‌طور پیش‌فرض از ریشه برمی‌دارد؛ پس قواعد تازه بدون ویرایش آن
  workflow اعمال می‌شوند.
- ماسک‌کردن سه مقداری که خودم در مرحلهٔ ۱ در `docs/fixes/*` و
  `docs/golddesk_backup.md` نوشته بودم (نقض قاعدهٔ ۵ توسط خودم؛ اصلاح شد).

انجام‌**نشده** (خارج از محدوده یا عمداً):
- `src/gold_desk/api_token.py:28` (پیش‌فرض salt) → `handoff_frontend_to_backend.md §۵`.
- `k8s/decision-engine-secret.yaml` + دو فایل compose سرویس‌های دیگر: **اصلاح شد که
  دو فایل compose در محدودهٔ من‌اند** (§۲-الف)؛ هنوز دست نزده‌ام چون هر سه اسلایس
  K1–K3 رفتار بالا‌آوردن سرویس را عوض می‌کنند و منتظر تأیید شما هستم. مالکیت
  `k8s/**` هم در هیچ فهرست سه‌گانه‌ای نیست (توصیه: دستیار ۳).
- `docs/analysis/02_backend_infra.md:538` → فایل فقط‌خواندنی؛ از صاحبش ماسک
  می‌خواهم (ردیف ۶ §۲).
- اجرای `git filter-repo` → **عمداً اجرا نکردم**؛ فقط راهنما نوشته شده
  (`docs/security/secret_rotation.md §۷`).

## ۶) چیزی که این اسکن تضمین نمی‌کند

- gitleaks واقعی روی این ماشین نصب نیست؛ `.gitleaks.toml` را با (الف) پارس TOML،
  (ب) سازگاری RE2، (ج) گرفتن ۵ هدف واقعی با regex معادل در Python سنجیدم. اجرای
  واقعی آن **در اولین run CI** معلوم می‌شود و ممکن است findings بیشتری بدهد
  (قواعد builtin gitleaks بازتر از rules من‌اند).
- مقادیر لو‌رفته در **زیرشاخه‌های `origin`** و forkها قابل اسکن نیستند؛ هر مقداری
  که در §۴ آمده باید فرض کند عمومی شده است.
- این اسکن درخت کاری/track‌شده را می‌بیند، نه همهٔ اشیاء تاریخچه (برای آن:
  `gitleaks git --config .gitleaks.toml .` بعد از نصب gitleaks).
- **اسکنر الگومحور مقدارِ «برهنه» را نمی‌بیند.** این نسخهٔ گزارش خودش یک نمونهٔ
  عملی از ضعف روش است: `docs/git-history-rotation.md` دو credential واقعی را در
  خط‌هایی چاپ کرده بود که هیچ `key=`، هیچ `:` و هیچ URLی نداشتند ⇒ صفر تطبیق، و من
  در نسخهٔ اول «۱۰ یافته / ۳ credential واقعی» نوشتم که **کم‌شمار** بود. راه رفعی که
  کار کرد: «دانشنامهٔ مقدارهای شناخته‌شده» — مقادیر decode‌شده از یک manifest را
  می‌گیرید و رشته‌های *همان* را در همهٔ فایل‌های track‌شده می‌جوئید (۱۲٬۹۲۵ فایل،
  ۱۲ occurrence در ۳ فایل). هر اسکنر secret در دنیا همین را با gitleaks/`--reveal`
  روی تاریخچه می‌کند؛ تا باینری gitleaks روی این ماشین نصب نشود، این cross-check
  دستی جای آن را می‌گیرد. قدم blocking CI هم الگومحور است ⇒ **صفر کاذب در جهت
  برعکس**: reprint بدون الگو را بلاک نمی‌کند.
- entropy-basedها مقادیر کوتاه‌تر از ۱۲ کاراکتر را نمی‌بینند؛ یک رمز ۸ رقمی ضعیف
  از این اسکن در امان می‌ماند. این محدودیتِ entropy است، نه ضعف rule.

## ۷) دو نکتهٔ جانبی که در همان لاگ دیدم (خارج از محدوده، فقط ثبت)

`reports/runs/2026-09-26_run_funds-all-code.txt:1658` سطحی‌ترین ظاهر را دارد ولی
دو چیز واقعی را نشان می‌دهد:
1. **لاگ‌های run، سورس را در فایل track‌شده کپی می‌کنند.** اگر روزی مقدار
   env-محور در همان اسنیپت باشد، لاگ آن را منتشر می‌کند. `reports/runs/**` باید
   یا `.gitignore` شود یا از اسکن خارج نگرد.
2. خط سورس به شکل `… or secrets.token_hex(32)` است: اگر env ست نشده باشد، هر
   process یک رمز **موقت** می‌سازد. یعنی JWT های سرویس بعد از restart باطل و در
   چند-replicas بین پروسه‌ها ناسازگار می‌شوند. این باگِ عملکردی است نه نشت، و
   مال سرویس sandooghyar است — برای صاحب همان سرویس ثبت شد.
