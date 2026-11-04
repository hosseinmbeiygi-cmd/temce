"""Import-cycle guard for the backend packages (AUD-ARCH-01).

Dependency-free replacement for an import-linter contract: parses every module
under the backend packages and fails the moment an import cycle reappears.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = {
    "apps",
    "core",
    "brsapi",
    "services",
    "domain",
    "ml",
    "jobs",
    "orchestration",
    "ingestion",
    "providers",
    "backtesting",
    "models",
}


def _source_key(relative_parts: tuple[str, ...]) -> str:
    # Files directly in a package collapse to the package; deeper files use two levels.
    return ".".join(relative_parts[:2]) if len(relative_parts) > 2 else relative_parts[0]


def _target_key(module: str) -> str:
    parts = module.split(".")
    return ".".join(parts[:2]) if len(parts) > 1 and parts[0] in PACKAGES else parts[0]


def _build_edges() -> dict[str, set[str]]:
    edges: dict[str, set[str]] = defaultdict(set)
    for package in PACKAGES:
        for path in (ROOT / package).rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, SyntaxError):
                continue
            source = _source_key(path.relative_to(ROOT).parts)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    if module.split(".")[0] not in PACKAGES:
                        continue
                    target = _target_key(module)
                    if target != source:
                        edges[source].add(target)
    return edges


def _find_cycles(edges: dict[str, set[str]]) -> list[tuple[str, ...]]:
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, stack: list[str], seen: set[str]) -> None:
        if node in stack:
            start = stack.index(node)
            cycles.add(tuple(stack[start:] + [node]))
            return
        if node in seen:
            return
        seen.add(node)
        for target in edges.get(node, ()):
            visit(target, stack + [node], seen)

    for node in list(edges):
        visit(node, [], set())

    canonical: dict[tuple[str, ...], tuple[str, ...]] = {}
    for cycle in cycles:
        body = cycle[:-1]
        rotations = [body[i:] + body[:i] for i in range(len(body))]
        canonical[min(rotations)] = cycle
    return sorted(canonical.values())


def test_no_two_level_import_cycles() -> None:
    cycles = _find_cycles(_build_edges())
    assert cycles == [], "import cycles: " + " | ".join(" -> ".join(c) for c in cycles)
