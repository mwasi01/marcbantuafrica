# Marcbantu Africa — Database Schema

40+ tables across 8 migrations. All tables use SQLite (Cloudflare D1).

---

## Migration Files

| File | Tables |
| :--- | :--- |
| 001_initial_schema.sql | farmers, farms, enterprises, records, transactions |
| 002_add_plots.sql | plots, tasks, workers, attendance, equipment, equipment_maintenance |
| 003_add_market_prices.sql | market_prices, buyers, sales, contracts, price_alerts |
| 004_add_pest_scouting.sql | pest_scouting, pest_library, treatments, chemical_inventory, ipm_practices |
| 005_add_learning.sql | courses, lessons, enrollments, lesson_progress, videos, chatbot_conversations, chatbot_messages, forum_topics, forum_replies, experts, consultations |
| 006_add_communications.sql | communication_log, sms_templates, ussd_sessions, ussd_menus, notifications, device_tokens, message_queue, whatsapp_templates |
| 007_add_audit_log.sql | audit_log, sessions, weather_cache, system_config, uploads, api_keys, rate_limit_log, system_metrics, schema_migrations |
| 008_add_record_sync_fields.sql | ALTER records: client_id, sync_source |

---

## Core Tables

### farmers

The user table.

| Column | Type | Notes |
| :--- | :--- | :--- |
| id | INTEGER PK | Auto |
| phone | TEXT UNIQUE | E.164 |
| email | TEXT UNIQUE | Nullable |
| full_name | TEXT | |
| password_hash | TEXT | PBKDF2 |
| country | TEXT | Default 'Kenya' |
| county | TEXT | |
| location | TEXT | |
| language | TEXT | Default 'en' |
| subscription_tier | TEXT | starter/pro/business |
| subscription_expires_at | TEXT | ISO date |
| verified | INTEGER | 0 or 1 |
| verified_at | TEXT | |
| last_login_at | TEXT | |
| created_at | TEXT | |
| updated_at | TEXT | |

### farms

| Column | Type | Notes |
| :--- | :--- | :--- |
| id | INTEGER PK | |
| farmer_id | INTEGER FK | → farmers |
| name | TEXT | |
| size_acres | REAL | |
| latitude, longitude | REAL | GPS |
| altitude_m | REAL | |
| soil_type | TEXT | |
| irrigation_type | TEXT | rain-fed/drip/sprinkler/furrow/borehole/other |
| water_source | TEXT | |
| notes | TEXT | |
| active | INTEGER | Default 1 |

### enterprises

| Column | Type | Notes |
| :--- | :--- | :--- |
| id | INTEGER PK | |
| farm_id | INTEGER FK | → farms |
| name | TEXT | |
| type | TEXT | crop/livestock/poultry/horticulture/aquaculture/mixed/other |
| species_or_crop | TEXT | |
| quantity, unit | REAL, TEXT | |
| start_date, expected_end_date | TEXT | |
| status | TEXT | planning/active/harvested/sold/closed |

### plots

| Column | Type | Notes |
| :--- | :--- | :--- |
| id | INTEGER PK | |
| farm_id | INTEGER FK | → farms |
| name | TEXT | e.g. "Plot A" |
| size_acres | REAL | |
| latitude, longitude | REAL | |
| soil_type, soil_ph | TEXT, REAL | |
| current_crop | TEXT | |

### records

The unified activity log.

| Column | Type | Notes |
| :--- | :--- | :--- |
| id | INTEGER PK | |
| farm_id | INTEGER FK | → farms |
| enterprise_id | INTEGER FK | Optional |
| plot_id | INTEGER FK | Optional |
| record_type | TEXT | crop_activity/livestock/poultry/input/harvest/sale/expense/observation |
| activity | TEXT | planting/spraying/milking/etc |
| description | TEXT | |
| quantity, unit | REAL, TEXT | |
| cost, revenue | REAL | |
| record_date | TEXT | |
| photo_url | TEXT | |
| latitude, longitude | REAL | |
| client_id | TEXT | Offline sync dedup |
| sync_source | TEXT | online/pwa/sms |
| created_by | INTEGER FK | → farmers |

### transactions

Financial ledger.

