# Development Roadmap

Last updated: 2026-04-28

## Current Status

The Discord Game Stats Bot implementation is functionally complete for the planned private-server MVP. Static compile and unit tests passed per task context, but real Discord/API smoke testing remains open.

## Milestones

| Milestone | Status | Notes |
| --- | --- | --- |
| Setup and config | Done | `.env.example`, Pydantic settings, logging, dependency list |
| SQLite persistence | Done | Links, rank cache, API state, WAL mode |
| Game providers | Done | LoL, Valorant, PUBG providers implemented |
| Discord commands | Done | Link, unlink, rank, lookup, leaderboard, admin reload |
| Cache and throttle | Done | TTL cache plus lightweight sequential throttle |
| Deployment templates | Done | systemd, install, update, logrotate |
| Automated tests | Partial | 22/22 passing, coverage 31% |
| Real smoke validation | Not started | Requires Discord bot token and real game API keys |

## Next Priorities

| Priority | Work | Why |
| --- | --- | --- |
| P1 | Run README manual smoke checklist | Confirms Discord command sync and real API behavior |
| P1 | Verify Oracle/systemd deployment on Ubuntu 22.04 ARM | Confirms service, logs, restart behavior |
| P2 | Add provider happy-path tests for LoL and PUBG | Raises confidence in API payload parsing |
| P2 | Add cog-level tests with mocked Discord interactions where practical | Reduces command regression risk |
| P3 | Document live key renewal runbook after first production use | Captures operational reality |

## Manual Smoke Checklist

- [ ] `/link lol` with a real Riot account.
- [ ] `/link valo` with a real Valorant account.
- [ ] `/link pubg` with a real PUBG account.
- [ ] `/rank` self.
- [ ] `/rank` another linked member.
- [ ] `/lookup` public player.
- [ ] `/leaderboard` with 3+ linked members.
- [ ] `/unlink` clears account and cache.
- [ ] `/admin reload-key` reloads Riot key after `.env` update.

## Completion Criteria

MVP is production-ready for the private server when:

- Real smoke checklist passes.
- Bot runs under systemd after reboot.
- Logs are visible under `/var/log/discord-bot/bot.log`.
- Riot key reload process is confirmed by a live LoL lookup.
- Known coverage gap is accepted or improved.

