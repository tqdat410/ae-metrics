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
5. Background task prewarms the current PUBG season cache.
6. Shutdown closes tasks, HTTP client, DB, then Discord client.

## Key Components

| Component | Responsibility |
| --- | --- |
| `bot/main.py` | Discord lifecycle, guild sync, DB init, season prewarm |
| `bot/cogs/*.py` | PUBG command handlers and visibility/permission behavior |
| `bot/db.py` | SQLite schema setup, migration, links, cache, match state, snapshots |
| `bot/providers/pubg_provider.py` | PUBG account/stats/match HTTP integration |
| `bot/cache.py` | View-based TTL cache for ranked/lifetime/source/overview payloads |
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
| `/profile` | Read linked account -> assemble cached overview payload -> one profile embed with button-switched all, recent, and rank pages |
| `/lookup` | Validate platform -> provider lookup -> assemble cached overview payload -> one overview embed |
| `/compare` | Read both links -> build overview payloads for both -> one compare embed with button-switched all, recent, and rank pages |
| `/leaderboard` | List links -> refresh recent match IDs/summaries -> aggregate stored 7-day survival time -> sort -> public embed |
| `/admin link set/delete` | Verify admin -> mutate another member link -> ephemeral result |

## Persistence

SQLite is a single database file at `DB_PATH` or `bot.db`.

| Table | Purpose |
| --- | --- |
| `schema_migrations` | Applied schema version tracking |
| `linked_accounts` | One primary PUBG link per Discord user |
| `rank_cache` | Cached ranked, lifetime, source, recent, and overview payloads by `pubg_account_id + platform + view` |
| `api_state` | Current season cache and small runtime state |
| `match_cursors` | Last seen recent-match cursor data per account |
| `match_summaries` | Normalized recent match summaries |
| `stat_snapshots` | Daily snapshots for ranked/lifetime-derived trends |

The DB layer uses one `aiosqlite` connection, WAL mode, and legacy migration with backup-before-forward-copy behavior.

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
