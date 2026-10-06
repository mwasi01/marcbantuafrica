/**
 * Marcbantu Africa — Offline support.
 * Stores records in IndexedDB when offline; flushes to server when online.
 */

(function () {
    'use strict';

    const DB_NAME = 'marcbantu-offline';
    const DB_VERSION = 1;
    const STORE = 'pending_records';

    let dbPromise = null;

    function openDB() {
        if (dbPromise) return dbPromise;
        dbPromise = new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE)) {
                    const store = db.createObjectStore(STORE, { keyPath: 'client_id' });
                    store.createIndex('created_at', 'created_at');
                }
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
        return dbPromise;
    }

    async function addPending(record) {
        const db = await openDB();
        const tx = db.transaction(STORE, 'readwrite');
        const store = tx.objectStore(STORE);
        const client_id = record.client_id || `off-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const item = { ...record, client_id, created_at: new Date().toISOString() };
        store.put(item);
        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve(item);
            tx.onerror = () => reject(tx.error);
        });
    }

    async function getAllPending() {
        const db = await openDB();
        const tx = db.transaction(STORE, 'readonly');
        const store = tx.objectStore(STORE);
        const req = store.getAll();
        return new Promise((resolve, reject) => {
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject(req.error);
        });
    }

    async function removePending(client_id) {
        const db = await openDB();
        const tx = db.transaction(STORE, 'readwrite');
        tx.objectStore(STORE).delete(client_id);
        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    async function countPending() {
        const db = await openDB();
        const tx = db.transaction(STORE, 'readonly');
        const store = tx.objectStore(STORE);
        const req = store.count();
        return new Promise((resolve, reject) => {
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function clearAll() {
        const db = await openDB();
        const tx = db.transaction(STORE, 'readwrite');
        tx.objectStore(STORE).clear();
        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    // ============================================================
    // FLUSH
    // ============================================================
    async function flush() {
        if (!navigator.onLine) return;
        if (!window.Auth?.isLoggedIn()) return;

        const pending = await getAllPending();
        if (!pending.length) return;

        console.log(`[Offline] Flushing ${pending.length} pending records`);

        // Send in chunks of 100
        const chunks = [];
        for (let i = 0; i < pending.length; i += 100) {
            chunks.push(pending.slice(i, i + 100));
        }

        for (const chunk of chunks) {
            const result = await Api.syncOffline(chunk, 'pwa');
            if (!result.ok) {
                console.warn('[Offline] Sync failed:', result.error);
                return;
            }

            // Remove synced records
            if (result.data?.queued) {
                // Job will handle; remove all in this chunk optimistically
                for (const record of chunk) {
                    await removePending(record.client_id);
                }
            }
        }

        window.Toast?.success(`${pending.length} offline records synced!`);
    }

    // ============================================================
    // WRAPPED API CALLS
    // ============================================================
    async function createRecordWithOffline(record) {
        if (navigator.onLine) {
            const result = await Api.createRecord(record);
            if (result.ok) return result;
            // If network error, fall through to offline
            if (result.code !== 'NETWORK_ERROR' && result.status !== 0) {
                return result;
            }
        }

        // Offline: store and return optimistic success
        const pending = await addPending(record);
        window.Toast?.info('Saved offline. Will sync when online.');
        return {
            ok: true,
            offline: true,
            data: { ...pending, _offline: true },
        };
    }

    // ============================================================
    // AUTO-FLUSH ON RECONNECT
    // ============================================================
    window.addEventListener('online', () => {
        setTimeout(flush, 1000);
    });

    // Also flush on page load if online and logged in
    document.addEventListener('DOMContentLoaded', () => {
        if (navigator.onLine && window.Auth?.isLoggedIn()) {
            setTimeout(flush, 2000);
        }
    });

    // Periodic flush every 5 min
    setInterval(() => {
        if (navigator.onLine && window.Auth?.isLoggedIn()) {
            flush();
        }
    }, 5 * 60 * 1000);

    // ============================================================
    // EXPORTS
    // ============================================================
    window.OfflineSync = {
        addPending,
        getAllPending,
        removePending,
        countPending,
        clearAll,
        flush,
        createRecordWithOffline,
    };
})();