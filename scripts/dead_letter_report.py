#!/usr/bin/env python
"""
📊 Dead-Letter Queue Report — گزارش خلاصه از پیام‌های job:dead

تولید یک گزارش تحلیلی از صف dead-letter (``job:dead``) تا مشخص شود
کدام جاب‌ها بیشتر شکست می‌خورند، خطاها در کدام دسته‌بندی‌ها تکرار می‌شوند
و آیا یک پیام منطقی (job_id) چند بار dead شده است.

این اسکریپت از هستهٔ مشترک ``jobs.replay.summarize_dead_letter`` استفاده
می‌کند — همان منطقی که اندپوینت ادمین
``GET /api/v1/jobs/queue/summary`` هم از آن استفاده می‌کند.

خروجی:
  - گزارش متنی زیبا در ترمینال
  - کپی JSON گزارش در ``json/reports/dead_letter_report.json``

مصرف:
    python scripts/dead_letter_report.py                  # گزارش واقعی از Redis
    python scripts/dead_letter_report.py --demo           # گزارش نمونه (بدون Redis)
    python scripts/dead_letter_report.py --dead job:dead  # صف سفارشی
    python scripts/dead_letter_report.py --no-save        # فقط نمایش، بدون ذخیره فایل

خروجی صفر: وقتی Redis در دسترس نیست یا صف خالی است، پیام واضح داده می‌شود
(کد خروج ۰ برای خالی، ۱ برای خطای اتصال).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
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
from jobs.replay import _build_summary, resolve_since, summarize_dead_letter

REPORT_DIR = Path(_project_root) / "json" / "reports"


# ── Redis access (mirrors scripts/replay_dead_letter.py) ─────────────
async def _get_redis() -> Any | None:
    """بازگرداندن redis client مشترک (None وقتی در دسترس نیست)."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        await cache.initialize()
        return cache.client
    except Exception:
        return None


# ── Demo payloads (realistic dead-letter messages for --demo) ────────
def _demo_raw_messages() -> list[str]:
    """پیام‌های dead-letter نمونه با الگوهای خطای رایج (برای نمایش فرمت).

    ``dead_lettered_at`` شامل ترکیبی از «امروز» و «قدیمی‌تر» است تا فیلتر
    زمانی (--window) در حالت demo هم قابل نمایش باشد.
    """
    now = time.time()
    day = 24 * 3600
    messages = [
        {
            "job_name": "SyncQuotesJob",
            "job_id": "sync-q-20260810-001",
            "attempt": 3,
            "error": "DBError: SQLAlchemy OperationalError: connection refused "
                     "to postgres at localhost:5432",
            "dead_lettered_at": now - 2 * 3600,          # امروز
        },
        {
            "job_name": "SyncQuotesJob",
            "job_id": "sync-q-20260810-002",
            "attempt": 3,
            "error": "DBError: psycopg2.OperationalError: server closed the "
                     "connection unexpectedly",
            "dead_lettered_at": now - 6 * 3600,          # امروز
        },
        {
            "job_name": "SyncCodalJob",
            "job_id": "sync-c-20260810-003",
            "attempt": 3,
            "error": "TimeoutError: timed out waiting for codal.ir after 30s",
            "dead_lettered_at": now - 10 * 3600,         # امروز
        },
        {
            "job_name": "SyncCodalJob",
            "job_id": "sync-c-20260810-003",
            "attempt": 3,
            "error": "TimeoutError: timed out waiting for codal.ir after 30s",
            "dead_lettered_at": now - 10 * 3600,         # امروز (تکرار)
        },
        {
            "job_name": "BrsapiCandlestickJob",
            "job_id": "candle-20260810-007",
            "attempt": 3,
            "error": "HTTP 429: rate limit exceeded on Api.BrsApi.ir",
            "dead_lettered_at": now - 2 * day,           # ۲ روز پیش (خارج از today)
        },
        {
            "job_name": "BrsapiCandlestickJob",
            "job_id": "candle-20260810-008",
            "attempt": 3,
            "error": "HTTP 500: internal server error from Api.BrsApi.ir",
            "dead_lettered_at": now - 3 * day,           # ۳ روز پیش
        },
        {
            "job_name": "NewsFetchJob",
            "job_id": "news-20260810-011",
            "attempt": 2,
            "error": "JSONDecodeError: Expecting value: json decode failed at line 1 column 1",
            "dead_lettered_at": now - 12 * 3600,         # امروز
        },
        {
            "job_name": "ModelRetrainJob",
            "job_id": "ml-20260810-005",
            "attempt": 3,
            "error": "RuntimeError: Lock not acquired: job already running",
            "dead_lettered_at": now - 5 * day,           # ۵ روز پیش (در week)
        },
    ]
    return [json.dumps(m, ensure_ascii=False) for m in messages]


