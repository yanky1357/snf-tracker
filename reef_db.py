"""ReefPilot — Database initialization and helpers."""

import os

DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras


def get_db():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        import sqlite3
        conn = sqlite3.connect(os.environ.get('REEF_DB_PATH', 'reefpilot.db'))
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        return conn


def db_execute(conn, query, params=None):
    if USE_POSTGRES:
        query = query.replace('?', '%s')
        query = query.replace('AUTOINCREMENT', '')
        query = query.replace('INTEGER PRIMARY KEY ', 'SERIAL PRIMARY KEY ')
    cur = conn.cursor()
    cur.execute(query, params or [])
    return cur


def db_fetchall(conn, query, params=None):
    if USE_POSTGRES:
        query = query.replace('?', '%s')
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params or [])
        return cur.fetchall()
    else:
        cur = conn.execute(query, params or [])
        return [dict(r) for r in cur.fetchall()]


def db_fetchone(conn, query, params=None):
    if USE_POSTGRES:
        query = query.replace('?', '%s')
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params or [])
        return cur.fetchone()
    else:
        cur = conn.execute(query, params or [])
        row = cur.fetchone()
        return dict(row) if row else None


def db_fetchval(conn, query, params=None):
    if USE_POSTGRES:
        query = query.replace('?', '%s')
        cur = conn.cursor()
        cur.execute(query, params or [])
        return cur.fetchone()[0]
    else:
        return conn.execute(query, params or []).fetchone()[0]


