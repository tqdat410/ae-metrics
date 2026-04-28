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

Deployment templates live in `deploy/` for Oracle Cloud Free ARM + Ubuntu + systemd.

1. Provision an Ubuntu 22.04 ARM instance.
2. Copy this repository to `/opt/discord-bot`.
3. Create `/opt/discord-bot/.env`.
4. Run `sudo deploy/install.sh`.
5. Start with `sudo systemctl start discord-bot`.

Riot development keys expire every 24 hours. Preferred renewal: edit `RIOT_API_KEY` in `.env` on the VM, then run `/admin reload-key` in Discord to reload it without restarting. Fallback: restart the service.

## Manual Smoke Test

- [ ] `/link lol` with a real account
- [ ] `/rank` self
- [ ] `/rank` another linked member
- [ ] `/lookup` a public Riot ID
- [ ] `/leaderboard` with 3+ linked members
- [ ] `/unlink` clears account and cache
