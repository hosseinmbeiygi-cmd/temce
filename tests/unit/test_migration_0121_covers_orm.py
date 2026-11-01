"""SIL-01 — migration 0121 must cover every ORM table/column it claims to fix.

بدون DB هم می‌توان تضمین کرد که لیست جدول‌های migration با مدل‌های ORM هم‌خوان
بماند؛ وگرنه با افزودن مدل تازه، همان خطای UndefinedColumn برمی‌گردد.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import brsapi.models  # noqa: F401 — همهٔ مدل‌ها را در metadata ثبت می‌کند
from brsapi.models.base import BrsApiBase

_MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0121_brsapi_instrument_ref.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0121", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_every_instrument_ref_table_is_listed() -> None:
    migration = _load_migration()
    orm_tables = {
        name
        for name, table in BrsApiBase.metadata.tables.items()
        if "ins_id" in table.c and "instrument_id" in table.c
    }

    assert orm_tables == set(migration.INSTRUMENT_REF_TABLES)


def test_orderbook_columns_match_the_ime_futures_model() -> None:
    migration = _load_migration()
    model = BrsApiBase.metadata.tables["brsapi_ime_futures"]
    expected = {name for name, _type in migration.ORDERBOOK_COLUMNS}

    assert expected <= set(model.c.keys())
    # هر ستون سفارش‌بوک مدل باید در migration هم باشد. ``Column.startswith``
    # یک عبارت SQL می‌سازد (نه bool)، پس روی ``c.name`` کار می‌کنیم.
    assert {c.name for c in model.c if c.name.startswith(("bid_", "ask_"))} == expected


def test_pro_tables_are_created_for_every_pro_model() -> None:
    migration = _load_migration()
    orm_pro_tables = {n for n in BrsApiBase.metadata.tables if n.startswith("brsapi_gold_currency_pro_")}

    assert orm_pro_tables == set(migration.PRO_TABLES)
