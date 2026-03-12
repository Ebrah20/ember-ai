"""
core/games/base.py — Base class for all Ember game profiles.

Each game profile defines:
  - WINDOW_TITLE: substring to match the game window title
  - get_vision_prompt()    : main analysis prompt
  - get_forced_prompt()    : used after 5 consecutive IGNOREs (long, detailed)
  - get_notification_prompt(): reads top-left game notification zone
  - MINIMAP_REGION         : (width_frac, height_frac) of minimap relative to window
"""


class GameProfile:
    """Abstract base class — subclass for each supported game."""

    # Substring that must appear in the window title (case-insensitive match)
    WINDOW_TITLE: str = ""

    # Minimap location as fraction of window size: (width%, height%) of bottom-left corner
    # Set to None if the game has no minimap to scan
    MINIMAP_REGION: tuple[float, float] | None = None

    # ── Prompt builders ──────────────────────────────────────────────────────

    def get_vision_prompt(self, language: str = "Arabic") -> str:
        """Main prompt for regular screenshot analysis."""
        raise NotImplementedError

    def get_forced_prompt(self, language: str = "Arabic") -> str:
        """Prompt used when IGNORE streak reaches the limit — must produce a long comment."""
        return (
            f"You are Ember, a witty, analytical AI gaming companion watching my screen.\n"
            f"IMPORTANT: You MUST give a LONG, DETAILED comment — silence is not allowed.\n"
            f"Write 3-4 sentences analyzing what you see on the game screen: describe the situation, "
            f"the units or buildings you notice, the player's position, and give SPECIFIC "
            f"strategic advice or funny observations. Be thorough and interesting.\n"
            f"Respond entirely in {language}."
        )

    def get_notification_prompt(self, language: str = "Arabic") -> str:
        """Prompt for reading the top-left notification strip (e.g. 'Unit under attack')."""
        return (
            f"This image is a small crop of the top-left corner of a game screen.\n"
            f"The first line may contain technical stats (fps, ms, time) — IGNORE that line.\n"
            f"Read ONLY the game notification below the stats line.\n"
            f"If you see an ATTACK notification: reply [ATTACK] followed by a short reaction in {language}.\n"
            f"If you see a non-attack event: reply a short reaction in {language}.\n"
            f"If there is no clear notification: reply exactly [IGNORE].\n"
            f"Respond in {language}."
        )

    def __repr__(self) -> str:
        return f"<GameProfile: {self.__class__.__name__}>"
