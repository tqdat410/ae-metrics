from __future__ import annotations

from typing import Any

import discord

TIER_COLORS = {
    "IRON": 0x6B7280,
    "BRONZE": 0xA16207,
    "SILVER": 0x94A3B8,
    "GOLD": 0xF59E0B,
    "PLATINUM": 0x14B8A6,
    "EMERALD": 0x10B981,
    "DIAMOND": 0x60A5FA,
    "MASTER": 0xA855F7,
    "GRANDMASTER": 0xEF4444,
    "CHALLENGER": 0xFACC15,
    "IMMORTAL": 0xDC2626,
    "RADIANT": 0xFDE68A,
    "UNRANKED": 0x64748B,
}

TIER_ORDER = {
    "UNRANKED": 0,
    "IRON": 1000,
    "BRONZE": 2000,
    "SILVER": 3000,
    "GOLD": 4000,
    "PLATINUM": 5000,
    "EMERALD": 6000,
    "DIAMOND": 7000,
    "MASTER": 8000,
    "IMMORTAL": 8500,
    "GRANDMASTER": 9000,
    "RADIANT": 9500,
    "CHALLENGER": 10000,
}

DIVISION_WEIGHT = {"IV": 1, "III": 2, "II": 3, "I": 4, "4": 1, "3": 2, "2": 3, "1": 4}


def _read(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def rank_to_dict(rank: Any) -> dict[str, Any]:
    if hasattr(rank, "to_dict"):
        return rank.to_dict()
    if hasattr(rank, "__dict__"):
        return dict(rank.__dict__)
    return dict(rank)


def tier_key(tier: str | None) -> str:
    text = (tier or "UNRANKED").upper()
    return next((key for key in TIER_ORDER if key in text), text)


def tier_weight(tier: str | None, division: str | None = None, points: int | None = None) -> int:
    base = TIER_ORDER.get(tier_key(tier), 0)
    div = DIVISION_WEIGHT.get(str(division or "").upper(), 0)
    return base + div * 100 + max(points or 0, 0)


def make_rank_embed(game: str, account: Any, rank: Any) -> discord.Embed:
    tier = _read(rank, "tier") or "Unranked"
    division = _read(rank, "division")
    points = _read(rank, "points")
    wins = _read(rank, "wins")
    losses = _read(rank, "losses")
    name = _read(account, "canonical_name") or _read(account, "game_name") or "Unknown"
    tag = _read(account, "tag_line")
    region = _read(account, "region", "unknown")
    display = f"{name}#{tag}" if tag else name

    title = f"{game.upper()} rank: {display}"
    description = f"**{tier}{f' {division}' if division else ''}**"
    if points is not None:
        description += f" - {points} pts"

    embed = discord.Embed(
        title=title,
        description=description,
        color=TIER_COLORS.get(tier_key(tier), TIER_COLORS["UNRANKED"]),
    )
    embed.add_field(name="Region", value=str(region), inline=True)
    if wins is not None or losses is not None:
        embed.add_field(name="Record", value=f"{wins or 0}W / {losses or 0}L", inline=True)
    return embed


def make_message_embed(title: str, message: str, *, color: int = 0x2563EB) -> discord.Embed:
    return discord.Embed(title=title, description=message, color=color)
