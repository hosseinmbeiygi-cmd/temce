#!/usr/bin/env bash
# QA backend unit suite runner.
#
# Runs tests/unit in per-directory chunks so a single long-running pytest is
# never orphaned by the invoking shell, and each chunk's result is appended to
# reports/pytest_chunks.txt as a single machine-readable line.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/venv/Scripts/python.exe"
OUT="$ROOT/reports/pytest_chunks.txt"
: > "$OUT"

run_chunk() {
  local label="$1"; shift
  local log
  log="$(mktemp)"

  "$PY" -m pytest "$@" -q --no-header --tb=no -p no:cacheprovider > "$log" 2>&1
  local rc=$?

  local passed failed error skipped
  passed=$(grep -oE "[0-9]+ passed"  "$log" | tail -1 | grep -oE "[0-9]+" || echo 0)
  failed=$(grep -oE "[0-9]+ failed"  "$log" | tail -1 | grep -oE "[0-9]+" || echo 0)
  error=$(grep -oE "[0-9]+ error"   "$log" | tail -1 | grep -oE "[0-9]+" || echo 0)
  skipped=$(grep -oE "[0-9]+ skipped" "$log" | tail -1 | grep -oE "[0-9]+" || echo 0)

  echo "$label|rc=$rc|passed=${passed:-0}|failed=${failed:-0}|error=${error:-0}|skipped=${skipped:-0}" >> "$OUT"
  echo "[chunk] $label -> passed=${passed:-0} failed=${failed:-0} error=${error:-0} skipped=${skipped:-0} (rc=$rc)"
  rm -f "$log"
}

# Directory chunks (the bulk of the suite)
for d in tests/unit/*/; do
  d="${d%/}"
  [ "$d" = "tests/unit" ] && continue
  run_chunk "$(basename "$d")" "$d"
done

# Top-level test_*.py files
run_chunk "toplevel_files" tests/unit/test_*.py

echo "=== TOTAL ==="
"$PY" - <<'EOF'
import re, pathlib
rows = [l.split("|") for l in pathlib.Path("reports/pytest_chunks.txt").read_text().splitlines() if l]
tot = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
for r in rows:
    for kv in r[1:]:
        k, _, v = kv.partition("=")
        if k in tot:
            try: tot[k] += int(v)
            except ValueError: pass
print(tot)
EOF