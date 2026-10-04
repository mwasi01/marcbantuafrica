#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Run tests + linters
# Runs pytest with coverage, ruff, and optional mypy.
#
# Usage:
#   bash backend/scripts/test.sh              # all tests
#   bash backend/scripts/test.sh --fast       # no coverage
#   bash backend/scripts/test.sh --cov        # with coverage
#   bash backend/scripts/test.sh --lint       # lint only
#   bash backend/scripts/test.sh test_auth    # single file
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TESTS_DIR="$BACKEND_DIR/src/tests"
SRC_DIR="$BACKEND_DIR/src"

RUN_TESTS=true
RUN_LINT=true
COVERAGE=false
SINGLE_TEST=""

# ---------- Parse args ----------
for arg in "$@"; do
    case $arg in
        --fast|--no-cov) COVERAGE=false ;;
        --cov)           COVERAGE=true ;;
        --lint)          RUN_TESTS=false; RUN_LINT=true ;;
        --no-lint)       RUN_LINT=false ;;
        test_*|*test*)   SINGLE_TEST="$arg" ;;
    esac
done

# ---------- Colors ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}▶${NC} $1"; }
ok()  { echo -e "${GREEN}✓${NC} $1"; }
warn(){ echo -e "${YELLOW}⚠${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }
step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ---------- Banner ----------
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Marcbantu Africa — Test Suite${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════╝${NC}"
echo ""

cd "$BACKEND_DIR"

# ---------- Check Python ----------
if ! command -v python3 &> /dev/null; then
    err "python3 not found"
    exit 1
fi
ok "python3: $(python3 --version)"

# ---------- Detect venv ----------
if [ -d "venv" ]; then
    log "Activating venv..."
    # shellcheck disable=SC1091
    source venv/bin/activate
    ok "venv activated"
elif [ -d ".venv" ]; then
    log "Activating .venv..."
    # shellcheck disable=SC1091
    source .venv/bin/activate
    ok ".venv activated"
fi

# ---------- Install test deps if needed ----------
if ! python3 -c "import pytest" 2>/dev/null; then
    warn "pytest not installed — installing..."
    pip install pytest pytest-asyncio pytest-cov
fi

if [ "$RUN_LINT" = true ] && ! python3 -c "import ruff" 2>/dev/null; then
    if command -v ruff &> /dev/null; then
        ok "ruff found"
    else
        warn "ruff not installed — skipping lint"
        RUN_LINT=false
    fi
fi

# ============================================================
# LINT
# ============================================================
if [ "$RUN_LINT" = true ]; then
    step "Linting (ruff)"

    if command -v ruff &> /dev/null; then
        if ruff check "$SRC_DIR" 2>&1; then
            ok "Lint passed"
        else
            warn "Lint issues found (non-blocking)"
        fi
    else
        warn "ruff CLI not found — skipping"
    fi
fi

# ============================================================
# TESTS
# ============================================================
if [ "$RUN_TESTS" = true ]; then
    step "Running tests"

    if [ ! -d "$TESTS_DIR" ]; then
        err "Tests directory not found: $TESTS_DIR"
        exit 1
    fi

    # Build pytest command
    PYTEST_ARGS=("-v" "--tb=short")

    if [ "$COVERAGE" = true ]; then
        PYTEST_ARGS+=(
            "--cov=$SRC_DIR"
            "--cov-report=term-missing"
            "--cov-report=html:$BACKEND_DIR/htmlcov"
            "--cov-fail-under=60"
        )
    fi

    if [ -n "$SINGLE_TEST" ]; then
        log "Running single test: $SINGLE_TEST"
        PYTEST_ARGS+=("$TESTS_DIR/$SINGLE_TEST.py")
    else
        PYTEST_ARGS+=("$TESTS_DIR")
    fi

    if python3 -m pytest "${PYTEST_ARGS[@]}"; then
        ok "All tests passed"
        if [ "$COVERAGE" = true ] && [ -d "$BACKEND_DIR/htmlcov" ]; then
            echo ""
            ok "Coverage report: backend/htmlcov/index.html"
        fi
    else
        err "Tests failed"
        exit 1
    fi
fi

# ============================================================
# SUMMARY
# ============================================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✓ Test run complete${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""