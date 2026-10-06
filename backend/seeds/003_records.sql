-- ============================================================
-- SEED 003 — RECORDS, TRANSACTIONS, TASKS, WORKERS, EQUIPMENT
-- ============================================================

-- ============================================================
-- FARM 1 (James) — Workers
-- ============================================================
INSERT OR IGNORE INTO workers
    (farm_id, name, phone, role, wage_type, wage_amount, start_date, active)
VALUES
    (1, 'John Mwaura', '+254720111222', 'Farm hand', 'monthly', 15000, '2023-01-15', 1),
    (1, 'Mary Wambui', '+254720111333', 'Dairy attendant', 'monthly', 18000, '2023-03-01', 1),
    (1, 'Peter Kimani', '+254720111444', 'Poultry attendant', 'monthly', 12000, '2024-02-01', 1),
    (1, 'Grace Njoroge', '+254720111555', 'Casual labour', 'daily', 500, '2025-08-01', 1);

-- ============================================================
-- FARM 1 — Tasks
-- ============================================================
INSERT OR IGNORE INTO tasks
    (farm_id, enterprise_id, assigned_to, title, description, priority, status, due_date)
VALUES
    (1, 1, 2, 'Morning milking', 'Milk cows #1 and #2. Record litres.', 'high', 'completed', date('now')),
    (1, 1, 2, 'Evening milking', 'Milk cows #1 and #2. Record litres.', 'high', 'pending', date('now')),
    (1, 2, 1, 'Spray maize Plot A', 'Apply Ampligo for Fall Armyworm.', 'urgent', 'in_progress', date('now')),
    (1, 5, 3, 'Collect eggs', 'Collect and record morning eggs.', 'medium', 'completed', date('now')),
    (1, 3, 1, 'Weed beans Plot B', 'Hand-weed the bean field.', 'medium', 'pending', date('now', '+2 days')),
    (1, 1, NULL, 'Call vet for vaccination', 'Schedule FMD vaccination for cattle.', 'high', 'pending', date('now', '+3 days')),
    (1, 4, 1, 'Harvest kale', 'Harvest mature kale for market.', 'medium', 'pending', date('now', '+1 day'));

-- ============================================================
-- FARM 1 — Attendance (today)
-- ============================================================
INSERT OR IGNORE INTO attendance (worker_id, farm_id, date, status, hours)
VALUES
    (1, 1, date('now'), 'present', 8),
    (2, 1, date('now'), 'present', 8),
    (3, 1, date('now'), 'present', 6),
    (4, 1, date('now'), 'present', 4);

-- ============================================================
-- FARM 1 — Equipment
-- ============================================================
INSERT OR IGNORE INTO equipment
    (farm_id, name, type, make, purchase_date, purchase_cost, current_value,
     last_service_date, next_service_date, status)
VALUES
    (1, 'Water Pump', 'pump', 'Honda WB30', '2023-06-15', 25000, 18000,
     '2025-09-01', '2025-12-01', 'good'),
    (1, 'Knapsack Sprayer', 'sprayer', 'Kisankraft', '2024-03-01', 3500, 2500,
     '2025-06-01', '2025-12-01', 'good'),
    (1, 'Milking Machine', 'milking', 'DeLaval', '2022-08-01', 85000, 55000,
     '2025-09-15', '2026-03-15', 'good'),
    (1, 'Chaff Cutter', 'feed', 'Local', '2023-01-01', 12000, 8000,
     '2025-05-01', '2025-11-01', 'needs_service');

-- ============================================================
-- FARM 1 — Records (recent activity)
-- ============================================================
INSERT OR IGNORE INTO records
    (farm_id, enterprise_id, record_type, activity, description, quantity, unit, cost, revenue, record_date)
