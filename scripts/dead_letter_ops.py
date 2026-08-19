#!/usr/bin/env python
"""
🔄 Dead-Letter Ops Cycle — چرخهٔ کامل عملیاتی روی Redis واقعی

یک دستور، کل چرخه:

  1. SEED     — پر کردن ``job:dead`` با پیام‌های واقع‌گرایانه (اگر خالی باشد)
  2. REPORT   — گزارش خلاصه (همان ``dead_letter_report.py``)
  3. REPLAY   — برگرداندن پیام‌ها به ``job:queue`` (همان ``replay_dead_letter.py``)
  4. VERIFY   — وضعیت نهایی صف‌ها

همهٔ مراحل از هستهٔ مشترک (``jobs.replay``) و رندرهای مشترک
(``scripts.dead_letter_report``) استفاده می‌کنند، پس خروجی با پنل ادمین و
اسکریپت‌های قبلی همیشه یکسان است.

مصرف:
    python scripts/dead_letter_ops.py                  # چرخهٔ کامل
    python scripts/dead_letter_ops.py --no-seed        # بدون seed (صف موجود)
    python scripts/dead_letter_ops.py --no-replay      # فقط گزارش + verify
    python scripts/dead_letter_ops.py --window today   # گزارش فقط امروز
    python scripts/dead_letter_ops.py --cleanup        # حذف صف‌ها در پایان
    python scripts/dead_letter_ops.py --force-seed     # seed حتی اگر صف خالی نباشد

کد خروجی: ۰ = موفق، ۱ = خطای اتصال/اعتبارسنجی.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# --- auto PYTHONPATH ---
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

# Windows consoles default to cp1252 — force UTF-8 so emoji/Persian print.
for _stream in (sys.stdout, sys.stderr):
    with suppress(AttributeError, ValueError):
        _stream.reconfigure(encoding="utf-8")

from core.config import settings
from jobs.replay import (
    SUMMARY_WINDOWS,
    current_token,
    replay_dead_letter_messages,
    summarize_dead_letter,
)

# اسم‌هایی که تست‌ها patch می‌کنند — عمداً همین‌جا نگه داشته می‌شوند:
#   _get_redis, settings, main


async def _get_redis() -> Any | None:
    """بازگرداندن redis client مشترک (None وقتی در دسترس نیست)."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        await cache.initialize()
        return cache.client
    except Exception:
        return None


def _demo_messages() -> list[str]:
    """پیام‌های dead-letter واقع‌گرایانه برای seed — از منبع مشترک گزارش."""
    from scripts.dead_letter_report import _demo_raw_messages  # noqa: PLC0415

    return _demo_raw_messages()


# ── Cycle steps ─────────────────────────────────────────────────────────


async def _seed(redis: Any, dead_queue: str, force: bool) -> None:
    """مرحلهٔ ۱ — پر کردن صف با پیام‌های دمو در صورت خالی بودن (یا --force-seed)."""
    current = int(await redis.llen(dead_queue) or 0)
    if current > 0 and not force:
        print(f"ℹ️ {dead_queue} خالی نیست ({current} پیام) — seed رد شد (از --force-seed استفاده کنید).")
        return
    messages = _demo_messages()
    for raw in messages:
        await redis.lpush(dead_queue, raw)
    print(f"🧪 SEED: {len(messages)} پیام در {dead_queue} قرار گرفت.")


async def _report(redis: Any, dead_queue: str, window: str, since: float | None, no_save: bool) -> None:
    """مرحلهٔ ۲ — گزارش خلاصهٔ dead-letter (همان dead_letter_report.py)."""
    from scripts.dead_letter_report import _print_summary, _save_report  # noqa: PLC0415

    generated_at = datetime.now(UTC).isoformat()
    summary = await summarize_dead_letter(
        redis,
        dead_queue=dead_queue,
        window=window,
        since=since,
    )
    _print_summary(summary, generated_at)
    if summary.total > 0 and not no_save:
        _save_report(summary, generated_at, "ops-cycle")


