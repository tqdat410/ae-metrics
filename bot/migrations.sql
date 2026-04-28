CREATE TABLE IF NOT EXISTS linked_accounts (
    discord_id INTEGER NOT NULL,
    game TEXT NOT NULL CHECK(game IN ('lol','valo','pubg')),
    region TEXT NOT NULL,
    game_name TEXT NOT NULL,
    tag_line TEXT,
    puuid TEXT,
    summoner_id TEXT,
    account_id TEXT,
    linked_at INTEGER NOT NULL,
    PRIMARY KEY(discord_id, game)
);

CREATE TABLE IF NOT EXISTS rank_cache (
    discord_id INTEGER NOT NULL,
    game TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY(discord_id, game)
);

CREATE TABLE IF NOT EXISTS api_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_linked_game ON linked_accounts(game);

