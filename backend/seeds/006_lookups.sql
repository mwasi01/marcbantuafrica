-- ============================================================
-- SEED 006 — LOOKUP TABLES & SYSTEM CONFIG
-- ============================================================

-- ============================================================
-- SYSTEM CONFIG
-- ============================================================
INSERT OR IGNORE INTO system_config (key, value, type, description, category, public)
VALUES
    ('app.name', 'Marcbantu Africa', 'string', 'Application name', 'general', 1),
    ('app.tagline', 'Smart farming starts with smart management.', 'string', 'Tagline', 'general', 1),
    ('app.version', '1.0.0', 'string', 'Current version', 'general', 1),
    ('app.support_email', 'support@marcbantuafrica.com', 'string', 'Support email', 'general', 1),
    ('app.support_phone', '+254700000000', 'string', 'Support phone', 'general', 1),

    ('subscription.starter_price', '0', 'number', 'Starter tier monthly price (KES)', 'billing', 1),
    ('subscription.pro_price', '500', 'number', 'Pro tier monthly price (KES)', 'billing', 1),
    ('subscription.business_price', '2000', 'number', 'Business tier monthly price (KES)', 'billing', 1),

    ('features.sms_enabled', 'true', 'boolean', 'Enable SMS notifications', 'features', 0),
    ('features.ussd_enabled', 'true', 'boolean', 'Enable USSD access', 'features', 0),
    ('features.whatsapp_enabled', 'true', 'boolean', 'Enable WhatsApp integration', 'features', 0),
    ('features.ai_chatbot', 'true', 'boolean', 'Enable AI chatbot', 'features', 0),
    ('features.pest_diagnosis', 'true', 'boolean', 'Enable AI pest diagnosis', 'features', 0),
    ('features.maintenance_mode', 'false', 'boolean', 'Put app in maintenance mode', 'features', 0),

    ('limits.starter_farms', '1', 'number', 'Max farms on Starter tier', 'limits', 1),
    ('limits.pro_farms', '5', 'number', 'Max farms on Pro tier', 'limits', 1),
    ('limits.business_farms', '50', 'number', 'Max farms on Business tier', 'limits', 1),

    ('weather.default_lat', '-1.286389', 'string', 'Default latitude for weather', 'weather', 0),
    ('weather.default_lon', '36.817223', 'string', 'Default longitude for weather', 'weather', 0),
    ('weather.cache_hours', '1', 'number', 'Weather cache duration in hours', 'weather', 0),

    ('sms.sender_id', 'MARCBANTU', 'string', 'SMS sender ID', 'comms', 0),
    ('sms.daily_price_hour', '6', 'number', 'Hour to send daily prices (24h)', 'comms', 0),
    ('sms.daily_reminder_hour', '7', 'number', 'Hour to send daily reminders', 'comms', 0),

    ('pest.alert_radius_km', '20', 'number', 'Radius for pest outbreak alerts', 'pest', 0),

    ('market.price_source', 'AMIS', 'string', 'Primary market price source', 'market', 0),
    ('market.default_currency', 'KES', 'string', 'Default currency', 'market', 1);

-- ============================================================
-- PEST LIBRARY (common Kenyan pests & diseases)
-- ============================================================
INSERT OR IGNORE INTO pest_library
    (name, scientific_name, type, affected_crops, symptoms, causes, treatment_organic, treatment_chemical, prevention)
