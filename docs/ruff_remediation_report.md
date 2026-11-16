# Ruff Error Remediation Report - Phase 2

## Executive Summary

**Total errors found:** 444 (from `ruff check .` output)  
**Goal:** Reduce from 444 to <222 (50% reduction), targeting <100 for the Phase 2 milestone

## Error Category Breakdown

| Category | Code(s) | Count | Description |
|----------|---------|-------|-------------|
| **Unused variables** | F841 | ~20+ | Local variables assigned but never used |
| **Multiple statements on one line** | E701 | ~20+ | Colon-separated statements on same line |
| **Try-except-pass patterns** | SIM105 | 2 | Using try-except-pass instead of contextlib.suppress |
| **Unused loop variables** | B007 | 1 | Loop control variable not used in body |
| **Bare except clauses** | E722 | 1 | Bare `except:` without specifying exception type |
| **Ambiguous variable names** | E741 | 1 | Single-character variable `l` confusing with `1` |
| **Negated conditions** | SIM103 | 1 | Returning negated condition instead of inlining |
| **Unnecessary list() in sorted()** | C414 | 1 | `sorted(list(...))` instead of `sorted(...)` |

*(Note: Exact counts may vary; the ruff output file contains 444 total error messages)*

## Top Priority Remediation (Target: ~80% of issues from ~20% of rules)

### 1. F841 - Remove unused variable assignments
**Affected files:**
- `tests/unit/test_api_inbound_simulation.py:124` - `limiter` variable
- `tests/unit/test_decision_gate.py:246` - `override1` variable  
- `tests/unit/test_decision_gate.py:248` - `previous_count` variable
- `tests/unit/test_json_atomic_write.py:48` - `original` variable
- `apps/api/endpoints/gold_analytics.py` - various

**Action:** Remove assignment to unused variables, or use `_` prefix convention

### 2. E701 - Split multiple statements on one line
**Affected files:**
- `apps/api/endpoints/gold_analytics.py` - multiple locations
- `apps/api/endpoints/gold.py` - various
- `scripts/*.py` - some utilities

**Action:** Split `statement1; statement2` onto separate lines

### 3. SIM105 - Replace try-except-pass with contextlib.suppress
**Affected files:**
- `.agents/skills/ai-research-explore/scripts/passes/execution_feasibility.py:288,353`

**Action:** Replace:
```python
try:
    sys.path.remove(repo_root)
except ValueError:
    pass
```
with:
```python
with contextlib.suppress(ValueError):
    sys.path.remove(repo_root)
```

### 4. B007 - Rename unused loop variables
**Affected files:**
- `.agents/skills/news-aggregator-skill/scripts/daily_briefing.py:187`

**Action:** Rename `section` to `_section` in loop

### 5. E722 - Specify exception types in bare except
**Affected files:**
- `.agents/skills/news-aggregator-skill/scripts/fetch_bensbites.py:74`

**Action:** Replace `except: pass` with specific exception types

### 6. E741 - Rename ambiguous variable `l`
**Affected files:**
- `tests/unit/test_audit_fixes_batch2.py:390`

**Action:** Rename `l` to `login_request` or similar descriptive name

### 7. SIM103 - Inline negated conditions
**Affected files:**
- `z.py:239`

**Action:** Replace:
```python
if sym.isdigit() or len(sym) > 30 or len(sym) < 2:
    return False
return True
```
with:
```python
return not (sym.isdigit() or len(sym) > 30 or len(sym) < 2)
```

### 8. C414 - Remove unnecessary list() in sorted()
**Affected files:**
- `z.py:374`

**Action:** Replace `sorted(list(symbols))` with `sorted(symbols)`

## Remediation Sprint Plan

### Week 1: F841 & E701 (Target: ~30 errors fixed)
- [ ] Remove 20+ unused variable assignments
- [ ] Split 20+ multiple-statement lines

### Week 2: SIM105, B007, E722 (Target: ~15 errors fixed)
- [ ] Fix 2 try-except-pass patterns with contextlib.suppress
- [ ] Rename 1 unused loop variable
- [ ] Fix 1 bare except clause

### Week 3: E741, SIM103, C414 (Target: ~10 errors fixed)
- [ ] Rename 1 ambiguous variable
- [ ] Inline 1 negated condition
- [ ] Remove 1 unnecessary list() call

### Week 4: Code review & verification
- [ ] Run `ruff check .` to verify reduction
- [ ] Target: <300 errors (66% reduction from 444)
- [ ] Generate final remediation report