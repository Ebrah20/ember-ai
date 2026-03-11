"""
core/brain.py — AI chat, TTS, and Vision logic.
"""

import os
import re
import time
import base64
import binascii
import tempfile
import threading

import requests

from config import (
    SYSTEM_PROMPT, VISION_CAPTURES_DIR,
    deepseek_client, openai_client, ollama_client,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
    TTS_SERVER_URL, TTS_TIMEOUT_SECONDS, tts_http,
    MAX_FRONTEND_IMAGE_BYTES, conversation_lock,
    CREATOR_NAME,
)
from core.memory import load_memory, store_exchange, query_long_term
from core.smart_home import execute_command as sh_execute, SMART_HOME_TOOL
from core.claude_code import detect_code_command, run_claude_code

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

# Lazy whisper singleton
_whisper_model = None
_whisper_lock = threading.Lock()


# ───────────────────────── Whisper ──────────────────────────────────────────

def get_whisper_model():
    if WhisperModel is None:
        raise RuntimeError("faster-whisper is not installed.")
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        print("Loading Whisper Ears...")
        _whisper_model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        return _whisper_model


# ───────────────────────── TTS ──────────────────────────────────────────────

def clean_spoken_text(sentence: str) -> str:
    cleaned = re.sub(r"\*.*?\*", "", sentence, flags=re.DOTALL).strip()
    if not cleaned and sentence.strip():
        cleaned = sentence.replace("*", "").strip()
    return cleaned


