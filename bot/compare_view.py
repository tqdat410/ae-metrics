from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import discord

from bot.embeds import TIER_COLORS, tier_key, tier_weight

BLANK = "\u200b"
BAR_FILLED = "█"
BAR_EMPTY = "░"
BAR_WIDTH = 10
ComparePage = Literal["all", "recent", "rank"]


@dataclass(frozen=True)
class CompareMetric:
    label: str
    left_text: str
    right_text: str
    left_scale: float | None
    right_scale: float | None


class CompareView(discord.ui.View):
    def __init__(self, left_member: str, right_member: str, left_payload: dict[str, Any], right_payload: dict[str, Any]) -> None:
        super().__init__(timeout=600)
        self.left_member = left_member
        self.right_member = right_member
        self.left_payload = left_payload
        self.right_payload = right_payload
        self.page: ComparePage = "all"
        self.message: Any | None = None
        self._sync_buttons()

    def current_embed(self) -> discord.Embed:
        return build_compare_embed(self.page, self.left_member, self.right_member, self.left_payload, self.right_payload)

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message is not None and hasattr(self.message, "edit"):
            await self.message.edit(view=self)

    @discord.ui.button(label="All", style=discord.ButtonStyle.primary)
    async def all_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._swap_page(interaction, "all")

    @discord.ui.button(label="Recent", style=discord.ButtonStyle.secondary)
    async def recent_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._swap_page(interaction, "recent")

    @discord.ui.button(label="Rank", style=discord.ButtonStyle.secondary)
    async def rank_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._swap_page(interaction, "rank")

    async def _swap_page(self, interaction: discord.Interaction, page: ComparePage) -> None:
        self.page = page
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    def _sync_buttons(self) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            is_active = (child.label == "All" and self.page == "all") or (child.label == "Recent" and self.page == "recent") or (child.label == "Rank" and self.page == "rank")
            child.style = discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary

def build_compare_embed(page: ComparePage, left_member: str, right_member: str, left_payload: dict[str, Any], right_payload: dict[str, Any]) -> discord.Embed:
    left_ranked = left_payload.get("ranked") or {}
    right_ranked = right_payload.get("ranked") or {}
    embed = discord.Embed(
        title=f"So sánh: {left_member} vs {right_member}",
        description=_description(page, left_member, right_member, left_ranked, right_ranked),
        color=_compare_color(left_ranked, right_ranked),
    )
    if page == "all":
        _add_metric_fields(embed, left_member, right_member, _lifetime_metrics(left_payload.get("lifetime") or {}, right_payload.get("lifetime") or {}))
    elif page == "rank":
        _add_metric_fields(embed, left_member, right_member, _rank_metrics(left_ranked, right_ranked))
    else:
        _add_metric_fields(embed, left_member, right_member, _recent_metrics(left_payload.get("recent") or {}, right_payload.get("recent") or {}))
    embed.set_footer(text=f"{left_member}: {_timestamp_text(left_payload.get('generated_at'))} ICT | {right_member}: {_timestamp_text(right_payload.get('generated_at'))} ICT")
    return embed

def _add_metric_fields(embed: discord.Embed, left_member: str | None, right_member: str | None, metrics: list[CompareMetric]) -> None:
    for metric in metrics:
        left_bar, right_bar = _bars(metric.left_scale, metric.right_scale)
        left_name = left_member or ""
        right_name = right_member or ""
        left_line = _metric_line(left_name, left_bar, metric.left_text)
        right_line = _metric_line(right_name, right_bar, metric.right_text)
        embed.add_field(name=metric.label, value=f"{left_line}\n{right_line}", inline=True)
    remainder = len(metrics) % 3
    if remainder:
        for _ in range(3 - remainder):
            embed.add_field(name=BLANK, value=BLANK, inline=True)

def _metric_line(member: str, bar: str, text: str) -> str:
    return f"{f'**{member}:** ' if member else ''}{bar} {text}"

def _description(page: ComparePage, left_member: str, right_member: str, left_ranked: dict[str, Any], right_ranked: dict[str, Any]) -> str:
    if page == "all": return "**All**  |  Lifetime core stats"
    if page == "recent": return "**Recent**  |  Avg. 20 Games"
    return f"**{left_member}:** {_rank_summary(left_ranked)}\n**{right_member}:** {_rank_summary(right_ranked)}"

def _rank_metrics(left: dict[str, Any], right: dict[str, Any]) -> list[CompareMetric]:
    return [
        CompareMetric("Tier", _tier_short(left), _tier_short(right), float(tier_weight(left.get("tier"), left.get("division"), left.get("points"))), float(tier_weight(right.get("tier"), right.get("division"), right.get("points")))),
        CompareMetric("Rank Points", f"{_metric(left.get('points'), 0)} RP", f"{_metric(right.get('points'), 0)} RP", _number(left.get("points")), _number(right.get("points"))),
        CompareMetric("Matches", _metric(left.get("matches"), 0), _metric(right.get("matches"), 0), _number(left.get("matches")), _number(right.get("matches"))),
        CompareMetric("Wins", _metric(left.get("wins"), 0), _metric(right.get("wins"), 0), _number(left.get("wins")), _number(right.get("wins"))),
        CompareMetric("Win Rate", _percent_text(left.get("wins"), left.get("matches")), _percent_text(right.get("wins"), right.get("matches")), _percent_value(left.get("wins"), left.get("matches")), _percent_value(right.get("wins"), right.get("matches"))),
        CompareMetric("K/D", _metric(left.get("kd")), _metric(right.get("kd")), _number(left.get("kd")), _number(right.get("kd"))),
    ]

