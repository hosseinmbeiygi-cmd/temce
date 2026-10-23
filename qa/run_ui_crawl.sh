#!/usr/bin/env bash
# QA UI crawl driver (F-UI): boots the built Next.js server, waits for
# readiness, runs the Playwright crawl, then tears the server down.
#
# Everything happens inside one process group so the server cannot outlive
# the tool invocation that started it.
#
# Usage: bash qa/run_ui_crawl.sh [port]
set -uo pipefail

PORT="${1:-3100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

LOG="$ROOT/reports/ui_crawl_server.log"
mkdir -p "$ROOT/reports"

echo "[crawl] starting next server on port $PORT"
PORT="$PORT" node node_modules/next/dist/bin/next start -p "$PORT" > "$LOG" 2>&1 &
SERVER_PID=$!

cleanup() {
  echo "[crawl] stopping server (pid $SERVER_PID)"
  kill "$SERVER_PID" 2>/dev/null || true
  # next start spawns a child; make sure the port is released
  sleep 2
}
trap cleanup EXIT

# Readiness poll instead of a fixed sleep.
READY=0
for _ in $(seq 1 60); do
  code="$(curl -s -m 5 -o /dev/null -w '%{http_code}' "http://localhost:$PORT/" || echo 000)"
  if [ "$code" = "200" ]; then READY=1; break; fi
  sleep 2
done

if [ "$READY" != "1" ]; then
  echo "[crawl] FAILED: server never became ready"
  tail -30 "$LOG"
  exit 1
fi

echo "[crawl] server ready; crawling"
cd "$ROOT"

# Playwright is not a project dependency; it is resolved from the npx cache
# (installed on demand via `npx playwright install chromium`). Export its
# node_modules root so `import { chromium } from 'playwright'` resolves.
PW_MODULES=""
for cand in "$HOME/AppData/Local/npm-cache/_npx"/*/node_modules; do
  if [ -d "$cand/playwright" ]; then PW_MODULES="$cand"; fi
done
if [ -z "$PW_MODULES" ]; then
  echo "[crawl] FAILED: playwright package not found (run: npx playwright install chromium)"
  exit 1
fi
echo "[crawl] using playwright from $PW_MODULES"
export NODE_PATH="$PW_MODULES"

node qa/ui_crawl.mjs "http://localhost:$PORT" reports
STATUS=$?

exit $STATUS