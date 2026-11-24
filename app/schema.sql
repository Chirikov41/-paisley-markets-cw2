-- Paisley Christmas Markets - proof-of-concept schema
-- SQLite (3.35+). Foreign keys are enabled per connection in app/db.py.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS traders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    pitch       TEXT,
    trading_days TEXT NOT NULL DEFAULT 'both',
    description TEXT,
    website     TEXT,
    featured    INTEGER NOT NULL DEFAULT 0 CHECK (featured IN (0, 1))
);

CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    reference       TEXT NOT NULL UNIQUE,
    business_name   TEXT NOT NULL,
    contact_name    TEXT NOT NULL,
    email           TEXT NOT NULL,
    phone           TEXT,
    category_id     INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    product_summary TEXT NOT NULL,
    preferred_days  TEXT NOT NULL,
    stall_type      TEXT NOT NULL DEFAULT 'standard',
    power_required  INTEGER NOT NULL DEFAULT 0 CHECK (power_required IN (0, 1)),
    status          TEXT NOT NULL DEFAULT 'submitted'
                    CHECK (status IN ('submitted', 'under_review', 'approved', 'rejected', 'withdrawn')),
    reviewer_note   TEXT,
    consent_given   INTEGER NOT NULL DEFAULT 0 CHECK (consent_given IN (0, 1)),
    consent_at      TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status);
CREATE INDEX IF NOT EXISTS idx_applications_email  ON applications (email);

CREATE TABLE IF NOT EXISTS admins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor      TEXT NOT NULL,
    action     TEXT NOT NULL,
    entity     TEXT NOT NULL,
    entity_id  INTEGER,
    detail     TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at DESC);
