#!/usr/bin/env bash
# Replace `Response(` with `Response.new(` in all backend Python files.
# Skips `Response.new(` (already correct) and `from js import Response`.

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "${BLUE}▶${NC} $1"; }
ok()  { echo -e "${GREEN}✓${NC} $1"; }

COUNT=0
for f in $(find backend/src -name "*.py" -not -path "*__pycache__*"); do
    # Does it call Response( but NOT Response.new( ?
    if grep -qE 'Response\(' "$f" && grep -qE 'Response\(' "$f" | grep -vqE 'Response\.new\('; then
        log "Patching: $f"
        # Only rewrite `Response(` that isn't already `Response.new(`
        # Use a negative lookbehind via perl for safety.
        perl -i -pe 's/(?<!\.)\bResponse\(/Response.new(/g' "$f"
        ok "Patched: $f"
        COUNT=$((COUNT + 1))
    fi
done

echo ""
echo "Files patched: $COUNT"
echo ""
log "Verifying..."
if grep -rnE '(?<!\.)\bResponse\(' backend/src --include="*.py" -P 2>/dev/null; then
    echo -e "${YELLOW}⚠ Some bare Response( calls remain — check above${NC}"
else
    ok "No bare Response( calls remain."
fi
