# Codebase Summary

Last updated: 2026-04-29

## Overview

AE Metrics is a private Discord slash-command bot for PUBG account linking, profile overviews, compare flows, shared leaderboards, and internal recent-match analytics. It uses Python 3.11+, `discord.py`, async `httpx`, `aiosqlite`, and SQLite persistence.

## Runtime Entry Points

| Path | Purpose |
| --- | --- |
| `bot/main.py` | Creates bot class, initializes DB, loads cogs, syncs guild commands, starts season prewarm and match warmer |
| `bot/config.py` | Loads `.env` settings |
| `bot/http_client.py` | Shared lazy `httpx.AsyncClient` |
| `bot/db.py` | SQLite connection, schema migration, CRUD helpers |
| `bot/match_warmer.py` | Background 5-minute refresh loop for recent match summaries |
| `bot/migrations.sql` | PUBG-only schema definition |

## Discord Commands

| Command | File | Notes |
| --- | --- | --- |
| `/link pubg` | `bot/cogs/link_cog.py` | Links caller to PUBG account |
| `/unlink` | `bot/cogs/link_cog.py` | Removes caller PUBG link and cached views |
| `/profile` | `bot/cogs/stats_cog.py` | One-embed profile view with button-switched all, recent, and rank pages |
| `/lookup` | `bot/cogs/stats_cog.py` | Direct PUBG lookup without DB write |
| `/compare` | `bot/cogs/stats_cog.py` | One-embed compare with button-switched all, recent, and rank pages |
| `/leaderboard` | `bot/cogs/leaderboard_cog.py` | Public `7D` activity leaderboard ranked by hours played from stored `played_at_unix` activity |
| `/admin link set/delete` | `bot/cogs/admin_cog.py` | Admin-only cross-user link mutation |

## Data Model

| Table | Purpose |
| --- | --- |
| `schema_migrations` | Schema version history |
| `linked_accounts` | PUBG link per Discord member |
| `rank_cache` | Cached payloads for ranked, lifetime, source, recent, and profile views |
| `api_state` | Current season cache |
| `match_cursors` | Recent-match heartbeat state |
| `match_summaries` | Normalized recent matches with `played_at_unix` for numeric activity windows |
| `stat_snapshots` | Daily view snapshots |

## Providers

| File | External API | Responsibility |
| --- | --- | --- |
| `bot/providers/pubg_provider.py` | PUBG Developer API | Account lookup, current season, ranked, lifetime, mastery, recent match ids, match summaries |
| `bot/providers/__init__.py` | shared | Provider dataclasses, errors, factory |

## Cache And Throttle

| File | Behavior |
| --- | --- |
| `bot/cache.py` | View-based cache for source payloads and profile assembly |
| `bot/rate_limiter.py` | Lightweight sequential PUBG throttle, enforced inside provider GETs |

## Tests And Validation

| Item | Status |
| --- | --- |
| Compile/import | Passed locally |
| Tests | `53/53` passing locally |
| Coverage | `62%` bot coverage |
| Real Discord/API smoke | Not performed |

Current tests cover validators, embeds, DB migration/CRUD, purge semantics, cache freshness, warmer ticks, selected cog behavior, `/profile` recent DB reads, and PUBG provider parsing/throttling.
