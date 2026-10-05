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
