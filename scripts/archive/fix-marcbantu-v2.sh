#!/usr/bin/env bash
#
# fix-marcbantu-v2.sh — corrected for frontend/assets/js layout.
# Fixes SW scope, cache versioning, UI guards, and misc bugs.
# Idempotent. Backs up every touched file.

set -euo pipefail

RED=$'\033[0;31m'; GRN=$'\033[0;32m'; YLW=$'\033[1;33m'; BLU=$'\033[0;34m'; NC=$'\033[0m'
info() { printf "%s[INFO]%s %s\n" "$BLU" "$NC" "$*"; }
ok()   { printf "%s[ OK ]%s %s\n" "$GRN" "$NC" "$*"; }
warn() { printf "%s[WARN]%s %s\n" "$YLW" "$NC" "$*"; }
fail() { printf "%s[FAIL]%s %s\n" "$RED" "$NC" "$*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FE="frontend"
JS="$FE/assets/js"

[[ -d "$FE" && -d "$JS" ]] || { fail "Run from project root"; exit 1; }

STAMP="$(date +%Y%m%d-%H%M%S)"
backup() {
    local f="$1"
    [[ -f "$f" && ! -f "$f.bak-$STAMP" ]] && cp "$f" "$f.bak-$STAMP"
    return 0
}

info "Project root: $SCRIPT_DIR"

# ============================================================
# 0. Warn about swap files
# ============================================================
for swp in "$JS"/.*.swp "$JS"/.*.swx; do
    [[ -e "$swp" ]] && warn "Swap file present: $swp (close vim!)"
done

# ============================================================
# 1. Move sw.js to frontend root
# ============================================================
if [[ -f "$JS/sw.js" ]]; then
    info "Moving $JS/sw.js → $FE/sw.js"
    [[ -f "$FE/sw.js" ]] && backup "$FE/sw.js"
    mv "$JS/sw.js" "$FE/sw.js"
    ok "sw.js relocated"
else
    info "sw.js already at frontend root"
fi

# ============================================================
# 2. Rewrite frontend/sw.js
# ============================================================
if [[ -f "$FE/sw.js" ]]; then
    info "Rewriting $FE/sw.js (v2 cache, SWR)"
    backup "$FE/sw.js"
    cat > "$FE/sw.js" <<'SW_EOF'
/**
 * Marcbantu Africa — Service Worker (v2).
 * At /sw.js so scope covers whole origin.
 */
const CACHE_NAME     = 'marcbantu-v2';
const API_CACHE_NAME = 'marcbantu-api-v2';

const STATIC_ASSETS = [
    '/', '/index.html', '/about.html', '/contact.html', '/partners.html',
    '/privacy.html', '/terms.html', '/404.html',
    '/login.html', '/register.html',
    '/dashboard.html', '/records.html', '/planning.html', '/finance.html',
    '/decisions.html', '/operations.html', '/market.html', '/weather.html',
    '/pest.html', '/learning.html', '/profile.html',
    '/manifest.json',
    '/assets/css/main.css', '/assets/css/app.css', '/assets/css/print.css',
    '/assets/js/api.js', '/assets/js/app.js', '/assets/js/auth.js',
    '/assets/js/register-sw.js', '/assets/js/offline.js',
    '/assets/js/notifications.js', '/assets/js/farms.js',
    '/assets/js/dashboard.js', '/assets/js/records.js',
    '/assets/js/planning.js', '/assets/js/finance.js',
    '/assets/js/decisions.js', '/assets/js/operations.js',
    '/assets/js/market.js', '/assets/js/weather.js',
    '/assets/js/pest.js', '/assets/js/learning.js',
    '/assets/js/profile.js',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) =>
            Promise.all(
                STATIC_ASSETS.map((url) =>
                    cache.add(url).catch((err) =>
                        console.warn('[SW] precache miss:', url, err)
                    )
                )
            )
        )
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    const keep = new Set([CACHE_NAME, API_CACHE_NAME]);
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    if (request.method !== 'GET') return;
    if (!url.protocol.startsWith('http')) return;
    if (url.origin !== self.location.origin) return;

    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirst(request, API_CACHE_NAME));
        return;
    }
    if (request.mode === 'navigate') {
        event.respondWith(networkFirst(request, CACHE_NAME));
        return;
    }
    event.respondWith(staleWhileRevalidate(request, CACHE_NAME));
});