def _lifetime_metrics(left: dict[str, Any], right: dict[str, Any]) -> list[CompareMetric]:
    return [
        CompareMetric("Matches", _metric(left.get("matches"), 0), _metric(right.get("matches"), 0), _number(left.get("matches")), _number(right.get("matches"))),
        CompareMetric("Wins", _metric(left.get("wins"), 0), _metric(right.get("wins"), 0), _number(left.get("wins")), _number(right.get("wins"))),
        CompareMetric("Win Rate", _percent_text(left.get("wins"), left.get("matches")), _percent_text(right.get("wins"), right.get("matches")), _percent_value(left.get("wins"), left.get("matches")), _percent_value(right.get("wins"), right.get("matches"))),
        CompareMetric("Top 10 Rate", _percent_text(left.get("top10s"), left.get("matches")), _percent_text(right.get("top10s"), right.get("matches")), _percent_value(left.get("top10s"), left.get("matches")), _percent_value(right.get("top10s"), right.get("matches"))),
        CompareMetric("K/D", _metric(left.get("kd")), _metric(right.get("kd")), _number(left.get("kd")), _number(right.get("kd"))),
        CompareMetric("Avg Kills", _ratio_text(left.get("kills"), left.get("matches")), _ratio_text(right.get("kills"), right.get("matches")), _ratio_value(left.get("kills"), left.get("matches")), _ratio_value(right.get("kills"), right.get("matches"))),
        CompareMetric("Avg Damage", _ratio_text(left.get("damage"), left.get("matches"), digits=0), _ratio_text(right.get("damage"), right.get("matches"), digits=0), _ratio_value(left.get("damage"), left.get("matches")), _ratio_value(right.get("damage"), right.get("matches"))),
        CompareMetric("Avg Assists", _ratio_text(left.get("assists"), left.get("matches")), _ratio_text(right.get("assists"), right.get("matches")), _ratio_value(left.get("assists"), left.get("matches")), _ratio_value(right.get("assists"), right.get("matches"))),
        CompareMetric("Avg Revives", _ratio_text(left.get("revives"), left.get("matches")), _ratio_text(right.get("revives"), right.get("matches")), _ratio_value(left.get("revives"), left.get("matches")), _ratio_value(right.get("revives"), right.get("matches"))),
        CompareMetric("Avg Survival", _minutes_text(left.get("avg_survival_time")), _minutes_text(right.get("avg_survival_time")), _number(left.get("avg_survival_time")), _number(right.get("avg_survival_time"))),
        CompareMetric("Headshots", _metric(left.get("headshots"), 0), _metric(right.get("headshots"), 0), _number(left.get("headshots")), _number(right.get("headshots"))),
        CompareMetric("HS Rate", _percent_text(left.get("headshots"), left.get("kills")), _percent_text(right.get("headshots"), right.get("kills")), _percent_value(left.get("headshots"), left.get("kills")), _percent_value(right.get("headshots"), right.get("kills"))),
        CompareMetric("Longest Kill", _distance_text(left.get("longest_kill")), _distance_text(right.get("longest_kill")), _number(left.get("longest_kill")), _number(right.get("longest_kill"))),
        CompareMetric("Total Kills", _metric(left.get("kills"), 0), _metric(right.get("kills"), 0), _number(left.get("kills")), _number(right.get("kills"))),
        CompareMetric("Total Damage", _metric(left.get("damage"), 0), _metric(right.get("damage"), 0), _number(left.get("damage")), _number(right.get("damage"))),
    ]

