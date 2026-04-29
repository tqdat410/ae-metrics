# Development Roadmap

Last updated: 2026-04-29

## Current Status

The bot has been pivoted from multi-game to `PUBG-only` in code. Local compile/test validation passed, legacy SQLite migration support was added, and the `/profile` command now returns one simplified overview with explicit current-ranked, lifetime, recent, mastery, and metadata sections. Real Discord + live PUBG API smoke is still pending.

## Milestones

| Milestone | Status | Notes |
| --- | --- | --- |
| PUBG-only contract | Done | Commands no longer expose LoL/Valorant flows |
| SQLite migration path | Done | Legacy `linked_accounts` and `rank_cache` migrate forward to PUBG-only schema |
| Runtime cleanup | Done | Riot/Valorant providers and key monitor removed from runtime |
| Core stats overview | Done | `/profile` one overview embed, `/lookup`, overview-style `/compare`, and `7D` activity `/leaderboard` shipped |
| Recent match summaries | Done | Internal recent window, match cursor storage, summary persistence, stat snapshots |
| Automated tests | Partial | 44/44 passing, local compile checks passed |
| Real smoke validation | Not started | Requires Discord token, guild sync, and real PUBG API calls |
| Deployment rollout | Partial | Code ready; operator backup/smoke/rollback sequence still pending |

## Next Priorities

| Priority | Work | Why |
| --- | --- | --- |
| P1 | Run README manual smoke checklist | Confirms Discord sync, overview clarity, permissions, and real PUBG payload behavior |
| P1 | Validate migration backup/restore on target host | Confirms rollback path with the live `bot.db` |
| P2 | Raise stats cog and `main.py` coverage | Biggest remaining automated-confidence gap |
| P2 | Refresh deployment guide for PUBG-only ops | Docs still need runtime/runbook alignment |
| P3 | Expand analytics carefully from stored match summaries | Avoids jumping straight to telemetry-heavy scope |

## Manual Smoke Checklist

- [ ] `/link pubg` with a real PUBG account
- [ ] `/profile` self overview
- [ ] `/profile` another linked member overview
- [ ] `/profile` with `visibility:public`
- [ ] `/lookup` a public PUBG player
- [ ] `/compare` between two linked members
- [ ] `/leaderboard` with 3+ linked members and visible 7-day activity
- [ ] `/unlink` clears link and cached views
- [ ] `/admin link set` and `/admin link delete` enforce admin-only behavior

## Completion Criteria

The PUBG-only pivot is rollout-ready when:

- Real smoke checklist passes.
- Guild command sync succeeds on target deployment.
- Legacy DB backup and migration are validated on the host.
- Logs show stable startup and season prewarm behavior.
- Remaining coverage gap is accepted or improved.
