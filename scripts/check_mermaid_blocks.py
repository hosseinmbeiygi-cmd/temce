"""Validate the syntax of every Mermaid diagram in docs/.

Extracts all ```mermaid blocks from docs/*.md, runs a structural sanity
check (balanced code fences), and delegates *real* syntax validation to
scripts/check_mermaid_syntax.cjs, which parses each block with the actual
Mermaid parser (mermaid.parse) running under jsdom — no headless browser,
no network, no external service.

Usage:
    python scripts/check_mermaid_blocks.py            # validate all docs
    python scripts/check_mermaid_blocks.py --quiet    # only report problems

Exit code 0 = every diagram is syntactically valid.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
NODE_CHECK = ROOT / "scripts" / "check_mermaid_syntax.cjs"

BLOCK_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
FENCE_RE = re.compile(r"^```", re.MULTILINE)


def extract_diagrams(docs_dir: Path) -> list[dict]:
    """Return [{file, index, code}] for every mermaid block, docs sorted."""
    items: list[dict] = []
    for path in sorted(docs_dir.glob("*.md")):
        src = path.read_text(encoding="utf-8")
        for i, block in enumerate(BLOCK_RE.findall(src), 1):
            items.append(
                {
                    "file": path.name,
                    "index": i,
                    "code": block.strip(),
                }
            )
    return items


def structural_errors(docs_dir: Path) -> list[str]:
    """Fence-balance check: every markdown file must have an even fence count."""
    errors: list[str] = []
    for path in sorted(docs_dir.glob("*.md")):
        src = path.read_text(encoding="utf-8")
        n = len(FENCE_RE.findall(src))
        if n % 2 != 0:
            errors.append(f"{path.name}: unbalanced code fences ({n} fences)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="only print problems")
    parser.add_argument("--docs", default=str(DOCS), help="docs directory to scan")
    args = parser.parse_args()

    docs_dir = Path(args.docs)

    # 1) structural check (fast, pure Python)
    errors = structural_errors(docs_dir)
    for err in errors:
        print(f"[STRUCT] {err}", file=sys.stderr)
    if errors:
        print(f"FAIL: {len(errors)} structural error(s)", file=sys.stderr)
        return 1

    # 2) real syntax validation via mermaid.parse (Node + jsdom)
    diagrams = extract_diagrams(docs_dir)
    if not diagrams:
        print("WARN: no mermaid blocks found in docs/*.md", file=sys.stderr)
    if not NODE_CHECK.exists():
        print(f"FAIL: {NODE_CHECK} not found", file=sys.stderr)
        return 1

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump({"diagrams": diagrams}, fh, ensure_ascii=False)
        manifest = fh.name

    try:
        proc = subprocess.run(
            ["node", str(NODE_CHECK), manifest],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
    finally:
        Path(manifest).unlink(missing_ok=True)

    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)

    if proc.returncode != 0:
        print(f"FAIL: {len(diagrams)} diagram(s) checked, invalid syntax detected", file=sys.stderr)
        return 1

    if not args.quiet and diagrams:
        print(f"OK: {len(diagrams)} mermaid diagram(s) passed syntax validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
