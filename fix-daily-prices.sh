#!/usr/bin/env bash
set -euo pipefail

FILE="backend/src/jobs/daily_prices.py"
[[ -f "$FILE" ]] || { echo "Missing $FILE"; exit 1; }

cp "$FILE" "$FILE.bak-$(date +%Y%m%d-%H%M%S)"
echo "Backup created"

python3 - "$FILE" << 'PY'
import pathlib, sys

path = pathlib.Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").split("\n")

# Find the two orphaned lines: `if hasattr(raw, 'to_py'):` at 1-space indent
# and the `raw = raw.to_py()` immediately after it.
out = []
i = 0
removed = 0
while i < len(lines):
    line = lines[i]

    # Orphan 1: " if hasattr(raw, 'to_py'):" — 1 space indent, no leading `#`
    if line == " if hasattr(raw, 'to_py'):":
        # Check the next line is the paired to_py
        if i + 1 < len(lines) and lines[i + 1] == "     raw = raw.to_py()":
            i += 2  # skip both
            removed += 1
            continue

    out.append(line)
    i += 1

result = "\n".join(out)

# Verify it parses
try:
    compile(result, str(path), "exec")
except SyntaxError as e:
    print(f"✗ Still broken at line {e.lineno}: {e.msg}")
    print("  NOT writing — manual review needed")
    sys.exit(1)

path.write_text(result, encoding="utf-8")
print(f"✓ Removed {removed} orphaned block(s)")
print(f"✓ File compiles cleanly")
PY

echo ""
echo "Verifying:"
python3 -m py_compile "$FILE" && echo "  ✓ $FILE parses cleanly" || echo "  ✗ Still broken"
