#!/usr/bin/env bash
# ── I4 — پشتیبان شبانهٔ دادهٔ GoldDesk ────────────────────────────────────
#
# چرا این مهم‌ترین شبکهٔ ایمنی این محصول است: GoldDesk تک‌کاربره است و داده‌ای
# که اینجا می‌نشیند (gold_holdings، gold_trades، gold_dca_plans) سابقهٔ مالیاتی
# کاربر است. هیچ نسخهٔ دوم، هیچ user_id و هیچ بازگشت UI وجود ندارد؛ اگر یک
# حذف سخت خراب شود، فقط همین dump برمی‌گرداند.
#
# طرز اجرا (cron شبانه، ۰۲:۱۵ به وقت سرور):
#   15 2 * * *  GOLD_BACKUP_DIR=/var/backups/golddesk /srv/temce/scripts/backup_golddesk.sh >> /var/log/golddesk-backup.log 2>&1
#
# نگهداری: ۱۴ نسخهٔ آخر (retention) — فقط فایلهایی که خودِ همین اسکریپت با
# پیشوند goldbackup- ساخته حذف می‌شوند؛ هیچ فایل دیگری لمس نمی‌شود.
#
# روش بازگردانی و نحوهٔ راستی‌آزمایی: docs/golddesk_backup.md

set -euo pipefail

# ── پیکربندی (همه از env قابل بازنویسی) ─────────────────────────────────
BACKUP_DIR="${GOLD_BACKUP_DIR:-./backups/golddesk}"
RETENTION_DAYS="${GOLD_BACKUP_RETENTION_DAYS:-14}"
# gold = فقط جدول‌های طلا (پیش‌فرض) | all = کل دیتابیس
BACKUP_SCOPE="${GOLD_BACKUP_SCOPE:-gold}"
PG_USER="${POSTGRES_USER:-quant_dev}"
PG_DB="${POSTGRES_DB:-tse_quant}"
COMPOSE_SERVICE="${GOLD_BACKUP_SERVICE:-timescaledb}"
COMPOSE_FILE="${GOLD_BACKUP_COMPOSE_FILE:-docker-compose.yml}"
PREFIX="goldbackup"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# ── انتخاب راه دسترسی به pg_dump ────────────────────────────────────────
# در محیط توسعهٔ ویندوزی این ماشین psql/pg_dump نصب نیست (see
# docs/golddesk_backup.md §۴)؛ پس اسکریپت از طریق کانتینر دیتابیس کار می‌کند و
# فقط وقتی pg_dump بومی هست آن را ترجیح می‌دهد.
run_pg_dump() {
  local out="$1"
  if command -v pg_dump >/dev/null 2>&1 && [[ -n "${PGHOST:-}" ]]; then
    log "pg_dump بومی (PGHOST=$PGHOST)"
    pg_dump -U "$PG_USER" -d "$PG_DB" -Fc $TABLES_ARG --file="$out"
  elif command -v docker >/dev/null 2>&1; then
    log "pg_dump داخل کانتینر $COMPOSE_SERVICE"
    # -T تا tty نباشد و باینری سالم بماند؛ خروجی با redirect به بیرون می‌آید.
    docker compose -f "$COMPOSE_FILE" exec -T "$COMPOSE_SERVICE" \
      pg_dump -U "$PG_USER" -d "$PG_DB" -Fc $TABLES_ARG > "$out"
  else
    die "نه pg_dump بومی و نه docker در دسترس است — هیچ راهی برای dump نیست."
  fi
}

case "$BACKUP_SCOPE" in
  gold)
    # فقط جدولهای طلا. اگر روزی FK از جدول دیگری به اینها بیاید، SCOPE=all بگیرید.
    TABLES_ARG="-t 'gold_*'"
    ;;
  all)
    TABLES_ARG=""
    ;;
  *)
    die "GOLD_BACKUP_SCOPE باید gold یا all باشد (الان: $BACKUP_SCOPE )"
    ;;
esac

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/$PREFIX-$STAMP.dump"
TMP="$OUT.partial"

log "شروع پشتیبان | scope=$BACKUP_SCOPE dir=$BACKUP_DIR"

# .partial تا نصفهٔ write نشده به‌عنوان نسخهٔ معتبر دیده نشود.
run_pg_dump "$TMP" || { rm -f "$TMP"; die "pg_dump شکست خورد."; }

# ── راستی‌آزمایی قبل از اعلام موفقیت ────────────────────────────────────
# یک dump که باز نشود فقط توهم امنیت است.
[[ -s "$TMP" ]] || { rm -f "$TMP"; die "خروجی خالی است."; }

if command -v pg_restore >/dev/null 2>&1; then
  pg_restore --list "$TMP" >/dev/null || { rm -f "$TMP"; die "dump قابل خواندن نیست (pg_restore --list)."; }
  log "pg_restore --list OK"
elif command -v docker >/dev/null 2>&1 \
  && docker compose -f "$COMPOSE_FILE" cp "$TMP" "$COMPOSE_SERVICE:/tmp/golddesk-check.dump" 2>/dev/null \
  && docker compose -f "$COMPOSE_FILE" exec -T "$COMPOSE_SERVICE" pg_restore --list /tmp/golddesk-check.dump >/dev/null 2>&1; then
  log "pg_restore --list OK (داخل کانتینر)"
else
  log "هشدار: pg_restore در دسترس نبود — فقط اندازه چک شد. بازگردانی را دستی آزمایش کنید."
fi

mv "$TMP" "$OUT"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$BACKUP_DIR" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256")
fi
SIZE_BYTES=$(wc -c < "$OUT" | tr -d ' ')
log "نسخه ساخته شد: $OUT ($SIZE_BYTES بایت)"

# ── نگهداری ۱۴ روزه ────────────────────────────────────────────────────
# فقط همین prefix؛ عمداً از find با -name محدود شده تا هیچ فایل دیگری حذف نشود.
PRUNED=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "$PREFIX-*.dump" -mtime +"$RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')
find "$BACKUP_DIR" -maxdepth 1 -type f -name "$PREFIX-*.dump.sha256" -mtime +"$RETENTION_DAYS" -delete || true
log "نگهداری: $PRUNED نسخهٔ قدیمی‌تر از $RETENTION_DAYS روز حذف شد"

KEPT=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "$PREFIX-*.dump" | wc -l | tr -d ' ')
log "پایان | $KEPT نسخه فعال در $BACKUP_DIR"
