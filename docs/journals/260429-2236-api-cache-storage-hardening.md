# API Cache Storage Hardening

**Date**: 2026-04-29 22:36
**Severity**: High
**Component**: PUBG recent-match ingestion, profile recent panel, leaderboard activity
**Status**: Resolved

## What Happened

The recent-match pipeline looked stable on the surface, but the review exposed two ugly holes after the first refactor pass. First, match dedup was keyed only by `match_id`, while the stored payload is player-specific. Second, `/profile` trusted any stored recent rows, even if a cold-fill died halfway through and left a truncated window in SQLite.

## The Brutal Truth

This was the kind of bug that hides behind green tests and then quietly lies to users. Two linked members could play the same match and one of them would effectively lose that match from their own recent stats. Worse, partial cold-fill state could keep serving incomplete recent panels until the warmer happened to repair it later. That is not a cosmetic issue. That is bad data with a friendly UI on top.

## Technical Details

- `match_summaries` moved from `PRIMARY KEY(match_id)` to `PRIMARY KEY(match_id, pubg_account_id, platform)`.
- `db.match_summary_exists(...)` is now scoped by `match_id + pubg_account_id + platform`.
- `ProfileHubService._recent_matches(...)` now trusts stored rows only when `match_cursors.fetched_at` exists.
- Local verification passed after the fixes:
  - `pytest -q` -> `53 passed`
  - `python -m compileall bot tests` -> pass
  - `validate-docs` -> pass

## What We Tried

The first pass centralized throttling, moved leaderboard reads to DB, added the warmer, and switched match writes to `INSERT OR IGNORE`. That fixed the rate-limit and request-path problems, but it was not enough because the dedup key was still wrong.

## Root Cause Analysis

The bad assumption was treating a PUBG match as one global row when the stored row actually represents one player's stats inside that match. The second bad assumption was treating “some recent rows exist” as equivalent to “the recent window is complete”.

## Lessons Learned

- If the payload is participant-scoped, the storage key must be participant-scoped too.
- DB-first read paths need a completeness signal, not just non-empty data.
- Review findings that smell like data correctness bugs deserve immediate follow-through, even after green tests.

## Next Steps

- Add a dedicated legacy DB upgrade test that exercises `_apply_schema_v3` against an old on-disk schema.
- Optionally dedupe duplicate match IDs inside one warmer batch before detail fetches to avoid wasted upstream calls.
