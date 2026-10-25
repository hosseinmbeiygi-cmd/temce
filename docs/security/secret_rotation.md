# چرخش secret در temce / GoldDesk (S3)

تاریخ: ۲۰۲۶-۱۰-۲۴ · یافته‌های خام و طبقه‌بندی: `docs/security/secret_scan_report.md`

> ## ⚠️ سه قانون این سند
> 1. **اول چون‌بَدِل، بعد پاک‌سازی.** یک secret که یک‌بار push شده، سوخته است؛
>    حذفش از تاریخچه آن را زنده نمی‌کند. کسی که clone گرفته، مقدار را دارد.
> 2. **مقدار تازه را در یک فایل commit‌شده نگذارید.** این repo دقیقاً همین اشتباه
>    را سه بار کرده (بخش ۴ سند اسکن) — «چرخش» با commit کردن مقدار جدید، فقط یک
>    نشت جدید است.
> 3. **دستورات پاک‌کردن تاریخچه (§۶) را خودتان و بدون بکاپ اجرا نکنید.** من آن‌ها
>    را **اجرا نکردم** و در این repo هیچ rewrite انجام نشده است.

---

## ۰) چه چیزهایی باید بچرخند

| # | چه چیزی | محل امروز | شدت |
|---|---|---|---|
| ۱ | `SECRET_KEY` امضای JWT/سشن | `k8s/decision-engine-secret.yaml:26` | Critical **مشروط**: مقدار فعلی عینِ متنِ «replace before production use» است (کلید واقعی لو نرفته). اگر حتی یک محیط با همین manifest اعمال شده باشد، این ردیف Critical قطعی است — کلید امضا عمومی است. |
| ۱-ب | رمز DB و رمز Redis سرویس decision-engine (نسخهٔ base64) | `k8s/decision-engine-secret.yaml:20,23` | High — همان دو مقداری که inline در `docker-compose.decision-engine.yml` هستند، پس credential واقعی‌اند و روی `origin/main` منتشر شده‌اند |
| ۲ | salt توکن API طلا | پیش‌فرض hard-code در `src/gold_desk/api_token.py:28` | Critical (prod) |
| ۳ | رمز Redis dev | در تاریخچه: `docker-compose.yml` (حذف‌شده از درخت کار) | High |
| ۴ | توکن صف job | در تاریخچه: `docker-compose.yml` (حذف‌شده از درخت کار) | High |
| ۵ | رمز DB سرویس decision-engine | `docker-compose.decision-engine.yml:73,74,76` (سه `DATABASE_URL*`) + همان مقدار در `k8s/decision-engine-secret.yaml:20` | High |
| ۶ | رمز DB سرویس sandooghyar | `docker-compose.sandooghyar.yml:39` | Medium |
| ۷ | هر API token طلای صادرشده با salt پیش‌فرض | `/gold/tokens` | High (وابسته به #۲) |
| ۸ | رمز DB/Redis prod، DSN Sentry، کلید BrsApi | خارج از repo (env/secret manager) | فقط اگر مشکوکید |

## ۱) ساخت مقدارهای تازه

```bash
openssl rand -hex 32      # برای هر کدام، جدا
```

هر مقدار **یک‌بار** و برای **یک** مصرف ساخته شود. یک مقدار را برای Redis و DB و
توکن صف به کار نبرید.

## ۲) محل نگهداری مقدار تازه (نه repo)

- dev: `.env` (در `.gitignore`) — الگوی فعلی repo همین است؛ `.env.example` فقط
  نام‌ها را با مقدار خالی دارد.
- k8s: Sealed Secrets یا External Secrets — الگو در
  `docs/secrets-management.md §Option A`؛ فقط خروجی `kubeseal` commit شود.
- docker-compose prod: `${VAR:?}` بدون پیش‌فرض (الگویی که در `docker-compose.yml`
  این رفع گذاشته شد).

## ۳) ترتیب اجرا (برنامهٔ توقف سرویس)

همهٔ این‌ها **خدمت را قطع می‌کنند**; در زمان کم‌ترافیک انجام دهید.

```bash
# ۰) اولین کار: نسخهٔ کامل. بعد از چرخش، مقادیر قدیمی دیگر بازگردانی‌شدنی نیستند.
GOLD_BACKUP_DIR=/var/backups/golddesk bash scripts/backup_golddesk.sh

# ۱) مقدارهای تازه را در محیط مقصد ست کنید (dev => .env ، prod => secret manager)
#    نام‌ها: DEV_POSTGRES_PASSWORD DEV_REDIS_PASSWORD DEV_JOB_QUEUE_TOKEN
#           GOLD_API_TOKEN_SALT SECRET_KEY
# ⚠️ هیچ‌کدام را در فایل commit‌شده ننویسید.

# ۲) restart تا همه از env تازه بخوانند
docker compose down && docker compose up -d
docker compose ps                          # همه healthy
curl -fsS http://localhost:8000/api/v1/gold/health    # 200 ⇒ redis_ok/db_ok true

# ۳) تأیید اینکه رمز قدیمی دیگر کار نمی‌کند (باید رد شود)
docker compose exec redis redis-cli -a '<رمز-قدیمی>' ping     # EXPECT: NOAUTH / invalid

# ۴) تأیید راه‌اندازی مجدد consumer ها (صف با توکن تازه احرا می‌شود)
docker compose logs --tail=50 worker | grep -i "queue\|auth" || true
```

## ۴) بازصدور API tokenهای طلا (بعد از چرخش salt)

`GOLD_API_TOKEN_SALT` در هش توکن‌ها مصرف می‌شود. با salt تازه:

- هر توکن صادرشده با salt قبلی **دیگر معتبر نیست** (auth رد می‌شود؛ این رفتار
  مطلوب است، نه باگ).
- ⚠️ **توکن‌ها بازیابی‌پذیر نیستند** — فقط هش ذخیره می‌شود، پس مقدار خام را هیچ‌کس
  از DB درنمی‌آورد. باید از نو صادر شوند.

```bash
# ۱) لیست توکن‌های موجود (بدون مقدار خام)
curl -H "Authorization: Bearer <jwt>" http://localhost:8000/api/v1/gold/tokens

# ۲) لغو تک‌تک توکن‌های قدیمی (UI: /gold/tokens ⇒ «لغو token»؛ یا:)
curl -X DELETE -H "Authorization: Bearer <jwt>" \
  "http://localhost:8000/api/v1/gold/tokens/<token_id>"

# ۳) صدور دوباره برای هر مصرف‌کننده (ربات تلگرام، Google Sheets، اپ)
curl -X POST -H "Authorization: Bearer <jwt>" \
  "http://localhost:8000/api/v1/gold/tokens?name=Telegram%20Bot&scopes=read"
#    ⚠️ مقدار خام **فقط یک‌بار** در پاسخ می‌آید؛ همان لحظه در محل مصرف کپی شود.

# ۴) جایگزینی در هر ابزار خارجی و تست:
curl -H "Authorization: Bearer <توکن-تازه>" http://localhost:8000/api/v1/gold/hot
```

مصرف‌کننده‌هایی که باید دستی به‌روز شوند: ربات تلگرام، Google Sheets/Apps Script،
اپ موبایل/Capacitor، هر cron یا اسکریپت خارجی، و `bearer_token_file` پرامتئوس
(بخش ۶).

## ۵) اسکن دوباره، بعد از چرخش

```bash
python scripts/scan_secrets.py            # باید صفر مورد در درخت کاری بماند
# با gitleaks واقعی (وقتی نصب شد):
gitleaks detect --config .gitleaks.toml --source . --no-git --redact
```

`--redact` را نگه دارید: بدون آن، خودِ ابزار لاگِ شما را به نشت تبدیل می‌کند.

## ۶) Prometheus و scope «metrics» (C9)

بعد از چرخش، token اسکرپ هم تازه می‌شود:

```bash
# مقدار تازه را در secret manager/k8s Secret بگذارید، نه در prometheus.yml
# مسیر فایل در monitoring/golddesk-prometheus.yml: authorization.credentials_file
```

⚠️ تا وقتی `Scope = Literal["read","write","admin"]` در `api_token.py:31` به
`metrics` گستر نیافته (درخواست در `handoff_frontend_to_backend.md §۵`)، هر توکن
`/metrics` با 401 جواب می‌دهد — صرف‌نظر از درست بودن مقدار.

## ۷) پاک‌کردن تاریخچهٔ git — توضیح، **نه دستور اجرا**

> 🛑 **این بخش را من اجرا نکردم و شما هم همین‌طور اجراش نکنید** مگر با: (الف)
> بکاپ کامل از همهٔ cloneها، (ب) توافق با همهٔ همکاران (هر branch و fork و CI
> cache که بازنویسی‌شده را داشته باشد باید force-push و re-clone شود)، (ج) آمادگی
> برای از دست دادن PR/مرجع‌های commit.
>
> و پیش از همه: **تا وقتی §۳ اجرا نشده، این کار بی‌فایده است.** اگر مقدار نو
> ساخته نشده باشد، پاک‌کردن تاریخچه فقط نشت را از دید شما پنهان می‌کند؛ مهاجم
> آن را در fork، در CI artifact، در صفحهٔ GitHub یا در cloneهای موجود دارد.

چرا پاک‌سازی تاریخچه به‌تنهایی کافی نیست:

- repo روی `origin` منتشر شده (`3c6103b1` روی `origin/main`) ⇒ هر کسی clone یا
  حتی صفحهٔ web را دیده، مقدار را دارد.
- GitHub پس از force-push، کامیت‌های بی‌فرزند (orphaned) را مدتی در cache نگه می‌دارد و لینک
  مستقیم shard/commit ممکن است کار کند (پشتیبانی GitHub برای prune کامل لازم است).
- PRها، Actions logs، و forkها بازنویسی نمی‌شوند.

اگر با وجود این‌ها می‌خواهید تاریخچه را تمیز کنید (روی **یک کپی** از repo، نه
روی working tree مشترک):

```bash
# 1) یک mirror تازه، نه کاری که در آن کار می‌کنید
git clone --mirror https://github.com/<org>/<repo>.git scrub.git
cd scrub.git

# 2) شناسایی دقیق اشیاء حاوی مقدار (از فایل env/secret manager، نه از تایپ)
#    توجه: مقدار را در یک فایل بگذارید تا در shell history نماند.
gitleaks git --config ../.gitleaks.toml --log-opts="--all" . --report-path leaks.json

# 3) بازنویسی (git-filter-repo ابزار استاندارد است؛ `filter-branch` منسوخ شده)
python3 -m pip install --user git-filter-repo
git filter-repo --replace-text <(sed 's/^/leaked-value-here==>REMOVED-BY-ROTATION/' /dev/null)

# 4) بازرسی، سپس force-push آگاهانه
git fsck --full
git push --force --mirror https://github.com/<org>/<repo>.git
```

`--replace-text` یک فایل نگاشت می‌خواهد که **سطر اولش مقدار لو‌رفته** است. آن فایل
باید ۰۶۰۰ باشد، در shell history نیفتد، و بعد از کار پاک شود. به همین دلیل اینجا
دستور آمادهٔ کپی‌کردن نمی‌گذارم.

## ۸) چک‌لیست نهایی

- [ ] نسخهٔ کامل گرفته شد و **بازگردانی‌اش آزموده شد** (`docs/golddesk_backup.md`)
- [ ] هر ۸ ردیف §۰ مقدار تازه دارند
- [ ] هیچ مقدار تازه در فایل commit‌شده نیست (`python scripts/scan_secrets.py` → صفر)
- [ ] `python scripts/scan_secrets.py` و `gitleaks detect` صفر یافته‌ی واقعی
- [ ] همهٔ توکن‌های طلا بازصدور و در ابزارها جایگزین شدند
- [ ] رمزهای قدیمی واقعاً رد می‌شوند (آزمون §۳/۳)
- [ ] `/gold/health` سبز است و `/metrics` با توکن `metrics` جواب می‌دهد (بعد از C9)
- [ ] ownerهای branchهای دیگر از بازنویسی تاریخچه باخبر شدند (اگر §۷ اجرا شد)
