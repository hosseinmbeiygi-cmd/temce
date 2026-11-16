"""Alert-engine lifecycle against the real PostgreSQL schema and stored market data.

Run with:  pytest tests/integration/test_alert_engine_lifecycle.py -m needs_db

Each test works inside a transaction that is rolled back (the one concurrency test commits
under a throw-away user id and deletes its rows). Market data is the real stored data;
ledger entries created here are synthetic test fixtures and never persist. The market is
*assumed closed* so last-session data is acceptable regardless of when the test runs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from core.config import settings as app_settings
from models.alert_engine import AlertAnalysisModel, AlertMonitorModel, AlertNotificationModel
from services.alert_engine import notifier
from services.alert_engine.engine import AlertEngine, EngineError
from services.alert_engine.risk import LedgerError
from services.alert_engine.settings import NotificationPrefs, SettingsError

pytestmark = pytest.mark.needs_db

USER, OTHER = "usr_ae_test_a", "usr_ae_test_b"
LEVERAGED, STOCK, RIGHTS = "موج", "فولاد", "امینح"


@pytest.fixture
async def db():
    engine = create_async_engine(app_settings.database_url_async)
    try:
        async with engine.connect() as probe:
            await probe.execute(text("SELECT 1 FROM alert_monitors LIMIT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"database or alert-engine tables unavailable: {exc}")
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db):
    async with db.connect() as conn:
        trans = await conn.begin()
        s = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield s
        finally:
            await s.close()
            await trans.rollback()


def make(session: AsyncSession, now: datetime | None = None) -> AlertEngine:
    return AlertEngine(session, market_open_fn=lambda: False, now_fn=(lambda: now) if now else None)


async def count(session: AsyncSession, model, **where) -> int:
    stmt = select(func.count()).select_from(model)
    for key, value in where.items():
        stmt = stmt.where(getattr(model, key) == value)
    return int((await session.execute(stmt)).scalar_one())


async def test_add_is_idempotent_and_survives_a_restart(session) -> None:
    first = await make(session).activate(USER, LEVERAGED)
    assert first["created"] and first["monitor"]["category"] == "leveraged_fund"
    report = first["monitor"]["report"]
    assert report["identity"]["isin"].startswith("IRT") and report["identity"]["ins_id"]
    assert report["coverage"]["estimated_nav"]["status"] == "unavailable"  # never fabricated
    assert report["recommendation"]["mode"] == "paper"

    again = await make(session).activate(USER, LEVERAGED)
    assert not again["created"] and again["monitor"]["id"] == first["monitor"]["id"]
    assert await count(session, AlertMonitorModel, user_id=USER) == 1
    assert await count(session, AlertNotificationModel, user_id=USER, event_type="monitoring_started") == 1

    # "restart": a brand-new engine instance finds the monitor in the database and does not redo work
    restarted = make(session)
    assert first["monitor"]["id"] in [mid for mid, _ in await restarted.active_monitor_ids()]
    result = await restarted.analyze(first["monitor"]["id"])
    assert result["unchanged"] is True
    assert await count(session, AlertAnalysisModel, monitor_id=first["monitor"]["id"]) == 1


async def test_remove_stops_monitoring_and_leaves_no_orphan(session) -> None:
    engine = make(session)
    monitor = (await engine.activate(USER, STOCK))["monitor"]
    out = await engine.remove(USER, monitor["id"])
    assert out["removed"] and not out["position_still_recorded"]
    assert monitor["id"] not in [mid for mid, _ in await engine.active_monitor_ids()]
    assert await engine.analyze(monitor["id"]) is None  # a removed monitor is never analysed again
    with pytest.raises(EngineError):
        await engine.remove(USER, monitor["id"])
    assert (await engine.activate(USER, STOCK))["created"]  # can be re-added afterwards


async def test_remove_with_a_recorded_position_requires_acknowledgement(session) -> None:
    engine = make(session)
    monitor = (await engine.activate(USER, STOCK))["monitor"]
    price = monitor["report"]["market"]["price_last"]
    await engine.add_ledger_entry(USER, {"entry_type": "buy", "symbol": STOCK, "quantity": 1000, "price_rial": price})
    warned = await engine.remove(USER, monitor["id"])
    assert warned["removed"] is False and warned["requires_acknowledgement"] and "فروش" in warned["warning"]
    done = await engine.remove(USER, monitor["id"], acknowledge_position=True)
    assert done["removed"] and done["position_still_recorded"]
    positions = (await engine.portfolio(USER))["positions"]
    assert positions and positions[0]["quantity"] == 1000  # removal is not a sale


async def test_shared_instrument_keeps_working_for_the_other_user(session) -> None:
    engine = make(session)
    mine = (await engine.activate(USER, LEVERAGED))["monitor"]
    theirs = (await engine.activate(OTHER, LEVERAGED))["monitor"]
    out = await engine.remove(USER, mine["id"])
    assert out["other_active_monitors_on_instrument"] == 1
    assert (await engine.analyze(theirs["id"], force=True))["state"] != "error"
    assert await engine.list_monitors(USER) == []  # ownership: no cross-user visibility
    with pytest.raises(EngineError):
        await engine.get_monitor(USER, theirs["id"])


async def test_unsupported_and_unknown_instruments_are_explicit(session) -> None:
    engine = make(session)
    rights = (await engine.activate(USER, RIGHTS))["monitor"]
    assert rights["monitoring_state"] == "unsupported" and rights["report"]["recommendation"]["state"] == "unsupported"
    assert rights["report"]["recommendation"]["entry"] is None
    assert rights["id"] not in [mid for mid, _ in await engine.active_monitor_ids()]  # no periodic pseudo-analysis
    with pytest.raises(EngineError):
        await engine.activate(USER, "نمادی‌که‌وجودندارد")


async def test_confirmed_position_switches_the_analysis_to_position_management(session) -> None:
    engine = make(session)
    monitor = (await engine.activate(USER, LEVERAGED))["monitor"]
    assert monitor["report"]["recommendation"]["subject"] == "new_position"
    price = monitor["report"]["market"]["price_last"]
    await engine.add_ledger_entry(USER, {"entry_type": "buy", "symbol": LEVERAGED, "quantity": 500, "price_rial": price})
    await engine.analyze(monitor["id"], force=True)
    rec = (await engine.get_monitor(USER, monitor["id"]))["report"]["recommendation"]
    assert rec["subject"] == "confirmed_position" and rec["exit_assessment"] is not None
    assert rec["state"] in ("hold", "reduce", "exit", "exit_infeasible")
    assert (await engine.active_monitor_ids())[0] == (monitor["id"], True)  # positions are analysed first


async def test_ledger_enforces_shared_cash_and_confirmed_holdings(session) -> None:
    engine = make(session)
    with pytest.raises(LedgerError):  # 600M toman > 500M capital
        await engine.add_ledger_entry(USER, {"entry_type": "buy", "symbol": STOCK, "quantity": 600_000, "price_rial": 10_000})
    await engine.add_ledger_entry(USER, {"entry_type": "buy", "symbol": STOCK, "quantity": 100_000, "price_rial": 10_000, "fees_toman": 371_200})
    await engine.add_ledger_entry(USER, {"entry_type": "sell", "symbol": STOCK, "quantity": 40_000, "price_rial": 10_100})  # partial fill
    with pytest.raises(LedgerError):
        await engine.add_ledger_entry(USER, {"entry_type": "sell", "symbol": STOCK, "quantity": 70_000, "price_rial": 10_100})
    await engine.add_ledger_entry(USER, {"entry_type": "buy", "book": "paper", "symbol": LEVERAGED, "quantity": 10, "price_rial": 100_000})
    actual = await engine.portfolio(USER)
    assert [p["symbol"] for p in actual["positions"]] == [STOCK] and actual["positions"][0]["quantity"] == 60_000
    assert actual["cash_toman"] == pytest.approx(500_000_000 - 100_000_000 - 371_200 + 40_400_000)
    paper = await engine.portfolio(USER, "paper", persist_hwm=False)
    assert [p["symbol"] for p in paper["positions"]] == [LEVERAGED]


async def test_settings_are_versioned_and_loosening_needs_confirmation(session) -> None:
    engine = make(session)
    assert (await engine.get_settings(USER))[1] == 0
    with pytest.raises(SettingsError):
        await engine.update_settings(USER, {"risk": {"per_trade_risk_pct": 1.0}}, approved_by=USER)
    v1 = await engine.update_settings(USER, {"risk": {"per_trade_risk_pct": 1.0}}, approved_by=USER, confirm_loosening=True)
    assert v1["version"] == 1 and "per_trade_risk_pct" in v1["note"]
    v2 = await engine.update_settings(USER, {"risk": {"per_trade_risk_pct": 0.25}}, approved_by=USER)  # tightening: no confirmation
    assert v2["version"] == 2
    v3 = await engine.rollback_settings(USER, 1, approved_by=USER)
    assert v3["version"] == 3 and v3["settings"]["risk"]["per_trade_risk_pct"] == 1.0
    assert [h["version"] for h in await engine.settings_history(USER)] == [3, 2, 1]


class FakeSender:
    def __init__(self, ok: bool) -> None:
        self.ok, self.sent = ok, []

    async def send(self, message: str):
        self.sent.append(message)
        return SimpleNamespace(success=self.ok, error=None if self.ok else "HTTP 500 for https://api.telegram.org/bot123:SECRET-x/sendMessage")


async def test_notifications_dedup_quiet_hours_stale_suppression_and_telegram_states(session, monkeypatch) -> None:
    now = datetime(2026, 11, 14, 8, 0, tzinfo=UTC)  # 11:30 Tehran
    on = NotificationPrefs(telegram_enabled=True)
    base = {"user_id": USER, "title": "t", "body": "b", "now": now, "symbol": LEVERAGED}
    nid = await notifier.notify(session, severity="risk_warning", event_type="x", dedupe_key="k1", prefs=on, **base)
    assert nid and await notifier.notify(session, severity="risk_warning", event_type="x", dedupe_key="k1", prefs=on, **base) is None
    stale = await notifier.notify(session, severity="opportunity", event_type="o", dedupe_key="k2", prefs=on,
                                  valid_until=now - timedelta(minutes=1), **base)
    quiet = NotificationPrefs(telegram_enabled=True, quiet_start="00:00", quiet_end="23:59")
    held = await notifier.notify(session, severity="critical", event_type="q", dedupe_key="k3", prefs=quiet, **base)
    approved = NotificationPrefs(telegram_enabled=True, quiet_start="00:00", quiet_end="23:59", critical_during_quiet=True)
    urgent = await notifier.notify(session, severity="critical", event_type="q", dedupe_key="k4", prefs=approved, **base)
    off = await notifier.notify(session, severity="critical", event_type="q", dedupe_key="k5", prefs=NotificationPrefs(), **base)

    monkeypatch.setattr(app_settings, "telegram_bot_token", "123:SECRET-x", raising=False)

    async def linked(_session, _user):
        return "42"

    monkeypatch.setattr(notifier, "_chat_id_for", linked)
    failing = FakeSender(ok=False)
    stats = await notifier.deliver_pending(session, now=now, user_id=USER, sender_factory=lambda t, c: failing, max_attempts=2)
    assert stats == {"accepted": 0, "failed": 2, "suppressed_stale": 1, "not_configured": 0}
    await notifier.deliver_pending(session, now=now, user_id=USER, sender_factory=lambda t, c: failing, max_attempts=2)
    await notifier.deliver_pending(session, now=now, user_id=USER, sender_factory=lambda t, c: failing, max_attempts=2)
    assert len(failing.sent) == 4  # 2 messages × 2 attempts, then retries stop

    rows = {n["id"]: n for n in await make(session, now).list_notifications(USER)}
    assert rows[nid]["telegram"]["state"] == "failed" and rows[nid]["telegram"]["attempts"] == 2
    assert "SECRET" not in rows[nid]["telegram"]["error"]  # token never stored
    assert rows[stale]["telegram"]["state"] == "suppressed_stale"
    assert rows[held]["telegram"]["state"] == "suppressed_quiet" and rows[urgent]["telegram"]["state"] == "failed"
    assert rows[off]["telegram"]["state"] == "not_requested"
    assert all(n["in_platform_state"] == "stored" and n["acknowledged_at"] is None for n in rows.values())

    ok_id = await notifier.notify(session, severity="risk_warning", event_type="x", dedupe_key="k6", prefs=on, **base)
    good = FakeSender(ok=True)
    assert (await notifier.deliver_pending(session, now=now, user_id=USER, sender_factory=lambda t, c: good, max_attempts=2))["accepted"] == 1
    assert "500,000,000" not in good.sent[0] and "تومان" not in good.sent[0]  # no balances by default
    engine = make(session, now)
    assert await engine.acknowledge(USER, ok_id) == 1
    after = {n["id"]: n for n in await engine.list_notifications(USER)}
    assert after[ok_id]["telegram"]["state"] == "accepted" and after[ok_id]["acknowledged_at"] is not None


async def test_telegram_without_configuration_is_reported_not_faked(session, monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(app_settings, "telegram_bot_token", "", raising=False)
    nid = await notifier.notify(session, user_id=USER, severity="critical", event_type="x", title="t", body="", dedupe_key="nc",
                                prefs=NotificationPrefs(telegram_enabled=True), now=now)
    stats = await notifier.deliver_pending(session, now=now, user_id=USER)
    assert stats["not_configured"] == 1
    row = next(n for n in await make(session).list_notifications(USER) if n["id"] == nid)
    assert row["telegram"]["state"] == "not_configured" and row["telegram"]["error"]


async def test_concurrent_analysis_of_one_monitor_is_skipped_not_duplicated(db) -> None:
    user = "usr_ae_test_concurrency"
    async with AsyncSession(db, expire_on_commit=False) as setup:
        monitor = (await make(setup).activate(user, STOCK))["monitor"]
        await setup.commit()
    try:
        async with db.connect() as holder:
            trans = await holder.begin()
            await holder.execute(text("SELECT id FROM alert_monitors WHERE id = :i FOR UPDATE"), {"i": monitor["id"]})
            async with AsyncSession(db, expire_on_commit=False) as second:
                assert await make(second).analyze(monitor["id"], force=True) is None  # locked elsewhere → skipped
            await trans.rollback()
        async with AsyncSession(db, expire_on_commit=False) as check:
            assert await count(check, AlertAnalysisModel, monitor_id=monitor["id"]) == 1
    finally:
        async with AsyncSession(db, expire_on_commit=False) as cleanup:
            for table in ("alert_notifications", "alert_analyses", "alert_monitors", "alert_equity_state"):
                await cleanup.execute(text(f"DELETE FROM {table} WHERE user_id = :u"), {"u": user})  # noqa: S608
            await cleanup.commit()
