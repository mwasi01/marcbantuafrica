-- ============================================================
-- Migration 010: Real market intelligence (v2)
-- ============================================================
-- Assumes base tables exist:
--   crops, markets, market_prices, farmer_price_reports
-- This migration:
--   1. Creates markets + crops if not present
--   2. Extends market_prices with geo / source / trend columns
--   3. Adds UNIQUE constraint for upserts
--   4. Adds alias + unmatched-name tables
--   5. Seeds 100 crops (idempotent)
--   6. Seeds ~500 markets across 50 African countries (idempotent)
--
-- NOTE: SQLite does not support ADD COLUMN IF NOT EXISTS.
--       Column ALTERs are wrapped in a Python migration runner
--       (see migration_runner.py) that checks PRAGMA table_info
--       before applying. Running this file raw twice WILL error
--       on the ALTER TABLE section — that is expected.
-- ============================================================
PRAGMA foreign_keys = ON;
-- ============================================================
-- 1. MASTER TABLES
-- ============================================================
CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    market_type TEXT DEFAULT 'retail' CHECK (market_type IN ('retail', 'wholesale', 'farmgate')),
    county_or_region TEXT,
    country TEXT NOT NULL,
    country_code TEXT NOT NULL,
    -- ISO 3166-1 alpha-2
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    currency TEXT NOT NULL,
    timezone TEXT DEFAULT 'Africa/Nairobi',
    active INTEGER DEFAULT 1,
    data_source TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(name, country_code)
);
CREATE INDEX IF NOT EXISTS idx_markets_country ON markets(country_code, active);
CREATE INDEX IF NOT EXISTS idx_markets_latlon ON markets(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_markets_active ON markets(active);
CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK (
        category IN (
            'staple',
            'cash',
            'livestock',
            'vegetable',
            'fruit',
            'other'
        )
    ),
    default_unit TEXT NOT NULL,
    aliases TEXT,
    -- JSON array
    icon TEXT,
    -- Font Awesome class
    active INTEGER DEFAULT 1
);
-- ============================================================
-- 2. EXTEND market_prices
-- ============================================================
-- Assumes market_prices already has: id, crop, market, price, unit, price_date
-- The ALTERs below are non-idempotent in raw SQLite — run via migration_runner.
ALTER TABLE market_prices
ADD COLUMN market_id INTEGER;
ALTER TABLE market_prices
ADD COLUMN county TEXT;
ALTER TABLE market_prices
ADD COLUMN country TEXT;
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
ADD COLUMN confidence TEXT DEFAULT 'medium';
ALTER TABLE market_prices
ADD COLUMN trend_7d_pct REAL;
ALTER TABLE market_prices
ADD COLUMN trend_30d_pct REAL;
ALTER TABLE market_prices
ADD COLUMN fetched_at TEXT;
-- ============================================================
-- 3. UPSERT TARGET + INDEXES
-- ============================================================
-- The UNIQUE index is what allows:
--   INSERT ... ON CONFLICT(crop, market_id, price_date, source) DO UPDATE
-- in market_intelligence.ingest_all().
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_prices_unique ON market_prices (crop, market_id, price_date, source);
CREATE INDEX IF NOT EXISTS idx_prices_crop_date ON market_prices (crop, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_market_date ON market_prices (market_id, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_geo ON market_prices (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_prices_crop_market_date ON market_prices (crop, market_id, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_country_date ON market_prices (country_code, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_source ON market_prices (source);
CREATE INDEX IF NOT EXISTS idx_prices_fetched_at ON market_prices (fetched_at DESC);
-- ============================================================
-- 4. MARKET ALIASES (fuzzy-join fallback)
-- ============================================================
CREATE TABLE IF NOT EXISTS market_aliases (
    alias TEXT NOT NULL,
    market_id INTEGER NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    source TEXT,
    confidence TEXT DEFAULT 'medium' CHECK (confidence IN ('high', 'medium', 'low')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (alias, market_id)
);
CREATE INDEX IF NOT EXISTS idx_market_aliases_alias ON market_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_market_aliases_market ON market_aliases(market_id);
-- ============================================================
-- 5. UNMATCHED MARKET NAMES (ingest diagnostics)
-- ============================================================
-- Populated by ingest_all() whenever match_market() returns None.
-- Reviewed weekly → promoted into market_aliases.
CREATE TABLE IF NOT EXISTS unmatched_market_names (
    raw_name TEXT NOT NULL,
    country_code TEXT,
    source TEXT,
    occurrences INTEGER DEFAULT 1,
    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (raw_name, country_code, source)
);
CREATE INDEX IF NOT EXISTS idx_unmatched_occurrences ON unmatched_market_names(occurrences DESC);
-- ============================================================
-- 6. FARMER-SUBMITTED PRICES
-- ============================================================
CREATE TABLE IF NOT EXISTS farmer_price_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    farm_id INTEGER,
    crop TEXT NOT NULL,
    market_id INTEGER REFERENCES markets(id),
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
CREATE INDEX IF NOT EXISTS idx_reports_market ON farmer_price_reports(market_id, report_date DESC);
-- ============================================================
-- 7. SEED: 100 CROPS
-- ============================================================
INSERT
    OR IGNORE INTO crops (name, category, default_unit, aliases, icon)
VALUES -- Staples
    (
        'Maize',
        'staple',
        'kg',
        '["corn","mahindi","mais"]',
        'fa-seedling'
    ),
    (
        'Beans',
        'staple',
        'kg',
        '["maharagwe","haricot"]',
        'fa-seedling'
    ),
    (
        'Rice',
        'staple',
        'kg',
        '["mchele","paddy"]',
        'fa-wheat-awn'
    ),
    (
        'Wheat',
        'staple',
        'kg',
        '["ngano","triticum"]',
        'fa-wheat-awn'
    ),
    (
        'Cassava',
        'staple',
        'kg',
        '["muhogo","manioc","yuca"]',
        'fa-carrot'
    ),
    (
        'Sorghum',
        'staple',
        'kg',
        '["mtama","durra"]',
        'fa-wheat-awn'
    ),
    (
        'Millet',
        'staple',
        'kg',
        '["mtama","bajra"]',
        'fa-wheat-awn'
    ),
    (
        'Finger Millet',
        'staple',
        'kg',
        '["wimbi","ragi","eleusine"]',
        'fa-wheat-awn'
    ),
    (
        'Sweet Potato',
        'staple',
        'kg',
        '["viazi vitamu","kumara"]',
        'fa-carrot'
    ),
    (
        'Irish Potato',
        'staple',
        'kg',
        '["viazi","waru","potato"]',
        'fa-carrot'
    ),
    (
        'Yam',
        'staple',
        'kg',
        '["viazi vikuu","nyama"]',
        'fa-carrot'
    ),
    (
        'Plantain',
        'staple',
        'kg',
        '["gonja","ndizi"]',
        'fa-carrot'
    ),
    (
        'Cowpeas',
        'staple',
        'kg',
        '["kunde","black-eyed peas"]',
        'fa-seedling'
    ),
    (
        'Pigeon Peas',
        'staple',
        'kg',
        '["mbaazi"]',
        'fa-seedling'
    ),
    (
        'Green Grams',
        'staple',
        'kg',
        '["ndengu","mung beans"]',
        'fa-seedling'
    ),
    (
        'Groundnuts',
        'staple',
        'kg',
        '["njugu","peanuts"]',
        'fa-seedling'
    ),
    (
        'Sesame',
        'staple',
        'kg',
        '["simsim","benne"]',
        'fa-seedling'
    ),
    (
        'Teff',
        'staple',
        'kg',
        '["tef","dagi"]',
        'fa-wheat-awn'
    ),
    (
        'Barley',
        'staple',
        'kg',
        '["shairi"]',
        'fa-wheat-awn'
    ),
    (
        'Oats',
        'staple',
        'kg',
        '["jai"]',
        'fa-wheat-awn'
    ),
    -- Cash crops
    (
        'Coffee (Arabica)',
        'cash',
        'kg',
        '["kahawa","arabica"]',
        'fa-mug-hot'
    ),
    (
        'Coffee (Robusta)',
        'cash',
        'kg',
        '["kahawa","robusta"]',
        'fa-mug-hot'
    ),
    (
        'Tea',
        'cash',
        'kg',
        '["chai","camellia"]',
        'fa-leaf'
    ),
    (
        'Cocoa',
        'cash',
        'kg',
        '["kakao","cacao"]',
        'fa-cookie'
    ),
    (
        'Cotton',
        'cash',
        'kg',
        '["pamba","cotton lint"]',
        'fa-tshirt'
    ),
    (
        'Tobacco',
        'cash',
        'kg',
        '["tumbaku"]',
        'fa-leaf'
    ),
    (
        'Sugarcane',
        'cash',
        'kg',
        '["miwa","cane"]',
        'fa-cubes-stacked'
    ),
    (
        'Pyrethrum',
        'cash',
        'kg',
        '["pyrethrum"]',
        'fa-leaf'
    ),
    (
        'Sisal',
        'cash',
        'kg',
        '["sisal","katani"]',
        'fa-leaf'
    ),
    (
        'Cashew Nuts',
        'cash',
        'kg',
        '["korosho","cashew"]',
        'fa-seedling'
    ),
    (
        'Macadamia',
        'cash',
        'kg',
        '["macadamia"]',
        'fa-seedling'
    ),
    (
        'Avocado',
        'cash',
        'kg',
        '["parachichi","avocado"]',
        'fa-seedling'
    ),
    (
        'Coconut',
        'cash',
        'head',
        '["nazi","coconut"]',
        'fa-seedling'
    ),
    (
        'Palm Oil',
        'cash',
        'litre',
        '["mafuta ya mawese","palm"]',
        'fa-droplet'
    ),
    -- Livestock
    (
        'Cattle',
        'livestock',
        'head',
        '["ngombe","cows","bulls"]',
        'fa-cow'
    ),
    (
        'Goats',
        'livestock',
        'head',
        '["mbuzi","goat"]',
        'fa-cow'
    ),
    (
        'Sheep',
        'livestock',
        'head',
        '["kondoo","sheep"]',
        'fa-cow'
    ),
    (
        'Pigs',
        'livestock',
        'head',
        '["nguruwe","pig"]',
        'fa-piggy-bank'
    ),
    (
        'Camels',
        'livestock',
        'head',
        '["ngamia","camel"]',
        'fa-cow'
    ),
    (
        'Donkeys',
        'livestock',
        'head',
        '["punda","donkey"]',
        'fa-cow'
    ),
    (
        'Rabbits',
        'livestock',
        'head',
        '["sungura","rabbit"]',
        'fa-cow'
    ),
    (
        'Chicken (Broiler)',
        'livestock',
        'head',
        '["kuku","broiler"]',
        'fa-drumstick-bite'
    ),
    (
        'Chicken (Layer)',
        'livestock',
        'head',
        '["kuku","layer"]',
        'fa-egg'
    ),
    (
        'Chicken (Local)',
        'livestock',
        'head',
        '["kuku wa kienyeji"]',
        'fa-drumstick-bite'
    ),
    (
        'Eggs',
        'livestock',
        'tray',
        '["mayai","eggs"]',
        'fa-egg'
    ),
    (
        'Milk',
        'livestock',
        'litre',
        '["maziwa","milk"]',
        'fa-glass-water'
    ),
    (
        'Beef',
        'livestock',
        'kg',
        '["nyama ya ngombe","beef"]',
        'fa-drumstick-bite'
    ),
    (
        'Goat Meat',
        'livestock',
        'kg',
        '["nyama ya mbuzi","chevon"]',
        'fa-drumstick-bite'
    ),
    (
        'Mutton',
        'livestock',
        'kg',
        '["nyama ya kondoo","mutton"]',
        'fa-drumstick-bite'
    ),
    (
        'Pork',
        'livestock',
        'kg',
        '["nyama ya nguruwe","pork"]',
        'fa-drumstick-bite'
    ),
    (
        'Honey',
        'livestock',
        'litre',
        '["asali","honey"]',
        'fa-jar'
    ),
    -- Vegetables
    (
        'Tomatoes',
        'vegetable',
        'kg',
        '["nyanya","tomato"]',
        'fa-apple-whole'
    ),
    (
        'Onions',
        'vegetable',
        'kg',
        '["vitunguu","onion"]',
        'fa-apple-whole'
    ),
    (
        'Kale',
        'vegetable',
        'kg',
        '["sukuma wiki","collards"]',
        'fa-leaf'
    ),
    (
        'Cabbage',
        'vegetable',
        'kg',
        '["kabichi","cabbage"]',
        'fa-leaf'
    ),
    (
        'Carrots',
        'vegetable',
        'kg',
        '["karoti","carrot"]',
        'fa-carrot'
    ),
    (
        'Spinach',
        'vegetable',
        'kg',
        '["mchicha","spinach"]',
        'fa-leaf'
    ),
    (
        'Green Pepper',
        'vegetable',
        'kg',
        '["pilipili hoho","capsicum"]',
        'fa-pepper-hot'
    ),
    (
        'Red Pepper',
        'vegetable',
        'kg',
        '["pilipili","pepper"]',
        'fa-pepper-hot'
    ),
    (
        'Cucumber',
        'vegetable',
        'kg',
        '["tango","cucumber"]',
        'fa-carrot'
    ),
    (
        'Lettuce',
        'vegetable',
        'kg',
        '["kabeji ya majani","lettuce"]',
        'fa-leaf'
    ),
    (
        'Broccoli',
        'vegetable',
        'kg',
        '["brokoli"]',
        'fa-leaf'
    ),
    (
        'Cauliflower',
        'vegetable',
        'kg',
        '["cauliflower"]',
        'fa-leaf'
    ),
    (
        'Beetroot',
        'vegetable',
        'kg',
        '["beetroot"]',
        'fa-carrot'
    ),
    (
        'Garlic',
        'vegetable',
        'kg',
        '["kitunguu saumu","garlic"]',
        'fa-apple-whole'
    ),
    (
        'Ginger',
        'vegetable',
        'kg',
        '["tangawizi","ginger"]',
        'fa-apple-whole'
    ),
    (
        'Okra',
        'vegetable',
        'kg',
        '["bamia","okra"]',
        'fa-seedling'
    ),
    (
        'Eggplant',
        'vegetable',
        'kg',
        '["biringanya","brinjal"]',
        'fa-carrot'
    ),
    (
        'Pumpkin',
        'vegetable',
        'kg',
        '["malenge","pumpkin"]',
        'fa-carrot'
    ),
    (
        'Butternut',
        'vegetable',
        'kg',
        '["butternut","squash"]',
        'fa-carrot'
    ),
    (
        'Zucchini',
        'vegetable',
        'kg',
        '["zucchini","courgette"]',
        'fa-carrot'
    ),
    -- Fruits
    (
        'Mango',
        'fruit',
        'kg',
        '["embe","mango"]',
        'fa-apple-whole'
    ),
    (
        'Banana',
        'fruit',
        'kg',
        '["ndizi","banana"]',
        'fa-apple-whole'
    ),
    (
        'Oranges',
        'fruit',
        'kg',
        '["chungwa","orange"]',
        'fa-apple-whole'
    ),
    (
        'Pineapple',
        'fruit',
        'head',
        '["nanasi","pineapple"]',
        'fa-apple-whole'
    ),
    (
        'Papaya',
        'fruit',
        'kg',
        '["papai","papaya"]',
        'fa-apple-whole'
    ),
    (
        'Watermelon',
        'fruit',
        'kg',
        '["tikiti maji","watermelon"]',
        'fa-apple-whole'
    ),
    (
        'Grapes',
        'fruit',
        'kg',
        '["zabibu","grapes"]',
        'fa-apple-whole'
    ),
    (
        'Strawberry',
        'fruit',
        'kg',
        '["stroberi","strawberry"]',
        'fa-apple-whole'
    ),
    (
        'Lemon',
        'fruit',
        'kg',
        '["limau","lemon"]',
        'fa-apple-whole'
    ),
    (
        'Lime',
        'fruit',
        'kg',
        '["ndimu","lime"]',
        'fa-apple-whole'
    ),
    (
        'Passion Fruit',
        'fruit',
        'kg',
        '["pasheni","passion"]',
        'fa-apple-whole'
    ),
    (
        'Guava',
        'fruit',
        'kg',
        '["mapera","guava"]',
        'fa-apple-whole'
    ),
    (
        'Pomegranate',
        'fruit',
        'kg',
        '["komamanga","pomegranate"]',
        'fa-apple-whole'
    ),
    (
        'Kiwi',
        'fruit',
        'kg',
        '["kiwi"]',
        'fa-apple-whole'
    ),
    (
        'Peach',
        'fruit',
        'kg',
        '["peach","pichi"]',
        'fa-apple-whole'
    ),
    (
        'Pear',
        'fruit',
        'kg',
        '["pear","pea"]',
        'fa-apple-whole'
    ),
    (
        'Plum',
        'fruit',
        'kg',
        '["plum","plamu"]',
        'fa-apple-whole'
    ),
    -- Other
    (
        'Sunflower',
        'other',
        'kg',
        '["alizeti","sunflower"]',
        'fa-seedling'
    ),
    (
        'Soya Beans',
        'other',
        'kg',
        '["soya","soybean"]',
        'fa-seedling'
    ),
    (
        'Cashew',
        'other',
        'kg',
        '["korosho","cashew"]',
        'fa-seedling'
    ),
    (
        'Vanilla',
        'other',
        'kg',
        '["vanilla","vanili"]',
        'fa-leaf'
    ),
    (
        'Cardamom',
        'other',
        'kg',
        '["iliki","cardamom"]',
        'fa-leaf'
    ),
    (
        'Cinnamon',
        'other',
        'kg',
        '["mdalasini","cinnamon"]',
        'fa-leaf'
    ),
    (
        'Turmeric',
        'other',
        'kg',
        '["manjano","turmeric"]',
        'fa-leaf'
    );
-- ============================================================
-- 8. SEED: ~500 MARKETS ACROSS 50 AFRICAN COUNTRIES
-- ============================================================
-- Original seed block (Kenya, Uganda, Tanzania, Rwanda, Ethiopia,
-- Nigeria, Ghana, Zambia, Zimbabwe, South Africa, Egypt, Morocco,
-- Senegal, Ivory Coast) — reinsert as-is if not already present.
-- The 300 additional markets from the expansion file follow.
-- ------------------------------------------------------------
-- KENYA — 30
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Wakulima Market',
        'wholesale',
        'Nairobi',
        'Kenya',
        'KE',
        -1.2864,
        36.8172,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Marikiti Market',
        'wholesale',
        'Nairobi',
        'Kenya',
        'KE',
        -1.2833,
        36.8200,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kangemi Market',
        'retail',
        'Nairobi',
        'Kenya',
        'KE',
        -1.2667,
        36.7500,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Gikomba Market',
        'wholesale',
        'Nairobi',
        'Kenya',
        'KE',
        -1.2833,
        36.8333,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'City Park Market',
        'retail',
        'Nairobi',
        'Kenya',
        'KE',
        -1.2667,
        36.8167,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Muthurwa Market',
        'retail',
        'Nairobi',
        'Kenya',
        'KE',
        -1.2833,
        36.8333,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kawangware Market',
        'retail',
        'Nairobi',
        'Kenya',
        'KE',
        -1.2833,
        36.7500,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Nakuru Market',
        'wholesale',
        'Nakuru',
        'Kenya',
        'KE',
        -0.3031,
        36.0800,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Eldoret Market',
        'wholesale',
        'Uasin Gishu',
        'Kenya',
        'KE',
        0.5167,
        35.2833,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kisumu Market',
        'wholesale',
        'Kisumu',
        'Kenya',
        'KE',
        -0.0917,
        34.7680,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Mombasa Market',
        'wholesale',
        'Mombasa',
        'Kenya',
        'KE',
        -4.0435,
        39.6682,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Thika Market',
        'wholesale',
        'Kiambu',
        'Kenya',
        'KE',
        -1.0333,
        37.0667,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Nyeri Market',
        'wholesale',
        'Nyeri',
        'Kenya',
        'KE',
        -0.4167,
        36.9500,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Meru Market',
        'wholesale',
        'Meru',
        'Kenya',
        'KE',
        0.0500,
        37.6500,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Embu Market',
        'wholesale',
        'Embu',
        'Kenya',
        'KE',
        -0.5333,
        37.4500,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kericho Market',
        'wholesale',
        'Kericho',
        'Kenya',
        'KE',
        -0.3667,
        35.2833,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kakamega Market',
        'wholesale',
        'Kakamega',
        'Kenya',
        'KE',
        0.2833,
        34.7500,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Bungoma Market',
        'wholesale',
        'Bungoma',
        'Kenya',
        'KE',
        0.5667,
        34.5667,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kitale Market',
        'wholesale',
        'Trans Nzoia',
        'Kenya',
        'KE',
        1.0167,
        35.0000,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kapsabet Market',
        'wholesale',
        'Nandi',
        'Kenya',
        'KE',
        0.2000,
        35.1000,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Nyahururu Market',
        'wholesale',
        'Laikipia',
        'Kenya',
        'KE',
        0.0333,
        36.3667,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Naivasha Market',
        'wholesale',
        'Nakuru',
        'Kenya',
        'KE',
        -0.7167,
        36.4333,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Machakos Market',
        'wholesale',
        'Machakos',
        'Kenya',
        'KE',
        -1.5167,
        37.2667,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kitui Market',
        'wholesale',
        'Kitui',
        'Kenya',
        'KE',
        -1.3667,
        38.0167,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Garissa Market',
        'wholesale',
        'Garissa',
        'Kenya',
        'KE',
        -0.4536,
        39.6461,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Malindi Market',
        'wholesale',
        'Kilifi',
        'Kenya',
        'KE',
        -3.2192,
        40.1169,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Kilifi Market',
        'wholesale',
        'Kilifi',
        'Kenya',
        'KE',
        -3.6333,
        39.8500,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Lamu Market',
        'wholesale',
        'Lamu',
        'Kenya',
        'KE',
        -2.2717,
        40.9020,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Narok Market',
        'wholesale',
        'Narok',
        'Kenya',
        'KE',
        -1.0833,
        35.8667,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    ),
    (
        'Bomet Market',
        'wholesale',
        'Bomet',
        'Kenya',
        'KE',
        -0.7833,
        35.3333,
        'KES',
        'Africa/Nairobi',
        'KAMIS'
    );
-- ------------------------------------------------------------
-- UGANDA — 15
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Nakasero Market',
        'wholesale',
        'Kampala',
        'Uganda',
        'UG',
        0.3136,
        32.5811,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Owino Market',
        'wholesale',
        'Kampala',
        'Uganda',
        'UG',
        0.3136,
        32.5811,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Kalerwe Market',
        'retail',
        'Kampala',
        'Uganda',
        'UG',
        0.3500,
        32.5667,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Gulu Market',
        'wholesale',
        'Gulu',
        'Uganda',
        'UG',
        2.7746,
        32.2990,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Mbarara Market',
        'wholesale',
        'Mbarara',
        'Uganda',
        'UG',
        -0.6072,
        30.6545,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Jinja Market',
        'wholesale',
        'Jinja',
        'Uganda',
        'UG',
        0.4244,
        33.2041,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Mbale Market',
        'wholesale',
        'Mbale',
        'Uganda',
        'UG',
        1.0803,
        34.1750,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Masaka Market',
        'wholesale',
        'Masaka',
        'Uganda',
        'UG',
        -0.3333,
        31.7333,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Fort Portal Market',
        'wholesale',
        'Kabarole',
        'Uganda',
        'UG',
        0.6545,
        30.2749,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Lira Market',
        'wholesale',
        'Lira',
        'Uganda',
        'UG',
        2.2499,
        32.8999,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Arua Market',
        'wholesale',
        'Arua',
        'Uganda',
        'UG',
        3.0201,
        30.9111,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Soroti Market',
        'wholesale',
        'Soroti',
        'Uganda',
        'UG',
        1.7146,
        33.6111,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Kabale Market',
        'wholesale',
        'Kabale',
        'Uganda',
        'UG',
        -1.2494,
        29.9899,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Hoima Market',
        'wholesale',
        'Hoima',
        'Uganda',
        'UG',
        1.4333,
        31.3500,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    ),
    (
        'Entebbe Market',
        'retail',
        'Wakiso',
        'Uganda',
        'UG',
        0.0500,
        32.4600,
        'UGX',
        'Africa/Kampala',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- TANZANIA — 15
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Kariakoo Market',
        'wholesale',
        'Dar es Salaam',
        'Tanzania',
        'TZ',
        -6.8161,
        39.2803,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Tandale Market',
        'retail',
        'Dar es Salaam',
        'Tanzania',
        'TZ',
        -6.7800,
        39.2500,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Mwanakwerekwe Market',
        'wholesale',
        'Zanzibar',
        'Tanzania',
        'TZ',
        -6.1659,
        39.2026,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Dodoma Market',
        'wholesale',
        'Dodoma',
        'Tanzania',
        'TZ',
        -6.1835,
        35.7464,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Arusha Market',
        'wholesale',
        'Arusha',
        'Tanzania',
        'TZ',
        -3.3667,
        36.6833,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Mwanza Market',
        'wholesale',
        'Mwanza',
        'Tanzania',
        'TZ',
        -2.5167,
        32.9000,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Mbeya Market',
        'wholesale',
        'Mbeya',
        'Tanzania',
        'TZ',
        -8.9000,
        33.4500,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Morogoro Market',
        'wholesale',
        'Morogoro',
        'Tanzania',
        'TZ',
        -6.8222,
        37.6597,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Tanga Market',
        'wholesale',
        'Tanga',
        'Tanzania',
        'TZ',
        -5.0689,
        39.0988,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Kigoma Market',
        'wholesale',
        'Kigoma',
        'Tanzania',
        'TZ',
        -4.8769,
        29.6267,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Iringa Market',
        'wholesale',
        'Iringa',
        'Tanzania',
        'TZ',
        -7.7700,
        35.6900,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Mtwara Market',
        'wholesale',
        'Mtwara',
        'Tanzania',
        'TZ',
        -10.2667,
        40.1833,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Kilimanjaro Market',
        'wholesale',
        'Kilimanjaro',
        'Tanzania',
        'TZ',
        -3.3667,
        37.3333,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Tabora Market',
        'wholesale',
        'Tabora',
        'Tanzania',
        'TZ',
        -5.0167,
        32.8000,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    ),
    (
        'Singida Market',
        'wholesale',
        'Singida',
        'Tanzania',
        'TZ',
        -4.8167,
        34.7500,
        'TZS',
        'Africa/Dar_es_Salaam',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- RWANDA — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Kimironko Market',
        'retail',
        'Kigali',
        'Rwanda',
        'RW',
        -1.9500,
        30.1167,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Nyabugogo Market',
        'wholesale',
        'Kigali',
        'Rwanda',
        'RW',
        -1.9400,
        30.0600,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Kimisagara Market',
        'wholesale',
        'Kigali',
        'Rwanda',
        'RW',
        -1.9500,
        30.0500,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Butare Market',
        'wholesale',
        'Huye',
        'Rwanda',
        'RW',
        -2.6000,
        29.7500,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Gisenyi Market',
        'wholesale',
        'Rubavu',
        'Rwanda',
        'RW',
        -1.6772,
        29.2603,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Musanze Market',
        'wholesale',
        'Musanze',
        'Rwanda',
        'RW',
        -1.4998,
        29.6349,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Rusizi Market',
        'wholesale',
        'Rusizi',
        'Rwanda',
        'RW',
        -2.4833,
        28.9000,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Nyagatare Market',
        'wholesale',
        'Nyagatare',
        'Rwanda',
        'RW',
        -1.2939,
        30.3272,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Rwamagana Market',
        'wholesale',
        'Rwamagana',
        'Rwanda',
        'RW',
        -1.9486,
        30.4347,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    ),
    (
        'Muhanga Market',
        'wholesale',
        'Muhanga',
        'Rwanda',
        'RW',
        -2.0833,
        29.7500,
        'RWF',
        'Africa/Kigali',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- ETHIOPIA — 15
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Merkato',
        'wholesale',
        'Addis Ababa',
        'Ethiopia',
        'ET',
        9.0300,
        38.7500,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Addis Ketema',
        'retail',
        'Addis Ababa',
        'Ethiopia',
        'ET',
        9.0300,
        38.7400,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Adama Market',
        'wholesale',
        'Oromia',
        'Ethiopia',
        'ET',
        8.5400,
        39.2694,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Dire Dawa Market',
        'wholesale',
        'Dire Dawa',
        'Ethiopia',
        'ET',
        9.5931,
        41.8661,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Mekelle Market',
        'wholesale',
        'Tigray',
        'Ethiopia',
        'ET',
        13.4969,
        39.4753,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Bahir Dar Market',
        'wholesale',
        'Amhara',
        'Ethiopia',
        'ET',
        11.5936,
        37.3908,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Hawassa Market',
        'wholesale',
        'Sidama',
        'Ethiopia',
        'ET',
        7.0621,
        38.4764,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Jimma Market',
        'wholesale',
        'Oromia',
        'Ethiopia',
        'ET',
        7.6733,
        36.8344,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Gondar Market',
        'wholesale',
        'Amhara',
        'Ethiopia',
        'ET',
        12.6000,
        37.4667,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Dessie Market',
        'wholesale',
        'Amhara',
        'Ethiopia',
        'ET',
        11.1333,
        39.6333,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Shashemene Market',
        'wholesale',
        'Oromia',
        'Ethiopia',
        'ET',
        7.2000,
        38.6000,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Nekemte Market',
        'wholesale',
        'Oromia',
        'Ethiopia',
        'ET',
        9.0833,
        36.5500,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Harar Market',
        'wholesale',
        'Harari',
        'Ethiopia',
        'ET',
        9.3111,
        42.1181,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Jijiga Market',
        'wholesale',
        'Somali',
        'Ethiopia',
        'ET',
        9.3500,
        42.8000,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    ),
    (
        'Arba Minch Market',
        'wholesale',
        'SNNPR',
        'Ethiopia',
        'ET',
        6.0333,
        37.5500,
        'ETB',
        'Africa/Addis_Ababa',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- NIGERIA — 15
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Mile 12 Market',
        'wholesale',
        'Lagos',
        'Nigeria',
        'NG',
        6.4667,
        3.3833,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Oshodi Market',
        'wholesale',
        'Lagos',
        'Nigeria',
        'NG',
        6.5553,
        3.3408,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Balogun Market',
        'retail',
        'Lagos',
        'Nigeria',
        'NG',
        6.4541,
        3.3947,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Bodija Market',
        'wholesale',
        'Oyo',
        'Nigeria',
        'NG',
        7.4167,
        3.9000,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Wuse Market',
        'retail',
        'Abuja',
        'Nigeria',
        'NG',
        9.0765,
        7.3986,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Karu Market',
        'wholesale',
        'Abuja',
        'Nigeria',
        'NG',
        9.0167,
        7.5500,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Kano Central Market',
        'wholesale',
        'Kano',
        'Nigeria',
        'NG',
        12.0000,
        8.5167,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Kaduna Central',
        'wholesale',
        'Kaduna',
        'Nigeria',
        'NG',
        10.5167,
        7.4333,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Port Harcourt Market',
        'wholesale',
        'Rivers',
        'Nigeria',
        'NG',
        4.7774,
        7.0134,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Benin City Market',
        'wholesale',
        'Edo',
        'Nigeria',
        'NG',
        6.3176,
        5.6145,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Onitsha Main Market',
        'wholesale',
        'Anambra',
        'Nigeria',
        'NG',
        6.1400,
        6.7900,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Aba Market',
        'wholesale',
        'Abia',
        'Nigeria',
        'NG',
        5.1167,
        7.3667,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Ibadan Central',
        'wholesale',
        'Oyo',
        'Nigeria',
        'NG',
        7.3776,
        3.9470,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Jos Market',
        'wholesale',
        'Plateau',
        'Nigeria',
        'NG',
        9.8965,
        8.8583,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    ),
    (
        'Maiduguri Market',
        'wholesale',
        'Borno',
        'Nigeria',
        'NG',
        11.8333,
        13.1500,
        'NGN',
        'Africa/Lagos',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- GHANA — 15
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Makola Market',
        'wholesale',
        'Greater Accra',
        'Ghana',
        'GH',
        5.5500,
        -0.2000,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Kaneshie Market',
        'wholesale',
        'Greater Accra',
        'Ghana',
        'GH',
        5.5667,
        -0.2333,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Madina Market',
        'retail',
        'Greater Accra',
        'Ghana',
        'GH',
        5.6833,
        -0.1667,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Kumasi Central',
        'wholesale',
        'Ashanti',
        'Ghana',
        'GH',
        6.6833,
        -1.6167,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Kejetia Market',
        'wholesale',
        'Ashanti',
        'Ghana',
        'GH',
        6.6833,
        -1.6167,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Tamale Market',
        'wholesale',
        'Northern',
        'Ghana',
        'GH',
        9.4000,
        -0.8333,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Takoradi Market',
        'wholesale',
        'Western',
        'Ghana',
        'GH',
        4.8833,
        -1.7500,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Cape Coast Market',
        'wholesale',
        'Central',
        'Ghana',
        'GH',
        5.1000,
        -1.2500,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Sunyani Market',
        'wholesale',
        'Bono',
        'Ghana',
        'GH',
        7.3333,
        -2.3333,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Ho Market',
        'wholesale',
        'Volta',
        'Ghana',
        'GH',
        6.6000,
        0.4667,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Bolgatanga Market',
        'wholesale',
        'Upper East',
        'Ghana',
        'GH',
        10.7833,
        -0.8500,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Wa Market',
        'wholesale',
        'Upper West',
        'Ghana',
        'GH',
        10.0667,
        -2.5000,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Tema Market',
        'wholesale',
        'Greater Accra',
        'Ghana',
        'GH',
        5.6667,
        0.0167,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Obuasi Market',
        'wholesale',
        'Ashanti',
        'Ghana',
        'GH',
        6.2000,
        -1.6667,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    ),
    (
        'Koforidua Market',
        'wholesale',
        'Eastern',
        'Ghana',
        'GH',
        6.0833,
        -0.2500,
        'GHS',
        'Africa/Accra',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- ZAMBIA — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Soweto Market',
        'wholesale',
        'Lusaka',
        'Zambia',
        'ZM',
        -15.4167,
        28.2833,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'City Market',
        'retail',
        'Lusaka',
        'Zambia',
        'ZM',
        -15.4167,
        28.2833,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'Kitwe Market',
        'wholesale',
        'Copperbelt',
        'Zambia',
        'ZM',
        -12.8000,
        28.2000,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'Ndola Market',
        'wholesale',
        'Copperbelt',
        'Zambia',
        'ZM',
        -12.9587,
        28.6366,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'Kabwe Market',
        'wholesale',
        'Central',
        'Zambia',
        'ZM',
        -14.4469,
        28.4464,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'Livingstone Market',
        'wholesale',
        'Southern',
        'Zambia',
        'ZM',
        -17.8500,
        25.8667,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'Chipata Market',
        'wholesale',
        'Eastern',
        'Zambia',
        'ZM',
        -13.6333,
        32.6500,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'Mansa Market',
        'wholesale',
        'Luapula',
        'Zambia',
        'ZM',
        -9.7833,
        29.0667,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'Solwezi Market',
        'wholesale',
        'North-Western',
        'Zambia',
        'ZM',
        -12.1833,
        26.4000,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    ),
    (
        'Mongu Market',
        'wholesale',
        'Western',
        'Zambia',
        'ZM',
        -15.2500,
        23.1333,
        'ZMW',
        'Africa/Lusaka',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- ZIMBABWE — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Mbare Musika',
        'wholesale',
        'Harare',
        'Zimbabwe',
        'ZW',
        -17.8667,
        31.0333,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Sakubva Market',
        'wholesale',
        'Manicaland',
        'Zimbabwe',
        'ZW',
        -18.9667,
        32.6667,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Bulawayo Market',
        'wholesale',
        'Bulawayo',
        'Zimbabwe',
        'ZW',
        -20.1500,
        28.5833,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Gweru Market',
        'wholesale',
        'Midlands',
        'Zimbabwe',
        'ZW',
        -19.4500,
        29.8167,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Mutare Market',
        'wholesale',
        'Manicaland',
        'Zimbabwe',
        'ZW',
        -18.9667,
        32.6667,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Masvingo Market',
        'wholesale',
        'Masvingo',
        'Zimbabwe',
        'ZW',
        -20.0667,
        30.8333,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Chitungwiza Market',
        'retail',
        'Harare',
        'Zimbabwe',
        'ZW',
        -17.9833,
        31.0500,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Kwekwe Market',
        'wholesale',
        'Midlands',
        'Zimbabwe',
        'ZW',
        -18.9167,
        29.8000,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Kadoma Market',
        'wholesale',
        'Mashonaland West',
        'Zimbabwe',
        'ZW',
        -18.3333,
        29.9167,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    ),
    (
        'Hwange Market',
        'wholesale',
        'Matabeleland North',
        'Zimbabwe',
        'ZW',
        -18.3667,
        26.5000,
        'USD',
        'Africa/Harare',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- SOUTH AFRICA — 15
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Johannesburg Market',
        'wholesale',
        'Gauteng',
        'South Africa',
        'ZA',
        -26.2041,
        28.0473,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Pretoria Market',
        'wholesale',
        'Gauteng',
        'South Africa',
        'ZA',
        -25.7479,
        28.2293,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Cape Town Market',
        'wholesale',
        'Western Cape',
        'South Africa',
        'ZA',
        -33.9249,
        18.4241,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Durban Market',
        'wholesale',
        'KwaZulu-Natal',
        'South Africa',
        'ZA',
        -29.8587,
        31.0218,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Port Elizabeth Market',
        'wholesale',
        'Eastern Cape',
        'South Africa',
        'ZA',
        -33.9608,
        25.6022,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Bloemfontein Market',
        'wholesale',
        'Free State',
        'South Africa',
        'ZA',
        -29.0852,
        26.1596,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'East London Market',
        'wholesale',
        'Eastern Cape',
        'South Africa',
        'ZA',
        -33.0292,
        27.8546,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Polokwane Market',
        'wholesale',
        'Limpopo',
        'South Africa',
        'ZA',
        -23.9045,
        29.4689,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Nelspruit Market',
        'wholesale',
        'Mpumalanga',
        'South Africa',
        'ZA',
        -25.4658,
        30.9853,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Kimberley Market',
        'wholesale',
        'Northern Cape',
        'South Africa',
        'ZA',
        -28.7282,
        24.7499,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Soweto Market (JHB)',
        'retail',
        'Gauteng',
        'South Africa',
        'ZA',
        -26.2677,
        27.8585,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Khayelitsha Market',
        'retail',
        'Western Cape',
        'South Africa',
        'ZA',
        -34.0333,
        18.6833,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Mitchells Plain Market',
        'retail',
        'Western Cape',
        'South Africa',
        'ZA',
        -34.0333,
        18.6167,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Tembisa Market',
        'retail',
        'Gauteng',
        'South Africa',
        'ZA',
        -26.0000,
        28.2333,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    ),
    (
        'Alexandra Market',
        'retail',
        'Gauteng',
        'South Africa',
        'ZA',
        -26.1000,
        28.0833,
        'ZAR',
        'Africa/Johannesburg',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- EGYPT — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Cairo Central Market',
        'wholesale',
        'Cairo',
        'Egypt',
        'EG',
        30.0444,
        31.2357,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Giza Market',
        'wholesale',
        'Giza',
        'Egypt',
        'EG',
        30.0131,
        31.2089,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Alexandria Market',
        'wholesale',
        'Alexandria',
        'Egypt',
        'EG',
        31.2001,
        29.9187,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Port Said Market',
        'wholesale',
        'Port Said',
        'Egypt',
        'EG',
        31.2653,
        32.3019,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Suez Market',
        'wholesale',
        'Suez',
        'Egypt',
        'EG',
        29.9668,
        32.5498,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Luxor Market',
        'wholesale',
        'Luxor',
        'Egypt',
        'EG',
        25.6872,
        32.6396,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Aswan Market',
        'wholesale',
        'Aswan',
        'Egypt',
        'EG',
        24.0889,
        32.8998,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Mansoura Market',
        'wholesale',
        'Dakahlia',
        'Egypt',
        'EG',
        31.0409,
        31.3785,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Tanta Market',
        'wholesale',
        'Gharbia',
        'Egypt',
        'EG',
        30.7865,
        31.0004,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    ),
    (
        'Asyut Market',
        'wholesale',
        'Asyut',
        'Egypt',
        'EG',
        27.1809,
        31.1837,
        'EGP',
        'Africa/Cairo',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- MOROCCO — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Casablanca Central',
        'wholesale',
        'Casablanca-Settat',
        'Morocco',
        'MA',
        33.5731,
        -7.5898,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Marrakesh Market',
        'wholesale',
        'Marrakesh-Safi',
        'Morocco',
        'MA',
        31.6295,
        -7.9811,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Fes Market',
        'wholesale',
        'Fès-Meknès',
        'Morocco',
        'MA',
        34.0181,
        -5.0078,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Tangier Market',
        'wholesale',
        'Tanger-Tétouan-Al Hoceïma',
        'Morocco',
        'MA',
        35.7595,
        -5.8340,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Agadir Market',
        'wholesale',
        'Souss-Massa',
        'Morocco',
        'MA',
        30.4278,
        -9.5981,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Rabat Market',
        'wholesale',
        'Rabat-Salé-Kénitra',
        'Morocco',
        'MA',
        34.0209,
        -6.8416,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Meknes Market',
        'wholesale',
        'Fès-Meknès',
        'Morocco',
        'MA',
        33.8935,
        -5.5473,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Oujda Market',
        'wholesale',
        'Oriental',
        'Morocco',
        'MA',
        34.6814,
        -1.9086,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Kenitra Market',
        'wholesale',
        'Rabat-Salé-Kénitra',
        'Morocco',
        'MA',
        34.2610,
        -6.5802,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    ),
    (
        'Tetouan Market',
        'wholesale',
        'Tanger-Tétouan-Al Hoceïma',
        'Morocco',
        'MA',
        35.5785,
        -5.3684,
        'MAD',
        'Africa/Casablanca',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- SENEGAL — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Dakar Central',
        'wholesale',
        'Dakar',
        'Senegal',
        'SN',
        14.6928,
        -17.4467,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Tilene Market',
        'wholesale',
        'Dakar',
        'Senegal',
        'SN',
        14.7333,
        -17.4000,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Thies Market',
        'wholesale',
        'Thiès',
        'Senegal',
        'SN',
        14.7833,
        -16.9333,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Saint-Louis Market',
        'wholesale',
        'Saint-Louis',
        'Senegal',
        'SN',
        16.0179,
        -16.4896,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Kaolack Market',
        'wholesale',
        'Kaolack',
        'Senegal',
        'SN',
        14.1652,
        -16.0758,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Ziguinchor Market',
        'wholesale',
        'Ziguinchor',
        'Senegal',
        'SN',
        12.5665,
        -16.2733,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Tambacounda Market',
        'wholesale',
        'Tambacounda',
        'Senegal',
        'SN',
        13.7708,
        -13.6673,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Diourbel Market',
        'wholesale',
        'Diourbel',
        'Senegal',
        'SN',
        14.6552,
        -16.2312,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Louga Market',
        'wholesale',
        'Louga',
        'Senegal',
        'SN',
        15.6143,
        -16.2249,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    ),
    (
        'Kolda Market',
        'wholesale',
        'Kolda',
        'Senegal',
        'SN',
        12.8983,
        -14.9412,
        'XOF',
        'Africa/Dakar',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- IVORY COAST — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Abidjan Market',
        'wholesale',
        'Abidjan',
        'Ivory Coast',
        'CI',
        5.3600,
        -4.0083,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'Treichville Market',
        'wholesale',
        'Abidjan',
        'Ivory Coast',
        'CI',
        5.3000,
        -4.0000,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'Adjamé Market',
        'wholesale',
        'Abidjan',
        'Ivory Coast',
        'CI',
        5.3667,
        -4.0167,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'Bouaké Market',
        'wholesale',
        'Vallée du Bandama',
        'Ivory Coast',
        'CI',
        7.6833,
        -5.0333,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'Yamoussoukro Market',
        'wholesale',
        'Lacs',
        'Ivory Coast',
        'CI',
        6.8167,
        -5.2833,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'San-Pédro Market',
        'wholesale',
        'Bas-Sassandra',
        'Ivory Coast',
        'CI',
        4.7485,
        -6.6363,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'Korhogo Market',
        'wholesale',
        'Savanes',
        'Ivory Coast',
        'CI',
        9.4578,
        -5.6294,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'Daloa Market',
        'wholesale',
        'Sassandra-Marahoué',
        'Ivory Coast',
        'CI',
        6.8774,
        -6.4502,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'Man Market',
        'wholesale',
        'Montagnes',
        'Ivory Coast',
        'CI',
        7.4125,
        -7.5537,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    ),
    (
        'Gagnoa Market',
        'wholesale',
        'Gôh',
        'Ivory Coast',
        'CI',
        6.1319,
        -5.9506,
        'XOF',
        'Africa/Abidjan',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- CAMEROON — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Mfoundi Market',
        'wholesale',
        'Centre',
        'Cameroon',
        'CM',
        3.8480,
        11.5021,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Marché Central Yaoundé',
        'retail',
        'Centre',
        'Cameroon',
        'CM',
        3.8667,
        11.5167,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Douala Market',
        'wholesale',
        'Littoral',
        'Cameroon',
        'CM',
        4.0511,
        9.7679,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Marché Mokolo',
        'wholesale',
        'Littoral',
        'Cameroon',
        'CM',
        4.0500,
        9.7000,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Bafoussam Market',
        'wholesale',
        'West',
        'Cameroon',
        'CM',
        5.4781,
        10.4172,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Bamenda Market',
        'wholesale',
        'North-West',
        'Cameroon',
        'CM',
        5.9631,
        10.1591,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Garoua Market',
        'wholesale',
        'North',
        'Cameroon',
        'CM',
        9.3017,
        13.3921,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Maroua Market',
        'wholesale',
        'Far North',
        'Cameroon',
        'CM',
        10.5956,
        14.3247,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Ngaoundéré Market',
        'wholesale',
        'Adamawa',
        'Cameroon',
        'CM',
        7.3167,
        13.5833,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    ),
    (
        'Bertoua Market',
        'wholesale',
        'East',
        'Cameroon',
        'CM',
        4.5772,
        13.6846,
        'XAF',
        'Africa/Douala',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- MOZAMBIQUE — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Maputo Central Market',
        'wholesale',
        'Maputo',
        'Mozambique',
        'MZ',
        -25.9655,
        32.5832,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Xipamanine Market',
        'wholesale',
        'Maputo',
        'Mozambique',
        'MZ',
        -25.9333,
        32.5667,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Matola Market',
        'wholesale',
        'Maputo',
        'Mozambique',
        'MZ',
        -25.9622,
        32.4589,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Beira Market',
        'wholesale',
        'Sofala',
        'Mozambique',
        'MZ',
        -19.8436,
        34.8389,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Nampula Market',
        'wholesale',
        'Nampula',
        'Mozambique',
        'MZ',
        -15.1165,
        39.2666,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Quelimane Market',
        'wholesale',
        'Zambézia',
        'Mozambique',
        'MZ',
        -17.8786,
        36.8883,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Chimoio Market',
        'wholesale',
        'Manica',
        'Mozambique',
        'MZ',
        -19.1164,
        33.4833,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Tete Market',
        'wholesale',
        'Tete',
        'Mozambique',
        'MZ',
        -16.1564,
        33.5867,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Pemba Market',
        'wholesale',
        'Cabo Delgado',
        'Mozambique',
        'MZ',
        -12.9739,
        40.5178,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    ),
    (
        'Lichinga Market',
        'wholesale',
        'Niassa',
        'Mozambique',
        'MZ',
        -13.3128,
        35.2406,
        'MZN',
        'Africa/Maputo',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- ANGOLA — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Luanda Central Market',
        'wholesale',
        'Luanda',
        'Angola',
        'AO',
        -8.8383,
        13.2344,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Roque Santeiro Market',
        'wholesale',
        'Luanda',
        'Angola',
        'AO',
        -8.8500,
        13.2333,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Belas Market',
        'retail',
        'Luanda',
        'Angola',
        'AO',
        -8.9167,
        13.1833,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Huambo Market',
        'wholesale',
        'Huambo',
        'Angola',
        'AO',
        -12.7761,
        15.7392,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Lobito Market',
        'wholesale',
        'Benguela',
        'Angola',
        'AO',
        -12.3644,
        13.5456,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Benguela Market',
        'wholesale',
        'Benguela',
        'Angola',
        'AO',
        -12.5763,
        13.4055,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Lubango Market',
        'wholesale',
        'Huíla',
        'Angola',
        'AO',
        -14.9177,
        13.4925,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Malanje Market',
        'wholesale',
        'Malanje',
        'Angola',
        'AO',
        -9.5400,
        16.3410,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Cabinda Market',
        'wholesale',
        'Cabinda',
        'Angola',
        'AO',
        -5.5500,
        12.2000,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    ),
    (
        'Namibe Market',
        'wholesale',
        'Namibe',
        'Angola',
        'AO',
        -15.1961,
        12.1522,
        'AOA',
        'Africa/Luanda',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- DRC — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Marché Central Kinshasa',
        'wholesale',
        'Kinshasa',
        'DRC',
        'CD',
        -4.3250,
        15.3222,
        'CDF',
        'Africa/Kinshasa',
        'FEWS NET'
    ),
    (
        'Marché Gambela',
        'wholesale',
        'Kinshasa',
        'DRC',
        'CD',
        -4.3167,
        15.3000,
        'CDF',
        'Africa/Kinshasa',
        'FEWS NET'
    ),
    (
        'Marché Matete',
        'retail',
        'Kinshasa',
        'DRC',
        'CD',
        -4.3833,
        15.3333,
        'CDF',
        'Africa/Kinshasa',
        'FEWS NET'
    ),
    (
        'Lubumbashi Market',
        'wholesale',
        'Haut-Katanga',
        'DRC',
        'CD',
        -11.6609,
        27.4794,
        'CDF',
        'Africa/Lubumbashi',
        'FEWS NET'
    ),
    (
        'Mbuji-Mayi Market',
        'wholesale',
        'Kasaï-Oriental',
        'DRC',
        'CD',
        -6.1500,
        23.6000,
        'CDF',
        'Africa/Lubumbashi',
        'FEWS NET'
    ),
    (
        'Kisangani Market',
        'wholesale',
        'Tshopo',
        'DRC',
        'CD',
        0.5153,
        25.1910,
        'CDF',
        'Africa/Lubumbashi',
        'FEWS NET'
    ),
    (
        'Kananga Market',
        'wholesale',
        'Kasaï-Central',
        'DRC',
        'CD',
        -5.8960,
        22.4166,
        'CDF',
        'Africa/Lubumbashi',
        'FEWS NET'
    ),
    (
        'Bukavu Market',
        'wholesale',
        'Sud-Kivu',
        'DRC',
        'CD',
        -2.5083,
        28.8608,
        'CDF',
        'Africa/Lubumbashi',
        'FEWS NET'
    ),
    (
        'Goma Market',
        'wholesale',
        'Nord-Kivu',
        'DRC',
        'CD',
        -1.6792,
        29.2228,
        'CDF',
        'Africa/Lubumbashi',
        'FEWS NET'
    ),
    (
        'Matadi Market',
        'wholesale',
        'Kongo-Central',
        'DRC',
        'CD',
        -5.8167,
        13.4500,
        'CDF',
        'Africa/Kinshasa',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- SUDAN — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Omdurman Market',
        'wholesale',
        'Khartoum',
        'Sudan',
        'SD',
        15.6445,
        32.4777,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'Khartoum Central Market',
        'wholesale',
        'Khartoum',
        'Sudan',
        'SD',
        15.5000,
        32.5500,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'Bahri Market',
        'wholesale',
        'Khartoum',
        'Sudan',
        'SD',
        15.6333,
        32.5333,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'Port Sudan Market',
        'wholesale',
        'Red Sea',
        'Sudan',
        'SD',
        19.6158,
        37.2164,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'Kassala Market',
        'wholesale',
        'Kassala',
        'Sudan',
        'SD',
        15.4500,
        36.4000,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'Nyala Market',
        'wholesale',
        'South Darfur',
        'Sudan',
        'SD',
        12.0500,
        24.8833,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'El Obeid Market',
        'wholesale',
        'North Kordofan',
        'Sudan',
        'SD',
        13.1833,
        30.2167,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'Wad Madani Market',
        'wholesale',
        'Al Jazirah',
        'Sudan',
        'SD',
        14.4000,
        33.5333,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'Gedaref Market',
        'wholesale',
        'Gedaref',
        'Sudan',
        'SD',
        14.0333,
        35.3833,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    ),
    (
        'Dongola Market',
        'wholesale',
        'Northern',
        'Sudan',
        'SD',
        19.1667,
        30.4833,
        'SDG',
        'Africa/Khartoum',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- TUNISIA — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Tunis Central Market',
        'wholesale',
        'Tunis',
        'Tunisia',
        'TN',
        36.8065,
        10.1815,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Marché Central Tunis',
        'retail',
        'Tunis',
        'Tunisia',
        'TN',
        36.8000,
        10.1833,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Sfax Market',
        'wholesale',
        'Sfax',
        'Tunisia',
        'TN',
        34.7406,
        10.7603,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Sousse Market',
        'wholesale',
        'Sousse',
        'Tunisia',
        'TN',
        35.8256,
        10.6084,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Kairouan Market',
        'wholesale',
        'Kairouan',
        'Tunisia',
        'TN',
        35.6781,
        10.0964,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Bizerte Market',
        'wholesale',
        'Bizerte',
        'Tunisia',
        'TN',
        37.2744,
        9.8739,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Gabès Market',
        'wholesale',
        'Gabès',
        'Tunisia',
        'TN',
        33.8815,
        10.0982,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Ariana Market',
        'retail',
        'Ariana',
        'Tunisia',
        'TN',
        36.8625,
        10.1956,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Gafsa Market',
        'wholesale',
        'Gafsa',
        'Tunisia',
        'TN',
        34.4250,
        8.7842,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    ),
    (
        'Monastir Market',
        'wholesale',
        'Monastir',
        'Tunisia',
        'TN',
        35.7694,
        10.8262,
        'TND',
        'Africa/Tunis',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- BURKINA FASO — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Ouagadougou Central',
        'wholesale',
        'Centre',
        'Burkina Faso',
        'BF',
        12.3714,
        -1.5197,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Marché Rood Woko',
        'wholesale',
        'Centre',
        'Burkina Faso',
        'BF',
        12.3667,
        -1.5167,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Bobo-Dioulasso Market',
        'wholesale',
        'Hauts-Bassins',
        'Burkina Faso',
        'BF',
        11.1771,
        -4.2979,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Koudougou Market',
        'wholesale',
        'Centre-Ouest',
        'Burkina Faso',
        'BF',
        12.2522,
        -2.3622,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Ouahigouya Market',
        'wholesale',
        'Nord',
        'Burkina Faso',
        'BF',
        13.5833,
        -2.4167,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Banfora Market',
        'wholesale',
        'Cascades',
        'Burkina Faso',
        'BF',
        10.6333,
        -4.7667,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Dédougou Market',
        'wholesale',
        'Boucle du Mouhoun',
        'Burkina Faso',
        'BF',
        12.4667,
        -3.4667,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Kaya Market',
        'wholesale',
        'Centre-Nord',
        'Burkina Faso',
        'BF',
        13.0833,
        -1.0833,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Tenkodogo Market',
        'wholesale',
        'Centre-Est',
        'Burkina Faso',
        'BF',
        11.7833,
        -0.3667,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    ),
    (
        'Fada N''Gourma Market',
        'wholesale',
        'Est',
        'Burkina Faso',
        'BF',
        12.0667,
        0.3667,
        'XOF',
        'Africa/Ouagadougou',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- MALI — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Bamako Central Market',
        'wholesale',
        'Bamako',
        'Mali',
        'ML',
        12.6392,
        -8.0029,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Marché Rose',
        'retail',
        'Bamako',
        'Mali',
        'ML',
        12.6500,
        -8.0000,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Sikasso Market',
        'wholesale',
        'Sikasso',
        'Mali',
        'ML',
        11.3176,
        -5.6665,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Mopti Market',
        'wholesale',
        'Mopti',
        'Mali',
        'ML',
        14.4843,
        -4.1829,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Ségou Market',
        'wholesale',
        'Ségou',
        'Mali',
        'ML',
        13.4317,
        -6.2157,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Kayes Market',
        'wholesale',
        'Kayes',
        'Mali',
        'ML',
        14.4469,
        -11.4445,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Gao Market',
        'wholesale',
        'Gao',
        'Mali',
        'ML',
        16.2717,
        -0.0447,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Timbuktu Market',
        'wholesale',
        'Tombouctou',
        'Mali',
        'ML',
        16.7735,
        -3.0074,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Koutiala Market',
        'wholesale',
        'Sikasso',
        'Mali',
        'ML',
        12.3917,
        -5.4642,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    ),
    (
        'Nioro Market',
        'wholesale',
        'Kayes',
        'Mali',
        'ML',
        15.2333,
        -9.5833,
        'XOF',
        'Africa/Bamako',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- NIGER — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Niamey Grand Marché',
        'wholesale',
        'Niamey',
        'Niger',
        'NE',
        13.5116,
        2.1254,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Petit Marché Niamey',
        'retail',
        'Niamey',
        'Niger',
        'NE',
        13.5167,
        2.1167,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Zinder Market',
        'wholesale',
        'Zinder',
        'Niger',
        'NE',
        13.8000,
        8.9833,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Maradi Market',
        'wholesale',
        'Maradi',
        'Niger',
        'NE',
        13.4833,
        7.1000,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Agadez Market',
        'wholesale',
        'Agadez',
        'Niger',
        'NE',
        16.9733,
        7.9911,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Tahoua Market',
        'wholesale',
        'Tahoua',
        'Niger',
        'NE',
        14.8888,
        5.2692,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Dosso Market',
        'wholesale',
        'Dosso',
        'Niger',
        'NE',
        13.0490,
        3.1937,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Tillabéri Market',
        'wholesale',
        'Tillabéri',
        'Niger',
        'NE',
        14.2117,
        1.4531,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Diffa Market',
        'wholesale',
        'Diffa',
        'Niger',
        'NE',
        13.3154,
        12.6113,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    ),
    (
        'Birni N''Konni Market',
        'wholesale',
        'Tahoua',
        'Niger',
        'NE',
        13.7956,
        5.2500,
        'XOF',
        'Africa/Niamey',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- CHAD — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'N''Djamena Central Market',
        'wholesale',
        'N''Djamena',
        'Chad',
        'TD',
        12.1348,
        15.0557,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Marché Central N''Djamena',
        'retail',
        'N''Djamena',
        'Chad',
        'TD',
        12.1167,
        15.0500,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Moundou Market',
        'wholesale',
        'Logone Occidental',
        'Chad',
        'TD',
        8.5667,
        16.0833,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Sarh Market',
        'wholesale',
        'Moyen-Chari',
        'Chad',
        'TD',
        9.1429,
        18.3922,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Abéché Market',
        'wholesale',
        'Ouaddaï',
        'Chad',
        'TD',
        13.8292,
        20.8324,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Kelo Market',
        'wholesale',
        'Mayo-Kebbi Est',
        'Chad',
        'TD',
        9.3086,
        15.8078,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Koumra Market',
        'wholesale',
        'Mandoul',
        'Chad',
        'TD',
        8.9125,
        17.5539,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Pala Market',
        'wholesale',
        'Mayo-Kebbi Ouest',
        'Chad',
        'TD',
        9.3642,
        14.9042,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Am Timan Market',
        'wholesale',
        'Salamat',
        'Chad',
        'TD',
        11.0297,
        20.2825,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    ),
    (
        'Bongor Market',
        'wholesale',
        'Mayo-Kebbi Est',
        'Chad',
        'TD',
        10.2806,
        15.3722,
        'XAF',
        'Africa/Ndjamena',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- CENTRAL AFRICAN REPUBLIC — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Bangui Central Market',
        'wholesale',
        'Bangui',
        'Central African Republic',
        'CF',
        4.3947,
        18.5582,
        'XAF',
        'Africa/Bangui',
        'FEWS NET'
    ),
    (
        'Marché PK5',
        'retail',
        'Bangui',
        'Central African Republic',
        'CF',
        4.3667,
        18.5500,
        'XAF',
        'Africa/Bangui',
        'FEWS NET'
    ),
    (
        'Bimbo Market',
        'wholesale',
        'Ombella-M''Poko',
        'Central African Republic',
        'CF',
        4.3333,
        18.5167,
        'XAF',
        'Africa/Bangui',
        'FEWS NET'
    ),
    (
        'Berbérati Market',
        'wholesale',
        'Mambéré-Kadéï',
        'Central African Republic',
        'CF',
        4.2614,
        15.7922,
        'XAF',
        'Africa/Bangui',
        'FEWS NET'
    ),
    (
        'Bambari Market',
        'wholesale',
        'Ouaka',
        'Central African Republic',
        'CF',
        5.7667,
        20.6833,
        'XAF',
        'Africa/Bangui',
        'FEWS NET'
    ),
    (
        'Bouar Market',
        'wholesale',
        'Nana-Mambéré',
        'Central African Republic',
        'CF',
        5.9500,
        15.6000,
        'XAF',
        'Africa/Bangui',
        'FEWS NET'
    ),
    (
        'Bossangoa Market',
        'wholesale',
        'Ouham',
        'Central African Republic',
        'CF',
        6.4925,
        17.4550,
        'XAF',
        'Africa/Bangui',
        'FEWS NET'
    ),
    (
        'Nola Market',
        'wholesale',
        'Sangha-Mbaéré',
        'Central African Republic',
        'CF',
        3.5333,
        16.0500,
        'XAF',
        'Africa/Bangui',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- REPUBLIC OF THE CONGO — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Brazzaville Central Market',
        'wholesale',
        'Brazzaville',
        'Congo',
        'CG',
        -4.2634,
        15.2429,
        'XAF',
        'Africa/Brazzaville',
        'FEWS NET'
    ),
    (
        'Marché Total',
        'retail',
        'Brazzaville',
        'Congo',
        'CG',
        -4.2667,
        15.2833,
        'XAF',
        'Africa/Brazzaville',
        'FEWS NET'
    ),
    (
        'Pointe-Noire Market',
        'wholesale',
        'Pointe-Noire',
        'Congo',
        'CG',
        -4.7889,
        11.8653,
        'XAF',
        'Africa/Brazzaville',
        'FEWS NET'
    ),
    (
        'Dolisie Market',
        'wholesale',
        'Niari',
        'Congo',
        'CG',
        -4.1997,
        12.6739,
        'XAF',
        'Africa/Brazzaville',
        'FEWS NET'
    ),
    (
        'Nkayi Market',
        'wholesale',
        'Bouenza',
        'Congo',
        'CG',
        -4.1833,
        13.2833,
        'XAF',
        'Africa/Brazzaville',
        'FEWS NET'
    ),
    (
        'Owando Market',
        'wholesale',
        'Cuvette',
        'Congo',
        'CG',
        -0.4819,
        15.8997,
        'XAF',
        'Africa/Brazzaville',
        'FEWS NET'
    ),
    (
        'Ouesso Market',
        'wholesale',
        'Sangha',
        'Congo',
        'CG',
        1.6136,
        16.0517,
        'XAF',
        'Africa/Brazzaville',
        'FEWS NET'
    ),
    (
        'Impfondo Market',
        'wholesale',
        'Likouala',
        'Congo',
        'CG',
        1.6186,
        18.0597,
        'XAF',
        'Africa/Brazzaville',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- GABON — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Libreville Central Market',
        'wholesale',
        'Estuaire',
        'Gabon',
        'GA',
        0.4162,
        9.4673,
        'XAF',
        'Africa/Libreville',
        'FEWS NET'
    ),
    (
        'Marché Mont-Bouët',
        'wholesale',
        'Estuaire',
        'Gabon',
        'GA',
        0.4000,
        9.4500,
        'XAF',
        'Africa/Libreville',
        'FEWS NET'
    ),
    (
        'Port-Gentil Market',
        'wholesale',
        'Ogooué-Maritime',
        'Gabon',
        'GA',
        -0.7193,
        8.7815,
        'XAF',
        'Africa/Libreville',
        'FEWS NET'
    ),
    (
        'Franceville Market',
        'wholesale',
        'Haut-Ogooué',
        'Gabon',
        'GA',
        -1.6333,
        13.5833,
        'XAF',
        'Africa/Libreville',
        'FEWS NET'
    ),
    (
        'Oyem Market',
        'wholesale',
        'Woleu-Ntem',
        'Gabon',
        'GA',
        1.5994,
        11.5794,
        'XAF',
        'Africa/Libreville',
        'FEWS NET'
    ),
    (
        'Lambaréné Market',
        'wholesale',
        'Moyen-Ogooué',
        'Gabon',
        'GA',
        -0.7000,
        10.2333,
        'XAF',
        'Africa/Libreville',
        'FEWS NET'
    ),
    (
        'Mouila Market',
        'wholesale',
        'Ngounié',
        'Gabon',
        'GA',
        -1.8667,
        11.0167,
        'XAF',
        'Africa/Libreville',
        'FEWS NET'
    ),
    (
        'Tchibanga Market',
        'wholesale',
        'Nyanga',
        'Gabon',
        'GA',
        -2.9333,
        10.9833,
        'XAF',
        'Africa/Libreville',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- EQUATORIAL GUINEA — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Malabo Market',
        'wholesale',
        'Bioko Norte',
        'Equatorial Guinea',
        'GQ',
        3.7500,
        8.7833,
        'XAF',
        'Africa/Malabo',
        'FEWS NET'
    ),
    (
        'Bata Market',
        'wholesale',
        'Litoral',
        'Equatorial Guinea',
        'GQ',
        1.8639,
        9.7658,
        'XAF',
        'Africa/Malabo',
        'FEWS NET'
    ),
    (
        'Ebebiyín Market',
        'wholesale',
        'Kié-Ntem',
        'Equatorial Guinea',
        'GQ',
        2.1500,
        11.3333,
        'XAF',
        'Africa/Malabo',
        'FEWS NET'
    ),
    (
        'Mongomo Market',
        'wholesale',
        'Wele-Nzas',
        'Equatorial Guinea',
        'GQ',
        1.6286,
        11.3153,
        'XAF',
        'Africa/Malabo',
        'FEWS NET'
    ),
    (
        'Luba Market',
        'wholesale',
        'Bioko Sur',
        'Equatorial Guinea',
        'GQ',
        3.4500,
        8.5500,
        'XAF',
        'Africa/Malabo',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- BENIN — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Cotonou Central Market',
        'wholesale',
        'Littoral',
        'Benin',
        'BJ',
        6.3703,
        2.3912,
        'XOF',
        'Africa/Porto-Novo',
        'FEWS NET'
    ),
    (
        'Dantokpa Market',
        'wholesale',
        'Littoral',
        'Benin',
        'BJ',
        6.3667,
        2.4333,
        'XOF',
        'Africa/Porto-Novo',
        'FEWS NET'
    ),
    (
        'Porto-Novo Market',
        'wholesale',
        'Ouémé',
        'Benin',
        'BJ',
        6.4969,
        2.6289,
        'XOF',
        'Africa/Porto-Novo',
        'FEWS NET'
    ),
    (
        'Parakou Market',
        'wholesale',
        'Borgou',
        'Benin',
        'BJ',
        9.3372,
        2.6303,
        'XOF',
        'Africa/Porto-Novo',
        'FEWS NET'
    ),
    (
        'Abomey-Calavi Market',
        'wholesale',
        'Atlantique',
        'Benin',
        'BJ',
        6.4489,
        2.3556,
        'XOF',
        'Africa/Porto-Novo',
        'FEWS NET'
    ),
    (
        'Bohicon Market',
        'wholesale',
        'Zou',
        'Benin',
        'BJ',
        7.1783,
        2.0667,
        'XOF',
        'Africa/Porto-Novo',
        'FEWS NET'
    ),
    (
        'Natitingou Market',
        'wholesale',
        'Atakora',
        'Benin',
        'BJ',
        10.3042,
        1.3797,
        'XOF',
        'Africa/Porto-Novo',
        'FEWS NET'
    ),
    (
        'Lokossa Market',
        'wholesale',
        'Mono',
        'Benin',
        'BJ',
        6.6389,
        1.7167,
        'XOF',
        'Africa/Porto-Novo',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- TOGO — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Lomé Central Market',
        'wholesale',
        'Maritime',
        'Togo',
        'TG',
        6.1375,
        1.2123,
        'XOF',
        'Africa/Lome',
        'FEWS NET'
    ),
    (
        'Grand Marché de Lomé',
        'wholesale',
        'Maritime',
        'Togo',
        'TG',
        6.1333,
        1.2167,
        'XOF',
        'Africa/Lome',
        'FEWS NET'
    ),
    (
        'Sokodé Market',
        'wholesale',
        'Centrale',
        'Togo',
        'TG',
        8.9833,
        1.1333,
        'XOF',
        'Africa/Lome',
        'FEWS NET'
    ),
    (
        'Kara Market',
        'wholesale',
        'Kara',
        'Togo',
        'TG',
        9.5511,
        1.1861,
        'XOF',
        'Africa/Lome',
        'FEWS NET'
    ),
    (
        'Kpalimé Market',
        'wholesale',
        'Plateaux',
        'Togo',
        'TG',
        6.9000,
        0.6333,
        'XOF',
        'Africa/Lome',
        'FEWS NET'
    ),
    (
        'Atakpamé Market',
        'wholesale',
        'Plateaux',
        'Togo',
        'TG',
        7.5333,
        1.1267,
        'XOF',
        'Africa/Lome',
        'FEWS NET'
    ),
    (
        'Dapaong Market',
        'wholesale',
        'Savanes',
        'Togo',
        'TG',
        10.8639,
        0.2075,
        'XOF',
        'Africa/Lome',
        'FEWS NET'
    ),
    (
        'Tsévié Market',
        'wholesale',
        'Maritime',
        'Togo',
        'TG',
        6.4261,
        1.2133,
        'XOF',
        'Africa/Lome',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- GUINEA — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Conakry Central Market',
        'wholesale',
        'Conakry',
        'Guinea',
        'GN',
        9.6412,
        -13.5784,
        'GNF',
        'Africa/Conakry',
        'FEWS NET'
    ),
    (
        'Marché Madina',
        'wholesale',
        'Conakry',
        'Guinea',
        'GN',
        9.6333,
        -13.5667,
        'GNF',
        'Africa/Conakry',
        'FEWS NET'
    ),
    (
        'Kankan Market',
        'wholesale',
        'Kankan',
        'Guinea',
        'GN',
        10.3856,
        -9.3056,
        'GNF',
        'Africa/Conakry',
        'FEWS NET'
    ),
    (
        'Nzérékoré Market',
        'wholesale',
        'Nzérékoré',
        'Guinea',
        'GN',
        7.7561,
        -8.8172,
        'GNF',
        'Africa/Conakry',
        'FEWS NET'
    ),
    (
        'Kindia Market',
        'wholesale',
        'Kindia',
        'Guinea',
        'GN',
        10.0567,
        -12.8658,
        'GNF',
        'Africa/Conakry',
        'FEWS NET'
    ),
    (
        'Labé Market',
        'wholesale',
        'Labé',
        'Guinea',
        'GN',
        11.3181,
        -12.2836,
        'GNF',
        'Africa/Conakry',
        'FEWS NET'
    ),
    (
        'Boké Market',
        'wholesale',
        'Boké',
        'Guinea',
        'GN',
        10.9333,
        -14.3000,
        'GNF',
        'Africa/Conakry',
        'FEWS NET'
    ),
    (
        'Mamou Market',
        'wholesale',
        'Mamou',
        'Guinea',
        'GN',
        10.3750,
        -12.0917,
        'GNF',
        'Africa/Conakry',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- SIERRA LEONE — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Freetown Central Market',
        'wholesale',
        'Western Area',
        'Sierra Leone',
        'SL',
        8.4844,
        -13.2344,
        'SLL',
        'Africa/Freetown',
        'FEWS NET'
    ),
    (
        'Marché King Jimmy',
        'retail',
        'Western Area',
        'Sierra Leone',
        'SL',
        8.4833,
        -13.2333,
        'SLL',
        'Africa/Freetown',
        'FEWS NET'
    ),
    (
        'Bo Market',
        'wholesale',
        'Southern',
        'Sierra Leone',
        'SL',
        7.9647,
        -11.7383,
        'SLL',
        'Africa/Freetown',
        'FEWS NET'
    ),
    (
        'Kenema Market',
        'wholesale',
        'Eastern',
        'Sierra Leone',
        'SL',
        7.8767,
        -11.1875,
        'SLL',
        'Africa/Freetown',
        'FEWS NET'
    ),
    (
        'Makeni Market',
        'wholesale',
        'Northern',
        'Sierra Leone',
        'SL',
        8.8833,
        -12.0500,
        'SLL',
        'Africa/Freetown',
        'FEWS NET'
    ),
    (
        'Koidu Market',
        'wholesale',
        'Eastern',
        'Sierra Leone',
        'SL',
        8.6439,
        -10.9714,
        'SLL',
        'Africa/Freetown',
        'FEWS NET'
    ),
    (
        'Lunsar Market',
        'wholesale',
        'Northern',
        'Sierra Leone',
        'SL',
        8.6833,
        -12.5333,
        'SLL',
        'Africa/Freetown',
        'FEWS NET'
    ),
    (
        'Port Loko Market',
        'wholesale',
        'Northern',
        'Sierra Leone',
        'SL',
        8.7667,
        -12.7833,
        'SLL',
        'Africa/Freetown',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- LIBERIA — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Monrovia Central Market',
        'wholesale',
        'Montserrado',
        'Liberia',
        'LR',
        6.3106,
        -10.8047,
        'LRD',
        'Africa/Monrovia',
        'FEWS NET'
    ),
    (
        'Waterside Market',
        'wholesale',
        'Montserrado',
        'Liberia',
        'LR',
        6.3167,
        -10.8000,
        'LRD',
        'Africa/Monrovia',
        'FEWS NET'
    ),
    (
        'Gbarnga Market',
        'wholesale',
        'Bong',
        'Liberia',
        'LR',
        6.9956,
        -9.4711,
        'LRD',
        'Africa/Monrovia',
        'FEWS NET'
    ),
    (
        'Buchanan Market',
        'wholesale',
        'Grand Bassa',
        'Liberia',
        'LR',
        5.8808,
        -10.0467,
        'LRD',
        'Africa/Monrovia',
        'FEWS NET'
    ),
    (
        'Kakata Market',
        'wholesale',
        'Margibi',
        'Liberia',
        'LR',
        6.5300,
        -10.3517,
        'LRD',
        'Africa/Monrovia',
        'FEWS NET'
    ),
    (
        'Voinjama Market',
        'wholesale',
        'Lofa',
        'Liberia',
        'LR',
        8.4219,
        -9.7478,
        'LRD',
        'Africa/Monrovia',
        'FEWS NET'
    ),
    (
        'Harper Market',
        'wholesale',
        'Maryland',
        'Liberia',
        'LR',
        4.3750,
        -7.7169,
        'LRD',
        'Africa/Monrovia',
        'FEWS NET'
    ),
    (
        'Zwedru Market',
        'wholesale',
        'Grand Gedeh',
        'Liberia',
        'LR',
        6.0667,
        -8.1281,
        'LRD',
        'Africa/Monrovia',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- GUINEA-BISSAU — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Bissau Central Market',
        'wholesale',
        'Bissau',
        'Guinea-Bissau',
        'GW',
        11.8636,
        -15.5977,
        'XOF',
        'Africa/Bissau',
        'FEWS NET'
    ),
    (
        'Marché de Bandim',
        'retail',
        'Bissau',
        'Guinea-Bissau',
        'GW',
        11.8500,
        -15.5833,
        'XOF',
        'Africa/Bissau',
        'FEWS NET'
    ),
    (
        'Bafatá Market',
        'wholesale',
        'Bafatá',
        'Guinea-Bissau',
        'GW',
        12.1658,
        -14.6617,
        'XOF',
        'Africa/Bissau',
        'FEWS NET'
    ),
    (
        'Gabú Market',
        'wholesale',
        'Gabú',
        'Guinea-Bissau',
        'GW',
        12.2800,
        -14.2222,
        'XOF',
        'Africa/Bissau',
        'FEWS NET'
    ),
    (
        'Cacheu Market',
        'wholesale',
        'Cacheu',
        'Guinea-Bissau',
        'GW',
        12.2744,
        -16.1650,
        'XOF',
        'Africa/Bissau',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- GAMBIA — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Banjul Central Market',
        'wholesale',
        'Banjul',
        'Gambia',
        'GM',
        13.4531,
        -16.5775,
        'GMD',
        'Africa/Banjul',
        'FEWS NET'
    ),
    (
        'Serrekunda Market',
        'wholesale',
        'Kanifing',
        'Gambia',
        'GM',
        13.4383,
        -16.6781,
        'GMD',
        'Africa/Banjul',
        'FEWS NET'
    ),
    (
        'Brikama Market',
        'wholesale',
        'West Coast',
        'Gambia',
        'GM',
        13.2667,
        -16.6500,
        'GMD',
        'Africa/Banjul',
        'FEWS NET'
    ),
    (
        'Farafenni Market',
        'wholesale',
        'North Bank',
        'Gambia',
        'GM',
        13.5667,
        -15.6000,
        'GMD',
        'Africa/Banjul',
        'FEWS NET'
    ),
    (
        'Basse Santa Su Market',
        'wholesale',
        'Upper River',
        'Gambia',
        'GM',
        13.3167,
        -14.2167,
        'GMD',
        'Africa/Banjul',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- MAURITANIA — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Nouakchott Central Market',
        'wholesale',
        'Nouakchott',
        'Mauritania',
        'MR',
        18.0735,
        -15.9582,
        'MRU',
        'Africa/Nouakchott',
        'FEWS NET'
    ),
    (
        'Marché Capitale',
        'retail',
        'Nouakchott',
        'Mauritania',
        'MR',
        18.0833,
        -15.9667,
        'MRU',
        'Africa/Nouakchott',
        'FEWS NET'
    ),
    (
        'Nouadhibou Market',
        'wholesale',
        'Dakhlet Nouadhibou',
        'Mauritania',
        'MR',
        20.9310,
        -17.0347,
        'MRU',
        'Africa/Nouakchott',
        'FEWS NET'
    ),
    (
        'Rosso Market',
        'wholesale',
        'Trarza',
        'Mauritania',
        'MR',
        16.5138,
        -15.8053,
        'MRU',
        'Africa/Nouakchott',
        'FEWS NET'
    ),
    (
        'Kaédi Market',
        'wholesale',
        'Gorgol',
        'Mauritania',
        'MR',
        16.1500,
        -13.5000,
        'MRU',
        'Africa/Nouakchott',
        'FEWS NET'
    ),
    (
        'Zouérat Market',
        'wholesale',
        'Tiris Zemmour',
        'Mauritania',
        'MR',
        22.7344,
        -12.4725,
        'MRU',
        'Africa/Nouakchott',
        'FEWS NET'
    ),
    (
        'Atar Market',
        'wholesale',
        'Adrar',
        'Mauritania',
        'MR',
        20.5169,
        -13.0500,
        'MRU',
        'Africa/Nouakchott',
        'FEWS NET'
    ),
    (
        'Aleg Market',
        'wholesale',
        'Brakna',
        'Mauritania',
        'MR',
        17.0500,
        -13.9167,
        'MRU',
        'Africa/Nouakchott',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- WESTERN SAHARA — 3
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Laayoune Market',
        'wholesale',
        'Laâyoune-Sakia El Hamra',
        'Western Sahara',
        'EH',
        27.1418,
        -13.1875,
        'MAD',
        'Africa/El_Aaiun',
        'FEWS NET'
    ),
    (
        'Dakhla Market',
        'wholesale',
        'Dakhla-Oued Ed-Dahab',
        'Western Sahara',
        'EH',
        23.6848,
        -15.9580,
        'MAD',
        'Africa/El_Aaiun',
        'FEWS NET'
    ),
    (
        'Smara Market',
        'wholesale',
        'Laâyoune-Sakia El Hamra',
        'Western Sahara',
        'EH',
        26.7384,
        -11.6719,
        'MAD',
        'Africa/El_Aaiun',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- ALGERIA — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Algiers Central Market',
        'wholesale',
        'Algiers',
        'Algeria',
        'DZ',
        36.7538,
        3.0588,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Marché d''Alger',
        'retail',
        'Algiers',
        'Algeria',
        'DZ',
        36.7667,
        3.0500,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Oran Market',
        'wholesale',
        'Oran',
        'Algeria',
        'DZ',
        35.6971,
        -0.6308,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Constantine Market',
        'wholesale',
        'Constantine',
        'Algeria',
        'DZ',
        36.3650,
        6.6147,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Annaba Market',
        'wholesale',
        'Annaba',
        'Algeria',
        'DZ',
        36.9000,
        7.7667,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Blida Market',
        'wholesale',
        'Blida',
        'Algeria',
        'DZ',
        36.4703,
        2.8277,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Batna Market',
        'wholesale',
        'Batna',
        'Algeria',
        'DZ',
        35.5550,
        6.1741,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Djelfa Market',
        'wholesale',
        'Djelfa',
        'Algeria',
        'DZ',
        34.6728,
        3.2631,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Sétif Market',
        'wholesale',
        'Sétif',
        'Algeria',
        'DZ',
        36.1898,
        5.4108,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    ),
    (
        'Tlemcen Market',
        'wholesale',
        'Tlemcen',
        'Algeria',
        'DZ',
        34.8783,
        -1.3150,
        'DZD',
        'Africa/Algiers',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- LIBYA — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Tripoli Central Market',
        'wholesale',
        'Tripoli',
        'Libya',
        'LY',
        32.8872,
        13.1913,
        'LYD',
        'Africa/Tripoli',
        'FEWS NET'
    ),
    (
        'Marché de Tripoli',
        'retail',
        'Tripoli',
        'Libya',
        'LY',
        32.9000,
        13.1833,
        'LYD',
        'Africa/Tripoli',
        'FEWS NET'
    ),
    (
        'Benghazi Market',
        'wholesale',
        'Benghazi',
        'Libya',
        'LY',
        32.1167,
        20.0667,
        'LYD',
        'Africa/Tripoli',
        'FEWS NET'
    ),
    (
        'Misrata Market',
        'wholesale',
        'Misrata',
        'Libya',
        'LY',
        32.3775,
        15.0920,
        'LYD',
        'Africa/Tripoli',
        'FEWS NET'
    ),
    (
        'Zliten Market',
        'wholesale',
        'Murqub',
        'Libya',
        'LY',
        32.4667,
        14.5667,
        'LYD',
        'Africa/Tripoli',
        'FEWS NET'
    ),
    (
        'Sabha Market',
        'wholesale',
        'Sabha',
        'Libya',
        'LY',
        27.0377,
        14.4283,
        'LYD',
        'Africa/Tripoli',
        'FEWS NET'
    ),
    (
        'Tobruk Market',
        'wholesale',
        'Butnan',
        'Libya',
        'LY',
        32.0833,
        23.9500,
        'LYD',
        'Africa/Tripoli',
        'FEWS NET'
    ),
    (
        'Zawiya Market',
        'wholesale',
        'Zawiya',
        'Libya',
        'LY',
        32.7522,
        12.7278,
        'LYD',
        'Africa/Tripoli',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- ERITREA — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Asmara Central Market',
        'wholesale',
        'Maekel',
        'Eritrea',
        'ER',
        15.3381,
        38.9318,
        'ERN',
        'Africa/Asmara',
        'FEWS NET'
    ),
    (
        'Marché d''Asmara',
        'retail',
        'Maekel',
        'Eritrea',
        'ER',
        15.3333,
        38.9333,
        'ERN',
        'Africa/Asmara',
        'FEWS NET'
    ),
    (
        'Keren Market',
        'wholesale',
        'Anseba',
        'Eritrea',
        'ER',
        15.7778,
        38.4511,
        'ERN',
        'Africa/Asmara',
        'FEWS NET'
    ),
    (
        'Massawa Market',
        'wholesale',
        'Northern Red Sea',
        'Eritrea',
        'ER',
        15.6097,
        39.4500,
        'ERN',
        'Africa/Asmara',
        'FEWS NET'
    ),
    (
        'Assab Market',
        'wholesale',
        'Southern Red Sea',
        'Eritrea',
        'ER',
        13.0092,
        42.7394,
        'ERN',
        'Africa/Asmara',
        'FEWS NET'
    ),
    (
        'Mendefera Market',
        'wholesale',
        'Debub',
        'Eritrea',
        'ER',
        14.8872,
        38.8153,
        'ERN',
        'Africa/Asmara',
        'FEWS NET'
    ),
    (
        'Barentu Market',
        'wholesale',
        'Gash-Barka',
        'Eritrea',
        'ER',
        15.1058,
        37.5906,
        'ERN',
        'Africa/Asmara',
        'FEWS NET'
    ),
    (
        'Adi Keyh Market',
        'wholesale',
        'Debub',
        'Eritrea',
        'ER',
        14.8444,
        39.3772,
        'ERN',
        'Africa/Asmara',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- DJIBOUTI — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Djibouti Central Market',
        'wholesale',
        'Djibouti',
        'Djibouti',
        'DJ',
        11.5880,
        43.1450,
        'DJF',
        'Africa/Djibouti',
        'FEWS NET'
    ),
    (
        'Marché de Djibouti',
        'retail',
        'Djibouti',
        'Djibouti',
        'DJ',
        11.5833,
        43.1500,
        'DJF',
        'Africa/Djibouti',
        'FEWS NET'
    ),
    (
        'Ali Sabieh Market',
        'wholesale',
        'Ali Sabieh',
        'Djibouti',
        'DJ',
        11.1558,
        42.7125,
        'DJF',
        'Africa/Djibouti',
        'FEWS NET'
    ),
    (
        'Tadjourah Market',
        'wholesale',
        'Tadjourah',
        'Djibouti',
        'DJ',
        11.7878,
        42.8822,
        'DJF',
        'Africa/Djibouti',
        'FEWS NET'
    ),
    (
        'Obock Market',
        'wholesale',
        'Obock',
        'Djibouti',
        'DJ',
        11.9631,
        43.2906,
        'DJF',
        'Africa/Djibouti',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- SOMALIA — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Mogadishu Central Market',
        'wholesale',
        'Banadir',
        'Somalia',
        'SO',
        2.0469,
        45.3182,
        'SOS',
        'Africa/Mogadishu',
        'FEWS NET'
    ),
    (
        'Bakara Market',
        'wholesale',
        'Banadir',
        'Somalia',
        'SO',
        2.0333,
        45.3333,
        'SOS',
        'Africa/Mogadishu',
        'FEWS NET'
    ),
    (
        'Hargeisa Market',
        'wholesale',
        'Woqooyi Galbeed',
        'Somalia',
        'SO',
        9.5600,
        44.0650,
        'SOS',
        'Africa/Mogadishu',
        'FEWS NET'
    ),
    (
        'Bosaso Market',
        'wholesale',
        'Bari',
        'Somalia',
        'SO',
        11.2842,
        49.1816,
        'SOS',
        'Africa/Mogadishu',
        'FEWS NET'
    ),
    (
        'Kismayo Market',
        'wholesale',
        'Lower Juba',
        'Somalia',
        'SO',
        -0.3582,
        42.5454,
        'SOS',
        'Africa/Mogadishu',
        'FEWS NET'
    ),
    (
        'Baidoa Market',
        'wholesale',
        'Bay',
        'Somalia',
        'SO',
        3.1167,
        43.6500,
        'SOS',
        'Africa/Mogadishu',
        'FEWS NET'
    ),
    (
        'Galkayo Market',
        'wholesale',
        'Mudug',
        'Somalia',
        'SO',
        6.7697,
        47.4308,
        'SOS',
        'Africa/Mogadishu',
        'FEWS NET'
    ),
    (
        'Beledweyne Market',
        'wholesale',
        'Hiran',
        'Somalia',
        'SO',
        4.7358,
        45.2036,
        'SOS',
        'Africa/Mogadishu',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- SOUTH SUDAN — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Juba Central Market',
        'wholesale',
        'Central Equatoria',
        'South Sudan',
        'SS',
        4.8517,
        31.5825,
        'SSP',
        'Africa/Juba',
        'FEWS NET'
    ),
    (
        'Konyo Konyo Market',
        'wholesale',
        'Central Equatoria',
        'South Sudan',
        'SS',
        4.8333,
        31.6000,
        'SSP',
        'Africa/Juba',
        'FEWS NET'
    ),
    (
        'Wau Market',
        'wholesale',
        'Western Bahr el Ghazal',
        'South Sudan',
        'SS',
        7.7029,
        28.0000,
        'SSP',
        'Africa/Juba',
        'FEWS NET'
    ),
    (
        'Malakal Market',
        'wholesale',
        'Upper Nile',
        'South Sudan',
        'SS',
        9.5333,
        31.6500,
        'SSP',
        'Africa/Juba',
        'FEWS NET'
    ),
    (
        'Yei Market',
        'wholesale',
        'Central Equatoria',
        'South Sudan',
        'SS',
        4.0944,
        30.6778,
        'SSP',
        'Africa/Juba',
        'FEWS NET'
    ),
    (
        'Aweil Market',
        'wholesale',
        'Northern Bahr el Ghazal',
        'South Sudan',
        'SS',
        8.7667,
        27.4000,
        'SSP',
        'Africa/Juba',
        'FEWS NET'
    ),
    (
        'Rumbek Market',
        'wholesale',
        'Lakes',
        'South Sudan',
        'SS',
        6.8000,
        29.6833,
        'SSP',
        'Africa/Juba',
        'FEWS NET'
    ),
    (
        'Torit Market',
        'wholesale',
        'Eastern Equatoria',
        'South Sudan',
        'SS',
        4.4117,
        32.5700,
        'SSP',
        'Africa/Juba',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- BURUNDI — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Bujumbura Central Market',
        'wholesale',
        'Bujumbura Mairie',
        'Burundi',
        'BI',
        -3.3822,
        29.3644,
        'BIF',
        'Africa/Bujumbura',
        'FEWS NET'
    ),
    (
        'Marché Central de Bujumbura',
        'retail',
        'Bujumbura Mairie',
        'Burundi',
        'BI',
        -3.3833,
        29.3667,
        'BIF',
        'Africa/Bujumbura',
        'FEWS NET'
    ),
    (
        'Gitega Market',
        'wholesale',
        'Gitega',
        'Burundi',
        'BI',
        -3.4264,
        29.9244,
        'BIF',
        'Africa/Bujumbura',
        'FEWS NET'
    ),
    (
        'Ngozi Market',
        'wholesale',
        'Ngozi',
        'Burundi',
        'BI',
        -2.9075,
        29.8306,
        'BIF',
        'Africa/Bujumbura',
        'FEWS NET'
    ),
    (
        'Rumonge Market',
        'wholesale',
        'Rumonge',
        'Burundi',
        'BI',
        -3.9736,
        29.4386,
        'BIF',
        'Africa/Bujumbura',
        'FEWS NET'
    ),
    (
        'Muyinga Market',
        'wholesale',
        'Muyinga',
        'Burundi',
        'BI',
        -2.8453,
        30.3414,
        'BIF',
        'Africa/Bujumbura',
        'FEWS NET'
    ),
    (
        'Ruyigi Market',
        'wholesale',
        'Ruyigi',
        'Burundi',
        'BI',
        -3.4764,
        30.2489,
        'BIF',
        'Africa/Bujumbura',
        'FEWS NET'
    ),
    (
        'Makamba Market',
        'wholesale',
        'Makamba',
        'Burundi',
        'BI',
        -4.1347,
        29.8042,
        'BIF',
        'Africa/Bujumbura',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- MALAWI — 8
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Lilongwe Central Market',
        'wholesale',
        'Central',
        'Malawi',
        'MW',
        -13.9833,
        33.7833,
        'MWK',
        'Africa/Blantyre',
        'FEWS NET'
    ),
    (
        'Blantyre Market',
        'wholesale',
        'Southern',
        'Malawi',
        'MW',
        -15.7861,
        35.0058,
        'MWK',
        'Africa/Blantyre',
        'FEWS NET'
    ),
    (
        'Mzuzu Market',
        'wholesale',
        'Northern',
        'Malawi',
        'MW',
        -11.4656,
        34.0219,
        'MWK',
        'Africa/Blantyre',
        'FEWS NET'
    ),
    (
        'Zomba Market',
        'wholesale',
        'Southern',
        'Malawi',
        'MW',
        -15.3861,
        35.3189,
        'MWK',
        'Africa/Blantyre',
        'FEWS NET'
    ),
    (
        'Kasungu Market',
        'wholesale',
        'Central',
        'Malawi',
        'MW',
        -13.0333,
        33.4833,
        'MWK',
        'Africa/Blantyre',
        'FEWS NET'
    ),
    (
        'Mangochi Market',
        'wholesale',
        'Southern',
        'Malawi',
        'MW',
        -14.4781,
        35.2644,
        'MWK',
        'Africa/Blantyre',
        'FEWS NET'
    ),
    (
        'Salima Market',
        'wholesale',
        'Central',
        'Malawi',
        'MW',
        -13.7806,
        34.4586,
        'MWK',
        'Africa/Blantyre',
        'FEWS NET'
    ),
    (
        'Karonga Market',
        'wholesale',
        'Northern',
        'Malawi',
        'MW',
        -9.9333,
        33.9333,
        'MWK',
        'Africa/Blantyre',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- MADAGASCAR — 10
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Antananarivo Central Market',
        'wholesale',
        'Analamanga',
        'Madagascar',
        'MG',
        -18.9137,
        47.5361,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Marché d''Analakely',
        'wholesale',
        'Analamanga',
        'Madagascar',
        'MG',
        -18.9089,
        47.5258,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Toamasina Market',
        'wholesale',
        'Atsinanana',
        'Madagascar',
        'MG',
        -18.1492,
        49.4022,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Antsirabe Market',
        'wholesale',
        'Vakinankaratra',
        'Madagascar',
        'MG',
        -19.8656,
        47.0333,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Fianarantsoa Market',
        'wholesale',
        'Haute Matsiatra',
        'Madagascar',
        'MG',
        -21.4522,
        47.0858,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Mahajanga Market',
        'wholesale',
        'Boeny',
        'Madagascar',
        'MG',
        -15.7167,
        46.3167,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Toliara Market',
        'wholesale',
        'Atsimo-Andrefana',
        'Madagascar',
        'MG',
        -23.3561,
        43.6667,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Antsiranana Market',
        'wholesale',
        'Diana',
        'Madagascar',
        'MG',
        -12.2761,
        49.2917,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Ambovombe Market',
        'wholesale',
        'Androy',
        'Madagascar',
        'MG',
        -25.1667,
        46.0833,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    ),
    (
        'Morondava Market',
        'wholesale',
        'Menabe',
        'Madagascar',
        'MG',
        -20.2833,
        44.2833,
        'MGA',
        'Indian/Antananarivo',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- MAURITIUS — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Port Louis Central Market',
        'wholesale',
        'Port Louis',
        'Mauritius',
        'MU',
        -20.1609,
        57.5012,
        'MUR',
        'Indian/Mauritius',
        'FEWS NET'
    ),
    (
        'Marché Central de Port Louis',
        'retail',
        'Port Louis',
        'Mauritius',
        'MU',
        -20.1617,
        57.5053,
        'MUR',
        'Indian/Mauritius',
        'FEWS NET'
    ),
    (
        'Curepipe Market',
        'wholesale',
        'Plaines Wilhems',
        'Mauritius',
        'MU',
        -20.3147,
        57.5203,
        'MUR',
        'Indian/Mauritius',
        'FEWS NET'
    ),
    (
        'Quatre Bornes Market',
        'wholesale',
        'Plaines Wilhems',
        'Mauritius',
        'MU',
        -20.2644,
        57.4792,
        'MUR',
        'Indian/Mauritius',
        'FEWS NET'
    ),
    (
        'Mahébourg Market',
        'wholesale',
        'Grand Port',
        'Mauritius',
        'MU',
        -20.4081,
        57.7000,
        'MUR',
        'Indian/Mauritius',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- SEYCHELLES — 3
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Victoria Market',
        'wholesale',
        'Mahé',
        'Seychelles',
        'SC',
        -4.6191,
        55.4513,
        'SCR',
        'Indian/Mahe',
        'FEWS NET'
    ),
    (
        'Sir Selwyn Selwyn-Clarke Market',
        'retail',
        'Mahé',
        'Seychelles',
        'SC',
        -4.6167,
        55.4500,
        'SCR',
        'Indian/Mahe',
        'FEWS NET'
    ),
    (
        'Anse Royale Market',
        'wholesale',
        'Mahé',
        'Seychelles',
        'SC',
        -4.7417,
        55.5083,
        'SCR',
        'Indian/Mahe',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- COMOROS — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Moroni Central Market',
        'wholesale',
        'Grande Comore',
        'Comoros',
        'KM',
        -11.7022,
        43.2551,
        'KMF',
        'Indian/Comoro',
        'FEWS NET'
    ),
    (
        'Marché de Moroni',
        'retail',
        'Grande Comore',
        'Comoros',
        'KM',
        -11.7000,
        43.2500,
        'KMF',
        'Indian/Comoro',
        'FEWS NET'
    ),
    (
        'Mutsamudu Market',
        'wholesale',
        'Anjouan',
        'Comoros',
        'KM',
        -12.1667,
        44.4000,
        'KMF',
        'Indian/Comoro',
        'FEWS NET'
    ),
    (
        'Fomboni Market',
        'wholesale',
        'Mohéli',
        'Comoros',
        'KM',
        -12.2833,
        43.7333,
        'KMF',
        'Indian/Comoro',
        'FEWS NET'
    ),
    (
        'Domoni Market',
        'wholesale',
        'Anjouan',
        'Comoros',
        'KM',
        -12.2500,
        44.5333,
        'KMF',
        'Indian/Comoro',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- CAPE VERDE — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Praia Central Market',
        'wholesale',
        'Santiago',
        'Cape Verde',
        'CV',
        14.9315,
        -23.5125,
        'CVE',
        'Atlantic/Cape_Verde',
        'FEWS NET'
    ),
    (
        'Mercado de Praia',
        'retail',
        'Santiago',
        'Cape Verde',
        'CV',
        14.9333,
        -23.5167,
        'CVE',
        'Atlantic/Cape_Verde',
        'FEWS NET'
    ),
    (
        'Mindelo Market',
        'wholesale',
        'São Vicente',
        'Cape Verde',
        'CV',
        16.8833,
        -24.9833,
        'CVE',
        'Atlantic/Cape_Verde',
        'FEWS NET'
    ),
    (
        'Assomada Market',
        'wholesale',
        'Santiago',
        'Cape Verde',
        'CV',
        15.1000,
        -23.6833,
        'CVE',
        'Atlantic/Cape_Verde',
        'FEWS NET'
    ),
    (
        'Espargos Market',
        'wholesale',
        'Sal',
        'Cape Verde',
        'CV',
        16.7550,
        -22.9453,
        'CVE',
        'Atlantic/Cape_Verde',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- SÃO TOMÉ AND PRÍNCIPE — 3
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'São Tomé Central Market',
        'wholesale',
        'São Tomé',
        'São Tomé and Príncipe',
        'ST',
        0.3361,
        6.7306,
        'STN',
        'Africa/Sao_Tome',
        'FEWS NET'
    ),
    (
        'Mercado de São Tomé',
        'retail',
        'São Tomé',
        'São Tomé and Príncipe',
        'ST',
        0.3333,
        6.7333,
        'STN',
        'Africa/Sao_Tome',
        'FEWS NET'
    ),
    (
        'Santo António Market',
        'wholesale',
        'Príncipe',
        'São Tomé and Príncipe',
        'ST',
        1.6375,
        7.4178,
        'STN',
        'Africa/Sao_Tome',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- ESWATINI — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Mbabane Market',
        'wholesale',
        'Hhohho',
        'Eswatini',
        'SZ',
        -26.3057,
        31.1367,
        'SZL',
        'Africa/Mbabane',
        'FEWS NET'
    ),
    (
        'Manzini Market',
        'wholesale',
        'Manzini',
        'Eswatini',
        'SZ',
        -26.4833,
        31.3667,
        'SZL',
        'Africa/Mbabane',
        'FEWS NET'
    ),
    (
        'Lobamba Market',
        'wholesale',
        'Hhohho',
        'Eswatini',
        'SZ',
        -26.4167,
        31.2000,
        'SZL',
        'Africa/Mbabane',
        'FEWS NET'
    ),
    (
        'Siteki Market',
        'wholesale',
        'Lubombo',
        'Eswatini',
        'SZ',
        -26.4500,
        31.9500,
        'SZL',
        'Africa/Mbabane',
        'FEWS NET'
    ),
    (
        'Nhlangano Market',
        'wholesale',
        'Shiselweni',
        'Eswatini',
        'SZ',
        -27.1167,
        31.2000,
        'SZL',
        'Africa/Mbabane',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- LESOTHO — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Maseru Market',
        'wholesale',
        'Maseru',
        'Lesotho',
        'LS',
        -29.3167,
        27.4833,
        'LSL',
        'Africa/Maseru',
        'FEWS NET'
    ),
    (
        'Teyateyaneng Market',
        'wholesale',
        'Berea',
        'Lesotho',
        'LS',
        -29.1489,
        27.7361,
        'LSL',
        'Africa/Maseru',
        'FEWS NET'
    ),
    (
        'Mafeteng Market',
        'wholesale',
        'Mafeteng',
        'Lesotho',
        'LS',
        -29.8231,
        27.2375,
        'LSL',
        'Africa/Maseru',
        'FEWS NET'
    ),
    (
        'Hlotse Market',
        'wholesale',
        'Leribe',
        'Lesotho',
        'LS',
        -28.8717,
        28.0517,
        'LSL',
        'Africa/Maseru',
        'FEWS NET'
    ),
    (
        'Mohale''s Hoek Market',
        'wholesale',
        'Mohale''s Hoek',
        'Lesotho',
        'LS',
        -30.1511,
        27.4769,
        'LSL',
        'Africa/Maseru',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- BOTSWANA — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Gaborone Market',
        'wholesale',
        'South-East',
        'Botswana',
        'BW',
        -24.6282,
        25.9231,
        'BWP',
        'Africa/Gaborone',
        'FEWS NET'
    ),
    (
        'Francistown Market',
        'wholesale',
        'North-East',
        'Botswana',
        'BW',
        -21.1667,
        27.5000,
        'BWP',
        'Africa/Gaborone',
        'FEWS NET'
    ),
    (
        'Maun Market',
        'wholesale',
        'North-West',
        'Botswana',
        'BW',
        -19.9833,
        23.4167,
        'BWP',
        'Africa/Gaborone',
        'FEWS NET'
    ),
    (
        'Serowe Market',
        'wholesale',
        'Central',
        'Botswana',
        'BW',
        -22.3833,
        26.7167,
        'BWP',
        'Africa/Gaborone',
        'FEWS NET'
    ),
    (
        'Kanye Market',
        'wholesale',
        'Southern',
        'Botswana',
        'BW',
        -24.9667,
        25.3333,
        'BWP',
        'Africa/Gaborone',
        'FEWS NET'
    );
-- ------------------------------------------------------------
-- NAMIBIA — 5
-- ------------------------------------------------------------
INSERT
    OR IGNORE INTO markets (
        name,
        market_type,
        county_or_region,
        country,
        country_code,
        latitude,
        longitude,
        currency,
        timezone,
        data_source
    )
VALUES (
        'Windhoek Central Market',
        'wholesale',
        'Khomas',
        'Namibia',
        'NA',
        -22.5609,
        17.0658,
        'NAD',
        'Africa/Windhoek',
        'FEWS NET'
    ),
    (
        'Oshakati Market',
        'wholesale',
        'Oshana',
        'Namibia',
        'NA',
        -17.7833,
        15.7000,
        'NAD',
        'Africa/Windhoek',
        'FEWS NET'
    ),
    (
        'Walvis Bay Market',
        'wholesale',
        'Erongo',
        'Namibia',
        'NA',
        -22.9575,
        14.5053,
        'NAD',
        'Africa/Windhoek',
        'FEWS NET'
    ),
    (
        'Rundu Market',
        'wholesale',
        'Kavango East',
        'Namibia',
        'NA',
        -17.9333,
        19.7667,
        'NAD',
        'Africa/Windhoek',
        'FEWS NET'
    ),
    (
        'Keetmanshoop Market',
        'wholesale',
        'Karas',
        'Namibia',
        'NA',
        -26.5833,
        18.1333,
        'NAD',
        'Africa/Windhoek',
        'FEWS NET'
    );
-- ============================================================
-- 9. SANITY CHECKS (run after migration)
-- ============================================================
-- SELECT COUNT(*) FROM crops;                        -- expect 100
-- SELECT COUNT(*) FROM markets;                      -- expect ~500
-- SELECT COUNT(DISTINCT country_code) FROM markets;  -- expect ~50
-- PRAGMA table_info(market_prices);
-- PRAGMA index_list(market_prices);