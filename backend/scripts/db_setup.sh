#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Database setup
# Creates D1 database (if not exists), applies migrations,
# and loads seed data. Safe to re-run — uses IF NOT EXISTS.
#
# Usage:
#   bash backend/scripts/db_setup.sh            # local
#   bash backend/scripts/db_setup.sh --remote   # production
#   bash backend/scripts/db_setup.sh --no-seed  # skip seeds
# ============================================================

set -e  # exit on error

# ---------- Config ----------
DB_NAME="${DB_NAME:-marcbantu-db}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$BACKEND_DIR/migrations"
SEEDS_DIR="$BACKEND_DIR/seeds"

# ---------- Parse args ----------
TARGET="--local"
LOAD_SEEDS=true
for arg in "$@"; do
    case $arg in
        --remote|--prod)
            TARGET="--remote"
            ;;
        --local)
            TARGET="--local"
            ;;
        --no-seed)
            LOAD_SEEDS=false
            ;;
        *)
            ;;
    esac
done

# ---------- Colors ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}▶${NC} $1"; }
ok()  { echo -e "${GREEN}✓${NC} $1"; }
warn(){ echo -e "${YELLOW}⚠${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }

# ---------- Banner ----------
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Marcbantu Africa — Database Setup${NC}"
echo -e "${BLUE}  Target: ${TARGET}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ---------- Check wrangler ----------
if ! command -v wrangler &> /dev/null; then
    err "wrangler not found. Install with: npm install -g wrangler"
    exit 1
fi
ok "wrangler found: $(wrangler --version)"

# ---------- Check directories ----------
if [ ! -d "$MIGRATIONS_DIR" ]; then
    err "Migrations directory not found: $MIGRATIONS_DIR"
    exit 1
fi

if [ "$LOAD_SEEDS" = true ] && [ ! -d "$SEEDS_DIR" ]; then
    warn "Seeds directory not found: $SEEDS_DIR — skipping seeds"
    LOAD_SEEDS=false
fi

# ---------- Create database (only if remote and doesn't exist) ----------
if [ "$TARGET" = "--remote" ]; then
    log "Checking if database '$DB_NAME' exists..."
    if wrangler d1 list 2>/dev/null | grep -q "$DB_NAME"; then
        ok "Database '$DB_NAME' already exists"
    else
        log "Creating database '$DB_NAME'..."
        wrangler d1 create "$DB_NAME"
        echo ""
        warn "⚠  IMPORTANT: Copy the database_id above into wrangler.toml"
        echo ""
        read -p "Press Enter to continue after updating wrangler.toml... "
    fi
else
    ok "Using local database (SQLite in .wrangler/state)"
fi

# ---------- Apply migrations ----------
echo ""
log "Applying migrations from $MIGRATIONS_DIR"
echo ""

MIGRATION_COUNT=0
for file in "$MIGRATIONS_DIR"/*.sql; do
    if [ ! -f "$file" ]; then
        continue
    fi
    name=$(basename "$file")
    log "→ $name"
    if wrangler d1 execute "$DB_NAME" $TARGET --file="$file" --yes 2>&1 | grep -q "Executed"; then
        ok "$name applied"
        MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
    else
        # Wrangler sometimes exits 0 even on SQL error — check for errors
        if wrangler d1 execute "$DB_NAME" $TARGET --file="$file" --yes 2>&1 | grep -qi "error"; then
            err "Failed: $name"
            exit 1
        else
            ok "$name applied"
            MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
        fi
    fi
done

if [ "$MIGRATION_COUNT" -eq 0 ]; then
    warn "No migration files found in $MIGRATIONS_DIR"
else
    ok "$MIGRATION_COUNT migration(s) applied"
fi

# ---------- Apply seeds ----------
if [ "$LOAD_SEEDS" = true ]; then
    echo ""
    log "Loading seed data from $SEEDS_DIR"
    echo ""

    SEED_COUNT=0
    for file in "$SEEDS_DIR"/*.sql; do
        if [ ! -f "$file" ]; then
            continue
        fi
        name=$(basename "$file")
        log "→ $name"
        if wrangler d1 execute "$DB_NAME" $TARGET --file="$file" --yes 2>&1 | grep -qi "error"; then
            warn "Seed failed (may be duplicate): $name"
        else
            ok "$name loaded"
            SEED_COUNT=$((SEED_COUNT + 1))
        fi
    done

    if [ "$SEED_COUNT" -eq 0 ]; then
        warn "No seed files found in $SEEDS_DIR"
    else
        ok "$SEED_COUNT seed file(s) loaded"
    fi
fi

# ---------- Verify ----------
echo ""
log "Verifying tables..."
TABLE_COUNT=$(wrangler d1 execute "$DB_NAME" $TARGET --command="SELECT COUNT(*) as c FROM sqlite_master WHERE type='table'" --json 2>/dev/null | grep -o '"c":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "$TABLE_COUNT" -gt 0 ]; then
    ok "$TABLE_COUNT tables in database"
else
    warn "Could not verify table count"
fi

# ---------- Done ----------
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ Database setup complete${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next steps:"
echo "  • Start dev server:  wrangler dev"
echo "  • Run tests:         bash backend/scripts/test.sh"
echo "  • Deploy:            bash backend/scripts/deploy.sh"
echo ""