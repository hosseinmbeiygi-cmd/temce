"""QA D1: the five critical concurrency invariants, executed live.

The audit scored D1 as "2 of 5 pass" and reported four scenarios as
inconclusive. This script executes all five against the real PostgreSQL
instance with genuinely concurrent workers (separate connections, separate
transactions), and removes its synthetic rows afterwards.

Usage:
    venv/Scripts/python.exe qa/concurrency_invariants.py

Writes:
    reports/d1_concurrency.json
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS: list[dict] = []
SYM = "__QATEST_RACE__"
MARK = "qa_d1"


def record(name: str, ok: bool, detail: str = "", **extra) -> None:
    RESULTS.append({"invariant": name, "ok": bool(ok), "detail": detail, **extra})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


async def cleanup() -> None:
    from sqlalchemy import text

    import core.database as db

    async with db.async_session_factory() as s:
        await s.execute(
            text("DELETE FROM paper_signal_snapshots WHERE symbol = :s"), {"s": SYM}
        )
        await s.execute(text("DELETE FROM paper_trades WHERE symbol = :s"), {"s": SYM})
        await s.execute(text("DELETE FROM alert_history WHERE alert_id LIKE 'qalr%'"))
        await s.execute(text("DELETE FROM alerts WHERE id LIKE 'qalr%'"))
        await s.commit()


async def invariant_1_alert_cooldown(workers: int = 30) -> None:
    """N parallel evaluations of one armed alert must fire exactly once."""
    import core.database as db
    from core.ids import new_id
    from models.alert import AlertModel
    from services.alert_service import AlertService

    await cleanup()
    condition = json.dumps(
        {"field": "price", "operator": "gte", "threshold": 100.0, "cooldown_minutes": 30}
    )
    async with db.async_session_factory() as s:
        alert = AlertModel(
            id=new_id("qalr"), symbol=SYM, alert_type="price", condition=condition,
            channels=json.dumps([]), enabled=True, triggered_count=0,
        )
        s.add(alert)
        await s.commit()
        alert_id = alert.id

    async def fire(i: int) -> None:
        async with db.async_session_factory() as s:
            await AlertService(s).evaluate_and_trigger("", SYM, "price", 150.0)
            await s.commit()

    await asyncio.gather(*(fire(i) for i in range(workers)))

    from sqlalchemy import text

    async with db.async_session_factory() as s:
        n = (
            await s.execute(
                text("SELECT count(*) FROM alert_history WHERE alert_id = :a"),
                {"a": alert_id},
            )
        ).scalar()
        count = (
            await s.execute(
                text("SELECT triggered_count FROM alerts WHERE id = :a"), {"a": alert_id}
            )
        ).scalar()
    record(
        "INV1 alert cooldown: N parallel evaluations fire the alert exactly once",
        n == 1 and count == 1,
        f"{workers} workers -> {n} history row(s), triggered_count={count}",
        workers=workers, history_rows=n, triggered_count=count,
    )


async def _make_snapshot(snapshot_id: str, price: float) -> None:
    import core.database as db
    from core.time import utc_now_naive
    from models.paper_trading import PaperSignalSnapshotModel

    async with db.async_session_factory() as s:
        s.add(
            PaperSignalSnapshotModel(
                id=snapshot_id, batch_id=f"{MARK}-batch", symbol=SYM,
                name=f"{MARK} signal", market="TSE", timeframe="1d", source=MARK,
                direction="buy", price=price, confidence=0.8, score=80.0,
                stop_loss="0", targets="0,0", reason=MARK,
                generated_at=utc_now_naive(),
            )
        )
        await s.commit()


async def invariant_2_double_open(workers: int = 20) -> None:
    """N concurrent open_trade() on ONE snapshot must create exactly one trade."""
    import core.database as db
    from services.paper_trading_service import PaperTradingService

    snap_id = f"{MARK}_snap2"
    await _make_snapshot(snap_id, 1000.0)

    async def open_it(i: int):
        async with db.async_session_factory() as s:
            return await PaperTradingService(s).open_trade(
                snap_id, quantity=10, capital_allocated=10_000, entry_price=1000.0
            )

    await asyncio.gather(*(open_it(i) for i in range(workers)))

    from sqlalchemy import text

    async with db.async_session_factory() as s:
        n = (
            await s.execute(
                text("SELECT count(*) FROM paper_trades WHERE signal_snapshot_id = :s"),
                {"s": snap_id},
            )
        ).scalar()
    record(
        "INV2 no duplicate open: N concurrent open_trade() on one snapshot -> 1 trade",
        n == 1,
        f"{workers} workers -> {n} trade(s)",
        workers=workers, trades=n,
    )


async def invariant_3_double_close(workers: int = 20) -> None:
    """N concurrent close_trade() must produce one close and one P&L."""
    import core.database as db
    from services.paper_trading_service import PaperTradingService

    snap_id = f"{MARK}_snap2"
    async with db.async_session_factory() as s:
        res = await PaperTradingService(s).open_trade(
            snap_id, quantity=10, capital_allocated=10_000, entry_price=1000.0
        )
    trade_id = res.value["id"]

    async def close_it(i: int) -> bool:
        async with db.async_session_factory() as s:
            r = await PaperTradingService(s).close_trade(
                trade_id, exit_price=1100.0, exit_reason=MARK
            )
            await s.commit()
            return r.success

    outcomes = await asyncio.gather(*(close_it(i) for i in range(workers)))

    from sqlalchemy import text

    async with db.async_session_factory() as s:
        row = (
            await s.execute(
                text("SELECT status, exit_price, pnl FROM paper_trades WHERE id = :t"),
                {"t": trade_id},
            )
        ).first()

    expected_pnl = (1100.0 - 1000.0) * 10
    ok = (
        row is not None
        and row[0] == "closed"
        and abs(float(row[1]) - 1100.0) < 1e-6
        and abs(float(row[2]) - expected_pnl) < 1e-6
        and outcomes.count(True) == 1
    )
    record(
        "INV3 no double-close: N concurrent close_trade() -> one close, one P&L",
        ok,
        f"{workers} workers -> {outcomes.count(True)} ok / status={row[0] if row else None} "
        f"exit={row[1] if row else None} pnl={row[2] if row else None} (expected {expected_pnl})",
        workers=workers, successes=outcomes.count(True),
    )


async def invariant_4_cash_check() -> None:
    """An allocation the simulated account cannot cover must be refused."""
    import core.database as db
    from services.paper_trading_service import PaperTradingService

    snap_id = f"{MARK}_snap4"
    await _make_snapshot(snap_id, 1000.0)
    async with db.async_session_factory() as s:
        over = await PaperTradingService(s).open_trade(
            snap_id, quantity=10_000_000, capital_allocated=99_000_000_000_000.0,
            entry_price=1000.0,
        )
    ok = (not over.success) and "capital" in (over.error or "").lower()
    record(
        "INV4 cash check: allocation beyond simulated capital is refused",
        ok,
        f"success={over.success} error={(over.error or '')[:100]}",
        success=over.success, error=over.error,
    )


async def invariant_5_idempotent_replay() -> None:
    """Replaying the same idempotency key must return the original trade."""
    import core.database as db
    from services.paper_trading_service import PaperTradingService

    snap_id = f"{MARK}_snap5"
    await _make_snapshot(snap_id, 1000.0)
    key = f"{MARK}-key-1"

    ids = []
    for _ in range(3):
        async with db.async_session_factory() as s:
            r = await PaperTradingService(s).open_trade(
                snap_id, quantity=10, capital_allocated=10_000,
                entry_price=1000.0, idempotency_key=key,
            )
            ids.append(r.value["id"] if r.success else None)

    from sqlalchemy import text

    async with db.async_session_factory() as s:
        n = (
            await s.execute(
                text(
                    "SELECT count(*) FROM paper_trades "
                    "WHERE signal_snapshot_id = :s AND idempotency_key = :k"
                ),
                {"s": snap_id, "k": key},
            )
        ).scalar()

    ok = n == 1 and len({i for i in ids if i}) == 1
    record(
        "INV5 idempotent replay: 3 identical requests with the same key -> 1 trade",
        ok,
        f"3 replays -> {n} row(s), returned ids={ids}",
        rows=n, ids=ids,
    )


async def main() -> int:
    from core.database import init_database

    await init_database()

    for fn in (
        invariant_1_alert_cooldown,
        invariant_2_double_open,
        invariant_3_double_close,
        invariant_4_cash_check,
        invariant_5_idempotent_replay,
    ):
        try:
            await fn()
        except Exception as exc:  # a crash is a FAIL, never a skip
            record(fn.__name__, False, f"raised {type(exc).__name__}: {exc}")

    await cleanup()

    passed = sum(1 for r in RESULTS if r["ok"])
    out = {
        "summary": {"passed": passed, "total": len(RESULTS), "all_ok": passed == len(RESULTS)},
        "invariants": RESULTS,
    }
    dest = ROOT / "reports" / "d1_concurrency.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{passed}/{len(RESULTS)} invariants passed -> {dest.relative_to(ROOT)}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))