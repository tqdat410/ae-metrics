# System Architecture

Last updated: 2026-04-28

## Architecture Summary

AE Metrics is a single-process async Discord bot. Discord slash commands call feature cogs, cogs use SQLite for linked accounts and cache, and providers fetch rank data from external game APIs.

```text
Discord user
  -> Guild slash command
  -> GameStatsBot
  -> Cog handler
  -> Validators / DB / Cache
  -> Game provider
  -> External API
  -> Discord embed response
```

## Runtime Flow

1. The module entry point runs the async bot startup.
2. Settings load from `.env` through the settings helper.
3. Required secret validation fails startup if required API secrets are blank.
4. Logging writes to stdout and `bot.log`.
5. Bot setup initializes SQLite, loads all cogs, syncs commands to one guild, and starts background tasks.
6. Shutdown closes background tasks, HTTP client, DB connection, then Discord client.

## Key Components

| Component | Responsibility |
| --- | --- |
| Bot class | Discord lifecycle, cog loading, command sync, cleanup |
| Cogs | Slash command handlers and user-facing error messages |
| DB layer | SQLite migrations, links, cache, state |
| Providers | LoL, Valorant, and PUBG HTTP integration |
| Cache | Game-specific rank TTL |
| Rate limiter | Lightweight sequential throttle |
| Key monitor | Riot key age warning and reload timestamp |

## Data Flow By Command

| Command | Flow |
| --- | --- |
| `/link lol` | Parse Riot ID -> validate region -> Riot lookup -> save link |
| `/link valo` | Parse Riot ID -> validate region -> Henrik lookup -> save link |
| `/link pubg` | Validate platform -> PUBG player lookup -> save link |
| `/rank` | Read linked account -> cache hit or provider fetch -> embed |
| `/lookup` | Validate input -> provider lookup -> provider rank fetch -> embed, no DB write |
| `/leaderboard` | List links -> throttle/cache/fetch each -> sort by rank weight -> embed |
| `/admin reload-key` | Verify admin -> read `.env` -> update process env/settings -> mark timestamp |

## Persistence

SQLite is a single database file at `DB_PATH` or `bot.db`.

| Table | Writes |
| --- | --- |
| `linked_accounts` | `/link`, `/unlink` |
| `rank_cache` | `/rank`, `/leaderboard`, cache invalidation |
| `api_state` | Riot key timestamp, PUBG season cache |

The DB module uses one `aiosqlite` connection for the process, WAL mode, and committed writes per helper.

## External Integrations

| Integration | Auth | Main use |
| --- | --- | --- |
| Discord | `DISCORD_TOKEN` | Slash command runtime |
| Riot API | `X-Riot-Token` | LoL account, summoner, ranked queue data |
| HenrikDev | Authorization header | Valorant account and MMR data |
| PUBG API | Bearer authorization header | PUBG player, seasons, ranked stats |

## Deployment Architecture

Deployment files target Ubuntu on Oracle Cloud Free ARM:

```text
/opt/discord-bot/
  bot/
  .venv/
  .env
  bot.db
/etc/systemd/system/discord-bot.service
/etc/logrotate.d/discord-bot
/var/log/discord-bot/bot.log
```

`deploy/install.sh` installs Python 3.11, creates the venv, installs requirements, registers the service, and enables it. `deploy/update.sh` pulls latest code, reinstalls requirements, restarts the service, and prints service status.

## Operational Gaps

- No real Discord smoke test recorded.
- No real external API smoke test recorded.
- Coverage is 31%, below the testing plan target.
- PUBG season prewarm currently covers only `steam` on startup.
