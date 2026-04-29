# Project Changelog

Last updated: 2026-04-29

## 2026-04-29

### Changed

- Pivoted the bot from multi-game to `PUBG-only`.
- Replaced old command surface with `/link pubg`, `/unlink`, `/profile`, `/lookup`, `/compare`, `/leaderboard`, `/matches`, and admin link CRUD commands.
- Reduced required runtime secrets to Discord + PUBG only.
- Removed Riot/Valorant runtime paths, providers, and Riot key monitor flow.

### Added

- Version-aware SQLite forward migration from legacy multi-game schema to PUBG-only schema.
- WAL-safe backup creation before legacy schema migration.
- PUBG-only link ownership model using `discord_user_id + pubg_account_id + platform`.
- View-based cache keyed by `pubg_account_id + platform + view`.
- Recent match cursor storage, match summary persistence, and stat snapshot storage.
- Admin permission helper plus admin-managed link metadata.
- Tests for legacy migration, permission checks, cog visibility behavior, provider parsing, and cache freshness behavior.

### Verified

- `.venv\Scripts\python.exe -m pytest -q` passed `27/27`.
- `.venv\Scripts\python.exe -m pytest --cov=bot --cov-report=term-missing -q` passed with `62%` bot coverage.
- Local compile/import checks passed.

### Known Gaps

- No live Discord smoke test completed yet.
- No live PUBG API smoke test completed yet.
- Coverage remains weakest in `bot/cogs/stats_cog.py`, `bot/cogs/leaderboard_cog.py`, `bot/embeds.py`, and `bot/main.py`.
- Deployment guide still needs full PUBG-only runbook cleanup.
