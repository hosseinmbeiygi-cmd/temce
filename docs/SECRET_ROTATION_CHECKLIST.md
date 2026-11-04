# چک‌لیست چرخش اسرار — Iran Market Platform

> **چرا این فایل مهم است:** کلیدهای BrsApi و AvalAI و رمزهای توسعه در سورس هاردکد
> بودند و در تاریخچهٔ git ثبت شده‌اند. پاک‌کردن آن‌ها از کد **کافی نیست** — باید فرض
> کنید لو رفته‌اند. این کار فقط از دست شما (دسترسی به پنل سرویس‌ها) برمی‌آید.

## ۱. کلیدهایی که باید چرخانده شوند

| # | چه چیزی | کجا استفاده می‌شود | متغیر محیطی |
|---|---|---|---|
| ۱ | کلید BrsApi | `z.py`, `collector.py`, `script.py`, `scripts/backfill_funds_only.py` | `BRSAPI_KEY` |
| ۲ | کلید AvalAI (سرویس LLM) | `assistant.py` | `AVALAI_API_KEY` |
| ۳ | رمز PostgreSQL توسعگی | docker-compose (dev/decision-engine/sandooghyar) + `.env` | `DEV_POSTGRES_PASSWORD` / `POSTGRES_PASSWORD` |
| ۴ | هر کلید دیگری که در گزارش ریویو یا تاریخچهٔ git raw دیده شد | — | — |
| ۵ | `SECRET_KEY` اپلیکیشن (اگر پیش‌فرض بوده) | JWT/session | `SECRET_KEY` |

> بعد از چرخش، مقدار جدید را **فقط** در `.env` محلی یا secret manager بگذارید؛
> در `.env.example` صرفاً نام متغیر (بدون مقدار) بماند.

## ۲. گام‌های انجام

1. **پنل هر سرویس:** کلید قدیمی BrsApi را revoke و کلید جدید بسازید. همین برای AvalAI.
2. **رمز دیتابیس dev** را عوض کنید: `ALTER USER ... WITH PASSWORD '...'`.
3. `.env` را به‌روز کنید (خرج‌شده از git است — تأیید کنید `.env` در `.gitignore` هست).
4. سرویس‌ها را restart کنید و صحت را بسنجید:
   ```bash
   venv/Scripts/python.exe scripts/check_secrets.py      # نباید چیزی پیدا کند
   venv/Scripts/python.exe -m pytest tests/unit/test_check_secrets_and_gold_scope.py
   ```
5. اگر رمز Postgres عوض شد، docker-compose را با رمز جدید بالا بیاورید (متغیر
   `${DEV_POSTGRES_PASSWORD:?...}` دیگر اجباری است و بدون مقدار خطا می‌دهد).

## ۳. پاک‌کردن تاریخچهٔ git (اختیاری، نیاز به تأیید شما)

بعد از چرخش کلیدها، مقدار **قدیمی** دیگر ارزشی ندارد؛ ولی اگر بخواهید از تاریخچه هم
پاک شود (خروجی `.git` کوچک‌تر، انتشار عمومی امن‌تر):

> ⚠️ بازنویسی تاریخچه عملیاتی **مخرب** است: هش commitها عوض می‌شود و هر clone/PR
> باز باید همگام شود. قبل از اجرا، بکاپ بگیرید و تیم را مطلع کنید. **این کار را این
> سند اجرا نمی‌کند؛ فقط مسیر را می‌دهد.**

```bash
# نصب: pip install git-filter-repo   (یا brew install git-filter-repo)
git filter-repo --replace-text replacements.txt   # فایل شامل: <secret>==>***REMOVED***
git filter-repo --path z.py.bak --invert-paths     # حذف کامل فایل پشتیبان
git push --force --all && git push --force --tags  # فقط با تأیید صریح
```

جایگزین سبک‌تر (بدون بازنویسی): کلید را revoke کنید و کار تمام است. برای اکثر تیم‌ها
همین کافی است.

## ۴. جلوگیری از تکرار

- اسکنر `scripts/check_secrets.py` در pre-commit نصب است و همان کلیدهای واقعی،
  secret‌های عمومی و رمزهای compose را می‌گیرد.
- توصیه: همان اسکنر را در CI هم اجرا کنید (مرحلهٔ جدا) تا bypass hook نگردد.
- برای پوشش وسیع‌تر می‌توانید `gitleaks`/`trufflehog` را به CI اضافه کنید؛ اما اسکنر
  فعلی برای کلیدهای واقعی این مخزن کافی است.
