#!/usr/bin/env bash
# ============================================================
# Marcbantu Africa — Fix JsProxy subscripts + URL search_params
# ============================================================
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}▶${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Fix JsProxy + URL.search_params${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ------------------------------------------------------------
# 1. Fix db.py
# ------------------------------------------------------------
log "Step 1: fixing db.py query / query_one"

python3 - << 'PYEOF'
import re
path = "backend/src/db.py"
with open(path) as fh:
    src = fh.read()

new_query = '''    async def query(self, sql: str, params: list = None) -> list:
        """Run a SELECT and return all rows as list of Python dicts."""
        stmt = self.db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        result = await stmt.all()
        if not result or not result.results:
            return []
        rows = result.results
        if hasattr(rows, "to_py"):
            rows = rows.to_py()
        return list(rows)
'''

new_query_one = '''    async def query_one(self, sql: str, params: list = None) -> dict | None:
        """Run a SELECT and return first row as a Python dict or None."""
        stmt = self.db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        result = await stmt.first()
        if not result:
            return None
        if hasattr(result, "to_py"):
            return result.to_py()
        return result
'''

src = re.sub(
    r"    async def query\(self, sql: str, params: list = None\) -> list:\n(?:        .*\n|\n)*?(?=\n    async def|\n    # ===|\Z)",
    new_query + "\n", src, count=1,
)
src = re.sub(
    r"    async def query_one\(self, sql: str, params: list = None\) -> dict \| None:\n(?:        .*\n|\n)*?(?=\n    async def|\n    # ===|\Z)",
    new_query_one + "\n", src, count=1,
)
with open(path, "w") as fh:
    fh.write(src)
print("  patched db.py")
PYEOF
ok "db.py patched"
echo ""

# ------------------------------------------------------------
# 2. Fix get_query / get_int_query in utils.py
# ------------------------------------------------------------
log "Step 2: fixing get_query / get_int_query in utils.py"

python3 - << 'PYEOF'
import re
path = "backend/src/utils.py"
with open(path) as fh:
    src = fh.read()

new_get_query = '''def get_query(request, key: str, default=None):
    """Get a query parameter (Pyodide-safe)."""
    try:
        from urllib.parse import urlparse, parse_qs
        raw = str(request.url)
        parsed = urlparse(raw)
        values = parse_qs(parsed.query)
        if key in values and values[key]:
            return values[key][0]
        return default
    except Exception:
        return default
'''

new_get_int_query = '''def get_int_query(request, key: str, default: int = 0) -> int:
    """Get an integer query parameter (Pyodide-safe)."""
    val = get_query(request, key)
    try:
        return int(val) if val is not None and val != "" else default
    except (TypeError, ValueError):
        return default
'''

src = re.sub(
    r"def get_query\(request, key: str, default=None\):\n(?:    .*\n|\n)*?(?=\ndef |\n# ===|\Z)",
    new_get_query + "\n", src, count=1,
)
src = re.sub(
    r"def get_int_query\(request, key: str, default: int = 0\) -> int:\n(?:    .*\n|\n)*?(?=\ndef |\n# ===|\Z)",
    new_get_int_query + "\n", src, count=1,
)
with open(path, "w") as fh:
    fh.write(src)
print("  patched utils.py")
PYEOF
ok "utils.py patched"
echo ""

# ------------------------------------------------------------
# 3. Add _sp helper to utils.py
# ------------------------------------------------------------
log "Step 3: adding _sp(request) helper to utils.py"

if grep -q "^def _sp(request)" backend/src/utils.py; then
    ok "  _sp already present"
else
    python3 - << 'PYEOF'
import re
path = "backend/src/utils.py"
with open(path) as fh:
    src = fh.read()

helper = '''

# ============================================================
# QUERY PARAM SHIM (drop-in replacement for url.search_params)
# ============================================================
class _SearchParams:
    """Mimics the JS URLSearchParams API using request.url string parsing."""
    def __init__(self, request):
        self._request = request

    def get(self, key, default=None):
        return get_query(self._request, key, default)

    def has(self, key):
        return get_query(self._request, key) is not None


def _sp(request) -> _SearchParams:
    """Return an object with .get()/.has() that works on Pyodide."""
    return _SearchParams(request)

'''

# Insert right before the "# AUTH HELPERS" section, or after get_int_query
marker = "def get_int_query(request, key: str, default: int = 0) -> int:"
idx = src.find(marker)
if idx >= 0:
    rest = src[idx:]
    m = re.search(r"\n\ndef |\n\n# ===|\Z", rest[10:])
    if m:
        end = idx + 10 + m.start()
        src = src[:end] + helper + src[end:]
    else:
        src += helper
else:
    src += helper

with open(path, "w") as fh:
    fh.write(src)
print("  added _sp() helper")
PYEOF
    ok "  _sp helper added"
fi
echo ""

# ------------------------------------------------------------
# 4. Rewrite url.search_params usages
# ------------------------------------------------------------
log "Step 4: rewriting url.search_params usages across route files"

python3 - << 'PYEOF'
import re, glob
files = glob.glob("backend/src/**/*.py", recursive=True)
patched = 0

for path in files:
    with open(path) as fh:
        src = fh.read()
    original = src

    src = re.sub(r"\burl\s*=\s*request\.url\b", "url = _sp(request)", src)
    src = re.sub(r"\brequest\.url\.search_params\.get\(", "get_query(request, ", src)
    src = re.sub(r"\bstr\(request\.url\)\.search_params\.get\(", "get_query(request, ", src)

    if src != original:
        with open(path, "w") as fh:
            fh.write(src)
        patched += 1
        print(f"  patched: {path}")

print(f"  total files patched: {patched}")
PYEOF
echo ""

# ------------------------------------------------------------
# 5. Ensure imports
# ------------------------------------------------------------
log "Step 5: ensuring imports"

for f in $(grep -rl "_sp(\|get_query(" backend/src --include="*.py" 2>/dev/null || true); do
    if [ "$f" = "backend/src/utils.py" ]; then continue; fi
    needs_sp=0; needs_gq=0
    grep -q "_sp(" "$f" && needs_sp=1
    grep -q "get_query(" "$f" && needs_gq=1

    python3 - "$f" "$needs_sp" "$needs_gq" << 'PYEOF'
import re, sys
path, sp, gq = sys.argv[1], sys.argv[2] == "1", sys.argv[3] == "1"
with open(path) as fh:
    src = fh.read()

add = []
if sp and not re.search(r"from utils import[\s\S]{0,500}\b_sp\b", src):
    add.append("_sp")
if gq and not re.search(r"from utils import[\s\S]{0,500}\bget_query\b", src):
    add.append("get_query")

if not add:
    sys.exit(0)

m = re.search(r"^from utils import \(([^)]*)\)", src, flags=re.M)
if m:
    inner = m.group(1)
    for name in add:
        if name not in inner:
            inner = inner.rstrip()
            if not inner.endswith(","):
                inner += ","
            inner += f"\n    {name},\n"
    src = src[:m.start(1)] + inner + src[m.end(1):]
    with open(path, "w") as fh:
        fh.write(src)
    print(f"  added {add} to multi-line import: {path}")
    sys.exit(0)

m = re.match(r"^from utils import (.+)$", src, flags=re.M)
if m:
    line = m.group(0)
    for name in add:
        if name not in line:
            line = line.rstrip() + f", {name}"
    src = src.replace(m.group(0), line, 1)
    with open(path, "w") as fh:
        fh.write(src)
    print(f"  added {add} to import: {path}")
    sys.exit(0)

print(f"  WARN: no from-utils import in {path}; add {add} manually")
PYEOF
done

echo ""
log "Verifying..."
echo ""
echo "  Remaining raw url.search_params uses (excluding utils.py shim):"
grep -rn "search_params" backend/src --include="*.py" 2>/dev/null | grep -v "utils.py" | grep -v "_SearchParams" | grep -v "_sp\b" || echo "    (none)"

echo ""
echo "  _sp / get_query uses:"
grep -rn "_sp(request)\|get_query(request" backend/src --include="*.py" 2>/dev/null | sed 's/^/    /' | head -40 || echo "    (none)"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Done${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next:"
echo "  npx wrangler deploy --env=\"\""
echo "  npx wrangler tail --env=\"\" --format=pretty"
