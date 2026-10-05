/**
 * Marcbantu Africa — Service Worker.
 * Cache-first for static assets; network-first for API calls.
 */

const CACHE_NAME = 'marcbantu-v1';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/login.html',
    '/register.html',
    '/dashboard.html',
    '/records.html',
    '/planning.html',
    '/finance.html',
    '/decisions.html',
    '/operations.html',
    '/market.html',
    '/weather.html',
    '/pest.html',
    '/learning.html',
    '/profile.html',
    '/assets/css/main.css',
    '/assets/js/api.js',
    '/assets/js/app.js',
    '/assets/js/auth.js',
    '/assets/js/dashboard.js',
    '/assets/js/records.js',
    '/assets/js/offline.js',
];

// ============================================================
// INSTALL
// ============================================================
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch((err) => {
                console.warn('[SW] Precache failed for some assets:', err);
            });
        })
    );
    self.skipWaiting();
});

// ============================================================
// ACTIVATE
// ============================================================
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
            );
        })
    );
    self.clients.claim();
});

// ============================================================
// FETCH
// ============================================================
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') return;

    // Skip cross-origin
    if (url.origin !== location.origin) return;

    // API requests: network-first
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirst(request));
        return;
    }

    // Static assets: cache-first
    event.respondWith(cacheFirst(request));
});

// ============================================================
// STRATEGIES
// ============================================================
async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        // Fallback for navigation requests
        if (request.mode === 'navigate') {
            const offline = await caches.match('/index.html');
            if (offline) return offline;
        }
        throw err;
    }
}

async function networkFirst(request) {
    try {
        const response = await fetch(request);
        // Don't cache API responses (they're dynamic)
        return response;
    } catch (err) {
        // Return cached if available (rare for API)
        const cached = await caches.match(request);
        if (cached) return cached;
        // Return a JSON error
        return new Response(
            JSON.stringify({ error: 'Offline', offline: true }),
            { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
    }
}

// ============================================================
// MESSAGE HANDLER
// ============================================================
self.addEventListener('message', (event) => {
    if (event.data?.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});