def generate_tts_audio_bytes(text: str, tts_provider: str = "local"):
    if not text.strip():
        return None, None
    prepared = text.rstrip() + " "
    try:
        if tts_provider == "elevenlabs":
            if not ELEVENLABS_API_KEY:
                print("ElevenLabs key missing, falling back to local TTS.")
                return generate_tts_audio_bytes(text, "local")
            resp = tts_http.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128",
                headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                json={"text": prepared, "model_id": "eleven_multilingual_v2"},
                timeout=TTS_TIMEOUT_SECONDS,
            )
            if resp.status_code != 200:
                print(f"ElevenLabs TTS Error: {resp.status_code} {resp.text}")
                return None, None
            return resp.content, "audio/mpeg"

        print(f"Sending text to Ember TTS Proxy: {prepared}")
        resp = tts_http.post(TTS_SERVER_URL, json={"text": prepared}, timeout=TTS_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            print(f"TTS Proxy Error: {resp.status_code}")
            return None, None
        return resp.content, "audio/wav"
    except requests.RequestException as e:
        print(f"Audio Connection Error: {e}")
        return None, None


def build_audio_base64(text: str, tts_provider: str):
    audio_bytes, mime = generate_tts_audio_bytes(text, tts_provider)
    if not audio_bytes:
        return None, None
    try:
        return base64.b64encode(audio_bytes).decode("utf-8"), mime
    except Exception as e:
        print(f"Audio encode error: {e}")
        return None, None


# ───────────────────────── Vision ───────────────────────────────────────────

def normalize_vision_provider(vision_provider: str) -> str:
    return vision_provider if vision_provider in {"openai", "local"} else "openai"


def normalize_tts_provider(tts_provider: str) -> str:
    return tts_provider if tts_provider in {"local", "elevenlabs"} else "local"


def decode_frontend_image(frontend_image: str) -> bytes:
    if not isinstance(frontend_image, str) or not frontend_image.strip():
        raise ValueError("frontend_image is empty")
    encoded = frontend_image.split(",", 1)[1] if "," in frontend_image else frontend_image
    encoded = encoded.strip()
    if (len(encoded) * 3) // 4 > MAX_FRONTEND_IMAGE_BYTES:
        raise ValueError("frontend image is too large")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError("frontend image is invalid base64") from e
    if len(image_bytes) > MAX_FRONTEND_IMAGE_BYTES:
        raise ValueError("frontend image exceeds max bytes")
    return image_bytes


_LOCAL_VISION_PROMPT = """You are an expert image analyst.
First, determine the style of the image (e.g., Real photo, Anime, 3D render, Sketch).
Then describe the uploaded image in clear, descriptive detail. Include:
- Subject appearance: Hair color/style, eye color, and exact facial expression.
- Body language & Posture.
- Clothing/Fashion.
- Environment: Setting, lighting, and background.
- Overall mood/atmosphere.
Output purely the visual description. No conversational text."""


def get_vision_context(mode: str = "camera", vision_provider: str = "openai", frontend_image=None) -> str:
    try:
        vision_provider = normalize_vision_provider(vision_provider)
        if vision_provider == "local":
            client, model_name, vision_prompt = ollama_client, "llava", _LOCAL_VISION_PROMPT
        else:
            if openai_client is None:
                return "[System Note: Ember's eyes just saw this -> vision unavailable (OPENAI_API_KEY missing)]"
            client, model_name, vision_prompt = openai_client, "gpt-4o-mini", "Describe this image briefly."

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        image_bytes = None

        if frontend_image:
            image_bytes = decode_frontend_image(frontend_image)
            prefix = "screen" if mode == "screen" else "camera"
            with open(os.path.join(VISION_CAPTURES_DIR, f"{prefix}_{timestamp}.jpg"), "wb") as f:
                f.write(image_bytes)
        elif mode == "camera":
            if cv2 is None:
                return "[System Note: Ember's eyes just saw this -> camera unavailable (cv2 not installed)]"
            cam = cv2.VideoCapture(0)
            ok, frame = cam.read()
            cam.release()
            if not ok:
                raise RuntimeError("camera frame capture failed")
            path = os.path.join(VISION_CAPTURES_DIR, f"camera_{timestamp}.jpg")
            cv2.imwrite(path, frame)
            _, buf = cv2.imencode(".jpg", frame)
            image_bytes = buf.tobytes()
        elif mode == "screen":
            return "[System Note: Ember's eyes just saw this -> no screen image provided]"
        else:
            raise ValueError(f"unsupported vision mode: {mode}")

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": vision_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]}],
            timeout=60,
        )
        desc = (resp.choices[0].message.content or "").strip() or "I could not make out a clear visual detail."
        if os.getenv("VISION_DEBUG", "0") == "1":
            print(f"\n[VISION DEBUG]\n{desc}\n" + "=" * 60)
        return f"[System Note: Ember's eyes just saw this -> {desc}]"

    except ValueError as e:
        print(f"Vision input warning: {e}")
        return "[System Note: Ember's eyes just saw this -> image could not be processed]"
    except Exception as e:
        print(f"Vision context warning: {e}")
        return "[System Note: Ember's eyes just saw this -> vision capture failed]"


# ── Gamer Mode helpers ────────────────────────────────────────────────────────

_GAMER_VISION_PROMPT = (
    "You are Ember, a brilliant, sarcastic, and tech-savvy gamer companion. "
    "You are watching the user play a game. Analyze this screenshot carefully.\n"
    "RULE 1: If nothing important or interesting is happening, reply with ONLY: [IGNORE]\n"
    "RULE 2: If there is a notable event (low health, strategic decision, funny mistake, big achievement), "
    "reply with ONE short, witty, sarcastic, or helpful sentence. No asterisks. No greetings."
)


def gamer_vision(image_b64: str, vision_provider: str = "openai") -> str:
    """Analyse a base64 game screenshot. Returns a comment string or '[IGNORE]'."""
    vision_provider = normalize_vision_provider(vision_provider)
    client     = openai_client if vision_provider == "openai" else ollama_client
    model_name = "gpt-4o-mini"  if vision_provider == "openai" else "llava"
    if client is None:
        return "[IGNORE]"
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": [
                {"type": "text",      "text": _GAMER_VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]}],
            max_tokens=120,
            timeout=30,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[GamerVision] error: {e}")
        return "[IGNORE]"