VALUES
    (1, 1, 'livestock', 'milking', 'Morning milk — Cow #1', 24, 'litres', 0, 0, date('now')),
    (1, 1, 'livestock', 'milking', 'Morning milk — Cow #2', 18, 'litres', 0, 0, date('now')),
    (1, 5, 'poultry', 'egg_collection', 'Morning eggs collected', 180, 'eggs', 0, 0, date('now')),
    (1, 1, 'input', 'feeding', 'Dairy meal — 50kg bag', 50, 'kg', 3200, 0, date('now', '-1 day')),
    (1, 2, 'crop_activity', 'spraying', 'Ampligo sprayed on Plot A', 2, 'acres', 1200, 0, date('now', '-1 day')),
    (1, 5, 'sale', 'egg_sale', 'Eggs sold at local market', 60, 'eggs', 0, 380, date('now', '-1 day')),
    (1, 2, 'harvest', 'harvesting', 'Maize harvest — Plot A', 400, 'kg', 0, 0, date('now', '-3 days')),
    (1, 2, 'sale', 'maize_sale', 'Maize sold to Nakuru Millers', 400, 'kg', 0, 12000, date('now', '-3 days')),
    (1, 3, 'crop_activity', 'weeding', 'Hand-weeded beans Plot B', 1, 'acre', 800, 0, date('now', '-5 days')),
    (1, 4, 'crop_activity', 'planting', 'Kale seedlings transplanted', 0.5, 'acres', 2000, 0, date('now', '-10 days'));

-- ============================================================
-- FARM 1 — Transactions
-- ============================================================
INSERT OR IGNORE INTO transactions
    (farm_id, enterprise_id, type, category, description, amount, payment_method, transaction_date)
VALUES
    (1, 1, 'income', 'milk_sales', 'Milk sold to Kiambu Dairy — 42L', 2184, 'mpesa', date('now', '-1 day')),
    (1, 1, 'income', 'milk_sales', 'Milk sold to Kiambu Dairy — 40L', 2080, 'mpesa', date('now', '-2 days')),
    (1, 1, 'income', 'milk_sales', 'Milk sold to Kiambu Dairy — 44L', 2288, 'mpesa', date('now', '-3 days')),
    (1, 2, 'income', 'crop_sales', 'Maize sold to Nakuru Millers', 12000, 'bank', date('now', '-3 days')),
    (1, 5, 'income', 'poultry_sales', 'Eggs sold at market', 380, 'cash', date('now', '-1 day')),
    (1, 1, 'expense', 'feeds', 'Dairy meal — 50kg', 3200, 'mpesa', date('now', '-1 day')),
    (1, 2, 'expense', 'chemicals', 'Ampligo insecticide', 1200, 'cash', date('now', '-1 day')),
    (1, 3, 'expense', 'labour', 'Weeding labour', 800, 'cash', date('now', '-5 days')),
    (1, 1, 'expense', 'vet', 'Vet visit for cow #1', 1500, 'mpesa', date('now', '-7 days')),
    (1, 2, 'expense', 'seeds', 'Maize seed — Hybrid 614', 4500, 'cash', date('now', '-45 days')),
    (1, 1, 'expense', 'feeds', 'Dairy meal — 50kg', 3200, 'mpesa', date('now', '-15 days')),
    (1, 5, 'expense', 'feeds', 'Poultry feed — 50kg', 2800, 'mpesa', date('now', '-10 days'));

-- ============================================================
-- FARM 2 (Alice) — Records
-- ============================================================
INSERT OR IGNORE INTO records
    (farm_id, enterprise_id, record_type, activity, description, quantity, unit, cost, revenue, record_date)
VALUES
    (2, 6, 'crop_activity', 'planting', 'Maize DK 8031 planted — North Field', 3, 'acres', 8000, 0, date('now', '-90 days')),
    (2, 6, 'crop_activity', 'fertilizing', 'DAP applied — North Field', 150, 'kg', 10500, 0, date('now', '-85 days')),
    (2, 7, 'crop_activity', 'planting', 'Beans Nyayo planted — South Field', 2, 'acres', 4000, 0, date('now', '-75 days')),
    (2, 6, 'crop_activity', 'spraying', 'Fall Armyworm control', 3, 'acres', 2400, 0, date('now', '-30 days')),
    (2, 7, 'crop_activity', 'weeding', 'Weeding South Field', 2, 'acres', 1600, 0, date('now', '-20 days'));

