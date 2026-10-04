-- ============================================================
-- MIGRATION 002 — PLOTS, TASKS, WORKERS, EQUIPMENT
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- PLOTS (fields / parcels within a farm)
-- ============================================================
CREATE TABLE IF NOT EXISTS plots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    size_acres REAL,
    latitude REAL,
    longitude REAL,
    soil_type TEXT,
    soil_ph REAL,
    irrigation_type TEXT,
    current_crop TEXT,
    notes TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE
);

CREATE INDEX idx_plots_farm ON plots(farm_id);
CREATE INDEX idx_plots_active ON plots(active);

-- ============================================================
-- TASKS
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    enterprise_id INTEGER,
    plot_id INTEGER,
    assigned_to INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT DEFAULT 'medium'
        CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
    status TEXT DEFAULT 'pending'
        CHECK(status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    due_date TEXT,
    completed_at TEXT,
    recurrence TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE SET NULL,
    FOREIGN KEY (plot_id) REFERENCES plots(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_to) REFERENCES workers(id) ON DELETE SET NULL
);

CREATE INDEX idx_tasks_farm ON tasks(farm_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due ON tasks(due_date);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_assigned ON tasks(assigned_to);

-- ============================================================
-- WORKERS (labour on the farm)
-- ============================================================
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    national_id TEXT,
    role TEXT,
    wage_type TEXT DEFAULT 'monthly'
        CHECK(wage_type IN ('monthly', 'daily', 'weekly', 'task', 'hourly')),
    wage_amount REAL,
    start_date TEXT,
    end_date TEXT,
    active INTEGER DEFAULT 1,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE
);

CREATE INDEX idx_workers_farm ON workers(farm_id);
CREATE INDEX idx_workers_active ON workers(active);

-- ============================================================
-- WORKER ATTENDANCE
-- ============================================================
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    farm_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    status TEXT DEFAULT 'present'
        CHECK(status IN ('present', 'absent', 'half-day', 'leave', 'holiday')),
    hours REAL,
    task_id INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE,
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL,
    UNIQUE(worker_id, date)
);

CREATE INDEX idx_attendance_worker ON attendance(worker_id);
CREATE INDEX idx_attendance_farm ON attendance(farm_id);
CREATE INDEX idx_attendance_date ON attendance(date);

-- ============================================================
-- EQUIPMENT
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT,
    make TEXT,
    model TEXT,
    serial_number TEXT,
    purchase_date TEXT,
    purchase_cost REAL,
    current_value REAL,
    last_service_date TEXT,
    next_service_date TEXT,
    service_interval_days INTEGER,
    hours_used REAL DEFAULT 0,
    fuel_type TEXT,
    status TEXT DEFAULT 'good'
        CHECK(status IN ('good', 'needs_service', 'broken', 'retired')),
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE
);

CREATE INDEX idx_equipment_farm ON equipment(farm_id);
CREATE INDEX idx_equipment_status ON equipment(status);

-- ============================================================
-- EQUIPMENT MAINTENANCE LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment_maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL,
    maintenance_type TEXT,
    description TEXT,
    cost REAL,
    maintenance_date TEXT NOT NULL,
    performed_by TEXT,
    next_service_date TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
);

CREATE INDEX idx_maint_equipment ON equipment_maintenance(equipment_id);
CREATE INDEX idx_maint_date ON equipment_maintenance(maintenance_date);