# Codebase Summary

Last updated: 2026-04-29

## Overview

AE Metrics is a private Discord slash-command bot for PUBG account linking, profile views, leaderboards, compare flows, and lightweight recent-match summaries. It uses Python 3.11+, `discord.py`, async `httpx`, `aiosqlite`, and SQLite persistence.

## Runtime Entry Points

| Path | Purpose |
| --- | --- |
| `bot/main.py` | Creates bot class, initializes DB, loads cogs, syncs guild commands, starts season prewarm |
| `bot/config.py` | Loads `.env` settings |
| `bot/http_client.py` | Shared lazy `httpx.AsyncClient` |
| `bot/db.py` | SQLite connection, schema migration, CRUD helpers |
| `bot/migrations.sql` | PUBG-only schema definition |

## Discord Commands

| Command | File | Notes |
| --- | --- | --- |
| `/link pubg` | `bot/cogs/link_cog.py` | Links caller to PUBG account |
| `/unlink` | `bot/cogs/link_cog.py` | Removes caller PUBG link and cached views |
| `/profile` | `bot/cogs/stats_cog.py` | Linked profile with `ranked` or `lifetime` view |
| `/lookup` | `bot/cogs/stats_cog.py` | Direct PUBG lookup without DB write |
| `/compare` | `bot/cogs/stats_cog.py` | Compares two linked members |
| `/matches` | `bot/cogs/stats_cog.py` | Shows recent stored/fetched match summaries |
| `/leaderboard` | `bot/cogs/leaderboard_cog.py` | Public leaderboard for supported metrics |
| `/admin link set/delete` | `bot/cogs/admin_cog.py` | Admin-only cross-user link mutation |

## Data Model

| Table | Purpose |
| --- | --- |
| `schema_migrations` | Schema version history |
| `linked_accounts` | PUBG link per Discord member |
| `rank_cache` | Cached payloads for ranked/lifetime/match views |
| `api_state` | Current season cache |
| `match_cursors` | Recent-match polling state |
| `match_summaries` | Normalized recent matches |
| `stat_snapshots` | Daily view snapshots |

## Providers

| File | External API | Responsibility |
| --- | --- | --- |
| `bot/providers/pubg_provider.py` | PUBG Developer API | Account lookup, current season, ranked, lifetime, recent matches, match summaries |
| `bot/providers/__init__.py` | shared | Provider dataclasses, errors, factory |

## Cache And Throttle

| File | Behavior |
| --- | --- |
| `bot/cache.py` | View-based cache for `ranked`, `lifetime`, `recent_matches` |
| `bot/rate_limiter.py` | Lightweight sequential PUBG throttle |

## Tests And Validation

| Item | Status |
| --- | --- |
| Compile/import | Passed locally |
| Tests | `27/27` passing |
| Coverage | `62%` bot coverage |
| Real Discord/API smoke | Not performed |

Current tests cover validators, embeds, DB migration/CRUD, cache freshness, permission helper, selected cog behavior, and PUBG provider parsing.
