#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

FILE="backend/src/services/weather_service.py"
[ -f "$FILE" ] || { echo "weather_service.py not found"; exit 1; }

python3 - "$FILE" << 'PYEOF'
import re, sys
path = sys.argv[1]
with open(path) as fh:
    src = fh.read()

before = src
src = re.sub(
    r"(\s*)raw = await response\.json\(\)(?!\n\s*if hasattr)",
    r"\1raw = await response.json()\n"
    r"\1if hasattr(raw, 'to_py'):\n"
    r"\1    raw = raw.to_py()",
    src,
)

if src != before:
    with open(path, "w") as fh:
        fh.write(src)
    print("  patched weather_service.py")
else:
    print("  no changes (already patched or pattern not found)")
PYEOF

echo ""
echo "Verify:"
grep -n "raw = await response.json()\|\.to_py()" backend/src/services/weather_service.py
