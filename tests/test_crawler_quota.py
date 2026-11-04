"""Simulation tests for the crawler's hard 10,000-requests/day quota.

No network and no PostgreSQL are involved: ``z.py`` is imported only for its
quota ledger, with the state/journal paths redirected into ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

os.environ.setdefault("BRSAPI_KEY", "test-key")
os.environ.setdefault("DB_NAME", "test-db")
os.environ.setdefault("DB_USER", "test-user")
os.environ.setdefault("DB_PASSWORD", "test-pass")

import z  # noqa: E402


@pytest.fixture()
def quota(tmp_path, monkeypatch):
    monkeypatch.setattr(z, "STATE_FILE", str(tmp_path / "crawler_state.json"))
    monkeypatch.setattr(z, "QUOTA_JOURNAL", str(tmp_path / "crawler_quota.jsonl"))
    monkeypatch.setattr(z, "HOLIDAYS_FILE", str(tmp_path / "market_holidays.json"))
    monkeypatch.setattr(z, "MARKET_NO_DATA_FILE", str(tmp_path / "market_no_data.json"))
    monkeypatch.setattr(z, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(z, "MIN_DELAY_PER_REQ", 0.0)
    z._HOLIDAYS.clear()
    z._NO_DATA.clear()
    yield tmp_path
    z._HOLIDAYS.clear()
    z._NO_DATA.clear()


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload
        self.text = ""

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response):
        self._response = response

    def get(self, *args, **kwargs):
        return self._response


def make_collector(limiter, response):
    collector = object.__new__(z.SmartCollector)
    collector.limiter = limiter
    collector.stop_event = threading.Event()
    collector._http_local = threading.local()
    collector.ins_map = {}
    collector.data_errors = 0
    collector._session = lambda: FakeSession(response)
    return collector


def make_limiter(limit, **kwargs):
    return z.RateLimiter(
        daily_limit=limit, burst_limit=10**6, burst_window=60, **kwargs
    )


def attempts(limiter, count):
    return [limiter.acquire_slot()[0] for _ in range(count)]


def read_state():
    with open(z.STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_default_daily_limit_is_10000(quota):
    assert z.DAILY_LIMIT == 10_000
    assert make_limiter(z.DAILY_LIMIT).daily_limit == 10_000


def test_threads_cannot_exceed_cap(quota):
    limit = 300
    limiter = make_limiter(limit)

    def worker(_):
        return sum(attempts(limiter, 40))

    with ThreadPoolExecutor(max_workers=48) as pool:
        granted = sum(pool.map(worker, range(48)))

    assert granted == limit
    assert limiter.acquire_slot() == (False, "DAILY_LIMIT_EXCEEDED")


def test_two_limiters_same_process(quota):
    limit = 50
    first, second = make_limiter(limit), make_limiter(limit)
    granted = 0
    for _ in range(limit * 4):
        limiter = first if granted % 2 == 0 else second
        allowed, _ = limiter.acquire_slot()
        granted += 1 if allowed else 0
    assert granted == limit


def test_multiprocess_cannot_exceed_cap(quota):
    limit = 240
    workers = 4
    try:
        procs = []
        for _ in range(workers):
            code = (
                "import os, sys\n"
                "sys.path.insert(0, os.getcwd())\n"
                "os.environ.setdefault('BRSAPI_KEY', 'test-key')\n"
                "os.environ.setdefault('DB_NAME', 'test-db')\n"
                "os.environ.setdefault('DB_USER', 'test-user')\n"
                "os.environ.setdefault('DB_PASSWORD', 'test-pass')\n"
                "import z\n"
                "z.STATE_FILE = sys.argv[1]\n"
                "z.QUOTA_JOURNAL = sys.argv[2]\n"
                "z.MIN_DELAY_PER_REQ = 0.0\n"
                "lim = z.RateLimiter(daily_limit=int(sys.argv[3]),"
                " burst_limit=10**6, burst_window=60)\n"
                "print(sum(1 for _ in range(int(sys.argv[4])) if lim.acquire_slot()[0]))\n"
            )
            procs.append(subprocess.Popen(
                [sys.executable, "-c", code, z.STATE_FILE, z.QUOTA_JOURNAL,
                 str(limit), "150"],
                cwd=os.path.dirname(z.__file__),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
        granted = 0
        for proc in procs:
            out, err = proc.communicate(timeout=120)
            assert proc.returncode == 0, err
            granted += int(out.strip())
    except (OSError, subprocess.SubprocessError) as e:  # pragma: no cover
        pytest.skip(f"multiprocess simulation unavailable: {e}")

    assert granted == limit
    assert make_limiter(limit).acquire_slot() == (False, "DAILY_LIMIT_EXCEEDED")


def test_state_file_deletion_does_not_reset(quota):
    limit = 20
    limiter = make_limiter(limit)
    assert sum(attempts(limiter, limit)) == limit

    os.remove(z.STATE_FILE)
    restarted = make_limiter(limit)
    assert restarted.acquire_slot() == (False, "DAILY_LIMIT_EXCEEDED")


def test_journal_deletion_does_not_reset(quota):
    limit = 20
    limiter = make_limiter(limit)
    assert sum(attempts(limiter, limit)) == limit

    os.remove(z.QUOTA_JOURNAL)
    restarted = make_limiter(limit)
    assert restarted.acquire_slot() == (False, "DAILY_LIMIT_EXCEEDED")


def test_corrupt_journal_fails_closed(quota):
    make_limiter(5).acquire_slot()
    with open(z.QUOTA_JOURNAL, "a", encoding="utf-8") as f:
        f.write("{not json}\n")
    with pytest.raises(RuntimeError):
        make_limiter(5)


def test_restart_preserves_counter(quota):
    limit = 40
    first = make_limiter(limit)
    assert sum(attempts(first, 25)) == 25

    second = make_limiter(limit)
    assert sum(attempts(second, 100)) == limit - 25


def test_clock_rollback_stops_crawler(quota):
    wall = [1_700_000_000.0]
    mono = [1_000.0]
    limiter = make_limiter(10, now_fn=lambda: wall[0], mono_fn=lambda: mono[0])
    assert sum(attempts(limiter, 3)) == 3

    wall[0] -= 3600
    mono[0] += 1
    assert limiter.acquire_slot() == (False, "CLOCK_ROLLBACK")


def test_clock_jump_forward_cannot_reset_cap(quota):
    wall = [1_700_000_000.0]
    mono = [1_000.0]
    limit = 5
    limiter = make_limiter(limit, now_fn=lambda: wall[0], mono_fn=lambda: mono[0])
    assert sum(attempts(limiter, limit)) == limit

    wall[0] += 2 * 24 * 3600
    mono[0] += 10
    assert limiter.acquire_slot() == (False, "ROLLING_LIMIT_EXCEEDED")


def test_ten_thousand_requests_then_hard_stop(quota, monkeypatch):
    """Full-scale simulation: exactly 10,000 grants, then the 10,001st is refused."""
    monkeypatch.setattr(z.os, "fsync", lambda _fd: None)
    limiter = make_limiter(z.DAILY_LIMIT)

    granted = 0
    for _ in range(z.DAILY_LIMIT):
        allowed, count = limiter.acquire_slot()
        assert allowed, f"refused early at {count}"
        granted += 1

    assert granted == 10_000
    assert limiter.acquire_slot() == (False, "DAILY_LIMIT_EXCEEDED")
    assert read_state()["requests_today"] == 10_000


def test_retries_consume_quota(quota, monkeypatch):
    monkeypatch.setattr(z.time, "sleep", lambda _seconds: None)
    collector = make_collector(make_limiter(100), FakeResponse(500, ValueError("not json")))

    result = collector.fetch_transaction(("X", "1403-01-01", str(quota / "x.json")))

    assert result == "API_STOP"
    assert read_state()["requests_today"] == z.MAX_ATTEMPTS


def test_http_424_is_no_data_single_request(quota):
    collector = make_collector(make_limiter(100), FakeResponse(424, {"status": "dependency_failed"}))

    out = quota / "1402-07-05.json"
    result = collector.fetch_transaction(("X", "1402-07-05", str(out)))

    assert result == "EMPTY"
    assert out.exists()
    assert read_state()["requests_today"] == 1
    with open(z.MARKET_NO_DATA_FILE, encoding="utf-8") as f:
        assert json.load(f) == {"1402-07-05": [1, 0]}


def test_invalid_rows_are_rejected_not_zeroed(quota):
    for bad in (
        {"row": None, "volume": "10", "price": "100"},
        {"row": "abc", "volume": "10", "price": "100"},
        {"row": "1", "volume": None, "price": "100"},
        {"row": "1", "volume": "10", "price": "xyz"},
    ):
        with pytest.raises(ValueError):
            z._extract_trade_rows([bad])

    rows = z._extract_trade_rows(
        [{"row": "1234.0", "volume": "1,200", "price": "10.5", "canceled": "0"}]
    )
    assert rows == [
        {"seq_no": 1234, "time": "", "volume": 1200, "price": 10.5, "is_canceled": 0}
    ]


def test_invalid_payload_fails_task_without_marker(quota):
    payload = [{"row": None, "volume": "1", "price": "2"}]
    collector = make_collector(make_limiter(10), FakeResponse(200, payload))
    out = quota / "bad.json"

    assert collector.fetch_transaction(("X", "1405-01-11", str(out))) == "DATA_ERROR"
    assert not out.exists()
    assert collector.data_errors == 1


def test_run_budget_counts_http_slots(quota):
    limiter = make_limiter(100, run_budget=5)

    assert sum(attempts(limiter, 10)) == 5
    assert limiter.acquire_slot() == (False, "RUN_BUDGET_EXCEEDED")
    assert read_state()["requests_today"] == 5


def test_run_budget_limits_retries(quota, monkeypatch):
    monkeypatch.setattr(z.time, "sleep", lambda _seconds: None)
    collector = make_collector(
        make_limiter(100, run_budget=1), FakeResponse(500, ValueError("not json"))
    )

    result = collector.fetch_transaction(("X", "1403-01-01", str(quota / "c.json")))

    assert result == "RUN_STOP"
    assert read_state()["requests_today"] == 1


def test_quota_day_uses_tehran_timezone(quota):
    late_utc = datetime(2026, 10, 30, 22, 0, tzinfo=UTC).timestamp()
    assert z.RateLimiter._today(late_utc) == "2026-10-31"


def test_generic_closed_message_does_not_blacklist_date(quota):
    collector = make_collector(
        make_limiter(10), FakeResponse(400, {"message_error": "این نماد تعطیل است"})
    )

    result = collector.fetch_transaction(("X", "1405-01-10", str(quota / "a.json")))

    assert result == "API_STOP"
    assert "1405-01-10" not in z._HOLIDAYS


def test_explicit_weekend_marks_market_holiday(quota):
    message = "The 'date' value falls on a weekend (Thursday). It is considered a holiday."
    collector = make_collector(make_limiter(10), FakeResponse(400, {"message_error": message}))

    result = collector.fetch_transaction(("X", "1405-01-10", str(quota / "b.json")))

    assert result == "EMPTY"
    assert "1405-01-10" in z._HOLIDAYS


def test_market_no_data_cancelled_by_real_data(quota):
    day = "1403-05-01"
    for _ in range(z.MARKET_NO_DATA_THRESHOLD):
        z._record_date_status(day, has_data=False)
    assert z._is_market_no_data(day)

    z._record_date_status(day, has_data=True)
    assert not z._is_market_no_data(day)


def test_market_no_data_date_is_skipped_in_tasks(quota):
    day = z._parse_jalali("1403-05-01")
    assert not z.is_market_closed(day)
    date_str = day.strftime("%Y-%m-%d")
    for _ in range(z.MARKET_NO_DATA_THRESHOLD):
        z._record_date_status(date_str, has_data=False)

    collector = object.__new__(z.SmartCollector)
    collector.symbols = ["X"]
    collector.skipped_closed = 0
    collector.skipped_no_data = 0
    collector.start_date = day
    collector.end_date = day
    collector.db_resume = False
    collector.market_skip = True
    assert list(collector._iter_tasks()) == []
    assert collector.skipped_no_data == 1

    collector.market_skip = False
    collector.skipped_no_data = 0
    assert len(list(collector._iter_tasks())) == 1


def test_rows_record_data_status(quota, monkeypatch):
    monkeypatch.setattr(z, "_insert_trades", lambda symbol, date, rows, ins_map: (len(rows), 0))
    payload = [{"row": "1", "volume": "10", "price": "100"}]
    collector = make_collector(make_limiter(10), FakeResponse(200, payload))

    assert collector.fetch_transaction(("X", "1403-05-02", str(quota / "ok.json"))) == "OK"

    with open(z.MARKET_NO_DATA_FILE, encoding="utf-8") as f:
        assert json.load(f) == {"1403-05-02": [0, 1]}
