# Project Changelog

Last updated: 2026-04-28

## 2026-04-28

### Added

- Implemented private Discord Game Stats Bot for LoL, Valorant, and PUBG.
- Added guild-scoped slash commands for linking, unlinking, rank lookup, arbitrary lookup, leaderboard, and admin Riot key reload.
- Added Pydantic settings from `.env` with required secret validation.
- Added SQLite schema and async DB helpers for linked accounts, rank cache, and API state.
- Added provider layer for Riot, HenrikDev, and PUBG APIs.
- Added shared provider dataclasses and exception mapping.
- Added rank embeds, message embeds, and tier weighting for leaderboard sorting.
- Added game-specific cache TTL and lightweight throttle helper.
- Added Riot dev-key monitor and reload timestamp tracking.
- Added Oracle/systemd deployment templates and log rotation config.
- Added pytest suite for validators, DB, cache, embeds, and selected provider behavior.

### Verified

- `compileall` passed, per task context.
- `pytest` passed 22/22, per task context.
- Coverage reported at 31%, per task context.

### Known Gaps

- No real Discord smoke test completed.
- No real external API smoke test completed.
- Automated coverage below original plan target.

