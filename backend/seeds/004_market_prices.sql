-- ============================================================
-- SEED 004 — MARKET PRICES, BUYERS, SALES, CONTRACTS
-- ============================================================

-- ============================================================
-- MARKET PRICES (today + last 7 days for trends)
-- ============================================================

-- Today's prices
INSERT OR IGNORE INTO market_prices (crop, market, county, price, unit, price_date, source)
VALUES
    ('Maize', 'Nakuru Market', 'Nakuru', 45, 'kg', date('now'), 'AMIS'),
    ('Maize', 'Eldoret Market', 'Uasin Gishu', 42, 'kg', date('now'), 'AMIS'),
    ('Maize', 'Nairobi Wakulima', 'Nairobi', 48, 'kg', date('now'), 'AMIS'),
    ('Beans', 'Nakuru Market', 'Nakuru', 120, 'kg', date('now'), 'AMIS'),
    ('Beans', 'Nairobi Wakulima', 'Nairobi', 130, 'kg', date('now'), 'AMIS'),
    ('Tomatoes', 'Limuru Market', 'Kiambu', 90, 'kg', date('now'), 'Local'),
    ('Tomatoes', 'Nairobi Wakulima', 'Nairobi', 100, 'kg', date('now'), 'Local'),
    ('Kale', 'Limuru Market', 'Kiambu', 50, 'kg', date('now'), 'Local'),
    ('Kale', 'Nairobi Wakulima', 'Nairobi', 60, 'kg', date('now'), 'Local'),
    ('Potatoes', 'Limuru Market', 'Kiambu', 55, 'kg', date('now'), 'Local'),
    ('Potatoes', 'Nakuru Market', 'Nakuru', 48, 'kg', date('now'), 'AMIS'),
    ('Milk', 'Kiambu Dairy', 'Kiambu', 52, 'litre', date('now'), 'Coop'),
    ('Milk', 'Nairobi', 'Nairobi', 55, 'litre', date('now'), 'Coop'),
    ('Eggs', 'Machakos Market', 'Machakos', 380, 'tray', date('now'), 'Local'),
    ('Eggs', 'Nairobi', 'Nairobi', 420, 'tray', date('now'), 'Local'),
    ('Rice', 'Ahero Market', 'Kisumu', 120, 'kg', date('now'), 'Local'),
    ('Spinach', 'Limuru Market', 'Kiambu', 45, 'kg', date('now'), 'Local');

-- Last 7 days of maize prices (for trend chart)
INSERT OR IGNORE INTO market_prices (crop, market, county, price, unit, price_date, source)
VALUES
    ('Maize', 'Nakuru Market', 'Nakuru', 43, 'kg', date('now', '-1 day'), 'AMIS'),
    ('Maize', 'Nakuru Market', 'Nakuru', 44, 'kg', date('now', '-2 days'), 'AMIS'),
    ('Maize', 'Nakuru Market', 'Nakuru', 42, 'kg', date('now', '-3 days'), 'AMIS'),
    ('Maize', 'Nakuru Market', 'Nakuru', 41, 'kg', date('now', '-4 days'), 'AMIS'),
    ('Maize', 'Nakuru Market', 'Nakuru', 43, 'kg', date('now', '-5 days'), 'AMIS'),
    ('Maize', 'Nakuru Market', 'Nakuru', 44, 'kg', date('now', '-6 days'), 'AMIS'),
    ('Maize', 'Nakuru Market', 'Nakuru', 42, 'kg', date('now', '-7 days'), 'AMIS');

-- ============================================================
-- BUYERS
-- ============================================================
INSERT OR IGNORE INTO buyers (name, type, phone, email, location, county, rating, payment_terms, products_bought)
VALUES
    ('Kiambu Dairy Cooperative', 'cooperative', '+254700111222', 'info@kiambudairy.co.ke',
     'Kiambu Town', 'Kiambu', 5.0, 'Weekly payment', 'Milk'),

    ('Nakuru Millers Ltd', 'processor', '+254700222333', 'buying@nakurumillers.co.ke',
     'Nakuru Town', 'Nakuru', 4.5, 'Cash on delivery', 'Maize, Wheat'),

    ('Nairobi Fresh Produce', 'trader', '+254700333444', NULL,
     'Wakulima Market', 'Nairobi', 3.5, 'Cash', 'Tomatoes, Kale, Spinach'),

    ('Brookside Dairy', 'processor', '+254700444555', 'procurement@brookside.co.ke',
     'Ruiru', 'Kiambu', 5.0, 'Bi-weekly payment', 'Milk'),

    ('Kenchic Ltd', 'processor', '+254700555666', 'supply@kenchic.co.ke',
     'Thika', 'Kiambu', 4.8, 'Weekly payment', 'Poultry, Eggs'),

    ('Machakos Wholesale Market', 'trader', '+254700666777', NULL,
     'Machakos Town', 'Machakos', 3.0, 'Cash', 'Eggs, Vegetables'),

    ('Kisumu Rice Millers', 'processor', '+254700777888', 'buy@kisumuricemillers.co.ke',
     'Ahero', 'Kisumu', 4.5, 'Cash on delivery', 'Rice');

