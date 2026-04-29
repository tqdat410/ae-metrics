from __future__ import annotations

PUBG_PLATFORMS = ("steam", "kakao", "xbox", "psn")
PROFILE_VIEWS = ("ranked", "lifetime")
LEADERBOARD_METRICS = ("rank_points", "wins", "kd", "damage")


def validate_platform(platform: str | None) -> str:
    normalized = (platform or PUBG_PLATFORMS[0]).lower().strip()
    if normalized not in PUBG_PLATFORMS:
        allowed = ", ".join(PUBG_PLATFORMS)
        raise ValueError(f"Unsupported platform. Use one of: {allowed}.")
    return normalized


def validate_profile_view(view: str | None) -> str:
    normalized = (view or PROFILE_VIEWS[0]).lower().strip()
    if normalized not in PROFILE_VIEWS:
        allowed = ", ".join(PROFILE_VIEWS)
        raise ValueError(f"Unsupported view. Use one of: {allowed}.")
    return normalized


def validate_leaderboard_metric(metric: str | None) -> str:
    normalized = (metric or LEADERBOARD_METRICS[0]).lower().strip()
    if normalized not in LEADERBOARD_METRICS:
        allowed = ", ".join(LEADERBOARD_METRICS)
        raise ValueError(f"Unsupported metric. Use one of: {allowed}.")
    return normalized
