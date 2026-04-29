from __future__ import annotations

from statistics import pstdev
from typing import Any


def filter_matches(matches: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "all":
        return matches
    if mode == "ranked":
        return [match for match in matches if str(match.get("match_type") or "").lower() == "competitive"]
    return [match for match in matches if str(match.get("game_mode") or "").lower() == mode]


def summarize_recent(matches: list[dict[str, Any]], mode: str, window: int) -> dict[str, Any]:
    filtered = filter_matches(matches, mode)[:window]
    sample_size = len(filtered)
    placements = [_number(match.get("placement")) for match in filtered if match.get("placement") is not None]
    kills = [_number(match.get("kills")) for match in filtered]
    damage = [_number(match.get("damage")) for match in filtered]
    survival = [_number(match.get("survival_time_seconds")) for match in filtered]
    wins = sum(1 for match in filtered if match.get("placement") is not None and int(match["placement"]) == 1)
    top10s = sum(1 for match in filtered if match.get("placement") is not None and int(match["placement"]) <= 10)
    return {
        "mode": mode,
        "window": window,
        "sample_size": sample_size,
        "matches": filtered,
        "avg_placement": _avg(placements),
        "avg_kills": _avg(kills),
        "avg_damage": _avg(damage),
        "avg_survival_time_seconds": _avg(survival),
        "wins": wins,
        "top10_rate": round((top10s / sample_size) * 100, 1) if sample_size else 0.0,
    }


def analyze_profile(recent: dict[str, Any]) -> dict[str, Any]:
    matches = recent.get("matches") or []
    sample_size = int(recent.get("sample_size") or 0)
    if not sample_size:
        return {
            "sample_size": 0,
            "form": "No recent sample yet.",
            "aggression": "No combat sample yet.",
            "survival": "No survival sample yet.",
            "support": "No support sample yet.",
            "consistency": "No consistency sample yet.",
        }

    avg_kills = float(recent.get("avg_kills") or 0.0)
    avg_damage = float(recent.get("avg_damage") or 0.0)
    avg_place = float(recent.get("avg_placement") or 99.0)
    avg_survival = float(recent.get("avg_survival_time_seconds") or 0.0)
    top10_rate = float(recent.get("top10_rate") or 0.0)
    assists = _avg([_number(match.get("assists")) for match in matches])
    revives = _avg([_number(match.get("revives")) for match in matches])
    placement_spread = _spread([_number(match.get("placement")) for match in matches if match.get("placement") is not None])
    return {
        "sample_size": sample_size,
        "form": _form_label(avg_place, top10_rate, avg_kills),
        "aggression": _aggression_label(avg_kills, avg_damage),
        "survival": _survival_label(avg_survival, avg_place, top10_rate),
        "support": _support_label(assists, revives),
        "consistency": _consistency_label(placement_spread, sample_size),
    }


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _number(value: Any) -> float:
    return float(value or 0)


def _spread(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round(float(pstdev(values)), 2)


def _form_label(avg_place: float, top10_rate: float, avg_kills: float) -> str:
    if avg_place <= 4 and top10_rate >= 60:
        return f"Hot streak. Avg place {avg_place:.1f}, top-10 rate {top10_rate:.0f}%."
    if avg_place <= 8 or avg_kills >= 3:
        return f"Stable form. Avg place {avg_place:.1f}, {avg_kills:.1f} kills/game."
    return f"Cold sample. Avg place {avg_place:.1f}, top-10 rate {top10_rate:.0f}%."


def _aggression_label(avg_kills: float, avg_damage: float) -> str:
    if avg_kills >= 4 or avg_damage >= 450:
        return f"High pressure. {avg_kills:.1f} kills and {avg_damage:.0f} dmg/game."
    if avg_kills >= 2 or avg_damage >= 250:
        return f"Balanced pace. {avg_kills:.1f} kills and {avg_damage:.0f} dmg/game."
    return f"Low-volley pace. {avg_kills:.1f} kills and {avg_damage:.0f} dmg/game."


def _survival_label(avg_survival: float, avg_place: float, top10_rate: float) -> str:
    if avg_survival >= 1200 or top10_rate >= 70:
        return f"Deep circles often. {avg_survival/60:.1f} min survival, avg place {avg_place:.1f}."
    if avg_survival >= 800 or avg_place <= 10:
        return f"Mid-to-late game stable. {avg_survival/60:.1f} min survival."
    return f"Early exits common. {avg_survival/60:.1f} min survival."


def _support_label(assists: float, revives: float) -> str:
    if assists + revives >= 2.5:
        return f"Strong squad utility. {assists:.1f} assists and {revives:.1f} revives/game."
    if assists + revives >= 1:
        return f"Some support impact. {assists:.1f} assists and {revives:.1f} revives/game."
    return f"Mostly self-driven fights. {assists:.1f} assists and {revives:.1f} revives/game."


def _consistency_label(placement_spread: float, sample_size: int) -> str:
    if sample_size < 3:
        return "Sample too small for strong consistency read."
    if placement_spread <= 4:
        return f"Consistent placements. Spread {placement_spread:.1f}."
    if placement_spread <= 8:
        return f"Moderate variance. Spread {placement_spread:.1f}."
    return f"Swingy results. Spread {placement_spread:.1f}."
