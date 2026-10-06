-- ============================================================
-- MIGRATION 001 — INITIAL SCHEMA
-- Core tables: farmers, farms, enterprises, records, transactions
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- FARMERS (users)
-- ============================================================
CREATE TABLE IF NOT EXISTS farmers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    country TEXT DEFAULT 'Kenya',
    county TEXT,
    location TEXT,
    language TEXT DEFAULT 'en',
    profile_photo_url TEXT,
    subscription_tier TEXT DEFAULT 'starter'
        CHECK(subscription_tier IN ('starter', 'pro', 'business')),
    subscription_expires_at TEXT,
    verified INTEGER DEFAULT 0,
    verified_at TEXT,
    last_login_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_farmers_phone ON farmers(phone);
CREATE INDEX idx_farmers_email ON farmers(email);
CREATE INDEX idx_farmers_county ON farmers(county);
CREATE INDEX idx_farmers_tier ON farmers(subscription_tier);

-- ============================================================
-- FARMS
-- ============================================================
CREATE TABLE IF NOT EXISTS farms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    size_acres REAL,
    latitude REAL,
    longitude REAL,
    altitude_m REAL,
    soil_type TEXT,
    irrigation_type TEXT
        CHECK(irrigation_type IS NULL OR irrigation_type IN
            ('rain-fed', 'drip', 'sprinkler', 'furrow', 'borehole', 'other')),
    water_source TEXT,
    notes TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX idx_farms_farmer ON farms(farmer_id);
CREATE INDEX idx_farms_active ON farms(active);

-- ============================================================
-- ENTERPRISES (crops, livestock, poultry, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS enterprises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL
        CHECK(type IN ('crop', 'livestock', 'poultry', 'horticulture', 'aquaculture', 'mixed', 'other')),
    species_or_crop TEXT,
    quantity REAL,
    unit TEXT,
    start_date TEXT,
    expected_end_date TEXT,
    status TEXT DEFAULT 'active'
        CHECK(status IN ('planning', 'active', 'harvested', 'sold', 'closed')),
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE
);

CREATE INDEX idx_enterprises_farm ON enterprises(farm_id);
CREATE INDEX idx_enterprises_status ON enterprises(status);
CREATE INDEX idx_enterprises_type ON enterprises(type);

-- ============================================================
-- RECORDS (unified farm activity log)
-- ============================================================
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    enterprise_id INTEGER,
    record_type TEXT NOT NULL
        CHECK(record_type IN
            ('crop_activity', 'livestock', 'poultry', 'input', 'harvest', 'sale', 'expense', 'observation', 'other')),
    activity TEXT,
    description TEXT,
    quantity REAL,
    unit TEXT,
    cost REAL DEFAULT 0,
    revenue REAL DEFAULT 0,
    record_date TEXT NOT NULL,
    notes TEXT,
    photo_url TEXT,
    latitude REAL,
    longitude REAL,
    weather_conditions TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES farmers(id) ON DELETE SET NULL
);

CREATE INDEX idx_records_farm ON records(farm_id);
CREATE INDEX idx_records_enterprise ON records(enterprise_id);
CREATE INDEX idx_records_date ON records(record_date);
CREATE INDEX idx_records_type ON records(record_type);
CREATE INDEX idx_records_activity ON records(activity);

-- ============================================================
-- TRANSACTIONS (financial ledger)
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    enterprise_id INTEGER,
    record_id INTEGER,
    type TEXT NOT NULL
        CHECK(type IN ('income', 'expense')),
    category TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL CHECK(amount >= 0),
    currency TEXT DEFAULT 'KES',
    payment_method TEXT
        CHECK(payment_method IS NULL OR payment_method IN
            ('cash', 'mpesa', 'airtel', 'bank', 'cheque', 'credit', 'other')),
    reference TEXT,
    transaction_date TEXT NOT NULL,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE SET NULL,
    FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES farmers(id) ON DELETE SET NULL
);

CREATE INDEX idx_transactions_farm ON transactions(farm_id);
CREATE INDEX idx_transactions_enterprise ON transactions(enterprise_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_transactions_type ON transactions(type);
CREATE INDEX idx_transactions_category ON transactions(category);