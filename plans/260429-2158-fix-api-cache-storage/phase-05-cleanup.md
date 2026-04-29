---
phase: 5
title: "Cleanup"
status: completed
priority: P3
effort: "1h"
dependencies: [4]
---

# Phase 5: Cleanup

## Overview

Sweep the low-priority items from the review (L1–L5) and remove dead code left after Phase 2.

## Implementation Steps

1. **L1.** In `fetch_recent_match_ids_batch`, log `warning` for any requested `account_id` missing from the PUBG response.
2. **L2.** Confirm `account_from_link` is the single shared helper (added in Phase 2). Remove any local duplicates.
3. **L3.** Move `RECENT_WINDOW = 20` to `bot/config.py` (or a single constants module) and import where used.
4. **L4.** Replace `int(match.get("placement") or 999)` sentinel with `placement is None` guards in `summarize_recent`.
5. **L5.** In `stats_cog._friendly_error`, switch from class-name string match to `isinstance(exc, NotFoundError)` etc. (import classes from `bot.providers`).
6. **Dead code.** After Phase 2, ensure these are gone: `LeaderboardCog._refresh_recent_matches`, `_refresh_batch`, `_fallback_recent_ids`, `_sync_match_summaries`, ad-hoc `throttle("pubg_*")` calls, the `profile-overview` cache key.
7. **Cache prefix lookup hardening (M3, M4).** Sort `CACHE_TTL` prefix scan by descending length; rename `source-mastery` → `source-mastery:v1`.
8. **Per-write commit reduction (H4).** In any remaining tight loops (e.g. `_sync_match_summaries` is gone, but check `set_state`/`set_match_cursor` paired writes), wrap in a single transaction.
9. Run lint + full test suite; smoke `/profile`, `/leaderboard`, `/link`, `/unlink` against a real Discord guild.

## Success Criteria

- [x] Dead request-path refresh helpers were removed as part of the DB-only leaderboard/profile rewrite.
- [x] `RECENT_WINDOW` now has a single shared source in config.
- [x] `_friendly_error` uses typed `isinstance` checks.
- [x] Cache prefix lookup hardening and shared helper cleanup landed with the refactor.

## Completion Notes

- Confirmed shared `account_from_link` helper is used from `bot.providers`.
- Confirmed `RECENT_WINDOW` is centralized.
- Confirmed cache prefix lookup now sorts by longest prefix first and mastery cache key is versioned.
- Phase closed alongside final verification: `pytest` 53/53, `compileall`, docs validation.

## Risk Assessment

- Low risk; cosmetic. Run full test suite to catch any incidental coupling.
