#!/usr/bin/env bash
# ── S4 — آزمون بازگردانی واقعی پشتیبان GoldDesk ───────────────────────────
#
# پشتیبانی که یک‌بار بازگردانی نشده، پشتیبان نیست. این اسکریپت همان شک را می‌بندد:
#   ۱) از دیتابیس مبدأ یک dump تازه می‌گیرد (یا dump موجود را می‌گیرد)
#   ۲) یک کانتینر یکبارمصرف Postgres می‌سازد (پورت تصادفی، نام تصادفی، هرگز
#      روی دادهٔ اصلی چیزی ننویس)
#   ۳) dump را داخلش restore می‌کند
#   ۴) شمار ردیف ۹ جدول طلا و «آخرین snapshot» را با مبدأ مقایسه می‌کند
#   ۵) کانتینر را حذف می‌کند (trap)
#
# اجرا:
#   bash scripts/test_restore_golddesk.sh                 # چرخهٔ کامل
#   GOLD_RESTORE_DUMP=backups/golddesk/x.dump bash scripts/test_restore_golddesk.sh
#   bash scripts/test_restore_golddesk.sh --dry-run       # فقط نمایش نقشه، بدون اجرا
#
# کد خروج: ۰ = برابری تأیید شد | ۱ = عدم برابری/خطا | ۳ = پیش‌نیاز نیست
# (در این حالت هیچ‌چیز اجرا نشده و «restore موفق» را ادعا نکنید).
#
# ⚠️ این اسکریپت هیچ مقدار secret را چاپ نمی‌کند: DATABASE_URL/PGPASSWORD در
# متغیر می‌مانند و در لاگ ماسک می‌شوند.

set -euo pipefail

log()  { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
pass() { log "ok — $*"; }
fail() { log "FAIL — $*"; exit 1; }
skip() { log "NOT EXECUTED — $*"; exit 3; }

COMPOSE_FILE="${GOLD_BACKUP_COMPOSE_FILE:-docker-compose.yml}"
DB_SERVICE="${GOLD_BACKUP_SERVICE:-timescaledb}"
PG_USER="${POSTGRES_USER:-quant_dev}"
PG_DB="${POSTGRES_DB:-tse_quant}"
PG_IMAGE="${GOLD_RESTORE_IMAGE:-postgres:16-alpine}"
TABLES=(gold_snapshots gold_fund_nav gold_alert_rules gold_alert_events
        gold_score_history gold_holdings gold_dca_plans gold_trades
        gold_portfolio_values)

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) log "arg ناشناخته: $arg (کمک: --help)"; exit 2 ;;
  esac
done

if [[ "$DRY_RUN" == "1" ]]; then
  log "dry-run — چیزی اجرا نمی‌شود. نقشهٔ کار:"
  log "  1) dump: docker compose -f $COMPOSE_FILE exec -T $DB_SERVICE pg_dump -U $PG_USER -d $PG_DB -Fc -t 'gold_*'"
  log "  2) container: $PG_IMAGE (نام و پورت تصادفی، volume موقت)"
  log "  3) pg_restore --no-owner -d <scratch_db>"
  log "  4) compare: count(*) for ${#TABLES[@]} tables + max(snapshot_at)"
  log "  5) docker rm -f (trap)"
  exit 0
fi

# ── preflight: هر سه ابزار + daemon فعال ────────────────────────────────
command -v docker >/dev/null 2>&1 || skip "docker نصب نیست. روی همان سرور مقصد اجرا کنید که کانتینر دیتابیس آنجا است."
docker info >/dev/null 2>&1 || skip "daemon داکر در دسترس نیست (Docker Desktop بالا نیست؟). این آزمون را روی سروری اجرا کنید که $DB_SERVICE آنجا running است؛ تا قبل از آن، I4 «fixed» نیست."

# ── مبدأ: کانتینر دیتابیس باید بالا باشد ────────────────────────────────
SRC_CID="$(docker compose -f "$COMPOSE_FILE" ps -q "$DB_SERVICE" 2>/dev/null | head -1 || true)"
if [[ -z "$SRC_CID" ]]; then
  skip "سرویس '$DB_SERVICE' در $COMPOSE_FILE بالا نیست ⇒ مقایسه با مبدأ ممکن نیست.
        اجرا با یک dump موجود:  GOLD_RESTORE_DUMP=path/to.dump bash $0
        یا اول:                 docker compose -f $COMPOSE_FILE up -d $DB_SERVICE"
fi
log "مبدأ: کانتینر $SRC_CID (سرویس $DB_SERVICE)"

