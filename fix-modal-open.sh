#!/usr/bin/env bash
# Fix Modal.open() in app.js — distinguish element IDs from HTML strings.
set -euo pipefail

FILE="frontend/assets/js/app.js"
[[ -f "$FILE" ]] || { echo "app.js not found"; exit 1; }

# Backup
STAMP="$(date +%Y%m%d-%H%M%S)"
cp "$FILE" "$FILE.bak-$STAMP"
echo "Backup: $FILE.bak-$STAMP"

python3 - << 'PY'
import re, pathlib, sys

p = pathlib.Path("frontend/assets/js/app.js")
src = p.read_text(encoding="utf-8")

# Match the current open() method body and replace it
pattern = re.compile(
    r"(open\(contentOrId\)\s*\{)(.*?)(\n\s*close\(modal\)\s*\{)",
    re.DOTALL,
)

m = pattern.search(src)
if not m:
    print("SKIP: could not find Modal.open block")
    sys.exit(1)

new_body = """
            let modal;
            const isHtmlString = typeof contentOrId === 'string'
                && contentOrId.trim().startsWith('<');

            if (!isHtmlString && typeof contentOrId === 'string') {
                modal = document.getElementById(contentOrId);
                if (!modal) return;
                modal.classList.add('open');
            } else {
                modal = document.createElement('div');
                modal.className = 'modal-overlay open';
                modal.innerHTML = `<div class="modal">${contentOrId}</div>`;
                modal.style.cssText = `
                    position:fixed; inset:0; background:rgba(0,0,0,0.6);
                    z-index:2000; display:flex; align-items:center;
                    justify-content:center; padding:20px;
                `;
                document.body.appendChild(modal);
            }

            modal.addEventListener('click', (e) => {
                if (e.target === modal) Modal.close(modal);
            });

            const handler = (e) => {
                if (e.key === 'Escape') {
                    Modal.close(modal);
                    document.removeEventListener('keydown', handler);
                }
            };
            document.addEventListener('keydown', handler);

            return modal;
        },
"""

# Replace from `open(contentOrId) {` up to (but not including) `close(modal) {`
src = src[:m.start(2)] + new_body + src[m.start(3):]
p.write_text(src, encoding="utf-8")
print("PATCHED: Modal.open now distinguishes IDs from HTML")
PY

echo ""
echo "Verify:"
grep -n "isHtmlString" frontend/assets/js/app.js