def _recent_metrics(left: dict[str, Any], right: dict[str, Any]) -> list[CompareMetric]:
    return [
        CompareMetric("Matches", _metric(left.get("sample_size"), 0), _metric(right.get("sample_size"), 0), _number(left.get("sample_size")), _number(right.get("sample_size"))),
        CompareMetric("Wins", _metric(left.get("wins"), 0), _metric(right.get("wins"), 0), _number(left.get("wins")), _number(right.get("wins"))),
        CompareMetric("Win Rate", _percent_text(left.get("wins"), left.get("sample_size")), _percent_text(right.get("wins"), right.get("sample_size")), _percent_value(left.get("wins"), left.get("sample_size")), _percent_value(right.get("wins"), right.get("sample_size"))),
        CompareMetric("Top 10 Rate", f"{_metric(left.get('top10_rate'))}%", f"{_metric(right.get('top10_rate'))}%", _number(left.get("top10_rate")), _number(right.get("top10_rate"))),
        CompareMetric("K/D", "n/a", "n/a", None, None),
        CompareMetric("Avg Kills", _metric(left.get("avg_kills")), _metric(right.get("avg_kills")), _number(left.get("avg_kills")), _number(right.get("avg_kills"))),
        CompareMetric("Avg Damage", _metric(left.get("avg_damage"), 0), _metric(right.get("avg_damage"), 0), _number(left.get("avg_damage")), _number(right.get("avg_damage"))),
        CompareMetric("Avg Assists", _metric(_avg_from_matches(left, "assists")), _metric(_avg_from_matches(right, "assists")), _avg_from_matches(left, "assists"), _avg_from_matches(right, "assists")),
        CompareMetric("Avg Revives", _metric(_avg_from_matches(left, "revives")), _metric(_avg_from_matches(right, "revives")), _avg_from_matches(left, "revives"), _avg_from_matches(right, "revives")),
        CompareMetric("Avg Survival", _minutes_text(left.get("avg_survival_time_seconds")), _minutes_text(right.get("avg_survival_time_seconds")), _number(left.get("avg_survival_time_seconds")), _number(right.get("avg_survival_time_seconds"))),
        CompareMetric("Avg Place", _metric(left.get("avg_placement")), _metric(right.get("avg_placement")), _number(left.get("avg_placement")), _number(right.get("avg_placement"))),
    ]

def _bars(left: float | None, right: float | None) -> tuple[str, str]:
    if left is None and right is None:
        return BAR_EMPTY * BAR_WIDTH, BAR_EMPTY * BAR_WIDTH
    left_value = max(left or 0.0, 0.0)
    right_value = max(right or 0.0, 0.0)
    if left_value == 0 and right_value == 0:
        return BAR_EMPTY * BAR_WIDTH, BAR_EMPTY * BAR_WIDTH
    if left_value == right_value:
        return BAR_FILLED * BAR_WIDTH, BAR_FILLED * BAR_WIDTH
    peak = max(left_value, right_value)
    return _bar(left_value, peak), _bar(right_value, peak)

def _bar(value: float, peak: float) -> str:
    if value <= 0 or peak <= 0: count = 0
    elif value == peak: count = BAR_WIDTH
    else: count = max(1, round((value / peak) * BAR_WIDTH))
    return BAR_FILLED * count + BAR_EMPTY * (BAR_WIDTH - count)

def _compare_color(left_ranked: dict[str, Any], right_ranked: dict[str, Any]) -> int:
    left_weight = tier_weight(left_ranked.get("tier"), left_ranked.get("division"), left_ranked.get("points"))
    right_weight = tier_weight(right_ranked.get("tier"), right_ranked.get("division"), right_ranked.get("points"))
    source = left_ranked if left_weight >= right_weight else right_ranked
    return TIER_COLORS.get(tier_key(source.get("tier")), 0x2563EB)

def _tier_short(payload: dict[str, Any]) -> str:
    tier = tier_key(payload.get("tier"))
    if tier == "MASTER":
        return "M"
    division = str(payload.get("division") or "").upper()
    division_text = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5"}.get(division, division)
    return f"{tier[:1]}{division_text}" if division_text else tier[:1]

def _rank_summary(payload: dict[str, Any]) -> str:
    return f"**{_tier_short(payload)}**  |  **{_metric(payload.get('points'), 0)} RP**  |  **{_label(payload.get('mode'))}**"

def _avg_from_matches(recent: dict[str, Any], key: str) -> float:
    matches = recent.get("matches") or []
    return 0.0 if not matches else round(sum(float(match.get(key) or 0) for match in matches) / len(matches), 2)

def _percent_value(numerator: Any, denominator: Any) -> float | None:
    bottom = _number(denominator)
    if bottom <= 0:
        return None
    return (_number(numerator) / bottom) * 100

def _percent_text(numerator: Any, denominator: Any) -> str:
    value = _percent_value(numerator, denominator); return "n/a" if value is None else f"{value:.1f}%"

def _ratio_value(numerator: Any, denominator: Any) -> float | None:
    bottom = _number(denominator)
    if bottom <= 0:
        return None
    return _number(numerator) / bottom

def _ratio_text(numerator: Any, denominator: Any, *, digits: int = 2) -> str:
    value = _ratio_value(numerator, denominator); return "n/a" if value is None else f"{value:.{digits}f}"

def _minutes_text(value: Any) -> str:
    seconds = _number(value); return "n/a" if seconds <= 0 else f"{seconds / 60:.1f} min"

def _distance_text(value: Any) -> str:
    number = _number(value); return "n/a" if number <= 0 else f"{number:.1f} m"

def _metric(value: Any, digits: int = 2) -> str:
    number = _number(value)
    if value is None: return "n/a"
    if isinstance(value, float): return f"{number:.{digits}f}"
    return str(int(number)) if digits == 0 else str(value)

def _number(value: Any) -> float:
    return float(value or 0)

def _label(value: Any) -> str:
    return str(value) if value else "n/a"

def _timestamp_text(value: Any) -> str:
    if not value:
        return "unknown"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)
