"""Regression guard: runtime ``CREATE TABLE`` must not fork the canonical schema.

Root cause being locked down (audit run2, stage DB/schema integrity):

Several ``services/*`` modules issue ``CREATE TABLE IF NOT EXISTS`` for tables
whose real definition is owned by the ORM (``models.*``) or Alembic
(``migrations/``).  Because ``create_all``/Alembic create the canonical table
first in every real environment, the runtime DDL silently no-ops — and any
column the runtime query needs that the canonical table does not have blows up
at query time with ``UndefinedColumn``.

Two concrete forks existed in this tree:

1. ``services/signal_performance_tracker.py`` created ``signal_accuracy`` with
   ``(source, period, total_signals, correct_signals, avg_return, weight)``
   whereas the canonical table (migration ``0007`` / ``models.signal_accuracy``)
   has none of ``period``/``weight``/``total_signals``.  Its
   ``_update_accuracy_summary()`` therefore could never run against the real
   table.
2. ``services/ensemble_engine.py::TIMESCALE_SCHEMA`` declared
   ``portfolio_positions(time, symbol, qty, avg_price, market_value,
   unrealized_pnl, weight)`` while the canonical ORM table
   (``models.portfolio.PortfolioPositionModel``) uses
   ``(portfolio_id, quantity, avg_cost, weight_pct, …)`` — the columns
   ``services/risk_metrics.py`` actually queries.

The guard parses the raw DDL, maps any table it recognises back to the ORM
column set, and fails when a fork is found.  It needs no database.

These tests are read-only and environment independent.
"""

from __future__ import annotations

import re
from pathlib import Path

import models  # noqa: F401 — registers every ORM table on Base.metadata
from models.base import Base

_ROOT = Path(__file__).resolve().parents[2]

# Runtime DDL sites that must stay consistent with the canonical schema.
_RUNTIME_DDL_FILES = (
    "services/signal_performance_tracker.py",
    "services/ensemble_engine.py",
    "services/quant_signal_orchestrator.py",
    "services/probability_calibrator.py",
    "services/diagnostics_runner.py",
    "services/watchlist_service.py",
)

_CONSTRAINT_PREFIXES = (
    "PRIMARY KEY",
    "UNIQUE",
    "FOREIGN KEY",
    "CONSTRAINT",
    "CHECK",
    "EXCLUDE",
    "LIKE",
    "SELECT",
)


def _orm_columns() -> dict[str, set[str]]:
    return {name: {c.name for c in tbl.columns} for name, tbl in Base.metadata.tables.items()}


def _extract_create_blocks(text: str) -> dict[str, set[str]]:
    """Return ``{table: {column, …}}`` for every ``CREATE TABLE`` in *text*.

    Handles the multi-line, parenthesised DDL used across ``services/``.
    Constraint clauses are skipped so only real columns are compared.
    """
    out: dict[str, set[str]] = {}
    pattern = re.compile(
        r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*\(",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        table = match.group(1)
        # Walk to the matching close paren so nested FKs/checks do not confuse us.
        depth = 1
        i = match.end()
        while i < len(text) and depth:
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        body = text[match.end(): i - 1]
        cols: set[str] = set()
        for line in body.split("\n"):
            line = line.strip().rstrip(",").strip()
            if not line:
                continue
            head = line.split()[0].strip('"').upper()
            if head in _CONSTRAINT_PREFIXES:
                continue
            # A real column starts with an identifier followed by a type.
            col_match = re.match(r'"?([A-Za-z_][A-Za-z0-9_]*)"?\s+\S', line)
            if col_match:
                cols.add(col_match.group(1))
        if cols:
            out.setdefault(table, set()).update(cols)
    return out


def test_signal_performance_tracker_does_not_fork_signal_accuracy() -> None:
    """The tracker must not redefine the canonical ``signal_accuracy`` table."""
    path = _ROOT / "services/signal_performance_tracker.py"
    blocks = _extract_create_blocks(path.read_text(encoding="utf-8"))

    assert "signal_accuracy" not in blocks, (
        "services/signal_performance_tracker.py issues CREATE TABLE signal_accuracy; "
        "the canonical definition is owned by migration 0007 / models.signal_accuracy. "
        "A runtime redefinition silently no-ops and then breaks on columns the "
        "canonical table lacks (period/weight/total_signals)."
    )


def test_ensemble_timescale_schema_does_not_fork_portfolio_positions() -> None:
    """The dead ``TIMESCALE_SCHEMA`` must not declare a conflicting table."""
    path = _ROOT / "services/ensemble_engine.py"
    blocks = _extract_create_blocks(path.read_text(encoding="utf-8"))

    assert "portfolio_positions" not in blocks, (
        "services/ensemble_engine.py::TIMESCALE_SCHEMA declares a "
        "portfolio_positions shape that conflicts with the canonical ORM table "
        "(models.portfolio.PortfolioPositionModel) used by services/risk_metrics.py."
    )


def test_signal_performance_tracker_never_targets_canonical_signal_accuracy() -> None:
    """The tracker's SQL must not read/write the canonical ``signal_accuracy`` table.

    Its weight rows live in ``signal_weight_accuracy``; any statement still
    naming ``signal_accuracy`` would hit a table without ``period``/``weight``.
    """
    text = (_ROOT / "services/signal_performance_tracker.py").read_text(encoding="utf-8")
    for verb in ("INSERT INTO signal_accuracy", "UPDATE signal_accuracy", "FROM signal_accuracy"):
        assert verb not in text, (
            f"services/signal_performance_tracker.py still issues {verb!r}; "
            "the canonical table has no period/weight columns — use "
            "signal_weight_accuracy instead."
        )


def test_no_runtime_ddl_forks_an_orm_table() -> None:
    """General guard: runtime DDL must not enumerate different columns than the ORM.

    If a table is defined by the ORM, any *other* source that also creates it
    must agree on the column set; otherwise one of the two silently loses.
    """
    orm = _orm_columns()
    forks: list[str] = []
    for rel in _RUNTIME_DDL_FILES:
        path = _ROOT / rel
        if not path.exists():
            continue
        for table, cols in _extract_create_blocks(path.read_text(encoding="utf-8")).items():
            canonical = orm.get(table)
            if canonical is None:
                continue  # not an ORM table → outside this guard's scope
            if not cols <= canonical:
                missing = sorted(cols - canonical)
                forks.append(f"{rel}: {table} declares non-canonical columns {missing}")

    assert not forks, "runtime DDL forks the canonical ORM schema:\n  " + "\n  ".join(forks)
