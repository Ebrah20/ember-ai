"""
routes/api.py — All Flask HTTP routes for Ember AI.
"""

import os
import tempfile

from flask import Blueprint, render_template, request, jsonify

from config import MAX_REQUEST_BYTES, MAX_UPLOAD_AUDIO_BYTES, CREATOR_IPS
from core.brain import (
    process_chat,
    get_whisper_model,
    normalize_tts_provider,
    normalize_vision_provider,
)

api_bp = Blueprint("api", __name__)


def get_real_ip() -> str:
    """
    Return the real client IP.
    - Behind Cloudflare Tunnel: CF-Connecting-IP header holds the real public IP.
    - Direct localhost access: falls back to request.remote_addr (127.0.0.1).
    """
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"


def get_user_role() -> str:
    """
    Creator  = accessing directly from localhost (no Cloudflare header present).
    Guest    = any request arriving through Cloudflare Tunnel (CF-Connecting-IP present).
    """
    if request.headers.get("CF-Connecting-IP"):
        return "guest"
    return "creator" if (request.remote_addr or "") in CREATOR_IPS else "guest"


# ── HTML page ────────────────────────────────────────────────────────────────

@api_bp.route("/")
def index():
    return render_template("index.html")


# ── Error handler (registered on the app, not the blueprint) ─────────────────

def handle_request_too_large(_error):
    return jsonify({"error": "Request too large"}), 413


# ── /ask ─────────────────────────────────────────────────────────────────────

@api_bp.route("/ask", methods=["POST"])
def ask():
    payload = request.get_json(silent=True) or {}
    msg = payload.get("message")
    if not isinstance(msg, str) or not msg.strip():
        return jsonify({"error": "message must be a non-empty string"}), 400

    user_role = get_user_role()
    print(f"[/ask] IP={get_real_ip()} | role={user_role} | message={msg[:60]}")

    tts_provider    = normalize_tts_provider(payload.get("tts_provider", "local"))
    vision_provider = normalize_vision_provider(payload.get("vision_provider", "openai"))
    frontend_image  = payload.get("frontend_image")
    vision_mode     = payload.get("vision_mode")

    reply, audio_b64, audio_mime = process_chat(
        msg.strip(), tts_provider, vision_provider, frontend_image, vision_mode,
        user_role=user_role,
    )
    return jsonify({"reply": reply, "audio_base64": audio_b64, "audio_mime": audio_mime})


@api_bp.route("/ask_stream", methods=["POST"])
def ask_stream():
    """Backward-compatible alias."""
    return ask()


# ── /transcribe ───────────────────────────────────────────────────────────────

def _transcribe_uploaded_file() -> str:
    if "file" not in request.files:
        raise ValueError("No file")
    if request.content_length and request.content_length > MAX_REQUEST_BYTES:
        raise ValueError("Request too large")

    uploaded = request.files["file"]
    uploaded.stream.seek(0, os.SEEK_END)
    file_size = uploaded.stream.tell()
    uploaded.stream.seek(0)
    if file_size > MAX_UPLOAD_AUDIO_BYTES:
        raise ValueError("Audio file too large")

    name = uploaded.filename or ""
    _, ext = os.path.splitext(name)
    safe_ext = ext.lower() if ext else ".wav"
    if len(safe_ext) > 10 or any(ch in safe_ext for ch in ("/", "\\", "\x00")):
        safe_ext = ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=safe_ext) as tmp:
        tmp_path = tmp.name
        uploaded.save(tmp_path)
    try:
        model = get_whisper_model()
        segments, info = model.transcribe(tmp_path, beam_size=5)
        language = getattr(info, "language", None)
        return "".join(s.text for s in segments) if language in ["en", "ar", "fr"] else "..."
    except Exception as e:
        print(f"Transcription error: {e}")
        return "..."
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@api_bp.route("/transcribe", methods=["POST"])
def transcribe():
    try:
        text = _transcribe_uploaded_file()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    tts_provider    = normalize_tts_provider(request.form.get("tts_provider", "local"))
    vision_provider = normalize_vision_provider(request.form.get("vision_provider", "openai"))
    frontend_image  = request.form.get("frontend_image")
    vision_mode     = request.form.get("vision_mode")

    reply, audio_b64, audio_mime = process_chat(
        text if text.strip() else "...",
        tts_provider, vision_provider, frontend_image, vision_mode,
    )
    return jsonify({"user_text": text, "reply": reply, "audio_base64": audio_b64, "audio_mime": audio_mime})


@api_bp.route("/transcribe_stream", methods=["POST"])
def transcribe_stream():
    """Backward-compatible alias."""
    return transcribe()
