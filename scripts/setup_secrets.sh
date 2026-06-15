#!/usr/bin/env bash
# Docker Secrets setup for production deployment.
# Usage: source scripts/setup_secrets.sh
#
# Generates secure random values and writes Docker secret files.
# These should be sourced before `docker stack deploy`.

set -euo pipefail

SECRETS_DIR="./secrets"
mkdir -p "$SECRETS_DIR"

# Generate secrets if they don't exist
if [ ! -f "$SECRETS_DIR/postgres_password.txt" ]; then
  openssl rand -base64 32 | tr -d '\n' > "$SECRETS_DIR/postgres_password.txt"
  echo "[created] $SECRETS_DIR/postgres_password.txt"
fi

if [ ! -f "$SECRETS_DIR/secret_key.txt" ]; then
  openssl rand -base64 64 | tr -d '\n' > "$SECRETS_DIR/secret_key.txt"
  echo "[created] $SECRETS_DIR/secret_key.txt"
fi

if [ ! -f "$SECRETS_DIR/api_key.txt" ]; then
  openssl rand -base64 48 | tr -d '\n' > "$SECRETS_DIR/api_key.txt"
  echo "[created] $SECRETS_DIR/api_key.txt"
fi

echo ""
echo "Secrets directory: $SECRETS_DIR"
ls -la "$SECRETS_DIR"
echo ""
echo "To deploy:"
echo "  docker stack deploy -c docker-compose.yml -c docker-compose.production.yml market"
