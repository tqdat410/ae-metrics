from __future__ import annotations

from typing import Any

import discord

TIER_COLORS = {
    "UNRANKED": 0x64748B,
    "BRONZE": 0xA16207,
    "SILVER": 0x94A3B8,
    "GOLD": 0xF59E0B,
    "PLATINUM": 0x14B8A6,
    "DIAMOND": 0x60A5FA,
    "MASTER": 0xA855F7,
}

TIER_ORDER = {
    "UNRANKED": 0,
    "BRONZE": 2000,
    "SILVER": 3000,
    "GOLD": 4000,
    "PLATINUM": 5000,
    "DIAMOND": 7000,
    "MASTER": 8000,
}

DIVISION_WEIGHT = {"5": 1, "4": 1, "III": 2, "3": 2, "II": 3, "2": 3, "I": 4, "1": 4}


def tier_key(tier: str | None) -> str:
    text = (tier or "UNRANKED").upper()
    return next((key for key in TIER_ORDER if key in text), text)


def tier_weight(tier: str | None, division: str | None = None, points: int | None = None) -> int:
    base = TIER_ORDER.get(tier_key(tier), 0)
    div = DIVISION_WEIGHT.get(str(division or "").upper(), 0)
    return base + div * 100 + max(points or 0, 0)


def make_message_embed(title: str, message: str, *, color: int = 0x2563EB) -> discord.Embed:
    return discord.Embed(title=title, description=message, color=color)


def make_profile_embed(account: Any, view: str, payload: dict[str, Any]) -> discord.Embed:
    name = getattr(account, "canonical_name", None) or payload.get("canonical_name") or "Unknown"
    platform = getattr(account, "region", None) or payload.get("platform") or "unknown"

    if view == "ranked":
        tier = payload.get("tier") or "Unranked"
        division = payload.get("division")
        title = f"PUBG ranked: {name}"
        description = f"**{tier}{f' {division}' if division else ''}**"
        if payload.get("points") is not None:
            description += f" - {payload['points']} pts"
        embed = discord.Embed(
            title=title,
            description=description,
            color=TIER_COLORS.get(tier_key(tier), TIER_COLORS["UNRANKED"]),
        )
        embed.add_field(name="Mode", value=str(payload.get("mode") or "n/a"), inline=True)
        embed.add_field(name="Matches", value=str(payload.get("matches") or 0), inline=True)
        embed.add_field(name="Wins", value=str(payload.get("wins") or 0), inline=True)
        embed.add_field(name="K/D", value=_metric_text(payload.get("kd")), inline=True)
        embed.add_field(name="Damage", value=_metric_text(payload.get("damage"), digits=0), inline=True)
        embed.add_field(name="Platform", value=str(platform), inline=True)
        return embed

    embed = discord.Embed(title=f"PUBG lifetime: {name}", color=0x2563EB)
    embed.description = f"Primary mode: **{payload.get('mode') or 'n/a'}**"
    embed.add_field(name="Matches", value=str(payload.get("matches") or 0), inline=True)
    embed.add_field(name="Wins", value=str(payload.get("wins") or 0), inline=True)
    embed.add_field(name="Top 10", value=str(payload.get("top10s") or 0), inline=True)
    embed.add_field(name="K/D", value=_metric_text(payload.get("kd")), inline=True)
    embed.add_field(name="Damage", value=_metric_text(payload.get("damage"), digits=0), inline=True)
    embed.add_field(name="Headshots", value=str(payload.get("headshots") or 0), inline=True)
    embed.add_field(name="Assists", value=str(payload.get("assists") or 0), inline=True)
    embed.add_field(name="Revives", value=str(payload.get("revives") or 0), inline=True)
    embed.add_field(name="Platform", value=str(platform), inline=True)
    return embed


def make_compare_embed(view: str, left_member: str, right_member: str, left: dict[str, Any], right: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(title=f"PUBG compare: {left_member} vs {right_member}", color=0x2563EB)
    fields = _compare_fields(view, left, right)
    for label, left_value, right_value in fields:
        embed.add_field(name=label, value=f"{left_value}\nvs\n{right_value}", inline=True)
    return embed


def make_leaderboard_embed(rows: list[str]) -> discord.Embed:
    embed = discord.Embed(title="PUBG leaderboard: Activity 7D", color=0x2563EB)
    embed.description = "**7D** | Hours played ranking\n\n"
    embed.description += "\n".join(rows) if rows else "No 7D activity data available right now."
    return embed


def make_matches_embed(name: str, matches: list[dict[str, Any]]) -> discord.Embed:
    embed = discord.Embed(title=f"PUBG recent matches: {name}", color=0x2563EB)
    lines = []
    for match in matches:
        lines.append(
            f"`{match.get('game_mode', 'unknown')}` place **#{match.get('placement', '?')}** "
            f"- {match.get('kills', 0)} kills - {int(match.get('damage') or 0)} dmg"
        )
    embed.description = "\n".join(lines) if lines else "No recent matches available."
    return embed


def _metric_text(value: Any, *, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _compare_fields(view: str, left: dict[str, Any], right: dict[str, Any]) -> list[tuple[str, str, str]]:
    if view == "ranked":
        return [
            ("Tier", _rank_label(left), _rank_label(right)),
            ("Points", _metric_text(left.get("points"), digits=0), _metric_text(right.get("points"), digits=0)),
            ("Wins", _metric_text(left.get("wins"), digits=0), _metric_text(right.get("wins"), digits=0)),
            ("K/D", _metric_text(left.get("kd")), _metric_text(right.get("kd"))),
        ]
    return [
        ("Matches", _metric_text(left.get("matches"), digits=0), _metric_text(right.get("matches"), digits=0)),
        ("Wins", _metric_text(left.get("wins"), digits=0), _metric_text(right.get("wins"), digits=0)),
        ("K/D", _metric_text(left.get("kd")), _metric_text(right.get("kd"))),
        ("Damage", _metric_text(left.get("damage"), digits=0), _metric_text(right.get("damage"), digits=0)),
    ]


def _rank_label(payload: dict[str, Any]) -> str:
    tier = payload.get("tier") or "Unranked"
    division = payload.get("division")
    return f"{tier}{f' {division}' if division else ''}"
