#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Database reset
# Drops all tables and rebuilds from migrations + seeds.
#
# Usage:
#   bash backend/scripts/db_reset.sh            # local — no prompt
#   bash backend/scripts/db_reset.sh --remote   # prod — confirm required
#   bash backend/scripts/db_reset.sh --remote --force  # skip confirm
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_NAME="${DB_NAME:-marcbantu-db}"

# ---------- Parse args ----------
TARGET="--local"
FORCE=false
for arg in "$@"; do
    case $arg in
        --remote|--prod) TARGET="--remote" ;;
        --local)         TARGET="--local" ;;
        --force|-f)      FORCE=true ;;
    esac
done

# ---------- Colors ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}▶${NC} $1"; }
ok()  { echo -e "${GREEN}✓${NC} $1"; }
warn(){ echo -e "${YELLOW}⚠${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }

# ---------- Confirm for remote ----------
if [ "$TARGET" = "--remote" ] && [ "$FORCE" != true ]; then
    echo ""
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  ⚠  WARNING: This will DESTROY all production data${NC}"
    echo -e "${RED}  Database: $DB_NAME${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    read -p "Type 'DELETE' to confirm: " confirm
    if [ "$confirm" != "DELETE" ]; then
        err "Aborted"
        exit 1
    fi
fi

echo ""
log "Resetting database '$DB_NAME' on $TARGET"

# ---------- Drop all tables ----------
log "Dropping all tables..."

# Get all tables (excluding internal sqlite tables)
TABLES=$(wrangler d1 execute "$DB_NAME" $TARGET --command="SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != '_cf_KV'" --json 2>/dev/null | grep -o '"name":"[^"]*"' | sed 's/"name":"//g;s/"//g' || echo "")

if [ -z "$TABLES" ]; then
    warn "No tables found (database may already be empty)"
else
    # Build a DROP statement for each
    for table in $TABLES; do
        log "  Dropping: $table"
        wrangler d1 execute "$DB_NAME" $TARGET --command="DROP TABLE IF EXISTS \"$table\"" --yes 2>/dev/null || true
    done
    ok "All tables dropped"
fi

# Also clear the D1 metadata tables
wrangler d1 execute "$DB_NAME" $TARGET --command="DELETE FROM d1_migrations" --yes 2>/dev/null || true
wrangler d1 execute "$DB_NAME" $TARGET --command="DELETE FROM schema_migrations" --yes 2>/dev/null || true

# ---------- Rebuild ----------
echo ""
log "Rebuilding from migrations + seeds"
echo ""

if [ ! -x "$SCRIPT_DIR/db_setup.sh" ]; then
    chmod +x "$SCRIPT_DIR/db_setup.sh"
fi

bash "$SCRIPT_DIR/db_setup.sh" $TARGET

# ---------- Done ----------
echo ""
ok "Database reset complete"
echo ""