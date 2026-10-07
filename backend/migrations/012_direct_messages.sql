-- ============================================================
-- Migration 012 — Direct Messages (farmer-to-farmer)
-- ============================================================

-- A conversation is between two farmers
-- We store them normalized so farmer_a < farmer_b to avoid duplicates
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_a INTEGER NOT NULL,
    farmer_b INTEGER NOT NULL,
    last_message_id INTEGER,
    last_message_at TEXT,
    unread_count_a INTEGER DEFAULT 0,
    unread_count_b INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_a) REFERENCES farmers(id) ON DELETE CASCADE,
    FOREIGN KEY (farmer_b) REFERENCES farmers(id) ON DELETE CASCADE,
    UNIQUE(farmer_a, farmer_b),
    CHECK(farmer_a < farmer_b)
);

CREATE INDEX IF NOT EXISTS idx_conversations_a ON conversations(farmer_a);
CREATE INDEX IF NOT EXISTS idx_conversations_b ON conversations(farmer_b);
CREATE INDEX IF NOT EXISTS idx_conversations_last ON conversations(last_message_at DESC);

-- Individual messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    message_type TEXT DEFAULT 'text' CHECK(message_type IN ('text', 'image', 'file')),
    media_url TEXT,
    read_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(conversation_id, read_at);
