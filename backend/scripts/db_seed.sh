#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Load seed data only
# Assumes migrations have already been applied.
#
# Usage:
#   bash backend/scripts/db_seed.sh            # local
#   bash backend/scripts/db_seed.sh --remote   # production
#   bash backend/scripts/db_seed.sh --file seeds/001_farmers.sql  # single file
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SEEDS_DIR="$BACKEND_DIR/seeds"
DB_NAME="${DB_NAME:-marcbantu-db}"

# ---------- Parse args ----------
TARGET="--local"
SINGLE_FILE=""
for ((i=1; i<=$#; i++)); do
    arg="${!i}"
    case $arg in
        --remote|--prod) TARGET="--remote" ;;
        --local)         TARGET="--local" ;;
        --file)
            i=$((i+1))
            SINGLE_FILE="${!i}"
            ;;
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

# ---------- Validate ----------
if [ ! -d "$SEEDS_DIR" ]; then
    err "Seeds directory not found: $SEEDS_DIR"
    exit 1
fi

if ! command -v wrangler &> /dev/null; then
    err "wrangler not found"
    exit 1
fi

# ---------- Banner ----------
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Marcbantu Africa — Load Seeds${NC}"
echo -e "${BLUE}  Target: ${TARGET}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ---------- Load single file ----------
if [ -n "$SINGLE_FILE" ]; then
    # Handle relative path
    if [ ! -f "$SINGLE_FILE" ]; then
        SINGLE_FILE="$SEEDS_DIR/$(basename "$SINGLE_FILE")"
    fi

    if [ ! -f "$SINGLE_FILE" ]; then
        err "File not found: $SINGLE_FILE"
        exit 1
    fi

    log "Loading: $(basename "$SINGLE_FILE")"
    wrangler d1 execute "$DB_NAME" $TARGET --file="$SINGLE_FILE" --yes
    ok "Loaded"
    exit 0
fi

# ---------- Load all seeds ----------
LOADED=0
FAILED=0

for file in "$SEEDS_DIR"/*.sql; do
    if [ ! -f "$file" ]; then
        continue
    fi

    name=$(basename "$file")
    log "→ $name"

    if wrangler d1 execute "$DB_NAME" $TARGET --file="$file" --yes 2>&1 | grep -qi "error"; then
        warn "Failed: $name"
        FAILED=$((FAILED + 1))
    else
        ok "$name loaded"
        LOADED=$((LOADED + 1))
    fi
done

# ---------- Summary ----------
echo ""
if [ "$LOADED" -gt 0 ]; then
    ok "$LOADED seed file(s) loaded"
fi
if [ "$FAILED" -gt 0 ]; then
    warn "$FAILED seed file(s) failed"
fi

echo ""