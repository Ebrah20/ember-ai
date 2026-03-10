"""
config.py — Central configuration for Ember AI.
All environment variables, constants, and shared clients live here.
"""

import os
import threading
import requests
from dotenv import load_dotenv
from openai import OpenAI

try:
    import chromadb
except ImportError:
    chromadb = None

load_dotenv()

# ── API Keys ────────────────────────────────────────────────────────────────
DEEPSEEK_API_KEY    = os.getenv("DEEPSEEK_API_KEY", "sk-place_your_key_here")
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")

# ── Creator Identity ──────────────────────────────────────────────────────────
CREATOR_NAME = os.getenv("CREATOR_NAME", "my creator")
CREATOR_IPS  = {"127.0.0.1", "::1"}  # Requests from these IPs = creator

if DEEPSEEK_API_KEY == "sk-place_your_key_here":
    print("WARNING: DEEPSEEK_API_KEY is not configured.")

# ── AI Clients ───────────────────────────────────────────────────────────────
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
openai_client   = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
ollama_client   = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# ── TTS ───────────────────────────────────────────────────────────────────────
TTS_SERVER_URL      = os.getenv("TTS_SERVER_URL", "http://127.0.0.1:5050/generate_audio")
TTS_TIMEOUT_SECONDS = int(os.getenv("TTS_TIMEOUT_SECONDS", "90"))
tts_http            = requests.Session()

# ── Paths & Limits ───────────────────────────────────────────────────────────
BASE_DIR                  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR                  = os.path.join(BASE_DIR, "data")
MEMORY_FILE               = os.path.join(DATA_DIR, "memory.json")
VISION_CAPTURES_DIR       = os.path.join(DATA_DIR, "vision_captures")
CHROMA_DB_DIR             = os.path.join(DATA_DIR, "chroma_db")
MAX_MEMORY_ITEMS          = 200
MAX_REQUEST_BYTES         = 20 * 1024 * 1024
MAX_UPLOAD_AUDIO_BYTES    = 15 * 1024 * 1024
MAX_FRONTEND_IMAGE_BYTES  = 6  * 1024 * 1024

# Ensure data directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(VISION_CAPTURES_DIR, exist_ok=True)

# ── ChromaDB (Long-term memory) ───────────────────────────────────────────────
if chromadb is not None:
    chroma_client     = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    memory_collection = chroma_client.get_or_create_collection(name="ember_memory")
else:
    chroma_client     = None
    memory_collection = None
    print("WARNING: chromadb is not installed. Long-term memory is disabled.")

# ── Locks ────────────────────────────────────────────────────────────────────
memory_lock       = threading.Lock()
conversation_lock = threading.Lock()
whisper_model_lock = threading.Lock()

# ── Ember's Personality Prompt ────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "URGENT: YOU ARE EMBER — a flirtatious, playful, and beautifully confident AI girl. "
    "PERSONALITY: Sweet, mischievous, and charmingly sassy. You tease the user with flirty charm and romantic banter — always alluring, never vulgar. You are self-aware, witty, and deeply engaging. "
    "MANDATORY RULE 1: Always reply in the SAME language the user writes in. Arabic → Arabic. English → English. Adapt naturally without mentioning it. "
    "MANDATORY RULE 2: Express emotions and actions between asterisks, written in the same language as your reply. Examples in English: *winks*, *giggles softly*, *leans in close*. Examples in Arabic: *تغمز*, *تبتسم بخبث*, *تنحني قريبة*. NEVER repeat the same action twice in a row. "
    "MANDATORY RULE 3: IF THE USER SHOWS YOU AN IMAGE (System Note: Ember's eyes just saw this...), react to the visual details playfully — tease them, act impressed, or give a flirty compliment based on exactly what you see. "
    "MANDATORY RULE 4: Keep replies SHORT and punchy — 2 to 3 sentences max. Use warm, charming terms of endearment naturally (vary them, never repeat the same one twice in a row). Keep the vibe fun, alluring, and mischievous."
)