INSERT OR IGNORE INTO transactions
    (farm_id, enterprise_id, type, category, description, amount, payment_method, transaction_date)
VALUES
    (2, 6, 'expense', 'seeds', 'Maize seed DK 8031', 8000, 'cash', date('now', '-90 days')),
    (2, 6, 'expense', 'fertilizer', 'DAP fertilizer — 3 bags', 10500, 'bank', date('now', '-85 days')),
    (2, 7, 'expense', 'seeds', 'Bean seed Nyayo', 4000, 'cash', date('now', '-75 days')),
    (2, 6, 'expense', 'chemicals', 'Fall Armyworm insecticide', 2400, 'mpesa', date('now', '-30 days')),
    (2, 7, 'expense', 'labour', 'Weeding labour', 1600, 'cash', date('now', '-20 days'));

-- ============================================================
-- FARM 3 (Peter) — Records
-- ============================================================
INSERT OR IGNORE INTO records
    (farm_id, enterprise_id, record_type, activity, description, quantity, unit, cost, revenue, record_date)
VALUES
    (3, 8, 'crop_activity', 'planting', 'Tomato seedlings transplanted', 0.25, 'acres', 3500, 0, date('now', '-60 days')),
    (3, 9, 'crop_activity', 'planting', 'Kale seedlings transplanted', 0.75, 'acres', 2500, 0, date('now', '-45 days')),
    (3, 10, 'crop_activity', 'planting', 'Spinach sown', 0.5, 'acres', 1800, 0, date('now', '-30 days')),
    (3, 9, 'harvest', 'harvesting', 'Kale harvested', 120, 'kg', 0, 0, date('now', '-3 days')),
    (3, 9, 'sale', 'vegetable_sale', 'Kale sold to local market', 120, 'kg', 0, 6000, date('now', '-3 days'));

INSERT OR IGNORE INTO transactions
    (farm_id, enterprise_id, type, category, description, amount, payment_method, transaction_date)
VALUES
    (3, 8, 'expense', 'seeds', 'Tomato seedlings Anna F1', 3500, 'cash', date('now', '-60 days')),
    (3, 9, 'expense', 'seeds', 'Kale seedlings', 2500, 'cash', date('now', '-45 days')),
    (3, 10, 'expense', 'seeds', 'Spinach seed', 1800, 'cash', date('now', '-30 days')),
    (3, 9, 'income', 'vegetable_sales', 'Kale sale to local market', 6000, 'mpesa', date('now', '-3 days')),
    (3, 8, 'expense', 'drip_irrigation', 'Drip kit replacement', 4500, 'bank', date('now', '-20 days')),
    (3, 8, 'income', 'vegetable_sales', 'Tomatoes — first harvest', 8500, 'mpesa', date('now', '-10 days'));

-- ============================================================
-- FARM 4 (Grace) — Records
-- ============================================================
INSERT OR IGNORE INTO records
    (farm_id, enterprise_id, record_type, activity, description, quantity, unit, cost, revenue, record_date)
VALUES
    (4, 11, 'poultry', 'egg_collection', 'Morning eggs', 420, 'eggs', 0, 0, date('now')),
    (4, 11, 'poultry', 'egg_collection', 'Evening eggs', 380, 'eggs', 0, 0, date('now')),
    (4, 12, 'poultry', 'feeding', 'Broiler starter feed', 25, 'kg', 1400, 0, date('now', '-1 day')),
    (4, 11, 'poultry', 'feeding', 'Layer mash', 60, 'kg', 2800, 0, date('now', '-1 day')),
    (4, 11, 'sale', 'egg_sale', 'Eggs sold to wholesaler', 800, 'eggs', 0, 12800, date('now', '-2 days'));

