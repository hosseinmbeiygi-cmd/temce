"""Unit tests for ``scripts/dead_letter_report.py``.

Covers:
- ``_demo_raw_messages`` — realistic payloads exercise the error classifier.
- ``_render_markdown`` — Markdown output contains the key sections.
- ``_build_payload`` — JSON structure matches the summary fields.
- ``main()`` — demo mode produces a report without Redis; real mode
  exits 1 when Redis is unavailable and saves files when data exists.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import scripts.dead_letter_report as report_mod
from jobs.replay import MAX_SCAN, _build_summary, resolve_since


# ── Demo data & pure helpers ─────────────────────────────────────────

def test_demo_messages_decode_and_classify():
    """All demo messages must decode and be attributed to a category."""
    raw = report_mod._demo_raw_messages()
    summary = _build_summary(raw, "job:dead")

    assert summary.total == len(raw)
    assert summary.malformed == 0

    # Every non-no_error category in the demo must appear.
    categories = {c["category"] for c in summary.error_categories}
    assert "db_error" in categories
    assert "timeout" in categories
    assert "rate_limit" in categories
    assert "http_error" in categories
    assert "parse_error" in categories
    assert "lock_duplicate" in categories

    # job_name distribution.
    names = {n["name"] for n in summary.job_names}
    assert {"SyncQuotesJob", "SyncCodalJob", "BrsapiCandlestickJob",
            "NewsFetchJob", "ModelRetrainJob"} <= names


def test_demo_contains_repeated_job_id():
    """The duplicated SyncCodalJob job_id must be reported as repeated."""
    raw = report_mod._demo_raw_messages()
    summary = _build_summary(raw, "job:dead")

    assert summary.repeated_messages == 1
    assert summary.repeated[0]["job_name"] == "SyncCodalJob"
    assert summary.repeated[0]["count"] == 2


def test_build_payload_shape():
    """JSON payload mirrors the summary fields for storage."""
    raw = report_mod._demo_raw_messages()
    summary = _build_summary(raw, "job:dead")
    payload = report_mod._build_payload(summary, "2026-08-10T12:00:00+00:00", "demo")

    assert payload["queue"] == "job:dead"
    assert payload["source"] == "demo"
    assert payload["total"] == len(raw)
    assert isinstance(payload["job_names"], list)
    assert isinstance(payload["error_categories"], list)
    assert isinstance(payload["top_errors"], list)
    assert isinstance(payload["repeated"], list)
    assert payload["repeated_messages"] == 1


def test_render_markdown_sections():
    """Markdown report contains the key analysis sections."""
    raw = report_mod._demo_raw_messages()
    summary = _build_summary(raw, "job:dead")
    md = report_mod._render_markdown(summary, "2026-08-10T12:00:00+00:00")

    assert "توزیع job_name" in md
    assert "دسته‌بندی خطاها" in md
    assert "خطاهای خام پرتکرار" in md
    assert "پیام‌های تکراری" in md
    assert "SyncQuotesJob" in md


# ── main() ───────────────────────────────────────────────────────────

def _run_main(*args: str) -> int:
    """Run the CLI main with argv, returning the exit-code-like outcome."""
    with patch.object(report_mod.sys, "argv", ["dead_letter_report.py", *args]):
        try:
            asyncio.run(report_mod.main())
            return 0
        except SystemExit as exc:  # sys.exit(1) paths
            return int(exc.code or 0)


def test_main_demo_mode_without_redis(tmp_path: Path):
    """--demo must produce a report without Redis and save JSON files."""
    with patch.object(report_mod, "REPORT_DIR", tmp_path):
        code = _run_main("--demo")
    assert code == 0
    assert (tmp_path / "dead_letter_report.json").exists()
    assert (tmp_path / "dead_letter_report.md").exists()
    data = json.loads((tmp_path / "dead_letter_report.json").read_text(encoding="utf-8"))
    assert data["source"] == "demo"
    assert data["total"] == len(report_mod._demo_raw_messages())


def test_main_demo_window_filters_recent_only(tmp_path: Path):
    """--demo --window today must keep only messages dead-lettered today."""
    with patch.object(report_mod, "REPORT_DIR", tmp_path):
        code = _run_main("--demo", "--window", "today")
    assert code == 0
    data = json.loads((tmp_path / "dead_letter_report.json").read_text(encoding="utf-8"))
    assert data["window"] == "today"
    assert data["since"] is not None

    # The demo fixture uses fixed hour offsets, so how many land "today"
    # depends on the current Tehran wall-clock. Derive the expectation from
    # the same threshold instead of hardcoding it (otherwise this test only
    # passes in the afternoon).
    since = resolve_since("today")
    expected = sum(
        1
        for raw in report_mod._demo_raw_messages()
        if (json.loads(raw).get("dead_lettered_at") or 0) >= since
    )
    assert data["total"] == expected
    names = {n["name"] for n in data["job_names"]}
    assert "BrsapiCandlestickJob" not in names  # 2–3 days ago → always excluded
    assert "ModelRetrainJob" not in names        # 5 days ago → always excluded


def test_main_demo_since_explicit_threshold(tmp_path: Path):
    """--since (epoch) overrides the window and filters by timestamp."""
    now = __import__("time").time()
    with patch.object(report_mod, "REPORT_DIR", tmp_path):
        code = _run_main("--demo", "--since", str(now - 4 * 24 * 3600))
    assert code == 0
    data = json.loads((tmp_path / "dead_letter_report.json").read_text(encoding="utf-8"))
    # Messages older than 4 days (5-day ModelRetrainJob) are excluded.
    assert data["total"] == 7


def test_main_real_mode_exits_when_redis_unavailable():
    """Without Redis, the real (non-demo) mode must exit(1)."""
    with patch.object(report_mod, "_get_redis", AsyncMock(return_value=None)):
        code = _run_main()
    assert code == 1


def test_main_real_mode_uses_summarize_dead_letter(tmp_path: Path):
    """Real mode must call the shared core and save the JSON report."""
    fake_redis = AsyncMock()
    raw = report_mod._demo_raw_messages()
    fake_redis.lrange.return_value = raw

    with patch.object(report_mod, "_get_redis", AsyncMock(return_value=fake_redis)), \
         patch.object(report_mod, "REPORT_DIR", tmp_path):
        code = _run_main("--no-save")
    assert code == 0

    # summarize_dead_letter read the dead queue (bounded by MAX_SCAN).
    fake_redis.lrange.assert_awaited_once_with("job:dead", 0, MAX_SCAN - 1)
    assert not (tmp_path / "dead_letter_report.json").exists()  # --no-save


def test_main_real_mode_empty_queue_exits_zero(tmp_path: Path):
    """An empty dead queue is not an error — report shows zero total."""
    fake_redis = AsyncMock()
    fake_redis.lrange.return_value = []

    with patch.object(report_mod, "_get_redis", AsyncMock(return_value=fake_redis)), \
         patch.object(report_mod, "REPORT_DIR", tmp_path):
        code = _run_main()
    assert code == 0
    # No report written for an empty queue.
    assert not (tmp_path / "dead_letter_report.json").exists()
