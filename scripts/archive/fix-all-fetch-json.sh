#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

python3 << 'PYEOF'
import re, glob

files = glob.glob("backend/src/**/*.py", recursive=True)
patched = []

for path in files:
    with open(path) as fh:
        src = fh.read()
    before = src

    # Pattern: <var> = await response.json()  — add .to_py() after if JsProxy
    # Skip if a following line already does .to_py()
    def add_to_py(match):
        indent = match.group(1)
        var = match.group(2)
        return (
            f"{indent}{var} = await response.json()\n"
            f"{indent}if hasattr({var}, 'to_py'):\n"
            f"{indent}    {var} = {var}.to_py()"
        )

    # Use negative lookahead to avoid double-patching
    src = re.sub(
        r"(\s*)(\w+) = await response\.json\(\)(?!\n\s*if hasattr)",
        add_to_py,
        src,
    )

    # Also handle `await resp.json()` where var is different
    src = re.sub(
        r"(\s*)(\w+) = await resp\.json\(\)(?!\n\s*if hasattr)",
        lambda m: (
            f"{m.group(1)}{m.group(2)} = await resp.json()\n"
            f"{m.group(1)}if hasattr({m.group(2)}, 'to_py'):\n"
            f"{m.group(1)}    {m.group(2)} = {m.group(2)}.to_py()"
        ),
        src,
    )

    # Also handle await fetch(...).json() chains if present
    if src != before:
        with open(path, "w") as fh:
            fh.write(src)
        patched.append(path)

print(f"  Patched {len(patched)} file(s):")
for p in patched:
    print(f"    {p}")
PYEOF
