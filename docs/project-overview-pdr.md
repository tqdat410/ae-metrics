# Project Overview And PDR

Last updated: 2026-04-28

## Product Summary

AE Metrics is a private Discord Game Stats Bot for a small server. It lets members link game accounts, query ranks, look up arbitrary players, and compare linked members on leaderboards for LoL, Valorant, and PUBG.

## Users

| User | Need |
| --- | --- |
| Server member | Link own accounts and fetch rank quickly from Discord |
| Server member | Lookup another public player without linking |
| Server group | Compare linked ranks through a leaderboard |
| Bot admin | Reload the 24h Riot dev key without full bot restart |

## Implemented Requirements

| Requirement | Status | Evidence |
| --- | --- | --- |
| Guild-scoped slash commands | Implemented | Bot setup syncs to `DISCORD_GUILD_ID` |
| Account linking | Implemented | `/link lol`, `/link valo`, `/link pubg` |
| Account unlinking | Implemented | `/unlink` deletes link and cache |
| Rank lookup for linked member | Implemented | `/rank` reads the linked account and cache |
| Arbitrary account lookup | Implemented | `/lookup` does provider fetch without DB write |
| Leaderboard | Implemented | `/leaderboard` lists linked members and sorts by rank weight |
| SQLite persistence | Implemented | `linked_accounts`, `rank_cache`, `api_state` |
| Provider error mapping | Implemented | HTTP 404/429/401/403/5xx mapped by shared provider handler |
| Riot dev-key reload | Implemented | `/admin reload-key` reads `.env` and updates settings |
| Oracle/systemd deployment files | Implemented | `deploy/install.sh`, `deploy/update.sh`, service, logrotate |

## Non-Functional Requirements

| Requirement | Current state |
| --- | --- |
| Python version | Target 3.11+; local validation used 3.13.4 |
| Small private server scale | Design assumes fewer than 10 members |
| Async IO | Providers, DB, and Discord handlers are async |
| Secrets handling | `.env.example` documents keys; real `.env` not required in repo |
| Fast interaction response | Command handlers defer before external API work |
| File size | Current code modules are under 200 LOC each |

## Acceptance Status

| Check | Status |
| --- | --- |
| `compileall` | Passed, per task context |
| `pytest` | Passed 22/22, per task context |
| Coverage | 31%, below plan target |
| Real Discord smoke | Not done |
| Real external API smoke | Not done |

## Out Of Scope For Current Implementation

- Multi-server operation.
- OAuth flows or web dashboard.
- High-volume public bot rate-limit strategy.
- Automated daily Riot key renewal.
- Discord E2E tests.

## Open Product Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Riot dev key expires every 24h | LoL lookup failure | Key monitor plus `/admin reload-key` |
| HenrikDev API availability | Valorant lookup failure | User-friendly upstream errors |
| PUBG season cache stale | PUBG rank failure | 7-day season cache and startup prewarm for `steam` |
| Low coverage | Regressions can slip | Add provider/cog tests before feature expansion |
| No real smoke test | Unknown Discord/API runtime issues | Run README manual checklist with real accounts |
