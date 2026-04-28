# Code Standards

Last updated: 2026-04-28

## Project Principles

- Keep implementation simple for a private server under 10 members.
- Prefer explicit modules over broad abstractions.
- Keep code files under 200 LOC where practical.
- Use async APIs for Discord handlers, HTTP calls, and SQLite operations.
- Do not commit secrets, real `.env`, tokens, API keys, databases, logs, or virtualenvs.

## Python Style

| Area | Standard |
| --- | --- |
| Version | Python 3.11+ target |
| Type hints | Use annotations on public helpers and command handlers |
| Imports | Standard library, third-party, local imports grouped in that order |
| Naming | Python modules use existing snake_case convention |
| Errors | Raise provider-specific exceptions for upstream/API failures |
| Comments | Add only when code intent is not obvious |

## Module Boundaries

| Concern | Location |
| --- | --- |
| Bot lifecycle | `bot/main.py` |
| Settings | `bot/config.py` |
| Persistence | `bot/db.py`, `bot/migrations.sql` |
| Discord commands | `bot/cogs/*.py` |
| API providers | `bot/providers/*.py` |
| Shared provider contracts | `bot/providers/__init__.py` |
| Embed rendering and ranking weight | `bot/embeds.py` |
| Input validation | `bot/validators.py` |
| Cache and throttling | `bot/cache.py`, `bot/rate_limiter.py` |
| Deployment | `deploy/*` |
| Tests | `tests/*.py` |

## Configuration Standards

Documented env vars in `.env.example`:

| Name | Required | Notes |
| --- | --- | --- |
| `DISCORD_TOKEN` | Yes | Discord bot token |
| `DISCORD_GUILD_ID` | Yes | Guild-scoped slash command sync |
| `RIOT_API_KEY` | Yes | Riot dev key |
| `HENRIK_API_KEY` | Yes | HenrikDev API key |
| `PUBG_API_KEY` | Yes | PUBG API key |
| `DB_PATH` | No | Defaults to `bot.db` |
| `LOG_LEVEL` | No | Defaults to INFO |
| `ADMIN_DISCORD_ID` | No | Enables admin-only key reload and DM warnings |

The settings layer checks required API secrets before bot startup.

## Provider Standards

- Return the shared account dataclass from account lookup.
- Return the shared rank dataclass from rank fetch.
- Use shared `http_client.get_client()` unless tests inject a client.
- Use the shared HTTP response handler for error mapping.
- Keep credentials read from settings, not hard-coded.
- URL-encode user-controlled path segments.

## Discord Command Standards

- Defer interactions before provider or DB work.
- Use ephemeral responses for account linking, rank lookup, lookup failures, and admin actions.
- Use public response for leaderboard.
- Convert provider exceptions into user-safe messages.
- Keep command files focused by feature group.

## Test Standards

- Use `pytest` with `pytest-asyncio` auto mode from `pytest.ini`.
- Test validators, DB helpers, cache behavior, rank sorting, provider error mapping, and critical provider parsing.
- Prefer mocked HTTP for provider tests.
- Current status: 22/22 tests passed, 31% coverage per task context.
- Next priority: raise provider and cog coverage before adding commands.