def init_db():
    conn = get_db()
    try:
        if USE_POSTGRES:
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS reef_users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    display_name VARCHAR(100),
                    tank_size_gallons REAL,
                    tank_type VARCHAR(50) DEFAULT 'mixed_reef',
                    salt_brand VARCHAR(50),
                    sump_size_gallons REAL,
                    onboarded SMALLINT DEFAULT 0,
                    experience_level VARCHAR(50),
                    tank_age_months INTEGER,
                    goals TEXT,
                    budget_monthly REAL,
                    time_weekly_hours REAL,
                    current_problems TEXT,
                    onboard_profile TEXT,
                    fish_count INTEGER,
                    dosing VARCHAR(20),
                    water_change_schedule VARCHAR(30),
                    maintenance_day VARCHAR(15),
                    has_sump SMALLINT DEFAULT 0,
                    filtration TEXT,
                    onboard_plan TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS parameter_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    parameter_type VARCHAR(30) NOT NULL,
                    value REAL NOT NULL,
                    unit VARCHAR(10),
                    source VARCHAR(10) DEFAULT 'manual',
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS livestock (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category VARCHAR(30) NOT NULL,
                    species VARCHAR(100),
                    common_name VARCHAR(100),
                    nickname VARCHAR(50),
                    quantity INTEGER DEFAULT 1,
                    added_date DATE DEFAULT CURRENT_DATE,
                    notes TEXT
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS equipment (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category VARCHAR(30) NOT NULL,
                    brand VARCHAR(100),
                    model VARCHAR(100),
                    notes TEXT,
                    installed_date DATE DEFAULT CURRENT_DATE
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    role VARCHAR(10) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS maintenance_log (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    task_type VARCHAR(30) NOT NULL,
                    notes TEXT,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.cursor().execute('''
                CREATE INDEX IF NOT EXISTS idx_params_user_type_date
                ON parameter_logs(user_id, parameter_type, logged_at)
            ''')
            conn.cursor().execute('''
                CREATE INDEX IF NOT EXISTS idx_chat_user_date
                ON chat_history(user_id, created_at)
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS calendar_tasks (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    title TEXT NOT NULL,
                    description TEXT,
                    frequency VARCHAR(20) NOT NULL,
                    day_of_week VARCHAR(15),
                    day_of_month INTEGER,
                    next_due DATE NOT NULL,
                    last_completed DATE,
                    category VARCHAR(30),
                    auto_generated SMALLINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS maintenance_schedule (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    task_name TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    next_due DATE,
                    last_done DATE,
                    notes TEXT
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS milestones (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    target_value TEXT,
                    current_status TEXT DEFAULT 'locked',
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS cost_entries (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    purchase_date DATE DEFAULT CURRENT_DATE,
                    notes TEXT
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS cost_wizard_profile (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    answer_value TEXT,
                    skipped SMALLINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, question_key)
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS recurring_costs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category TEXT NOT NULL,
                    description TEXT,
                    monthly_amount REAL NOT NULL,
                    source TEXT DEFAULT 'calculated',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, category, description)
                )
            ''')
            conn.cursor().execute('''
                CREATE TABLE IF NOT EXISTS auth_codes (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    code VARCHAR(10) NOT NULL,
                    code_type VARCHAR(20) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used SMALLINT DEFAULT 0,
                    attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.cursor().execute('''
                CREATE INDEX IF NOT EXISTS idx_auth_codes_email_type
                ON auth_codes(email, code_type, used)
            ''')
            # Add email_verified column if not exists
            try:
                conn.cursor().execute('''
                    ALTER TABLE reef_users ADD COLUMN email_verified SMALLINT DEFAULT 0
                ''')
            except Exception:
                pass
            # Add cost_wizard_completed column if not exists
            try:
                conn.cursor().execute('''
                    ALTER TABLE reef_users ADD COLUMN cost_wizard_completed SMALLINT DEFAULT 0
                ''')
            except Exception:
                pass  # Column already exists
            try:
                conn.cursor().execute('''
                    ALTER TABLE reef_users ADD COLUMN tank_photo TEXT
                ''')
            except Exception:
                pass  # Column already exists
            # Dosing/Food Presets & Daily Journal
            try:
                conn.cursor().execute('''
                    CREATE TABLE IF NOT EXISTS dosing_presets (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER,
                        name VARCHAR(100) NOT NULL,
                        preset_type VARCHAR(20) DEFAULT 'dosing',
                        amount VARCHAR(50),
                        frequency VARCHAR(20) DEFAULT 'daily',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.cursor().execute('''
                    CREATE TABLE IF NOT EXISTS dosing_logs (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER,
                        preset_id INTEGER,
                        logged_date DATE DEFAULT CURRENT_DATE,
                        notes VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, preset_id, logged_date)
                    )
                ''')
                conn.cursor().execute('''
                    CREATE TABLE IF NOT EXISTS daily_journal (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER,
                        log_date DATE DEFAULT CURRENT_DATE,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, log_date)
                    )
                ''')
            except Exception:
                pass
        else:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS reef_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    tank_size_gallons REAL,
                    tank_type TEXT DEFAULT 'mixed_reef',
                    salt_brand TEXT,
                    sump_size_gallons REAL,
                    onboarded INTEGER DEFAULT 0,
                    experience_level TEXT,
                    tank_age_months INTEGER,
                    goals TEXT,
                    budget_monthly REAL,
                    time_weekly_hours REAL,
                    current_problems TEXT,
                    onboard_profile TEXT,
                    fish_count INTEGER,
                    dosing TEXT,
                    water_change_schedule TEXT,
                    maintenance_day TEXT,
                    has_sump INTEGER DEFAULT 0,
                    filtration TEXT,
                    onboard_plan TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS parameter_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    parameter_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT,
                    source TEXT DEFAULT 'manual',
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS livestock (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category TEXT NOT NULL,
                    species TEXT,
                    common_name TEXT,
                    nickname TEXT,
                    quantity INTEGER DEFAULT 1,
                    added_date DATE DEFAULT CURRENT_DATE,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category TEXT NOT NULL,
                    brand TEXT,
                    model TEXT,
                    notes TEXT,
                    installed_date DATE DEFAULT CURRENT_DATE
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS maintenance_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    task_type TEXT NOT NULL,
                    notes TEXT,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_params_user_type_date
                ON parameter_logs(user_id, parameter_type, logged_at);

                CREATE INDEX IF NOT EXISTS idx_chat_user_date
                ON chat_history(user_id, created_at);

                CREATE TABLE IF NOT EXISTS calendar_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    title TEXT NOT NULL,
                    description TEXT,
                    frequency TEXT NOT NULL,
                    day_of_week TEXT,
                    day_of_month INTEGER,
                    next_due DATE NOT NULL,
                    last_completed DATE,
                    category TEXT,
                    auto_generated BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS maintenance_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    task_name TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    next_due DATE,
                    last_done DATE,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS milestones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    target_value TEXT,
                    current_status TEXT DEFAULT 'locked',
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS cost_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    purchase_date DATE DEFAULT CURRENT_DATE,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS cost_wizard_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    answer_value TEXT,
                    skipped INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, question_key)
                );

                CREATE TABLE IF NOT EXISTS recurring_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES reef_users(id),
                    category TEXT NOT NULL,
                    description TEXT,
                    monthly_amount REAL NOT NULL,
                    source TEXT DEFAULT 'calculated',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, category, description)
                );


                CREATE TABLE IF NOT EXISTS auth_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    code TEXT NOT NULL,
                    code_type TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used INTEGER DEFAULT 0,
                    attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_auth_codes_email_type
                ON auth_codes(email, code_type, used);
            ''')
            # Add email_verified column if not exists
            try:
                conn.execute('ALTER TABLE reef_users ADD COLUMN email_verified INTEGER DEFAULT 0')
            except Exception:
                pass
            # Add cost_wizard_completed column if not exists
            try:
                conn.execute('ALTER TABLE reef_users ADD COLUMN cost_wizard_completed INTEGER DEFAULT 0')
            except Exception:
                pass  # Column already exists
            try:
                conn.execute('ALTER TABLE reef_users ADD COLUMN tank_photo TEXT')
            except Exception:
                pass  # Column already exists
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS dosing_presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    preset_type TEXT DEFAULT 'dosing',
                    amount TEXT,
                    frequency TEXT DEFAULT 'daily',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS dosing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    preset_id INTEGER REFERENCES dosing_presets(id) ON DELETE CASCADE,
                    logged_date DATE DEFAULT (date('now')),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, preset_id, logged_date)
                );
                CREATE TABLE IF NOT EXISTS daily_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    log_date DATE DEFAULT (date('now')),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, log_date)
                );
            ''')
        conn.commit()
    finally:
        conn.close()
