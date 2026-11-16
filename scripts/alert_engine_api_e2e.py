"""End-to-end check of the alert-engine HTTP API on a local dev server.

Creates (once) a local test account whose generated credentials are stored in
``.env.alert_e2e`` (git-ignored via the ``.env.*`` rule) and never printed, then walks the
real routes: add → duplicate add → list → detail → portfolio → ledger → remove (with the
position acknowledgement) → notifications → health.

Usage:  python scripts/alert_engine_api_e2e.py [--base http://127.0.0.1:8000/api/v1] [--symbol موج] [--keep]
"""

from __future__ import annotations

import io
import json
import secrets
import sys
from pathlib import Path

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
CREDS = ROOT / ".env.alert_e2e"


def credentials() -> tuple[str, str, bool]:
    if CREDS.exists():
        doc = dict(line.split("=", 1) for line in CREDS.read_text(encoding="utf-8").splitlines() if "=" in line)
        return doc["ALERT_E2E_USERNAME"], doc["ALERT_E2E_PASSWORD"], False
    user, password = f"alert_e2e_{secrets.token_hex(4)}", secrets.token_urlsafe(18) + "aA1!"
    CREDS.write_text(f"# local dev test account for scripts/alert_engine_api_e2e.py\nALERT_E2E_USERNAME={user}\nALERT_E2E_PASSWORD={password}\n",
                     encoding="utf-8")
    return user, password, True


def main() -> int:
    args = sys.argv[1:]
    base = args[args.index("--base") + 1] if "--base" in args else "http://127.0.0.1:8000/api/v1"
    symbol = args[args.index("--symbol") + 1] if "--symbol" in args else "موج"
    if not base.startswith(("http://127.0.0.1", "http://localhost")):
        print("refusing: this script only talks to a local dev server")
        return 2
    user, password, fresh = credentials()
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(label)

    with httpx.Client(base_url=base, timeout=180.0) as c:
        if fresh:
            r = c.post("/auth/register", json={"username": user, "email": f"{user}@example.test", "password": password})
            check("register local test account", r.status_code == 200, f"HTTP {r.status_code}")
        c.cookies.clear()  # token auth only: a session cookie would bring the CSRF check into play
        r = c.post("/auth/login", json={"username": user, "password": password})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        token = (body.get("data") or body).get("access_token")
        check("login", bool(token), f"HTTP {r.status_code}")
        if not token:
            return 1
        c.cookies.clear()
        c.headers["Authorization"] = f"Bearer {token}"

        r = c.get("/alerts/monitors")
        for old in r.json()["data"]["items"]:  # start clean
            c.delete(f"/alerts/monitors/{old['id']}", params={"acknowledge_position": True})

        r = c.post("/alerts/monitors", json={"symbol": symbol})
        d = r.json()
        check("add instrument", r.status_code == 200 and d.get("success") and d["data"]["created"], json.dumps(d.get("error"), ensure_ascii=False))
        mon = d["data"]["monitor"]
        rec = mon["report"]["recommendation"]
        print(f"      {mon['symbol']} → {mon['category']} | monitoring={mon['monitoring_state']} | decision={rec['state']} | {(rec['reasons'] or [''])[0]}")
        check("identity verified", bool(mon["report"]["identity"]["isin"]) and mon["report"]["identity"]["identified"])
        check("coverage matrix present", "quote" in mon["report"]["coverage"] and "market_breadth" in mon["report"]["coverage"])

        r = c.post("/alerts/monitors", json={"symbol": symbol})
        check("duplicate add is idempotent", r.json()["data"]["created"] is False and r.json()["data"]["monitor"]["id"] == mon["id"])
        check("list shows one monitor", len(c.get("/alerts/monitors").json()["data"]["items"]) == 1)
        check("unknown symbol refused", c.post("/alerts/monitors", json={"symbol": "نمادناموجود"}).json().get("success") is False)
        check("threshold-alert routes still work", c.get("/alerts/", params={"page_size": 5}).status_code == 200)

        pf = c.get("/alerts/engine/portfolio").json()["data"]
        check("portfolio defaults", pf["allocated_capital_toman"] == 500_000_000 and pf["budgets_toman"]["per_trade_risk"] == 2_500_000,
              f"cash={pf['cash_toman']:,.0f}")
        r = c.post("/alerts/engine/ledger", json={"entry_type": "buy", "symbol": symbol, "quantity": 10 ** 9, "price_rial": 100_000})
        check("purchase beyond cash rejected", r.json().get("success") is False)
        price = (mon["report"].get("market") or {}).get("price_last") or 100_000
        r = c.post("/alerts/engine/ledger", json={"entry_type": "buy", "symbol": symbol, "quantity": 100, "price_rial": price})
        check("confirmed trade recorded", r.json().get("success") is True)
        r = c.delete(f"/alerts/monitors/{mon['id']}")
        check("removal with a position asks for acknowledgement", r.json()["data"].get("requires_acknowledgement") is True)
        s = c.put("/alerts/engine/settings", json={"patch": {"risk": {"per_trade_risk_pct": 2.0}}}).json()
        check("loosening a limit needs confirmation", s.get("success") is False)
        notes = c.get("/alerts/engine/notifications").json()["data"]["items"]
        check("in-platform notification stored", any(n["event_type"] == "monitoring_started" for n in notes), f"{len(notes)} stored")
        t = c.post("/alerts/engine/notifications/test-telegram").json()
        print(f"      telegram test → success={t.get('success')} state={(t.get('data') or {}).get('telegram', {}).get('state')}")
        h = c.get("/alerts/engine/health").json()["data"]
        print(f"      health → market_data={h['market_data']['status']} market_open={h['market_open']} telegram={h['telegram']}")
        check("support matrix served", len(c.get("/alerts/engine/support-matrix").json()["data"]["items"]) >= 8)

        if "--keep" not in args:
            r = c.delete(f"/alerts/monitors/{mon['id']}", params={"acknowledge_position": True})
            check("remove after acknowledgement", r.json()["data"].get("removed") is True)
            check("list empty after removal", c.get("/alerts/monitors").json()["data"]["items"] == [])
    print(f"\n{'ALL PASSED' if not failures else 'FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
