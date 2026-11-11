"""Offline tests for the legacy↔mirror parity audit (read-only SQL).

The audit answers “are ``news_articles`` and ``news_items`` in sync right now?”
with counts over a recent window. It must stay a pure reader: any mutation in
this module would be a data-loss footgun in an ops command.
"""

from __future__ import annotations

from typing import Any

import pytest

from services.news_parity import news_parity_report

COUNT_KEYS = (
    "legacy_total",
    "mirror_total",
    "legacy_recent",
    "mirror_recent",
    "legacy_missing_mirror",
    "mirror_missing_legacy",
    "linked_rows",
    "linked_missing_time",
)


def _row(**overrides: Any) -> dict[str, Any]:
    base = dict.fromkeys(COUNT_KEYS, 0)
    base.update(overrides)
    return base


class _Mappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def one(self) -> dict[str, Any]:
        return self._rows[0]

    def all(self) -> list[dict[str, Any]]:
        return list(self._rows)


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _Mappings:
        return _Mappings(self._rows)


class _Session:
    def __init__(self, *result_sets: list[dict[str, Any]]) -> None:
        self._queue = list(result_sets)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        self.calls.append((" ".join(str(statement).split()), params or {}))
        row = self._queue.pop(0) if self._queue else []
        return _Result(row if isinstance(row, list) else [row])


async def test_parity_is_ok_when_both_sides_agree() -> None:
    session = _Session(_row(legacy_total=10, mirror_total=10, legacy_recent=4, mirror_recent=4))

    report = await news_parity_report(session)  # type: ignore[arg-type]

    assert report["parity_ok"] is True
    assert report["legacy_total"] == 10
    assert report["mirror_total"] == 10
    assert report["sample_missing"] == []
    assert report["window_days"] == 7


async def test_missing_mirror_rows_break_parity_and_are_sampled() -> None:
    session = _Session(
        _row(legacy_recent=5, mirror_recent=4, legacy_missing_mirror=1),
        [{"id": "news_1", "title": "خبر جاافتاده", "url": "https://example.invalid/x"}],
    )

    report = await news_parity_report(session, days=3)  # type: ignore[arg-type]

    assert report["parity_ok"] is False
    assert report["legacy_missing_mirror"] == 1
    assert report["sample_missing"][0]["id"] == "news_1"
    assert session.calls[1][1] == {"days": 3, "limit": 10}


async def test_missing_legacy_rows_break_parity_without_sampling() -> None:
    session = _Session(_row(mirror_missing_legacy=2))

    report = await news_parity_report(session)  # type: ignore[arg-type]

    assert report["parity_ok"] is False
    assert report["mirror_missing_legacy"] == 2
    assert len(session.calls) == 1, "no sample query when only the mirror is ahead"


@pytest.mark.parametrize("days", [0, -4, 500])
async def test_window_is_clamped(days: int) -> None:
    session = _Session(_row())

    await news_parity_report(session, days=days)  # type: ignore[arg-type]

    clamped = session.calls[0][1]["days"]
    assert 1 <= clamped <= 90


def test_module_generates_select_only() -> None:
    """Guard: an ops audit must never write."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "services" / "news_parity.py").read_text(
        encoding="utf-8"
    )
    upper = source.upper()
    for verb in ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE ", "DROP "):
        assert verb not in upper, f"parity audit must not contain {verb!r}"
