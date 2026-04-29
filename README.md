# AE Metrics

Private Discord bot for PUBG account linking, profile lookup, leaderboard views, and lightweight match analytics in a small private server.

## Features

- PUBG-only slash commands for linking, unlinking, direct lookup, profile views, compare, leaderboard, admin link override, and recent matches.
- SQLite persistence for linked accounts, cached profile views, season state, match cursors, match summaries, and stat snapshots.
- Async PUBG provider with season cache, ranked/lifetime views, and lightweight recent-match summary parsing.
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
- `/profile [user] [view]`
- `/lookup name [platform] [view]`
- `/compare user_a user_b [view]`
- `/leaderboard [metric]`
- `/matches [user] [count]`
- `/admin link set user name platform`
- `/admin link delete user`

## Deployment

Bot runs anywhere Python 3.11+ and a process supervisor (systemd, Docker, supervisord, pm2) are available. See [`docs/deployment-guide.md`](docs/deployment-guide.md) for generic steps and adapt it to the PUBG-only env set above.

## Manual Smoke Test

- [ ] `/link pubg` with a real PUBG account
- [ ] `/profile` self with `ranked`
- [ ] `/profile` another linked member with `lifetime`
- [ ] `/lookup` a public PUBG name
- [ ] `/compare` between two linked members
- [ ] `/leaderboard` with 3+ linked members
- [ ] `/matches` returns recent summaries
- [ ] `/unlink` clears account and cached views
- [ ] `/admin link set` and `/admin link delete` enforce admin-only behavior
