"""
app.py — Ember AI entry point.
All logic lives in config.py, core/, and routes/.
"""

import os
from flask import Flask
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

from config import (
    MAX_REQUEST_BYTES,
    GAMER_MODE_TARGET_WINDOW,
    GAMER_MODE_INTERVAL,
)
from routes.api import api_bp, handle_request_too_large
import routes.api as _api_routes


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

    CORS(app)
    app.register_blueprint(api_bp)
    app.register_error_handler(RequestEntityTooLarge, handle_request_too_large)

    # ── Gamer Mode singleton ──────────────────────────────────────────────────
    from core.gamer import GamerMode
    from core.brain import gamer_vision, gamer_tts, read_notification
    from core.games import detect_game

    # Auto-detect which game profile to use from the window title in .env
    game_profile = detect_game(GAMER_MODE_TARGET_WINDOW)
    print(f"[Ember] Gamer Mode profile: {game_profile}")

    gm = GamerMode(
        target_window=GAMER_MODE_TARGET_WINDOW,
        interval=GAMER_MODE_INTERVAL,
        vision_fn=gamer_vision,
        tts_fn=gamer_tts,
    )
    gm._notif_fn = read_notification   # vision reader for top-left notification zone
    gm._profile  = game_profile        # game-specific prompts & minimap config
    gm.start()
    _api_routes.gamer_instance = gm

    return app


if __name__ == "__main__":
    app = create_app()
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    print("Ember is Ready!")
    app.run(debug=debug_mode, port=5000)
