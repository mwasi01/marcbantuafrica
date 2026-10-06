-- ============================================================
-- MIGRATION 004 — PEST & DISEASE MANAGEMENT
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- PEST SCOUTING (field observations)
-- ============================================================
CREATE TABLE IF NOT EXISTS pest_scouting (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    plot_id INTEGER,
    enterprise_id INTEGER,
    pest_name TEXT NOT NULL,
    pest_type TEXT
        CHECK(pest_type IS NULL OR pest_type IN
            ('insect', 'fungus', 'bacteria', 'virus', 'weed', 'rodent', 'bird', 'nematode', 'other')),
    severity TEXT DEFAULT 'low'
        CHECK(severity IN ('low', 'medium', 'high', 'critical')),
    affected_area_pct REAL,
    photo_url TEXT,
    symptoms TEXT,
    scout_date TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    weather_conditions TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (plot_id) REFERENCES plots(id) ON DELETE SET NULL,
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE SET NULL
);

CREATE INDEX idx_scouting_farm ON pest_scouting(farm_id);
CREATE INDEX idx_scouting_plot ON pest_scouting(plot_id);
CREATE INDEX idx_scouting_date ON pest_scouting(scout_date);
CREATE INDEX idx_scouting_severity ON pest_scouting(severity);

-- ============================================================
-- PEST & DISEASE LIBRARY (reference database)
-- ============================================================
CREATE TABLE IF NOT EXISTS pest_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    scientific_name TEXT,
    type TEXT
        CHECK(type IN ('insect', 'fungus', 'bacteria', 'virus', 'weed', 'rodent', 'bird', 'nematode', 'other')),
    affected_crops TEXT,
    symptoms TEXT,
    causes TEXT,
    treatment_organic TEXT,
    treatment_chemical TEXT,
    prevention TEXT,
    image_url TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_pest_lib_name ON pest_library(name);
CREATE INDEX idx_pest_lib_type ON pest_library(type);

-- ============================================================
-- TREATMENTS (chemical applications)
-- ============================================================
CREATE TABLE IF NOT EXISTS treatments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    plot_id INTEGER,
    enterprise_id INTEGER,
    pest_scouting_id INTEGER,
    product TEXT NOT NULL,
    product_type TEXT
        CHECK(product_type IS NULL OR product_type IN
            ('pesticide', 'herbicide', 'fungicide', 'insecticide', 'organic', 'biological', 'other')),
    active_ingredient TEXT,
    rate TEXT,
    quantity_used REAL,
    unit TEXT,
    total_cost REAL,
    target_pest TEXT,
    application_method TEXT,
    application_date TEXT NOT NULL,
    applied_by TEXT,
    weather_conditions TEXT,
    re_entry_interval_hours INTEGER,
    pre_harvest_interval_days INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (plot_id) REFERENCES plots(id) ON DELETE SET NULL,
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE SET NULL,
    FOREIGN KEY (pest_scouting_id) REFERENCES pest_scouting(id) ON DELETE SET NULL
);

CREATE INDEX idx_treatments_farm ON treatments(farm_id);
CREATE INDEX idx_treatments_plot ON treatments(plot_id);
CREATE INDEX idx_treatments_date ON treatments(application_date);
CREATE INDEX idx_treatments_product ON treatments(product);

-- ============================================================
-- CHEMICAL INVENTORY (track chemical stock)
-- ============================================================
CREATE TABLE IF NOT EXISTS chemical_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    active_ingredient TEXT,
    category TEXT,
    quantity_in_stock REAL,
    unit TEXT,
    purchase_date TEXT,
    purchase_cost REAL,
    expiry_date TEXT,
    storage_location TEXT,
    safety_notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE
);

CREATE INDEX idx_chem_inv_farm ON chemical_inventory(farm_id);
CREATE INDEX idx_chem_inv_expiry ON chemical_inventory(expiry_date);

-- ============================================================
-- IPM PRACTICES (Integrated Pest Management log)
-- ============================================================
CREATE TABLE IF NOT EXISTS ipm_practices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    plot_id INTEGER,
    practice_type TEXT
        CHECK(practice_type IN
            ('crop_rotation', 'intercropping', 'biological_control', 'sanitation', 'trap_crop', 'mulching', 'companion_planting', 'other')),
    description TEXT,
    applied_date TEXT NOT NULL,
    effectiveness TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (plot_id) REFERENCES plots(id) ON DELETE SET NULL
);

CREATE INDEX idx_ipm_farm ON ipm_practices(farm_id);
CREATE INDEX idx_ipm_date ON ipm_practices(applied_date);