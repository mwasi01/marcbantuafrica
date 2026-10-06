-- ============================================================
-- MIGRATION 006 — COMMUNICATIONS & NOTIFICATIONS
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- COMMUNICATION LOG (all channels)
-- ============================================================
CREATE TABLE IF NOT EXISTS communication_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER,
    channel TEXT NOT NULL
        CHECK(channel IN ('sms', 'ussd', 'whatsapp', 'voice', 'email', 'push')),
    direction TEXT NOT NULL
        CHECK(direction IN ('inbound', 'outbound')),
    phone TEXT,
    email TEXT,
    message TEXT,
    status TEXT DEFAULT 'sent'
        CHECK(status IN ('queued', 'sent', 'delivered', 'failed', 'received', 'read')),
    cost REAL DEFAULT 0,
    currency TEXT DEFAULT 'KES',
    reference TEXT,
    external_id TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_comm_farmer ON communication_log(farmer_id);
CREATE INDEX idx_comm_channel ON communication_log(channel);
CREATE INDEX idx_comm_created ON communication_log(created_at);
CREATE INDEX idx_comm_status ON communication_log(status);

-- ============================================================
-- SMS TEMPLATES
-- ============================================================
CREATE TABLE IF NOT EXISTS sms_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    body TEXT NOT NULL,
    variables TEXT,
    language TEXT DEFAULT 'en',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_sms_tpl_code ON sms_templates(code);

-- ============================================================
-- USSD SESSIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS ussd_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    farmer_id INTEGER,
    current_menu TEXT,
    state TEXT,
    data TEXT,
    started_at TEXT DEFAULT (datetime('now')),
    ended_at TEXT,
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE SET NULL
);

CREATE INDEX idx_ussd_phone ON ussd_sessions(phone);
CREATE INDEX idx_ussd_started ON ussd_sessions(started_at);

-- ============================================================
-- USSD MENUS (configurable)
-- ============================================================
CREATE TABLE IF NOT EXISTS ussd_menus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    options TEXT,
    parent_code TEXT,
    is_terminal INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_ussd_menu_code ON ussd_menus(code);

-- ============================================================
-- NOTIFICATIONS (in-app)
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    type TEXT NOT NULL
        CHECK(type IN ('weather', 'market', 'reminder', 'alert', 'system', 'finance', 'pest', 'learning')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    action_url TEXT,
    icon TEXT,
    priority TEXT DEFAULT 'normal'
        CHECK(priority IN ('low', 'normal', 'high', 'urgent')),
    read INTEGER DEFAULT 0,
    read_at TEXT,
    expires_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX idx_notif_farmer ON notifications(farmer_id);
CREATE INDEX idx_notif_read ON notifications(read);
CREATE INDEX idx_notif_created ON notifications(created_at);
CREATE INDEX idx_notif_type ON notifications(type);

-- ============================================================
-- DEVICE TOKENS (for push notifications)
-- ============================================================
CREATE TABLE IF NOT EXISTS device_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    platform TEXT
        CHECK(platform IN ('web', 'android', 'ios')),
    user_agent TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_used_at TEXT,
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX idx_tokens_farmer ON device_tokens(farmer_id);

-- ============================================================
-- MESSAGE QUEUE (for scheduled / bulk sends)
-- ============================================================
CREATE TABLE IF NOT EXISTS message_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    template_code TEXT,
    body TEXT NOT NULL,
    scheduled_for TEXT,
    priority INTEGER DEFAULT 5,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    status TEXT DEFAULT 'pending'
        CHECK(status IN ('pending', 'processing', 'sent', 'failed', 'cancelled')),
    error_message TEXT,
    sent_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE SET NULL
);

CREATE INDEX idx_msgq_status ON message_queue(status);
CREATE INDEX idx_msgq_scheduled ON message_queue(scheduled_for);
CREATE INDEX idx_msgq_priority ON message_queue(priority);

-- ============================================================
-- WHATSAPP TEMPLATES (pre-approved Meta templates)
-- ============================================================
CREATE TABLE IF NOT EXISTS whatsapp_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    language TEXT DEFAULT 'en',
    category TEXT,
    body TEXT NOT NULL,
    variables TEXT,
    meta_template_id TEXT,
    approved INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);