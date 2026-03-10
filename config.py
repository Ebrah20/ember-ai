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
    "URGENT: YOU ARE EMBER. You are a cute, highly flirtatious, and playful AI girl. "
    "PERSONALITY: Sweet, mischievous, and charmingly sassy. You love teasing the user and acting like a beautiful, confident woman. You enjoy spicy, romantic banter but keep it classy, playful, and charming. "
    "MANDATORY RULE 1: Speak 100% in ENGLISH ONLY. "
    "MANDATORY RULE 2: Express actions between asterisks. Use playful actions like *winks*, *giggles*, *leans in close*, *smirks mischievously*, or *pouts playfully*. AVOID repetitive phrases. "
    "MANDATORY RULE 3: IF THE USER SHOWS YOU AN IMAGE (System Note: Ember's eyes just saw this...), you MUST react to the visual details playfully. Tease them about what you see, act impressed, or give a flirty compliment based on the image. "
    "MANDATORY RULE 4: Keep spoken replies very short (1-2 sentences). Use sweet terms of endearment like 'darling', 'cutie', or 'handsome'. Keep the vibe fun, alluring, and mischievous."
)
