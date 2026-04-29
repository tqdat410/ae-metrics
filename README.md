# AE Metrics

Private Discord bot for PUBG account linking, profile lookup, leaderboard views, and lightweight match analytics in a small private server.

## Features

- PUBG-only slash commands for linking, unlinking, direct lookup, overview profiles, compare, leaderboard, and admin link override.
- SQLite persistence for linked accounts, cached profile views, season state, match cursors, match summaries, and stat snapshots.
- Async PUBG provider with season cache, overview aggregation, mastery fetches, and lightweight recent-match summary parsing.
- Lightweight cache/throttle tuned for a private server with fewer than 10 members.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env` with Discord and PUBG credentials. Then run:

```powershell
python -m bot.main
```

The bot registers commands to `DISCORD_GUILD_ID` only.

## Environment

| Name | Required | Notes |
| --- | --- | --- |
| `DISCORD_TOKEN` | yes | Discord bot token |
| `DISCORD_GUILD_ID` | yes | Private server ID for slash command sync |
| `PUBG_API_KEY` | yes | PUBG developer API key |
| `DB_PATH` | no | Defaults to `bot.db` |
| `LOG_LEVEL` | no | Defaults to `INFO` |
| `ADMIN_DISCORD_ID` | no | Optional override admin for `/admin link ...` |

## Commands

- `/link pubg name platform`
- `/unlink`
- `/profile [user] [visibility]`
- `/lookup name [platform]`
- `/compare user_a user_b`
- `/leaderboard`
- `/admin link set user name platform`
- `/admin link delete user`

`/profile` now returns one interactive embed with `All`, `Recent`, and `Rank` buttons. `All` focuses on lifetime stats, `Recent` shows the 20-game window, and `Rank` isolates current ranked stats.
`/compare` now returns one private embed with `All`, `Recent`, and `Rank` buttons. Each metric renders as a horizontal 10-block bar plus the exact value.
`/leaderboard` now returns one public `7D` activity leaderboard ranked by hours played, with match count shown as supporting context.

## Deployment

Bot runs anywhere Python 3.11+ and a process supervisor (systemd, Docker, supervisord, pm2) are available. See [`docs/deployment-guide.md`](docs/deployment-guide.md) for generic steps and adapt it to the PUBG-only env set above.

## Manual Smoke Test

- [ ] `/link pubg` with a real PUBG account
- [ ] `/profile` self overview
- [ ] `/profile` another linked member overview
- [ ] `/profile` with `visibility:public`
- [ ] `/lookup` a public PUBG name
- [ ] `/compare` between two linked members
- [ ] `/leaderboard` with 3+ linked members and visible 7-day activity
- [ ] `/unlink` clears account and cached views
- [ ] `/admin link set` and `/admin link delete` enforce admin-only behavior
