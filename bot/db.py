from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA_VERSION = 3
_conn: aiosqlite.Connection | None = None
_db_path: Path | None = None


async def init(path: str) -> None:
    global _conn, _db_path
    _db_path = Path(path)
    _conn = await aiosqlite.connect(path)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")
    await _ensure_schema()


async def close() -> None:
    global _conn, _db_path
    if _conn:
        await _conn.close()
        _conn = None
    _db_path = None


async def commit() -> None:
    await _db().commit()


def _db() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialized")
    return _conn


def _row(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


async def _table_exists(name: str) -> bool:
    cur = await _db().execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return await cur.fetchone() is not None


async def _table_columns(name: str) -> set[str]:
    if not await _table_exists(name):
        return set()
    cur = await _db().execute(f"PRAGMA table_info({name})")
    return {row["name"] for row in await cur.fetchall()}


async def _schema_version() -> int:
    if not await _table_exists("schema_migrations"):
        return 0
    cur = await _db().execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations")
    row = await cur.fetchone()
    return int(row["version"]) if row else 0


async def _mark_schema_version(version: int) -> None:
    await _db().execute(
        "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (version, int(time.time())),
    )


def _backup_path() -> Path:
    if _db_path is None:
        raise RuntimeError("Database path unavailable")
    return _db_path.with_suffix(_db_path.suffix + ".pre-pubg-pivot.bak")


async def _maybe_backup_db() -> None:
    if _db_path is None or not _db_path.exists():
        return
    backup_path = _backup_path()
    if backup_path.exists():
        return

    await _db().execute("PRAGMA wal_checkpoint(FULL)")
    target = await aiosqlite.connect(str(backup_path))
    try:
        await _db().backup(target)
        await target.commit()
    finally:
        await target.close()


async def _ensure_schema() -> None:
    legacy_columns = await _table_columns("linked_accounts")
    if "game" in legacy_columns:
        await _maybe_backup_db()
        await _migrate_legacy_schema()
        return

    migrations = Path(__file__).with_name("migrations.sql").read_text(encoding="utf-8")
    await _db().executescript(migrations)
    await _apply_schema_v2()
    await _apply_schema_v3()
    if await _schema_version() < SCHEMA_VERSION:
        await _mark_schema_version(SCHEMA_VERSION)
    await _db().commit()


async def _migrate_legacy_schema() -> None:
    migrations = Path(__file__).with_name("migrations.sql").read_text(encoding="utf-8")
    await _db().execute("BEGIN")
    legacy_pubg_rows = await list_legacy_pubg_links()
    missing_ids = [row["discord_id"] for row in legacy_pubg_rows if not row.get("account_id")]
    if missing_ids:
        await _db().execute("ROLLBACK")
        raise RuntimeError(f"Legacy PUBG links missing account_id for discord ids: {missing_ids}")

    if await _table_exists("linked_accounts"):
        await _db().execute("ALTER TABLE linked_accounts RENAME TO linked_accounts_legacy")
    if await _table_exists("rank_cache"):
        await _db().execute("ALTER TABLE rank_cache RENAME TO rank_cache_legacy")

    await _db().executescript(migrations)
    await _db().execute(
        """
        INSERT INTO linked_accounts (
            discord_user_id, pubg_account_id, platform, canonical_name, linked_at, last_resolved_at, linked_by_admin_id
        )
        SELECT
            discord_id,
            account_id,
            region,
            game_name,
            linked_at,
            linked_at,
            NULL
        FROM linked_accounts_legacy
        WHERE game='pubg' AND account_id IS NOT NULL
        """
    )
    await _db().execute(
        """
        INSERT INTO rank_cache (pubg_account_id, platform, view, payload_json, updated_at)
        SELECT
            legacy_links.account_id,
            legacy_links.region,
            'ranked',
            legacy_cache.payload_json,
            legacy_cache.updated_at
        FROM rank_cache_legacy AS legacy_cache
        JOIN linked_accounts_legacy AS legacy_links
            ON legacy_links.discord_id = legacy_cache.discord_id
           AND legacy_links.game = legacy_cache.game
        WHERE legacy_cache.game='pubg' AND legacy_links.account_id IS NOT NULL
        """
    )
    await _apply_schema_v2()
    await _apply_schema_v3()
    await _mark_schema_version(SCHEMA_VERSION)
    await _db().commit()


async def _apply_schema_v2() -> None:
    columns = await _table_columns("match_summaries")
    if "played_at_unix" not in columns:
        await _db().execute("ALTER TABLE match_summaries ADD COLUMN played_at_unix INTEGER")

    await _db().execute(
        """
        UPDATE match_summaries
        SET played_at_unix = CAST(strftime('%s', REPLACE(played_at, 'Z', '+00:00')) AS INTEGER)
        WHERE played_at_unix IS NULL AND played_at IS NOT NULL AND played_at != ''
        """
    )
    await _db().execute("CREATE INDEX IF NOT EXISTS idx_match_summaries_played_unix ON match_summaries(played_at_unix)")


async def _apply_schema_v3() -> None:
    columns = await _table_columns("match_summaries")
    if not columns:
        return

    cur = await _db().execute("PRAGMA table_info(match_summaries)")
    pk_columns = [row["name"] for row in await cur.fetchall() if row["pk"]]
    if pk_columns == ["match_id", "pubg_account_id", "platform"]:
        return

    await _db().execute(
        """
        CREATE TABLE IF NOT EXISTS match_summaries_v3 (
            match_id TEXT NOT NULL,
            pubg_account_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            game_mode TEXT NOT NULL,
            played_at TEXT NOT NULL,
            map_name TEXT,
            placement INTEGER,
            kills INTEGER,
            damage REAL,
            assists INTEGER,
            revives INTEGER,
            survival_time_seconds REAL,
            payload_json TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            played_at_unix INTEGER,
            PRIMARY KEY(match_id, pubg_account_id, platform)
        )
        """
    )
    await _db().execute(
        """
        INSERT OR IGNORE INTO match_summaries_v3 (
            match_id, pubg_account_id, platform, game_mode, played_at, map_name, placement, kills,
            damage, assists, revives, survival_time_seconds, payload_json, updated_at, played_at_unix
        )
        SELECT
            match_id, pubg_account_id, platform, game_mode, played_at, map_name, placement, kills,
            damage, assists, revives, survival_time_seconds, payload_json, updated_at, played_at_unix
        FROM match_summaries
        """
    )
    await _db().execute("DROP TABLE match_summaries")
    await _db().execute("ALTER TABLE match_summaries_v3 RENAME TO match_summaries")
    await _db().execute("CREATE INDEX IF NOT EXISTS idx_match_summaries_account_played ON match_summaries(pubg_account_id, platform, played_at DESC)")
    await _db().execute("CREATE INDEX IF NOT EXISTS idx_match_summaries_played ON match_summaries(played_at)")
    await _db().execute("CREATE INDEX IF NOT EXISTS idx_match_summaries_played_unix ON match_summaries(played_at_unix)")


def _parse_played_at_unix(played_at: str | None) -> int | None:
    if not played_at:
        return None
    try:
        return int(datetime.fromisoformat(played_at.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


async def list_legacy_pubg_links() -> list[dict[str, Any]]:
    if "game" not in await _table_columns("linked_accounts"):
        return []
    cur = await _db().execute("SELECT * FROM linked_accounts WHERE game='pubg' ORDER BY linked_at")
    return [dict(row) for row in await cur.fetchall()]


async def get_pubg_link(discord_user_id: int) -> dict[str, Any] | None:
    cur = await _db().execute("SELECT * FROM linked_accounts WHERE discord_user_id=?", (discord_user_id,))
    return _row(await cur.fetchone())


async def upsert_pubg_link(
    discord_user_id: int,
    pubg_account_id: str,
    platform: str,
    canonical_name: str,
    *,
    linked_by_admin_id: int | None = None,
) -> None:
    now = int(time.time())
    await _db().execute(
        """
        INSERT INTO linked_accounts (
            discord_user_id, pubg_account_id, platform, canonical_name, linked_at, last_resolved_at, linked_by_admin_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(discord_user_id) DO UPDATE SET
            pubg_account_id=excluded.pubg_account_id,
            platform=excluded.platform,
            canonical_name=excluded.canonical_name,
            last_resolved_at=excluded.last_resolved_at,
            linked_by_admin_id=excluded.linked_by_admin_id
        """,
        (discord_user_id, pubg_account_id, platform, canonical_name, now, now, linked_by_admin_id),
    )
    await _db().commit()


async def _purge_account_rows(pubg_account_id: str, platform: str) -> None:
    for table in ("rank_cache", "match_summaries", "match_cursors", "stat_snapshots"):
        await _db().execute(f"DELETE FROM {table} WHERE pubg_account_id=? AND platform=?", (pubg_account_id, platform))


async def purge_account(pubg_account_id: str, platform: str) -> None:
    await _purge_account_rows(pubg_account_id, platform)
    await _db().commit()


async def delete_pubg_link(discord_user_id: int) -> bool:
    link = await get_pubg_link(discord_user_id)
    if not link:
        return False
    await _db().execute("DELETE FROM linked_accounts WHERE discord_user_id=?", (discord_user_id,))
    await _purge_account_rows(link["pubg_account_id"], link["platform"])
    await _db().commit()
    return True


async def list_pubg_links() -> list[dict[str, Any]]:
    cur = await _db().execute("SELECT * FROM linked_accounts ORDER BY linked_at")
    return [dict(row) for row in await cur.fetchall()]


async def get_cache(pubg_account_id: str, platform: str, view: str) -> tuple[Any, int] | None:
    cur = await _db().execute(
        "SELECT payload_json, updated_at FROM rank_cache WHERE pubg_account_id=? AND platform=? AND view=?",
        (pubg_account_id, platform, view),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return json.loads(row["payload_json"]), int(time.time()) - row["updated_at"]


async def set_cache(pubg_account_id: str, platform: str, view: str, payload: Any) -> None:
    await _db().execute(
        """
        INSERT OR REPLACE INTO rank_cache(pubg_account_id, platform, view, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (pubg_account_id, platform, view, json.dumps(payload), int(time.time())),
    )
    await _db().commit()


async def delete_cache(pubg_account_id: str, platform: str, view: str | None = None) -> None:
    if view is None:
        await _db().execute("DELETE FROM rank_cache WHERE pubg_account_id=? AND platform=?", (pubg_account_id, platform))
    else:
        await _db().execute(
            "DELETE FROM rank_cache WHERE pubg_account_id=? AND platform=? AND view=?",
            (pubg_account_id, platform, view),
        )
    await _db().commit()


async def get_state(key: str) -> str | None:
    cur = await _db().execute("SELECT value FROM api_state WHERE key=?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else None


async def set_state(key: str, value: str, *, commit: bool = True) -> None:
    await _db().execute(
        "INSERT OR REPLACE INTO api_state(key, value, updated_at) VALUES (?, ?, ?)",
        (key, value, int(time.time())),
    )
    if commit:
        await _db().commit()


async def get_match_cursor(pubg_account_id: str, platform: str) -> dict[str, Any] | None:
    cur = await _db().execute(
        "SELECT cursor_json FROM match_cursors WHERE pubg_account_id=? AND platform=?",
        (pubg_account_id, platform),
    )
    row = await cur.fetchone()
    return json.loads(row["cursor_json"]) if row else None


async def set_match_cursor(pubg_account_id: str, platform: str, cursor: dict[str, Any], *, commit: bool = True) -> None:
    await _db().execute(
        """
        INSERT OR REPLACE INTO match_cursors(pubg_account_id, platform, cursor_json, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (pubg_account_id, platform, json.dumps(cursor), int(time.time())),
    )
    if commit:
        await _db().commit()


async def set_match_cursors(cursors: list[tuple[str, str, dict[str, Any]]], *, commit: bool = True) -> None:
    now = int(time.time())
    await _db().executemany(
        """
        INSERT OR REPLACE INTO match_cursors(pubg_account_id, platform, cursor_json, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        [(account_id, platform, json.dumps(cursor), now) for account_id, platform, cursor in cursors],
    )
    if commit:
        await _db().commit()


async def match_summary_exists(match_id: str, pubg_account_id: str, platform: str) -> bool:
    cur = await _db().execute(
        "SELECT 1 FROM match_summaries WHERE match_id=? AND pubg_account_id=? AND platform=?",
        (match_id, pubg_account_id, platform),
    )
    return await cur.fetchone() is not None


async def _insert_match_summary_if_absent(summary: dict[str, Any]) -> None:
    await _db().execute(
        """
        INSERT OR IGNORE INTO match_summaries (
            match_id, pubg_account_id, platform, game_mode, played_at, played_at_unix, map_name, placement, kills,
            damage, assists, revives, survival_time_seconds, payload_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            summary["match_id"],
            summary["pubg_account_id"],
            summary["platform"],
            summary["game_mode"],
            summary["played_at"],
            _parse_played_at_unix(summary.get("played_at")),
            summary.get("map_name"),
            summary.get("placement"),
            summary.get("kills"),
            summary.get("damage"),
            summary.get("assists"),
            summary.get("revives"),
            summary.get("survival_time_seconds"),
            json.dumps(summary),
            int(time.time()),
        ),
    )


async def insert_match_summary_if_absent(summary: dict[str, Any]) -> None:
    await _insert_match_summary_if_absent(summary)
    await _db().commit()


async def insert_match_summaries_if_absent(summaries: list[dict[str, Any]], *, commit: bool = True) -> None:
    for summary in summaries:
        await _insert_match_summary_if_absent(summary)
    if commit:
        await _db().commit()


async def upsert_match_summary(summary: dict[str, Any]) -> None:
    await insert_match_summary_if_absent(summary)


async def list_recent_match_summaries(pubg_account_id: str, platform: str, limit: int = 5) -> list[dict[str, Any]]:
    cur = await _db().execute(
        """
        SELECT payload_json
        FROM match_summaries
        WHERE pubg_account_id=? AND platform=?
        ORDER BY COALESCE(played_at_unix, 0) DESC, played_at DESC
        LIMIT ?
        """,
        (pubg_account_id, platform, limit),
    )
    rows = await cur.fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


async def list_match_activity_since(played_at_cutoff: str) -> list[dict[str, Any]]:
    cur = await _db().execute(
        """
        SELECT
            pubg_account_id,
            platform,
            COUNT(*) AS match_count,
            COALESCE(SUM(survival_time_seconds), 0) AS total_survival_seconds
        FROM match_summaries
        WHERE played_at >= ?
        GROUP BY pubg_account_id, platform
        """,
        (played_at_cutoff,),
    )
    return [dict(row) for row in await cur.fetchall()]


async def list_match_activity_since_unix(cutoff_unix: int) -> list[dict[str, Any]]:
    cur = await _db().execute(
        """
        SELECT
            pubg_account_id,
            platform,
            COUNT(*) AS match_count,
            COALESCE(SUM(survival_time_seconds), 0) AS total_survival_seconds
        FROM match_summaries
        WHERE played_at_unix IS NOT NULL AND played_at_unix >= ?
        GROUP BY pubg_account_id, platform
        """,
        (cutoff_unix,),
    )
    return [dict(row) for row in await cur.fetchall()]


async def upsert_stat_snapshot(
    pubg_account_id: str,
    platform: str,
    snapshot_type: str,
    snapshot_date: str,
    payload: dict[str, Any],
) -> None:
    await _db().execute(
        """
        INSERT OR REPLACE INTO stat_snapshots(
            pubg_account_id, platform, snapshot_type, snapshot_date, payload_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (pubg_account_id, platform, snapshot_type, snapshot_date, json.dumps(payload), int(time.time())),
    )
    await _db().commit()
