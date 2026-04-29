from __future__ import annotations

PUBG_PLATFORMS = ("steam", "kakao", "xbox", "psn")
PROFILE_VISIBILITIES = ("private", "public")


def validate_platform(platform: str | None) -> str:
    normalized = (platform or PUBG_PLATFORMS[0]).lower().strip()
    if normalized not in PUBG_PLATFORMS:
        allowed = ", ".join(PUBG_PLATFORMS)
        raise ValueError(f"Unsupported platform. Use one of: {allowed}.")
    return normalized


def validate_profile_visibility(visibility: str | None) -> str:
    normalized = (visibility or PROFILE_VISIBILITIES[0]).lower().strip()
    if normalized not in PROFILE_VISIBILITIES:
        allowed = ", ".join(PROFILE_VISIBILITIES)
        raise ValueError(f"Unsupported visibility. Use one of: {allowed}.")
    return normalized
