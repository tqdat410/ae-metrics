# AE Metrics

Private Discord bot for game rank lookups across League of Legends, Valorant, and PUBG.

## Features

- Slash commands for linking accounts, rank lookup, arbitrary lookup, leaderboard, and Riot dev-key reload.
- SQLite persistence for linked accounts, rank cache, and API state.
- Async HTTP providers for Riot, HenrikDev Valorant, and PUBG APIs.
- Lightweight cache/throttle designed for a private server with fewer than 10 members.

## Setup

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env` with Discord and game API credentials. Then run:

```powershell
python -m bot.main
```

The bot registers commands to `DISCORD_GUILD_ID` only.

## Environment

| Name | Required | Notes |
| --- | --- | --- |
| `DISCORD_TOKEN` | yes | Discord bot token |
| `DISCORD_GUILD_ID` | yes | Private server ID for slash command sync |
| `RIOT_API_KEY` | yes | 24-hour Riot development key |
| `HENRIK_API_KEY` | yes | HenrikDev Valorant API key |
| `PUBG_API_KEY` | yes | PUBG developer API key |
| `DB_PATH` | no | Defaults to `bot.db` |
| `LOG_LEVEL` | no | Defaults to `INFO` |
| `ADMIN_DISCORD_ID` | no | Enables `/admin reload-key` |

## Commands

- `/link lol riot_id region`
- `/link valo riot_id region`
- `/link pubg name platform`
- `/unlink game`
- `/rank game user`
- `/lookup game player region`
- `/leaderboard game`
- `/admin reload-key`

## Deployment

Bot runs anywhere Python 3.11+ and a process supervisor (systemd, Docker, supervisord, pm2) are available. See [`docs/deployment-guide.md`](docs/deployment-guide.md) for generic steps and a systemd unit template.

Riot development keys expire every 24 hours. Preferred renewal: edit `RIOT_API_KEY` in `.env`, then run `/admin reload-key` in Discord. Fallback: restart the service.

## Manual Smoke Test

- [ ] `/link lol` with a real account
- [ ] `/rank` self
- [ ] `/rank` another linked member
- [ ] `/lookup` a public Riot ID
- [ ] `/leaderboard` with 3+ linked members
- [ ] `/unlink` clears account and cache
