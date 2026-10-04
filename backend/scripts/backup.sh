#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Database backup
# Exports D1 to a timestamped SQL file in backups/.
#
# Usage:
#   bash backend/scripts/backup.sh              # remote backup
#   bash backend/scripts/backup.sh --local      # local backup
#   bash backend/scripts/backup.sh --keep 10    # keep last 10 backups
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
BACKUP_DIR="$ROOT_DIR/backups"
DB_NAME="${DB_NAME:-marcbantu-db}"

TARGET="--remote"
KEEP=20

# ---------- Parse args ----------
for ((i=1; i<=$#; i++)); do
    arg="${!i}"
    case $arg in
        --remote|--prod) TARGET="--remote" ;;
        --local)         TARGET="--local" ;;
        --keep)
            i=$((i+1))
            KEEP="${!i}"
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

# ---------- Setup ----------
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ENV_LABEL=$([ "$TARGET" = "--remote" ] && echo "prod" || echo "local")
FILENAME="marcbantu_${ENV_LABEL}_${TIMESTAMP}.sql"
FILEPATH="$BACKUP_DIR/$FILENAME"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Marcbantu Africa — Database Backup${NC}"
echo -e "${BLUE}  Target: $TARGET${NC}"
echo -e "${BLUE}  Output: backups/$FILENAME${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ---------- Check wrangler ----------
if ! command -v wrangler &> /dev/null; then
    err "wrangler not found"
    exit 1
fi

# ---------- Get tables ----------
log "Listing tables..."
TABLES=$(wrangler d1 execute "$DB_NAME" $TARGET --command="SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'" --json 2>/dev/null | grep -o '"name":"[^"]*"' | sed 's/"name":"//g;s/"//g' || echo "")

if [ -z "$TABLES" ]; then
    err "No tables found or database not accessible"
    exit 1
fi

TABLE_COUNT=$(echo "$TABLES" | wc -l | tr -d ' ')
ok "$TABLE_COUNT tables found"

# ---------- Write header ----------
{
    echo "-- ============================================================"
    echo "-- Marcbantu Africa — Database Backup"
    echo "-- Environment: $ENV_LABEL"
    echo "-- Database:    $DB_NAME"
    echo "-- Created:     $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo "-- Tables:      $TABLE_COUNT"
    echo "-- ============================================================"
    echo ""
    echo "PRAGMA foreign_keys = OFF;"
    echo "BEGIN TRANSACTION;"
    echo ""
} > "$FILEPATH"

# ---------- Dump each table ----------
ROWS_TOTAL=0

for table in $TABLES; do
    log "  → $table"

    # Get CREATE statement
    CREATE_SQL=$(wrangler d1 execute "$DB_NAME" $TARGET --command="SELECT sql FROM sqlite_master WHERE type='table' AND name='$table'" --json 2>/dev/null | grep -o '"sql":"[^"]*"' | sed 's/"sql":"//;s/"$//' | sed 's/\\"/"/g' || echo "")

    if [ -n "$CREATE_SQL" ]; then
        {
            echo "-- Table: $table"
            echo "DROP TABLE IF EXISTS \"$table\";"
            echo "$CREATE_SQL;"
        } >> "$FILEPATH"
    fi

    # Get row count
    ROW_COUNT=$(wrangler d1 execute "$DB_NAME" $TARGET --command="SELECT COUNT(*) as c FROM \"$table\"" --json 2>/dev/null | grep -o '"c":[0-9]*' | grep -o '[0-9]*' || echo "0")
    ROWS_TOTAL=$((ROWS_TOTAL + ROW_COUNT))

    # Get data as INSERTs (limit to prevent massive dumps)
    if [ "$ROW_COUNT" -gt 0 ] && [ "$ROW_COUNT" -lt 100000 ]; then
        wrangler d1 execute "$DB_NAME" $TARGET --command="SELECT * FROM \"$table\"" --json 2>/dev/null | \
            python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if not data or not isinstance(data, list):
        sys.exit(0)
    # wrangler --json returns [{'results': [...], 'success': True}]
    for block in data:
        for row in block.get('results', []):
            cols = ', '.join(f'\"{k}\"' for k in row.keys())
            vals = ', '.join(_fmt(v) for v in row.values())
            print(f'INSERT INTO \"$table\" ({cols}) VALUES ({vals});')
except Exception:
    pass

def _fmt(v):
    if v is None:
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    return \"'\" + str(v).replace(\"'\", \"''\") + \"'\"
" >> "$FILEPATH" 2>/dev/null || true
    fi

    echo "" >> "$FILEPATH"
done

# ---------- Write footer ----------
{
    echo "COMMIT;"
    echo ""
    echo "-- ============================================================"
    echo "-- End of backup — $ROWS_TOTAL rows across $TABLE_COUNT tables"
    echo "-- ============================================================"
} >> "$FILEPATH"

# ---------- Compress ----------
log "Compressing backup..."
if command -v gzip &> /dev/null; then
    gzip "$FILEPATH"
    FILEPATH="${FILEPATH}.gz"
    ok "Compressed: $(basename "$FILEPATH")"
else
    warn "gzip not available — backup kept uncompressed"
fi

# ---------- Report size ----------
SIZE=$(du -h "$FILEPATH" | cut -f1)
ok "Backup size: $SIZE"
ok "Total rows: $ROWS_TOTAL"

# ---------- Rotate old backups ----------
log "Rotating old backups (keeping $KEEP)..."
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/marcbantu_*.sql* 2>/dev/null | wc -l | tr -d ' ')

if [ "$BACKUP_COUNT" -gt "$KEEP" ]; then
    DELETE_COUNT=$((BACKUP_COUNT - KEEP))
    ls -1t "$BACKUP_DIR"/marcbantu_*.sql* | tail -n "$DELETE_COUNT" | while read -r f; do
        rm -f "$f"
        log "  Deleted: $(basename "$f")"
    done
    ok "Removed $DELETE_COUNT old backup(s)"
else
    ok "No rotation needed ($BACKUP_COUNT backups)"
fi

# ---------- Summary ----------
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ Backup complete${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  File:   $FILEPATH"
echo "  Size:   $SIZE"
echo "  Rows:   $ROWS_TOTAL"
echo ""
echo "Restore with:"
echo "  gunzip -c $FILEPATH | wrangler d1 execute $DB_NAME $TARGET --file=/dev/stdin"
echo ""