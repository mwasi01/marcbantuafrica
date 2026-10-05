#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Domain migration
# Replaces marcbantuafrica.com → marcbantuafrica.com in all files
#
# Usage:
#   bash update-domain.sh            # Preview changes
#   bash update-domain.sh --apply    # Apply changes
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- Config ----------
OLD_DOMAIN="marcbantu\.africa"
NEW_DOMAIN="marcbantuafrica.com"

# File extensions to search
EXTS=("html" "js" "json" "xml" "css" "md" "toml" "sql" "py" "txt" "sh" "yml" "yaml")

# Directories to skip
SKIP_DIRS=(".git" "node_modules" ".wrangler" "__pycache__" "venv" ".venv" "htmlcov" ".pytest_cache" "backups" "dist" "build")

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

# ---------- Parse args ----------
APPLY=false
for arg in "$@"; do
    case $arg in
        --apply) APPLY=true ;;
        --help|-h)
            echo "Usage: bash update-domain.sh [--apply]"
            echo ""
            echo "  (no args)     Preview changes only"
            echo "  --apply       Actually modify files"
            echo ""
            exit 0
            ;;
    esac
done

# ---------- Build find command ----------
FIND_ARGS=()
for ext in "${EXTS[@]}"; do
    FIND_ARGS+=("-name" "*.${ext}" "-o")
done
# Remove trailing -o
unset 'FIND_ARGS[${#FIND_ARGS[@]}-1]'

EXCLUDE_ARGS=()
for dir in "${SKIP_DIRS[@]}"; do
    EXCLUDE_ARGS+=("-path" "*/${dir}" "-prune" "-o")
done

# ---------- Banner ----------
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Marcbantu Africa — Domain migration${NC}"
echo -e "${BLUE}  ${OLD_DOMAIN//\\/}  →  ${NEW_DOMAIN}${NC}"
if [ "$APPLY" = true ]; then
    echo -e "${YELLOW}  Mode: APPLY (files will be modified)${NC}"
else
    echo -e "${BLUE}  Mode: PREVIEW (no changes)${NC}"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ---------- Find files containing the old domain ----------
MATCHING_FILES=$(grep -rl "marcbantu\.africa" . \
    --include="*.html" \
    --include="*.js" \
    --include="*.json" \
    --include="*.xml" \
    --include="*.css" \
    --include="*.md" \
    --include="*.toml" \
    --include="*.sql" \
    --include="*.py" \
    --include="*.txt" \
    --include="*.sh" \
    --include="*.yml" \
    --include="*.yaml" \
    --exclude-dir=".git" \
    --exclude-dir="node_modules" \
    --exclude-dir=".wrangler" \
    --exclude-dir="__pycache__" \
    --exclude-dir="venv" \
    --exclude-dir=".venv" \
    --exclude-dir="htmlcov" \
    --exclude-dir=".pytest_cache" \
    --exclude-dir="backups" \
    --exclude-dir="dist" \
    --exclude-dir="build" \
    2>/dev/null || true)

if [ -z "$MATCHING_FILES" ]; then
    ok "No files contain marcbantuafrica.com. Nothing to do."
    exit 0
fi

FILE_COUNT=$(echo "$MATCHING_FILES" | wc -l | tr -d ' ')
log "Found $FILE_COUNT file(s) containing marcbantuafrica.com"
echo ""

# ---------- Show matches ----------
echo -e "${BLUE}Files:${NC}"
echo "$MATCHING_FILES" | while read -r f; do
    COUNT=$(grep -c "marcbantu\.africa" "$f" 2>/dev/null || echo "0")
    printf "  %-60s (%s match%s)\n" "$f" "$COUNT" "$([ "$COUNT" != "1" ] && echo "es")"
done
echo ""

# ---------- Preview changes ----------
if [ "$APPLY" = false ]; then
    log "Preview of changes (first 5 matches per file):"
    echo ""
    echo "$MATCHING_FILES" | while read -r f; do
        echo -e "${YELLOW}── $f ──${NC}"
        grep -n "marcbantu\.africa" "$f" 2>/dev/null | head -5 | while read -r line; do
            NEW_LINE=$(echo "$line" | sed "s/marcbantu\.africa/marcbantuafrica.com/g")
            echo "  ${RED}−${NC} $line"
            echo "  ${GREEN}+${NC} $NEW_LINE"
        done
        echo ""
    done

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  This was a PREVIEW. No files were changed.${NC}"
    echo -e "${YELLOW}  To apply, run: bash update-domain.sh --apply${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
fi

# ---------- Apply changes ----------
log "Applying changes..."
echo ""

CHANGED=0
FAILED=0

echo "$MATCHING_FILES" | while read -r f; do
    if [ -f "$f" ]; then
        if sed -i "s/marcbantu\.africa/marcbantuafrica.com/g" "$f" 2>/dev/null; then
            ok "Updated: $f"
            CHANGED=$((CHANGED + 1))
        else
            err "Failed: $f"
            FAILED=$((FAILED + 1))
        fi
    fi
done

# ---------- Verification ----------
echo ""
log "Verifying..."
REMAINING=$(grep -rl "marcbantu\.africa" . \
    --include="*.html" \
    --include="*.js" \
    --include="*.json" \
    --include="*.xml" \
    --include="*.css" \
    --include="*.md" \
    --include="*.toml" \
    --include="*.sql" \
    --include="*.py" \
    --include="*.txt" \
    --include="*.sh" \
    --exclude-dir=".git" \
    --exclude-dir="node_modules" \
    --exclude-dir=".wrangler" \
    --exclude-dir="__pycache__" \
    2>/dev/null | grep -v "marcbantuafrica.com" || true)

echo ""
if [ -z "$REMAINING" ]; then
    ok "All files updated. No traces of marcbantuafrica.com remain."
else
    warn "Some files still contain marcbantuafrica.com:"
    echo "$REMAINING"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ Domain migration complete${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next steps:"
echo "  1. Review changes:  git diff"
echo "  2. Commit:          git add . && git commit -m 'Update domain to marcbantuafrica.com'"
echo "  3. Push:            git push"
echo ""
