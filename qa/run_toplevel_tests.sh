#!/usr/bin/env bash
# QA: run the 96 top-level tests/unit/test_*.py files in batches.
# The full set exceeds a single tool-call budget, so it is chunked.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/venv/Scripts/python.exe"
OUT="$ROOT/reports/pytest_chunks.txt"

mapfile -t FILES < <(ls tests/unit/test_*.py)
BATCH="${1:-12}"

for ((i = 0; i < ${#FILES[@]}; i += BATCH)); do
  chunk=("${FILES[@]:i:BATCH}")
  label="toplevel_$i"
  log="$(mktemp)"

  # --timeout bounds individual tests: some suites block on network/DB waits,
  # which would otherwise consume the whole batch budget and lose the results.
  timeout 560 "$PY" -m pytest "${chunk[@]}" -q --no-header --tb=no \
    -p no:cacheprovider --timeout=20 --timeout-method=thread \
    > "$log" 2>&1
  rc=$?

  p=$(grep -oE "[0-9]+ passed"  "$log" | tail -1 | grep -oE "[0-9]+" || echo 0)
  f=$(grep -oE "[0-9]+ failed"  "$log" | tail -1 | grep -oE "[0-9]+" || echo 0)
  e=$(grep -oE "[0-9]+ error"   "$log" | tail -1 | grep -oE "[0-9]+" || echo 0)
  s=$(grep -oE "[0-9]+ skipped" "$log" | tail -1 | grep -oE "[0-9]+" || echo 0)
  [ -z "$p" ] && p=0; [ -z "$f" ] && f=0; [ -z "$e" ] && e=0; [ -z "$s" ] && s=0

  echo "$label|rc=$rc|passed=$p|failed=$f|error=$e|skipped=$s" >> "$OUT"
  echo "[batch] $label (${#chunk[@]} files) -> passed=$p failed=$f error=$e skipped=$s rc=$rc"
  rm -f "$log"
done