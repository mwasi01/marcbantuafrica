#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Fix Pyodide Response.new() headers
# ============================================================
# Problem: Pyodide's Response.new(body, headers=<python dict>)
# throws: "TypeError: Incorrect type: the provided value is
# not of type 'Sequence'".
#
# Fix: convert every Python dict passed as headers= to a JS
# object via Object.fromEntries([...]).
#
# This script:
#   1. Adds `Object` to the `from js import Response` line in
#      every file that uses Response.new().
#   2. Adds a `js_headers()` helper to utils.py.
#   3. Rewrites all `headers=<dict literal or expr>` inside
#      Response.new(...) to `headers=js_headers(<expr>)`.
#   4. Fixes `headers=default_headers` in utils.py's json_response.
#   5. Verifies no un-wrapped headers remain.
# ============================================================

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}▶${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Marcbantu Africa — Fix Response.new() headers${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ---------- Sanity ----------
if [ ! -f backend/src/utils.py ]; then
    err "backend/src/utils.py not found. Run from the project root."
    exit 1
fi

# ============================================================
# 1. Add `Object` to the `from js import Response` line
# ============================================================
log "Step 1: ensuring 'Object' is imported from js in every file that needs it"

FILES_WITH_RESPONSE=$(grep -rl "Response\.new(" backend/src --include="*.py" 2>/dev/null || true)

for f in $FILES_WITH_RESPONSE; do
    if grep -q "^from js import Response$" "$f"; then
        sed -i 's/^from js import Response$/from js import Response, Object/' "$f"
        ok "  patched import: $f"
    elif grep -q "from js import Response, Object" "$f"; then
        ok "  already correct: $f"
    elif grep -q "from js import" "$f"; then
        # has a from-js line but not the exact one — append Object if missing
        if ! grep -q "from js import.*\bObject\b" "$f"; then
            sed -i -E 's/^from js import (.*)$/from js import \1, Object/' "$f"
            ok "  appended Object: $f"
        fi
    fi
done

echo ""

# ============================================================
# 2. Add js_headers() helper to utils.py (idempotent)
# ============================================================
log "Step 2: adding js_headers() helper to utils.py"

if grep -q "^def js_headers" backend/src/utils.py; then
    ok "  js_headers() already present"
else
    # Insert after the last top-level import line
    python3 - << 'PYEOF'
import re
path = "backend/src/utils.py"
with open(path) as fh:
    content = fh.read()

helper = '''

# ============================================================
# JS HEADERS HELPER (Pyodide)
# ============================================================
def js_headers(d: dict):
    """Convert a Python dict to a JS-friendly headers object
    suitable for Response.new(..., headers=...)."""
    from js import Object
    return Object.fromEntries([(str(k), str(v)) for k, v in d.items()])


'''

# Insert after the last import line at the top
lines = content.splitlines(keepends=True)
insert_at = 0
for i, line in enumerate(lines):
    s = line.strip()
    if s.startswith("import ") or s.startswith("from "):
        insert_at = i + 1
    elif s and not s.startswith("#") and insert_at > 0:
        break

new_content = "".join(lines[:insert_at]) + helper + "".join(lines[insert_at:])
with open(path, "w") as fh:
    fh.write(new_content)
print("  inserted js_headers() helper")
PYEOF
    ok "  helper added"
fi

echo ""

# ============================================================
# 3. Rewrite headers= in every Response.new(...) call
# ============================================================
log "Step 3: wrapping headers= dict arguments with js_headers(...)"

# We handle two cases per file:
#   a) utils.py:   headers=default_headers          -> headers=js_headers(default_headers)
#   b) others:     headers={ ... }                  -> headers=js_headers({ ... })
#   c) middleware: headers=cors_headers()           -> headers=js_headers(cors_headers())

for f in $FILES_WITH_RESPONSE; do
    # (a) bare identifier headers=
    sed -i -E 's/headers=default_headers([,)])/headers=js_headers(default_headers)\1/g' "$f"

    # (c) helper-function headers=  (only cors_headers for now)
    sed -i -E 's/headers=cors_headers\(\)([,)])/headers=js_headers(cors_headers())\1/g' "$f"

    ok "  scanned: $f"
done

# (b) inline dict literals on one line:  headers={'Content-Type': 'text/plain'}
# Use python for correctness with quoting.
python3 - << 'PYEOF'
import re, glob

files = glob.glob("backend/src/**/*.py", recursive=True)
pattern = re.compile(r"headers=(\{[^{}]*\})")

for path in files:
    with open(path) as fh:
        src = fh.read()

    new_src, count = pattern.subn(lambda m: f"headers=js_headers({m.group(1)})", src)

    # Avoid double-wrapping
    new_src = new_src.replace("js_headers(js_headers(", "js_headers((")

    if count and new_src != src:
        with open(path, "w") as fh:
            fh.write(new_src)
        print(f"  wrapped {count} inline dict(s) in {path}")
PYEOF

echo ""

# ============================================================
# 4. Add js_headers to `from utils import ...` in each file that uses it
# ============================================================
log "Step 4: ensuring js_headers is imported in every file that uses it"

for f in $(grep -rl "js_headers(" backend/src --include="*.py" 2>/dev/null || true); do
    if [ "$f" = "backend/src/utils.py" ]; then
        continue
    fi
    if grep -qE "^from utils import.*\bjs_headers\b" "$f"; then
        ok "  already imported: $f"
        continue
    fi

    # Append js_headers to the existing multi-line or single-line utils import
    python3 - "$f" << 'PYEOF'
import re, sys
path = sys.argv[1]
with open(path) as fh:
    src = fh.read()

# Case 1: single-line  from utils import (a, b, c)
m = re.search(r"^from utils import \(([^)]*)\)", src, flags=re.M)
if m:
    inner = m.group(1)
    if "js_headers" not in inner:
        # Insert before closing paren
        new_inner = inner.rstrip()
        if not new_inner.endswith(","):
            new_inner += ","
        new_inner += "\n    js_headers,\n"
        src = src[:m.start(1)] + new_inner + src[m.end(1):]
        with open(path, "w") as fh:
            fh.write(src)
        print(f"  added js_headers to multi-line import in {path}")
        sys.exit(0)

# Case 2: single-line  from utils import a, b, c
m = re.match(r"^from utils import (.+)$", src, flags=re.M)
if m:
    line = m.group(0)
    if "js_headers" not in line:
        src = src.replace(line, line.rstrip() + ", js_headers", 1)
        with open(path, "w") as fh:
            fh.write(src)
        print(f"  added js_headers to import in {path}")
        sys.exit(0)

print(f"  WARN: could not find a from-utils import in {path} — add it manually")
PYEOF
    ok "  done: $f"
done

echo ""

# ============================================================
# 5. Verify
# ============================================================
log "Step 5: verifying"

echo ""
echo "  Remaining bare `headers=` inside Response.new that are NOT wrapped:"
BAD=$(grep -rn "Response\.new(" backend/src --include="*.py" -A 4 2>/dev/null \
    | grep -E "headers=" \
    | grep -v "js_headers(" \
    | grep -v "headers=None" \
    || true)

if [ -z "$BAD" ]; then
    ok "  none — all headers= are wrapped"
else
    warn "  the following lines still pass a raw value to headers=:"
    echo "$BAD"
fi

echo ""
echo "  Lines currently using js_headers(...):"
grep -rn "js_headers(" backend/src --include="*.py" 2>/dev/null | sed 's/^/    /' || true

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Done${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next steps:"
echo "  1. Inspect:  git diff backend/src | head -200"
echo "  2. Deploy:   npx wrangler deploy --env=\"\""
echo "  3. Tail:     npx wrangler tail --env=\"\" --format=pretty"
echo "  4. Test:     curl.exe -i https://marcbantu-api.josuit-mwasi.workers.dev/api/health"
echo ""
