#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}▶${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Fix missing `fetch` import (Pyodide)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Files that use fetch() but don't import it from js
log "Scanning for files that use fetch() but don't import it"

FIXED=0

for f in $(grep -rl "fetch(" backend/src --include="*.py" 2>/dev/null || true); do
    # Skip __pycache__
    if echo "$f" | grep -q "__pycache__"; then continue; fi

    # Does it already have `from js import ...fetch...`?
    if grep -qE "from js import .*\bfetch\b" "$f"; then
        ok "  already imported: $f"
        continue
    fi

    # Does it have ANY `from js import ...` line?
    if grep -qE "^from js import " "$f"; then
        # Append fetch to the existing js import
        sed -i -E 's/^from js import (.*)$/from js import \1, fetch/' "$f"
        ok "  appended fetch: $f"
        FIXED=$((FIXED + 1))
        continue
    fi

    # No js import at all — add one after the docstring
    log "  adding new js import to: $f"
    python3 - "$f" << 'PYEOF'
import re, sys
path = sys.argv[1]
with open(path) as fh:
    src = fh.read()

import_line = "from js import fetch\n"

# Match leading docstring
m = re.match(r'^("""[\s\S]*?"""\s*\n)', src)
if m:
    new_src = m.group(1) + "\n" + import_line + src[m.end():]
else:
    new_src = import_line + "\n" + src

with open(path, "w") as fh:
    fh.write(new_src)
print(f"    inserted `{import_line.strip()}` in {path}")
PYEOF
    ok "  patched: $f"
    FIXED=$((FIXED + 1))
done

echo ""
echo "Fixed: $FIXED file(s)"
echo ""

# Verify
log "Verifying every file that uses fetch() imports it"
MISSING=0
for f in $(grep -rl "fetch(" backend/src --include="*.py" 2>/dev/null || true); do
    if echo "$f" | grep -q "__pycache__"; then continue; fi
    if ! grep -qE "from js import .*\bfetch\b" "$f"; then
        warn "  MISSING: $f"
        MISSING=$((MISSING + 1))
    fi
done

if [ "$MISSING" -eq 0 ]; then
    ok "  every file that uses fetch() imports it"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Done${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
