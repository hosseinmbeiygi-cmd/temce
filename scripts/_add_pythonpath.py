"""Add auto-PYTHONPATH snippet to all scripts in scripts/ that import project modules.

NOTE: This is a one-time utility. It has already been run — do not run again
or it may insert duplicate snippets.
"""
import os
import re

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_IMPORTS = re.compile(
    r"^(from|import) (core|services|providers|repositories|models|domain|ml|backtesting|jobs|schemas|apps|iran_market_data|brsapi)\.",
    re.MULTILINE,
)
HAS_PATH_SETUP = re.compile(r"sys\.path\.insert.*parent", re.MULTILINE)

SNIPPET = """# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---
"""

updated = []
skipped = []

for fname in sorted(os.listdir(SCRIPTS_DIR)):
    if not fname.endswith(".py") or fname.startswith("_"):
        continue
    fpath = os.path.join(SCRIPTS_DIR, fname)
    with open(fpath, encoding="utf-8") as f:
        content = f.read()

    if not PROJECT_IMPORTS.search(content):
        continue
    if HAS_PATH_SETUP.search(content):
        skipped.append(fname)
        continue

    # Find insertion point: after shebang/docs/future-imports, before project imports
    lines = content.split("\n")
    insert_at = 0
    in_triple = False
    triple_char = None

    for i, line in enumerate(lines):
        s = line.strip()
        if in_triple:
            if triple_char and triple_char in s:
                in_triple = False
                triple_char = None
            insert_at = i + 1
            continue
        if s.startswith("#!") or s.startswith("#"):
            insert_at = i + 1
            continue
        if s.startswith('"""') or s.startswith("'''"):
            triple_char = s[:3]
            if s.count(triple_char) >= 2:
                insert_at = i + 1
            else:
                in_triple = True
            continue
        if s.startswith("from __future__"):
            insert_at = i + 1
            continue
        if s == "":
            insert_at = i + 1
            continue
        break

    lines.insert(insert_at, SNIPPET)
    with open(fpath, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    updated.append(fname)

print(f"Updated ({len(updated)}):")
for u in updated:
    print(f"  + {u}")
print(f"\nSkipped (already has path setup) ({len(skipped)}):")
for s in skipped:
    print(f"  ~ {s}")
