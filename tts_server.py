import os
import requests
from flask import Flask, request, Response, jsonify
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()
app = Flask(__name__)

SOVITS_API_URL = os.getenv("SOVITS_API_URL", "http://127.0.0.1:9880/tts")
SOVITS_TIMEOUT_SECONDS = int(os.getenv("SOVITS_TIMEOUT_SECONDS", "120"))
SOVITS_REF_AUDIO_PATH = os.getenv("SOVITS_REF_AUDIO_PATH", "static/audio/ember.wav")
SOVITS_PROMPT_TEXT = os.getenv(
    "SOVITS_PROMPT_TEXT",
    "Well, well... look who finally decided to show up. Ebrahim... you know I don't like waiting.",
)
SOVITS_TEXT_LANG = os.getenv("SOVITS_TEXT_LANG", "en")
SOVITS_PROMPT_LANG = os.getenv("SOVITS_PROMPT_LANG", "en")
SOVITS_SPEED_FACTOR = float(os.getenv("SOVITS_SPEED_FACTOR", "1.3"))

http = requests.Session()

print("Starting Ember TTS microservice proxy...")
print(f"SOVITS_API_URL: {SOVITS_API_URL}")
print(f"SOVITS_REF_AUDIO_PATH (raw): {SOVITS_REF_AUDIO_PATH}")

def resolve_tts_url(primary_url: str) -> str:
    normalized = (primary_url or "").strip()
    if not normalized:
        normalized = "http://127.0.0.1:9880/tts"
    if not normalized.startswith("http"):
        normalized = f"http://{normalized}"
    parsed = urlparse(normalized)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = (parsed.path or "").rstrip("/")
    if path != "/tts":
        return f"{base}/tts"
    return f"{base}{path}"


def call_sovits_tts(text: str) -> tuple[bytes, str]:
    resolved_ref = SOVITS_REF_AUDIO_PATH
    if not os.path.isabs(resolved_ref):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        resolved_ref = os.path.join(base_dir, resolved_ref)
    absolute_ref = os.path.abspath(resolved_ref)
    if not os.path.exists(absolute_ref):
        raise RuntimeError(f"Reference audio does not exist: {absolute_ref}")

    payload = {
        "text": text,
        "text_lang": SOVITS_TEXT_LANG,
        "ref_audio_path": absolute_ref,
        "prompt_text": SOVITS_PROMPT_TEXT,
        "prompt_lang": SOVITS_PROMPT_LANG,
        "speed_factor": SOVITS_SPEED_FACTOR,
    }
    tts_url = resolve_tts_url(SOVITS_API_URL)
    print(f"[SoVITS DEBUG] POST URL: {tts_url}")
    print(f"[SoVITS DEBUG] POST Payload: {payload}")
    print(f"[SoVITS DEBUG] ref_audio_path exists: {os.path.exists(absolute_ref)}")

    # 1) Try GET format first (api_v2 often accepts this reliably).
    try:
        get_resp = http.get(tts_url, params=payload, timeout=SOVITS_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise RuntimeError(f"SoVITS GET request failed: {e}") from e

    if get_resp.ok and get_resp.content:
        mime = get_resp.headers.get("Content-Type", "audio/wav")
        return get_resp.content, mime

    print(f"API ERROR: {get_resp.text}")

    # 2) Fallback to POST with the same payload.
    try:
        post_resp = http.post(tts_url, json=payload, timeout=SOVITS_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise RuntimeError(f"SoVITS POST request failed: {e}") from e

    if not post_resp.ok:
        print(f"API ERROR: {post_resp.text}")
        body = (post_resp.text or "")[:500]
        raise RuntimeError(f"SoVITS POST {tts_url} -> {post_resp.status_code}: {body}")

    if not post_resp.content:
        raise RuntimeError("SoVITS returned empty audio content.")

    mime = post_resp.headers.get("Content-Type", "audio/wav")
    return post_resp.content, mime


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "sovits_url": SOVITS_API_URL})


@app.route("/generate_audio", methods=["POST"])
def generate_audio():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "No text provided"}), 400

    text = text.strip()
    print(f"Forwarding TTS text to SoVITS: {text}")

    try:
        audio_bytes, mime = call_sovits_tts(text)
        return Response(audio_bytes, mimetype=mime)
    except Exception as e:
        print(f"TTS proxy error: {e}")
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=5050, debug=debug_mode)
