CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS linked_accounts (
    discord_user_id INTEGER PRIMARY KEY,
    pubg_account_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    linked_at INTEGER NOT NULL,
    last_resolved_at INTEGER NOT NULL,
    linked_by_admin_id INTEGER
);

CREATE TABLE IF NOT EXISTS rank_cache (
    pubg_account_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    view TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY(pubg_account_id, platform, view)
);

CREATE TABLE IF NOT EXISTS api_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS match_cursors (
    pubg_account_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    cursor_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY(pubg_account_id, platform)
);

CREATE TABLE IF NOT EXISTS match_summaries (
    match_id TEXT NOT NULL,
    pubg_account_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    game_mode TEXT NOT NULL,
    played_at TEXT NOT NULL,
    map_name TEXT,
    placement INTEGER,
    kills INTEGER,
    damage REAL,
    assists INTEGER,
    revives INTEGER,
    survival_time_seconds REAL,
    payload_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY(match_id, pubg_account_id, platform)
);

CREATE TABLE IF NOT EXISTS stat_snapshots (
    pubg_account_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY(pubg_account_id, platform, snapshot_type, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_linked_accounts_platform ON linked_accounts(platform);
CREATE INDEX IF NOT EXISTS idx_rank_cache_platform_view ON rank_cache(platform, view);
CREATE INDEX IF NOT EXISTS idx_match_summaries_account_played ON match_summaries(pubg_account_id, platform, played_at DESC);
CREATE INDEX IF NOT EXISTS idx_match_summaries_played ON match_summaries(played_at);
