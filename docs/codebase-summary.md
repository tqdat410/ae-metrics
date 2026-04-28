# Codebase Summary

Last updated: 2026-04-28

## Overview

AE Metrics is a private Discord slash-command bot for game rank lookups across League of Legends, Valorant, and PUBG. It uses Python 3.11+, `discord.py`, async `httpx`, `aiosqlite`, and SQLite persistence.

Repomix compaction was generated during this documentation pass at a temporary path outside the repo to avoid adding non-doc artifacts.

## Runtime Entry Points

| Path | Purpose |
| --- | --- |
| `bot/main.py` | Creates the Discord bot class, initializes DB, loads cogs, syncs guild commands, starts background tasks |
| `bot/config.py` | Loads `.env` settings through Pydantic settings |
| `bot/http_client.py` | Shared lazy `httpx.AsyncClient` with 10s timeout |
| `bot/db.py` | Single async SQLite connection and CRUD helpers |
| `bot/migrations.sql` | Idempotent table/index creation |

## Discord Commands

| Command | Implemented in | Notes |
| --- | --- | --- |
| `/link lol` | `bot/cogs/link_cog.py` | Links Riot ID to Discord user, default region `vn2` |
| `/link valo` | `bot/cogs/link_cog.py` | Links Valorant Riot ID, default region `ap` |
| `/link pubg` | `bot/cogs/link_cog.py` | Links PUBG name, default platform `steam` |
| `/unlink` | `bot/cogs/link_cog.py` | Deletes linked account and cached rank for game |
| `/rank` | `bot/cogs/stats_cog.py` | Gets linked member rank, uses cache |
| `/lookup` | `bot/cogs/stats_cog.py` | Looks up account without DB write |
| `/leaderboard` | `bot/cogs/leaderboard_cog.py` | Fetches linked members sequentially, sorts by rank weight |
| `/admin reload-key` | `bot/cogs/admin_cog.py` | Admin-only Riot key reload from `.env` |

## Data Model

SQLite tables in `bot/migrations.sql`:

| Table | Purpose |
| --- | --- |
| `linked_accounts` | One linked account per Discord user and game |
| `rank_cache` | Cached rank payloads by Discord user and game |
| `api_state` | Small runtime state, including Riot key timestamp and PUBG season cache |

`bot/db.py` enables WAL mode and foreign keys on startup.

## Providers

| Provider | File | External API |
| --- | --- | --- |
| League of Legends | `bot/providers/lol_provider.py` | Riot Account, Summoner, League APIs |
| Valorant | `bot/providers/valorant_provider.py` | HenrikDev Valorant API |
| PUBG | `bot/providers/pubg_provider.py` | PUBG Developer API |

Shared provider dataclasses and provider errors live in `bot/providers/__init__.py`.

## Cache And Throttle

| File | Behavior |
| --- | --- |
| `bot/cache.py` | Rank cache TTL: LoL 15m, Valorant 15m, PUBG 30m |
| `bot/rate_limiter.py` | Per-name async lock plus interval: PUBG 6s, LoL/Valorant 0.1s |
| `bot/key_monitor.py` | Hourly Riot dev-key warning after 22h when `ADMIN_DISCORD_ID` is configured |

## Tests And Validation

| Item | Status |
| --- | --- |
| Compile | `compileall` passed, per task context |
| Tests | `pytest` passed 22/22, per task context |
| Coverage | 31%, per task context |
| Real Discord/API smoke | Not performed |
| Local Python | 3.13.4 |
| Target Python | 3.11+ |

Test files cover validators, embed tier ordering, DB CRUD/cache, cache helper behavior, provider error mapping, LoL region routing, and Valorant MMR parsing.
