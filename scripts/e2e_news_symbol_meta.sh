#!/usr/bin/env bash
# Live E2E validation of the news symbol mapping stack against the real
# Postgres (news suite, 2026-09-19):
#
#   1. GET  /api/v1/news/symbol/{symbol}      → items + SymbolMatchMeta in `message`
#   2. GET  /api/v1/news-tag-map              → admin view (auth chain: admin JWT)
#   3. POST /api/v1/news-tag-map/{tag}/manual → manual override (validated target)
#   4. GET  /api/v1/news-tag-map/{tag}/verify → dry-resolve returns the manual row
#   5. Seeded news_items row tagged with the manual alias is found via
#      GET /news/symbol/{canonical} with confidence meta (read flag ON)
#   6. DELETE /api/v1/news-tag-map/{tag}      → 404 afterwards, audit rows written
#
# Usage: bash scripts/e2e_news_symbol_meta.sh [port]
# Exits 0 only if every check passes. Spawns a real uvicorn server.
set -u

PORT="${1:-3199}"
BASE="http://localhost:$PORT"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$(mktemp)"
FAILED=0

step() { printf '\n== %s ==\n' "$1"; }
pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; FAILED=1; }

cd "$PROJECT_ROOT"
# shellcheck disable=SC2046
export $(grep -E "^DATABASE_URL" .env | sed 's/\r$//' | tr -d '"' | tr -d "'")
export PYTHONIOENCODING=utf-8
# The dev machine routes localhost through a system proxy (WhiteAesther)
# — bypass it so httpx/curl hit the local uvicorn directly.
export NO_PROXY="*"
export no_proxy="*"
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
# Read path served from news_items so the seeded alias row is visible.
export NEWS_READ_FROM_ITEMS=true

step "1. starting real uvicorn server on :$PORT"
python -m uvicorn apps.api.app:app --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

READY=0
for _ in $(seq 1 60); do
  if curl -sf -o /dev/null "$BASE/api/v1/news?page_size=1"; then READY=1; break; fi
  sleep 1
done
if [ "$READY" = "1" ]; then pass "server ready"; else fail "server did not start"; tail -30 "$LOG"; exit 1; fi

step "2. E2E checks against live API + Postgres"
python - "$BASE" "$PORT" <<'EOF'
import asyncio, json, os, re, sys, uuid
import httpx

base = sys.argv[1]
failed = []

def check(name, cond, extra=""):
    print(("PASS: " if cond else "FAIL: ") + name + ("" if cond else f"  [{extra}]"))
    if not cond:
        failed.append(name)

