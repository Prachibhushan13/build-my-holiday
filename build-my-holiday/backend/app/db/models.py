SCHEMA = """
CREATE TABLE IF NOT EXISTS packages (
    package_id   TEXT PRIMARY KEY,
    group_id     TEXT,
    option_label TEXT,
    status       TEXT NOT NULL DEFAULT 'PLANNED',
    reference    TEXT,
    request_json TEXT NOT NULL,
    spec_json    TEXT NOT NULL,
    trip_json    TEXT NOT NULL,
    total_inr    INTEGER NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations (
    reference     TEXT PRIMARY KEY CHECK (length(reference) = 10),
    package_id    TEXT NOT NULL UNIQUE,
    snapshot_json TEXT NOT NULL,
    confirmed_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_packages_group ON packages(group_id);
"""
