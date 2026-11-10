"""WS8: Signal journal + revoke events.

RED (before fixes):
  1. src.gold_desk.signal_journal does not exist — all tests ImportError.
  2. SignalJournalEntry dataclass does not exist.
  3. from_score_result() factory does not exist.
  4. as_revoked() method does not exist.
  5. append_journal() async function does not exist.
  6. revoke_signal() async function does not exist.
  7. list_journal() async function does not exist.

GREEN (after fixes):
  1. src/gold_desk/signal_journal.py created with SignalJournalEntry (frozen
     dataclass), append_journal(), revoke_signal(), list_journal() async
     functions using injectable cache (same pattern as WS3/WS5).
  2. from_score_result(score_result) → SignalJournalEntry with new UUID.
  3. as_revoked(reason) → new frozen instance with revoked=True.
  4. append_journal / revoke_signal / list_journal tested with in-memory
     mock cache — no live Redis required.

WS8 scope: journal is Redis-backed (TTL 7 days, max 100 entries). No DB
needed. revoke_signal() marks an existing entry as invalid; list_journal()
returns entries newest-first.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── in-memory mock cache (same pattern as WS3/WS5) ─────────────────────────

class _MemCache:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None):
        self._store[key] = value


# ─── 1. Import check ─────────────────────────────────────────────────────────

def test_import_signal_journal():
    """src.gold_desk.signal_journal must be importable.

    RED: module does not exist.
    GREEN: module created.
    """
    from src.gold_desk.signal_journal import (  # noqa: F401
        SignalJournalEntry,
        append_journal,
        list_journal,
        revoke_signal,
    )


# ─── 2. SignalJournalEntry dataclass ─────────────────────────────────────────

def test_journal_entry_has_required_fields():
    """SignalJournalEntry must have entry_id, scored_at, decision, total,
    available_weight, hard_stop_active, hard_stop_reason, components_summary.

    RED: class does not exist.
    GREEN: frozen dataclass with all fields.
    """
    from src.gold_desk.signal_journal import SignalJournalEntry

    entry = SignalJournalEntry(
        entry_id="test-id-001",
        scored_at="2026-11-10T12:00:00Z",
        decision="GREEN",
        total=85,
        available_weight=100,
        hard_stop_active=False,
        hard_stop_reason=None,
        components_summary={"bubble": 20, "nav": 18},
    )
    assert entry.entry_id == "test-id-001"
    assert entry.decision == "GREEN"
    assert entry.total == 85
    assert entry.revoked is False
    assert entry.revoke_reason is None


def test_journal_entry_to_dict():
    """to_dict() must include all fields.

    RED: class does not exist.
    GREEN: returns dict with all fields.
    """
    from src.gold_desk.signal_journal import SignalJournalEntry

    entry = SignalJournalEntry(
        entry_id="x",
        scored_at="2026-11-10T12:00:00Z",
        decision="YELLOW",
        total=60,
        available_weight=80,
        hard_stop_active=False,
        hard_stop_reason=None,
        components_summary={"bubble": 15},
    )
    d = entry.to_dict()
    assert "entry_id" in d
    assert "decision" in d
    assert "total" in d
    assert "revoked" in d
    assert "components_summary" in d


# ─── 3. from_score_result factory ────────────────────────────────────────────

def test_from_score_result_captures_decision():
    """from_score_result(result) must copy decision/total/available_weight/
    hard_stop fields from ScoreResult.

    RED: method does not exist.
    GREEN: factory builds entry from ScoreResult.
    """
    from src.gold_desk.scorer import compute_score
    from src.gold_desk.signal_journal import SignalJournalEntry

    result = compute_score(
        bubble_pct=3.0,
        nav_bubble_pct=0.3,
        bpr=2.5,
        net_inflow=6e9,
        xau_rsi=35.0,
        aed_gap_pct=0.3,
        nav_7d_pct=2.0,
    )
    entry = SignalJournalEntry.from_score_result(result)

    assert entry.decision == result.decision
    assert entry.total == result.total
    assert entry.available_weight == result.available_weight
    assert entry.hard_stop_active == result.hard_stop_active
    assert entry.hard_stop_reason == result.hard_stop_reason
    assert entry.revoked is False


def test_from_score_result_captures_components():
    """components_summary must contain the score value for every component.

    RED: method does not exist.
    GREEN: maps component name → value int.
    """
    from src.gold_desk.scorer import compute_score
    from src.gold_desk.signal_journal import SignalJournalEntry

    result = compute_score(
        bubble_pct=3.0,
        nav_bubble_pct=0.3,
        bpr=2.5,
        net_inflow=6e9,
        xau_rsi=35.0,
        aed_gap_pct=0.3,
        nav_7d_pct=2.0,
    )
    entry = SignalJournalEntry.from_score_result(result)

    for name, comp in result.components.items():
        assert name in entry.components_summary
        assert entry.components_summary[name] == comp.value


def test_from_score_result_generates_unique_ids():
    """Each call to from_score_result() must produce a different entry_id.

    RED: method does not exist.
    GREEN: uses uuid.uuid4().
    """
    from src.gold_desk.scorer import compute_score
    from src.gold_desk.signal_journal import SignalJournalEntry

    result = compute_score(
        bubble_pct=3.0, nav_bubble_pct=None, bpr=None, net_inflow=None,
        xau_rsi=None, aed_gap_pct=None, nav_7d_pct=None,
    )
    ids = {SignalJournalEntry.from_score_result(result).entry_id for _ in range(5)}
    assert len(ids) == 5, "from_score_result() must generate a unique UUID each call"


# ─── 4. as_revoked ───────────────────────────────────────────────────────────

def test_as_revoked_creates_new_entry_with_flag():
    """as_revoked(reason) must return a NEW frozen entry with revoked=True.

    RED: method does not exist.
    GREEN: returns new instance; original is unchanged (frozen=True).
    """
    from src.gold_desk.signal_journal import SignalJournalEntry

    original = SignalJournalEntry(
        entry_id="e1",
        scored_at="2026-11-10T10:00:00Z",
        decision="GREEN",
        total=90,
        available_weight=100,
        hard_stop_active=False,
        hard_stop_reason=None,
        components_summary={"bubble": 20},
    )
    revoked = original.as_revoked("داده BrsApi نادرست بود")

    assert revoked.revoked is True
    assert revoked.revoke_reason == "داده BrsApi نادرست بود"
    assert revoked.entry_id == original.entry_id  # same id
    assert revoked.decision == original.decision   # same decision
    assert original.revoked is False               # original unchanged


def test_as_revoked_records_revoked_at():
    """as_revoked() must set revoked_at to a non-None timestamp.

    RED: method does not exist.
    GREEN: revoked_at is an ISO-8601 string.
    """
    from src.gold_desk.signal_journal import SignalJournalEntry

    entry = SignalJournalEntry(
        entry_id="e2",
        scored_at="2026-11-10T10:00:00Z",
        decision="YELLOW",
        total=60,
        available_weight=80,
        hard_stop_active=False,
        hard_stop_reason=None,
        components_summary={},
    )
    revoked = entry.as_revoked("test revoke")

    assert revoked.revoked_at is not None
    assert isinstance(revoked.revoked_at, str)
    assert "T" in revoked.revoked_at  # basic ISO 8601 shape


# ─── 5. append_journal ───────────────────────────────────────────────────────

def test_append_journal_uses_injectable_cache():
    """append_journal(entry, cache=mock) must write to the provided cache.

    RED: function does not exist.
    GREEN: writes JSON to REDIS_KEY_JOURNAL using injected cache.
    """
    from src.gold_desk.scorer import compute_score
    from src.gold_desk.signal_journal import (
        SignalJournalEntry,
        append_journal,
        REDIS_KEY_JOURNAL,
    )

    cache = _MemCache()
    result = compute_score(
        bubble_pct=3.0, nav_bubble_pct=0.3, bpr=2.5, net_inflow=6e9,
        xau_rsi=35.0, aed_gap_pct=0.3, nav_7d_pct=2.0,
    )
    entry = SignalJournalEntry.from_score_result(result)

    asyncio.run(append_journal(entry, cache=cache))

    stored = asyncio.run(cache.get(REDIS_KEY_JOURNAL))
    assert stored is not None, "append_journal() must write to REDIS_KEY_JOURNAL"


def test_append_journal_respects_max_entries():
    """After JOURNAL_MAX_ENTRIES+5 appends, list_journal returns <= JOURNAL_MAX_ENTRIES.

    RED: function does not exist.
    GREEN: truncates to JOURNAL_MAX_ENTRIES.
    """
    from src.gold_desk.scorer import compute_score
    from src.gold_desk.signal_journal import (
        SignalJournalEntry,
        append_journal,
        list_journal,
        JOURNAL_MAX_ENTRIES,
    )

    cache = _MemCache()
    result = compute_score(
        bubble_pct=5.0, nav_bubble_pct=1.0, bpr=2.0, net_inflow=3e9,
        xau_rsi=40.0, aed_gap_pct=0.5, nav_7d_pct=1.0,
    )

    for _ in range(JOURNAL_MAX_ENTRIES + 5):
        entry = SignalJournalEntry.from_score_result(result)
        asyncio.run(append_journal(entry, cache=cache))

    entries = asyncio.run(list_journal(cache=cache))
    assert len(entries) <= JOURNAL_MAX_ENTRIES


# ─── 6. list_journal ─────────────────────────────────────────────────────────

def test_list_journal_returns_entries_newest_first():
    """list_journal() must return entries newest-first.

    RED: function does not exist.
    GREEN: entries returned in reverse-chronological order (last append first).
    """
    from src.gold_desk.scorer import compute_score
    from src.gold_desk.signal_journal import (
        SignalJournalEntry,
        append_journal,
        list_journal,
    )

    cache = _MemCache()
    result_green = compute_score(
        bubble_pct=3.0, nav_bubble_pct=0.3, bpr=2.5, net_inflow=6e9,
        xau_rsi=35.0, aed_gap_pct=0.3, nav_7d_pct=2.0,
    )
    result_red = compute_score(
        bubble_pct=30.0, nav_bubble_pct=5.0, bpr=0.5, net_inflow=0,
        xau_rsi=80.0, aed_gap_pct=5.0, nav_7d_pct=-3.0,
    )

    asyncio.run(append_journal(SignalJournalEntry.from_score_result(result_green), cache=cache))
    asyncio.run(append_journal(SignalJournalEntry.from_score_result(result_red), cache=cache))

    entries = asyncio.run(list_journal(cache=cache))
    assert len(entries) >= 2
    assert entries[0].decision == "RED"   # most recent first
    assert entries[1].decision == "GREEN"


def test_list_journal_empty_cache_returns_empty_list():
    """list_journal() on empty cache must return [], not raise.

    RED: function does not exist.
    GREEN: returns empty list when cache has no data.
    """
    from src.gold_desk.signal_journal import list_journal

    cache = _MemCache()
    entries = asyncio.run(list_journal(cache=cache))
    assert entries == []


# ─── 7. revoke_signal ────────────────────────────────────────────────────────

def test_revoke_signal_marks_entry_revoked():
    """revoke_signal(entry_id, reason) must mark the matching entry as revoked.

    RED: function does not exist.
    GREEN: finds entry by entry_id, replaces with as_revoked(), persists.
    """
    from src.gold_desk.scorer import compute_score
    from src.gold_desk.signal_journal import (
        SignalJournalEntry,
        append_journal,
        list_journal,
        revoke_signal,
    )

    cache = _MemCache()
    result = compute_score(
        bubble_pct=3.0, nav_bubble_pct=0.3, bpr=2.5, net_inflow=6e9,
        xau_rsi=35.0, aed_gap_pct=0.3, nav_7d_pct=2.0,
    )
    entry = SignalJournalEntry.from_score_result(result)
    asyncio.run(append_journal(entry, cache=cache))

    found = asyncio.run(revoke_signal(entry.entry_id, "data error", cache=cache))
    assert found is True

    entries = asyncio.run(list_journal(cache=cache))
    revoked_entries = [e for e in entries if e.entry_id == entry.entry_id]
    assert len(revoked_entries) == 1
    assert revoked_entries[0].revoked is True
    assert revoked_entries[0].revoke_reason == "data error"


def test_revoke_signal_nonexistent_entry_returns_false():
    """revoke_signal() with unknown entry_id must return False, not raise.

    RED: function does not exist.
    GREEN: returns False when id not found.
    """
    from src.gold_desk.signal_journal import revoke_signal

    cache = _MemCache()
    found = asyncio.run(revoke_signal("nonexistent-id-xyz", "test", cache=cache))
    assert found is False


def test_revoke_signal_preserves_other_entries():
    """revoke_signal() must only modify the target entry, not others.

    RED: function does not exist.
    GREEN: other entries remain unchanged after one revocation.
    """
    from src.gold_desk.scorer import compute_score
    from src.gold_desk.signal_journal import (
        SignalJournalEntry,
        append_journal,
        list_journal,
        revoke_signal,
    )

    cache = _MemCache()
    result = compute_score(
        bubble_pct=3.0, nav_bubble_pct=0.3, bpr=2.5, net_inflow=6e9,
        xau_rsi=35.0, aed_gap_pct=0.3, nav_7d_pct=2.0,
    )
    e1 = SignalJournalEntry.from_score_result(result)
    e2 = SignalJournalEntry.from_score_result(result)
    asyncio.run(append_journal(e1, cache=cache))
    asyncio.run(append_journal(e2, cache=cache))

    asyncio.run(revoke_signal(e1.entry_id, "only e1", cache=cache))

    entries = asyncio.run(list_journal(cache=cache))
    revoked = [e for e in entries if e.revoked]
    not_revoked = [e for e in entries if not e.revoked]

    assert len(revoked) == 1
    assert revoked[0].entry_id == e1.entry_id
    assert any(e.entry_id == e2.entry_id for e in not_revoked)
