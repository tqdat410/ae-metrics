---
phase: 3
title: "Tests"
status: completed
priority: P2
effort: "4h"
dependencies: [2]
---

# Phase 3: Tests

## Overview

Cover the new code paths and the regression scenarios reported in production. No DB mocks; use a temp SQLite file. PUBG provider is the only mocked seam.

## Requirements

- Functional: all existing tests pass; new tests cover dedup, warmer tick, 7D numeric range, all-users leaderboard render, purge on unlink, throttle, DB-only profile path.
- Non-functional: total suite under 30s.

## Architecture

- Reuse existing fixtures.
- Add a fake `PubgProvider` (already a pattern in `test_cogs.py`) returning canned payloads.
- Expose `match_warmer.tick(provider)` as the unit-testable surface; `_loop` calls `tick` then sleeps.

## Related Code Files

- Create: `tests/test_match_warmer.py`.
- Create: `tests/test_db_match_activity.py`.
- Modify: `tests/test_cogs.py`, `tests/test_providers.py`, `tests/test_validators.py` (only if pre-existing assertions break).

## Implementation Steps

1. **Dedup test.** Insert same `match_id` twice with different payloads; assert first wins (INSERT OR IGNORE) and `updated_at` unchanged.
2. **7D numeric range test.** Seed 5 matches at -1d, -3d, -7d+1m, -7d-1m, -10d via `played_at_unix`. Call `list_match_activity_since_unix(now-7d)`; assert exactly 3 rows.
3. **Warmer tick test.** Fake provider returns 3 IDs for 1 account. Call `match_warmer.tick(provider)`; assert 3 `match_summaries` rows, 1 cursor row, second tick = no duplicates.
4. **Leaderboard render test.** 3 linked users, 2 active in 7D. Assert embed contains 3 rows, inactive user shows `0h | 0 matches`.
5. **Purge on unlink test.** Seed match_summaries + cursor + stat_snapshots; call `delete_pubg_link`; assert all three tables empty for that account.
6. **Throttle test.** Override `INTERVALS["pubg"]` to 0.05s; monkeypatch `_client.get` to a no-op response; two back-to-back `_get_json` calls; assert ≥ 50ms elapsed between them.
7. **Profile DB-only path test.** Pre-seed 20 `match_summaries`; build profile via `ProfileHubService.build`; assert fake provider's `fetch_recent_match_ids` / `fetch_match_summary` were NOT called.
8. Run `pytest -q`; fix red.

## Success Criteria

- [x] Regression and new-path tests were added for the warmer, DB reads, and provider/storage changes.
- [x] Existing tests pass after the refactor.
- [x] Local verification passed with `pytest` 53/53.

## Completion Notes

- Added coverage for the match warmer and DB-first recent/profile flows.
- Updated existing tests for the new storage and leaderboard behavior.
- Local verification: `pytest` 53/53 passed, `compileall` passed.

## Risk Assessment

- Risk: throttle test flaky on slow CI. Mitigation: monkeypatch `asyncio.sleep` to record call args instead of actually sleeping.
- Risk: tests assumed old `INSERT OR REPLACE`. Mitigation: grep `upsert_match_summary` in tests; update expectations.