| Column | Type | Notes |
| :--- | :--- | :--- |
| id | INTEGER PK | |
| farm_id | INTEGER FK | → farms |
| enterprise_id | INTEGER FK | Optional |
| record_id | INTEGER FK | If auto-created from record |
| type | TEXT | income/expense |
| category | TEXT | milk_sales, feeds, labour, etc |
| description | TEXT | |
| amount | REAL | |
| payment_method | TEXT | cash/mpesa/airtel/bank/cheque/credit |
| reference | TEXT | M-Pesa code etc |
| transaction_date | TEXT | |

---

## Operations Tables

### tasks

| Column | Type |
| :--- | :--- |
| id, farm_id, enterprise_id, plot_id, assigned_to | INTEGER |
| title, description | TEXT |
| priority | TEXT (low/medium/high/urgent) |
| status | TEXT (pending/in_progress/completed/cancelled) |
| due_date, completed_at | TEXT |

### workers

| Column | Type |
| :--- | :--- |
| id, farm_id | INTEGER |
| name, phone, role | TEXT |
| wage_type | TEXT (monthly/daily/weekly/task/hourly) |
| wage_amount | REAL |
| start_date, end_date | TEXT |
| active | INTEGER |

### attendance

| Column | Type |
| :--- | :--- |
| id, worker_id, farm_id, task_id | INTEGER |
| date | TEXT |
| status | TEXT (present/absent/half-day/leave/holiday) |
| hours | REAL |

Unique constraint: `(worker_id, date)`.

### equipment

| Column | Type |
| :--- | :--- |
| id, farm_id | INTEGER |
| name, type, make, model, serial_number | TEXT |
| purchase_date, purchase_cost | TEXT, REAL |
| current_value | REAL |
| last_service_date, next_service_date | TEXT |
| service_interval_days | INTEGER |
| hours_used | REAL |
| status | TEXT (good/needs_service/broken/retired) |

### equipment_maintenance

| Column | Type |
| :--- | :--- |
| id, equipment_id | INTEGER |
| maintenance_type, description | TEXT |
| cost | REAL |
| maintenance_date | TEXT |
| performed_by | TEXT |

---

## Market Tables

### market_prices

| Column | Type | Notes |
| :--- | :--- | :--- |
| id | INTEGER PK | |
| crop | TEXT | |
| variety | TEXT | |
| market | TEXT | |
| county, country | TEXT | |
| price | REAL | |
| currency | TEXT | Default KES |
| unit | TEXT | kg/litre/tray |
| price_date | TEXT | |
| source | TEXT | AMIS/KAMIS/Manual |

### buyers

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| name | TEXT |
| type | TEXT (cooperative/processor/trader/retail/exporter/institution) |
| phone, email, location, county | TEXT |
| rating | REAL (0–5) |
| payment_terms | TEXT |
| products_bought | TEXT |
| active | INTEGER |

### sales

| Column | Type |
| :--- | :--- |
| id, farm_id, buyer_id, enterprise_id, record_id | INTEGER |
| product | TEXT |
| quantity, unit, unit_price, total | REAL/TEXT |
| payment_status | TEXT (pending/partial/paid/cancelled) |
| payment_method | TEXT |
| amount_paid | REAL |
| sale_date, payment_date | TEXT |

### contracts

| Column | Type |
| :--- | :--- |
| id, farm_id, buyer_id, enterprise_id | INTEGER |
| product | TEXT |
| quantity, unit, price_per_unit, total_value | NUMERIC |
| delivery_start_date, delivery_end_date | TEXT |
| status | TEXT (draft/active/fulfilled/cancelled/breached) |

### price_alerts

| Column | Type |
| :--- | :--- |
| id, farmer_id | INTEGER |
| crop | TEXT |
| target_price | REAL |
| direction | TEXT (above/below) |
| active | INTEGER |
| triggered_at | TEXT |

---

## Pest Tables

### pest_scouting

| Column | Type |
| :--- | :--- |
| id, farm_id, plot_id, enterprise_id | INTEGER |
| pest_name | TEXT |
| pest_type | TEXT (insect/fungus/bacteria/virus/weed/rodent/bird/nematode/other) |
| severity | TEXT (low/medium/high/critical) |
| affected_area_pct | REAL |
| photo_url, symptoms | TEXT |
| scout_date | TEXT |

### pest_library

Reference database of pests.

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| name, scientific_name, type | TEXT |
| affected_crops, symptoms, causes | TEXT |
| treatment_organic, treatment_chemical, prevention | TEXT |

### treatments

| Column | Type |
| :--- | :--- |
| id, farm_id, plot_id, enterprise_id, pest_scouting_id | INTEGER |
| product, product_type, active_ingredient | TEXT |
| rate, quantity_used, unit, total_cost | NUMERIC |
| target_pest | TEXT |
| application_date | TEXT |
| pre_harvest_interval_days | INTEGER |

