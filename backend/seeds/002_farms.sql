-- ============================================================
-- SEED 002 — FARMS, PLOTS, ENTERPRISES
-- ============================================================

-- ============================================================
-- FARM 1: James Mwangi — Limuru (3.5 acres)
-- ============================================================
INSERT OR IGNORE INTO farms
    (id, farmer_id, name, size_acres, latitude, longitude, altitude_m, soil_type, irrigation_type, water_source, notes)
VALUES
    (1, (SELECT id FROM farmers WHERE phone = '+254712345678'),
     'Mwangi Family Farm', 3.5, -1.1167, 36.6500, 2200,
     'loam', 'rain-fed', 'borehole',
     'Mixed farm: dairy, maize, poultry. Been farming 8 years.');

-- Plots for Farm 1
INSERT OR IGNORE INTO plots (farm_id, name, size_acres, latitude, longitude, soil_type, soil_ph, current_crop)
VALUES
    (1, 'Plot A — Maize', 2.0, -1.1167, 36.6500, 'loam', 6.2, 'Maize (Hybrid 614)'),
    (1, 'Plot B — Beans', 1.0, -1.1168, 36.6501, 'loam', 6.0, 'Beans (Rosecoco)'),
    (1, 'Plot C — Kale', 0.5, -1.1169, 36.6502, 'loam', 6.5, 'Kale (Sukuma wiki)');

-- Enterprises for Farm 1
INSERT OR IGNORE INTO enterprises
    (farm_id, name, type, species_or_crop, quantity, unit, start_date, status)
VALUES
    (1, 'Dairy Herd', 'livestock', 'Friesian × Ayrshire', 2, 'cows', '2023-06-15', 'active'),
    (1, 'Maize Plot A', 'crop', 'Hybrid 614', 2.0, 'acres', '2025-08-15', 'active'),
    (1, 'Beans Plot B', 'crop', 'Rosecoco', 1.0, 'acres', '2025-09-01', 'active'),
    (1, 'Kale Plot C', 'horticulture', 'Sukuma wiki', 0.5, 'acres', '2025-07-20', 'active'),
    (1, 'Poultry Flock', 'poultry', 'Improved Kienyeji', 200, 'birds', '2025-04-01', 'active');

-- ============================================================
-- FARM 2: Alice Wanjiku — Njoro (5 acres)
-- ============================================================
INSERT OR IGNORE INTO farms
    (id, farmer_id, name, size_acres, latitude, longitude, altitude_m, soil_type, irrigation_type, water_source)
VALUES
    (2, (SELECT id FROM farmers WHERE phone = '+254723456789'),
     'Wanjiku Grain Farm', 5.0, -0.3667, 35.9333, 2100,
     'clay-loam', 'rain-fed', 'river');

INSERT OR IGNORE INTO plots (farm_id, name, size_acres, latitude, longitude, soil_type, current_crop)
VALUES
    (2, 'North Field', 3.0, -0.3667, 35.9333, 'clay-loam', 'Maize (DK 8031)'),
    (2, 'South Field', 2.0, -0.3668, 35.9334, 'clay-loam', 'Beans (Nyayo)');

INSERT OR IGNORE INTO enterprises
    (farm_id, name, type, species_or_crop, quantity, unit, start_date, status)
VALUES
    (2, 'Maize North', 'crop', 'DK 8031', 3.0, 'acres', '2025-03-15', 'active'),
    (2, 'Beans South', 'crop', 'Nyayo', 2.0, 'acres', '2025-04-01', 'active');

-- ============================================================
-- FARM 3: Peter Kariuki — Limuru (1.5 acres)
-- ============================================================
INSERT OR IGNORE INTO farms
    (id, farmer_id, name, size_acres, latitude, longitude, altitude_m, soil_type, irrigation_type, water_source)
VALUES
    (3, (SELECT id FROM farmers WHERE phone = '+254734567890'),
     'Kariuki Greens', 1.5, -1.1000, 36.6333, 2300,
     'volcanic-loam', 'drip', 'borehole');

INSERT OR IGNORE INTO plots (farm_id, name, size_acres, latitude, longitude, soil_type, current_crop)
VALUES
    (3, 'Greenhouse 1', 0.25, -1.1000, 36.6333, 'volcanic-loam', 'Tomatoes (Anna F1)'),
    (3, 'Open Field A', 0.75, -1.1001, 36.6334, 'volcanic-loam', 'Kale (Sukuma wiki)'),
    (3, 'Open Field B', 0.5, -1.1002, 36.6335, 'volcanic-loam', 'Spinach');

INSERT OR IGNORE INTO enterprises
    (farm_id, name, type, species_or_crop, quantity, unit, start_date, status)
VALUES
    (3, 'Tomato Greenhouse', 'horticulture', 'Anna F1', 0.25, 'acres', '2025-06-01', 'active'),
    (3, 'Kale Field A', 'horticulture', 'Sukuma wiki', 0.75, 'acres', '2025-05-15', 'active'),
    (3, 'Spinach Field B', 'horticulture', 'Spinach', 0.5, 'acres', '2025-07-01', 'active');

-- ============================================================
-- FARM 4: Grace Njeri — Kangundo (0.5 acres)
-- ============================================================
INSERT OR IGNORE INTO farms
    (id, farmer_id, name, size_acres, latitude, longitude, altitude_m, soil_type, irrigation_type, water_source)
VALUES
    (4, (SELECT id FROM farmers WHERE phone = '+254745678901'),
     'Njeri Poultry Farm', 0.5, -1.3167, 37.3500, 1600,
     'sandy-loam', 'rain-fed', 'tap');

INSERT OR IGNORE INTO enterprises
    (farm_id, name, type, species_or_crop, quantity, unit, start_date, status)
VALUES
    (4, 'Layer Flock', 'poultry', 'Lohmann Brown', 500, 'birds', '2025-02-15', 'active'),
    (4, 'Broiler Batch 1', 'poultry', 'Cobb 500', 100, 'birds', '2025-09-15', 'active');

-- ============================================================
-- FARM 5: David Otieno — Ahero (4 acres)
-- ============================================================
INSERT OR IGNORE INTO farms
    (id, farmer_id, name, size_acres, latitude, longitude, altitude_m, soil_type, irrigation_type, water_source)
VALUES
    (5, (SELECT id FROM farmers WHERE phone = '+254756789012'),
     'Otieno Mixed Farm', 4.0, -0.1667, 34.9333, 1150,
     'black-cotton', 'furrow', 'river');

INSERT OR IGNORE INTO plots (farm_id, name, size_acres, latitude, longitude, soil_type, current_crop)
VALUES
    (5, 'Rice Paddy', 2.0, -0.1667, 34.9333, 'black-cotton', 'Rice (Basmati)'),
    (5, 'Maize Field', 1.5, -0.1668, 34.9334, 'black-cotton', 'Maize (Hybrid 628)'),
    (5, 'Kitchen Garden', 0.5, -0.1669, 34.9335, 'black-cotton', 'Vegetables');

INSERT OR IGNORE INTO enterprises
    (farm_id, name, type, species_or_crop, quantity, unit, start_date, status)
VALUES
    (5, 'Rice Paddy', 'crop', 'Basmati', 2.0, 'acres', '2025-07-01', 'active'),
    (5, 'Maize Field', 'crop', 'Hybrid 628', 1.5, 'acres', '2025-08-01', 'active'),
    (5, 'Dairy Unit', 'livestock', 'Crossbreed', 3, 'cows', '2024-11-01', 'active'),
    (5, 'Kitchen Garden', 'horticulture', 'Mixed vegetables', 0.5, 'acres', '2025-06-01', 'active');