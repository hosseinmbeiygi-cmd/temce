"""DB-free guards for migration 0119 (service-private tables, audit run2 D4).

``signal_performance``, ``signal_weight_accuracy``, ``calibration_models``,
``isotonic_calibration`` and ``diagnostic_runs``/``diagnostic_findings`` used to
exist only because a service ran ``CREATE TABLE IF NOT EXISTS`` at runtime. A
clean production database (migrations only) lacked them. Migration ``0119``
provides the canonical definition.

These tests need no database: they check the migration structure and, crucially,
that the frozen DDL has not drifted from the DDL the services still ship (a
divergence would mean the migration and the runtime path disagree).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION = _ROOT / "migrations" / "versions" / "0119_service_private_tables.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("_mig_0119", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_create_blocks(text: str) -> dict[str, set[str]]:
    """``{table: {column, ...}}`` for every ``CREATE TABLE`` in *text*."""
    out: dict[str, set[str]] = {}
    pattern = re.compile(
        r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*\(",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        table = match.group(1)
        depth = 1
        i = match.end()
        while i < len(text) and depth:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        body = text[match.end(): i - 1]
        cols: set[str] = set()
        for line in body.split("\n"):
            line = line.strip().rstrip(",").strip()
            if not line:
                continue
            if re.match(
                r"^\"?(PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY|CONSTRAINT|CHECK|EXCLUDE|REFERENCES)\b",
                line,
                re.IGNORECASE,
            ):
                continue
            col = re.match(r'"?([A-Za-z_][A-Za-z0-9_]*)"?\s+\S', line)
            if col:
                cols.add(col.group(1))
        out.setdefault(table, set()).update(cols)
    return out


def test_0119_defines_the_expected_tables() -> None:
    module = _load_migration()
    names = {name for name, _ddl in module._TABLES}
    assert {
        "signal_performance",
        "signal_weight_accuracy",
        "calibration_models",
        "isotonic_calibration",
        "diagnostic_runs",
        "diagnostic_findings",
    } <= names
    assert module.revision == "0119_service_private_tables"
    assert module.down_revision == "0118_core_tables_backfill"


def test_0119_ddl_matches_service_source_ddl() -> None:
    """The migration DDL must match the DDL the services still ship."""
    module = _load_migration()
    frozen = {name: _extract_create_blocks(ddl)[name] for name, ddl in module._TABLES}

    sources = {
        "signal_performance": "services/signal_performance_tracker.py",
        "signal_weight_accuracy": "services/signal_performance_tracker.py",
        "calibration_models": "services/probability_calibrator.py",
        "isotonic_calibration": "services/isotonic_calibrator.py",
        "diagnostic_runs": "services/diagnostics_runner.py",
        "diagnostic_findings": "services/diagnostics_runner.py",
    }

    drift: list[str] = []
    for table, rel in sources.items():
        text = (_ROOT / rel).read_text(encoding="utf-8")
        blocks = _extract_create_blocks(text)
        if table not in blocks:
            drift.append(f"{table}: no longer defined in {rel} (migration may be stale)")
            continue
        if blocks[table] != frozen[table]:
            drift.append(
                f"{table}: migration={sorted(frozen[table])} service={sorted(blocks[table])}"
            )

    assert not drift, "0119 DDL drifted from the service source DDL:\n  " + "\n  ".join(drift)


def test_0119_creates_pending_signal_index() -> None:
    """The partial unique index the orchestrator relied on must be in a migration."""
    module = _load_migration()
    index_names = {name for name, _ddl in module._INDEXES}
    assert "uq_signal_accuracy_pending_key" in index_names
