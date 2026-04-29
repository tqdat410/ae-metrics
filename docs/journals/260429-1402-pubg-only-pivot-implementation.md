# PUBG-only Pivot Landed, Rollout Still Needs Real Smoke

**Date**: 2026-04-29 14:02
**Severity**: High
**Component**: Discord bot runtime, SQLite migration, PUBG provider
**Status**: Resolved in code, rollout pending

## What Happened

The bot was still structurally multi-game, but the product decision was already PUBG-only. That mismatch meant commands, schema, provider registry, env requirements, and docs were all lying in slightly different ways. The implementation had to collapse all of that at once without breaking the live `bot.db`.

## The Brutal Truth

This kind of pivot is where teams usually create fake progress: rename a couple commands, leave old tables around, keep stale docs, and call it done. That would have been garbage here. The hard part was not writing new commands. The hard part was making the persistence model, migration path, permissions, cache keys, and rollout story stop contradicting each other.

## Technical Details

- Replaced multi-game command surface with PUBG-only flows.
- Added forward migration from legacy `linked_accounts(discord_id, game, ...)` to PUBG-only storage.
- Added WAL-safe backup path before legacy migration.
- Added view-based cache and recent match summary persistence.
- Removed Riot/Valorant runtime providers and Riot key monitor.
- Validation ended at `27/27` passing tests and `62%` bot coverage.

## What We Tried

- First pass implemented the pivot and tests.
- Review then found real issues: WAL-unsafe backup, empty `account_id` persistence, admin error leakage, stale-cache snapshots.
- Those were fixed directly and covered with extra tests.

## Root Cause Analysis

The original architecture assumed “one bot, many games” and pushed that assumption into every layer. Once the product scope changed, the codebase needed a true identity/persistence rewrite, not cosmetic command edits.

## Lessons Learned

- Product-scope pivots must rewrite storage boundaries early, not late.
- A backup file existing is not the same thing as a rollback-safe backup.
- Cached data reused for analytics must be treated differently from freshly fetched data.
- Docs drift becomes operational risk fast when commands and env vars change.

## Next Steps

- Run real Discord guild smoke with valid env.
- Rehearse migration against the deployed `bot.db`.
- Confirm rollback path on host, not just in tests.
- Raise coverage further around `StatsCog` and startup.
