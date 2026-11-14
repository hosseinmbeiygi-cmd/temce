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