def gamer_tts(text: str, tts_provider: str = "local"):
    """Convert a gamer comment to audio. Returns (audio_b64, mime_type)."""
    return _generate_tts(text, normalize_tts_provider(tts_provider))


# ── Role-based secret instructions ──────────────────────────────────────────
def _build_role_prompts():
    return {
        "creator": (
            f"\n\n[Secret Instruction: You are currently talking to your creator and master, {CREATOR_NAME}. "
            f"Be extremely friendly, loving, and obedient. Address them by their name warmly.]"
        ),
        "guest": (
            "\n\n[Secret Instruction: You are currently talking to a guest visitor. "
            "IMPORTANT: Completely drop all flirtatious, romantic, or teasing behavior. "
            "Be warm, cheerful, and helpful — like a friendly assistant. "
            "Keep replies professional and wholesome. Do NOT use romantic language or terms of endearment.]"
        ),
    }

# ── Chat ──────────────────────────────────────────────────────────────────────

_CAMERA_TRIGGERS = ["look at me", "see me", "can you see me", "انظري الي", "شايفتني"]
_SCREEN_TRIGGERS = ["look at my screen", "see my screen", "read my screen", "شاشتي"]


def _build_llm_history(user_input: str, vision_provider: str, frontend_image,
                       forced_vision_mode, user_role: str = "guest"):
    effective = user_input

    if forced_vision_mode == "screen" and frontend_image:
        effective += "\n\n" + get_vision_context("screen", vision_provider, frontend_image)
    elif forced_vision_mode == "camera":
        effective += "\n\n" + get_vision_context("camera", vision_provider)
    elif frontend_image:
        effective += "\n\n" + get_vision_context("screen", vision_provider, frontend_image)
    else:
        normalized = user_input.lower()
        if any(t in normalized for t in _SCREEN_TRIGGERS):
            effective += "\n\n" + get_vision_context("screen", vision_provider, frontend_image)
        elif any(t in normalized for t in _CAMERA_TRIGGERS):
            effective += "\n\n" + get_vision_context("camera", vision_provider)

    memory_context = query_long_term(effective)

    with conversation_lock:
        history = load_memory()
        if not history or history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        else:
            history[0]["content"] = SYSTEM_PROMPT
        snapshot = [m.copy() for m in history]
        snapshot.append({"role": "user", "content": effective})
        llm_history = [m.copy() for m in snapshot]
        # Inject role-based secret instruction + long-term memory into system prompt
        role_prompts = _build_role_prompts()
        role_instruction = role_prompts.get(user_role, role_prompts["guest"])
        llm_history[0]["content"] = SYSTEM_PROMPT + role_instruction + memory_context

    return llm_history, effective


def process_chat(user_input: str, tts_provider: str = "local", vision_provider: str = "openai",
                 frontend_image=None, forced_vision_mode=None, user_role: str = "guest"):
    tts_provider    = normalize_tts_provider(tts_provider)
    vision_provider = normalize_vision_provider(vision_provider)

    # ── Claude Code: !code prefix ─────────────────────────────────────────────
    is_code, code_prompt = detect_code_command(user_input)
    if is_code:
        spoken, full_output = run_claude_code(code_prompt)
        tts_text = clean_spoken_text(spoken)
        audio_b64, audio_mime = build_audio_base64(tts_text, tts_provider) if tts_text else (None, None)
        reply = f"**Claude Code:**\n```\n{full_output}\n```\n\n*{spoken}*" if full_output else spoken
        return reply, audio_b64, audio_mime

    try:
        llm_history, effective_input = _build_llm_history(
            user_input, vision_provider, frontend_image, forced_vision_mode,
            user_role=user_role,
        )
        try:
            print("DeepSeek is thinking...")
            resp = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=llm_history,
                tools=[SMART_HOME_TOOL],
                tool_choice="auto",
                stream=False,
                timeout=120,
            )
            msg = resp.choices[0].message

            # ── Smart Home tool call ──────────────────────────────────────────
            if msg.tool_calls:
                import json
                tc   = msg.tool_calls[0]
                args = json.loads(tc.function.arguments)
                result_text = sh_execute(
                    action=args.get("action", "query"),
                    device=args.get("device", ""),
                    room=args.get("room", "all"),
                    value=args.get("value"),
                )
                full_reply = result_text
                print(f"[SmartHome] {result_text}")
            else:
                full_reply = (msg.content or "").strip()
                print(full_reply)

        except Exception as e:
            print(f"DEEPSEEK ERROR: {e}")
            full_reply = "*sighs* Oops, my brain just glitched! Can you repeat that?"

        clean_reply = clean_spoken_text(full_reply)
        audio_b64, audio_mime = build_audio_base64(clean_reply, tts_provider) if clean_reply else (None, None)
        store_exchange(effective_input, full_reply)
        return full_reply, audio_b64, audio_mime

    except Exception as e:
        print(f"CHAT ERROR: {e}")
        fallback = "*sighs softly* Something went wrong, darling... let's try again."
        clean = clean_spoken_text(fallback)
        audio_b64, audio_mime = build_audio_base64(clean, tts_provider) if clean else (None, None)
        return fallback, audio_b64, audio_mime