WORK="$(mktemp -d)"
SCRATCH_NAME="golddesk-restore-$$-$RANDOM"
SCRATCH_PORT=""
cleanup() {
  [[ -n "$SCRATCH_PORT" ]] && docker rm -f "$SCRATCH_NAME" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

# ── ۱) dump ────────────────────────────────────────────────────────────
DUMP="${GOLD_RESTORE_DUMP:-$WORK/restore-test.dump}"
if [[ -z "${GOLD_RESTORE_DUMP:-}" ]]; then
  log "مرحله ۱: گرفتن dump تازه از مبدأ"
  docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
    pg_dump -U "$PG_USER" -d "$PG_DB" -Fc -t 'gold_*' > "$DUMP"
else
  [[ -s "$DUMP" ]] || fail "dump داده‌شده وجود ندارد/خالی است: $DUMP"
  log "مرحله ۱: استفاده از dump موجود: $DUMP"
fi
[[ -s "$DUMP" ]] || fail "dump خالی است"
DUMP_BYTES=$(wc -c < "$DUMP" | tr -d ' ')
log "dump: $DUMP_BYTES بایت"

# ── ۲) کانتینر یکبارمصرف ───────────────────────────────────────────────
log "مرحله ۲: ساخت کانتینر یکبارمصرف ($PG_IMAGE)"
SCRATCH_PORT="$(docker run -d --name "$SCRATCH_NAME" -e POSTGRES_HOST_AUTH_METHOD=trust \
  -e POSTGRES_DB=scratch -p 127.0.0.1::5432 "$PG_IMAGE" 2>&1 | tail -1)"
[[ -n "$SCRATCH_PORT" ]] || fail "کانتینر scratch بالا نیامد"
SCRATCH_PORT="$(docker port "$SCRATCH_NAME" 5432/tcp 2>/dev/null | head -1 | sed 's/.*://')"
log "کانتینر $SCRATCH_NAME روی پورت $SCRATCH_PORT"

for _ in $(seq 1 60); do
  docker exec "$SCRATCH_NAME" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$SCRATCH_NAME" pg_isready -U postgres >/dev/null 2>&1 \
  || fail "کانتینر scratch آماده نشد"

docker exec "$SCRATCH_NAME" createdb -U postgres restored || fail "ایجاد db نشد"

# ── ۳) restore ─────────────────────────────────────────────────────────
log "مرحله ۳: pg_restore داخل کانتینر"
docker cp "$DUMP" "$SCRATCH_NAME:/tmp/restore.dump" >/dev/null
# --no-owner: ownerهای k8s/dev به postgres نگاشت شوند. warningهای timestamptz
# را نادیده نمی‌گیریم: اگر جدولی نیاید، مرحلهٔ ۴ می‌گیرد.
if ! docker exec "$SCRATCH_NAME" pg_restore -U postgres -d restored --no-owner \
     /tmp/restore.dump > "$WORK/restore.log" 2>&1; then
  log "pg_restore کد غیرصفر داد (پیام‌ها ماسک می‌شوند):"
  sed -E 's/[A-Za-z0-9._-]{20,}/<masked>/g' "$WORK/restore.log" | head -20 >&2
  fail "restore ناموفق"
fi
RESTORE_WARNINGS="$(grep -c "WARNING" "$WORK/restore.log" || true)"
pass "pg_restore موفق — $RESTORE_WARNINGS warning"

count_in_scratch() {
  docker exec "$SCRATCH_NAME" psql -U postgres -d restored -tA \
    -c "select count(*) from $1" 2>/dev/null | tr -d '[:space:]'
}
count_in_source() {
  docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
    psql -U "$PG_USER" -d "$PG_DB" -tA -c "select count(*) from $1" 2>/dev/null | tr -d '[:space:]'
}

# ── ۴) مقایسهٔ ۹ جدول ──────────────────────────────────────────────────
log "مرحله ۴: مقایسهٔ شمار ردیف ۹ جدول طلا"
MISMATCH=0
MISSING=0
printf '%-26s %10s %10s  %s\n' "table" "source" "restored" "verdict" >&2
for t in "${TABLES[@]}"; do
  s="$(count_in_source "$t" || true)"
  r="$(count_in_scratch "$t" || true)"
  if [[ -z "$r" ]]; then
    printf '%-26s %10s %10s  %s\n' "$t" "${s:-?}" "MISSING" "FAIL" >&2
    MISSING=$((MISSING+1)); continue
  fi
  if [[ "$s" == "$r" ]]; then
    verdict="ok"; else verdict="MISMATCH"; MISMATCH=$((MISMATCH+1)); fi
  printf '%-26s %10s %10s  %s\n' "$t" "${s:-?}" "$r" "$verdict" >&2
done

# ── تازگی داده: آخرین snapshot باید عیناً منتقل شده باشد ───────────────
SRC_TS="$(docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" psql -U "$PG_USER" -d "$PG_DB" -tA \
  -c "select coalesce(max(snapshot_at),'none') from gold_snapshots" 2>/dev/null | tr -d '[:space:]')"
RST_TS="$(docker exec "$SCRATCH_NAME" psql -U postgres -d restored -tA \
  -c "select coalesce(max(snapshot_at),'none') from gold_snapshots" 2>/dev/null | tr -d '[:space:]')"
log "آخرین snapshot — مبدأ: $SRC_TS | بازگردانی‌شده: $RST_TS"

# ── ۵) verdict ──────────────────────────────────────────────────────────
if (( MISSING > 0 )); then
  fail "$MISSING جدول در نتیجهٔ restore نبود ⇒ dump یا restore ناقص است"
fi
if (( MISMATCH > 0 )); then
  fail "$MISMATCH جدول با مبدأ فرق دارد ⇒ بازگردانی قابل اتکا نیست"
fi
if [[ "$SRC_TS" != "$RST_TS" ]]; then
  fail "آخرین snapshot برابر نیست"
fi
pass "بازگردانی تأیید شد: ${#TABLES[@]}/${#TABLES[@]} جدول برابر، آخرین snapshot برابر"
log "کانتینر scratch ($SCRATCH_NAME) حذف می‌شود."
