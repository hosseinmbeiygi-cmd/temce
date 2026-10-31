"""DB-02 independent review of the ``0004b_core_baseline`` migration (offline).

The baseline was written by a concurrent agent; these tests do not duplicate it.
They lock the properties the audit requires:

* the chain keeps a single head and the baseline sits between 0004 and 0005;
* every table that a pre-0118 migration references exists before its first
  consumer (the 18-table matrix of report 31);
* the baseline DDL matches its three sources: ``0118`` (core 8), the orphan
  ``brsapi/migrations/001`` tree (25 tables) and ``scripts/install_dates`` (dual);
* no later migration unconditionally re-adds a column the baseline created;
* the baseline is idempotent and its downgrade is a no-op;
* an offline ``alembic upgrade 0005 --sql`` renders without a database.

One known defect is documented as an expected failure: the orphan DDL does not
carry the ORM ``InstrumentRefMixin`` columns (``ins_id``/``instrument_id``), and
no later migration adds them, so a fresh database loses columns the ORM still
maps (runtime ``UndefinedColumn`` risk). See report 34.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "migrations" / "versions"
BASELINE_FILE = VERSIONS / "0004b_core_baseline.py"
ORPHAN_FILE = ROOT / "brsapi" / "migrations" / "001_create_brsapi_tables.py"
BACKFILL_FILE = VERSIONS / "0118_core_tables_backfill.py"
INSTALL_DUAL_FILE = ROOT / "scripts" / "install_dual_dates.py"

CORE8 = (
    "users", "instruments", "trades", "quotes",
    "news_articles", "signals", "alerts", "ml_model_versions",
)
USERS_MFA_COLUMNS = {
    "totp_secret", "totp_enabled", "totp_confirmed_at", "mfa_method", "telegram_chat_id",
}
# Baseline carries the ORM (post-0118) shape for these two brsapi tables while the
# orphan tree is older; values captured from the review.
BRSAPI_BASELINE_EXTRAS = {
    "brsapi_ime_futures": {
        "price_first", "price_first_change", "price_first_change_pct",
        "price_last", "price_last_change", "price_last_change_pct",
        "price_last_settlement", "price_max", "price_max_change",
        "price_max_change_pct", "price_min", "price_min_change",
        "price_min_change_pct", "price_yesterday",
    },
    "brsapi_symbol_snapshots": {
        *(f"{side}_{kind}_{n}" for side in ("bid", "ask")
          for kind in ("price", "volume", "count") for n in range(1, 6)),
    },
}
REPORT31_TABLES = {
    "quotes": "0005_add_performance_indexes",
    "trades": "0005_add_performance_indexes",
    "instruments": "0005_add_performance_indexes",
    "brsapi_codal_announcements": "0016",
    "brsapi_sync_log": "0017",
    "brsapi_symbol_snapshots": "0020_brsapi_snapshots_unique",
    "news_articles": "0021_news_published_at_width",
    "users": "0022_add_user_mfa_columns",
    "dual_date_columns": "0025_add_dual_date_columns",
    "brsapi_ime_funds": "0026_funds_etf_indexes",
    "brsapi_candlesticks": "0032_candlestick_dedup_indexes",
    "brsapi_shareholder_records": "0033_add_shareholder_id",
    "brsapi_historical_daily": "0037_index_gregorian_dates",
    "brsapi_intraday_trades": "0037_index_gregorian_dates",
    "brsapi_raw_payloads": "0042",
    "ml_model_versions": "0050",
    "signals": "0099",
    "alerts": "0117",
}


# ── parsers ──────────────────────────────────────────────────────────────


def _revisions() -> dict[str, dict]:
    revs: dict[str, dict] = {}
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^revision\s*(?::[^=\n]+)?=\s*["\']([^"\']+)["\']', text, re.M)
        d = re.search(r'^down_revision\s*(?::[^=\n]+)?=\s*(.+)$', text, re.M)
        if m:
            revs[m.group(1)] = {
                "path": path,
                "text": text,
                "downs": re.findall(r'["\']([^"\']+)["\']', d.group(1)) if d else [],
            }
    return revs


def _order(revs: dict[str, dict]) -> list[str]:
    children: dict[str, list[str]] = {}
    for rev, meta in revs.items():
        for down in meta["downs"]:
            children.setdefault(down, []).append(rev)
    order, seen, queue = [], set(), ["0001"]
    while queue:
        rev = queue.pop(0)
        if rev in seen or rev not in revs:
            continue
        seen.add(rev)
        order.append(rev)
        queue.extend(sorted(children.get(rev, [])))
    return order


def _tables_from_module(path: Path, var: str = "_TABLES") -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == var:
            for elt in node.value.elts:
                if isinstance(elt, ast.Tuple) and isinstance(elt.elts[0], ast.Constant):
                    out[elt.elts[0].value.lower()] = elt.elts[-1].value
    return out


def _ddl_columns(ddl: str) -> set[str]:
    cols: set[str] = set()
    for line in ddl.splitlines()[1:]:
        s = line.strip().rstrip(",")
        if not s or s.startswith(")"):
            continue
        if re.match(r"^(PRIMARY|UNIQUE|CONSTRAINT|FOREIGN|CHECK)\b", s, re.I):
            continue
        m = re.match(r'^"?([A-Za-z_][\w]*)"?\s+[A-Za-z]', s)
        if m:
            cols.add(m.group(1).lower())
    return cols


def _orphan_columns() -> dict[str, set[str]]:
    tree = ast.parse(ORPHAN_FILE.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", None) == "create_table"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            name = str(node.args[0].value).lower()
            cols: set[str] = set()
            for arg in node.args[1:]:
                if isinstance(arg, ast.Call):
                    fn = getattr(arg.func, "attr", None) or getattr(arg.func, "id", None)
                    if fn == "Column" and arg.args and isinstance(arg.args[0], ast.Constant):
                        cols.add(str(arg.args[0].value).lower())
            out[name] = cols
    return out


def _baseline_columns() -> dict[str, set[str]]:
    return {name: _ddl_columns(ddl) for name, ddl in _tables_from_module(BASELINE_FILE).items()}


def _columns_added_after(baseline_rev: str) -> list[tuple[str, str, str, bool]]:
    """(revision, table, column, idempotent) for every add-column after the baseline."""
    revs = _revisions()
    order = _order(revs)
    start = order.index(baseline_rev) + 1
    adds: list[tuple[str, str, str, bool]] = []
    for rev in order[start:]:
        text = revs[rev]["text"]

        def push(table: str, col: str, idem: bool, _rev: str = rev) -> None:
            adds.append((_rev, table.lower(), col.lower(), idem))

        for m in re.finditer(
            r'op\.add_column\(\s*["\'](\w+)["\']\s*,\s*(?:sa\.)?Column\(\s*["\'](\w+)["\']',
            text,
        ):
            push(m.group(1), m.group(2), False)
        for block in re.finditer(
            r'batch_alter_table\(\s*["\'](\w+)["\']\s*\)(.*?)(?=batch_alter_table\(|def downgrade|\Z)',
            text,
            re.S,
        ):
            for m in re.finditer(
                r'add_column\(\s*(?:sa\.)?Column\(\s*["\'](\w+)["\']', block.group(2)
            ):
                push(block.group(1), m.group(1), False)
        for m in re.finditer(
            r'ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?["\']?(\w+)["\']?\s+ADD\s+COLUMN\s+'
            r'(IF\s+NOT\s+EXISTS\s+)?["\']?(\w+)',
            text,
            re.I,
        ):
            push(m.group(1), m.group(3), bool(m.group(2)))
        if "ADD COLUMN IF NOT EXISTS updated_at" in text and "{table_name}" in text:
            lst = re.search(r"TABLES_NEEDING_UPDATED_AT\s*=\s*\[(.*?)\]", text, re.S)
            for name in re.findall(r'["\'](\w+)["\']', lst.group(1) if lst else ""):
                push(name, "updated_at", True)
        if "ALTER TABLE IF EXISTS signals ADD COLUMN IF NOT EXISTS {col}" in text:
            cols = re.search(r"columns\s*=\s*\[(.*?)\]", text, re.S)
            for name in re.findall(r'\(\s*["\'](\w+)["\']\s*,', cols.group(1) if cols else ""):
                push("signals", name, True)
        if rev.startswith("0025") and "gregorian_date" in text and "shamsi_date" in text:
            for table in _tables_from_module(BASELINE_FILE):
                push(table, "gregorian_date", True)
                push(table, "shamsi_date", True)
    return adds


# ── chain shape ─────────────────────────────────────────────────────────


def test_chain_has_a_single_head() -> None:
    revs = _revisions()
    referenced = {d for meta in revs.values() for d in meta["downs"]}
    heads = [r for r in revs if r not in referenced]
    assert heads == ["0119_service_private_tables"]


def test_baseline_sits_between_0004_and_0005() -> None:
    baseline = ast.parse(BASELINE_FILE.read_text(encoding="utf-8"))
    ns: dict[str, object] = {}
    exec(compile(baseline, str(BASELINE_FILE), "exec"), ns)
    assert ns["revision"] == "0004b_core_baseline"
    assert ns["down_revision"] == "0004_ml_symbol_results"

    five = (VERSIONS / "0005_add_performance_indexes.py").read_text(encoding="utf-8")
    assert re.search(r'down_revision\s*=\s*["\']0004b_core_baseline["\']', five)


def test_baseline_has_the_expected_surface() -> None:
    tables = _tables_from_module(BASELINE_FILE)
    assert len(tables) == 34
    assert set(CORE8) <= set(tables)
    assert "dual_date_columns" in tables
    assert "funds" not in tables, "0015 creates funds; the baseline must not duplicate it"
    brsapi = {name for name in tables if name.startswith("brsapi_")}
    assert len(brsapi) == 25


# ── structural: report-31 tables exist before their first consumer ─────


def test_every_referenced_table_is_created_before_its_first_consumer() -> None:
    revs = _revisions()
    order = _order(revs)
    baseline_pos = order.index("0004b_core_baseline")
    tables = _tables_from_module(BASELINE_FILE)
    ddl_all = "\n".join(tables.values())

    for table, consumer in REPORT31_TABLES.items():
        assert table in tables, f"{table} missing from baseline"
        assert f"CREATE TABLE IF NOT EXISTS {table} " in ddl_all or f'"{table}"' in ddl_all
        assert baseline_pos < order.index(consumer), (
            f"baseline must precede the first consumer of {table} ({consumer})"
        )


# ── drift vs sources ────────────────────────────────────────────────────


def test_core_tables_match_0118_except_the_documented_mfa_omission() -> None:
    baseline = _baseline_columns()
    backfill = {k: _ddl_columns(v) for k, v in _tables_from_module(BACKFILL_FILE).items()}
    for table in CORE8:
        expected_extra = USERS_MFA_COLUMNS if table == "users" else set()
        assert baseline[table] == backfill[table] - expected_extra, (
            f"{table}: baseline and 0118 drifted beyond the documented omission"
        )


def test_brsapi_tables_match_the_orphan_tree() -> None:
    baseline = _baseline_columns()
    orphan = _orphan_columns()
    assert {t for t in baseline if t.startswith("brsapi_")} == set(orphan)
    for table, orphan_cols in orphan.items():
        expected_extra = BRSAPI_BASELINE_EXTRAS.get(table, set())
        assert baseline[table] - expected_extra == orphan_cols, (
            f"{table}: baseline drifted from the orphan DDL"
        )
        assert baseline[table] >= orphan_cols


def test_dual_date_columns_matches_the_install_script() -> None:
    script = INSTALL_DUAL_FILE.read_text(encoding="utf-8")
    m = re.search(r"CREATE TABLE IF NOT EXISTS dual_date_columns\s*\((.*?)\)", script, re.S)
    assert m, "install script no longer defines dual_date_columns"
    script_cols = {
        mm.group(1).lower()
        for line in m.group(1).splitlines()
        if (mm := re.match(r"\s*([A-Za-z_]\w*)\s+", line))
    }
    assert _baseline_columns()["dual_date_columns"] == script_cols


def test_no_later_migration_unconditionally_readds_a_baseline_column() -> None:
    baseline = _baseline_columns()
    collisions = [
        (rev, table, col)
        for rev, table, col, idem in _columns_added_after("0004b_core_baseline")
        if table in baseline and col in baseline[table] and not idem
    ]
    assert collisions == [], f"non-idempotent column re-adds: {collisions}"


def test_no_later_create_table_redeclares_a_baseline_table() -> None:
    baseline = set(_tables_from_module(BASELINE_FILE))
    offenders: list[str] = []
    for path in sorted(VERSIONS.glob("*.py")):
        if path.name.startswith("0004b"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'op\.create_table\(\s*["\'](\w+)["\']', text):
            if m.group(1).lower() in baseline:
                offenders.append(f"{path.name}:{text.count(chr(10), 0, m.start()) + 1}")
    assert offenders == []


# ── baseline hygiene ────────────────────────────────────────────────────


def test_baseline_ddl_is_idempotent() -> None:
    tables = _tables_from_module(BASELINE_FILE)
    text = BASELINE_FILE.read_text(encoding="utf-8")
    for name, ddl in tables.items():
        assert f"CREATE TABLE IF NOT EXISTS {name} " in ddl, f"{name} lacks IF NOT EXISTS"
    # every index DDL in the module must be idempotent too
    for stmt in re.findall(r"CREATE (?:UNIQUE )?INDEX[^'\"]*", text):
        assert "IF NOT EXISTS" in stmt, stmt[:80]


def test_baseline_downgrade_is_a_noop() -> None:
    tree = ast.parse(BASELINE_FILE.read_text(encoding="utf-8"))
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
    )
    body = [node for node in fn.body if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant)]
    assert body == [] or all(isinstance(node, ast.Pass) for node in body)


def test_offline_upgrade_to_0005_renders_without_a_database() -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = "postgresql+asyncpg://audit:audit@localhost:15432/tse_audit_offline"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0005", "--sql"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "CREATE TABLE IF NOT EXISTS users" in proc.stdout


# ── known defect: ORM mixin columns are absent on a fresh database ─────


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DB-02 residual: the orphan brsapi DDL (used by the baseline) has no "
        "InstrumentRefMixin columns (ins_id/instrument_id) and no later migration "
        "adds them, while the ORM still maps them — a fresh DB would fail with "
        "UndefinedColumn. Needs a follow-up migration (report 34)."
    ),
)
def test_orm_instrument_reference_columns_are_reachable_after_upgrade() -> None:
    import brsapi.models  # noqa: F401 — register metadata
    from brsapi.models.base import BrsApiBase

    baseline = _baseline_columns()
    added = {(table, col) for _rev, table, col, _idem in _columns_added_after("0004b_core_baseline")}
    missing = []
    for table, cols in baseline.items():
        if not table.startswith("brsapi_"):
            continue
        orm = {c.name.lower() for c in BrsApiBase.metadata.tables[table].columns}
        for col in ("ins_id", "instrument_id"):
            if col in orm and col not in cols and (table, col) not in added:
                missing.append(f"{table}.{col}")
    assert missing == [], f"columns mapped by the ORM but absent on a fresh DB: {missing}"
