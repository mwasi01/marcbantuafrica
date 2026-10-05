#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

FILE="backend/src/utils.py"
[ -f "$FILE" ] || { echo "utils.py not found"; exit 1; }

python3 - "$FILE" << 'PYEOF'
import re, sys
path = sys.argv[1]
with open(path) as fh:
    src = fh.read()

new_shim = '''class _SearchParams:
    """Mimics the JS URL object with .search_params.get()/.has()."""
    def __init__(self, request):
        self._request = request
        # Some code does url.search_params.get(...) — expose self as that.
        self.search_params = self

    def get(self, key, default=None):
        return get_query(self._request, key, default)

    def has(self, key):
        return get_query(self._request, key) is not None


def _sp(request) -> _SearchParams:
    """Return an object with .get()/.has() that works on Pyodide.

    Also exposes .search_params so `url.search_params.get(...)` works.
    """
    return _SearchParams(request)
'''

# Replace existing _SearchParams class + _sp function
pattern = r"class _SearchParams:\n(?:    .*\n|\n)*?def _sp\(request\) -> _SearchParams:\n(?:    .*\n|\n)*?(?=\n\n# |\n\ndef |\Z)"
src2, n = re.subn(pattern, new_shim, src, count=1)

if n == 0:
    print("  WARN: could not find _SearchParams block; check utils.py manually")
    sys.exit(1)

with open(path, "w") as fh:
    fh.write(src2)
print("  _SearchParams + _sp patched")
PYEOF

grep -n "class _SearchParams\|def _sp\|self.search_params" backend/src/utils.py