# ── Rendering ─────────────────────────────────────────────────────────
def _bar(count: int, max_count: int, width: int = 30) -> str:
    """نوار افقی ساده برای نمایش نسبی فراوانی."""
    if max_count <= 0:
        return ""
    filled = max(1, round(width * count / max_count))
    return "█" * filled + "░" * (width - filled)


def _render_markdown(summary: Any, generated_at: str) -> str:
    """تبدیل DeadLetterSummary به گزارش Markdown."""
    lines: list[str] = []
    lines.append("# 📊 گزارش صف Dead-Letter (job:dead)")
    lines.append("")
    lines.append(f"- **تاریخ تولید:** {generated_at}")
    lines.append(f"- **تعداد کل پیام‌ها:** {summary.total}")
    lines.append(f"- **پیام‌های malformed:** {summary.malformed}")
    lines.append("")

    lines.append("## 📋 توزیع job_name ها")
    lines.append("")
    lines.append("| job_name | تعداد |")
    lines.append("|----------|-------|")
    for item in summary.job_names:
        lines.append(f"| `{item['name']}` | {item['count']} |")
    lines.append("")

    lines.append("## 🐛 دسته‌بندی خطاها")
    lines.append("")
    lines.append("| دسته | تعداد |")
    lines.append("|------|-------|")
    for item in summary.error_categories:
        lines.append(f"| {item['category']} | {item['count']} |")
    lines.append("")

    lines.append("## 🔁 خطاهای خام پرتکرار (top)")
    lines.append("")
    lines.append("| خطا | تعداد |")
    lines.append("|-----|-------|")
    for item in summary.top_errors:
        lines.append(f"| {item['error']} | {item['count']} |")
    lines.append("")

    lines.append("## 🔄 پیام‌های تکراری (job_id مشترک)")
    lines.append("")
    if summary.repeated:
        lines.append("| job_name | job_id | تعداد کپی |")
        lines.append("|----------|--------|-----------|")
        for item in summary.repeated:
            lines.append(f"| `{item['job_name']}` | `{item['job_id']}` | {item['count']} |")
        lines.append("")
        lines.append(f"**تعداد پیام‌های تکراری:** {summary.repeated_messages}")
    else:
        lines.append("_هیچ پیام تکراری یافت نشد._")
    lines.append("")
    return "\n".join(lines)


def _print_summary(summary: Any, generated_at: str) -> None:
    """چاپ گزارش متنی زیبا در ترمینال."""
    print("=" * 62)
    print("📊  گزارش خلاصه صف Dead-Letter")
    print("=" * 62)
    print(f"   صف:        {summary.queue or settings.job_queue_dead_letter}")
    print(f"   تولید شده: {generated_at}")
    window_lbl = getattr(summary, "window", "all") or "all"
    since_lbl = getattr(summary, "since", None)
    if since_lbl:
        print(f"   بازه:      {window_lbl} (از {datetime.fromtimestamp(since_lbl, tz=UTC).isoformat()})")
    print(f"   کل پیام‌ها: {summary.total}  |  malformed: {summary.malformed}")
    print()

    print("📋 توزیع job_name:")
    if not summary.job_names:
        print("   — خالی —")
    max_count = max((i["count"] for i in summary.job_names), default=1)
    for item in summary.job_names:
        print(
            f"   {item['name']:24s} {item['count']:>5d}  "
            f"{_bar(item['count'], max_count)}"
        )
    print()

    print("🐛 دسته‌بندی خطاها:")
    if not summary.error_categories:
        print("   — خالی —")
    max_count = max((i["count"] for i in summary.error_categories), default=1)
    for item in summary.error_categories:
        print(
            f"   {item['category']:16s} {item['count']:>5d}  "
            f"{_bar(item['count'], max_count)}"
        )
    print()

    print("🔁 خطاهای خام پرتکرار (top 5):")
    for i, item in enumerate(summary.top_errors[:5], 1):
        print(f"   {i}. [{item['count']}×] {item['error'][:95]}")
    print()

    print("🔄 پیام‌های تکراری (job_id مشترک):")
    if summary.repeated:
        for item in summary.repeated:
            print(
                f"   • {item['job_name']} / {item['job_id']} "
                f"— {item['count']} کپی"
            )
        print(f"   → مجموع پیام‌های تکراری: {summary.repeated_messages}")
    else:
        print("   — هیچ پیام تکراری یافت نشد —")
    print("=" * 62)


