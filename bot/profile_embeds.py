from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import discord

from bot.embeds import TIER_COLORS, tier_key

BLANK = "\u200b"
ProfilePage = Literal["all", "recent", "rank"]


def build_profile_embed(page: ProfilePage, account: Any, payload: dict[str, Any]) -> discord.Embed:
    ranked = payload.get("ranked") or {}
    lifetime = payload.get("lifetime") or {}
    metadata = payload.get("metadata") or {}
    recent = payload.get("recent") or {}
    mastery = payload.get("mastery") or {}
    survival = mastery.get("survival") or {}
    embed = discord.Embed(
        title=f"Game Thủ: {account.canonical_name}",
        description=_description(page, metadata, ranked, survival),
        color=TIER_COLORS.get(tier_key(ranked.get("tier")), 0x2563EB),
    )
    if page == "all":
        _add_cards(embed, _lifetime_cards(lifetime))
    elif page == "rank":
        _add_cards(embed, _rank_cards(ranked))
    else:
        _add_cards(embed, _recent_cards(recent))
    embed.set_footer(text=f"Freshness: {_timestamp_text(payload.get('generated_at'))} ICT")
    return embed


def make_profile_response(account: Any, payload: dict[str, Any]) -> list[discord.Embed]:
    return [build_profile_embed("all", account, payload)]
def _add_cards(embed: discord.Embed, cards: list[tuple[str, str]]) -> None:
    for label, value in cards:
        embed.add_field(name=label, value=value, inline=True)
    remainder = len(cards) % 3
    if remainder:
        for _ in range(3 - remainder):
            embed.add_field(name=BLANK, value=BLANK, inline=True)
def _overview_text(metadata: dict[str, Any], ranked: dict[str, Any], survival: dict[str, Any]) -> str:
    lines = [_rank_summary(ranked), _masterdata_text(metadata, ranked, survival)]
    return "\n".join(line for line in lines if line)


def _description(page: ProfilePage, metadata: dict[str, Any], ranked: dict[str, Any], survival: dict[str, Any]) -> str:
    if page == "all":
        return _masterdata_text(metadata, ranked, survival)
    if page == "recent":
        return "**Recent**  |  Avg. 20 Games"
    return _rank_summary(ranked)


def _masterdata_text(metadata: dict[str, Any], ranked: dict[str, Any], survival: dict[str, Any]) -> str:
    return "\n".join([
        f"Name: **{metadata.get('name') or 'n/a'}**",
        f"Survival Lv: **{_metric(survival.get('level'), 0)}**",
        f"Clan: **{metadata.get('clan_id') or 'n/a'}**",
        f"Primary Mode: **{ranked.get('mode') or 'n/a'}**",
    ])


def _rank_cards(payload: dict[str, Any]) -> list[tuple[str, str]]:
    matches = float(payload.get("matches") or 0)
    wins = float(payload.get("wins") or 0)
    return [
        ("Tier", _rank_label(payload)),
        ("Rank Points", f"{_metric(payload.get('points'), 0)} RP"),
        ("Matches", _metric(matches, 0)),
        ("Wins", _metric(wins, 0)),
        ("Win Rate", _percent(wins, matches)),
        ("K/D", _metric(payload.get("kd"))),
    ]


def _lifetime_cards(payload: dict[str, Any]) -> list[tuple[str, str]]:
    matches = float(payload.get("matches") or 0)
    wins = float(payload.get("wins") or 0)
    kills = float(payload.get("kills") or 0)
    damage = float(payload.get("damage") or 0)
    headshots = float(payload.get("headshots") or 0)
    top10s = float(payload.get("top10s") or 0)
    return [
        ("Matches", _metric(matches, 0)),
        ("Wins", _metric(wins, 0)),
        ("Win Rate", _percent(wins, matches)),
        ("Top 10 Rate", _percent(top10s, matches)),
        ("K/D", _metric(payload.get("kd"))),
        ("Avg Kills", _ratio(kills, matches)),
        ("Avg Damage", _ratio(damage, matches, digits=0)),
        ("Avg Assists", _ratio(float(payload.get("assists") or 0), matches)),
        ("Avg Revives", _ratio(float(payload.get("revives") or 0), matches)),
        ("Avg Survival", _minutes_text(payload.get("avg_survival_time"))),
        ("Headshots", _metric(headshots, 0)),
        ("HS Rate", _percent(headshots, kills)),
        ("Longest Kill", _distance_text(payload.get("longest_kill"))),
        ("Total Kills", _metric(kills, 0)),
        ("Total Damage", _metric(damage, 0)),
    ]


def _recent_cards(recent: dict[str, Any]) -> list[tuple[str, str]]:
    sample_size = float(recent.get("sample_size") or 0)
    wins = float(recent.get("wins") or 0)
    top10_rate = float(recent.get("top10_rate") or 0)
    avg_kills = float(recent.get("avg_kills") or 0)
    avg_damage = float(recent.get("avg_damage") or 0)
    avg_assists = _avg_from_matches(recent, "assists")
    avg_revives = _avg_from_matches(recent, "revives")
    return [
        ("Matches", _metric(sample_size, 0)),
        ("Wins", _metric(wins, 0)),
        ("Win Rate", _percent(wins, sample_size)),
        ("Top 10 Rate", f"{_metric(top10_rate)}%"),
        ("K/D", "n/a"),
        ("Avg Kills", _metric(avg_kills)),
        ("Avg Damage", _metric(avg_damage, 0)),
        ("Avg Assists", _metric(avg_assists)),
        ("Avg Revives", _metric(avg_revives)),
        ("Avg Survival", _minutes_text(recent.get("avg_survival_time_seconds"))),
        ("Avg Place", _metric(recent.get("avg_placement"))),
    ]


def _avg_from_matches(recent: dict[str, Any], key: str) -> float:
    matches = recent.get("matches") or []
    if not matches:
        return 0.0
    return round(sum(float(match.get(key) or 0) for match in matches) / len(matches), 2)


def _rank_summary(payload: dict[str, Any]) -> str:
    return (
        f"**{_rank_label(payload)}**"
        f"  |  **{_metric(payload.get('points'), 0)} RP**"
        f"  |  **{_label(payload.get('mode'))}**"
    )


def _rank_label(payload: dict[str, Any]) -> str:
    tier = payload.get("tier") or "Unranked"
    division = payload.get("division")
    return f"{tier}{f' {division}' if division else ''}"
def _ratio(numerator: float, denominator: float, *, digits: int = 2) -> str:
    if denominator <= 0:
        return "n/a"
    return f"{numerator / denominator:.{digits}f}"


def _percent(numerator: float, denominator: float) -> str:
    if denominator <= 0:
        return "n/a"
    return f"{(numerator / denominator) * 100:.1f}%"


def _minutes_text(value: Any) -> str:
    seconds = float(value or 0)
    if seconds <= 0:
        return "n/a"
    return f"{seconds / 60:.1f} min"


def _distance_text(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1f} m"


def _label(value: Any) -> str:
    if not value:
        return "n/a"
    return str(value)


def _metric(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(int(value)) if digits == 0 and isinstance(value, (int, float)) else str(value)


def _timestamp_text(value: Any) -> str:
    if not value:
        return "unknown"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        ict = timezone(timedelta(hours=7))
        return dt.astimezone(ict).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)
