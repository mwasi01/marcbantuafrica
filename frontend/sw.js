/**
 * Marcbantu Africa — Service Worker (v4).
 * At /sw.js so scope covers whole origin.
 */
const CACHE_NAME     = 'marcbantu-v4';
const API_CACHE_NAME = 'marcbantu-api-v4';

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
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);

    const net = fetch(request)
        .then((res) => {
            if (res && res.ok) {
                cache.put(request, res.clone());
            }
            return res;
        })
        .catch((err) => {
            // Don't log navigation fetches that fail — they're expected
            // for /dashboard style URLs that don't have a matching file.
            if (request.mode !== 'navigate') {
                console.warn('[SW] fetch failed:', request.url, err.message);
            }
            return null;
        });

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