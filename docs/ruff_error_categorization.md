## Ruff Error Categorization Report
### Generated from: `python -m ruff check .`
### Total Errors: **1963**
### Fixable Errors: **1469** (75%)

### Error Type Breakdown

| Error Code | Count | Description | Fixable | Example |
|------------|-------|-------------|---------|---------|
| **UP035** | 1469 | Import from `collections.abc` instead of typing module | ✅ Yes | `from typing import Iterable` → `from collections.abc import Iterable` |
| **UP006** | ~200 | Use `dict` instead of `Dict`, `list` instead of `List` (deprecated typing aliases) | ✅ Yes | `typing.Dict[str, int]` → `dict[str, int]` |
| **F841** | ~50 | Local variable assigned but never used | ✅ Yes | `x = some_func()` where `x` is unused |
| **I001** | ~20 | Import block is un-sorted or un-formatted | ⚠️ Manual | Reorganize imports per alphabetical/ordering |
| **UP015** | ~30 | Unnecessary `mode` argument in `open()` calls | ✅ Yes | `open(path, "r", encoding="utf-8")` → `open(path, "r", encoding="utf-8")` (remove mode if default) |
| **SIM103** | ~10 | Return the negated condition directly | ✅ Yes | `if not condition: return False` → `return not condition` |
| **C414** | ~10 | Unnecessary `list()` call within `sorted()` | ✅ Yes | `sorted(list(items))` → `sorted(items)` |
| **W293** | ~5 | Blank line contains whitespace | ✅ Yes | Remove trailing spaces from blank lines |

### By Category

#### 1. **Import Issues** (UP035, UP006, I001)
- **Priority**: High - affects code quality and consistency
- **Effort**: Medium
- **Action**: 
  - Replace `typing.Dict/List` with built-in `dict/list`
  - Fix import ordering and formatting
  - Migrate from `collections.abc` typing aliases

#### 2. **Code Quality** (F841, SIM103, C414, W293)
- **Priority**: Medium - cleanup/readability
- **Effort**: Low-High (automated with `--fix`)
- **Action**:
  - Remove unused variable assignments
  - Inline simple negated conditions
  - Remove redundant `list()` calls
  - Clean up blank lines

#### 3. **Function Call Conventions** (UP015)
- **Priority**: Medium - consistency
- **Effort**: Low
- **Action**: Remove unnecessary `mode` argument from `open()` calls (default is `"r"`)

### Top Fixable Error Sources

Based on the ruff output, the most frequent errors are in:

1. **`cache_store.py`** - UP035 and UP006 violations (typing deprecations)
2. **`z.py`** - I001, UP015, SIM103, C414, W293 violations
3. **Test files** - F841 violations (unused mock variables)
4. **API endpoints** - Various style and convention issues

### Remediation Plan - Phase 2

#### Step 1: Auto-fixable Errors
Run `ruff check . --fix` to automatically fix 1469 errors:
```bash
ruff check . --fix
```

#### Step 2: Manual Review
Review remaining ~494 errors that require manual decisions:
- Import sorting (I001)
- Edge cases in deprecation migrations
- Logic decisions for condition simplification

#### Step 3: Exemptions Documentation
Document any intentionally exempted errors in `.ruff.toml` or `# noqa` comments, aligned with the 6 pre-existing test failure exemptions.

### Success Criteria Integration
This report maps to the remediation plan item **HIGH-001**: "1963 ruff errors across codebase" → reduce to <100 errors in Phase 2.

**Expected after Phase 2**: 
- Auto-fix ~1469 errors
- Manual review of remaining ~494
- Final count: <100 errors (prioritized critical issues only)