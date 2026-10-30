PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS states (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS districts (
    id INTEGER PRIMARY KEY,
    state_id INTEGER NOT NULL REFERENCES states(id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state_id, name)
);

CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    source_path TEXT,
    sha256 TEXT,
    source_type TEXT NOT NULL DEFAULT 'local',
    reporting_status TEXT NOT NULL DEFAULT 'unverified',
    last_successful_update TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, sha256)
);

CREATE TABLE IF NOT EXISTS yield_records (
    id INTEGER PRIMARY KEY,
    record_key TEXT NOT NULL UNIQUE,
    crop_id INTEGER NOT NULL REFERENCES crops(id),
    state_id INTEGER REFERENCES states(id),
    district_id INTEGER REFERENCES districts(id),
    season_id INTEGER REFERENCES seasons(id),
    crop_year TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL DEFAULT 'unknown',
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    reporting_status TEXT NOT NULL DEFAULT 'unverified',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS production_records (
    id INTEGER PRIMARY KEY,
    record_key TEXT NOT NULL UNIQUE,
    crop_id INTEGER NOT NULL REFERENCES crops(id),
    state_id INTEGER REFERENCES states(id),
    district_id INTEGER REFERENCES districts(id),
    season_id INTEGER REFERENCES seasons(id),
    crop_year TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL DEFAULT 'unknown',
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    reporting_status TEXT NOT NULL DEFAULT 'unverified',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS area_records (
    id INTEGER PRIMARY KEY,
    record_key TEXT NOT NULL UNIQUE,
    crop_id INTEGER NOT NULL REFERENCES crops(id),
    state_id INTEGER REFERENCES states(id),
    district_id INTEGER REFERENCES districts(id),
    season_id INTEGER REFERENCES seasons(id),
    crop_year TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL DEFAULT 'unknown',
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    reporting_status TEXT NOT NULL DEFAULT 'unverified',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_logs (
    id INTEGER PRIMARY KEY,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    outcome TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_runs (
    id INTEGER PRIMARY KEY,
    model_name TEXT NOT NULL,
    crop_name TEXT,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    artifact_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS variability_results (
    id INTEGER PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id),
    state_id INTEGER REFERENCES states(id),
    season_id INTEGER REFERENCES seasons(id),
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(crop_id, state_id, season_id, source_id)
);

CREATE TABLE IF NOT EXISTS anomaly_records (
    id INTEGER PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id),
    state_id INTEGER REFERENCES states(id),
    crop_year TEXT NOT NULL,
    yield_value REAL NOT NULL,
    trend_value REAL NOT NULL,
    residual REAL NOT NULL,
    score REAL,
    explanation TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(crop_id, state_id, crop_year, source_id)
);

CREATE INDEX IF NOT EXISTS idx_yield_crop_year ON yield_records(crop_id, crop_year);
CREATE INDEX IF NOT EXISTS idx_yield_state_year ON yield_records(state_id, crop_year);
CREATE INDEX IF NOT EXISTS idx_yield_season ON yield_records(season_id);
CREATE INDEX IF NOT EXISTS idx_yield_source ON yield_records(source_id);
CREATE INDEX IF NOT EXISTS idx_district_state ON districts(state_id);