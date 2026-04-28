from __future__ import annotations

import re

VALID_GAMES = ("lol", "valo", "pubg")
RIOT_ID_RE = re.compile(r"^[^#]{3,16}#[A-Za-z0-9]{2,5}$")

REGIONS: dict[str, tuple[str, ...]] = {
    "lol": ("vn2", "na1", "euw1", "kr", "jp1", "br1", "la1", "la2", "oc1", "tr1", "ru"),
    "valo": ("ap", "eu", "na", "kr"),
    "pubg": ("steam", "kakao", "xbox", "psn"),
}


def parse_riot_id(riot_id: str) -> tuple[str, str]:
    value = riot_id.strip()
    if not RIOT_ID_RE.fullmatch(value):
        raise ValueError("Use Riot ID format `Name#TAG`.")
    name, tag = value.split("#", 1)
    if not name.strip():
        raise ValueError("Riot ID name cannot be blank.")
    return name, tag


def validate_game(game: str) -> str:
    normalized = game.lower().strip()
    if normalized not in VALID_GAMES:
        raise ValueError("Choose one of: lol, valo, pubg.")
    return normalized


def validate_region(game: str, region: str | None) -> str:
    normalized_game = validate_game(game)
    default = REGIONS[normalized_game][0]
    normalized_region = (region or default).lower().strip()
    if normalized_region not in REGIONS[normalized_game]:
        allowed = ", ".join(REGIONS[normalized_game])
        raise ValueError(f"Unsupported region/platform. Use one of: {allowed}.")
    return normalized_region
