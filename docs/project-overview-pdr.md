# Project Overview And PDR

Last updated: 2026-04-29

## Product Summary

AE Metrics is a private Discord PUBG stats bot for a small server. It lets members link one PUBG account, inspect ranked/lifetime views, compare linked members, browse a shared leaderboard, and inspect recent match summaries without leaving Discord.

## Users

| User | Need |
| --- | --- |
| Server member | Link own PUBG account and retrieve stats quickly |
| Server member | Look up another PUBG player without linking |
| Server group | Compare linked members and view a shared leaderboard |
| Bot admin | Manage or correct another member’s PUBG link |

## Implemented Requirements

| Requirement | Status | Evidence |
| --- | --- | --- |
| Guild-scoped slash commands | Implemented | Bot syncs to `DISCORD_GUILD_ID` |
| PUBG account linking | Implemented | `/link pubg`, `/unlink` |
| Linked profile views | Implemented | `/profile [user] [view]` |
| Direct player lookup | Implemented | `/lookup name [platform] [view]` |
| Member compare | Implemented | `/compare user_a user_b [view]` |
| Shared leaderboard | Implemented | `/leaderboard [metric]` |
| Recent match summaries | Implemented | `/matches [user] [count]` |
| Admin link override | Implemented | `/admin link set/delete` |
| SQLite persistence and migration | Implemented | `linked_accounts`, cache, match, snapshot, migration tables |

## Non-Functional Requirements

| Requirement | Current state |
| --- | --- |
| Python version | Target 3.11+; local validation used repo venv |
| Small private server scale | Still designed for fewer than 10 members |
| Async IO | Discord handlers, DB, and provider calls are async |
| Secrets handling | `.env.example` documents required values; real `.env` stays out of repo |
| Response visibility | Personal/admin flows are ephemeral; leaderboard is public |
| Rate budget awareness | Cache + throttle + narrow command surface reduce PUBG API pressure |

## Acceptance Status

| Check | Status |
| --- | --- |
| Automated tests | Passed `27/27` |
| Coverage | `62%` bot coverage |
| Real Discord smoke | Not done |
| Real PUBG API smoke | Not done |
| Live migration rollback rehearsal | Not done |

## Out Of Scope For Current Implementation

- Multi-game support.
- OAuth flows or web dashboard.
- Telemetry-heavy deep analytics.
- Multi-server public-bot scale strategy.
- Full Discord E2E automation.

## Open Product Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| No live smoke test yet | Unknown Discord/API runtime issues | Run README manual checklist |
| Live migration not rehearsed on target host | Rollback confidence gap | Backup + migration validation before production switch |
| Coverage still weak in startup and some cog paths | Regressions can slip | Add deeper cog/startup tests |
| PUBG upstream freshness is delayed | “Real-time” perception can be wrong | Keep summaries/stats labeled and lightweight |
