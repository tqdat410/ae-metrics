# Project Overview And PDR

Last updated: 2026-04-29

## Product Summary

AE Metrics is a private Discord PUBG stats bot for a small server. It lets members link one PUBG account, open one clear overview profile, compare linked members, and browse a shared leaderboard without leaving Discord.

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
| Linked profile overview | Implemented | `/profile [user] [visibility]` |
| Direct player lookup | Implemented | `/lookup name [platform]` |
| Member compare | Implemented | `/compare user_a user_b` |
| Shared leaderboard | Implemented | `/leaderboard` fixed to 7-day activity |
| Recent match summaries | Internal support only | Recent-20 form inside `/profile` and `/compare` |
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
| Automated tests | Passed `44/44` |
| Coverage | `62%` bot coverage |
| Real Discord smoke | Not done |
| Real PUBG API smoke | Not done |
| Live migration rollback rehearsal | Not done |

## Out Of Scope For Current Implementation

- Multi-game support.
- OAuth flows or web dashboard.
- Telemetry-heavy deep analytics beyond stored-match heuristics.
- Multi-server public-bot scale strategy.
- Full Discord E2E automation.

## Open Product Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| No live smoke test yet | Unknown Discord/API runtime issues | Run README manual checklist |
| Live migration not rehearsed on target host | Rollback confidence gap | Backup + migration validation before production switch |
| Overview mixes current ranked, lifetime, and recent windows | Users can misread time scope | Keep labels explicit in embed copy |
| PUBG upstream freshness is delayed | “Real-time” perception can be wrong | Keep summaries/stats labeled and lightweight |
