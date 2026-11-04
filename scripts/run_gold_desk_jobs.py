"""اجرای دستی job های GoldDesk (پر کردن جداول gold_*).

معمولاً scheduler اصلی این jobها را طبق cron اجرا می‌کند. این اسکریپت برای
اجرای فوری/بک‌فیل روی محیطی که scheduler در آن فعال نیست استفاده می‌شود:

    python scripts/run_gold_desk_jobs.py                 # همهٔ jobها (به ترتیب وابستگی)
    python scripts/run_gold_desk_jobs.py gold_snapshot   # فقط یک job
    python scripts/run_gold_desk_jobs.py --seed-rules    # + درج قوانین هشدار پیش‌فرض

اجرا از همان مسیر واقعی رجیستری (``BrsApiJobRegistry.run_job_now``) انجام می‌شود
تا wiring تولیدی هم آزمایش شود.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# ترتیب مهم است: snapshot اول، بعد وابسته‌ها.
DEFAULT_ORDER = [
    "gold_snapshot",
    "gold_score_persist",
    "gold_fund_nav",
    "gold_portfolio_value",
    "gold_alert_evaluate",
    "gold_daily_history",
]


async def _seed_rules() -> int:
    """درج قوانین هشدار پیش‌فرض (شامل قوانین تمرکز/ری‌بالانس/افت)."""
    from core.database import get_session
    from src.gold_desk.alert_engine import seed_default_rules

    async for session in get_session():
        inserted = await seed_default_rules(session)
        return inserted
    return 0


async def main(argv: list[str]) -> int:
    from brsapi.jobs.registry import get_brsapi_job_registry
    from core.database import init_database

    await init_database()

    seed = "--seed-rules" in argv
    names = [a for a in argv if not a.startswith("-")] or DEFAULT_ORDER

    registry = get_brsapi_job_registry()

    if seed:
        inserted = await _seed_rules()
        print(f"[seed] gold_alert_rules inserted={inserted}")

    failures = 0
    for name in names:
        result = await registry.run_job_now(name)
        ok = bool(result.get("success"))
        failures += 0 if ok else 1
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {result.get('message')}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