async function staleWhileRevalidate(request, cacheName) {
    const cache  = await caches.open(cacheName);
    const cached = await cache.match(request);
    const net = fetch(request)
        .then((res) => { if (res && res.ok) cache.put(request, res.clone()); return res; })
        .catch(() => null);
    return cached || (await net) || offlineResponse(request);
}

async function networkFirst(request, cacheName) {
    try {
        const res = await fetch(request);
        if (res && res.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, res.clone());
        }
        return res;
    } catch {
        const cached = await caches.match(request);
        if (cached) return cached;
        return offlineResponse(request);
    }
}

function offlineResponse(request) {
    if (request.mode === 'navigate') {
        return caches.match('/index.html').then((r) => r || new Response('Offline', { status: 503 }));
    }
    if (request.url.includes('/api/')) {
        return new Response(
            JSON.stringify({ error: 'Offline', offline: true }),
            { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
    }
    return new Response('Offline', { status: 503 });
}

self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});
SW_EOF
    ok "sw.js rewritten"
fi

# ============================================================
# 3. Patch register-sw.js
# ============================================================
if [[ -f "$JS/register-sw.js" ]]; then
    info "Hardening register-sw.js"
    backup "$JS/register-sw.js"
    cat > "$JS/register-sw.js" <<'REG_EOF'
/**
 * Marcbantu Africa — SW registration.
 * Registers /sw.js at root scope.
 */
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js', { scope: '/' })
            .then((reg) => {
                console.log('[SW] registered', reg.scope);
                reg.addEventListener('updatefound', () => {
                    const nw = reg.installing;
                    if (!nw) return;
                    nw.addEventListener('statechange', () => {
                        if (nw.state === 'installed' && navigator.serviceWorker.controller) {
                            console.log('[SW] new version ready');
                        }
                    });
                });
            })
            .catch((err) => console.warn('[SW] registration failed', err));
    });
}
REG_EOF
    ok "register-sw.js updated"
fi

# ============================================================
# 4. Fix app.js Toast palette
# ============================================================
if [[ -f "$JS/app.js" ]]; then
    info "Patching app.js Toast palette"
    backup "$JS/app.js"
    python3 - <<'PY'
import re, pathlib, sys
p = pathlib.Path("frontend/assets/js/app.js")
src = p.read_text(encoding="utf-8")
pat = re.compile(
    r"const\s+colors\s*=\s*\{(?P<body>.*?)\}\s*\[\s*type\s*\]\s*\|\|\s*colors\.info\s*;",
    re.DOTALL,
)
m = pat.search(src)
if not m:
    print("SKIP: already patched"); sys.exit(0)
body = m.group("body").strip()
repl = (
    "const palettes = {\n"
    f"                {body}\n"
    "            };\n"
    "            const colors = palettes[type] || palettes.info;"
)
src = src[:m.start()] + repl + src[m.end():]
p.write_text(src, encoding="utf-8")
print("PATCHED: app.js")
PY
    ok "app.js patched"
fi

# ============================================================
# 5. Rewrite farms.js with UI guard
# ============================================================
if [[ -f "$JS/farms.js" ]]; then
    info "Rewriting farms.js with UI guard"
    backup "$JS/farms.js"
    cat > "$JS/farms.js" <<'FARMS_EOF'
/**
 * Marcbantu Africa — Farm creation helper.
 */