-- ============================================================
-- SALES (recent sales from our farmers)
-- ============================================================
INSERT OR IGNORE INTO sales
    (farm_id, buyer_id, enterprise_id, product, quantity, unit, unit_price, total,
     payment_status, payment_method, amount_paid, sale_date, payment_date)
VALUES
    -- James (farm 1)
    (1, 1, 1, 'Milk', 42, 'litres', 52, 2184, 'paid', 'mpesa', 2184, date('now', '-1 day'), date('now', '-1 day')),
    (1, 1, 1, 'Milk', 40, 'litres', 52, 2080, 'paid', 'mpesa', 2080, date('now', '-2 days'), date('now', '-2 days')),
    (1, 2, 2, 'Maize', 400, 'kg', 30, 12000, 'paid', 'bank', 12000, date('now', '-3 days'), date('now', '-3 days')),
    (1, 6, 5, 'Eggs', 60, 'pieces', 6.33, 380, 'paid', 'cash', 380, date('now', '-1 day'), date('now', '-1 day')),

    -- Alice (farm 2) — will sell later
    (2, 2, 6, 'Maize', 1500, 'kg', 42, 63000, 'pending', NULL, 0, date('now', '+10 days'), NULL),

    -- Peter (farm 3)
    (3, 3, 9, 'Kale', 120, 'kg', 50, 6000, 'paid', 'mpesa', 6000, date('now', '-3 days'), date('now', '-3 days')),
    (3, 3, 8, 'Tomatoes', 85, 'kg', 100, 8500, 'paid', 'mpesa', 8500, date('now', '-10 days'), date('now', '-10 days')),

    -- Grace (farm 4)
    (4, 5, 11, 'Eggs', 800, 'pieces', 16, 12800, 'paid', 'mpesa', 12800, date('now', '-2 days'), date('now', '-2 days')),

    -- David (farm 5)
    (5, 4, 15, 'Milk', 36, 'litres', 48, 1728, 'paid', 'mpesa', 1728, date('now', '-1 day'), date('now', '-1 day')),
    (5, 4, 15, 'Milk', 34, 'litres', 48, 1632, 'paid', 'mpesa', 1632, date('now', '-2 days'), date('now', '-2 days'));

-- ============================================================
-- CONTRACTS
-- ============================================================
INSERT OR IGNORE INTO contracts
    (farm_id, buyer_id, enterprise_id, product, quantity, unit, price_per_unit, total_value,
     delivery_start_date, delivery_end_date, payment_terms, status, signed_date)
VALUES
    (1, 1, 1, 'Milk', 40, 'litres', 52, NULL,
     date('now'), date('now', '+1 year'), 'Weekly payment', 'active', date('now', '-90 days')),

    (2, 2, 6, 'Maize', 1500, 'kg', 42, 63000,
     date('now', '+10 days'), date('now', '+15 days'), 'Cash on delivery', 'active', date('now', '-30 days')),

    (4, 5, 11, 'Eggs', 600, 'pieces', 16, NULL,
     date('now'), date('now', '+6 months'), 'Weekly payment', 'active', date('now', '-60 days'));

-- ============================================================
-- PRICE ALERTS
-- ============================================================
INSERT OR IGNORE INTO price_alerts (farmer_id, crop, target_price, direction, active)
VALUES
    ((SELECT id FROM farmers WHERE phone = '+254712345678'), 'Maize', 50, 'above', 1),
    ((SELECT id FROM farmers WHERE phone = '+254712345678'), 'Milk', 55, 'above', 1),
    ((SELECT id FROM farmers WHERE phone = '+254723456789'), 'Maize', 48, 'above', 1),
    ((SELECT id FROM farmers WHERE phone = '+254734567890'), 'Tomatoes', 110, 'above', 1),
    ((SELECT id FROM farmers WHERE phone = '+254745678901'), 'Eggs', 400, 'above', 1);