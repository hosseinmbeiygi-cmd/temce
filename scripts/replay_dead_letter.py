#!/usr/bin/env python
"""
🔁 Replay Dead-Letter Jobs — برگرداندن جاب‌های شکست‌خورده به صف اصلی

پیام‌های dead-letter (``job:dead``) را بعد از رفع مشکل، دوباره به صف اصلی
(``job:queue``) برمی‌گرداند تا workerها دوباره آن‌ها را اجرا کنند.

این اسکریپت یک wrapper نازک روی هستهٔ مشترک ``jobs.replay`` است — همان
منطقی که اندپوینت ادمین ``POST /api/v1/jobs/queue/replay`` هم از آن
استفاده می‌کند؛ پس رفتار CLI و پنل ادمین همیشه یکسان است.

جریان کار:
  1. ``LRANGE job:dead 0 -1`` — خواندن همه پیام‌های dead-letter
  2. فیلتر اختیاری (``--job-name`` / ``--search`` / ``--limit``)
  3. برای هر پیام:
       - ``attempt`` به ۱ ریست می‌شود (بودجه retry تازه)
       - ``token`` به توکن جاری به‌روز می‌شود
       - ``LPUSH job:queue <پیام>`` و فقط بعد از موفقیت → ``LREM job:dead``
  4. گزارش نهایی + سایز زنده صف‌ها

مصرف:
    python scripts/replay_dead_letter.py                    # لیست + replay همه
    python scripts/replay_dead_letter.py --list             # فقط نمایش، بدون تغییر
    python scripts/replay_dead_letter.py --dry-run          # نمایش پیام‌هایی که replay می‌شوند
    python scripts/replay_dead_letter.py --job-name SyncQuotesJob
    python scripts/replay_dead_letter.py --search "timeout"
    python scripts/replay_dead_letter.py --limit 10
    python scripts/replay_dead_letter.py --discard          # حذف از job:dead بدون replay
    python scripts/replay_dead_letter.py --summary          # گزارش خلاصه (همان dead_letter_report.py) — فقط خواندنی
    python scripts/replay_dead_letter.py --summary --window today
    python scripts/replay_dead_letter.py --summary --no-save
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

# --- auto PYTHONPATH ---
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

from core.config import settings
from jobs.replay import (
    SUMMARY_WINDOWS,
    current_token,
    replay_dead_letter_messages,
    summarize_dead_letter,
)

# Windows consoles default to cp1252 — force UTF-8 so emoji/Persian print.
for _stream in (sys.stdout, sys.stderr):
    with suppress(AttributeError, ValueError):
        _stream.reconfigure(encoding="utf-8")

# اسم‌هایی که تست‌ها patch می‌کنند — عمداً همین‌جا نگه داشته می‌شوند:
#   _get_redis, _current_token, settings, main


def _current_token() -> str:
    """توکن احراز هویت جاری — دقیقاً همان منطق Publisher."""
    return current_token(settings.job_queue_token)


async def _get_redis() -> Any | None:
    """بازگرداندن redis client مشترک (None وقتی در دسترس نیست)."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        await cache.initialize()
        return cache.client
    except Exception:
        return None


def _format_message(msg: Any) -> str:
    """نمایش تک‌خطی یک پیام dead-letter از ReplayMessage."""
    return (
        f"  {msg.job_name:24s} | attempt={msg.attempt:<3} | "
        f"{str(msg.job_id)[:12]:12s} | {str(msg.error or '')[:80]}"
    )


