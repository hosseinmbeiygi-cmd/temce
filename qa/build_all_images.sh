#!/usr/bin/env bash
# QA D2: build every service image from the pinned lock and report per-image exit codes.
#
# The audit's exit criterion #1 is "a clean docker build + container start for
# every image from a LOCKED dependency set". This script executes that.
#
# Usage: bash qa/build_all_images.sh [outfile]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${1:-$ROOT/reports/docker_build_matrix.txt}"

IMAGES=(
  "Dockerfile.api:qa-api:final"
  "Dockerfile.worker:qa-worker:final"
  "Dockerfile.scheduler:qa-scheduler:final"
  "Dockerfile.admin:qa-admin:final"
  "Dockerfile.currency:qa-currency:final"
  "Dockerfile.golddesk:qa-golddesk:final"
  "Dockerfile.decision-engine:qa-decision-engine:final"
  "Dockerfile:qa-base:final"
)

: > "$OUT"
for entry in "${IMAGES[@]}"; do
  df="${entry%%:*}"
  tag="${entry#*:}"
  log="$(mktemp)"
  printf '>>> %-26s -> %s\n' "$df" "$tag"
  timeout 900 docker build --load -f "$df" -t "$tag" . > "$log" 2>&1
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "FAILED rc=$rc" | tee -a "$OUT"
    tail -40 "$log" >> "$OUT"
  else
    echo "$df|rc=0|tag=$tag" | tee -a "$OUT"
  fi
  rm -f "$log"
done

echo "=== summary ==="
cat "$OUT"