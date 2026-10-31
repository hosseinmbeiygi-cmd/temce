"""DB-free guards for Alembic coverage of the core ORM tables (audit run2, D3).

Two properties are locked down:

1. **Coverage** — every table in ``Base.metadata`` must be created by some
   Alembic migration. Historically ~26% of ORM tables (portfolios, users,
   instruments, quotes, signals, alerts, ml_*, ...) existed only because
   ``core.database`` ran ``Base.metadata.create_all`` during early development;
   a clean production database (which never runs ``create_all``) lacked them.
   Migration ``0118_core_tables_backfill`` closes that gap.

2. **No drift** — the DDL frozen into ``0118`` must still match the ORM column
   set exactly. If a model changes without a new migration, this test fails and
   forces a real migration instead of a silent fork.

No database is required: the checks read source text and ORM metadata.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import models  # noqa: F401 — registers every ORM table on Base.metadata
from models.base import Base

_ROOT = Path(__file__).resolve().parents[2]
_VERSIONS = _ROOT / "migrations" / "versions"

# A table-level clause starts with one of these keywords as a whole word — matched
# with ``\b`` so an ordinary column such as ``checked_at`` is not mistaken for
# ``CHECK``.
_CONSTRAINT_RE = re.compile(
    r"^\"?(PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY|CONSTRAINT|CHECK|EXCLUDE|LIKE|SELECT)\b",
    re.IGNORECASE,
)


def _tables_created_by_migrations() -> set[str]:
    """Names of tables any migration creates (op.create_table or raw DDL)."""
    found: set[str] = set()
    for path in sorted(_VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r'op\.create_table\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']', text, re.S):
            found.add(match.group(1))
        for match in re.finditer(
            r'CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+"?([A-Za-z_][A-Za-z0-9_]*)"?\s*\(',
            text,
            re.IGNORECASE,
        ):
            found.add(match.group(1))
    return found


def _columns_in_ddl(ddl: str) -> set[str]:
    """Column names from a single ``CREATE TABLE … ( … )`` statement."""
    open_paren = ddl.index("(")
    depth = 1
    i = open_paren + 1
    while i < len(ddl) and depth:
        if ddl[i] == "(":
            depth += 1
        elif ddl[i] == ")":
            depth -= 1
        i += 1
    body = ddl[open_paren + 1: i - 1]
    cols: set[str] = set()
    for line in body.split("\n"):
        line = line.strip().rstrip(",").strip()
        if not line:
            continue
        if _CONSTRAINT_RE.match(line):
            continue
        col = re.match(r'"?([A-Za-z_][A-Za-z0-9_]*)"?\s+\S', line)
        if col:
            cols.add(col.group(1))
    return cols


def _load_frozen_tables() -> list[tuple[str, str]]:
    path = _VERSIONS / "0118_core_tables_backfill.py"
    spec = importlib.util.spec_from_file_location("_mig_0118", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._TABLES


def test_every_orm_table_is_created_by_a_migration() -> None:
    """D3 guard: no ORM table may rely on ``create_all`` to exist."""
    covered = _tables_created_by_migrations()
    orm = set(Base.metadata.tables)
    missing = sorted(orm - covered)
    assert not missing, (
        f"{len(missing)} ORM table(s) are created by no Alembic migration: {missing}. "
        "A clean production database (no create_all) would not have them."
    )


def test_backfill_ddl_matches_orm_metadata() -> None:
    """Drift guard: the frozen 0118 DDL must match the ORM column set exactly."""
    frozen = _load_frozen_tables()
    assert frozen, "0118 migration exposes no _TABLES to verify"

    drift: list[str] = []
    for table, ddl in frozen:
        orm_table = Base.metadata.tables.get(table)
        assert orm_table is not None, f"0118 creates {table} but it is no longer an ORM table"
        orm_cols = {c.name for c in orm_table.columns}
        ddl_cols = _columns_in_ddl(ddl)
        if orm_cols != ddl_cols:
            drift.append(
                f"{table}: only-orm={sorted(orm_cols - ddl_cols)} only-ddl={sorted(ddl_cols - orm_cols)}"
            )

    assert not drift, (
        "0118 frozen DDL drifted from the ORM metadata — add a NEW migration "
        "(do not edit a shipped one in place):\n  " + "\n  ".join(drift)
    )


def test_backfill_migration_is_single_head_chain() -> None:
    """0118 must extend 0117 and expose the expected revision identifiers."""
    spec = importlib.util.spec_from_file_location(
        "_mig_0118b", _VERSIONS / "0118_core_tables_backfill.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "0118_core_tables_backfill"
    assert module.down_revision == "0117"
