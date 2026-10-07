#!/usr/bin/env bash
set -euo pipefail

FILE="backend/src/scheduled/morning_jobs.py"
[[ -f "$FILE" ]] || { echo "Missing: $FILE"; exit 1; }

cp "$FILE" "$FILE.bak-$(date +%Y%m%d-%H%M%S)"
echo "Backup created"

python3 - "$FILE" << 'PY'
import pathlib, sys, re

path = pathlib.Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").split("\n")
out = []
i = 0
removed = 0

# Match orphan pattern: a line whose stripped form is `if hasattr(X, 'to_py'):`
# whose indent does not match surrounding code, immediately followed by a
# `.to_py()` reassignment at deeper indent.
if_re = re.compile(r"^\s*if\s+hasattr\(\s*(\w+)\s*,\s*['\"]to_py['\"]\s*\)\s*:\s*$")
top_re = re.compile(r"^\s*(\w+)\s*=\s*\1\.to_py\(\)\s*$")

while i < len(lines):
    line = lines[i]
    m = if_re.match(line)
    if m:
        var = m.group(1)
        # Next non-blank line must be the paired to_py assignment
        j = i + 1
        if j < len(lines):
            m2 = top_re.match(lines[j])
            if m2 and m2.group(1) == var:
                # Find indent of "if" line
                indent_if = len(line) - len(line.lstrip())
                # Heuristic: the preceding code line's indent should be same as `if`
                # (it's part of the same statement block). If the indent is
                # anything other than "the previous code line's indent + 0"
                # OR the "if" line itself is at an odd indent like 1 space
                # (which is what breaks Python), remove the block.
                prev_code_indent = None
                for k in range(i - 1, -1, -1):
                    if lines[k].strip():
                        prev_code_indent = len(lines[k]) - len(lines[k].lstrip())
                        break

                # Detect broken indentation: 1-space indent, or mismatch with
                # the previous non-blank line's indent.
                broken = False
                if indent_if == 1:
                    broken = True
                elif prev_code_indent is not None and indent_if > prev_code_indent:
                    # "if" is deeper than previous code but previous code
                    # doesn't end with ":" — so "if" shouldn't be indented more
                    if not lines[k].rstrip().endswith(":"):
                        broken = True

                if broken:
                    # Skip the if and to_py lines
                    i += 2
                    removed += 1
                    continue
    out.append(line)
    i += 1

result = "\n".join(out)

try:
    compile(result, str(path), "exec")
except SyntaxError as e:
    print(f"✗ Still broken at line {e.lineno}: {e.msg}")
    print(f"  Line: {repr(lines[e.lineno - 1]) if e.lineno else '?'}")
    print("  NOT writing — manual review needed")
    sys.exit(1)

path.write_text(result, encoding="utf-8")
print(f"✓ Removed {removed} orphaned block(s)")
print(f"✓ File compiles cleanly")
PY

echo ""
echo "Verifying:"
python3 -m py_compile "$FILE" && echo "  ✓ $FILE parses cleanly" || {
    echo "  ✗ Still broken:"
    python3 -m py_compile "$FILE" 2>&1 | head -3
}