async def _replay(redis: Any, queue_name: str, dead_queue: str) -> None:
    """مرحلهٔ ۳ — برگرداندن پیام‌ها به صف اصلی (همان replay_dead_letter.py)."""
    result = await replay_dead_letter_messages(
        redis,
        queue_name=queue_name,
        dead_queue=dead_queue,
        token=current_token(settings.job_queue_token),
        mode="replay",
    )
    if result.total == 0:
        print("ℹ️ REPLAY: صف dead-letter خالی است — چیزی برای replay نیست.")
        return result
    print(f"🔁 REPLAY: ✅ {result.replayed} پیام به {queue_name} رفت | ❌ {result.failed} ناموفق (در {dead_queue} ماندند)")
    return result


async def _verify(redis: Any, queue_name: str, dead_queue: str) -> None:
    """مرحلهٔ ۴ — وضعیت نهایی صف‌ها."""
    queue_size = int(await redis.llen(queue_name) or 0)
    dead_size = int(await redis.llen(dead_queue) or 0)
    print(f"📊 VERIFY: {queue_name} = {queue_size} پیام | {dead_queue} = {dead_size} پیام")


# ── Main ────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Full dead-letter ops cycle: seed → report → replay → verify",
    )
    parser.add_argument("--no-seed", action="store_true", help="بدون seed — از صف موجود استفاده کن")
    parser.add_argument("--force-seed", action="store_true", help="seed حتی اگر صف خالی نباشد")
    parser.add_argument("--no-replay", action="store_true", help="فقط گزارش + verify (بدون replay)")
    parser.add_argument("--window", default="all", help="بازهٔ گزارش: all | today | week | 24h")
    parser.add_argument("--since", type=float, default=None, help="آستانهٔ صریح (epoch seconds) برای گزارش")
    parser.add_argument("--no-save", action="store_true", help="فقط نمایش گزارش، بدون ذخیره فایل")
    parser.add_argument("--cleanup", action="store_true", help="حذف job:queue و job:dead در پایان")
    parser.add_argument("--queue", default=None, help="نام صف اصلی (پیش‌فرض: settings.job_queue_name)")
    parser.add_argument("--dead", default=None, help="نام صف dead-letter (پیش‌فرض: settings.job_queue_dead_letter)")
    args = parser.parse_args()

    if args.window not in SUMMARY_WINDOWS:
        print(f"❌ بازهٔ نامعتبر: {args.window!r} — باید یکی از {SUMMARY_WINDOWS} باشد")
        sys.exit(1)
    if args.since is not None and args.since < 0:
        print("❌ --since باید یک عدد epoch غیرمنفی باشد")
        sys.exit(1)

    queue_name = args.queue or settings.job_queue_name
    dead_queue = args.dead or settings.job_queue_dead_letter

    redis = await _get_redis()
    if redis is None:
        print("❌ Redis در دسترس نیست — چرخه قابل اجرا نیست.")
        sys.exit(1)

    print("=" * 62)
    print("🔄  چرخهٔ کامل Dead-Letter Ops")
    print("=" * 62)

    # 1) SEED
    if not args.no_seed:
        await _seed(redis, dead_queue, force=args.force_seed)

    # 2) REPORT
    await _report(redis, dead_queue, args.window, args.since, args.no_save)

    # 3) REPLAY
    replay_result = None
    if not args.no_replay:
        replay_result = await _replay(redis, queue_name, dead_queue)

    # 4) VERIFY
    await _verify(redis, queue_name, dead_queue)

    # 5) CLEANUP (اختیاری) — فقط با هشدار اگر پیام‌های replay نشده باقی مانده باشند
    if args.cleanup:
        leftover = int(await redis.llen(dead_queue) or 0)
        if leftover > 0:
            print(f"⚠️ CLEANUP: {leftover} پیام هنوز در {dead_queue} هستند و حذف خواهند شد (پس از {queue_name} و {dead_queue}).")
        await redis.delete(queue_name, dead_queue)
        print("🧹 CLEANUP: صف‌ها پاک شدند.")

    # 6) کد خروجی: شکست replay باید در اتوماسیون دیده شود
    if replay_result is not None and replay_result.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
