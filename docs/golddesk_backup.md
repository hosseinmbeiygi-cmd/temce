# پشتیبان‌گیری و بازگردانی دادهٔ GoldDesk (I4)

نویسنده: دستیار ۳ (`fix/frontend-infra`) — تاریخ: ۲۰۲۶-۱۰-۲۴

> **چرا این سند وجود دارد:** GoldDesk تک‌کاربره است. جدول‌های طلا سابقهٔ واقعی
> خرید/فروش کاربر را نگه می‌دارند و هیچ مسیر بازگشت UI وجود ندارد. اگر یک حذف
> سخت یا یک migration خراب شود، تنها چیزی که داده را برمی‌گرداند همین dump است.

---

## ۱) چه چیزی پشتیبان گرفته می‌شود

درون اسکریپت، دامنهٔ پیش‌فرض `gold` است؛ یعنی ۹ جدولِ این ماژول (همان‌ها که در
`src/gold_desk/models.py` تعریف شده‌اند):

| # | جدول | چرا حیاتی است |
|---|---|---|
| ۱ | `gold_holdings` | دارایی‌های کاربر؛ منبع P&L و گزارش مالیاتی |
| ۲ | `gold_trades` | سابقهٔ معاملات؛ با `ON DELETE SET NULL` به holdings وصل است |
| ۳ | `gold_dca_plans` | پلن‌های DCA و وضعیت اجرای پله‌ها |
| ۴ | `gold_portfolio_values` | نقاط زمانی ارزش پرتفو (سری TWR) |
| ۵ | `gold_score_history` | تاریخچهٔ امتیاز/تصمیم |
| ۶ | `gold_snapshots` | اسنپ‌شات‌های ذخیره‌شده |
| ۷ | `gold_fund_nav` | NAV صندوق‌ها |
| ۸ | `gold_alert_rules` | قواعد هشدار کاربر |
| ۹ | `gold_alert_events` | رویدادهای هشدار (خوانده/ناخوانده) |

برای دامنهٔ کل دیتابیس: `GOLD_BACKUP_SCOPE=all` (پیش‌فرض: `gold`).

## ۲) نصب cron (شبانه)

```cron
15 2 * * *  GOLD_BACKUP_DIR=/var/backups/golddesk /srv/temce/scripts/backup_golddesk.sh >> /var/log/golddesk-backup.log 2>&1
```

نگهداری: `GOLD_BACKUP_RETENTION_DAYS` (پیش‌فرض **۱۴** روز). اسکریپت فقط فایل‌هایی
را حذف می‌کند که خودشان با پیشوند `goldbackup-` ساخته شده‌اند؛ هیچ فایل دیگری
در پوشهٔ مقصد دست نمی‌خورد (این رفتار در `scripts/test_backup_golddesk.sh` تست
شده است).

متغیرهای محیطی:

| نام | پیش‌فرض | توضیح |
|---|---|---|
| `GOLD_BACKUP_DIR` | `./backups/golddesk` | مقصد نسخه‌ها |
| `GOLD_BACKUP_RETENTION_DAYS` | `14` | عمر نسخه‌ها |
| `GOLD_BACKUP_SCOPE` | `gold` | `gold` یا `all` |
| `POSTGRES_USER` / `POSTGRES_DB` | `quant_dev` / `tse_quant` | همان مقدار compose |
| `GOLD_BACKUP_SERVICE` | `timescaledb` | نام سرویس دیتابیس در compose |
| `GOLD_BACKUP_COMPOSE_FILE` | `docker-compose.yml` | فایل compose مقصد |

## ۳) بازگردانی

**همیشه اول روی یک دیتابیس جدا آزمایش کنید، بعد روی اصلی.**

```bash
# الف) نسخه را پیدا و سالم‌سنجی کنید
ls -1t /var/backups/golddesk/goldbackup-*.dump | head -1
sha256sum -c /var/backups/golddesk/goldbackup-<STAMP>.dump.sha256
pg_restore --list /var/backups/golddesk/goldbackup-<STAMP>.dump | head

# ب) روی کانتینر در حال اجرا: اول copy، بعد restore در یک اسکیما/دیتابیس تازه
docker compose -f docker-compose.yml cp \
  /var/backups/golddesk/goldbackup-<STAMP>.dump tse_timescaledb:/tmp/g.dump

# حالت ۱ — دیتابیس تازه (پیشنهادی، بدون خطر روی دادهٔ فعال)
docker compose -f docker-compose.yml exec -T timescaledb \
  createdb -U quant_dev tse_quant_restored
docker compose -f docker-compose.yml exec -T timescaledb \
  pg_restore -U quant_dev -d tse_quant_restored --no-owner /tmp/g.dump

# حالت ۲ — بازنویسی همان دیتابیس (مخرب؛ فقط با تأیید صریح و پس از یک نسخهٔ فوری)
docker compose -f docker-compose.yml exec -T timescaledb \
  pg_restore -U quant_dev -d tse_quant --clean --if-exists --no-owner /tmp/g.dump
```