(function () {
    'use strict';

    function boot() {
        const UI = window.UI;
        if (!UI || !UI.Modal || !UI.Toast) return false;
        const { Toast, Modal } = UI;

        async function openCreateModal(onCreated) {
            const modal = Modal.open(`
                <div style="padding:28px; max-width:520px;">
                    <h2 style="margin:0 0 6px; color:#1a3c2e; display:flex; align-items:center; gap:10px;">
                        <i class="fas fa-seedling" style="color:#d4a017;"></i> Create Your Farm
                    </h2>
                    <p style="margin:0 0 20px; color:#4a5a4a; font-size:.9rem;">
                        Add your first farm to start tracking records, planning seasons, and seeing profit.
                    </p>
                    <form id="createFarmForm" style="display:flex; flex-direction:column; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Farm Name *</span>
                            <input name="name" required placeholder="e.g. Home Farm, Kieni Plot"
                                style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                            <label style="display:flex; flex-direction:column; gap:6px;">
                                <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Size (acres)</span>
                                <input type="number" step="0.01" name="size_acres" placeholder="e.g. 5"
                                    style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                            </label>
                            <label style="display:flex; flex-direction:column; gap:6px;">
                                <span style="font-size:13px; font-weight:600; color:#1a3c2e;">County</span>
                                <input name="county" placeholder="e.g. Nyeri"
                                    style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                            </label>
                        </div>
                        <details style="border:1px solid #e2e8dd; border-radius:10px; padding:12px;">
                            <summary style="cursor:pointer; font-weight:600; color:#1a3c2e; font-size:14px;">
                                Optional: GPS coordinates (for weather)
                            </summary>
                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:12px;">
                                <label style="display:flex; flex-direction:column; gap:6px;">
                                    <span style="font-size:12px; font-weight:600; color:#1a3c2e;">Latitude</span>
                                    <input type="number" step="0.0001" name="latitude" placeholder="-1.2864"
                                        style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                </label>
                                <label style="display:flex; flex-direction:column; gap:6px;">
                                    <span style="font-size:12px; font-weight:600; color:#1a3c2e;">Longitude</span>
                                    <input type="number" step="0.0001" name="longitude" placeholder="36.8172"
                                        style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                </label>
                            </div>
                            <button type="button" id="useMyLocation" class="btn-outline"
                                style="margin-top:10px; width:100%; justify-content:center; font-size:13px;">
                                <i class="fas fa-location-arrow"></i> Use my current location
                            </button>
                        </details>
                        <div style="display:flex; gap:12px; justify-content:flex-end; margin-top:6px;">
                            <button type="button" class="btn-outline" data-action="cancel">Cancel</button>
                            <button type="submit" class="btn-primary">Create Farm</button>
                        </div>
                    </form>
                </div>
            `);

            modal.querySelector('[data-action="cancel"]')
                .addEventListener('click', () => Modal.close(modal));

            modal.querySelector('#useMyLocation').addEventListener('click', () => {
                if (!navigator.geolocation) {
                    Toast.warning('Geolocation not supported');
                    return;
                }
                Toast.info('Getting your location...');
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        modal.querySelector('[name="latitude"]').value = pos.coords.latitude.toFixed(4);
                        modal.querySelector('[name="longitude"]').value = pos.coords.longitude.toFixed(4);
                        Toast.success('Location set!');
                    },
                    (err) => Toast.error('Could not get location: ' + err.message),
                    { timeout: 10000 }
                );
            });

            const form = modal.querySelector('#createFarmForm');
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const fd = new FormData(form);
                const payload = {};
                for (const [k, v] of fd.entries()) {
                    if (v === '') continue;
                    payload[k] = ['size_acres', 'latitude', 'longitude'].includes(k)
                        ? parseFloat(v) : v;
                }
                const btn = form.querySelector('button[type="submit"]');
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';

                const r = await Api.createFarm(payload);
                if (!r.ok) {
                    Toast.error(r.error || 'Failed to create farm');
                    btn.disabled = false;
                    btn.textContent = 'Create Farm';
                    return;
                }
                Toast.success('Farm created!');
                Modal.close(modal);
                if (typeof onCreated === 'function') onCreated(r.data);
            });

            return modal;
        }

        window.Farm = { openCreateModal };
        window.dispatchEvent(new Event('farm:ready'));
        return true;
    }

    if (boot()) return;
    document.addEventListener('DOMContentLoaded', () => {
        if (boot()) return;
        let tries = 0;
        const timer = setInterval(() => {
            if (boot() || ++tries > 20) clearInterval(timer);
        }, 100);
    });
})();
FARMS_EOF
    ok "farms.js rewritten"
fi

# ============================================================
# 6. Deduplicate renderNeedsSetup
# ============================================================
if [[ -f "$JS/dashboard.js" ]]; then
    info "Deduplicating dashboard.js"
    backup "$JS/dashboard.js"
    python3 - <<'PY'
import re, pathlib, sys
p = pathlib.Path("frontend/assets/js/dashboard.js")
src = p.read_text(encoding="utf-8")
matches = list(re.finditer(r"function\s+renderNeedsSetup\s*\(", src))
if len(matches) < 2:
    print("SKIP: no duplicate"); sys.exit(0)
start = matches[1].start()
next_fn = re.search(r"\n\s{4}function\s+\w+\s*\(", src[start:])
if not next_fn:
    print("SKIP: cannot find boundary"); sys.exit(1)
end = start + next_fn.start() + 1
src = src[:start] + src[end:]
p.write_text(src, encoding="utf-8")
print("REMOVED duplicate renderNeedsSetup")
PY
    ok "dashboard.js deduplicated"
