"""Shadow-database probe for the pre-buy write path.

Creates a throwaway database, builds the ORM schema in it, applies migration 0060's DDL
and drives ``PreBuySheetService`` end to end. Nothing is written to the developer's own
database except CREATE/DROP of the shadow, so no test sheet can ever appear in real data.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

SHADOW = "temce_pb_shadow"
UID = "shadow-user"


def urls() -> tuple[str, str]:
    url = os.environ["DATABASE_URL"]
    return re.sub(r"/([^/]+)$", "/postgres", url), re.sub(r"/([^/]+)$", f"/{SHADOW}", url)


def load_ddl() -> list[str]:
    """The pre-buy DDL, in migration order: the tables, then the instrument axis."""

    stmts: list[str] = []
    for name in ("0060_pre_buy_decision_sheet.py", "0062_pre_buy_instrument_axis.py"):
        spec = importlib.util.spec_from_file_location(name[:4], os.path.join("migrations", "versions", name))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        stmts.extend(mod._DDL)
    return stmts


async def main() -> int:
    # The app's UTF-8-safe stdout handler; without it a Persian symbol in a debug log
    # kills a Windows cp1252 console.
    from core.logging import setup_logging

    setup_logging()

    admin_url, shadow = urls()

    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as c:
        if not (await c.execute(text("select 1 from pg_database where datname = :n"), {"n": SHADOW})).first():
            await c.execute(text(f'CREATE DATABASE "{SHADOW}" TEMPLATE template0'))
    await admin.dispose()
    print(f"[shadow] {SHADOW} ready")

    eng = create_async_engine(shadow)
    try:
        await probe(eng)
    finally:
        await eng.dispose()
        await drop()
    return 0


async def drop() -> None:
    admin_url, _ = urls()
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as c:
        await c.execute(
            text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :n"), {"n": SHADOW}
        )
        await c.execute(text(f'DROP DATABASE IF EXISTS "{SHADOW}"'))
    await admin.dispose()
    print("[shadow] dropped")


async def probe(eng) -> None:  # noqa: ANN001 - SQLAlchemy engine
    import models  # noqa: F401  — registers every table on Base.metadata
    from brsapi.models.base import BrsApiBase
    from models.base import Base

    built = skipped = 0
    # The two pre-buy tables are deliberately left to migration 0060: building them from
    # the ORM first would make the DDL a no-op and hide a model/migration mismatch.
    deferred = {"pre_buy_sheets", "pre_buy_reviews"}
    # Two declarative bases: the app's own tables and the brsapi ones. ``classify`` reads
    # ``brsapi_ime_funds``, so the shadow needs both or the probe would fail silently.
    registry = list(Base.metadata.sorted_tables) + list(BrsApiBase.metadata.sorted_tables)
    seen: set[str] = set()
    for table in registry:
        if table.name in deferred or table.name in seen:
            continue
        seen.add(table.name)
        try:
            async with eng.begin() as conn:
                await conn.run_sync(table.create, checkfirst=True)
            built += 1
        except Exception as exc:  # noqa: BLE001 — shadow setup is best effort
            skipped += 1
            print(f"[schema] skipped {table.name}: {type(exc).__name__}: {str(exc)[:100]}")
    print(f"[schema] built={built} skipped={skipped}")

    async with eng.begin() as conn:
        for stmt in load_ddl():
            await conn.execute(text(stmt))
    print("[ddl] 0060 + 0062 applied")

    from models.user import UserModel
    from services.pre_buy_service import PreBuySheetService, parse_answers

    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as s:
        s.add(UserModel(id=UID, username="shadow", email="s@example.com", hashed_password="x", roles="user"))
        await s.commit()

    # A handful of identity rows so ``classify`` runs its real SQL rather than a stub. The
    # shadow database is throwaway; nothing here touches the developer's data.
    from brsapi.models.ime import ImeFundModel
    from models.fund import FundModel
    from models.instrument import InstrumentModel
    from models.market_data import CommodityFuturesModel, StockOptionModel, SymbolModel

    async with Session() as s:
        s.add_all([
            InstrumentModel(id="ins-folad", symbol="فولاد", name="فولاد مبارکه",
                            market_type="stock", asset_class="equity"),
            SymbolModel(symbol="طلا", name="صندوق طلا", market_type="ETF", asset_class="commodity"),
            FundModel(id="f-ahram", symbol="اهرم", name="صندوق اهرم", fund_type="اهرمی"),
            FundModel(id="f-agas", symbol="آگاس", name="صندوق آگاس", fund_type="سهامی"),
            ImeFundModel(id=1, ins_id="ime-tala", symbol="طلا", name="صندوق س.پشتوانه طلای طلا"),
            CommodityFuturesModel(id=1, symbol="KBKH05", name="آتی صندوق طلای کهربا"),
            StockOptionModel(id=1, symbol="ضخود1234", underlying_symbol="خودرو",
                             strike_price=250.0, expiry_date=date(2026, 10, 10),
                             option_type="call", price_last=30.0, trade_volume=1000),
        ])
        await s.commit()

    from services.pre_buy_instrument import classify

    async with Session() as s:
        for symbol in ("فولاد", "اهرم", "آگاس", "طلا", "KBKH05", "ضخود1234", "NAMAD-NIST"):
            decided = await classify(s, symbol)
            print(
                f"[classify] {symbol} → {decided.instrument_type} "
                f"evidenced={decided.evidenced} bank={decided.has_bank} :: {decided.basis}"
            )

    async with Session() as s:
        svc = PreBuySheetService(session=s)
        sheet, created = await svc.get_or_create(UID, "فولاد")
        await s.commit()
        sheet_id = sheet.id
        print(
            f"[create] id={sheet.id} created={created} status={sheet.status} verdict={sheet.verdict} "
            f"instrument={sheet.instrument_type} basis={sheet.instrument_basis}"
        )

    async with Session() as s:
        from core.question_bank.registry import UnknownInstrument
        from services.pre_buy_instrument import InstrumentUndetermined
        from services.pre_buy_service import bank_unavailable

        svc = PreBuySheetService(session=s)
        for symbol, instrument, label in (
            ("NAMAD-NIST", None, "undetermined symbol"),
            ("خودرو", "reit", "class with no table behind it"),
            ("آگاس", "unknown", "classified type with no bank"),
        ):
            try:
                await svc.get_or_create(UID, symbol, instrument_type=instrument)
                print(f"[refuse] {label}: NOT refused — bug")
            except UnknownInstrument as exc:
                print(f"[refuse] {label}: UnknownInstrument :: {bank_unavailable(str(exc.key))[:90]}")
            except InstrumentUndetermined as exc:
                print(f"[refuse] {label}: InstrumentUndetermined :: {str(exc)[:90]}")
            except Exception as exc:  # noqa: BLE001
                print(f"[refuse] {label}: unexpected {type(exc).__name__}: {str(exc)[:90]}")
            await s.rollback()

    async with Session() as s:
        svc = PreBuySheetService(session=s)
        row = await svc.owned(UID, sheet_id)
        try:
            await svc.set_instrument(row, "reit")  # type: ignore[arg-type]
            print("[switch] to an unauthored bank: NOT refused — bug")
        except Exception as exc:  # noqa: BLE001
            print(f"[switch] unauthored refused: {type(exc).__name__}")
        kept, dropped = await svc.set_instrument(row, "equity")
        await s.commit()
        print(f"[switch] same bank kept={kept.instrument_type} dropped={dropped}")

    async with Session() as s:
        svc = PreBuySheetService(session=s)
        row = await svc.owned(UID, sheet_id)
        _, ev, _ = await svc.save(
            row,
            {
                "PB-001": {"value": "yes"},
                "PB-002": {"value": "no"},
                "PB-003": {"value": "no"},
                "PB-013": {"value": "unknown"},
                "PB-999": {"value": "yes"},
            },
            refresh_evidence=False,
        )
        await s.commit()
        stored = list(parse_answers(row.answers))
        print(
            f"[save] verdict={ev.verdict} pct={ev.completion_pct} unlocked={ev.unlocked_stage} "
            f"vetoes={[v.code for v in ev.vetoes]} unknowns={list(ev.unknowns)} stored={len(stored)} "
            f"unknown_code_dropped={'PB-999' not in stored}"
        )

    async with Session() as s:
        svc = PreBuySheetService(session=s)
        print(f"[ownership] other user sees {await svc.owned('another-user', sheet_id)}")

    async with Session() as s:
        svc = PreBuySheetService(session=s)
        again, created2 = await svc.get_or_create(UID, "فولاد")
        print(f"[idempotent] same draft={again.id == sheet_id} created={created2}")

    async with Session() as s:
        svc = PreBuySheetService(session=s)
        row = await svc.owned(UID, sheet_id)
        review = await svc.submit(row, "دلیل آزمایشی")
        await s.commit()
        print(
            f"[submit] review={review.id} status={row.status} hash={row.input_hash[:12]} "
            f"frozen_instrument={review.instrument_type}"
        )

    async with Session() as s:
        svc = PreBuySheetService(session=s)
        row = await svc.owned(UID, sheet_id)
        try:
            await svc.save(row, {"PB-001": {"value": "no"}}, refresh_evidence=False)
            print("[lock] NOT blocked — bug")
        except Exception as exc:  # noqa: BLE001
            print(f"[lock] save on submitted refused: {type(exc).__name__}")

    async with Session() as s:
        svc = PreBuySheetService(session=s)
        rows = await svc.list_for_user(UID)
        revs = await svc.list_reviews(UID, sheet_id)
        print(f"[list] sheets={len(rows)} reviews={len(revs)} first={rows[0].symbol if rows else None}")
        row = await svc.owned(UID, sheet_id)
        await svc.reopen(row)
        await s.commit()
        print(f"[reopen] status={row.status} verdict={row.verdict} detail_stages={len(row.detail['stages'])}")

    await multi_instrument(eng)




async def multi_instrument(eng) -> None:  # noqa: ANN001
    """Each authored class gets its own bank, its own stage rail and its own gate.

    A leveraged fund, an option and a futures contract are created here for the shadow
    user and judged: the point is that none of them is answered with the 115 stock
    questions, and each ★ belongs to its own class.
    """
    from services.pre_buy_service import PreBuySheetService, evaluation_to_json

    Session = async_sessionmaker(eng, expire_on_commit=False)
    for symbol in ("اهرم", "ضخود1234", "طلا"):
        async with Session() as s:
            svc = PreBuySheetService(session=s)
            try:
                sheet, _created = await svc.get_or_create(UID, symbol)
            except Exception as exc:  # noqa: BLE001
                print(f"[multi] {symbol}: refused {type(exc).__name__}: {str(exc)[:70]}")
                continue
            _, evaluation, _ev = await svc.save(
                sheet,
                {"PB-003": {"value": "yes"}, "PB-212": {"value": None}, "PB-001": {"value": "yes"}},
                refresh_evidence=False,
            )
            stage_titles = [st["title"] for st in evaluation_to_json(evaluation)["stages"]]
            print(
                f"[multi] {symbol}: {sheet.instrument_type} total={evaluation.total} "
                f"stages={len(evaluation.stages)} verdict={evaluation.verdict} "
                f"unlocked={evaluation.unlocked_stage} :: {' / '.join(stage_titles)}"
            )
            await s.rollback()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