# ── Main ─────────────────────────────────────────────────────────────
def _build_payload(summary: Any, generated_at: str, source: str) -> dict[str, Any]:
    """ساخت ساختار JSON گزارش برای ذخیره در فایل."""
    return {
        "generated_at": generated_at,
        "source": source,
        "queue": summary.queue,
        "window": getattr(summary, "window", "all") or "all",
        "since": getattr(summary, "since", None),
        "total": summary.total,
        "malformed": summary.malformed,
        "job_names": summary.job_names,
        "error_categories": summary.error_categories,
        "top_errors": summary.top_errors,
        "repeated": summary.repeated,
        "repeated_messages": summary.repeated_messages,
    }


def _save_report(summary: Any, generated_at: str, source: str) -> None:
    """ذخیره گزارش در ``json/reports`` (JSON + Markdown) — مشترک بین CLIها.

    هم ``dead_letter_report.py`` و هم ``replay_dead_letter.py --summary``
    از این تابع استفاده می‌کنند تا دو نقطهٔ ورود هرگز از هم جدا نشوند.
    """
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        payload = _build_payload(summary, generated_at, source)
        report_path = REPORT_DIR / "dead_letter_report.json"
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n💾 گزارش JSON ذخیره شد: {report_path}")
        md_path = REPORT_DIR / "dead_letter_report.md"
        md_path.write_text(
            _render_markdown(summary, generated_at),
            encoding="utf-8",
        )
        print(f"💾 گزارش Markdown ذخیره شد: {md_path}")
    except OSError as exc:
        print(f"⚠️ ذخیره فایل ناموفق: {exc}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summary report of job:dead messages (error distribution, "
                    "job_name counts, repetitions)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="گزارش نمونه با دادهٔ واقع‌گرایانه (بدون نیاز به Redis)",
    )
    parser.add_argument(
        "--dead",
        default=None,
        help="نام صف dead-letter (پیش‌فرض: settings.job_queue_dead_letter)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="فقط نمایش در ترمینال، بدون ذخیره فایل JSON",
    )
    parser.add_argument(
        "--window",
        default="all",
        help="بازهٔ زمانی dead_lettered_at: all | today | week | 24h",
    )
    parser.add_argument(
        "--since",
        type=float,
        default=None,
        help="آستانهٔ صریح (epoch seconds) — جایگزین --window می‌شود",
    )
    args = parser.parse_args()

    dead_queue = args.dead or settings.job_queue_dead_letter
    generated_at = datetime.now(UTC).isoformat()

    if args.demo:
        effective_since = args.since if args.since is not None else resolve_since(args.window)
        summary = _build_summary(
            _demo_raw_messages(),
            dead_queue,
            window=args.window,
            since=effective_since,
        )
        source = "demo"
        print("🧪 حالت --demo — گزارش با دادهٔ نمونه (نه دادهٔ واقعی)\n")
    else:
        redis = await _get_redis()
        if redis is None:
            print(
                "❌ Redis در دسترس نیست — گزارش واقعی قابل تولید نیست.\n"
                "   • Redis را بالا بیاورید (redis-server یا docker compose up -d redis)\n"
                "   • یا با `--demo` فرمت گزارش را ببینید."
            )
            sys.exit(1)
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
        source = "redis"

    _print_summary(summary, generated_at)

    if summary.total == 0 and not args.demo:
        print("\nℹ️ صف dead-letter خالی است — گزارشی برای تحلیل وجود ندارد.")
        return

    # ── Save JSON report ─────────────────────────────────────────────
    if not args.no_save:
        _save_report(summary, generated_at, source)


if __name__ == "__main__":
    asyncio.run(main())
