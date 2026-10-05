#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Fix missing `Response` imports
# ============================================================
# Adds `from js import Response` to every backend file
# that uses Response() without importing it.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- Colors ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}▶${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Marcbantu Africa — Fix Response imports${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ---------- Find all Python files ----------
FILES=$(find backend/src -name "*.py" -type f 2>/dev/null || true)

if [ -z "$FILES" ]; then
    err "No Python files found under backend/src"
    exit 1
fi

FIXED=0
SKIPPED=0
NO_NEED=0

for f in $FILES; do
    # Skip __pycache__ and package __init__ unless they use Response
    if echo "$f" | grep -q "__pycache__"; then
        continue
    fi

    # Does this file use Response( ?
    if ! grep -q "Response(" "$f" 2>/dev/null; then
        NO_NEED=$((NO_NEED + 1))
        continue
    fi

    # Does it already import Response?
    if grep -q "from js import Response" "$f" 2>/dev/null; then
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    # Insert the import after the docstring
    log "Fixing: $f"

    python3 - "$f" << 'PYEOF'
import sys, re

path = sys.argv[1]
with open(path, 'r') as fh:
    content = fh.read()

# Match a leading triple-quoted docstring
m = re.match(r'^("""[\s\S]*?"""\s*\n)', content)

import_line = "from js import Response\n"

if m:
    # Insert after docstring, with a blank line
    new_content = m.group(1) + "\n" + import_line + content[m.end():]
else:
    # No docstring — prepend
    new_content = import_line + "\n" + content

with open(path, 'w') as fh:
    fh.write(new_content)

print(f"  → added import to {path}")
PYEOF

    ok "Fixed: $f"
    FIXED=$((FIXED + 1))
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ Done${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Files fixed:        $FIXED"
echo "  Already had import: $SKIPPED"
echo "  Don't use Response: $NO_NEED"
echo ""

# ---------- Verify ----------
log "Verifying..."
REMAINING=$(grep -rl "Response(" backend/src --include="*.py" 2>/dev/null | while read f; do
    if echo "$f" | grep -q "__pycache__"; then continue; fi
    if ! grep -q "from js import Response" "$f" 2>/dev/null; then
        echo "$f"
    fi
done)

if [ -z "$REMAINING" ]; then
    ok "All files that use Response now import it."
else
    warn "Files still missing the import:"
    echo "$REMAINING"
fi

echo ""
echo "Next steps:"
echo "  1. Verify:   grep -r 'from js import Response' backend/src --include='*.py'"
echo "  2. Deploy:   npx wrangler deploy --env=\"\""
echo ""
