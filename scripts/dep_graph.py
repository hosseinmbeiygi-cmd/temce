"""Phase 0: services/ dependency graph — stdlib only, no new deps.

Usage:
    python scripts/dep_graph.py                 # top fan-in/out to stdout
    python scripts/dep_graph.py --json out.json # full edge list

 ponytail: ceiling = intra-repo imports; external site-packages intentionally
 excluded. Upgrade path: replace with `grimp` build when per-domain contracts
 land in Phase 2 (grimp already in venv via import-linter).
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = {d.name for d in ROOT.iterdir() if d.is_dir() and (d / "__init__.py").exists()}
TOP_LEVEL |= {"apps", "services", "repositories"}  # namespace-ish roots


def module_of(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def imports_of(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def internal_target(mod: str) -> str | None:
    root = mod.split(".")[0]
    return mod if root in TOP_LEVEL else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", dest="json_out", help="write full edge list here")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    edges = defaultdict(set)  # importer -> imported
    files = defaultdict(list)
    for pkg in ("apps", "services", "repositories", "jobs", "core", "ml", "domain", "ingestion"):
        for f in (ROOT / pkg).rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            src = module_of(f)
            for mod in imports_of(f):
                tgt = internal_target(mod)
                if tgt and tgt != src:
                    edges[src].add(tgt)
                    files[src].append(f.name)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({k: sorted(v) for k, v in edges.items()}, indent=1, sort_keys=True),
            encoding="utf-8",
        )

    fan_in = defaultdict(int)
    for tgts in edges.values():
        for t in tgts:
            fan_in[t] += 1

    print(f"== files scanned: {len(edges)} importers ==")
    print(f"\n== TOP {args.top} FAN-IN (most depended-upon internal modules) ==")
    for m, c in sorted(fan_in.items(), key=lambda x: -x[1])[: args.top]:
        print(f"{c:4}  {m}")
    print(f"\n== TOP {args.top} FAN-OUT (most tangled importers) ==")
    for m, tgts in sorted(edges.items(), key=lambda x: -len(x[1]))[: args.top]:
        print(f"{len(tgts):4}  {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
