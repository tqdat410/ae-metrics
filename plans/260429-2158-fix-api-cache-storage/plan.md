---
title: "Fix API/Cache/Storage issues from code review"
description: "Fix recent-20-games gap and /leaderboard 7D inaccuracy by centralising throttling, switching match storage to INSERT-OR-IGNORE, adding a background warmer, and tightening the cache layer."
status: completed
priority: P1
branch: "main"
tags: [pubg, cache, leaderboard, profile, ratelimit, sqlite]
blockedBy: []
blocks: []
created: "2026-04-29T14:58:41.352Z"
createdBy: "ck:plan"
source: skill
---

# Fix API/Cache/Storage issues from code review

## Overview

Implements the fixes from `plans/reports/code-review-260429-2151-api-cache-storage.md`.
Goal: `/profile` recent panel reflects all games PUBG actually returns, `/leaderboard` shows every linked user with accurate 7D activity, and PUBG API calls stay under the rate limit.

Reference: see report for root-cause mapping (C1–C5, H1–H5, M1–M5, L1–L5).

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Quick wins (throttle + dedup + index)](./phase-01-quick-wins-throttle-dedup-index.md) | Completed |
| 2 | [Redesign (warmer + read-from-DB + schema)](./phase-02-redesign-warmer-read-from-db-schema.md) | Completed |
| 3 | [Tests](./phase-03-tests.md) | Completed |
| 4 | [Docs](./phase-04-docs.md) | Completed |
| 5 | [Cleanup](./phase-05-cleanup.md) | Completed |

## Dependencies

- Phase 2 depends on Phase 1 (uses centralised throttle).
- Phase 3 depends on Phase 2 (tests target final shape).
- Phases 4–5 depend on Phase 3.

## Key Decisions

- `match_summaries` is the single source of truth; cursor's `recent_match_ids` set semantics are dropped.
- Throttling moves into `_get_json` so every PUBG GET is rate-limited (no per-call-site `throttle()`).
- `played_at` stays as ISO string; we add `played_at_unix INTEGER` for numeric range queries.
- Background warmer runs every 5 min when ≥1 linked user exists; `/profile` and `/leaderboard` read DB only.
- Outer `profile-overview` cache is removed; per-source caches retained.

## Completed Implementation

- Centralized provider throttling in `PubgProvider._get_json`.
- Match storage changed to `INSERT OR IGNORE`.
- Schema v2 shipped with `played_at_unix` and numeric 7D aggregation.
- `/leaderboard` now reads DB only.
- `/profile` recent reads from DB with one-account fallback.
- Background match warmer added and wired into bot lifecycle.
- Shared `account_from_link` helper extracted.
- Docs updated to reflect warmer-backed ingestion and DB-first reads.

## Verification

- `pytest`: 53/53 passed locally.
- `compileall`: passed locally.
- docs validation: passed locally.

## Open Decisions (resolved during implementation)

1. PUBG throttling centralized at `_get_json`; production interval still config-driven.
2. `/leaderboard` keeps inactive linked users visible with `0.0h | 0 matches`.
3. Retention policy for `match_summaries` remains none for now; revisit at higher row count.
