-- ============================================================
-- MIGRATION 003 — MARKET PRICES, BUYERS, SALES, CONTRACTS
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- MARKET PRICES
-- ============================================================
CREATE TABLE IF NOT EXISTS market_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop TEXT NOT NULL,
    variety TEXT,
    market TEXT NOT NULL,
    county TEXT,
    country TEXT DEFAULT 'Kenya',
    price REAL NOT NULL,
    currency TEXT DEFAULT 'KES',
    unit TEXT DEFAULT 'kg',
    price_date TEXT NOT NULL,
    source TEXT,
    quality_grade TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_prices_crop ON market_prices(crop);
CREATE INDEX idx_prices_market ON market_prices(market);
CREATE INDEX idx_prices_date ON market_prices(price_date);
CREATE INDEX idx_prices_county ON market_prices(county);

-- ============================================================
-- BUYERS
-- ============================================================
CREATE TABLE IF NOT EXISTS buyers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT
        CHECK(type IS NULL OR type IN
            ('cooperative', 'processor', 'trader', 'retail', 'exporter', 'institution', 'other')),
    phone TEXT,
    email TEXT,
    location TEXT,
    county TEXT,
    country TEXT DEFAULT 'Kenya',
    rating REAL DEFAULT 0 CHECK(rating >= 0 AND rating <= 5),
    payment_terms TEXT,
    products_bought TEXT,
    notes TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_buyers_name ON buyers(name);
CREATE INDEX idx_buyers_type ON buyers(type);
CREATE INDEX idx_buyers_county ON buyers(county);

-- ============================================================
-- SALES
-- ============================================================
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    buyer_id INTEGER,
    enterprise_id INTEGER,
    record_id INTEGER,
    product TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT DEFAULT 'kg',
    unit_price REAL NOT NULL,
    total REAL NOT NULL,
    currency TEXT DEFAULT 'KES',
    payment_status TEXT DEFAULT 'pending'
        CHECK(payment_status IN ('pending', 'partial', 'paid', 'cancelled')),
    payment_method TEXT,
    amount_paid REAL DEFAULT 0,
    payment_date TEXT,
    sale_date TEXT NOT NULL,
    delivery_date TEXT,
    receipt_number TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (buyer_id) REFERENCES buyers(id) ON DELETE SET NULL,
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE SET NULL,
    FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE SET NULL
);

CREATE INDEX idx_sales_farm ON sales(farm_id);
CREATE INDEX idx_sales_buyer ON sales(buyer_id);
CREATE INDEX idx_sales_date ON sales(sale_date);
CREATE INDEX idx_sales_payment_status ON sales(payment_status);

-- ============================================================
-- CONTRACTS (forward agreements with buyers)
-- ============================================================
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    buyer_id INTEGER NOT NULL,
    enterprise_id INTEGER,
    product TEXT NOT NULL,
    quantity REAL,
    unit TEXT DEFAULT 'kg',
    price_per_unit REAL,
    currency TEXT DEFAULT 'KES',
    total_value REAL,
    delivery_start_date TEXT,
    delivery_end_date TEXT,
    delivery_location TEXT,
    payment_terms TEXT,
    status TEXT DEFAULT 'active'
        CHECK(status IN ('draft', 'active', 'fulfilled', 'cancelled', 'breached')),
    signed_date TEXT,
    document_url TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (buyer_id) REFERENCES buyers(id) ON DELETE CASCADE,
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE SET NULL
);

CREATE INDEX idx_contracts_farm ON contracts(farm_id);
CREATE INDEX idx_contracts_buyer ON contracts(buyer_id);
CREATE INDEX idx_contracts_status ON contracts(status);

-- ============================================================
-- PRICE ALERTS (farmer-set targets)
-- ============================================================
CREATE TABLE IF NOT EXISTS price_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    crop TEXT NOT NULL,
    target_price REAL NOT NULL,
    direction TEXT DEFAULT 'above'
        CHECK(direction IN ('above', 'below')),
    active INTEGER DEFAULT 1,
    triggered_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX idx_alerts_farmer ON price_alerts(farmer_id);
CREATE INDEX idx_alerts_crop ON price_alerts(crop);
CREATE INDEX idx_alerts_active ON price_alerts(active);