**راستی‌آزمایی بعد از بازگردانی** — شمارش ردیف‌های ۹ جدول باید با خروجی
`pg_restore --list` و با انتظار کاربر هم‌خوان باشد:

```bash
docker compose -f docker-compose.yml exec -T timescaledb psql -U quant_dev -d tse_quant \
  -c "select 'gold_holdings' t, count(*) from gold_holdings
      union all select 'gold_trades', count(*) from gold_trades
      union all select 'gold_dca_plans', count(*) from gold_dca_plans
      union all select 'gold_portfolio_values', count(*) from gold_portfolio_values
      union all select 'gold_score_history', count(*) from gold_score_history
      union all select 'gold_snapshots', count(*) from gold_snapshots
      union all select 'gold_fund_nav', count(*) from gold_fund_nav
      union all select 'gold_alert_rules', count(*) from gold_alert_rules
      union all select 'gold_alert_events', count(*) from gold_alert_events;"
```

و در UI: `/gold/portfolio` باید همان دارایی‌ها و همان `cost_basis` را نشان دهد؛
`/portfolio/tax` باید همان FIFO قبلی را بدهد.

## ۴) چیزی که این سند و این تست ثابت **نمی‌کند**

`scripts/test_backup_golddesk.sh` با `pg_dump`/`pg_restore` ساختگی روی `PATH`
منطق اسکریپت را می‌آزماید (ساخت نسخه، اعتبارسنجی، چک‌سام، retention،
fail-closed بودن). **این چیزی دربارهٔ بازگردانی واقعی ثابت نمی‌کند.**

برای همان کار، اسکریپت دوم نوشته شده است:

```bash
bash scripts/test_restore_golddesk.sh            # چرخهٔ کامل: dump → کانتینر
                                               # یکبارمصرف → restore → مقایسهٔ
                                               # ۹ جدول + آخرین snapshot → حذف
bash scripts/test_restore_golddesk.sh --dry-run  # فقط نمایش نقشه
```

وضعیت اجرا روی این ماشین (۲۰۲۶-۱۰-۲۴): **انجام نشد.**

```
$ bash scripts/test_restore_golddesk.sh
NOT EXECUTED — daemon داکر در دسترس نیست (Docker Desktop بالا نیست؟)…
EXIT=3
```

- `psql` / `pg_dump` / `pg_restore` روی این ویندوز نصب نیستند؛
- باینری `docker` هست ولی **daemon** بالا نیست؛
- سرویس `timescaledb` هم در این ماشین running نیست.

اسکریپت عمداً در نبود پیش‌نیاز **کد خروج ۳** و پیام «NOT EXECUTED» می‌دهد تا هیچ‌کس
نتواند «آزمون اجرا شد» را با «آزمون پاس شد» اشتباه بگیرد.

**دستی که باید اجرا کنید** (روی سروری که دیتابیس GoldDesk آنجا running است):

```bash
cd /srv/temce
docker compose -f docker-compose.yml up -d timescaledb
bash scripts/test_restore_golddesk.sh
# انتظار: 9/9 جدول «ok» و «آخرین snapshot برابر» ⇒ آنگاه I4 را fixed بنویسید.
```

تا پیش از یک اجرای سبز، I4 **partial** است و عبارت «پشتیبان‌گیری تست‌شده» را
به‌کار نبرید.

## ۵) متغیرهای جدیدِ اجباری (جنبهٔ امنیتی I3)

`docker-compose.yml` از این نسخه دو مقدار را **بدون پیش‌فرض** و با `:?` می‌خواهد؛
بد آن‌ها `docker compose up` همان اول fail می‌شود (این خواستهٔ I3 است):

- `GOLD_API_TOKEN_SALT` — salt هش API tokenهای طلا.
  ⚠️ اگر مقدار تازه‌ای بگذارید، tokenهای صادرشده با salt قبلی دیگر معتبر نیستند
  و باید از `/gold/tokens` بازصدور شوند.
- `DEV_JOB_QUEUE_TOKEN` و `DEV_REDIS_PASSWORD` — تا پیش از این به‌صورت
  **پیش‌فرضِ commit‌شده** در فایل بودند (یک رمز Redis و یک توکن صف job؛ مقدارها اینجا نمی‌آید — قاعدهٔ ۵. فهرست محل‌ها: `docs/security/secret_scan_report.md`).
  این دو رشته حالا در فایل نیستند، اما چون در تاریخ repo منتشر شده‌اند باید
  **چون‌بدل** شوند (در همان `.env` و در هر سرویس دیگری که دوباره استفاده‌شان کرده).

فایل `.env.example` در محدودهٔ مالکیت این دستیار نیست و دو خطِ بالا را ندارد؛
درخواست افزودن در `docs/fixes/handoff_frontend_to_ops_env.md` آمده است.
