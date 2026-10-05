#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

FILE="backend/src/routes/weather.py"
[ -f "$FILE" ] || { echo "weather.py not found"; exit 1; }

python3 - "$FILE" << 'PYEOF'
import re, sys
path = sys.argv[1]
with open(path) as fh:
    src = fh.read()

# Match: raw = await response.json()
# Replace with: raw = await response.json(); then to_py() if JsProxy
before = src
src = re.sub(
    r"(\s*)raw = await response\.json\(\)",
    r"\1raw = await response.json()\n"
    r"\1if hasattr(raw, 'to_py'):\n"
    r"\1    raw = raw.to_py()",
    src,
)

# Also handle `data = await response.json()` in some places
src = re.sub(
    r"(\s*)data = await response\.json\(\)",
    r"\1data = await response.json()\n"
    r"\1if hasattr(data, 'to_py'):\n"
    r"\1    data = data.to_py()",
    src,
)

# Also handle `result = await response.json()` in some places
src = re.sub(
    r"(\s*)result = await response\.json\(\)",
    r"\1result = await response.json()\n"
    r"\1if hasattr(result, 'to_py'):\n"
    r"\1    result = result.to_py()",
    src,
)

# Also fix response.status -> response.status (keep as-is; Pyodide handles int access)
# But also fix possible response.ok usages that may fail
src = re.sub(
    r"if response\.status != 200:",
    "if response.status != 200:",
    src,
)

if src != before:
    with open(path, "w") as fh:
        fh.write(src)
    print("  patched weather.py")
else:
    print("  NO CHANGES — pattern not found; check file manually")
    sys.exit(1)

# Show the changed areas
import subprocess
PYEOF

echo ""
echo "Verifying:"
grep -n "raw = await response.json()\|data = await response.json()\|result = await response.json()\|\.to_py()" backend/src/routes/weather.py | head -20
