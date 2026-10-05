-- ============================================================
-- SEED 001 — FARMERS (5 pilot farmers + 1 admin)
-- ============================================================

-- Admin account (password: Admin@2025)
INSERT OR IGNORE INTO farmers
    (phone, email, full_name, password_hash, country, county, location, language,
     subscription_tier, subscription_expires_at, verified, verified_at)
VALUES
    ('+254700000001', 'admin@marcbantuafrica.com', 'Marcbantu Admin',
     'YWRtaW5zYWx0$cGFzc3dvcmRfaGFzaF9hZG1pbg',
     'Kenya', 'Nairobi', 'Westlands', 'en', 'business',
     datetime('now', '+10 years'), 1, datetime('now')),

    -- Farmer 1: James Mwangi (dairy + maize + poultry)
    ('+254712345678', 'james.mwangi@example.com', 'James Mwangi',
     'amFtZXNzYWx0$cGFzc3dvcmRfaGFzaF9qYW1lcw',
     'Kenya', 'Kiambu', 'Limuru', 'en', 'pro',
     datetime('now', '+1 year'), 1, datetime('now')),

    -- Farmer 2: Alice Wanjiku (maize + beans)
    ('+254723456789', 'alice.wanjiku@example.com', 'Alice Wanjiku',
     'YWxpY2VzYWx0$cGFzc3dvcmRfaGFzaF9hbGljZQ',
     'Kenya', 'Nakuru', 'Njoro', 'sw', 'pro',
     datetime('now', '+6 months'), 1, datetime('now')),

    -- Farmer 3: Peter Kariuki (horticulture — tomatoes, kale)
    ('+254734567890', 'peter.kariuki@example.com', 'Peter Kariuki',
     'cGV0ZXJzYWx0$cGFzc3dvcmRfaGFzaF9wZXRlcg',
     'Kenya', 'Kiambu', 'Limuru', 'en', 'starter',
     NULL, 1, datetime('now')),

    -- Farmer 4: Grace Njeri (poultry — 500 layers)
    ('+254745678901', 'grace.njeri@example.com', 'Grace Njeri',
     'Z3JhY2VzYWx0$cGFzc3dvcmRfaGFzaF9ncmFjZQ',
     'Kenya', 'Machakos', 'Kangundo', 'en', 'pro',
     datetime('now', '+8 months'), 1, datetime('now')),

    -- Farmer 5: David Otieno (mixed — dairy + maize + horticulture)
    ('+254756789012', 'david.otieno@example.com', 'David Otieno',
     'ZGF2aWRzYWx0$cGFzc3dvcmRfaGFzaF9kYXZpZA',
     'Kenya', 'Kisumu', 'Ahero', 'en', 'starter',
     NULL, 1, datetime('now'));

-- Update last login for realism
UPDATE farmers SET last_login_at = datetime('now', '-2 hours') WHERE phone = '+254712345678';
UPDATE farmers SET last_login_at = datetime('now', '-1 day') WHERE phone = '+254723456789';
UPDATE farmers SET last_login_at = datetime('now', '-3 days') WHERE phone = '+254734567890';
UPDATE farmers SET last_login_at = datetime('now', '-6 hours') WHERE phone = '+254745678901';
UPDATE farmers SET last_login_at = datetime('now', '-4 days') WHERE phone = '+254756789012';