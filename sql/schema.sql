PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tender_notices (
    notice_id TEXT PRIMARY KEY,
    publication_date TEXT,
    title TEXT NOT NULL,
    buyer_name TEXT,
    buyer_country TEXT,
    sector TEXT,
    cpv_codes_json TEXT NOT NULL DEFAULT '[]',
    place_codes_json TEXT NOT NULL DEFAULT '[]',
    estimated_value REAL,
    currency TEXT,
    deadline_date TEXT,
    notice_type TEXT,
    procedure_type TEXT,
    ted_url TEXT NOT NULL,
    description TEXT,
    primary_theme TEXT NOT NULL,
    matched_keywords_json TEXT NOT NULL DEFAULT '{}',
    matched_cpv_json TEXT NOT NULL DEFAULT '{}',
    classification_score REAL NOT NULL,
    is_relevant INTEGER NOT NULL CHECK (is_relevant IN (0, 1)),
    opportunity_score REAL NOT NULL CHECK (opportunity_score BETWEEN 0 AND 100),
    score_explanation_json TEXT NOT NULL,
    raw_notice_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    lifecycle_status TEXT NOT NULL DEFAULT 'new'
        CHECK (lifecycle_status IN ('new', 'updated', 'unchanged', 'closed')),
    content_hash TEXT NOT NULL DEFAULT '',
    closed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tenders_country ON tender_notices (buyer_country);
CREATE INDEX IF NOT EXISTS idx_tenders_theme ON tender_notices (primary_theme);
CREATE INDEX IF NOT EXISTS idx_tenders_publication_date ON tender_notices (publication_date);
CREATE INDEX IF NOT EXISTS idx_tenders_score ON tender_notices (opportunity_score DESC);

CREATE TABLE IF NOT EXISTS fetch_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    countries TEXT NOT NULL,
    scope TEXT NOT NULL,
    requested_limit INTEGER NOT NULL,
    api_match_count INTEGER,
    received_count INTEGER NOT NULL,
    relevant_count INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    raw_snapshot_path TEXT,
    fetched_page_count INTEGER NOT NULL DEFAULT 0,
    is_complete INTEGER NOT NULL DEFAULT 0,
    new_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    unchanged_count INTEGER NOT NULL DEFAULT 0,
    closed_count INTEGER NOT NULL DEFAULT 0,
    publication_json_path TEXT,
    publication_parquet_path TEXT
);

CREATE VIEW IF NOT EXISTS relevant_opportunities AS
SELECT *
FROM tender_notices
WHERE is_relevant = 1;
