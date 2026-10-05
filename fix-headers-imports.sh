#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Fix missing js_headers imports
# ============================================================
# The previous script added `js_headers(...)` calls to files
# that don't import js_headers. This script adds the import.
# ============================================================

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}▶${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Fix missing js_headers imports${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

FIXED=0

for f in $(grep -rl "js_headers(" backend/src --include="*.py" 2>/dev/null || true); do
    # Skip utils.py — it defines js_headers
    if [ "$f" = "backend/src/utils.py" ]; then
        continue
    fi

    # Already imported?
    if grep -qE "^\s*from utils import.*\bjs_headers\b" "$f"; then
        ok "  already imports js_headers: $f"
        continue
    fi

    if grep -qE "^\s*import js_headers\b" "$f"; then
        ok "  already imports js_headers: $f"
        continue
    fi

    # Case A: multi-line  from utils import ( ... )
    if grep -qE "^from utils import \(" "$f"; then
        python3 - "$f" << 'PYEOF'
import re, sys
path = sys.argv[1]
with open(path) as fh:
    src = fh.read()
m = re.search(r"^from utils import \(([^)]*)\)", src, flags=re.M)
if m:
    inner = m.group(1)
    if "js_headers" not in inner:
        new_inner = inner.rstrip()
        if not new_inner.endswith(","):
            new_inner += ","
        new_inner += "\n    js_headers,\n"
        src = src[:m.start(1)] + new_inner + src[m.end(1):]
        with open(path, "w") as fh:
            fh.write(src)
        print(f"    added js_headers to multi-line import in {path}")
PYEOF
        ok "  patched multi-line import: $f"
        FIXED=$((FIXED + 1))
        continue
    fi

    # Case B: single-line  from utils import a, b, c
    if grep -qE "^from utils import " "$f"; then
        sed -i -E 's/^from utils import (.+)$/from utils import \1, js_headers/' "$f" 2>/dev/null || true
        # Guard against double-adding
        sed -i -E 's/, js_headers, js_headers/, js_headers/g' "$f"
        ok "  patched single-line import: $f"
        FIXED=$((FIXED + 1))
        continue
    fi

    # Case C: no utils import at all — prepend one after the docstring
    warn "  no utils import found; adding one: $f"
    python3 - "$f" << 'PYEOF'
import re, sys
path = sys.argv[1]
with open(path) as fh:
    src = fh.read()

import_line = "from utils import js_headers\n"

# Match a leading triple-quoted docstring
m = re.match(r'^("""[\s\S]*?"""\s*\n)', src)
if m:
    new_src = m.group(1) + "\n" + import_line + src[m.end():]
else:
    new_src = import_line + src

with open(path, "w") as fh:
    fh.write(new_src)
print(f"    inserted `{import_line.strip()}` at top of {path}")
PYEOF
    ok "  patched: $f"
    FIXED=$((FIXED + 1))
done

echo ""
log "Fixing imports done. Total files patched: $FIXED"
echo ""

# ============================================================
# Verify: every file that uses js_headers() must import it
# ============================================================
log "Verifying every js_headers() use has an import..."

MISSING=0
for f in $(grep -rl "js_headers(" backend/src --include="*.py" 2>/dev/null || true); do
    if [ "$f" = "backend/src/utils.py" ]; then
        continue
    fi
    if ! grep -qE "from utils import.*\bjs_headers\b|import js_headers\b" "$f"; then
        warn "  MISSING IMPORT: $f"
        MISSING=$((MISSING + 1))
    fi
done

if [ "$MISSING" -eq 0 ]; then
    ok "  every file that uses js_headers() imports it"
else
    warn "  $MISSING file(s) still missing the import — check above"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Done${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next steps:"
echo "  1. Review:   git diff backend/src | head -200"
echo "  2. Deploy:   npx wrangler deploy --env=\"\""
echo "  3. Test:     curl.exe -i https://marcbantu-api.josuit-mwasi.workers.dev/api/health"
echo ""
