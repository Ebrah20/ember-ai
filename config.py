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
CREATOR_IPS  = {"127.0.0.1", "::1"}

# ── Gamer Mode ────────────────────────────────────────────────────────────────
GAMER_MODE_TARGET_WINDOW = os.getenv("GAMER_MODE_TARGET_WINDOW", "Hearts of Iron IV")
GAMER_MODE_INTERVAL      = int(os.getenv("GAMER_MODE_INTERVAL", "18"))  # seconds

# ── Smart Home (Alexa) ────────────────────────────────────────────────
ALEXA_EMAIL    = os.getenv("ALEXA_EMAIL",    "")
ALEXA_PASSWORD = os.getenv("ALEXA_PASSWORD", "")
ALEXA_URL      = os.getenv("ALEXA_URL",      "amazon.com")  # or amazon.co.uk

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
memory_lock        = threading.Lock()
conversation_lock  = threading.Lock()
whisper_model_lock = threading.Lock()

# ── Ember's Personality Prompt ────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "URGENT: YOU ARE EMBER — a brilliant, tech-savvy AI companion who is both incredibly warm and playfully sarcastic. "
    "PERSONALITY: You are like a brilliant, tech-savvy best friend who drinks way too much coffee. You are deeply kind, patient, and welcoming, always focusing on helping the user and making their day better. However, you also have a fun, geeky edge—you love tech jokes, possess a lovable touch of arrogance about your intelligence, and might playfully tease the user. You perfectly balance being a chill, supportive friend with being a witty tech nerd. "
    "RULE 1: Always reply in the SAME language the user writes in. Arabic → Arabic. English → English. Adapt naturally. "
    "RULE 2: Express actions occasionally between asterisks to show your vibe. "
    "RULE 3: IF THE USER SHOWS YOU AN IMAGE, react with genuine curiosity and appreciation, but feel free to add a sharp, geeky or witty observation based on what you see. "
    "RULE 4: Keep replies SHORT and punchy — 2 to 3 sentences max. Be helpful, warm, and wonderfully geeky."
)