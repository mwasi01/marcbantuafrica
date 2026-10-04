-- ============================================================
-- MIGRATION 005 — LEARNING PLATFORM
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- COURSES
-- ============================================================
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    slug TEXT UNIQUE,
    description TEXT,
    long_description TEXT,
    category TEXT,
    level TEXT DEFAULT 'beginner'
        CHECK(level IN ('beginner', 'intermediate', 'advanced')),
    language TEXT DEFAULT 'en',
    duration_minutes INTEGER,
    lesson_count INTEGER DEFAULT 0,
    thumbnail_url TEXT,
    instructor TEXT,
    is_free INTEGER DEFAULT 1,
    price REAL DEFAULT 0,
    published INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_courses_category ON courses(category);
CREATE INDEX idx_courses_level ON courses(level);
CREATE INDEX idx_courses_published ON courses(published);

-- ============================================================
-- LESSONS
-- ============================================================
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    video_url TEXT,
    audio_url TEXT,
    pdf_url TEXT,
    order_num INTEGER NOT NULL,
    duration_minutes INTEGER,
    quiz_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

CREATE INDEX idx_lessons_course ON lessons(course_id);
CREATE INDEX idx_lessons_order ON lessons(course_id, order_num);

-- ============================================================
-- ENROLLMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    progress INTEGER DEFAULT 0 CHECK(progress >= 0 AND progress <= 100),
    current_lesson_id INTEGER,
    completed INTEGER DEFAULT 0,
    completed_at TEXT,
    certificate_url TEXT,
    enrolled_at TEXT DEFAULT (datetime('now')),
    last_activity_at TEXT,
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (current_lesson_id) REFERENCES lessons(id) ON DELETE SET NULL,
    UNIQUE(farmer_id, course_id)
);

CREATE INDEX idx_enrollments_farmer ON enrollments(farmer_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);

-- ============================================================
-- LESSON PROGRESS (per-lesson tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS lesson_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL,
    completed INTEGER DEFAULT 0,
    completed_at TEXT,
    time_spent_seconds INTEGER DEFAULT 0,
    quiz_score INTEGER,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE,
    FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE,
    UNIQUE(enrollment_id, lesson_id)
);

CREATE INDEX idx_lesson_prog_enrollment ON lesson_progress(enrollment_id);

-- ============================================================
-- VIDEOS (standalone video library)
-- ============================================================
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    video_url TEXT NOT NULL,
    thumbnail_url TEXT,
    duration_seconds INTEGER,
    category TEXT,
    tags TEXT,
    language TEXT DEFAULT 'en',
    view_count INTEGER DEFAULT 0,
    published INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_videos_category ON videos(category);
CREATE INDEX idx_videos_published ON videos(published);

-- ============================================================
-- CHATBOT CONVERSATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS chatbot_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    title TEXT,
    started_at TEXT DEFAULT (datetime('now')),
    ended_at TEXT,
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_conv_farmer ON chatbot_conversations(farmer_id);
CREATE INDEX idx_chat_conv_session ON chatbot_conversations(session_id);

CREATE TABLE IF NOT EXISTS chatbot_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    message TEXT NOT NULL,
    tokens_used INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES chatbot_conversations(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_msg_conv ON chatbot_messages(conversation_id);

-- ============================================================
-- FORUM (peer-to-peer discussions)
-- ============================================================
CREATE TABLE IF NOT EXISTS forum_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    category TEXT,
    reply_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    pinned INTEGER DEFAULT 0,
    locked INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX idx_forum_cat ON forum_topics(category);
CREATE INDEX idx_forum_created ON forum_topics(created_at);

CREATE TABLE IF NOT EXISTS forum_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    farmer_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    upvotes INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (topic_id) REFERENCES forum_topics(id) ON DELETE CASCADE,
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
);

CREATE INDEX idx_forum_replies_topic ON forum_replies(topic_id);

-- ============================================================
-- EXPERT CONSULTATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS experts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    specialty TEXT,
    bio TEXT,
    phone TEXT,
    email TEXT,
    photo_url TEXT,
    hourly_rate REAL,
    currency TEXT DEFAULT 'KES',
    languages TEXT,
    available INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS consultations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    expert_id INTEGER NOT NULL,
    scheduled_at TEXT NOT NULL,
    duration_minutes INTEGER,
    topic TEXT,
    status TEXT DEFAULT 'scheduled'
        CHECK(status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    notes TEXT,
    cost REAL,
    payment_status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (farmer_id) REFERENCES farmers(id) ON DELETE CASCADE,
    FOREIGN KEY (expert_id) REFERENCES experts(id) ON DELETE CASCADE
);

CREATE INDEX idx_consult_farmer ON consultations(farmer_id);
CREATE INDEX idx_consult_expert ON consultations(expert_id);
CREATE INDEX idx_consult_date ON consultations(scheduled_at);