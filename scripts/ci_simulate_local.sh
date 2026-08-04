#!/usr/bin/env bash
# ── Local CI Simulator ────────────────────────────────────────
# Simulates what GitHub Actions would run for ci-pr.yml.
# Usage: bash scripts/ci_simulate_local.sh
# Can also be sourced: source scripts/ci_simulate_local.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SEPARATOR="────────────────────────────────────────────────────────"
PASS="[PASS]"
FAIL="[FAIL]"
SKIP="[SKIP]"

# ── Path Filter Simulation ────────────────────────────────────
# Same as ci-pr.yml paths: only run if Python-related files changed.
# Uses git diff against the merge-base (or HEAD~1 if not in a PR).
# When no git history exists (detached HEAD, shallow clone), runs anyway.
GIT_HASH=
if git rev-parse --git-dir >/dev/null 2>&1; then
    if git rev-parse HEAD~1 >/dev/null 2>&1; then
        # Check if any tracked .py / pyproject / requirements / workflow files changed
        CHANGED_FILES=$(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only 2>/dev/null || echo "")
        MATCHING_FILES=$(echo "$CHANGED_FILES" | grep -E '\.py$|pyproject\.toml|requirements.*\.txt|\.github/workflows/ci-pr\.yml|frontend/src/.*\.(ts|tsx|js)$|frontend/package\.json|frontend/package-lock\.json|frontend/tsconfig\.json|frontend/next\.config\..*|frontend/eslint\.config\.mjs|Dockerfile.*' || true)
        if [ -n "$CHANGED_FILES" ] && [ -z "$MATCHING_FILES" ]; then
            echo "$SEPARATOR"
            echo "  ⏭️  PATH FILTER: No Python-related files changed."
            echo "     Changed files:"
            echo "$CHANGED_FILES" | sed 's/^/       /'
            echo "     SKIPPING all checks (ci-pr.yml paths filter would skip)."
            echo "$SEPARATOR"
            exit 0
        fi
        GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    fi
fi

# Check / install required packages (same as CI workflow does).
# NOTE: This machine has a local proxy blocking PyPI; on GitHub Actions
# (no proxy) the pip install in the workflow will succeed.
MISSING_DEPS=false
pip show pytest-timeout >/dev/null 2>&1 || MISSING_DEPS=true
pip show pytest-asyncio >/dev/null 2>&1 || MISSING_DEPS=true
if [ "$MISSING_DEPS" = true ]; then
    echo "  [setup] Attempting to install missing packages..."
    pip install -q pytest-timeout pytest-asyncio 2>/dev/null && echo "  [setup] OK" || echo "  [setup] WARNING: proxy blocks PyPI — will run without --timeout flag"
fi

echo "$SEPARATOR"
echo "  PR Quality Gate — Local CI Simulation"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
if [ -n "$GIT_HASH" ]; then
    echo "  Git hash: $GIT_HASH"
fi
echo "$SEPARATOR"
echo ""

ALL_PASSED=true

# ── Helper ───────────────────────────────────────────────────
run_step() {
    local step_name="$1"
    shift
    echo ""
    echo "  Step: $step_name"
    echo "  Command: $*"
    echo "  $(printf '%.0s-' {1..60})"
    if "$@" 2>&1; then
        echo "  $PASS $step_name"
        return 0
    else
        local rc=$?
        echo "  $FAIL $step_name (exit code $rc)"
        ALL_PASSED=false
        return $rc
    fi
}

# ═══════════════════════════════════════════════════════════════
# JOB 1: Lint (ruff)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "$SEPARATOR"
echo "  JOB 1: Lint (ruff)"
echo "$SEPARATOR"

run_step "ruff check ." ruff check . --output-format=concise

# ═══════════════════════════════════════════════════════════════
# JOB 2: Type-check (mypy) — signal chain strict
# ═══════════════════════════════════════════════════════════════
echo ""
echo "$SEPARATOR"
echo "  JOB 2: Type-check (mypy) — signal chain strict"
echo "$SEPARATOR"

run_step "mypy signal chain" mypy \
    services/quant_signal_orchestrator.py \
    services/signal_voting_system.py \
    services/confidence_scorer.py \
    services/probability_calibrator.py \
    services/signal_decision_engine.py \
    services/signal_accuracy_tracker.py \
    services/ml_signal_connector.py \
    services/auto_retrain_pipeline.py \
    core/calibration_bootstrap.py \
    core/db_utils.py \
    --show-error-codes \
    --ignore-missing-imports

# ═══════════════════════════════════════════════════════════════
# JOB 3: Unit Tests (pytest)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "$SEPARATOR"
echo "  JOB 3: Unit Tests (pytest)"
echo "$SEPARATOR"