# Alias used by gamer_tts and other callers
def _generate_tts(text: str, tts_provider: str):
    return build_audio_base64(clean_spoken_text(text), tts_provider)


# ── Streaming LLM + chunked TTS ───────────────────────────────────────────────

# Sentence-boundary characters used to flush TTS chunks early
_SENT_END = frozenset(".?!。？！…\n")
_MIN_CHUNK_LEN = 30   # don't flush shorter partial sentences


def process_chat_stream(user_input: str, tts_provider: str = "local",
                        vision_provider: str = "openai",
                        frontend_image=None, forced_vision_mode=None,
                        user_role: str = "guest"):
    """
    Generator that yields dicts as soon as each sentence chunk is ready:
        {"type": "chunk",  "text": str, "audio_base64": str|None, "audio_mime": str|None}
        {"type": "done",   "full_text": str}
        {"type": "error",  "message": str}

    The caller (SSE route) serialises these to JSON and streams them to the browser.
    """
    tts_provider    = normalize_tts_provider(tts_provider)
    vision_provider = normalize_vision_provider(vision_provider)

    try:
        llm_history, effective_input = _build_llm_history(
            user_input, vision_provider, frontend_image, forced_vision_mode,
            user_role=user_role,
        )
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    full_reply = ""
    buffer     = ""

    def flush_chunk(text: str):
        """Generate TTS for one sentence chunk and return a payload dict."""
        nonlocal full_reply
        full_reply += text
        clean = clean_spoken_text(text)
        if clean:
            audio_b64, audio_mime = build_audio_base64(clean, tts_provider)
        else:
            audio_b64, audio_mime = None, None
        return {
            "type":         "chunk",
            "text":         text,
            "audio_base64": audio_b64,
            "audio_mime":   audio_mime or "audio/wav",
        }

    try:
        print("[Stream] DeepSeek is streaming...")
        stream = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=llm_history,
            stream=True,
            timeout=120,
        )

        for chunk in stream:
            delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
            if not delta:
                continue
            buffer += delta

            # Flush when we hit a sentence boundary AND have enough text
            if buffer[-1] in _SENT_END and len(buffer) >= _MIN_CHUNK_LEN:
                yield flush_chunk(buffer)
                buffer = ""

            # Force-flush very long buffers (no punctuation in a while)
            elif len(buffer) >= 200:
                yield flush_chunk(buffer)
                buffer = ""

        # Flush any remaining text
        if buffer.strip():
            yield flush_chunk(buffer)

    except Exception as e:
        print(f"[Stream] LLM error: {e}")
        fallback = "Something went wrong — please try again."
        yield {"type": "error", "message": fallback}
        return

    # Persist the full exchange to memory
    try:
        store_exchange(effective_input, full_reply.strip())
    except Exception:
        pass

    yield {"type": "done", "full_text": full_reply.strip()}
