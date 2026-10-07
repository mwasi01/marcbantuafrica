PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS notifications_new (
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

INSERT OR IGNORE INTO notifications_new
    (id, farmer_id, type, title, message, action_url, priority, read_at, created_at)
SELECT id, farmer_id, type, title, message, action_url, priority, read_at, created_at
FROM notifications;

DROP TABLE notifications;
ALTER TABLE notifications_new RENAME TO notifications;

CREATE INDEX IF NOT EXISTS idx_notifications_farmer ON notifications(farmer_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(farmer_id, read_at);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);

PRAGMA foreign_keys = ON;
