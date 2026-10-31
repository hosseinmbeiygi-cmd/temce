"""Contract tests for ``scripts/history_quality_preflight.py``.

The script exists to unblock the DB-dependent checks without ever writing. These
tests pin that property: only SELECTs are executable, the remediation DDL is
kept out of the executable list, and importing the module needs no database.
"""

from __future__ import annotations

import importlib
import re

from brsapi.quality import NAV_HISTORY_TABLES, OHLC_HISTORY_TABLES
from scripts import history_quality_preflight as preflight

# Word-boundary match: the column list legitimately contains `updated_at` and
# `created_at`, which must not be mistaken for UPDATE/CREATE statements.
_MUTATING = re.compile(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|ALTER|DROP|CREATE|GRANT)\b")


def test_module_imports_without_a_database() -> None:
    module = importlib.reload(preflight)
    assert module.TABLES


def test_every_executable_statement_is_a_select() -> None:
    statements = preflight.all_statements()

    assert statements, "the pre-flight must execute something"
    for label, sql in statements:
        normalized = " ".join(sql.upper().split())
        assert normalized.startswith("SELECT"), f"{label} is not a SELECT"
        match = _MUTATING.search(normalized)
        assert match is None, f"{label} contains {match.group(0)}: {sql}"


def test_labels_are_unique() -> None:
    labels = [label for label, _ in preflight.all_statements()]
    assert len(labels) == len(set(labels))


def test_covers_all_three_history_tables() -> None:
    sql_text = " ".join(sql for _, sql in preflight.all_statements())

    for table in OHLC_HISTORY_TABLES + NAV_HISTORY_TABLES:
        assert table in sql_text

    labels = {label for label, _ in preflight.all_statements()}
    assert {"schema.time_columns", "schema.dual_date_source", "schema.indexes"} <= labels


def test_each_table_reports_the_audited_defects() -> None:
    labels = {label for label, _ in preflight.all_statements()}

    assert "brsapi_gold_coin_history.high_below_low" in labels
    assert "brsapi_gold_coin_history.duplicate_symbol_date" in labels
    assert "brsapi_gold_currency_pro_daily_history.close_outside_range" in labels
    assert "brsapi_nav_records.issue_redemption_mismatch" in labels


def test_remediation_ddl_is_review_only_not_executable() -> None:
    executable = " ".join(sql for _, sql in preflight.all_statements()).upper()
    review = "\n".join(preflight.REVIEW_ONLY_DDL).upper()

    assert "CREATE UNIQUE INDEX" in review
    assert "DUAL_DATE_COLUMNS" in review
    assert "SET SOURCE_COLUMN" in review

    # The executable statements never contain the remediation statements.
    assert "CREATE UNIQUE INDEX" not in executable
    assert "SET SOURCE_COLUMN" not in executable
    assert _MUTATING.search(" ".join(executable.split())) is None
