#!/usr/bin/env bash
# QA D2: start every built image and record whether the container stays up.
#
# The audit's exit criterion #1 is "a clean docker build + container start for
# every image". Build success alone is not enough: the original P0 was a
# ModuleNotFoundError at startup, which only shows up when the process runs.
#
# Usage: bash qa/boot_all_images.sh [settle_seconds]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
SETTLE="${1:-25}"
OUT="$ROOT/reports/docker_boot_matrix.txt"
: > "$OUT"

IMAGES=(
  "Dockerfile:qa-base:final"
  "Dockerfile.api:qa-api:final"
  "Dockerfile.worker:qa-worker:final"
  "Dockerfile.scheduler:qa-scheduler:final"
  "Dockerfile.admin:qa-admin:final"
  "Dockerfile.currency:qa-currency:final"
  "Dockerfile.golddesk:qa-golddesk:final"
  "Dockerfile.decision-engine:qa-decision-engine:final"
)

for entry in "${IMAGES[@]}"; do
  df="${entry%%:*}"
  tag="${entry#*:}"
  name="qaboot_$(echo "$tag" | tr -c 'a-z0-9' '_')"
  docker rm -f "$name" >/dev/null 2>&1

  docker run -d --name "$name" "$tag" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "$df|START_FAILED" | tee -a "$OUT"
    continue
  fi

  sleep "$SETTLE"
  state="$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null)"
  exitc="$(docker inspect -f '{{.State.ExitCode}}' "$name" 2>/dev/null)"

  logs="$(docker logs --tail 200 "$name" 2>&1)"
  # The real regression signal: a dependency that is missing from the image.
  if printf '%s' "$logs" | grep -qE "ModuleNotFoundError|ImportError: cannot import name"; then
    verdict="MODULE_NOT_FOUND"
    printf '%s' "$logs" | grep -E "ModuleNotFoundError|ImportError: cannot import name" | head -3 >> "$OUT"
  elif printf '%s' "$logs" | grep -qE "form data requires|Requirement"; then
    verdict="MISSING_RUNTIME_REQ"
  elif [ "$state" = "running" ]; then
    verdict="UP"
  elif [ "$state" = "exited" ]; then
    verdict="EXITED_$exitc"
  else
    verdict="$state"
  fi

  echo "$df|$verdict|state=$state|exit=$exitc" | tee -a "$OUT"
  docker rm -f "$name" >/dev/null 2>&1
done

echo "=== summary ==="
cat "$OUT"