### chemical_inventory

| Column | Type |
| :--- | :--- |
| id, farm_id | INTEGER |
| product_name, active_ingredient, category | TEXT |
| quantity_in_stock, unit | NUMERIC/TEXT |
| purchase_date, expiry_date | TEXT |
| storage_location | TEXT |

### ipm_practices

| Column | Type |
| :--- | :--- |
| id, farm_id, plot_id | INTEGER |
| practice_type | TEXT (crop_rotation/intercropping/biological_control/sanitation/trap_crop/mulching/companion_planting) |
| description | TEXT |
| applied_date | TEXT |

---

## Learning Tables

### courses

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| title, slug, description, long_description | TEXT |
| category, level, language | TEXT |
| duration_minutes, lesson_count | INTEGER |
| thumbnail_url, instructor | TEXT |
| is_free, price, published | INTEGER/REAL |

### lessons

| Column | Type |
| :--- | :--- |
| id, course_id | INTEGER |
| title, content | TEXT |
| video_url, audio_url, pdf_url | TEXT |
| order_num, duration_minutes | INTEGER |

### enrollments

| Column | Type |
| :--- | :--- |
| id, farmer_id, course_id, current_lesson_id | INTEGER |
| progress | INTEGER (0–100) |
| completed | INTEGER |
| completed_at | TEXT |

Unique: `(farmer_id, course_id)`.

### lesson_progress

| Column | Type |
| :--- | :--- |
| id, enrollment_id, lesson_id | INTEGER |
| completed | INTEGER |
| time_spent_seconds, quiz_score | INTEGER |

Unique: `(enrollment_id, lesson_id)`.

### videos

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| title, description, video_url, thumbnail_url | TEXT |
| duration_seconds | INTEGER |
| category, tags, language | TEXT |
| view_count | INTEGER |

### chatbot_conversations

| Column | Type |
| :--- | :--- |
| id, farmer_id | INTEGER |
| session_id | TEXT UNIQUE |
| title, started_at, ended_at | TEXT |

### chatbot_messages

| Column | Type |
| :--- | :--- |
| id, conversation_id | INTEGER |
| role | TEXT (user/assistant/system) |
| message | TEXT |
| tokens_used | INTEGER |

### forum_topics

| Column | Type |
| :--- | :--- |
| id, farmer_id | INTEGER |
| title, body, category | TEXT |
| reply_count, view_count | INTEGER |
| pinned, locked | INTEGER |

### forum_replies

| Column | Type |
| :--- | :--- |
| id, topic_id, farmer_id | INTEGER |
| body | TEXT |
| upvotes | INTEGER |

### experts

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| name, specialty, bio | TEXT |
| phone, email, photo_url | TEXT |
| hourly_rate, currency | REAL, TEXT |
| languages | TEXT |
| available | INTEGER |

### consultations

| Column | Type |
| :--- | :--- |
| id, farmer_id, expert_id | INTEGER |
| scheduled_at | TEXT |
| duration_minutes | INTEGER |
| topic | TEXT |
| status | TEXT (scheduled/completed/cancelled/no_show) |
| cost, payment_status | REAL, TEXT |

---

## Communication Tables

### communication_log

Every SMS/USSD/WhatsApp/voice/email.

| Column | Type |
| :--- | :--- |
| id, farmer_id | INTEGER |
| channel | TEXT (sms/ussd/whatsapp/voice/email/push) |
| direction | TEXT (inbound/outbound) |
| phone, email | TEXT |
| message | TEXT |
| status | TEXT (queued/sent/delivered/failed/received/read) |
| cost, currency | REAL, TEXT |
| reference, external_id | TEXT |

### sms_templates

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| code | TEXT UNIQUE |
| name, body | TEXT |
| variables | TEXT (comma-separated) |
| language | TEXT |
| active | INTEGER |

### ussd_sessions

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| session_id | TEXT UNIQUE |
| phone | TEXT |
| farmer_id | INTEGER |
| current_menu, state, data | TEXT |
| started_at, ended_at | TEXT |

### ussd_menus

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| code | TEXT UNIQUE |
| title, body, options | TEXT |
| parent_code | TEXT |
| is_terminal | INTEGER |

### notifications

