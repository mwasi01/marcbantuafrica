-- ============================================================
-- MIGRATION 007 — AUDIT, SESSIONS, CACHE, CONFIG
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- AUDIT LOG (who did what, when)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER,
    action TEXT NOT NULL,
    entity TEXT,
    entity_id INTEGER,
    details TEXT,
    ip_address TEXT,
    user_agent TEXT,
    channel TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_audit_farmer ON audit_log(farmer_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_entity ON audit_log(entity, entity_id);
CREATE INDEX idx_audit_created ON audit_log(created_at);

-- ============================================================
-- ACTIVE SESSIONS (server-side session tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    farmer_id INTEGER NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    device TEXT,
    channel TEXT DEFAULT 'web',
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    last_active_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_farmer ON sessions(farmer_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- ============================================================
-- WEATHER CACHE (per location)
-- ============================================================
CREATE TABLE IF NOT EXISTS weather_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    location_name TEXT,
    forecast_date TEXT NOT NULL,
    data TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    UNIQUE(latitude, longitude, forecast_date)
);

CREATE INDEX idx_weather_loc ON weather_cache(latitude, longitude);
CREATE INDEX idx_weather_date ON weather_cache(forecast_date);

-- ============================================================
-- SYSTEM CONFIG (feature flags, settings)
-- ============================================================
CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    type TEXT DEFAULT 'string'
        CHECK(type IN ('string', 'number', 'boolean', 'json')),
    description TEXT,
    category TEXT,
    public INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_config_key ON system_config(key);
CREATE INDEX idx_config_cat ON system_config(category);

-- ============================================================
-- FILE UPLOADS (R2 metadata)
-- ============================================================
CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER,
    farm_id INTEGER,
    entity TEXT,
    entity_id INTEGER,
    file_key TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT,
    file_size INTEGER,
    mime_type TEXT,
    url TEXT,
    thumbnail_url TEXT,
    metadata TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE SET NULL,
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE SET NULL
);

CREATE INDEX idx_uploads_farmer ON uploads(farmer_id);
CREATE INDEX idx_uploads_farm ON uploads(farm_id);
CREATE INDEX idx_uploads_entity ON uploads(entity, entity_id);

-- ============================================================
-- API KEYS (for partners)
-- ============================================================
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    key_hash TEXT UNIQUE NOT NULL,
    partner_name TEXT,
    scopes TEXT,
    rate_limit_per_day INTEGER DEFAULT 1000,
    active INTEGER DEFAULT 1,
    expires_at TEXT,
    last_used_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(active);

-- ============================================================
-- RATE LIMIT LOG (lightweight tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS rate_limit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    window_start TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    UNIQUE(identifier, endpoint, window_start)
);

CREATE INDEX idx_rate_identifier ON rate_limit_log(identifier);
CREATE INDEX idx_rate_window ON rate_limit_log(window_start);

-- ============================================================
-- SYSTEM METRICS (for observability)
-- ============================================================
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    tags TEXT,
    recorded_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_metrics_name ON system_metrics(metric);
CREATE INDEX idx_metrics_date ON system_metrics(recorded_at);

-- ============================================================
-- MIGRATION TRACKING (applied migrations)
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    applied_at TEXT DEFAULT (datetime('now'))
);