async def main():
    from core.security.tokens import create_access_token

    token = create_access_token({"sub": "e2e-admin", "roles": ["admin"]})
    headers = {"Authorization": f"Bearer {token}"}
    marker = f"e2e_map_{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(base_url=base, timeout=30) as c:
        # ── 2a. public /news/symbol with meta ──────────────────────────
        r = await c.get("/api/v1/news/symbol/وبانك", params={"page_size": 20})
        check("symbol endpoint 200", r.status_code == 200, r.text[:200])
        body = r.json()
        items = body.get("data", {}).get("items", [])
        check("وبانك returns items", body.get("success") and len(items) > 0)
        meta_raw = body.get("message")
        check("message carries meta", bool(meta_raw))
        meta = json.loads(meta_raw) if meta_raw else {}
        check("meta.symbol == وبانك", meta.get("symbol") == "وبانك", str(meta)[:200])
        check("meta.matched includes وبانک", "وبانک" in meta.get("matched", []))
        webank = [m for m in meta.get("maps", []) if m.get("tag_value") == "وبانک"]
        check("meta.maps has وبانک arabic_fallback@0.8",
              bool(webank) and webank[0]["match_type"] == "arabic_fallback"
              and abs(webank[0]["confidence"] - 0.8) < 1e-9)

        # ── 2b. admin view over the live corpus ────────────────────────
        r = await c.get("/api/v1/news-tag-map", params={"page_size": 10}, headers=headers)
        check("admin list 200", r.status_code == 200, r.text[:200])
        listed = r.json().get("data", {})
        check("admin list sees >=5 mapped rows", listed.get("total", 0) >= 5, str(listed)[:200])
        r = await c.get("/api/v1/news-tag-map/stats", headers=headers)
        check("stats 200 + counts sum", r.status_code == 200
              and sum(r.json()["data"]["counts"].values()) == r.json()["data"]["total"])

        # ── 2c. manual override (validated) ─────────────────────────────
        import asyncpg
        dsn = re.sub(r"\?.*$", "", os.environ["DATABASE_URL"]).replace(
            "postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        row = await conn.fetchrow("SELECT id FROM symbols WHERE symbol = 'فولاد' LIMIT 1")
        target_id = int(row["id"])

        r = await c.post(f"/api/v1/news-tag-map/{marker}/manual", headers=headers,
                         json={"resolved_type": "symbol", "resolved_id": target_id})
        check("manual override 200", r.status_code == 200, r.text[:300])
        check("override payload manual@1.0",
              r.json()["data"]["match_type"] == "manual"
              and abs(r.json()["data"]["confidence"] - 1.0) < 1e-9)

        r = await c.get(f"/api/v1/news-tag-map/{marker}/verify", headers=headers)
        resolved = r.json()["data"]["resolved"]
        check("verify returns manual row",
              bool(resolved) and resolved["resolved_symbol"] == "فولاد"
              and resolved["match_type"] == "manual")

        # audit trail written
        n_audit = await conn.fetchval(
            "SELECT count(*) FROM audit_logs WHERE entity_id=$1 AND entity_type='news_tag_symbol_map'",
            marker)
        check("audit_logs row written", (n_audit or 0) >= 1)

        # ── 2d. alias item found via canonical symbol ───────────────────
        item = await conn.fetchrow(
            "INSERT INTO news_items (title, body, source, source_url, published_at,"
            " category, dedup_hash) VALUES ($1,$2,$3,$4, now()::timestamp, 'market', $5)"
            " RETURNING id",
            f"{marker} عنوان خبر", f"{marker} body", "e2e_src",
            f"https://x.test/{marker}", f"hash_{marker}")
        item_id = item["id"]
        await conn.execute(
            "INSERT INTO news_tags (news_id, tag_type, tag_value, confidence)"
            " VALUES ($1, 'stock_symbol', $2, 1.0)", item_id, marker)
        await conn.close()

        r = await c.get("/api/v1/news/symbol/فولاد", params={"page_size": 100})
        body = r.json()
        ids = [i["id"] for i in body.get("data", {}).get("items", [])]
        check("alias-tagged item found via canonical فولاد", f"ni_{item_id}" in ids, str(ids)[:200])
        meta = json.loads(body["message"]) if body.get("message") else {}
        check("meta.matched includes manual alias", marker in meta.get("matched", []))
        manual = [m for m in meta.get("maps", []) if m.get("tag_value") == marker]
        check("meta.maps shows manual@1.0 alias", bool(manual)
              and manual[0]["match_type"] == "manual"
              and abs(manual[0]["confidence"] - 1.0) < 1e-9)

        # ── 2e. delete + 404 afterwards ─────────────────────────────────
        r = await c.delete(f"/api/v1/news-tag-map/{marker}", headers=headers)
        check("delete 200", r.status_code == 200, r.text[:200])
        r = await c.get(f"/api/v1/news-tag-map/{marker}/verify", headers=headers)
        check("mapping gone (verify empty)", r.json()["data"]["resolved"] is None)

        # cleanup seeded rows (cascade removes the tag)
        conn = await asyncpg.connect(dsn)
        await conn.execute("DELETE FROM news_items WHERE id=$1", item_id)
        await conn.execute(
            "DELETE FROM audit_logs WHERE entity_id=$1 AND entity_type='news_tag_symbol_map'",
            marker)
        await conn.close()

    if failed:
        print(f"\n{len(failed)} check(s) failed: {failed}")
        sys.exit(1)
    print("\nALL E2E CHECKS PASSED")

asyncio.run(main())
EOF
[ $? -eq 0 ] && pass "E2E python checks" || fail "E2E python checks"

step "3. server log tail"
tail -5 "$LOG"

if [ "$FAILED" = "0" ]; then printf '\nE2E: ALL GREEN\n'; exit 0; else printf '\nE2E: FAILURES\n'; exit 1; fi
