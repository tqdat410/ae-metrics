# Project Changelog

Last updated: 2026-04-29

## 2026-04-29

### Added

- Interactive `/profile` hub with default `view=full`, single-panel shortcuts, full return control, exact mode select, and private/public visibility handling.
- Cached profile assembly layers for full deck, overview, ranked, lifetime, recent, mastery, and analysis payloads.
- PUBG mastery ingestion for `weapon_mastery` and `survival_mastery`.
- Recent-form and analysis summaries built from stored match summaries.
- Tests covering hub services, render limits, interaction controls, mastery parsing, and expanded validators.
- Simplified one-embed overview profile with explicit current-ranked, lifetime, recent-form, mastery, and account metadata sections.

### Changed

- Pivoted the bot from multi-game to `PUBG-only`.
- Replaced old command surface with `/link pubg`, `/unlink`, `/profile`, `/lookup`, `/compare`, `/leaderboard`, `/matches`, and admin link CRUD commands.
- Reduced required runtime secrets to Discord + PUBG only.
- Removed Riot/Valorant runtime paths, providers, and Riot key monitor flow.
- Version-aware SQLite forward migration from legacy multi-game schema to PUBG-only schema.
- WAL-safe backup creation before legacy schema migration.
- PUBG-only link ownership model using `discord_user_id + pubg_account_id + platform`.
- View-based cache keyed by `pubg_account_id + platform + view`.
- Recent match cursor storage, match summary persistence, and stat snapshot storage.
- Removed public `/matches`, switched `/compare` to one embed with All / Recent / Rank buttons plus horizontal bar comparisons, switched `/profile` to the same 3-tab embed pattern, and refit `/leaderboard` into one public `7D` activity board ranked by hours played with match count as supporting context.
- Admin permission helper plus admin-managed link metadata.
- Tests for legacy migration, permission checks, cog visibility behavior, provider parsing, and cache freshness behavior.
- Removed `/profile` and `/lookup` multi-view interaction flow in favor of one overview-only contract.

### Verified

- `.venv\Scripts\python.exe -m pytest -q` passed `44/44`.
- `.venv\Scripts\python.exe -m compileall bot tests` passed.
- Local compile/import checks passed.

### Known Gaps

- No live Discord smoke test completed yet.
- No live PUBG API smoke test completed yet.
- Coverage remains weakest in `bot/cogs/stats_cog.py`, `bot/cogs/leaderboard_cog.py`, `bot/embeds.py`, and `bot/main.py`.
- Deployment guide still needs full PUBG-only runbook cleanup.