fi

# ============================================================
# 7. UI guards
# ============================================================
info "Adding UI guards to page scripts"
for f in dashboard records planning finance decisions operations market weather pest learning profile; do
    file="$JS/$f.js"
    [[ -f "$file" ]] || continue
    grep -q "Marcbantu UI guard" "$file" && { info "  $f.js already guarded"; continue; }
    backup "$file"
    python3 - "$file" <<'PY'
import re, pathlib, sys
p = pathlib.Path(sys.argv[1])
src = p.read_text(encoding="utf-8")
guard = (
    "\n    // === Marcbantu UI guard ===\n"
    "    if (!window.UI) {\n"
    "        console.error('[%s] window.UI missing — app.js failed to load.');\n"
    "        return;\n"
    "    }\n"
    "    // === end guard ===\n"
) % p.name
m = re.search(r"(\s*if\s*\(\s*!window\.Auth\?\.requireLogin\(\)\s*\)\s*return\s*;?\s*\n)", src)
if not m:
    print(f"  SKIP: no anchor in {p.name}")
    sys.exit(0)
src = src[:m.end(1)] + guard + src[m.end(1):]
p.write_text(src, encoding="utf-8")
print(f"  GUARDED: {p.name}")
PY
done
ok "UI guards applied"

# ============================================================
# 8. manifest.json start_url
# ============================================================
if [[ -f "$FE/manifest.json" ]]; then
    info "Patching manifest.json"
    backup "$FE/manifest.json"
    python3 - <<'PY'
import json, pathlib
p = pathlib.Path("frontend/manifest.json")
data = json.loads(p.read_text(encoding="utf-8"))
data["start_url"] = "/?source=pwa"
data["scope"] = "/"
p.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
print("PATCHED: start_url")
PY
    ok "manifest.json updated"
fi

# ============================================================
# 9. api.js API_BASE
# ============================================================
if [[ -f "$JS/api.js" ]]; then
    info "Patching api.js API_BASE"
    backup "$JS/api.js"
    python3 - <<'PY'
import re, pathlib, sys
p = pathlib.Path("frontend/assets/js/api.js")
src = p.read_text(encoding="utf-8")
old = re.search(r"const\s+API_BASE\s*=\s*\(\(\)\s*=>\s*\{.*?\}\)\(\)\s*;", src, re.DOTALL)
if not old:
    print("SKIP: block not found"); sys.exit(0)
new_block = """const API_BASE = (() => {
    const meta = document.querySelector('meta[name="api-base"]');
    if (meta && meta.content) return meta.content.replace(/\\/$/, '');
    if (typeof window.__MARCBANTU_API_BASE__ === 'string') {
        return window.__MARCBANTU_API_BASE__.replace(/\\/$/, '');
    }
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') return 'http://localhost:8787';
    if (host.endsWith('marcbantuafrica.com')) return 'https://api.marcbantuafrica.com';
    return 'https://marcbantu-api.josuit-mwasi.workers.dev';
})();"""
src = src[:old.start()] + new_block + src[old.end():]
p.write_text(src, encoding="utf-8")
print("PATCHED: API_BASE")
PY
    ok "api.js patched"
fi

# ============================================================
# 10. Syntax check
# ============================================================
if command -v node >/dev/null 2>&1; then
    info "Syntax-checking JS"
    fail_count=0
    while IFS= read -r f; do
        node --check "$f" >/dev/null 2>&1 || { fail "  $f"; fail_count=$((fail_count+1)); }
    done < <(find "$JS" -name "*.js" -not -name "*.bak-*" 2>/dev/null)
    if [[ -f "$FE/sw.js" ]]; then
        node --check "$FE/sw.js" >/dev/null 2>&1 || { fail "  $FE/sw.js"; fail_count=$((fail_count+1)); }
    fi
    [[ $fail_count -eq 0 ]] && ok "All JS parses cleanly" || warn "$fail_count file(s) failed"
else
    warn "node not installed — skipping"
fi

echo
echo "========================================================"
ok "Done. Backups: *.bak-$STAMP"
echo "========================================================"
echo
echo "NEXT:"
echo "  1. Chrome DevTools → Application → Service Workers → Unregister all"
echo "  2. Storage → Clear site data"
echo "  3. Hard reload (Ctrl+Shift+R)"
echo "  4. Test /dashboard.html button"
echo