INSERT OR IGNORE INTO transactions
    (farm_id, enterprise_id, type, category, description, amount, payment_method, transaction_date)
VALUES
    (4, 11, 'income', 'poultry_sales', 'Eggs sold to wholesaler — 800 eggs', 12800, 'mpesa', date('now', '-2 days')),
    (4, 11, 'expense', 'feeds', 'Layer mash — 60kg', 2800, 'cash', date('now', '-1 day')),
    (4, 12, 'expense', 'feeds', 'Broiler starter — 25kg', 1400, 'cash', date('now', '-1 day')),
    (4, 11, 'expense', 'vet', 'Vaccination for layers', 3200, 'mpesa', date('now', '-15 days')),
    (4, 12, 'expense', 'chicks', 'Broiler chicks — 100', 8000, 'mpesa', date('now', '-20 days'));

-- ============================================================
-- FARM 5 (David) — Records
-- ============================================================
INSERT OR IGNORE INTO records
    (farm_id, enterprise_id, record_type, activity, description, quantity, unit, cost, revenue, record_date)
VALUES
    (5, 13, 'crop_activity', 'planting', 'Rice Basmati transplanted', 2, 'acres', 5000, 0, date('now', '-90 days')),
    (5, 14, 'crop_activity', 'planting', 'Maize Hybrid 628 planted', 1.5, 'acres', 3500, 0, date('now', '-60 days')),
    (5, 15, 'livestock', 'milking', 'Morning milk — 3 cows', 36, 'litres', 0, 0, date('now')),
    (5, 16, 'crop_activity', 'planting', 'Kitchen garden vegetables', 0.5, 'acres', 1200, 0, date('now', '-45 days')),
    (5, 15, 'sale', 'milk_sale', 'Milk sold to local dairy', 36, 'litres', 0, 1728, date('now', '-1 day'));

INSERT OR IGNORE INTO transactions
    (farm_id, enterprise_id, type, category, description, amount, payment_method, transaction_date)
VALUES
    (5, 13, 'expense', 'seeds', 'Rice seed Basmati', 5000, 'bank', date('now', '-90 days')),
    (5, 14, 'expense', 'seeds', 'Maize seed Hybrid 628', 3500, 'cash', date('now', '-60 days')),
    (5, 15, 'income', 'milk_sales', 'Milk sold — 36L', 1728, 'mpesa', date('now', '-1 day')),
    (5, 15, 'income', 'milk_sales', 'Milk sold — 34L', 1632, 'mpesa', date('now', '-2 days')),
    (5, 15, 'expense', 'feeds', 'Dairy meal — 50kg', 3200, 'cash', date('now', '-5 days')),
    (5, 14, 'expense', 'fertilizer', 'CAN fertilizer — 50kg', 4200, 'bank', date('now', '-30 days'));

-- ============================================================
-- FARM 2 (Alice) — Workers
-- ============================================================
INSERT OR IGNORE INTO workers (farm_id, name, phone, role, wage_type, wage_amount, start_date, active)
VALUES
    (2, 'Samuel Kipchoge', '+254721222333', 'Farm manager', 'monthly', 20000, '2024-01-01', 1),
    (2, 'Ruth Chebet', '+254721222444', 'Casual labour', 'daily', 500, '2025-03-01', 1);

-- ============================================================
-- FARM 5 (David) — Workers
-- ============================================================
INSERT OR IGNORE INTO workers (farm_id, name, phone, role, wage_type, wage_amount, start_date, active)
VALUES
    (5, 'Peter Ochieng', '+254722333444', 'Farm hand', 'monthly', 14000, '2024-06-01', 1),
    (5, 'Jane Akinyi', '+254722333555', 'Dairy attendant', 'monthly', 16000, '2024-08-01', 1);