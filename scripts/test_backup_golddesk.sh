#!/usr/bin/env bash
# ── تست یک‌بارهٔ scripts/backup_golddesk.sh ────────────────────────────────
#
# این هارنس با pg_dump/pg_restore ساختگی روی PATH، کل مسیر اسکریپت را اجرا
# می‌کند: ساخت نسخه → اعتبارسنجی → چک‌سام → نگهداری ۱۴ روزه.
#
# صریح بگویم چه چیزی را ثابت می‌کند و چه چیزی را نه:
#   ثابت می‌کند: منطق فایل/اسم/retention/verify و fail-closed بودن اسکریپت.
#   ثابت نمی‌کند: بازگردانی واقعی روی دیتابیس — روی این ماشین psql/pg_dump و
#   داکر نصب نیست (docs/golddesk_backup.md §۴). بازگردانی واقعی باید روی
#   همان سرور هدف یک‌بار دستی آزمایش شود؛ دستور آن در همان فایل آمده است.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_SCRIPT="$REPO_ROOT/scripts/backup_golddesk.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

FAKE_BIN="$WORK/bin"
BACKUP_DIR="$WORK/backups"
mkdir -p "$FAKE_BIN" "$BACKUP_DIR"

# pg_dump ساختگی: آرگومان --file یا stdout را پر می‌کند و جدول‌ها را لاگ می‌کند.
cat > "$FAKE_BIN/pg_dump" <<'EOF'
#!/usr/bin/env bash
out=""
tables=""
prev=""
for a in "$@"; do
  case "$prev" in
    -t) tables="$a" ;;
  esac
  case "$a" in
    --file=*) out="${a#--file=}" ;;
  esac
  prev="$a"
done
payload="FAKE-DUMP gold_snapshots gold_holdings gold_trades tables_filter=$tables"
if [ -n "$out" ]; then printf '%s' "$payload" > "$out"; else printf '%s' "$payload"; fi
EOF

cat > "$FAKE_BIN/pg_restore" <<'EOF'
#!/usr/bin/env bash
# فقط حالت --list را پشتیبانی می‌کند؛ اگر فایل خالی/نامعتبر بود غیرصفر برمی‌گردد.
file=""
for a in "$@"; do [ "$a" != "--list" ] && file="$a"; done
[ -s "$file" ] || exit 2
grep -q "FAKE-DUMP" "$file" || exit 3
EOF

chmod +x "$FAKE_BIN/pg_dump" "$FAKE_BIN/pg_restore"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok — $*"; }

export PATH="$FAKE_BIN:$PATH"
export PGHOST="fake-host"        # تا شاخهٔ pg_dump بومی انتخاب شود
export POSTGRES_USER=quant_dev
export POSTGRES_DB=tse_quant
export GOLD_BACKUP_DIR="$BACKUP_DIR"
export GOLD_BACKUP_RETENTION_DAYS=14

echo "── ۱) اجرای معمولی: نسخه + چک‌سام ساخته شود ─────────────────"
"$BACKUP_SCRIPT" 2> "$WORK/run1.log" || fail "اسکریپت با شکست خارج شد: $(cat "$WORK/run1.log")"
DUMPS=( "$BACKUP_DIR"/goldbackup-*.dump )
[[ -e "${DUMPS[0]}" ]] || fail "هیچ dump ای ساخته نشد"
grep -q "FAKE-DUMP" "${DUMPS[0]}" || fail "محتوای dump درست منتقل نشد"
grep -q "gold_" "${DUMPS[0]}" && pass "فیلتر جدولهای طلا به pg_dump رسید"
[[ -e "${DUMPS[0]}.sha256" ]] && pass "چک‌سام کنار نسخه نوشته شد"
[[ ! -e "${DUMPS[0]}.partial" ]] && pass "فایل .partial باقی نمانده"

echo "── ۲) فایل‌های نامربوط نباید حذف شوند ──────────────────────"
touch -d "40 days ago" "$BACKUP_DIR/keep-me.txt"
touch -d "40 days ago" "$BACKUP_DIR/goldbackup-20200101T000000Z.dump"
touch -d "2 days ago"  "$BACKUP_DIR/goldbackup-20261022T000000Z.dump"
"$BACKUP_SCRIPT" 2> "$WORK/run2.log" || fail "اجرای دوم شکست خورد: $(cat "$WORK/run2.log")"
[[ -e "$BACKUP_DIR/keep-me.txt" ]] && pass "فایل بدون پیشوندِ خودِ اسکریپت دست نخورد"
[[ ! -e "$BACKUP_DIR/goldbackup-20200101T000000Z.dump" ]] && pass "نسخهٔ ۴۰ روزه حذف شد"
[[ -e "$BACKUP_DIR/goldbackup-20261022T000000Z.dump" ]] && pass "نسخهٔ ۲ روزه باقی ماند"

echo "── ۳) دامنهٔ نامعتبر باید اسکریپت را متوقف کند ──────────────"
if GOLD_BACKUP_SCOPE=bogus "$BACKUP_SCRIPT" 2>/dev/null; then
  fail "دامنهٔ scope نامعتبار رد نشد"
else
  pass "GOLD_BACKUP_SCOPE نامعتبر ⇒ خروج غیرصفر"
fi

echo "── ۴) pg_dump خراب ⇒ نسخهٔ جعلی اعلام نشود ─────────────────"
cat > "$FAKE_BIN/pg_dump" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "$FAKE_BIN/pg_dump"
BEFORE=$(find "$BACKUP_DIR" -name 'goldbackup-*.dump' | wc -l | tr -d ' ')
if "$BACKUP_SCRIPT" 2> "$WORK/run4.log"; then
  fail "اسکریپت با pg_dump شکست‌خورده موفق گزارش داد"
fi
AFTER=$(find "$BACKUP_DIR" -name 'goldbackup-*.dump' | wc -l | tr -d ' ')
[[ "$BEFORE" == "$AFTER" ]] && pass "هیچ نسخهٔ ناقصی به مجموعه اضافه نشد"
[[ -z "$(find "$BACKUP_DIR" -name '*.partial' -print -quit)" ]] && pass "فایل .partial پاک ماند"

echo
echo "همهٔ بررسی‌ها پاس شد."
