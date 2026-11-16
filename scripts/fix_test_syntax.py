"""
Fix syntax errors in corrupted test files.

Usage:
    python fix_test_syntax.py <file1.py> [file2.py ...]

Fixes:
1. Unterminated triple-quoted strings (adds closing)
2. Orphaned closing parentheses at module level
"""
from __future__ import annotations

import re
import sys
import tokenize


def find_unterminated_string(filepath: str) -> tuple[int, str] | None:
    """Find unterminated multi-line string using Python tokenizer."""
    try:
        with tokenize.open(filepath) as f:
            list(tokenize.generate_tokens(f.readline))
        return None  # No error
    except tokenize.TokenError as e:
        # Parse the error: 'EOF in multi-line string' at (line, col)
        msg = str(e)
        if "EOF in multi-line string" in msg:
            # Find the error position
            match = re.search(r'\((\d+), (\d+)\)', msg)
            if match:
                line = int(match.group(1))
                int(match.group(2))
                return (line, "unterminated_triple_quote")
        return None
    except SyntaxError as e:
        return (e.lineno or 0, str(e))


def fix_triple_quotes(content: str) -> tuple[str, list[str]]:
    """Fix unterminated triple-quoted strings by tracking open/close state."""
    lines = content.split('\n')
    fixes: list[str] = []

    inside_triple = False
    triple_start_line = 0

    for i, line in enumerate(lines):
        # Count triple quotes in this line
        # Use a simple state machine
        j = 0
        while j < len(line):
            if line[j:j+3] == '"""':
                if inside_triple:
                    inside_triple = False
                    j += 3
                else:
                    inside_triple = True
                    triple_start_line = i + 1
                    j += 3
            else:
                j += 1

    if inside_triple:
        # Add closing triple quote at end of file
        lines.append('"""')
        fixes.append(f"Closed unterminated triple-quoted string started at line {triple_start_line}")

    return '\n'.join(lines), fixes


def fix_indentation(content: str) -> tuple[str, list[str]]:
    """Fix common indentation issues.

    Detects lines at 4-space indent where 8-space is expected (inside methods).
    """
    lines = content.split('\n')
    fixes: list[str] = []

    # Track indentation context
    in_class = False
    in_method = False
    method_indent = 0

    for i, line in enumerate(lines):
        if not line.strip() or line.strip().startswith('#'):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Detect class definition
        if stripped.startswith('class ') and stripped.endswith(':'):
            in_class = True
            in_method = False
            continue

        # Detect method definition
        if in_class and stripped.startswith('def ') and stripped.endswith(':'):
            in_method = True
            method_indent = indent
            continue

        # Inside a method, indent should be method_indent + 4
        if in_method and indent > 0 and indent < method_indent + 4:
            # Line is at wrong indentation - pad it
            if not stripped.startswith(')'):  # Don't fix closing parens
                new_indent = method_indent + 4
                lines[i] = ' ' * new_indent + stripped
                fixes.append(f"Fixed indentation at line {i+1}: {indent} -> {new_indent}")

    return '\n'.join(lines), fixes


def fix_orphaned_parens(content: str) -> tuple[str, list[str]]:
    """Remove orphaned closing parentheses at module level (indented with 8 spaces)."""
    lines = content.split('\n')
    fixes: list[str] = []

    # Find the first class/function definition
    first_def = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('class ') or stripped.startswith('def '):
            first_def = i
            break

    if first_def < 0:
        return content, fixes

    # Before the first class/function, find orphaned ')' lines
    cleaned = []
    in_import = False
    for i, line in enumerate(lines[:first_def]):
        stripped = line.strip()

        # Track import blocks
        if stripped.startswith('from ') or stripped.startswith('import '):
            cleaned.append(line)
            in_import = ')' not in line and ('(' in line or stripped.endswith('\\'))
            continue

        if in_import:
            cleaned.append(line)
            if stripped.endswith(')') and not stripped.startswith(')'):
                in_import = False
            continue

        # Skip orphaned ')' lines and garbage import items
        if stripped == ')':
            fixes.append(f"Removed orphaned ')' at line {i+1}")
            continue

        if stripped.startswith('from ') or stripped.startswith('import ') or stripped.startswith('services.'):
            fixes.append(f"Removed orphaned import/garbage at line {i+1}")
            continue

        # Skip lines that look like garbage import items (indented module paths, etc.)
        if stripped.startswith(('ControlTester', 'format_', 'AssertionRisk', 'AuditRiskAssessor',
                                'ClassicalVariablesSampler', 'PPSampler', 'StratifiedSampler',
                                'REVENUE_FRAUD_INDICATORS', 'FraudAssessor')):
            fixes.append(f"Removed orphaned import item at line {i+1}: {stripped[:30]}")
            continue

        cleaned.append(line)

    return '\n'.join(cleaned + lines[first_def:]), fixes


def fix_file(filepath: str) -> bool:
    """Apply all fixes to a file. Returns True if changes were made."""
    with open(filepath, encoding='utf-8') as f:
        original = f.read()

    content = original
    all_fixes: list[str] = []

    # Step 1: Fix triple quotes
    content, fixes = fix_triple_quotes(content)
    all_fixes.extend(fixes)

    # Step 2: Fix orphaned parens and garbage imports
    content, fixes = fix_orphaned_parens(content)
    all_fixes.extend(fixes)

    # Step 3: Fix indentation
    content, fixes = fix_indentation(content)
    all_fixes.extend(fixes)

    if content == original:
        print(f"  No changes needed for {filepath}")
        return True

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  Fixed {filepath}:")
    for fix in all_fixes:
        print(f"    - {fix}")

    return True


def main():
    files = sys.argv[1:] if len(sys.argv) > 1 else [
        "tests/unit/services/test_probability_calibrator.py",
        "tests/unit/services/test_orchestrator_signal_integration.py",
        "tests/unit/services/test_audit_modules.py",
    ]

    for fp in files:
        print(f"\nProcessing {fp}...")
        try:
            # Check current state
            err = find_unterminated_string(fp)
            if err:
                print(f"  Current error: line {err[0]}: {err[1]}")

            fix_file(fp)

            # Verify after fix
            err = find_unterminated_string(fp)
            if err:
                print(f"  Remaining error after fix: line {err[0]}: {err[1]}")
            else:
                print("  ✅ Tokenizes successfully!")
        except Exception as e:
            print(f"  Error processing {fp}: {e}")


if __name__ == "__main__":
    main()
