"""
app.py — Ember AI entry point.
All logic lives in config.py, core/, and routes/.
"""

import os
from flask import Flask
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from config import MAX_REQUEST_BYTES
from routes.api import api_bp, handle_request_too_large


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

    # Trust 1 proxy hop (ngrok / nginx) so request.remote_addr = real client IP
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    CORS(app)
    app.register_blueprint(api_bp)
    app.register_error_handler(RequestEntityTooLarge, handle_request_too_large)

    return app



if __name__ == "__main__":
    app = create_app()
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    print("Ember is Ready!")
    app.run(debug=debug_mode, port=5000)
