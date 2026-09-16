#!/usr/bin/env bash
# Reproducible validation of the nonce-based CSP + Sentry wiring (report §7).
# Usage:  bash frontend/scripts/validate-csp.sh [port]
# Exits 0 only if every check passes. Requires a completed `npm run build`.
set -u

PORT="${1:-3199}"
BASE="http://localhost:$PORT"
FAILED=0

step() { printf '\n== %s ==\n' "$1"; }
pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; FAILED=1; }

# ── 1. prod server ────────────────────────────────────────────────
step "start prod server on :$PORT"
if ! curl -sf -o /dev/null "$BASE/"; then
  (npx next start -p "$PORT" > /tmp/validate-csp-server.log 2>&1 &)
  for _ in $(seq 1 20); do
    sleep 1
    curl -sf -o /dev/null "$BASE/" && break
  done
fi
curl -sf -o /dev/null "$BASE/" || { fail "server not reachable"; exit 1; }
pass "server reachable"

cleanup() {
  ps aux | grep "next start" | grep -v grep | awk '{print $1}' | xargs -r kill 2>/dev/null
}
trap cleanup EXIT

# ── 2. nonce match (header == theme script) in ONE response ──────
step "nonce match: CSP header vs theme script (single response)"
curl -s -D /tmp/vcsp_h.txt "$BASE/" -o /tmp/vcsp_b.html
H=$(grep -i "content-security-policy" /tmp/vcsp_h.txt | grep -oE "nonce-[A-Za-z0-9+/=]+" | head -1)
B=$(grep -oE '<script nonce="[A-Za-z0-9+/=]+"' /tmp/vcsp_b.html | head -1 | grep -oE 'nonce="[^"]+' | cut -d'"' -f2)
if [ -n "$H" ] && [ "nonce-$B" = "$H" ]; then
  pass "header and script nonce match ($H)"
else
  fail "header '$H' vs script 'nonce-$B'"
fi

# ── 3. nonce freshness across requests ────────────────────────────
step "nonce freshness across requests"
N1=$(curl -sI "$BASE/" | grep -ioE "nonce-[A-Za-z0-9+/=]+" | head -1)
N2=$(curl -sI "$BASE/" | grep -ioE "nonce-[A-Za-z0-9+/=]+" | head -1)
if [ -n "$N1" ] && [ "$N1" != "$N2" ]; then
  pass "two requests, two distinct nonces"
else
  fail "nonces repeated or empty ('$N1' / '$N2')"
fi

# ── 4. strict CSP directives present ──────────────────────────────
step "hardened CSP directives"
CSP=$(curl -sI "$BASE/" | grep -i "content-security-policy")
echo "$CSP" | grep -q "strict-dynamic"            && pass "strict-dynamic"        || fail "strict-dynamic missing"
echo "$CSP" | grep -q "object-src 'none'"         && pass "object-src 'none'"     || fail "object-src missing"
echo "$CSP" | grep -q "frame-ancestors 'self'"    && pass "frame-ancestors"       || fail "frame-ancestors missing"
if echo "$CSP" | grep -q "script-src 'self' 'unsafe-inline'"; then
  fail "unsafe-inline present in script-src"
else
  pass "no unsafe-inline in script-src"
fi

# ── 5. protected-route redirect carries CSP ───────────────────────
step "protected route redirect"
REDIR=$(curl -sI "$BASE/admin/users")
echo "$REDIR" | head -1 | grep -q "307"          && pass "307 redirect"          || fail "expected 307"
echo "$REDIR" | grep -q "content-security-policy" && pass "CSP on redirect"      || fail "no CSP on redirect"

# ── 6. Sentry bundle hygiene (no DSN => no trace) ─────────────────
step "Sentry bundle hygiene"
if grep -rq "sentry.io/project-id" .next/static/chunks/ 2>/dev/null; then
  fail "placeholder DSN leaked into bundles"
else
  pass "no placeholder DSN in bundles"
fi

printf '\n'
if [ "$FAILED" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
else
  echo "SOME CHECKS FAILED"
fi
exit "$FAILED"
