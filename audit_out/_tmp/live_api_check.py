"""Live check: new GoldDesk endpoints through the real ASGI app."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from httpx import ASGITransport, AsyncClient  # noqa: E402

BASE = "/api/v1/gold"


async def main() -> None:
    from apps.api.app import create_app
    from core.database import init_database

    await init_database()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for method, url in [
            ("GET", f"{BASE}/freshness"),
            ("GET", f"{BASE}/portfolio/performance?days=90"),
            ("GET", f"{BASE}/portfolio/history?days=30"),
            ("POST", f"{BASE}/portfolio/snapshot"),
            ("GET", f"{BASE}/portfolio"),
            ("GET", f"{BASE}/health"),
        ]:
            try:
                r = await c.request(method, url, timeout=120)
                body = r.json()
                if url.endswith("/freshness"):
                    d = body["data"]
                    print(f"{method} {url} -> {r.status_code} overall={d['overall']} counts={d['counts']} jobs={d['scheduler_jobs']}")
                elif "performance" in url:
                    d = body["data"]
                    print(f"{method} {url} -> {r.status_code} points={d['points']} twr={d['twr_pct']}")
                    print("   benchmarks:", json.dumps(d["benchmarks"], ensure_ascii=False))
                    print("   concentration:", d["concentration_pct"], "drift:", d["max_drift_pct"])
                elif "history" in url:
                    d = body["data"]
                    print(f"{method} {url} -> {r.status_code} points={d['points']} first={d['items'][0] if d['items'] else None}")
                elif "snapshot" in url:
                    print(f"{method} {url} -> {r.status_code} {json.dumps(body['data'], ensure_ascii=False)}")
                elif url.endswith("/portfolio"):
                    d = body["data"]
                    print(f"{method} {url} -> {r.status_code} value={d['total_value']} returns_real={d['returns']['real_xirr']}")
                else:
                    print(f"{method} {url} -> {r.status_code} jobs={body.get('scheduler_jobs')} rules={body.get('active_alert_rules')} last_snap={body.get('last_snapshot_at')}")
            except Exception as exc:  # noqa: BLE001
                print(f"{method} {url} -> ERROR {type(exc).__name__}: {str(exc)[:200]}")


asyncio.run(main())