VALUES
    ('Fall Armyworm', 'Spodoptera frugiperda', 'insect', 'Maize, Sorghum, Rice',
     'Ragged holes in leaves, moist sawdust-like frass, whorl damage, window-pane feeding.',
     'Moths migrate; warm humid conditions; continuous maize cropping.',
     'Neem extract, Bt (Bacillus thuringiensis), hand-picking, wood ash in whorls.',
     'Ampligo 150 ZC (10ml/20L), Karate 5 EC (10ml/20L), Match 050 EC (10ml/20L). Spray at dusk.',
     'Early planting, crop rotation, intercropping with legumes, scouting twice weekly.'),

    ('Maize Streak Virus', 'Maize streak virus (MSV)', 'virus', 'Maize',
     'Yellow streaks parallel to leaf veins, stunted growth, small cobs, poor grain fill.',
     'Transmitted by leafhoppers; more severe in dry seasons.',
     'No cure — remove infected plants, control leafhoppers.',
     'Imidacloprid seed treatment, Thiamethoxam sprays.',
     'Plant resistant varieties (e.g., KH series), control leafhoppers, plant early.'),

    ('Late Blight', 'Phytophthora infestans', 'fungus', 'Tomatoes, Potatoes',
     'Water-soaked spots on leaves, white mold on underside, brown/black rot on fruit.',
     'Cool, wet conditions; high humidity; poor air circulation.',
     'Copper-based fungicides, remove infected plants, improve drainage.',
     'Ridomil Gold (25g/20L), Mancozeb (50g/20L), Revus (20ml/20L).',
     'Resistant varieties, crop rotation, drip irrigation, stake plants.'),

    ('Bacterial Wilt', 'Ralstonia solanacearum', 'bacteria', 'Tomatoes, Potatoes, Eggplant',
     'Sudden wilting of green plants, brown discoloration in stem, white bacterial ooze.',
     'Soil-borne; warm humid conditions; contaminated tools and water.',
     'No effective organic treatment — remove and destroy infected plants.',
     'Copper hydroxide soil drench (limited effectiveness).',
     'Crop rotation (3+ years), resistant varieties, raised beds, clean tools.'),

    ('Aphids', 'Aphidoidea', 'insect', 'Kale, Tomatoes, Beans, Many vegetables',
     'Curled leaves, sticky honeydew, black sooty mold, stunted growth.',
     'Warm dry conditions; high nitrogen fertilization.',
     'Ladybugs, neem oil, soap spray, garlic-chili spray.',
     'Actara 25 WG (4g/20L), Confidor 200 SL (5ml/20L).',
     'Encourage natural predators, avoid excess nitrogen, reflective mulches.'),

    ('Striga (Witchweed)', 'Striga hermonthica', 'weed', 'Maize, Sorghum, Millet',
     'Purple/pink flowers emerging from soil, stunted crop, yellowing, poor yields.',
     'Continuous cereal cropping, poor soil fertility, dry conditions.',
     'Hand-pull before flowering, push-pull with Desmodium.',
     'No effective chemical control once emerged.',
     'Crop rotation with legumes, nitrogen fertilization, resistant varieties.'),

    ('Coffee Berry Borer', 'Hypothenemus hampei', 'insect', 'Coffee',
     'Small holes in berries, black dust around berries, empty berries.',
     'Warm humid conditions; poor farm sanitation.',
     'Beauveria bassiana (fungal biopesticide), hand-pick infested berries.',
     'Chlorpyrifos, Imidacloprid (follow label directions).',
     'Timely picking, strip harvest, farm sanitation, shade management.'),

    ('Tomato Leaf Miner', 'Tuta absoluta', 'insect', 'Tomatoes, Potatoes',
     'Blotchy mines on leaves, curled leaflets, holes in fruit, heavy defoliation.',
     'Warm climate; continuous tomato cropping.',
     'Pheromone traps, neem oil, Bt sprays, remove infested leaves.',
     'Coragen (5ml/20L), Ampligo 150 ZC (10ml/20L), Tracer (5ml/20L).',
     'Crop rotation, remove crop debris, pheromone traps, resistant varieties.'),

    ('Bollworm', 'Helicoverpa armigera', 'insect', 'Tomatoes, Cotton, Maize, Beans',
     'Circular holes in fruit, bored cobs, caterpillars inside, droppings.',
     'Warm weather; continuous cropping.',
     'Bt sprays, neem extract, hand-pick caterpillars, Trichogramma wasps.',
     'Ampligo 150 ZC, Karate 5 EC, Match 050 EC.',
     'Crop rotation, early scouting, trap crops.'),

    ('Rust', 'Puccinia spp.', 'fungus', 'Beans, Wheat, Maize',
     'Orange/brown pustules on leaves and stems, yellowing, defoliation.',
     'Cool humid conditions; susceptible varieties.',
     'Sulfur dust, remove infected leaves.',
     'Folicur (10ml/20L), Tilt 250 EC (10ml/20L).',
     'Resistant varieties, crop rotation, proper spacing.');

-- ============================================================
-- SMS TEMPLATES
-- ============================================================
INSERT OR IGNORE INTO sms_templates (code, name, body, variables, language)
VALUES
    ('WELCOME', 'Welcome new farmer',
     'Welcome to Marcbantu Africa, {name}! Your farm management journey starts now. Reply HELP for commands.',
     'name', 'en'),

    ('DAILY_PRICE', 'Daily market price alert',
     '{crop} today: KES {price}/{unit} at {market}. Reply PRICE for more.',
     'crop,price,unit,market', 'en'),

    ('WEATHER_ALERT', 'Weather alert',
     'Weather alert: {condition} expected in {location} on {date}. Plan accordingly.',
     'condition,location,date', 'en'),

    ('MILK_REMINDER', 'Milk record reminder',
     'Hi {name}, remember to record today''s milk production. Reply MILK [litres].',
     'name', 'en'),

    ('PAYMENT_DUE', 'Loan payment reminder',
     'Hi {name}, your loan repayment of KES {amount} is due on {date}. Please ensure funds are ready.',
     'name,amount,date', 'en'),

    ('PEST_ALERT', 'Pest outbreak alert',
     'PEST ALERT: {pest} reported in your area. Scout your {crop} today. Reply HELP for treatment tips.',
     'pest,crop', 'en'),

    ('VACCINATION', 'Vaccination reminder',
     'Hi {name}, vaccination for your {animal} is due on {date}. Contact your vet.',
     'name,animal,date', 'en'),

    ('WEEKLY_SUMMARY', 'Weekly farm summary',
     'Weekly summary: Income KES {income}, Expenses KES {expenses}, Profit KES {profit}. Keep going, {name}!',
     'income,expenses,profit,name', 'en'),

    ('PRICE_TARGET', 'Price target hit',
     'Great news! {crop} at {market} hit KES {price}. Your target was KES {target}. Consider selling.',
     'crop,market,price,target', 'en'),

    ('REGISTER_CONFIRM', 'Registration confirmation',
     'Hi {name}, welcome to Marcbantu! Your account is ready. Visit marcbantuafrica.com to start.',
     'name', 'en');

