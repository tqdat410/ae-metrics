from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite

_conn: aiosqlite.Connection | None = None


async def init(path: str) -> None:
    global _conn
    _conn = await aiosqlite.connect(path)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")
    migrations = Path(__file__).with_name("migrations.sql").read_text(encoding="utf-8")
    await _conn.executescript(migrations)
    await _conn.commit()


async def close() -> None:
    global _conn
    if _conn:
        await _conn.close()
        _conn = None


def _db() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialized")
    return _conn


def _row(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


async def get_link(discord_id: int, game: str) -> dict[str, Any] | None:
    cur = await _db().execute("SELECT * FROM linked_accounts WHERE discord_id=? AND game=?", (discord_id, game))
    return _row(await cur.fetchone())


async def upsert_link(
    discord_id: int,
    game: str,
    region: str,
    game_name: str,
    tag_line: str | None = None,
    puuid: str | None = None,
    summoner_id: str | None = None,
    account_id: str | None = None,
) -> None:
    await _db().execute(
        """
        INSERT OR REPLACE INTO linked_accounts
        (discord_id, game, region, game_name, tag_line, puuid, summoner_id, account_id, linked_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (discord_id, game, region, game_name, tag_line, puuid, summoner_id, account_id, int(time.time())),
    )
    await _db().commit()


async def delete_link(discord_id: int, game: str) -> bool:
    cur = await _db().execute("DELETE FROM linked_accounts WHERE discord_id=? AND game=?", (discord_id, game))
    await _db().execute("DELETE FROM rank_cache WHERE discord_id=? AND game=?", (discord_id, game))
    await _db().commit()
    return cur.rowcount > 0


async def list_links_by_game(game: str) -> list[dict[str, Any]]:
    cur = await _db().execute("SELECT * FROM linked_accounts WHERE game=? ORDER BY linked_at", (game,))
    return [dict(row) for row in await cur.fetchall()]


async def get_cache(discord_id: int, game: str) -> tuple[dict[str, Any], int] | None:
    cur = await _db().execute("SELECT payload_json, updated_at FROM rank_cache WHERE discord_id=? AND game=?", (discord_id, game))
    row = await cur.fetchone()
    if not row:
        return None
    return json.loads(row["payload_json"]), int(time.time()) - row["updated_at"]


async def set_cache(discord_id: int, game: str, payload: dict[str, Any]) -> None:
    await _db().execute(
        "INSERT OR REPLACE INTO rank_cache(discord_id, game, payload_json, updated_at) VALUES (?, ?, ?, ?)",
        (discord_id, game, json.dumps(payload), int(time.time())),
    )
    await _db().commit()


async def delete_cache(discord_id: int, game: str) -> None:
    await _db().execute("DELETE FROM rank_cache WHERE discord_id=? AND game=?", (discord_id, game))
    await _db().commit()


async def get_state(key: str) -> str | None:
    cur = await _db().execute("SELECT value FROM api_state WHERE key=?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else None


async def set_state(key: str, value: str) -> None:
    await _db().execute(
        "INSERT OR REPLACE INTO api_state(key, value, updated_at) VALUES (?, ?, ?)",
        (key, value, int(time.time())),
    )
    await _db().commit()