async def _run_summary(redis: Any, dead_queue: str, args: argparse.Namespace) -> None:
    """حالت --summary — گزارش خلاصهٔ dead-letter بدون تغییر صف.

    همان خروجی و فایل‌های گزارش ``scripts/dead_letter_report.py`` را تولید
    می‌کند (هستهٔ مشترک ``jobs.replay.summarize_dead_letter`` + رندر مشترک
    ``scripts.dead_letter_report``) تا گزارش ترمینال و پنل ادمین همیشه
    یکسان باشند. فقط خواندنی است — صف دست‌نخورده می‌ماند.
    """
    from datetime import UTC, datetime

    # رندر مشترک — lazy import تا بارگذاری عادی replay سنگین نشود.
    from scripts.dead_letter_report import _print_summary, _save_report  # noqa: PLC0415

    if args.window not in SUMMARY_WINDOWS:
        print(f"❌ بازهٔ نامعتبر: {args.window!r} — باید یکی از {SUMMARY_WINDOWS} باشد")
        sys.exit(1)
    if args.since is not None and args.since < 0:
        print("❌ --since باید یک عدد epoch غیرمنفی باشد")
        sys.exit(1)

    generated_at = datetime.now(UTC).isoformat()

    try:
        summary = await summarize_dead_letter(
            redis,
            dead_queue=dead_queue,
            window=args.window,
            since=args.since,
        )
    except Exception as exc:  # noqa: BLE001 — connection errors surface cleanly
        print(f"❌ خطا در خواندن {dead_queue}: {exc}")
        sys.exit(1)

    _print_summary(summary, generated_at)

    if summary.total == 0:
        print("\nℹ️ صف dead-letter خالی است — گزارشی برای تحلیل وجود ندارد.")
        return

    # ── Save JSON/Markdown (همانند dead_letter_report.py) ────────────
    if not args.no_save:
        _save_report(summary, generated_at, "replay-cli")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay dead-letter job messages back to the main job queue",
    )
    parser.add_argument("--job-name", default=None, help="فقط جاب‌های با این نام (exact)")
    parser.add_argument("--search", default=None, help="جستجوی زیررشته در کل پیام (job_name / error / ...)")
    parser.add_argument("--limit", type=int, default=0, help="حداکثر تعداد پیام برای پردازش (0 = همه)")
    parser.add_argument("--list", action="store_true", help="فقط لیست پیام‌ها، بدون اعمال تغییر")
    parser.add_argument("--dry-run", action="store_true", help="نمایش عملیات بدون لمس Redis")
    parser.add_argument("--discard", action="store_true", help="حذف پیام‌ها از job:dead بدون replay")
    parser.add_argument("--queue", default=None, help="نام صف اصلی (پیش‌فرض: settings.job_queue_name)")
    parser.add_argument("--dead", default=None, help="نام صف dead-letter (پیش‌فرض: settings.job_queue_dead_letter)")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="گزارش خلاصهٔ dead-letter (همان dead_letter_report.py) — فقط خواندنی، صف تغییر نمی‌کند",
    )
    parser.add_argument(
        "--window",
        default="all",
        help="بازهٔ زمانی dead_lettered_at برای --summary: all | today | week | 24h",
    )
    parser.add_argument(
        "--since",
        type=float,
        default=None,
        help="آستانهٔ صریح (epoch seconds) برای --summary — جایگزین --window می‌شود",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="در حالت --summary: فقط نمایش، بدون ذخیره فایل گزارش",
    )
    args = parser.parse_args()

    queue_name = args.queue or settings.job_queue_name
    dead_queue = args.dead or settings.job_queue_dead_letter

    redis = await _get_redis()
    if redis is None:
        print("❌ Redis در دسترس نیست — صف قابل خواندن نیست.")
        sys.exit(1)

    if args.summary:
        await _run_summary(redis, dead_queue, args)
        return

    if args.list:
        mode = "list"
    elif args.dry_run:
        mode = "dry-run"
    elif args.discard:
        mode = "discard"
    else:
        mode = "replay"

    print(f"📥 پیام‌های dead-letter ({dead_queue}): در حال خواندن ...")
    result = await replay_dead_letter_messages(
        redis,
        queue_name=queue_name,
        dead_queue=dead_queue,
        token=_current_token(),
        job_name=args.job_name,
        search=args.search,
        limit=args.limit,
        mode=mode,
    )

    if result.total == 0:
        print("✅ صف dead-letter خالی است (یا هیچ پیامی مطابق فیلتر نیست) — کاری نیست.")
        return

    if args.job_name or args.search:
        print(f"🔍 فیلتر اعمال شد → {result.total} پیام مطابقت دارد")
    if args.limit and args.limit > 0:
        print(f"🔢 محدود به {result.total} پیام")

    print("\n📋 پیام‌های انتخابی:")
    for i, msg in enumerate(result.messages, 1):
        print(f"[{i}] {_format_message(msg)}")

    # ── Read-only modes ──────────────────────────────────────────────
    if mode == "list":
        print("\nℹ️ حالت --list — فقط نمایش، تغییری اعمال نشد.")
        return
    if mode == "dry-run":
        print(f"\n🔍 Dry-run — {result.total} پیام replay می‌شد (بدون اعمال).")
        return

    # ── Discard mode ─────────────────────────────────────────────────
    if mode == "discard":
        print(
            f"\n🗑️ {result.discarded} پیام از {dead_queue} حذف شد (بدون replay). "
            f"باقی‌مانده: {result.dead_size}"
        )
        return

    # ── Replay mode ──────────────────────────────────────────────────
    print(f"\n🔁 در حال replay به {queue_name} ...")
    for i, msg in enumerate(result.messages, 1):
        if msg.status == "replayed":
            print(f"  ✅ [{i}/{result.total}] {msg.job_name:24s} → {queue_name}")
        else:
            print(f"  ❌ [{i}/{result.total}] {msg.job_name:24s}: {msg.message}")

    print("\n" + "=" * 60)
    print(
        f"🔁 نتایج: ✅ {result.replayed} پیام replay شد | "
        f"❌ {result.failed} ناموفق (در {dead_queue} ماندند)"
    )
    print(f"   {queue_name} = {result.queue_size} پیام | {dead_queue} = {result.dead_size} پیام")
    print("=" * 60)

    if result.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