-- ============================================================
-- USSD MENUS
-- ============================================================
INSERT OR IGNORE INTO ussd_menus (code, title, body, options, parent_code, is_terminal)
VALUES
    ('main', 'Main Menu',
     'Welcome to Marcbantu\n1. Market prices\n2. Record activity\n3. Check balance\n4. Weather\n5. Help',
     '1:prices,2:record,3:balance,4:weather,5:help', NULL, 0),

    ('prices', 'Market Prices',
     'Today''s prices:\n{crop_list}\n0. Back',
     '0:main', 'main', 0),

    ('record', 'Record Activity',
     'What do you want to record?\n1. Milk\n2. Eggs\n3. Sales\n4. Expense\n0. Back',
     '1:milk,2:eggs,3:sales,4:expense,0:main', 'main', 0),

    ('milk', 'Record Milk',
     'Enter litres of milk:',
     NULL, 'record', 0),

    ('balance', 'Check Balance',
     'Income: KES {income}\nExpenses: KES {expenses}\nProfit: KES {profit}\n0. Back',
     '0:main', 'main', 1),

    ('weather', 'Weather',
     '{location} forecast:\n{forecast}\n0. Back',
     '0:main', 'main', 1),

    ('help', 'Help',
     'Marcbantu Help\nReply to SMS with:\nMILK [litres]\nPRICE\nBALANCE\nWEATHER\n0. Back',
     '0:main', 'main', 1),

    ('register', 'Register',
     'To register, visit marcbantuafrica.com or ask your extension officer.',
     NULL, NULL, 1);

-- ============================================================
-- WHATSAPP TEMPLATES
-- ============================================================
INSERT OR IGNORE INTO whatsapp_templates (name, language, category, body, variables, approved)
VALUES
    ('welcome_farmer', 'en', 'UTILITY',
     'Hello {{1}}! Welcome to Marcbantu Africa. Your farm management assistant is ready. Type "help" to see what I can do.',
     'name', 1),

    ('daily_summary', 'en', 'UTILITY',
     'Hi {{1}}, your farm summary for {{2}}:\nIncome: KES {{3}}\nExpenses: KES {{4}}\nProfit: KES {{5}}\nKeep up the great work!',
     'name,date,income,expenses,profit', 1),

    ('market_update', 'en', 'UTILITY',
     '{{1}} update: {{2}} at {{3}} is now KES {{4}}/{{5}}. Log in to Marcbantu to see more.',
     'date,crop,market,price,unit', 1),

    ('pest_warning', 'en', 'UTILITY',
     'Pest alert in your area: {{1}}. Affected crops: {{2}}. Scout your farm today. Reply for treatment tips.',
     'pest,crops', 1);

-- ============================================================
-- MIGRATION TRACKING (mark all migrations as applied)
-- ============================================================
INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES
    ('001', 'initial_schema'),
    ('002', 'add_plots'),
    ('003', 'add_market_prices'),
    ('004', 'add_pest_scouting'),
    ('005', 'add_learning'),
    ('006', 'add_communications'),
    ('007', 'add_audit_log');

-- ============================================================
-- WEATHER CACHE (sample data for offline testing)
-- ============================================================
INSERT OR IGNORE INTO weather_cache (latitude, longitude, location_name, forecast_date, data, expires_at)
VALUES
    (-1.1167, 36.6500, 'Limuru', date('now'),
     '{"current":{"temp":24,"humidity":68,"wind":12,"condition":"Partly cloudy"},"daily":[{"date":"today","high":26,"low":14,"rain":10},{"date":"tomorrow","high":25,"low":14,"rain":20},{"date":"+2","high":22,"low":13,"rain":80}]}',
     datetime('now', '+1 hour')),
    (-0.3667, 35.9333, 'Njoro', date('now'),
     '{"current":{"temp":22,"humidity":70,"wind":10,"condition":"Cloudy"},"daily":[{"date":"today","high":24,"low":12,"rain":30},{"date":"tomorrow","high":23,"low":12,"rain":50},{"date":"+2","high":21,"low":11,"rain":70}]}',
     datetime('now', '+1 hour'));