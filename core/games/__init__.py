"""
core/games/__init__.py — Game profile registry and auto-detection.

Usage:
    from core.games import detect_game, GAME_REGISTRY

    profile = detect_game("GeneralsOnline ~2127 ...")
    prompt  = profile.get_vision_prompt("Arabic")
"""

from .base import GameProfile
from .generals_zh import GeneralsZeroHour
from .hoi4 import HeartsOfIronIV
from .generic import GenericGame

# ── Registry ─────────────────────────────────────────────────────────────────
# Order matters: first match wins. Generic must always be last.
GAME_REGISTRY: list[GameProfile] = [
    GeneralsZeroHour(),
    HeartsOfIronIV(),
    GenericGame(),     # fallback — always last
]


def detect_game(window_title: str) -> GameProfile:
    """
    Return the best matching GameProfile for the given window title.
    Matches by WINDOW_TITLE substring (case-insensitive).
    Falls back to GenericGame if nothing matches.
    """
    title_lower = window_title.lower()
    for profile in GAME_REGISTRY:
        if profile.WINDOW_TITLE and profile.WINDOW_TITLE.lower() in title_lower:
            return profile
    # GenericGame has WINDOW_TITLE = "" — always falls through to here
    return GAME_REGISTRY[-1]


__all__ = ["GameProfile", "GAME_REGISTRY", "detect_game"]
