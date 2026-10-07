-- ============================================================
-- Migration 010: Real market intelligence
-- ============================================================
-- Master list of markets across Africa
CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    market_type TEXT DEFAULT 'retail',
    -- 'retail' | 'wholesale' | 'farmgate'
    county_or_region TEXT,
    country TEXT NOT NULL,
    country_code TEXT NOT NULL,
    -- ISO 3166-1 alpha-2
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    currency TEXT NOT NULL,
    -- KES, UGX, NGN, etc.
    timezone TEXT DEFAULT 'Africa/Nairobi',
    active INTEGER DEFAULT 1,
    data_source TEXT,
    -- 'KAMIS', 'FEWS NET', 'farmer'
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(name, country_code)
);
CREATE INDEX IF NOT EXISTS idx_markets_country ON markets(country_code, active);
CREATE INDEX IF NOT EXISTS idx_markets_latlon ON markets(latitude, longitude);
-- Master list of crops with categories and units
CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    -- 'staple' | 'cash' | 'livestock' | 'vegetable' | 'fruit' | 'other'
    default_unit TEXT NOT NULL,
    -- 'kg' | 'litre' | 'head' | 'dozen'
    aliases TEXT,
    -- JSON array: ["maize","corn","mahindi"]
    icon TEXT,
    -- Font Awesome class
    active INTEGER DEFAULT 1
);
-- ============================================================
-- Extend market_prices
-- ============================================================
ALTER TABLE market_prices
ADD COLUMN market_id INTEGER;
ALTER TABLE market_prices
ADD COLUMN country_code TEXT;
ALTER TABLE market_prices
ADD COLUMN currency TEXT DEFAULT 'KES';
ALTER TABLE market_prices
ADD COLUMN latitude REAL;
ALTER TABLE market_prices
ADD COLUMN longitude REAL;
ALTER TABLE market_prices
ADD COLUMN source TEXT DEFAULT 'manual';
ALTER TABLE market_prices
ADD COLUMN source_url TEXT;
ALTER TABLE market_prices
ADD COLUMN trend_7d_pct REAL;
ALTER TABLE market_prices
ADD COLUMN trend_30d_pct REAL;
ALTER TABLE market_prices
ADD COLUMN confidence TEXT DEFAULT 'medium';
-- 'high' | 'medium' | 'low'
CREATE INDEX IF NOT EXISTS idx_prices_crop_date ON market_prices(crop, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_market_date ON market_prices(market_id, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_geo ON market_prices(latitude, longitude);
-- ============================================================
-- Farmer-submitted prices
-- ============================================================
CREATE TABLE IF NOT EXISTS farmer_price_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    farm_id INTEGER,
    crop TEXT NOT NULL,
    market_id INTEGER,
    market_name TEXT,
    country_code TEXT NOT NULL,
    currency TEXT NOT NULL,
    price REAL NOT NULL,
    unit TEXT NOT NULL,
    quantity_available REAL,
    report_date TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    verified INTEGER DEFAULT 0,
    verified_by_count INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(farmer_id, crop, market_id, report_date)
);
CREATE INDEX IF NOT EXISTS idx_reports_crop_date ON farmer_price_reports(crop, report_date DESC);
CREATE INDEX IF NOT EXISTS idx_reports_country ON farmer_price_reports(country_code, verified);