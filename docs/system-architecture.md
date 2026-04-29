# System Architecture

Last updated: 2026-04-29

## Architecture Summary

AE Metrics is a single-process async Discord bot focused only on PUBG. Discord slash commands call PUBG-specific cogs, cogs use SQLite for identity/cache/analytics state, and the PUBG provider fetches account, season, ranked, lifetime, mastery, and match data for one simplified overview profile.

```text
Discord user
  -> Guild slash command
  -> GameStatsBot
  -> Cog handler
  -> Permission / Validation / DB / Cache
  -> PUBG provider
  -> PUBG API
  -> Discord embed response
```

## Runtime Flow

1. `bot.main` loads settings from `.env`.
2. Startup validates required Discord/PUBG secrets.
3. Bot initializes SQLite and runs schema setup or legacy migration.
4. Bot loads cogs and syncs commands to one guild.
5. Background tasks prewarm the current PUBG season cache and run a 5-minute match warmer.
6. Shutdown closes tasks, HTTP client, DB, then Discord client.

## Key Components

| Component | Responsibility |
| --- | --- |
| `bot/main.py` | Discord lifecycle, guild sync, DB init, season prewarm, warmer startup/shutdown |
| `bot/cogs/*.py` | PUBG command handlers and visibility/permission behavior |
| `bot/db.py` | SQLite schema setup, migration, links, cache, match state, snapshots |
| `bot/match_warmer.py` | Periodic recent-match ingestion into SQLite |
| `bot/providers/pubg_provider.py` | PUBG account/stats/match HTTP integration |
| `bot/cache.py` | View-based TTL cache for ranked/lifetime/source payloads |
| `bot/permissions.py` | Admin identity check |
| `bot/embeds.py` | Shared message and leaderboard rendering helpers |
| `bot/profile_hub_service.py` | Overview profile assembly and source cache reuse |
| `bot/profile_embeds.py` | Profile embed render rules for all, recent, and rank pages |
| `bot/profile_view.py` | Profile embed button interaction state |
| `bot/compare_view.py` | Compare embed render rules and button interaction state |
| `bot/profile_metrics.py` | Recent-form and analysis heuristics from stored match summaries |

## Data Flow By Command

| Command | Flow |
| --- | --- |
| `/link pubg` | Validate platform -> PUBG player lookup -> save link |
| `/unlink` | Delete linked account and cached views |
| `/profile` | Read linked account -> assemble cached overview payload -> prefer recent matches from SQLite -> cold-fill only if warmer data is absent -> one profile embed with button-switched all, recent, and rank pages |
| `/lookup` | Validate platform -> provider lookup -> assemble cached overview payload -> one overview embed |
| `/compare` | Read both links -> build overview payloads for both -> one compare embed with button-switched all, recent, and rank pages |
| `/leaderboard` | List links -> aggregate stored 7-day survival time from SQLite via `played_at_unix` cutoff -> sort active users -> append inactive users -> public embed |
| `/admin link set/delete` | Verify admin -> mutate another member link -> ephemeral result |

## Match Ingestion Flow

```text
every 5 min
  -> bot.match_warmer.tick()
  -> list linked accounts grouped by platform
  -> fetch recent match ids in batches of 10 accounts
  -> fetch unseen match summaries only
  -> INSERT OR IGNORE into match_summaries
  -> update match_cursors.fetched_at

/profile after warmer, and /leaderboard
  -> read cached sources + match_summaries from SQLite
  -> leaderboard stays DB-only
  -> profile recent path only cold-fills if warmer data is missing
```

## Persistence

SQLite is a single database file at `DB_PATH` or `bot.db`.

| Table | Purpose |
| --- | --- |
| `schema_migrations` | Applied schema version tracking |
| `linked_accounts` | One primary PUBG link per Discord user |
| `rank_cache` | Cached ranked, lifetime, source, recent, and profile payloads by `pubg_account_id + platform + view` |
| `api_state` | Current season cache and small runtime state |
| `match_cursors` | Recent-match heartbeat per account (`fetched_at`) |
| `match_summaries` | Normalized recent match summaries with `played_at` and `played_at_unix` for numeric activity-window queries |
| `stat_snapshots` | Daily snapshots for ranked/lifetime-derived trends |

The DB layer uses one `aiosqlite` connection, WAL mode, additive schema upgrades, and legacy migration with backup-before-forward-copy behavior.

## External Integrations

| Integration | Auth | Main use |
| --- | --- | --- |
| Discord | `DISCORD_TOKEN` | Slash command runtime |
| PUBG API | Bearer authorization header | Account lookup, seasons, ranked, lifetime, matches |

## Operational Gaps

- Real Discord smoke is still missing.
- Real PUBG API smoke is still missing.
- Coverage is improved but still incomplete in startup paths.
- Deployment docs still need full PUBG-only operator cleanup.
