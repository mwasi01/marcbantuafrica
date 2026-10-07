-- ============================================================
-- Migration 014 — Permanently fix notifications.type constraint
-- ============================================================
-- Previous migration 013 was non-idempotent: re-running it
-- restored the old CHECK constraint. This version:
--   1. Drops any stale notifications_new table
--   2. Creates notifications_new with the final schema
--   3. Copies data
--   4. Drops old + renames
--   5. Adds indexes
-- ============================================================

PRAGMA foreign_keys = OFF;

-- 1. Cleanup any leftover staging table
DROP TABLE IF EXISTS notifications_new;

-- 2. Build the correct table
CREATE TABLE notifications_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN (
        'weather', 'market', 'reminder', 'alert', 'system',
        'finance', 'pest', 'learning', 'message', 'social'
    )),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    action_url TEXT,
    priority TEXT DEFAULT 'normal' CHECK(priority IN ('low', 'normal', 'high', 'urgent')),
    read_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

-- 3. Copy data (drop any rows with invalid types — shouldn't happen)
INSERT INTO notifications_new
    (id, farmer_id, type, title, message, action_url, priority, read_at, created_at)
SELECT id, farmer_id, type, title, message, action_url, priority, read_at, created_at
FROM notifications
WHERE type IN ('weather', 'market', 'reminder', 'alert', 'system', 'finance', 'pest', 'learning', 'message', 'social');

-- 4. Swap tables
DROP TABLE notifications;
ALTER TABLE notifications_new RENAME TO notifications;

-- 5. Rebuild indexes
CREATE INDEX IF NOT EXISTS idx_notifications_farmer ON notifications(farmer_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(farmer_id, read_at);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);

PRAGMA foreign_keys = ON;