| Column | Type |
| :--- | :--- |
| id, farmer_id | INTEGER |
| type | TEXT (weather/market/reminder/alert/system/finance/pest/learning) |
| title, message, action_url, icon | TEXT |
| priority | TEXT (low/normal/high/urgent) |
| read, read_at | INTEGER, TEXT |
| expires_at | TEXT |

### device_tokens

| Column | Type |
| :--- | :--- |
| id, farmer_id | INTEGER |
| token | TEXT UNIQUE |
| platform | TEXT (web/android/ios) |
| active | INTEGER |
| last_used_at | TEXT |

### message_queue

| Column | Type |
| :--- | :--- |
| id, farmer_id | INTEGER |
| channel | TEXT |
| recipient, body | TEXT |
| scheduled_for | TEXT |
| priority, attempts, max_attempts | INTEGER |
| status | TEXT (pending/processing/sent/failed/cancelled) |

### whatsapp_templates

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| name | TEXT UNIQUE |
| language, category, body | TEXT |
| meta_template_id | TEXT |
| approved, active | INTEGER |

---

## System Tables

### audit_log

| Column | Type |
| :--- | :--- |
| id, farmer_id | INTEGER |
| action | TEXT |
| entity, entity_id | TEXT, INTEGER |
| details | TEXT (JSON) |
| ip_address, user_agent, channel | TEXT |

### sessions

| Column | Type |
| :--- | :--- |
| id | TEXT PK |
| farmer_id | INTEGER |
| ip_address, user_agent, device, channel | TEXT |
| expires_at, last_active_at | TEXT |

### weather_cache

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| latitude, longitude | REAL |
| location_name | TEXT |
| forecast_date | TEXT |
| data | TEXT (JSON) |
| expires_at | TEXT |

Unique: `(latitude, longitude, forecast_date)`.

### system_config

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| key | TEXT UNIQUE |
| value | TEXT |
| type | TEXT (string/number/boolean/json) |
| category, description | TEXT |
| public | INTEGER |

### uploads

| Column | Type |
| :--- | :--- |
| id, farmer_id, farm_id | INTEGER |
| entity, entity_id | TEXT, INTEGER |
| file_key | TEXT UNIQUE |
| file_name, file_type, mime_type | TEXT |
| file_size | INTEGER |
| url, thumbnail_url | TEXT |

### api_keys

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| name | TEXT |
| key_hash | TEXT UNIQUE |
| partner_name | TEXT |
| scopes | TEXT |
| rate_limit_per_day | INTEGER |
| active | INTEGER |
| expires_at | TEXT |

### rate_limit_log

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| identifier, endpoint | TEXT |
| window_start | TEXT |
| count | INTEGER |

Unique: `(identifier, endpoint, window_start)`.

### system_metrics

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| metric | TEXT |
| value | REAL |
| unit, tags | TEXT |
| recorded_at | TEXT |

### schema_migrations

| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| version | TEXT UNIQUE |
| name | TEXT |
| applied_at | TEXT |

---

## Indexes

Every foreign key has an index. Every frequently-filtered column has an index:

- `farmers(phone)`, `farmers(email)`, `farmers(county)`, `farmers(subscription_tier)`
- `farms(farmer_id)`, `farms(active)`
- `enterprises(farm_id)`, `enterprises(status)`, `enterprises(type)`
- `records(farm_id)`, `records(enterprise_id)`, `records(date)`, `records(type)`, `records(client_id)`
- `transactions(farm_id)`, `transactions(date)`, `transactions(type)`, `transactions(category)`
- `market_prices(crop)`, `market_prices(date)`, `market_prices(county)`
- `sales(farm_id)`, `sales(buyer_id)`, `sales(date)`, `sales(payment_status)`
- `notifications(farmer_id)`, `notifications(read)`, `notifications(created_at)`
- `communication_log(farmer_id)`, `communication_log(channel)`, `communication_log(status)`

---

## D1 Limits

| Limit | Value |
| :--- | :--- |
| Max DB size | 10 GB |
| Max rows per query | No hard limit (SQLite) |
| Max query duration | 30s |
| Prepared statements | Yes |
| Transactions | Yes (BEGIN/COMMIT) |
| Foreign keys | Enforced (`PRAGMA foreign_keys = ON`) |

---

## Backup & Restore

See `backend/scripts/backup.sh` for automated backup.

Restore:
```bash
gunzip -c backups/marcbantu_prod_YYYYMMDD.sql.gz | \
  wrangler d1 execute marcbantu-db --remote --file=/dev/stdin