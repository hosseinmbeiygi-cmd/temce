"""Alembic revision ids must be unique across every migration tree.

The former collision (brsapi ``0022`` vs main ``0022``) was resolved; brsapi
now uses ``brsapi_0001``.  The test still guards against future regressions.
Note: migrations_backup_20261030/ is intentionally excluded from TREES because
it is an archived snapshot — adding it would generate ~90 false conflicts with
the live tree (DB-07).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TREES = (ROOT / "migrations", ROOT / "brsapi" / "migrations")

_REVISION = re.compile(r'^revision(?::\s*str)?\s*=\s*["\']([^"\']+)', re.M)
_DOWN = re.compile(r'^down_revision(?::\s*str\s*\|\s*None)?\s*=\s*["\']([^"\']+)', re.M)


def _migration_files() -> list[Path]:
    files: list[Path] = []
    for tree in TREES:
        if tree.is_dir():
            files.extend(sorted(tree.rglob("*.py")))
    return files


def test_revision_ids_are_unique_across_all_trees() -> None:
    seen: dict[str, str] = {}
    duplicates: dict[str, list[str]] = {}

    for path in _migration_files():
        match = _REVISION.search(path.read_text(encoding="utf-8"))
        if not match:
            continue
        revision = match.group(1)
        relative = str(path.relative_to(ROOT))
        if revision in seen:
            duplicates.setdefault(revision, [seen[revision]]).append(relative)
        else:
            seen[revision] = relative

    assert not duplicates, f"duplicate alembic revision ids: {duplicates}"


def test_managed_chain_has_a_single_head() -> None:
    revisions: set[str] = set()
    referenced: set[str] = set()

    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        revision = _REVISION.search(text)
        if revision:
            revisions.add(revision.group(1))
        down = _DOWN.search(text)
        if down:
            referenced.add(down.group(1))

    heads = revisions - referenced
    assert len(heads) == 1, f"expected exactly one alembic head, found {sorted(heads)}"


def _managed_graph() -> dict[str, str | None]:
    """Map every managed revision to its parent (``None`` for the root)."""
    graph: dict[str, str | None] = {}
    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        revision = _REVISION.search(text)
        if not revision:
            continue
        down = _DOWN.search(text)
        graph[revision.group(1)] = down.group(1) if down else None
    return graph


def test_every_down_revision_points_at_an_existing_revision() -> None:
    """DB-16: a slug typo in ``down_revision`` must fail by name, not as "two heads"."""
    graph = _managed_graph()
    dangling = {rev: parent for rev, parent in graph.items() if parent is not None and parent not in graph}
    assert not dangling, f"down_revision points at a revision that does not exist: {dangling}"


def test_managed_chain_is_one_unbroken_line() -> None:
    """DB-15: walking down from the head must visit every revision exactly once."""
    graph = _managed_graph()
    roots = sorted(rev for rev, parent in graph.items() if parent is None)
    assert len(roots) == 1, f"expected exactly one root revision, found {roots}"

    heads = set(graph) - {parent for parent in graph.values() if parent is not None}
    assert len(heads) == 1, f"expected exactly one alembic head, found {sorted(heads)}"

    visited: list[str] = []
    cursor: str | None = next(iter(heads))
    while cursor is not None:
        assert cursor not in visited, f"cycle in migration chain at {cursor}"
        visited.append(cursor)
        cursor = graph[cursor]

    unreachable = sorted(set(graph) - set(visited))
    assert not unreachable, f"revisions not reachable from the head: {unreachable}"


def test_alembic_never_scans_the_archived_backup_tree() -> None:
    """DB-07: the backup tree duplicates ~90 live ids; it must stay outside Alembic."""
    ini = (ROOT / "alembic.ini").read_text(encoding="utf-8")
    active = [line for line in ini.splitlines() if not line.lstrip().startswith(("#", ";"))]
    offenders = [line for line in active if "migrations_backup" in line]
    assert not offenders, f"alembic.ini references the archived migration tree: {offenders}"
