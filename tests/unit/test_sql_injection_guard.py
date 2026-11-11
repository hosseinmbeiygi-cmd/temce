"""SQL-injection guard: values are bound, identifiers are allow-listed.

The 2026-10-31 audit walked every interpolated SQL string in the runtime
packages. Values are passed as bind parameters everywhere; the only f-string
interpolations left are identifiers (table/schema/column names), which SQL
cannot bind. This module keeps it that way:

* ``%``-formatting and ``str.format`` on SQL text are forbidden outright.
* The identifier entry points that remain are allow-listed or validated.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from brsapi.quality import history_quality_queries
from services.codal_analysis.point_in_time import MaterializedViewBuilder

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_RUNTIME_ROOTS = (
    "apps",
    "services",
    "repositories",
    "brsapi",
    "core",
    "integrations",
    "src",
    "jobs",
    "domain",
)
_SQL_KEYWORDS = (
    "select",
    "insert into",
    "update ",
    "delete from",
    "from ",
    "where ",
    "truncate",
    "alter table",
    "create table",
    "create materialized",
)


def _looks_like_sql(value: str) -> bool:
    low = " " + value.lower()
    return any(keyword in low for keyword in _SQL_KEYWORDS)


def _formatted_sql_offenders() -> list[str]:
    offenders: list[str] = []
    for root in _RUNTIME_ROOTS:
        base = _REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            rel = path.relative_to(_REPO_ROOT)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.BinOp)
                    and isinstance(node.op, ast.Mod)
                    and isinstance(node.left, ast.Constant)
                    and isinstance(node.left.value, str)
                    and _looks_like_sql(node.left.value)
                ):
                    offenders.append(f"{rel}:{node.lineno} (% formatting)")
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "format"
                    and isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                    and _looks_like_sql(node.func.value.value)
                ):
                    offenders.append(f"{rel}:{node.lineno} (str.format)")
    return offenders


def test_runtime_sql_is_never_built_with_format_operators() -> None:
    offenders = _formatted_sql_offenders()
    assert offenders == [], (
        "SQL must use bind parameters, not % / str.format: " + ", ".join(offenders)
    )


class TestIdentifierAllowLists:
    """The remaining identifier interpolations reject anything unexpected."""

    def test_quality_queries_reject_unknown_table(self) -> None:
        with pytest.raises(ValueError):
            history_quality_queries("instruments; DROP TABLE users")

    def test_quality_queries_are_select_only(self) -> None:
        for table in ("brsapi_gold_coin_history", "brsapi_nav_records"):
            for name, sql in history_quality_queries(table).items():
                normalized = " ".join(sql.upper().split())
                assert normalized.startswith("SELECT"), f"{name}: {sql}"
                for forbidden in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "ALTER", "DROP"):
                    assert forbidden not in normalized, f"{name}: {sql}"

    def test_schema_identifier_is_validated(self) -> None:
        builder = MaterializedViewBuilder()
        with pytest.raises(ValueError):
            builder.build_pivoted_snapshot_sql("public; DROP TABLE users")
        with pytest.raises(ValueError):
            builder.build_pivoted_snapshot_sql("Public")

    def test_schema_identifier_accepts_plain_name(self) -> None:
        sql = MaterializedViewBuilder().build_pivoted_snapshot_sql("public")
        assert "CREATE MATERIALIZED VIEW public.mv_financial_snapshot AS" in sql

    def test_query_builder_rejects_unsafe_table(self) -> None:
        from providers.historical.sql_database.query_builder import QueryBuilder

        for table in (
            "historical_data; DROP TABLE users",
            "historical_data\" WHERE 1=1 --",
            "public.historical_data",
            "",
        ):
            with pytest.raises(ValueError):
                QueryBuilder(table)

    def test_query_builder_rejects_unsafe_columns(self) -> None:
        from providers.historical.sql_database.query_builder import QueryBuilder

        builder = QueryBuilder("historical_data")
        with pytest.raises(ValueError):
            builder.insert({"symbol) VALUES (1); DROP TABLE users; --": 1})
        with pytest.raises(ValueError):
            builder.insert_many([{"symbol": "فولاد", "close AS x": 1.0}])

    def test_query_builder_binds_values_not_sql(self) -> None:
        from providers.historical.sql_database.query_builder import QueryBuilder

        builder = QueryBuilder("historical_data")
        payload = "'; DROP TABLE users; --"
        sql, params = builder.insert({"symbol": payload, "price_close": 1.0})
        assert params == [payload, 1.0]
        assert "DROP" not in sql
        assert sql.startswith('INSERT INTO historical_data (symbol, price_close) VALUES (?')

        select_sql, select_params = builder.select(symbol=payload)
        assert payload not in select_sql
        assert select_params[0] == payload


class TestEndpointQueriesBindValues:
    """Handlers must bind every request value, including LIMIT/OFFSET."""

    async def test_codal_announcement_search_binds_paging_and_filters(self) -> None:
        from apps.api.endpoints import codal as codal_endpoints

        class _Result:
            def scalar(self) -> int:
                return 0

            def fetchall(self) -> list[object]:
                return []

        class _RecordingSession:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []

            async def execute(self, statement: object, params: dict | None = None) -> _Result:
                self.calls.append((str(statement), dict(params or {})))
                return _Result()

        session = _RecordingSession()
        await codal_endpoints.brsapi_search_announcements(
            symbol="فولاد'",
            category=None,
            date_start="2024-01-01",
            date_end="2024-12-31",
            audited=None,
            unaudited=None,
            page=3,
            session=session,  # type: ignore[arg-type]
        )

        assert len(session.calls) == 2
        count_sql, count_params = session.calls[0]
        page_sql, page_params = session.calls[1]

        # The client value travels as a bind parameter, never in the SQL text.
        assert "فولاد" not in page_sql
        assert page_params["symbol"] == "فولاد'"
        assert page_params["date_start"] == "2024-01-01"
        # Paging is bound too: page 3 of 20 is expressed as params, not literals.
        assert ":limit" in page_sql and ":offset" in page_sql
        assert page_params["limit"] == 20
        assert page_params["offset"] == 40
        assert "LIMIT 20" not in page_sql
        # The count query receives only the filter params it references.
        assert count_params == {"symbol": "فولاد'", "date_start": "2024-01-01", "date_end": "2024-12-31"}
