/**
 * Marcbantu Africa — register the service worker.
 */
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then((reg) => console.log('[SW] registered', reg.scope))
            .catch((err) => console.warn('[SW] registration failed', err));
    });
}