export ENV=test
export DATABASE_URL="sqlite+aiosqlite:///:memory:?check_same_thread=false"
export REDIS_URL="redis://localhost:6379/0"

# Use --timeout only if pytest-timeout is installed (local proxy may block PyPI)
PYTEST_EXTRA=""
pip show pytest-timeout >/dev/null 2>&1 && PYTEST_EXTRA="--timeout=60"

run_step "pytest tests/unit" python -m pytest tests/unit \
    $PYTEST_EXTRA \
    --tb=short \
    --no-header \
    -q 2>&1

# ═══════════════════════════════════════════════════════════════
# JOB 4: Signal Quality Benchmark (quick mode)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "$SEPARATOR"
echo "  JOB 4: Signal Quality Benchmark (quick mock)"
echo "$SEPARATOR"

# This is informational — always passes even if benchmark has issues
if python tests/benchmark_signal_quality.py --quick 2>&1; then
    echo "  $PASS benchmark"
else
    echo "  $SKIP benchmark (informational)"
fi

# ═══════════════════════════════════════════════════════════════
# JOB 5: Frontend Lint (tsc + eslint)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "$SEPARATOR"
echo "  JOB 5: Frontend Lint (tsc + eslint)"
echo "$SEPARATOR"

if command -v node &>/dev/null && command -v npm &>/dev/null; then
    echo "  Node.js: $(node --version)"
    echo "  npm:     $(npm --version)"
    echo ""

    # npm ci (simulate with npm install if no lockfile changes — local may differ)
    if [ -f frontend/package-lock.json ]; then
        run_step "npm ci" bash -c "cd frontend && npm ci 2>&1"
    else
        echo "  $SKIP npm ci (no package-lock.json found)"
    fi

    # TypeScript type-check
    if [ -f frontend/tsconfig.json ]; then
        run_step "tsc --noEmit" bash -c "cd frontend && npx tsc --noEmit 2>&1"
    else
        echo "  $SKIP tsc --noEmit (no tsconfig.json found)"
    fi

    # ESLint (informational)
    if [ -f frontend/eslint.config.mjs ]; then
        if cd frontend && npm run lint 2>&1; then
            echo "  $PASS ESLint"
        else
            echo "  $SKIP ESLint (informational — non-zero exit ignored)"
        fi
        cd "$ROOT_DIR"
    else
        echo "  $SKIP ESLint (no ESLint config found)"
    fi
else
    echo "  $SKIP Frontend Lint — Node.js/npm not found locally"
    echo "  (GitHub Actions provides Node.js ${{ env.NODE_VERSION }} automatically)"
fi

# ═══════════════════════════════════════════════════════════════
# JOB 6: Dockerfile Lint (hadolint)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "$SEPARATOR"
echo "  JOB 6: Dockerfile Lint (hadolint)"
echo "$SEPARATOR"

if command -v hadolint &>/dev/null; then
    echo "  hadolint: $(hadolint --version 2>&1 | head -1)"
    echo ""

    # Lint each Dockerfile
    DOCKERFILES=(
        Dockerfile
        Dockerfile.api
        Dockerfile.admin
        Dockerfile.worker
        Dockerfile.frontend
        Dockerfile.scheduler
        Dockerfile.decision-engine
    )

    ALL_DOCKERFILE_OK=true
    for df in "${DOCKERFILES[@]}"; do
        if [ ! -f "$df" ]; then
            echo "  $SKIP $df — file not found"
            continue
        fi
        echo "  Linting $df..."
        if hadolint "$df" --failure-threshold warning 2>&1; then
            echo "  $PASS $df"
        else
            echo "  $FAIL $df"
            ALL_DOCKERFILE_OK=false
        fi
        echo ""
    done

    if [ "$ALL_DOCKERFILE_OK" = false ]; then
        ALL_PASSED=false
    fi
else
    echo "  $SKIP Dockerfile Lint — hadolint CLI not installed locally"
    echo "  Install: brew install hadolint  OR  download from github.com/hadolint/hadolint"
    echo "  (GitHub Actions uses hadolint/hadolint-action@v3.1.0 instead)"
fi

# ═══════════════════════════════════════════════════════════════
# Final Result
# ═══════════════════════════════════════════════════════════════
echo ""
echo "$SEPARATOR"
if [ "$ALL_PASSED" = true ]; then
    echo "  $PASS ALL CHECKS PASSED — CI-PR workflow is valid!"
    exit 0
else
    echo "  $FAIL SOME CHECKS FAILED — review errors above."
    exit 1
fi
